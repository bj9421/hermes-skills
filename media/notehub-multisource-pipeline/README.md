# NoteHub — Multi-Source Note Pipeline

> 升級自 yt2md pipeline。支援 YouTube、網頁 URL、PDF、本地文字檔。
> 所有來源 → 提取 → LLM 組織 → 輸出（script.md + podcast + PPT + visual）。
> SQLite FTS5 搜尋 + 9 個 MCP 工具，打造類似 NotebookLM 的使用體驗。

## 架構

```
notehub/
├── extractors/          # 4 種來源提取器（Strategy Pattern）
│   ├── base.py          # 基礎介面 + ExtractResult 資料模型
│   ├── detector.py      # 自動偵測來源類型
│   ├── youtube.py       # YouTube 逐字稿（3 策略：api → vtt → whisper）
│   ├── url.py           # 網頁文章（HTML strip）
│   ├── pdf.py           # PDF（pymupdf4llm → markdown）
│   └── text.py          # 本地 .md/.txt 檔案
├── core/
│   ├── llm.py           # LLM 模組（rate limiter + 3-model fallback）
│   └── pipeline.py      # 統一 pipeline
├── db/
│   └── models.py        # SQLite FTS5 搜尋 + 標籤 + 日期篩選
├── generators/          # 生成器包裝器
│   ├── podcast.py       # → podcast.py（Edge-TTS 雙人播客）
│   ├── ppt.py           # → ppt_gen.py（python-pptx）
│   └── visual.py        # → visual_gen.py（Pillow + 芫荽字型）
├── mcp/
│   └── server.py        # 9 個 MCP 工具
└── __main__.py          # CLI 入口
```

## 安裝

### 相依套件

```bash
cd /opt/data
UV_CACHE_DIR=/opt/data/.cache/uv uv pip install pymupdf4llm mcp
```

### 已有套件（無需安裝）

- openai（NVIDIA API）
- edge-tts（TTS）
- python-pptx（PPT）
- Pillow（圖片生成）
- yt-dlp（YouTube 下載）
- youtube-transcript-api（YouTube 逐字稿）

## 使用方式

### 基本指令

```bash
cd /opt/data/skills/media/youtube-note-pipeline/scripts
PYTHON=/opt/data/.venv/bin/python3
```

### 1. YouTube 影片

```bash
# 完整功能（組織 + 雙人播客 + PPT + 視覺摘要 + 中文翻譯）
$PYTHON -m notehub "https://youtube.com/watch?v=VIDEO_ID" \
  --organize --podcast dual --ppt --visual --lang zh

# 只要結構化筆記
$PYTHON -m notehub "https://youtube.com/watch?v=VIDEO_ID" --organize

# 雙人播客 + 視覺摘要
$PYTHON -m notehub "https://youtube.com/watch?v=VIDEO_ID" \
  --podcast dual --visual --lang zh
```

### 2. 網頁文章

```bash
# 抓取網頁內容並組織
$PYTHON -m notehub "https://example.com/article" --organize

# 組織 + 視覺摘要
$PYTHON -m notehub "https://example.com/article" --organize --visual
```

### 3. PDF 文件

```bash
# 解析 PDF 並組織
$PYTHON -m notehub ./document.pdf --organize

# 解析 + 產生 PPT
$PYTHON -m notehub ./document.pdf --organize --ppt

# 解析 + 產生播客
$PYTHON -m notehub ./document.pdf --organize --podcast solo
```

### 4. 本地文字檔

```bash
# 讀取 .md 或 .txt 檔案
$PYTHON -m notehub ./notes.txt --organize

# 文字檔 + 播客
$PYTHON -m notehub ./meeting-notes.md --podcast dual --lang zh
```

## CLI 參數

### 功能開關

| 參數 | 說明 |
|------|------|
| `--organize` | LLM 組織結構化筆記 |
| `--podcast solo` | 單人播客 |
| `--podcast dual` | 雙人播客（預設聲音：女 zh-TW-HsiaoChenNeural、男 zh-TW-YunJheNeural） |
| `--ppt` | 產生 PowerPoint |
| `--visual` | 產生視覺摘要圖（1920×1080） |

### 語言與聲音

| 參數 | 說明 |
|------|------|
| `--lang zh` | 翻譯成中文（預設） |
| `--lang en` | 翻譯成英文 |
| `--lang auto` | 不翻譯 |
| `--voice-a "name"` | 播客 A 聲音（預設：zh-TW-HsiaoChenNeural） |
| `--voice-b "name"` | 播客 B 聲音（預設：zh-TW-YunJheNeural） |

### 搜尋模式

| 參數 | 說明 |
|------|------|
| `--search "關鍵字"` | FTS5 全文搜尋 |
| `--list` | 列出所有筆記（最新優先） |
| `--stats` | 顯示統計資訊 |

## 輸出路徑

所有輸出儲存到 Obsidian vault：

```
/opt/data/obsidian-vault/口播/{翻譯標題} [source_id]/
├── script.md          # 原始內容（YouTube 逐字稿 / 網頁文字 / PDF 內容）
├── _notes.md          # LLM 組織後的結構化筆記
├── _raw.md            # 原始提取資料（含 metadata）
├── _podcast.mp3       # 播客音檔（如有 --podcast）
├── _podcast.txt       # 播客腳本（如有 --podcast）
├── _podcast_a.mp3     # 播客 A 聲道（dual 模式）
├── _podcast_b.mp3     # 播客 B 聲道（dual 模式）
├── _podcast_merged.mp3 # 播客混音（dual 模式）
├── _summary.pptx      # PowerPoint（如有 --ppt）
└── _summary.png       # 視覺摘要圖（如有 --visual）
```

### 文字檔 / PDF / 網頁輸出路徑

```
/opt/data/obsidian-vault/notes/{標題} [hash]/
├── script.md          # 原始內容
├── _notes.md          # LLM 組織後的結構化筆記
├── _raw.md            # 原始提取資料
└── _summary.png       # 視覺摘要圖（如有 --visual）
```

## SQLite 搜尋

### 資料庫位置

```
/opt/data/.notehub/notes.db
```

### Schema

- **notes** — 筆記主表（title, source_type, source_id, content, tags, created_at）
- **tags** — 標籤表
- **note_tags** — 筆記-標籤關聯
- **notes_fts** — FTS5 全文搜尋虛擬表

### 搜尋語法

```bash
# 簡單關鍵字
$PYTHON -m notehub --search "人工智慧"

# FTS5 語法
$PYTHON -m notehub --search "AI AND 機器學習"
$PYTHON -m notehub --search "Python OR JavaScript"
$PYTHON -m notehub --search "深度學習 NOT CNN"
```

## MCP 工具（9 個）

NoteHub 提供 MCP Server，讓 AI Agent 可以直接操作筆記。

### 工具列表

| 工具 | 功能 | 參數 |
|------|------|------|
| `notehub_add` | 新增筆記 | `source`（URL/路徑）, `tags`（逗號分隔） |
| `notehub_search` | 全文搜尋 | `query`, `tags`, `date_from`, `date_to`, `source_type`, `limit` |
| `notehub_list` | 列出筆記 | `limit`, `offset` |
| `notehub_get` | 取得單一筆記 | `note_id` |
| `notehub_update` | 更新筆記 | `note_id`, `title`, `content`, `tags` |
| `notehub_delete` | 刪除筆記 | `note_id` |
| `notehub_export` | 匯出筆記 | `note_id`, `format`（markdown/txt） |
| `notehub_batch` | 批次新增 | `sources`（換行分隔）, `tags` |
| `notehub_stats` | 統計資訊 | 無 |

### MCP Server 啟動

```bash
cd /opt/data/skills/media/youtube-note-pipeline/scripts
/opt/data/.venv/bin/python3 -m notehub.mcp.server
```

### Hermes Agent 整合

在 `config.yaml` 中加入 MCP Server：

```yaml
mcp:
  servers:
    notehub:
      command: /opt/data/.venv/bin/python3
      args: ["-m", "notehub.mcp.server"]
      cwd: /opt/data/skills/media/youtube-note-pipeline/scripts
```

## LLM  resilience（容錯機制）

### Rate Limiting

- 每次 API 呼叫間隔至少 **2 秒**（NVIDIA 免費版限制 ~40 RPM）
- `_rate_limit()` 函數強制執行

### 3-Model Fallback

每次 LLM 呼叫失敗時，自動依序嘗試：

1. `deepseek-ai/deepseek-v4-flash`（預設，中文最佳）
2. `meta/llama-3.3-70b-instruct`（英文強）
3. `nvidia/nemotron-70b-instruct`（穩定）

### 3-Retry Exponential Backoff

每個模型最多重試 3 次，間隔指數成長：3s → 6s → 12s。

### 已知限制

- NVIDIA 503 `ResourceExhausted` 錯誤：worker-level 限制，影響所有模型
- 恢復時間：30 秒 ~ 2+ 小時（不固定）
- 建議：大批處理時，每 5 個影片暫停 1 分鐘

## 與舊版差異

| 項目 | 舊版（yt2md） | 新版（notehub） |
|------|------|------|
| 支援來源 | YouTube only | YouTube / 網頁 / PDF / 文字檔 |
| 搜尋 | ❌ | SQLite FTS5 全文搜尋 |
| MCP 工具 | ❌ | 9 個工具（CRUD + 搜尋 + 批次 + 統計） |
| 進入點 | `python3 yt2md_pipeline.py` | `python3 -m notehub` |
| 資料庫 | ❌ | `/opt/data/.notehub/notes.db` |
| 標籤 | ❌ | 支援標籤分類 |
| 日期篩選 | ❌ | 支援 date_from / date_to |

## 範例

### 完整流程

```bash
# 1. 抓取 YouTube 影片並產生所有輸出
$PYTHON -m notehub "https://youtube.com/watch?v=dQw4w9WgXcQ" \
  --organize --podcast dual --ppt --visual --lang zh

# 2. 搜尋所有筆記
$PYTHON -m notehub --search "人工智慧"

# 3. 列出所有筆記
$PYTHON -m notehub --list

# 4. 查看統計
$PYTHON -m notehub --stats
```

### 批次處理

```bash
# 批次抓取多個來源
cat > /tmp/sources.txt << 'EOF'
https://youtube.com/watch?v=VIDEO_ID_1
https://example.com/article-1
./document.pdf
./notes.txt
EOF

# 透過 MCP 工具 notehub_batch 批次新增
```

## 常見問題

### Q: 為什麼 visual 生成失敗？

A: LLM 呼叫可能 timeout（預設 30 秒）。改用 `--organize` only，或確保 NVIDIA API 正常。

### Q: PDF 提取為空？

A: pymupdf4llm 對掃描式 PDF 無法提取文字。需先 OCR。

### Q: 搜尋找不到結果？

A: FTS5 預設使用 AND 邏輯。改用 `OR` 擴大搜尋範圍。

### Q: MCP 工具在 Hermes 中看不到？

A: 確認 `config.yaml` 中的 MCP 設定正確，且 notehub.mcp.server 可執行。

## 檔案路徑

- **原始碼：** `/opt/data/skills/media/youtube-note-pipeline/scripts/notehub/`
- **Skill 文件：** `/opt/data/skills/media/notehub-multisource-pipeline/SKILL.md`
- **設計規格：** `/opt/data/skills/media/youtube-note-pipeline/docs/specs/2026-07-26-multisource-design.md`
- **實作計畫：** `/opt/data/skills/media/youtube-note-pipeline/docs/plans/2026-07-26-multisource-plan.md`
- **資料庫：** `/opt/data/.notehub/notes.db`
- **輸出目錄：** `/opt/data/obsidian-vault/口播/`
- **GitHub：** `https://github.com/bj9421/hermes-skills/tree/master/media/notehub-multisource-pipeline`
