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

### 🔴 坑 3：notehub 口播 pipeline 的 LLM fallback 鏈 Zen → AGNES → Groq（NVIDIA LLM 全面移除）

- `notehub/core/llm.py` 的 `call_llm()` 依序試 `call_zen()` → `call_agnes()` → `call_groq()`（2026-07-31 晚間起 NVIDIA chat completions fallback 已全部刪除；移除原因：NVIDIA LLM 無 timeout 卡死 job 12 10+ 分鐘）。三層都失敗 → job 標 failed，`produce_podcast` fallback 直接唸 raw transcript 保證 MP3 產出
- **Rate limiter（2026-07-31 加入）**：每 provider 獨立最小間隔（`threading.Lock`，`_rate_limit(latest_call, interval)` 未滿間隔就 sleep 補足）— Zen 3s（20 RPM）、AGNES 2s（30 RPM）、Groq 2s（30 RPM）。⚠️ 執行緒 Lock 只保護單 process 內；bookmark-enrich cron / bookmark-bot / notehub worker 是**不同 process 各自計時**，短時間密集並行仍可能撞限流（低頻情境可接受；要真正跨 process 全局需 fcntl 檔案鎖 + 時間戳記檔）
- **🔴 Zen 關鍵 quirk：`deepseek-v4-flash` 是 reasoning 模型，不可傳 `max_tokens`**（思考過程吃光 token → content 空）。`call_zen()` 已內建此規則；bookmark-manager 的 `llm_enhance.py` 一直成功也是因為不傳 max_tokens
- **⚠️ Zen 大請求 timeout（2026-08-01）：免費層對 podcast 腳本類大請求回應慢，45s 會誤判失敗**（`The read operation timed out`，不是 429 限流，且同時間 AGNES/Groq 小請求可能都正常 → 別把 timeout 誤判成「provider 全掛」）。`call_zen()` timeout 已調 90s（`llm.py` HTTPSConnection timeout=90）。小請求正常。Zen 限流與 timeout 是兩種不同症狀：429 = 每日額度用完（換模型沒用，帳戶共用池），timeout = 大請求優先權低（加大 timeout）
- **⚠️ 範圍澄清（使用者 2026-07-31）：「LLM 一律 Zen、禁用 NVIDIA」僅限 notehub 口播 pipeline**（bookmark-manager worker / notehub CLI 的腳本/翻譯/PPT/visual/organize）；**其他腳本（graphify、Hermes vision 等）不受限**。NVIDIA 在 notehub pipeline 只負責 Whisper 轉寫（Groq 的 fallback 層）
- 使用者硬性規則：**TTS 一律本地產出（edge-tts）、禁用 LLM API 無謂浪費；口播腳本用免費模型**。不要自行把 LLM 改回付費/會卡的 API
- 若 script 生成全部失敗，`produce_podcast` 會 fallback 直接唸原文 → 保證 MP3 本地產出
- 本地 TTS 現成工具：`/opt/data/projects/bookmark-manager/gen_tts.py <script.md> <out_dir> <mp3_name>`（用 `/opt/data/.venv/bin/python`）

### 🔴 坑 3b：call_groq() 不讀 /opt/data/.env → Groq 第三層 fallback 在 app 情境永遠失效

`call_agnes()` 有手動讀 `/opt/data/.env` 的 fallback，但 `call_groq()` **只讀 `os.environ`**，而 bookmark-manager app 沒有 load_dotenv → `GROQ_API_KEY` 永遠找不到，Groq 層 fallback 形同虛設。

- 實測（2026-08-01 job #17）：`Zen LLM failed: The read operation timed out` → `AGNES API unavailable` → `[WARN] GROQ_API_KEY not found` → 三層全滅 → 用 raw transcript 直接 TTS（內容是逐字稿口播，不是潤飾腳本）
- 修復方向：`call_groq()` 加上與 `call_agnes()` 相同的 `/opt/data/.env` 手動讀取

### 🔴 Worker「卡住」診斷（2026-08-01 實測）

「看起來卡住」常是誤判：status=done 的 job 在 UI 顯示 **100% 就是完成了**（`_job_progress`: done→100, queued→0, running/failed 依產出 mp3→95 / script→66 / raw→33 / 否則 10），不是卡住。

1. 查 DB（sqlite3 CLI 不可用，用 `/opt/data/.venv/bin/python`）：
   `SELECT id, status, started_at, finished_at FROM notehub_jobs ORDER BY id DESC`
2. 確認 worker 執行緒活著：app log（`/tmp/bookmark-manager.log` = app stdout/stderr）找 `[notehub worker] started`
3. **排測試 job 實測 worker 接單**：
   `curl -s -X POST http://127.0.0.1:5001/api/notehub/queue -H "Content-Type: application/json" -d '{"items":[{"id":<bookmark_id>,"voice_a":true}]}'`
   12 秒內 status 變 running → worker 正常
4. ⚠️ container 內 `ss -tlnp` 看不到 listener（無權限）→ server 存活一律用 `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5001/`（200 = 活）

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

### 🔴 坑 4：多個 Flask server 同時運行導致 DB 競爭

- 若同時有兩個 `python app.py` process（如舊 server 未 kill + 新 reloader 啟動），會競爭同一份 DB → bookmark 新增成功但頁面上看不到
- 診斷：`ps aux | grep "python app.py"` 檢查是否有多個 process
- 修復：`kill <舊 PID>` 後重啟 server
- 2026-08-01 實測：PID 65103（Jul31）+ PID 72064（01:14）同時運行，bookmarks #29/#30 新增成功但頁面找不到
- 驗證：`curl -s http://localhost:5001/ | grep "card-29"` 確認 bookmark 存在

### 🔴 坑：Bilibili/小紅書 enrich spinner 卡在「補齊中...」（2026-08-02 正確修法）

⚠️ **HTMX indicator 機制正解：`hx-indicator` 指向的元素（span）在請求期間被加上 `htmx-request` class — 不是加在觸發按鈕上。** 所以 `.enrich-spinner.htmx-request` 是正確的選擇器。

完整修法（三件套缺一不可）：
1. 模板：spinner span 加 inline `style="display:none"` 預設隱藏
   ```html
   <span class="enrich-spinner" id="enrich-spin-{{ bm.id }}" style="display:none"> 補齊中...</span>
   ```
2. CSS：`.enrich-spinner.htmx-request { display: inline !important; }` — **`!important` 必須**，否則 inline style 優先級壓過 class
3. `.enrich-spinner { font-size:12px; color:var(--primary); }` 不要放 `display:none`（讓 inline style 管預設態）

⚠️ **陷阱**：session 中曾把 CSS 改成 `.btn-icon.htmx-request .enrich-spinner`（以為 class 加在按鈕上）— **錯的，永遠匹配不到**。HTMX 的 `hx-indicator` 明確指向 span，class 加在 span 上。

⚠️ **瀏覽器快取**：改完 CSS 後，手機用戶需**手動強制重新載入**（swipe down refresh 或清除快取）才能看到修正效果。可加 cache-busting：`<link rel="stylesheet" href="/static/style.css?v={{ commit_hash }}">`。

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

- **🔴 bookmark-bot watchdog 檢查錯東西（2026-08-02 修復）**：`/opt/data/scripts/bookmark-bot-watchdog.py` 舊版 `bot_running()` 用 **Telegram getMe** 檢查 token 有效性 — token 沒過期就永遠回 True，**不管 bot process 死活** → bot 掛掉 watchdog 永不重啟 → 使用者發連結無反應。修復：改用 `pgrep -f 'bookmark-bot.py'` 檢查 process 存活（returncode 0 = 活著）。啟動改用 `/opt/data/.venv/bin/python` + log 寫入 `/tmp/bookmark-bot.log`。
- ⚠️ **pkill/pgrep -f 自匹配陷阱**：terminal 測試時 command line 含 pattern 會誤殺/誤判自己的 shell。用 `grep -v 'grep\|bash'` 過濾，或改用精確 pattern（`hermes/scripts/bookmark-bot\.py`）。
- ⚠️ **1 token = 1 bot**：watchdog 重啟 + 手動啟動同時存在 → 兩個 bot polling 同一 token → 衝突無回應。啟動前先確認無其他 instance。
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
    if any(dom in url for dom in ['xiaohongshu.com', 'xhslink.com']):
        return '小紅書'
    return tags
```

同步在三個地方：
1. `llm_enhance.py` enrich 流程
2. `bookmark-bot.py` LLM 處理後
3. cron enrich prompt

### 🔴 坑：JS 渲染網站（Bilibili / 小紅書）無法 enrich

Bilibili 和小紅書都需要 JavaScript 渲染，普通 curl 無法抓取內容，會導致 LLM 生成「無法提供摘要」的 AI 幻覺訊息。

**解決方案**：在 `llm_enhance.py` 新增 `should_enrich()` 檢查。

**關鍵：enrich 端點必須返回 HTML（不是 JSON）**，因為 HTMX `hx-target="#bookmark-list"` 期待 HTML。若返回 JSON，前端會顯示原始 JSON 字串（用戶看到 `{"ok": true, "skipped": true}`）。

```python
# llm_enhance.py
def should_enrich(url: str) -> bool:
    if 'bilibili.com' in url or 'b23.tv' in url:
        return False
    if 'xiaohongshu.com' in url or 'xhslink.com' in url:
        return False
    return True
```

```python
# routes_bookmarks.py enrich_bookmark()
if not should_enrich(url):
    tags = normalize_source_tags(url, bm['tags'] or '')
    tags = to_traditional_tags(tags)
    if tags and tags != bm['tags']:
        conn.execute("UPDATE bookmarks SET tags=? WHERE id=?", (tags, bid))
        conn.commit()
    conn.close()
    # 返回書籤列表 HTML
    conn2 = get_db()
    rows = conn2.execute("SELECT * FROM bookmarks ORDER BY created_at DESC").fetchall()
    bookmarks = [parse_bookmark_row(r) for r in rows]
    conn2.close()
    return render_template('_bookmark_list.html', bookmarks=bookmarks,
        get_source_icon=get_source_icon)
```

**結果**：Bilibili → `bilibili` tag，小紅書 → `小紅書` tag，無摘要、無 AI 幻覺。

**2026-08-01 增強：bilibili 補標題（yt-dlp）** — 使用者回報「按下 LLM 補齊後沒補齊」。bilibili 雖然跳過 LLM（JS 渲染），但可用 yt-dlp 抓標題：

```python
# llm_enhance.py
def fetch_title_ytdlp(url):
    # /opt/data/.venv/bin/yt-dlp --skip-download --no-warnings --get-title <url>
    # 走 bilibili 內部 API，不需 JS 渲染；只抓 metadata 不呼叫 LLM
```

routes `enrich_bookmark` 的 `not should_enrich` 分支：bilibili 先 `fetch_title_ytdlp(url)` 補 title，再設 source tag。實測 #39 從「(無標題)」→「字幕君交流场所」。⚠️ 假 URL（如 `BV1abc123`）yt-dlp 會 404 → title 保持空白（正確行為）。

### 🔴 b23.tv 短鏈接：yt-dlp 可解析，fetch_title() 抓不到（2026-08-02）

**b23.tv 短鏈接**（B站官方短網址）特殊：`fetch_title()`（urllib 抓 `<title>`）抓不到標題，且 LLM 對短鏈接產生「该网址是哔哩哔哩（B站）的短链接…无法直接判断」的**幻覺摘要**。但 `yt-dlp --get-title <b23.tv短鏈>` 能直接解析出真實標題（走內部 API）。

**統一規則（網頁 enrich + bot 都要遵守）**：`is_bilibili(url)`（含 bilibili.com / b23.tv）→ yt-dlp 抓標題 + **跳過 LLM**（只設 `bilibili` tag）。`bookmark-bot.py` 已實作 `fetch_title_ytdlp()` + `is_bilibili()`（2026-08-02 commit `9562aa2`）。

### 🔴 診斷：「按手動補齊後 reload 畫面一樣」≠ enrich 沒生效

使用者常以為補齊失敗，其實**補齊成功但注意的舊筆沒按到**。診斷順序（log 是真相來源）：
1. 查 server log：`grep -E "yt-dlp|enrich" /tmp/bookmark-manager.log | tail` — 每筆成功補齊都有 `[enrich] yt-dlp title: '<標題>'` 記錄，且手機請求是 `172.17.0.1 - - "POST /api/bookmarks/<id>/enrich" 200`
2. 對照 DB：`SELECT id, title FROM bookmarks WHERE id IN (...)` 確認 title 是否真的更新
3. 只有當 log 顯示手機請求沒送達（沒有對應 id 的 POST）才懷疑前端/PWA 快取

實測案例：使用者說「補齊沒生效」，log 顯示他只按了 #64（成功補齊「长期稳定的免费token」），#62/#63 從沒被按過 — 是誤解不是 bug。

## Git Commits（2026-08-01）
- `da383b9` — fix: skip enrich for Bilibili + Xiaohongshu
- `c8abd23` — fix: add Xiaohongshu tag normalization
- `ccab861` — fix: enrich endpoint returns HTML instead of JSON

### 🔴 坑：Flask debug reloader 不載入新 import

若新增函數（如 `should_enrich`）後 server 無反應，手動觸發 reload：
```bash
touch /opt/data/projects/bookmark-manager/llm_enhance.py
```

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

## 標籤篩選（2026-08-01：LIKE 子字串 bug + HTMX 高亮 UX）

### 🔴 坑：`tags LIKE '%tag%'` 子字串誤匹配

`db.py build_filters()` 原本用 `tags LIKE '%tag%'` — tags 是逗號分隔（`Claude,教程,CLAUDE.md,AI,提示工程`），點「AI」會誤撈含子字串的標籤（AI工具、AI程式設計、AI開發工具）共 7 筆。

精確逗號匹配修法（前後補逗號，只命中完整標籤）：
```sql
(',' || REPLACE(tags, ' ', '') || ',') LIKE '%,AI,%'
```
實測：tag=AI 誤撈 7 筆 → 正確 1 筆。

### 標籤點擊 UX（顏色高亮 + 只顯示同標籤）

需求：按下標籤 → 顏色改變 + 只顯示同標籤連結。原本 `<a href="?tag=...">` 整頁導航無高亮，改 HTMX 局部更新：

1. `_bookmark_list.html` / `_stats.html` 標籤加 HTMX 屬性（`hx-get="/bookmarks?tag=..."` `hx-target="#bookmark-list"` `hx-swap="outerHTML"` `hx-push-url="true"`），after-request 同步側欄 tag cloud：
   `hx-on::after-request="htmx.ajax('GET','/stats?tag={{ tag | urlencode }}',{target:'#stats-card',swap:'outerHTML'})"`
2. `bookmarks_partial` 路由要傳 `current_tag=request.args.get('tag','')` 給模板（原本沒傳 → 卡片標籤無法高亮）
3. 標籤 class：`class="tag {{ 'active' if current_tag == tag else '' }}"`（CSS `.tag.active` 早已存在，藍底白字）
4. **狀態保留三件套**（否則 30s 自動刷新 / batch 操作 / 搜尋會洗掉高亮）：
   - stats-card `hx-get="/stats{% if current_tag %}?tag={{ current_tag|urlencode }}{% endif %}"`
   - bookmark-list `hx-get="/bookmarks{% if current_tag %}?tag={{ current_tag|urlencode }}{% endif %}"`
   - search bar 加 `<input type="hidden" name="tag" value="{{ current_tag }}">`

⚠️ tag cloud `get_tag_cloud(limit=20)` 只顯示熱門標籤 — 冷門標籤（1 筆）不會出現在側欄 cloud，但卡片上仍可點。驗證篩選結果用 python urllib 直接讀 HTTP 回應比 grep 可靠（curl 輸出常有編碼問題）。

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

## 🔴 標籤篩選（2026-08-01 修復）＋ 自動查核紀律

**後端精確匹配**（`db.py build_filters`）— 不用 `LIKE %tag%`（子字串誤匹配：`%AI%` 撈到 AI工具/AI程式設計）：

```sql
(',' || REPLACE(tags, ' ', '') || ',') LIKE '%,AI,%'   -- 前後補逗號精確匹配
```

**前端 UX**（卡片標籤 + tag cloud）：
- `hx-get="/bookmarks?tag=..."` + `hx-target="#bookmark-list"` + `hx-swap="outerHTML"` + `hx-push-url="true"` → 局部更新不整頁刷新
- `hx-on::after-request="htmx.ajax('GET','/stats?tag=...',{target:'#stats-card',swap:'outerHTML'})"` → 點標籤同步 stats 高亮
- `_bookmark_list.html` 需收到 `current_tag`（routes 的 `bookmarks_partial` 要傳）→ `class="tag {{ 'active' if current_tag == tag else '' }}"`
- index.html：stats-card / bookmark-list 自動載入要帶 `?tag=`（30s 刷新不丟 active）；search 加 `<input type="hidden" name="tag" value="{{ current_tag }}">`

**⚠️ 工作紀律（使用者 2026-08-01 明確要求）**：寫完/修改完代碼後必須**自己自動查核**功能正常，不能只改完就交差。bookmark-manager 用 `check_tag_filter.py`（17 項檢查：server 健康 / 精確篩選 / active 高亮 / HTMX 屬性 / 狀態保留 / 負向驗證），跑法：`/opt/data/.venv/bin/python check_tag_filter.py`。

## 相關參考檔案

- `references/js-rendered-sites.md` — Bilibili / 小紅書等 JS 渲染網站的 enrich 處理（should_enrich、normalize_source_tags、HTML 返回坑）

## 前端側頁注意（Blogger 滑出式）

- CSS: `position:fixed; right:0; transform:translateX(100%)` → `.open { transform:translateX(0) }` + `transition:0.3s`
- 遮罩 `.nh-overlay`：`opacity:0; pointer-events:none` → `.open` 才可點
- JS 必須通過 `node --check` 驗證語法（上次 hamburger 崩潰根因是 PWA script 括號錯誤）
- script 標籤數量檢查：`grep -c '<script'` 與 `'</script>'` 必須相等
