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
| Synthesis | `notehub/core/synthesis.py` | 多來源合成（2026-08-06 Phase 5）|

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

## 📝 daily-review 報告格式（2026-07-31 用戶指示）

每日工作檢討報告（cron daily-review，每天 22:00）**必須同時記錄**：
1. **系統錯誤**：cron job 失敗、API 限流等
2. **代碼錯誤**：我改代碼過程中犯的錯，被你糾正的

## 📚 References

- `references/multi-source-synthesis.md` — NotebookLM 式多來源合成（2026-08-05）：決策已定（混合來源/兩階段/勾選入口）

## ⚠️ Pitfalls

20. **notehub 口播 pipeline 的 LLM 一律不用 NVIDIA** — 範圍限定本 pipeline，NVIDIA 只負責 Whisper 轉寫

32. **🔴 YouTube Shorts URL 偵測 bug（2026-08-04 實測，重做案例）** — `_extract_video_id()` 與 `YOUTUBE_PATTERNS` **都必須**包含 `youtube\\.com/shorts/`，否則 shorts 影片不被 `detect()` 認出 → fallback 到通用網頁抓取 → **把 YouTube 頁面雜訊（簡介/媒體/著作權/© Google LLC）當逐字稿** → LLM script 寫「內容不完整」道歉信 → podcast 唸道歉信。**症狀辨識**：raw.md 內容是 YouTube 頁面 chrome 文字 = extractor 誤判成通用網頁，不是影片真的沒字幕。已修：兩個 regex 都補 `youtube\\.com/shorts/`（extractors/youtube.py）。修復驗證：`_extract_video_id('https://youtube.com/shorts/XXXX')` 回 11 字元 id + `detect()` True，再接 `_fetch_via_api` 確認無字幕 → 走 Whisper fallback。

35. **🔴 小紅書 URL 直接抓會 SSL 失敗（2026-08-05 實測）** — `xhslink.com` 短鏈 / `xiaohongshu.com` 在台灣被 DNS 污染，notehub `URLExtractor` 用 urllib 直接抓 → `SSL: CERTIFICATE_VERIFY_FAILED self-signed certificate`，job 秒失敗（status=failed、finished 0 秒，錯誤樣本 job #24「英伟达开源AI视觉模型…」xhslink.com/m/8qWhW4ScJIU）。**已修**：`notehub/extractors/url.py` 新增 `_is_xhs_url()` + `_fetch_xhs()` 專用路徑（解法搬自 bookmark-manager `llm_enhance.py fetch_xiaohongshu_meta()`）：
   - 短鏈 302 追蹤：`curl -s -o /dev/null -w '%{url_effective}' -A <iPhone UA> -k -L`
   - DoH 查 **www 子域**真實 IP：`https://dns.google/resolve?name=www.xiaohongshu.com&type=A`（根域會拿到錯 IP）
   - `curl --resolve 'www.xiaohongshu.com:443:<IP>'` 繞 DNS 污染抓頁面（手機 UA + `-k`）
   - parse `window.__INITIAL_STATE__`（大括號平衡 + `undefined→null`）→ `noteData.data.noteData` 的 title/desc/tagList
   - 產出文字格式：`標題：…\\n<desc>\\n標籤：…`，title 取第一行去「標題：」前綴
   - **注意**：小紅書圖文筆記無逐字稿，口播 pipeline 以 title+desc+tags 為基礎擴寫屬預期；影片筆記目前未接 yt-dlp+Whisper，需另做。

36. **🔴 CLI `--synthesize` 參數解析 bug（2026-08-06 Phase 5 實測）** — 原始實作 `sources = [a for a in args[idx+1:] if not a.startswith("--")]` 只會過濾 flag 本身（`--lang`、`--podcast`），**不會過濾 flag 的值**（`zh`、`solo`、`台女`）。結果 `--lang zh` 的 `zh` 被當成 source URL → 來源清單含 `['url1', 'url2', 'zh']` → 合成報告多一筆「來源 3（zh）」處理失敗記錄、標題包含 zh 字樣。

   **正確修法**（已實作）：掃描時遇到 flag 跳過下一個值：
   ```python
   raw = args[idx + 1:]
   sources, skip_next = [], False
   for a in raw:
       if skip_next:
           skip_next = False
           continue
       if a.startswith("--"):
           skip_next = a in ('--lang', '--podcast', '--voice-a', '--voice-b')
           continue
       sources.append(a)
   ```
   **驗證指令**：`python3 -c "args=['--synthesize','url1','url2','--lang','zh']; ... print(sources)"` 應輸出 `['url1', 'url2']`。

   **端對端驗證**：跑 `python -m notehub --synthesize <url1> <url2> --lang zh` → 檢查 obsidian 報告 frontmatter 的 `sources:` 欄位（不含 `zh`）、報告標題無 `zh` 字眼、STDERR 無「來源處理失敗 zh」。