---
name: personal-bookmark-system
description: 自架書籤管理系統（Flask + HTMX + PWA + Telegram Bot + LLM 自動補齊 + Notehub 口播佇列）
trigger: 使用者提及 bookmark-manager、書籤管理、add2、URL收藏、bookmark-bot、@add2bm_bot、notehub 佇列、口播
---

# Personal Bookmark System

Flask + HTMX 自架書籤管理系統，支援 PWA、Telegram bot 一鍵收藏、LLM 自動補摘要與標籤、Notehub 口播工作佇列。

## 架構（已拆分，2026-07 完成）

```
app.py (18行, 僅 blueprint 註冊 + startup)
├── routes_bookmarks.py   書籤路由 Blueprint（14 端點）
├── routes_tags.py        標籤管理 + PWA Blueprint（7 端點）
├── routes_notehub.py     Notehub 佇列 Blueprint（queue/jobs API + 背景 worker）
├── db.py                 資料庫層（SQLite CRUD + notehub_jobs 操作）
├── llm_enhance.py        LLM 補齊層（fetch_title / llm_enhance / normalize_source_tags）
├── bookmark.py           單筆處理（不動，cohesion 0.39 良好範本）
└── schema.sql            bookmarks + tags + notehub_jobs 表
```

- **Port**: 5001
- **DB**: `/opt/data/projects/bookmark-manager/bookmarks.db`
- **啟動**: `cd /opt/data/projects/bookmark-manager && .venv/bin/python app.py`

## Notehub 工作佇列（☰ 側頁）

右上角 ☰ → Blogger 滑出式側頁（`translateX(100%) → 0` + 遮罩），顯示工作佇列：

```
次序號碼 | 工作名稱 | 口播選項（☑台女 ☐台男）
```

### 語音邏輯（queue API 自動判定）

| 勾選 | mode | CLI 參數 |
|------|------|----------|
| 僅台女 | solo | `--voice-a 台女` |
| 僅台男 | solo | `--voice-a 台男` |
| 兩者都勾 | **dual** | `--voice-a 台女 --voice-b 台男` |

### 非同步佇列設計

- `POST /api/notehub/queue` → 建立 jobs（status=queued）→ 立即回應
- 背景 worker（daemon thread）逐筆處理：queued → running → done/failed
- `GET /api/notehub/jobs` → 前端每 5 秒輪詢進度（⏳等待/🔄處理中/✅完成/❌失敗）
- 前端 `index.html` 的 batch「🎙️ 送 notehub」→ `openNotehubSidebar()`（不再同步送出）

### 進度條 + 產出 checkbox（2026-07-31 新增）

`GET /api/notehub/jobs` 每筆 job 回傳 `progress`（0-100）+ `artifacts`（{raw, script, mp3}）：

```python
# routes_notehub.py
def _job_progress(job):
    if status == 'done': return 100
    if status == 'queued': return 0
    # running/failed：依產出檔案 — mp3→95, script→66, raw→33, 否則 10
def _job_artifacts(job):
    # 從 worker 存的 output（notehub stderr）parse 標記行：
    #   Raw saved|_raw.md → 逐字稿
    #   Script saved|script.md → 整理過文字檔
    #   Podcast saved|_podcast.mp3 → 音檔
    # done 狀態兜底視為全產出
```

前端渲染（`pollNotehubJobs`）：標題行 + `%` → 進度條（`.nh-bar.${status}`，done=綠/running=藍/failed=紅/queued=黃）→ 3 個 disabled checkbox（☑逐字稿 ☑整理過文字檔 ☐音檔）。

⚠️ **輸出標記行依賴**：前端 artifacts 判斷依賴 worker output 中的 notehub stderr 標記行（`Raw saved` / `Script saved` / `Podcast saved`）。**不要改動 notehub pipeline 的這些 print 格式**，否則佇列 UI 的 checkbox 會失效。worker 存 output 用 `(stderr or stdout)[-500:]`——注意截斷可能影響早期標記（Raw saved 在最前面），若 artifacts 判斷不準可提高截斷長度。

### 🔴 重大坑：worker 的 python 必須用 /opt/data/.venv

notehub CLI 需要 `openai` + `edge_tts`：
- bookmark-manager 的 `.venv`：**沒有 openai**（`ModuleNotFoundError: No module named 'openai'`）
- `/opt/hermes/.venv`：有 openai 但**沒有 edge_tts**（TTS 步驟才失敗，pipeline 吞錯誤照樣 done）
- **`/opt/data/.venv`：兩者都有 ✅（唯一正確選擇）**

```python
# routes_notehub.py 內（正確寫法）
NOTEHUB_PYTHON = '/opt/data/.venv/bin/python'  # openai + edge_tts 都有
cmd = [NOTEHUB_PYTHON, '-m', 'notehub', job['url'], '--podcast', job['mode'], '--lang', 'zh']
```

### 🔴 坑 2：notehub CLI 的錯誤在 stderr，且 pipeline 會吞 podcast 錯誤

- `produce_podcast` 被 pipeline 的 try/except 包住，失敗只 print `[ERROR] Podcast failed: ...` 到 stderr，**returncode 仍為 0** → worker 會誤標 done
- worker 取 output 時**必須優先 stderr**：`(result.stderr or result.stdout or '')[-500:]`，否則 stdout 會蓋掉真正錯誤
- 驗證 MP3 是否真的產生：`find /opt/data -name "*.mp3" -mmin -10`

### 🔴 坑 3：notehub 口播 pipeline 的 LLM 一律只走 OpenCode Zen（2026-07-31 晚間起，NVIDIA LLM 全面移除）

- `notehub/core/llm.py` 的 `call_llm()` 只呼叫 `call_zen()`（`opencode.ai/zen/v1` + `deepseek-v4-flash-free`，免費免 Key，http.client 直連）——**NVIDIA chat completions fallback 已全部刪除**（移除原因：NVIDIA LLM 無 timeout 卡死 job 12 10+ 分鐘）
- **🔴 Zen 關鍵 quirk：`deepseek-v4-flash` 是 reasoning 模型，不可傳 `max_tokens`**（思考過程吃光 token → content 空）。`call_zen()` 已內建此規則；bookmark-manager 的 `llm_enhance.py` 一直成功也是因為不傳 max_tokens
- **⚠️ 範圍澄清（使用者 2026-07-31）：「LLM 一律 Zen、禁用 NVIDIA」僅限 notehub 口播 pipeline**（bookmark-manager worker / notehub CLI 的腳本/翻譯/PPT/visual/organize）；**其他腳本（graphify、Hermes vision 等）不受限**。NVIDIA 在 notehub pipeline 只負責 Whisper 轉寫（Groq 的 fallback 層）
- 使用者硬性規則：**TTS 一律本地產出（edge-tts）、禁用 LLM API 無謂浪費；口播腳本用免費模型**。不要自行把 LLM 改回付費/會卡的 API
- 若 script 生成全部失敗，`produce_podcast` 會 fallback 直接唸原文 → 保證 MP3 本地產出
- 本地 TTS 現成工具：`/opt/data/projects/bookmark-manager/gen_tts.py <script.md> <out_dir> <mp3_name>`（用 `/opt/data/.venv/bin/python`）

### 清除功能（2026-07-31 新增）

**設計定案（使用者討論）：失敗→清紀錄+刪半成品；完成→只清紀錄。**

API：
- `DELETE /api/notehub/jobs/<id>` — 單筆 ✕（done/failed 才允許；**running/queued 回 400 拒絕**）
- `POST /api/notehub/jobs/clear` body `{scope: 'done'|'failed'}` — 批次；running/queued 永不參與

UI：佇列頂部「🧹 清已完成」「🗑️ 清失敗」+ 每筆 ✕（done/failed 才顯示）。

🔴 **半成品刪除安全規則**（`_delete_job_artifacts`）：
- **只刪 output 中明確標記 `Raw saved:` / `Script saved:` / `Podcast saved:` 路徑的檔案**
- failed job 的 output 通常只有 traceback（無路徑標記）→ 只清紀錄，檔案不動
- 永不猜測目錄、永不刪未標記檔案——避免誤刪同 bookmark 其他 job 的成果（job 11/12 同 bookmark 案例）

🔴 **坑：sqlite3.Row 沒有 `.get()`** — `SELECT *` 直接查回傳 Row（支援 `[]` 不支援 `.get()`）。`_delete_job_artifacts` 內用 `job['output']`。若 job 來自 `get_notehub_jobs()`（已轉 dict）才可用 `.get()`。

🔴 **坑：Flask debug reloader 競態** — 同時改多個檔案（db.py + routes_notehub.py）時，reloader 可能在「import 新符號的瞬間」重啟 → `ImportError: cannot import name 'X'` → server 死（HTTP 000）。改多檔案後務必確認 server 存活：`curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5001/`，掛了就重啟。

### 驗證方式

```bash
curl -s -X POST http://127.0.0.1:5001/api/notehub/queue -H "Content-Type: application/json" \
  -d '{"items":[{"id":14,"voice_a":true,"voice_b":false}]}'
curl -s http://127.0.0.1:5001/api/notehub/jobs
```

notehub 產出：`/opt/data/obsidian-vault/notes/<標題> [hash]/` 內含 `script.md` + `_raw.md`。

## Web UI (Flask + HTMX)

### 卡片操作按鈕順序（_bookmark_list.html）

```
☆ 🤖 🔴/✅ 📋 ✏️ 🗑️
```

### Batch 操作（index.html）

選取後出現 batch bar，操作完成後呼叫 `refreshWithDelay()`（3 秒延遲）：

```js
function refreshWithDelay() {
    setTimeout(() => {
        htmx.trigger('#bookmark-list', 'load');
        htmx.trigger('#stats-card', 'load');
    }, 3000);
}
```

### 編輯功能

- `GET /api/bookmarks/<id>/edit-form` → 回傳 inline edit form (HTMX fragment)
- `PUT /api/bookmarks/<id>/update` → 更新 title/summary/tags

### LLM 自動補齊（🤖 按鈕）

- `POST /api/bookmarks/<id>/enrich`
- 抓 title → 呼叫 OpenCode Zen API → 更新 summary + tags + processed=1
- 使用 `http.client`（非 urllib，因 OpenCode 會擋 urllib → 403）

## Telegram Bot (@add2bm_bot)

輕量 bot，零依賴（stdlib only）。

### 路徑

- 腳本: `/opt/data/.hermes/scripts/bookmark-bot.py`
- Token: `/opt/data/.bookmark-bot-token`
- Watchdog: `bookmark-bot-watchdog.py` (cron 每 5 分鐘)

### 坑

- **urllib.request 連 OpenCode Zen 會 403** → 改用 `http.client.HTTPSConnection`
- **Bot token 不能重複 polling** → 同 token 開多個 process 會 Conflict error
- **getUpdates offset 必須永遠前進** → 即使處理失敗也要 `update_id + 1`，避免無限循環

### 啟動

```bash
exec python3 /opt/data/.hermes/scripts/bookmark-bot.py "$(cat /opt/data/.bookmark-bot-token)"
```

## 標籤強制規範（normalize_source_tags）

來源強制統一，避免 LLM 隨意產生不同寫法：

```python
def normalize_source_tags(url, tags):
    if any(dom in url for dom in ['bilibili.com', 'b23.tv']):
        return 'bilibili'
    return tags
```

同步在三個地方：
1. `llm_enhance.py` enrich 流程
2. `bookmark-bot.py` LLM 處理後
3. cron enrich prompt

## 標籤繁簡轉換（2026-07-31 使用者硬性規則）

**bookmark 產生的簡體中文標籤一律翻譯繁體中文**（台灣用語）。單點實作在 `db.py`：

```python
# db.py — to_traditional_tags()：opencc s2twp，lazy import
def to_traditional_tags(tags):
    if not tags: return tags
    # import opencc; _trad_converter = opencc.OpenCC('s2twp')
    # 逐個 tag convert 再 join；缺 opencc 時原樣回傳（不阻斷寫入）
```

套用於 **4 個標籤寫入點**（`routes_bookmarks.py`）：
1. `add_bookmark` INSERT（涵蓋 Telegram bot / API 來源）
2. enrich UPDATE（LLM 自動標籤）
3. `bookmark_update`（Web UI 編輯）
4. batch `tag` action（批次加標籤）

既有資料 backfill：掃描 `bookmarks.tags`，`converted != original` 的筆數 UPDATE + `sync_tags_from_bookmark`。

### 🔴 坑：bookmark-manager/.venv 缺 opencc → lazy import 靜默失敗

- **server 用專案自己的 venv**（`cd /opt/data/projects/bookmark-manager && .venv/bin/python app.py` → `bookmark-manager/.venv`），**不是** `/opt/data/.venv`
- `bookmark-manager/.venv` 原本**沒有 opencc** → `to_traditional_tags` 的 `import opencc` 失敗 → except 回傳原值（**靜默失敗，DB 照樣存簡體**）
- 修復：`uv pip install opencc-py --python .venv/bin/python`（裝到專案 venv）
- 驗證：POST `{"tags":"机器学习"}` → DB 應存 `機器學習`（lazy import 設計讓 server 不需重啟）

## LLM enrichment cron

- 每 10 分鐘掃 `processed=0` 的書籤
- 抓頁面 → LLM 摘要+標籤 → 更新 DB
- Bilibili 來源需強制設 tag = "bilibili"

## Tailscale Serve

```bash
tailscale serve --https=443 off
tailscale serve --bg --https=443 localhost:5001
```

## PWA

- `manifest.json`, `sw.js` 在 `static/`
- `Service-Worker-Allowed: /` header 必須設
- 子路徑部署時所有 URL 必須用相對路徑（無前綴 `/`）

## 拆分工作流（已完成版本）

app.py 已從 766 行 / 53 函數 / cohesion 0.10 拆成上述模組結構（cohesion 0.21~0.31，2~3 倍提升）。未來再拆分時遵循：

1. **確認 git 開啟、工作區乾淨** — `git status --short`，確保可隨時 `git checkout HEAD` 回滾
2. **列出拆分計劃給使用者確認** — 目標結構、搬哪些函數、哪些檔案不動，等使用者點頭
3. **建立 checkpoint list（todo）** — 每步動作 + 驗證方式 + 通過標準；每完成一步 `git commit`（繁體中文訊息）
4. **確認後才開始改碼**；任何一步驗證失敗 → `git checkout` 回滾，不硬撐
5. 拆完用 `graphify update .` 增量更新圖譜，對比 cohesion 確認改善

## 前端側頁注意（Blogger 滑出式）

- CSS: `position:fixed; right:0; transform:translateX(100%)` → `.open { transform:translateX(0) }` + `transition:0.3s`
- 遮罩 `.nh-overlay`：`opacity:0; pointer-events:none` → `.open` 才可點
- JS 必須通過 `node --check` 驗證語法（上次 hamburger 崩潰根因是 PWA script 括號錯誤）
- script 標籤數量檢查：`grep -c '<script'` 與 `'</script>'` 必須相等
