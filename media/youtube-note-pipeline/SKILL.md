---
name: youtube-note-pipeline
description: YouTube/IG/Bilibili 影片轉口播 podcast 完整流程。Notehub CLI + bookmark-manager 整合。
related_skills: [verified-capabilities, taiwan-stock-data-pipeline, instagram-reel-podcast]
---

# NoteHub YouTube Pipeline

## 🎯 功能總覽

完整影片處理流程：YouTube/IG/Bilibili → Whisper 轉寫 → LLM 整理 → TTS 口播

## 📋 核心模組

| 模組 | 路徑 | 功能 |
|------|------|------|
| Pipeline | `notehub/core/pipeline.py` | 主流程協調 |
| LLM | `notehub/core/llm.py` | 多 provider fallback chain |
| Transcribe | `notehub/core/transcribe.py` | Whisper 三層 fallback |
| Podcast | `podcast.py` | 口播腳本生成 + TTS |
| Extractors | `notehub/extractors/` | YouTube/IG/Bilibili |

## 🔧 LLM Fallback Chain（2026-08-01 更新）

### notehub pipeline（口播腳本）
```
1. OpenCode Zen (deepseek-v4-flash-free) — 20 RPM
   ↓ 429 限流
2. AGNES API (agnes-2.5-flash) — 20 RPM
   ↓ 失敗
3. Groq (llama-3.3-70b-versatile) — 30 RPM
   ↓ 失敗
4. 本地正則 (add_punctuation.py) — ∞
```

### bookmark-manager（書籤 enrich）
```
1. OpenCode Zen (deepseek-v4-flash-free)
   ↓ 429 限流
2. AGNES API (agnes-2.5-flash)
   ↓ 失敗
3. Groq (llama-3.3-70b-versatile)
   ↓ 失敗
4. 空回應（tags 保持不變）
```
- 兩者共享同一套 fallback 邏輯，但獨立實現（不共用程式碼）
- Zen 限流時 bookmark-manager 的 enrich 仍會成功（自動切換）

## 📊 Provider RPM 限制

| Provider | 模型 | RPM | 狀態 |
|----------|------|-----|------|
| OpenCode Zen | deepseek-v4-flash-free | 20 | ✅ 已恢復（2026-08-01 23:00 實測 HTTP 200）|
| AGNES | agnes-2.5-flash | 20 | ✅ 正常 |
| Groq | llama-3.3-70b-versatile | 30 | ✅ 可用 |
| 本地正則 | add_punctuation.py | ∞ | ✅ 備用 |

## 🔑 API Key 讀取陷阱（2026-07-31 實測）

從 `.env` 讀取 API key 時，**必須去除換行符**：
```python
# ❌ 錯誤：會帶換行 → Authorization header 無效
key = os.environ.get('OPENCODE_ZEN_API_KEY', '')

# ✅ 正確：strip + 去除換行
with open('/opt/data/.env') as f:
    for line in f:
        if line.startswith('OPENCODE_ZEN_API_KEY='):
            key = line.split('=', 1)[1].strip()
            break
```

curl 測試時用 shell 變數也要 `tr -d '\n\r'`：
```bash
export KEY=$(grep "^OPENCODE_ZEN_API_KEY=" /opt/data/.env | cut -d= -f2- | tr -d '\n\r')
```

HTTP 43 / HTTP 000 錯誤通常是 header 格式問題，先檢查 key 是否有換行。

## 📝 daily-review 報告格式（2026-07-31 用戶指示）

每日工作檢討報告（cron daily-review，每天 22:00）**必須同時記錄**：
1. **系統錯誤**：cron job 失敗、API 限流等
2. **代碼錯誤**：我改代碼過程中犯的錯，被你糾正的

### 報告格式
```
# 每日工作檢討報告 - YYYY-MM-DD

## 執行摘要
- 今日工作：N 項 cron job + M 項代碼修改
- 成功：X 項 cron + Y 項代碼
- 失敗：A 項 cron + B 項代碼
- 待跟进：C 項

---

## 問題清單（系統錯誤）
### 問題 1：[標題]
- What/Why/When/Where/Who/How/Impact/改善方案

---

## 代碼修改錯誤清單（我犯的錯，被用戶糾正）
### 錯誤 1：[標題]
- What: [犯了什麼錯]
- Why: [為什麼犯錯]
- When: [時間]
- Where: [檔案位置]
- Who: 我（Agnes）
- How: [如何被糾正（用戶說了什麼）]
- Impact: [影響]
- 修正: [如何修正]
- 教訓: [學到什麼]

---

## 修復記錄
| 問題 | 修復時間 | 狀態 |

---

## 經驗教訓
1. **[教訓標題]**
   - [說明]

---

## 明日重點
1. [重點]
```

### 數據來源
1. cron 錯誤：`cat /opt/data/cron/jobs.json | python3 -c "..."`
2. git 歷史：`git log --since="today" --oneline`
3. session 錯誤：`session_search(query="錯誤 失敗 用戶糾正")`

### 完整實例
參見 `/opt/data/obsidian-vault/Holographic/每日檢討/2026-07-31-工作檢討.md`

## 🔒 RPM 限流保護（pitfall 22）

```python
# llm.py 中的 rate limiters
_zen_interval = 3.0   # 20 RPM
_agnes_interval = 3.0 # 20 RPM
_groq_interval = 2.0  # 30 RPM

def _rate_limit(latest_call: float, interval: float) -> float:
    with _rate_lock:
        elapsed = time.time() - latest_call
        if elapsed < interval:
            time.sleep(interval - elapsed)
        return time.time()
```

**🔴 規則**：任何 LLM 呼叫必須經過 `_rate_limit()`，禁止直接 `requests.post()`

## 📝 使用方式

```bash
# CLI
cd /opt/data/skills/media/youtube-note-pipeline/scripts
python -m notehub <url> --podcast solo --lang zh

# 直接呼叫
from notehub.core.llm import call_llm
result = call_llm([{'role': 'user', 'content': '...'}])
```

## 📚 References

- `references/zen-free-tier-limits.md` — Zen 免費層共享額度研究（big-pickle 無額度優勢、IP 層限流、GitHub 證據鏈）
- `references/llm-rate-limit-landscape.md` — 跨 process 限流地圖 + 全局檔案鎖方案

## ⚠️ Pitfalls

19. **抽共用模組前先調查既有實作** — 血的教訓：bilibili.py 的 `_check_size_and_compress` 早已存在，未參考導致重寫出缺陷版本

20. **notehub 口播 pipeline 的 LLM 一律不用 NVIDIA** — 範圍限定本 pipeline，NVIDIA 只負責 Whisper 轉寫

21. **Zen API 限流 fallback 流程** — 當 Zen 429 時，自動切換到 AGNES API（agnes-2.5-flash）

22. **RPM 限流保護** — 每個 provider 都有 `_rate_limit()`，避免 429 限流或封號

23. **Provider RPM 限制調查** — OpenCode Zen 未公開 RPM（實際被限），AGNES ~20 RPM，Groq 30 RPM / 6K TPM

24. **daily-review 報告格式（2026-07-31 用戶指示）** — 必須同時記錄「系統錯誤」+「代碼錯誤」。代碼錯誤格式：What/Why/When/Where/Who/How/Impact/修正/教訓。數據來源：cron/jobs.json + git log + session_search

25. **Zen FreeUsageLimitError 狀態（2026-08-01）** — 當日 21:14 仍在限流（retry-after 39372s ≈ 11h），**23:00 已恢復**（三層 provider 實測 HTTP 200）。診斷指令：`curl -s https://opencode.ai/zen/v1/chat/completions -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" -d '{"model":"deepseek-v4-flash-free","messages":[{"role":"user","content":"hi"}],"max_tokens":5}'`，成功回應 JSON 才算恢復。**限流週期實測：16-24h 重置，一天內可能用完又恢復**。

26. **bookmark-manager LLM Fallback（2026-08-01 實測）** — `llm_enhance.py` 已改為多 provider fallback：Zen → AGNES → Groq。當 Zen 429 時自動切換，不中斷 enrich 流程。

27. **簡體標籤統一轉換** — 所有 bookmark 新增/更新都會經過 `to_traditional_tags()` 轉換，避免同意思標籤有簡體+繁體兩版。已有 backfill 腳本處理既有資料。

28. **跨 process 限流缺口（2026-08-01 調查）** — `_rate_limit()` 的 `threading.Lock` 只擋單 process；bookmark-enrich cron、bookmark-bot.py 打 Zen **無限流**（各自計時互不知情）。完整地圖（誰打哪個 LLM、現有 interval、風險評估）與全局檔案鎖方案（fcntl + state file）見 `references/llm-rate-limit-landscape.md`。決策待使用者確認：A（全域檔案鎖）/ B（錯開 cron 時間）。**風險評估補充：低頻 cron（10 分鐘 5 筆）其實離 20 RPM 很遠，threading.Lock 已夠；只有多密集 worker 並行才需要檔案鎖。**

29. **Zen 免費層共享額度（2026-08-01 上網查證）** — Zen 免費模型**共用同一帳戶/IP 額度池**（~100 req/day），**big-pickle 不會比 deepseek-v4-flash-free 多**（GitHub #15714/#33318/#28166 證據）。FreeUsageLimitError 是 **IP 層級限流**（ipRateLimiter.ts），有付費餘額也躲不掉。換模型不會增加可用量；要降用量只能減請求數 + RPM 限流 + fallback 鏈。big-pickle 本身還更不穩（5/18 routing bug #28141、"too many requests" loop #10404）— notehub 主用 deepseek-v4-flash-free 是對的選擇。

30. **Zen timeout ≠ 429（2026-08-01 實測）** — 大請求（產生 podcast 腳本）在 Zen 免費層優先權低，45s 會 `The read operation timed out` 被當失敗；小請求（摘要）正常。**兩個不同症狀：429 FreeUsageLimitError = 每日額度用完；timeout = 大請求回應慢**。`call_zen()` timeout 已調 **45s → 90s**（llm.py:206）。job 顯示「Zen LLM failed: The read operation timed out」≠ 限流，別誤判為 429。

31. **fallback 無狀態設計（2026-08-01 驗證）** — `call_llm()` 每次呼叫**先試 Zen**，只有失敗才 fallback AGNES → Groq，無持久化狀態檔。**Zen 恢復後自動調回，不需手動切換**。若 Zen 卡死較久想快速回到 Zen：直接重試 job 即可，不用改任何 code。

32. **🔴 YouTube Shorts URL 偵測 bug（2026-08-04 實測，重做案例）** — `_extract_video_id()` 與 `YOUTUBE_PATTERNS` **都必須**包含 `youtube\.com/shorts/`，否則 shorts 影片不被 `detect()` 認出 → fallback 到通用網頁抓取 → **把 YouTube 頁面雜訊（簡介/媒體/著作權/© Google LLC）當逐字稿** → LLM script 寫「內容不完整」道歉信 → podcast 唸道歉信。**症狀辨識**：raw.md 內容是 YouTube 頁面 chrome 文字 = extractor 誤判成通用網頁，不是影片真的沒字幕。已修：兩個 regex 都補 `youtube\.com/shorts/`（extractors/youtube.py）。修復驗證：`_extract_video_id('https://youtube.com/shorts/XXXX')` 回 11 字元 id + `detect()` True，再接 `_fetch_via_api` 確認無字幕 → 走 Whisper fallback。

33. **Shorts 很短，逐字稿短是正常的** — 12 秒 Shorts 的完整台詞只有 ~49 字（列舉式），Whisper 轉寫正確但極短。**重做/除錯前先驗證影片時長**：`yt-dlp --print "%(duration)s 秒" <url>`。LLM 口播腳本會以真實台詞為基礎大幅擴寫 — **回報時誠實告知真實 vs 生成的比例**，不要讓使用者誤以為那 49 字是「內容不足」或把擴寫冒充原話。

34. **notehub 輸出目錄可能變（notes/ vs 口播/）** — 完成檔可能在 `obsidian-vault/notes/` 或 `obsidian-vault/口播/`（依 notehub 版本/設定）。回答「檔案在哪」**別硬編碼目錄**，以 job output 的 `✅ Pipeline complete! Output:` 行或 UI paths 欄位為準（worker output 是唯一真相來源）。