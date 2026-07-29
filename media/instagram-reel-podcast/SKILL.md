---
name: instagram-reel-podcast
description: "Instagram Reel → podcast workflow: yt-dlp download → Groq Whisper transcribe → notehub solo/dual 口播 → Obsidian vault。針對 IG Reel 無字幕、檔名亂碼、Groq 413 等特殊情況的最佳化流程。"
platforms: [linux]
compatibility:
  - yt-dlp
  - groq
  - ffmpeg
  - edge-tts
  - notehub
related_skills: [youtube-note-pipeline, notehub-multisource-pipeline]
---

# Instagram Reel → Podcast 工作流程

## 什麼時候用

使用者丟來一個 **Instagram Reel 網址**（或任何非 YouTube 短影片），要求轉成口播 podcast（solo/dual）。

**核心差異 vs YouTube 流程：**
- ❌ IG Reel **沒有自動字幕** — 不能靠 youtube-transcript-api
- ✅ yt-dlp 原生支援 Instagram — 直接下載音檔
- ⚠️ notehub TextExtractor 用「檔名」當目錄名 → 一定亂碼，**必須事後手動改名**

## 完整工作流程（5 大步驟）

### Step 1 — 下載音檔 + 抓標題

```bash
# 下載音檔 (yt-dlp 原生支援 Instagram)
yt-dlp -x --audio-format m4a -o "/tmp/audio/%(id)s.%(ext)s" "INSTAGRAM_URL"

# 抓真正的影片標題（用於後續改名）
yt-dlp --print title "INSTAGRAM_URL"
# 👉 實際輸出通常是 "Video by username"，更完整的在 description 裡
yt-dlp --print title,description "INSTAGRAM_URL"
```

**注意：** yt-dlp 對 IG Reel 回傳的 title 通常是 "Video by username"，真正的內容主題在 `description` 欄位的第一行。手動從 description 取出主題作為 podcast 標題。

### Step 2 — 確認檔案大小（Groq 413 防護）

Groq Whisper 限制音檔 **< ~10MB**。IG Reel 通常很短（1-3 min, 2-4MB），一般不會超過。但超過的話要壓縮：

```bash
# 🔴 只在大於 10MB 時才需要
ffmpeg -y -i /tmp/audio/ID.m4a -c:a libopus -b:a 32k /tmp/audio/ID.opus
# 14MB m4a → ~4.5MB opus
```

### Step 3 — Groq Whisper 轉錄

```bash
cd /opt/data && source .venv/bin/activate
export $(grep -v '^#' /opt/data/.env | grep -v '^$' | xargs)
python3 -c "
from groq import Groq
import os
client = Groq(api_key=os.environ['GROQ_API_KEY'])
with open('/tmp/audio/ID.m4a','rb') as f:
    r = client.audio.transcriptions.create(
        file=('audio.m4a',f),
        model='whisper-large-v3',
        language='zh',
        response_format='verbose_json'
    )
print(f'[OK] {len(r.text)} chars, {r.duration}s')
with open('/tmp/ID-transcript.md','w') as f:
    f.write(r.text)
"
```

**參數說明：**
- `model='whisper-large-v3'` — Groq 免費方案，支援中文
- `language='zh'` — 強制中文辨識（IG Reel 幾乎都是中文口語）
- `response_format='verbose_json'` — 可取得 duration 資訊

### Step 4 — notehub 產出口播

```bash
cd /opt/data/skills/media/youtube-note-pipeline/scripts && \
source /opt/data/.venv/bin/activate && \
python -m notehub /tmp/ID-transcript.md --podcast solo --lang zh 台女
```

**⚠️ 語音捷徑（放在 args 最後，不需 `--voice-a`）：**

| 捷徑 | 對應語音 | 性別 |
|------|---------|------|
| `台女` | zh-TW-HsiaoChenNeural | 女聲（預設） |
| `台男` | zh-TW-YunJheNeural | 男聲 |
| `英女` | en-US-JennyNeural | 美式女 |
| `英男` | en-US-GuyNeural | 美式男 |

### Step 5 — 目錄清理 + 正名（🔴 必做）

notehub 處理文字檔時，目錄名稱來自**檔名**（`ID-transcript.md` → `ID 抄本 [hash]/`），不是真實標題。**使用者一定找不到檔案。**

```bash
# 真實標題（從 Step 1 的 description 取出）
TITLE="理解能力差的根本原因"
VID="DbU4cgNJM0t"

# 尋找 notehub 產出的目錄（通常是 /opt/data/obsidian-vault/notes/ 下）
ls /opt/data/obsidian-vault/notes/

# 改名 + 搬到 口播/
SRC="/opt/data/obsidian-vault/notes/ID 抄本 [HASH]"
DST="/opt/data/obsidian-vault/口播/${TITLE} [${VID}]"
mkdir -p "/opt/data/obsidian-vault/口播"
mv "$SRC" "$DST"

# 修正 script.md 的 frontmatter title
sed -i "s/title: ID Transcript/title: $TITLE/" "$DST/script.md"

# 把 podcast.mp3 改名（原有的是 ID 文字稿_podcast.mp3）
# 找目錄內的 .mp3 檔，改名為 ${TITLE}_口播.mp3
find "$DST" -name "*_podcast.mp3" -exec mv {} "$DST/${TITLE}_口播.mp3" \;

# 把 raw transcript 也改名（ID 抄本_raw.md → ${TITLE}_逐字稿.md）
find "$DST" -name "*_raw.md" -exec mv {} "$DST/${TITLE}_逐字稿.md" \;

chmod -R 777 "$DST"
```

**輸出目錄結構範例：**
```
/opt/data/obsidian-vault/口播/理解能力差的根本原因 [DbU4cgNJM0t]/
├── script.md                          # 口播腳本（含 YAML frontmatter）
├── 理解能力差的根本原因_口播.mp3        # podcast 音檔
└── 理解能力差的根本原因_逐字稿.md        # 原始逐字稿（Groq Whisper 輸出）
```

## 完整一鍵腳本（參考）

以下是用於快速執行的完整 bash 流程（替換 INSTAGRAM_URL 與實際標題）：

```bash
URL="https://www.instagram.com/reel/..."
cd /opt/data && source .venv/bin/activate

# Step 1: 下載音檔
yt-dlp -x --audio-format m4a -o "/tmp/audio/%(id)s.%(ext)s" "$URL"
VID=$(basename "$URL" | sed 's/?.*//')

# 抓標題描述
DESC=$(yt-dlp --print description "$URL" 2>/dev/null | head -1)
echo "🔍 建議標題：$DESC"
echo "⚠️  請手動設定 TITLE 變數後繼續"

# Step 2: 確認大小
ls -lh /tmp/audio/${VID}*.m4a

# Step 3: 轉錄
export $(grep -v '^#' /opt/data/.env | grep -v '^$' | xargs)
python3 -c "
from groq import Groq; import os
client = Groq(api_key=os.environ['GROQ_API_KEY'])
with open('/tmp/audio/${VID}*','rb') as f:
    r = client.audio.transcriptions.create(file=('audio.m4a',f), model='whisper-large-v3', language='zh')
with open('/tmp/${VID}-transcript.md','w') as f: f.write(r.text)
print(f'OK: {len(r.text)} chars')
"

# Step 4: 口播
python -m notehub "/tmp/${VID}-transcript.md" --podcast solo --lang zh 台女

# Step 5: 搬移改名（手動設 TITLE 後執行）
# TITLE="你的標題"
# VID="..."
# find /opt/data/obsidian-vault/notes/ -maxdepth 1 -name "*${VID}*" -type d
```

## 常見錯誤處理

### ❌ `Groq API Error 413 Request Entity Too Large`
音檔超過 Groq 的 ~10MB 限制。先檢查大小再壓縮：
```bash
ls -lh /tmp/audio/ID*
ffmpeg -y -i /tmp/audio/ID.m4a -c:a libopus -b:a 32k /tmp/audio/ID.opus
```
再對 `.opus` 檔執行 Groq Whisper

### ❌ 使用者說「沒看到檔案」
一定是因為 text source 的目錄名稱亂碼（如 `Lun Yydhpyy 抄本 [hash]/`）。
**解法：** 用 `find /opt/data/obsidian-vault/notes/ -maxdepth 1 -name "*VID*"` 找到實際目錄，再執行改名流程。

### ❌ yt-dlp 無法下載
Instagram 可能因登入限制阻擋。可嘗試：
```bash
yt-dlp --cookies-from-browser chrome "URL"
```
或在容器內無瀏覽器時，用 `--cn-verification-url` 或 `--extractor-retries 3`

## 與 YouTube 流程的差異

| 面向 | YouTube | Instagram Reel |
|------|---------|----------------|
| 字幕來源 | youtube-transcript-api (自動) | ❌ 無字幕 → Groq Whisper |
| 標題取得 | `--print title` 直接可用 | description 第一行才是主題 |
| 目錄名稱 | 直接從影片標題派生 | 從檔名派生 → 一定亂碼 |
| 音檔大小 | 可長達 1hr+ → 容易超過 10MB | 通常 1-3 min → 安全 |
| 處理時間 | 快（有字幕） | 慢（需 Whisper 轉錄） |
