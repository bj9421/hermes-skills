---
name: verified-capabilities
description: "📋 已驗證可跑通功能總盤點（Verified Capabilities Inventory）— 本機 RPi4/Docker 環境中實測通過的功能清單，含呼叫方式、驗證日期、狀態與關鍵坑。需要調用任何既有功能時先查這份清單。"
platforms: [linux]
---

# ✅ 已驗證可跑通功能總盤點

> 本清單記錄**實測通過**的功能（非理論可用）。每個條目含：呼叫方式（可直接複製）、驗證日期、狀態、關鍵坑。
> 更新原則：新功能驗證通過 → 補上；功能失效 → 標 ⚠️。

## 🔧 環境基礎

| 項目 | 內容 |
|------|------|
| Python 環境 | **`/opt/data/.venv/bin/python`**（唯一全依賴環境：openai + edge_tts + pydub + opencc + groq + riva + faster-whisper） |
| ❌ 錯誤環境 | `/opt/hermes/.venv`（缺 edge_tts）、`/opt/data/projects/*/.venv`（缺 notehub 依賴）、`uv run`（Docker 無權限） |
| API keys | `/opt/data/.env`：GROQ_API_KEY、NVIDIA_API_KEY（NVIDIA 免費 tier 40 RPM） |
| Obsidian vault | `/opt/data/obsidian-vault/`（Syncthing 同步，寫入須 chmod -R 777） |
| notehub 模組 | `/opt/data/skills/media/youtube-note-pipeline/scripts/notehub/`（**非 pip 套件**，需 cd scripts 或設 PYTHONPATH） |

**環境驗證指令：**
```bash
/opt/data/.venv/bin/python -c "import edge_tts, pydub, openai, opencc; print('all deps OK')"
```

## 🤖 LLM 服務

### 1. OpenCode Zen（deepseek-v4-flash-free）✅ 2026-07-31 驗證
**用途：** 口播腳本生成、書籤摘要（免費免 Key）
```python
# http.client 直連（urllib→403 的坑）
conn = http.client.HTTPSConnection('opencode.ai', timeout=45)
conn.request('POST', '/zen/v1/chat/completions', body, {'Content-Type': 'application/json'})
# model: 'deepseek-v4-flash-free'
```
- 🔑 **關鍵坑：deepseek-v4-flash 是 reasoning 模型，不可傳 max_tokens**（思考吃光 token → content 空）
- 現成函數：`notehub/core/llm.py` 的 `call_zen(messages, temperature=0.7)`
- 驗證：notehub job 10 口播腳本 3.1KB 生成成功

### 2. NVIDIA LLM（deepseek-ai/deepseek-v4-flash）⚠️ fallback only
- `integrate.api.nvidia.com/v1` + NVIDIA_API_KEY，OpenAI SDK 相容
- 2026-07-31 發生長時間無回應（chat completion timeout），**已降為 Zen 的 fallback**（`call_llm()` 邏輯）
- 📋 **無回應處理（2026-07-31 anysearch 查證）：免費 tier 無 SLA、無保證回應時間（共享 GPU 叢集）；504/403/429 是普遍已知問題，非環境特例；rate limit（40 RPM）官方明確無法提升（唯一正解付費自架 NIM）。** 對策：①不當主路徑（已做——Zen 優先）②fallback 已有 3-retry exponential backoff ③熱門模型（deepseek-v4-pro）易卡，可換低流量模型 ④持續 403/504 = 帳號層級，等 cooldown（30s-2h+ 不確定）
- 坑：free tier 40 RPM + 503 ResourceExhausted 不確定 cooldown

### 3. Groq Whisper（STT）✅ 2026-07-31 驗證
```bash
# whisper-large-v3，GROQ_API_KEY
# >10MB 檔案先壓 opus 32k（ffmpeg），否則 413
```
- 5.5s 音檔 → 23 chars 轉寫，~10s 完成

## 🎙️ 語音 / 音訊

### 4. edge-tts（TTS 本地產出）✅ 2026-07-26 / 07-31 驗證
**使用者硬性規則：TTS 一律本地產出，禁用 LLM API 無謂浪費**
```bash
# 直接產 MP3（工具：/opt/data/projects/bookmark-manager/gen_tts.py）
/opt/data/.venv/bin/python gen_tts.py <script.md> <out_dir> <mp3_name>
```
- 台女 `zh-TW-HsiaoChenNeural` / 台男 `zh-TW-YunJheNeural`
- 分段策略：≤200 chars/段 + `asyncio.sleep(2)` + 3 retry + ffmpeg concat
- 驗證：蚊子愛叮誰呢？ 634 chars → 133s / 1MB MP3，<1 分鐘，0 API

### 5. NVIDIA Whisper（gRPC）✅ 2026-07-31 驗證
```python
# notehub/core/transcribe.py 的 _transcribe_nvidia()
# server: grpc.nvcf.nvidia.com:443
# function-id: b702f636-f60c-4a3d-a6f4-f3568c13bd7d（whisper-large-v3 固定）
# 依賴：nvidia-riva-client（已裝 /opt/data/.venv）
```
- 🔑 音訊先 ffmpeg 轉 **wav 16-bit mono 16kHz**，讀**整個檔**（含 header）
- 🔑 config 加 `add_custom_configuration_to_config(config, "task:transcribe")`
- 🔑 結果欄位是 **`alternatives[].transcript`**（不是 text！）
- 驗證：「这是第二段测试,验证NVIDIA Whisper Fallback是否正常运作。」✅

### 6. 本地 faster-whisper ✅ 2026-07-31 驗證
```python
# small/int8 CPU（RPi），HF cache 必須設：
os.environ["HF_HOME"] = "/opt/data/.cache/huggingface"
os.environ["HF_HUB_CACHE"] = "/opt/data/.cache/huggingface/hub"
```
- 坑：Docker 中 `/root/.cache` 無寫入權限 → Permission denied
- 模型 small 已下載（464MB）；輸出簡體 → pipeline opencc 轉繁體

### 7. Whisper fallback chain（統一入口）✅ 2026-07-31 驗證
**使用者硬性規則：Groq → NVIDIA → 本地 faster-whisper**
```python
from notehub.core.transcribe import transcribe_audio
text = transcribe_audio('/path/audio.m4a', language='zh')  # 自動三層 fallback
```
- youtube / bilibili / instagram 三個 extractor 已統一使用

## 🔄 管線

### 8. notehub CLI（多來源 → 筆記 + 口播 + PPT + Visual）✅ 2026-07-31 驗證
```bash
cd /opt/data/skills/media/youtube-note-pipeline/scripts && \
  /opt/data/.venv/bin/python -m notehub "URL" --podcast solo --lang zh 台女
```
- 支援：YouTube（transcript-api → VTT → Whisper 三策略）/ Instagram / URL / PDF / 文字檔
- 口播腳本：Zen 免費模型 → NVIDIA fallback → 原文兜底
- TTS：本地 edge-tts；輸出目錄：YouTube/IG → `口播/`、URL/PDF/text → `notes/`（需手動搬）
- 驗證：job 10 完整流程（bookmark → worker → Zen 腳本 → 本地 TTS → MP3 3.9MB）✅

### 9. yt2md_pipeline（legacy YouTube 專用）✅
```bash
/opt/data/.venv/bin/python yt2md_pipeline.py "URL" --obsidian
```

### 10. Bilibili 手動流程 ✅ 2026-07-26 驗證
```bash
yt-dlp -x --audio-format m4a -o "/tmp/audio/%(id)s.%(ext)s" "URL"  # 下載音訊
ffmpeg -y -i <id>.m4a -c:a libopus -b:a 32k <id>.opus             # 壓縮（Groq 413 fix）
# Groq Whisper 轉寫 → notehub 處理
```
- 驗證：12 分鐘 Bilibili → 4510 chars 轉寫 → 34-line script → 266s MP3（<5 分鐘）

### 11. bookmark-manager 口播佇列 ✅ 2026-07-31 驗證
```bash
# Flask port 5001，Telegram 觸發 add2 <url>
curl -X POST http://127.0.0.1:5001/api/notehub/queue -H "Content-Type: application/json" \
  -d '{"items":[{"id":<bookmark_id>,"voice_a":true,"voice_b":false}]}'
```
- worker 必須用 `/opt/data/.venv/bin/python`（坑：用錯環境 → 只有 script.md 無 MP3）
- DB：`/opt/data/projects/bookmark-manager/bookmarks.db`、job 表 `notehub_jobs`

## 🛠️ 其他驗證過的工具

| 功能 | 狀態 | 呼叫方式 |
|------|------|---------|
| opencc 繁中轉換（s2twp） | ✅ | pipeline `_convert_to_traditional()` 自動；bookmark 標籤 `to_traditional_tags()`（db.py）4 寫入點 + backfill；已知過轉換：指令碼→腳本、全域性→全局 |
| PPT 生成（python-pptx） | ✅ | notehub `--ppt`（深色 16:9，8 slides） |
| Visual 摘要（Pillow） | ✅ | notehub `--visual`（1920×1080，字型 iansui/NotoSansSC/NotoEmoji） |
| notehub MCP Server | ✅ | 9 tools：add/search/list/get/update/delete/export/batch/stats |
| bookmark-manager 摘要卡 | ✅ | `add2 <url>` → llm_enhance.py（Zen）自動摘要+標籤 → SQLite + 回覆卡片 |
| 台股收盤價管線 | ✅ | 見 `taiwan-stock-data-pipeline` skill（cron 每日 14:30，SQLite 增量） |
| 旅遊文章產出 | ✅ | 見 `taiwan-travel-food-writer` skill（Trends 選題 → 查證 → 文章 → Obsidian + Mail2Blogger） |
| Mail2Blogger | ✅ | `bash /opt/data/scripts/blogger_send.sh`（MX port 25，無帳密） |
| 每日對話日誌 | ✅ | 見 `obsidian-daily-summary` skill（cron 自動產 Obsidian 日誌） |
| Groq Whisper IG 流程 | ✅ | 見 `instagram-reel-podcast` skill（yt-dlp → Groq → notehub → 口播） |
| 知識圖譜管線 | ✅ | 見 `knowledge-graph-pipeline` skill（Graphify + 自訂 LLM providers） |
| Claude Code / Codex CLI 委派 | 📘 有 skill | `claude-code` / `codex` skill（未於本環境實測） |

## 📌 使用方式

調用任何功能前：
1. 先查本清單確認該功能已驗證 + 呼叫方式
2. 複製命令直接使用
3. 若功能異常 → 查對應 skill（youtube-note-pipeline / personal-bookmark-system / notehub-multisource-pipeline）的 Pitfalls 段

## 🔍 關聯 skill

- `youtube-note-pipeline` — 完整管線細節 + Podcast Pitfalls（18 條）
- `notehub-multisource-pipeline` — notehub 架構
- `personal-bookmark-system` / `bookmark-manager` — 書籤管理系統
- `instagram-reel-podcast` — IG 專用流程
