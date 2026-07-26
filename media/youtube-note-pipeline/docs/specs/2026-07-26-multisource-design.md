# NoteHub Pipeline 升級設計 Spec

> 日期：2026-07-26
> 狀態：Phase 1 — Brainstorming
> 專案：yt2md pipeline → NoteHub（多來源筆記平台）

---

## 1. 目標

將 yt2md pipeline 從「YouTube 專用工具」升級為「多來源筆記平台」，類似 NotebookLM 體驗：

- **多來源輸入**：YouTube / URL / PDF / 本地文字檔
- **歷史筆記搜尋**：SQLite FTS5 全文搜尋 + 標籤 + 日期篩選
- **MCP Server**：讓 AI 助手直接操作筆記

## 2. 架構設計

### 2.1 現有架構（Before）

```
yt2md_pipeline.py (main)
├── _extract_transcript()  # YouTube 逐字稿
├── _organize_via_llm()    # LLM 整理
├── _get_video_title()     # YouTube 標題
└── main()                 # CLI 入口

podcast.py    # TTS 口播
ppt_gen.py    # PPT 生成
visual_gen.py # 視覺摘要圖
```

### 2.2 新架構（After）

```
notehub/
├── __init__.py
├── extractors/           # 來源提取器（Strategy Pattern）
│   ├── __init__.py
│   ├── base.py           # 抽象基類 BaseExtractor
│   ├── youtube.py        # YouTube 逐字稿提取
│   ├── url.py            # 網頁文章提取
│   ├── pdf.py            # PDF 文字+表格提取
│   └── text.py           # 本地文字檔提取
├── core/                 # 核心處理
│   ├── __init__.py
│   ├── pipeline.py       # 統一 pipeline（取代 yt2md_pipeline.py）
│   ├── llm.py            # LLM 呼叫（含 rate limiter + fallback）
│   └── translate.py      # 標題翻譯
├── db/                   # 資料庫層
│   ├── __init__.py
│   ├── models.py         # SQLite schema + FTS5
│   └── search.py         # 搜尋 API
├── generators/           # 輸出生成器（現有）
│   ├── __init__.py
│   ├── podcast.py        # TTS 口播（搬過來）
│   ├── ppt.py            # PPT 生成（搬過來）
│   └── visual.py         # 視覺摘要圖（搬過來）
└── mcp/                  # MCP Server
    ├── __init__.py
    └── server.py         # MCP 工具定義
```

### 2.3 資料流

```
使用者輸入（YouTube/URL/PDF/文字）
    │
    ▼
┌─────────────────┐
│  SourceDetector  │  自動偵測來源類型
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Extractor       │  專屬提取器
│  (youtube/url/   │  → transcript_text, metadata
│   pdf/text)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  LLM Organizer   │  統一 LLM 整理（共享）
│  (_organize)     │  → structured_notes
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌────────┐ ┌────────┐
│ SQLite │ │ Output │
│ Index  │ │ Gen    │  script.md / ppt / visual / podcast
└────────┘ └────────┘
```

## 3. 來源提取器設計

### 3.1 BaseExtractor（抽象基類）

```python
class BaseExtractor:
    def detect(self, input_path: str) -> bool:
        """偵測輸入是否為此類型"""
    
    def extract(self, input_path: str) -> ExtractResult:
        """提取內容"""
    
    def get_metadata(self, input_path: str) -> dict:
        """取得中繼資料（標題、來源、日期等）"""

@dataclass
class ExtractResult:
    text: str           # 主要文字內容
    metadata: dict      # 標題、來源 URL、日期等
    source_type: str    # "youtube" | "url" | "pdf" | "text"
    source_id: str      # 唯一識別碼（video_id / url hash / filename hash）
```

### 3.2 各提取器

| 提取器 | 偵測方式 | 提取方法 | source_id |
|--------|---------|---------|-----------|
| YouTube | regex match youtube/youtu.be | youtube-transcript-api → yt-dlp fallback | video_id |
| URL | startswith http/https | web_extract (Anysearch) → readability | url hash |
| PDF | endswith .pdf | pymupdf4llm / PyMuPDF | filename hash |
| Text | endswith .md/.txt | 直接讀取 | filename hash |

### 3.3 CLI 入口改變

```bash
# 現有（仍支援）
python yt2md_pipeline.py "https://youtube.com/watch?v=xxx" --podcast dual

# 新增
python yt2md_pipeline.py "https://example.com/article" --podcast dual
python yt2md_pipeline.py "./document.pdf" --organize --ppt
python yt2md_pipeline.py "./notes.txt" --visual

# 批次
python yt2md_pipeline.py --batch urls.txt --podcast solo --lang zh
```

## 4. SQLite 資料庫設計

### 4.1 Schema

```sql
-- 筆記主表
CREATE TABLE notes (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    source_type TEXT NOT NULL,      -- youtube/url/pdf/text
    source_id TEXT NOT NULL,        -- video_id/url_hash/filename_hash
    source_url TEXT,                -- 原始 URL（如有）
    content TEXT,                   -- LLM 整理後的結構化筆記
    raw_content TEXT,               -- 原始提取內容
    tags TEXT DEFAULT '[]',         -- JSON 陣列
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    dir_path TEXT,                  -- 輸出目錄路徑
    UNIQUE(source_type, source_id)
);

-- FTS5 全文搜尋索引
CREATE VIRTUAL TABLE notes_fts USING fts5(
    title, content, tags,
    content=notes,
    content_rowid=id
);

-- 標籤表（ normalized）
CREATE TABLE tags (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL
);

-- 筆記-標籤關聯
CREATE TABLE note_tags (
    note_id INTEGER REFERENCES notes(id),
    tag_id INTEGER REFERENCES tags(id),
    PRIMARY KEY (note_id, tag_id)
);
```

### 4.2 搜尋 API

```python
class NoteDB:
    def search(self, query: str, tags: list = None, 
               date_from: str = None, date_to: str = None,
               source_type: str = None, limit: int = 20) -> list[dict]:
        """全文搜尋 + 標籤 + 日期篩選"""
    
    def add_note(self, title, source_type, source_id, content, tags, dir_path) -> int:
        """新增筆記"""
    
    def get_note(self, note_id: int) -> dict:
        """取得單一筆記"""
    
    def list_notes(self, limit: int = 50, offset: int = 0) -> list[dict]:
        """列出所有筆記"""
    
    def update_note(self, note_id: int, **kwargs) -> bool:
        """更新筆記"""
    
    def delete_note(self, note_id: int) -> bool:
        """刪除筆記"""
    
    def export_note(self, note_id: int, format: str = "markdown") -> str:
        """匯出筆記"""
    
    def get_stats(self) -> dict:
        """統計資訊（總筆記數、各來源數量、標籤分布）"""
```

## 5. MCP Server 設計

### 5.1 工具清單

| 工具 | 功能 | 參數 |
|------|------|------|
| `notehub_add` | 新增筆記（從來源提取+整理） | source, tags |
| `notehub_search` | 全文搜尋 | query, tags, date_from, date_to |
| `notehub_list` | 列出筆記 | limit, offset |
| `notehub_get` | 取得單一筆記 | note_id |
| `notehub_update` | 更新筆記 | note_id, title, content, tags |
| `notehub_delete` | 刪除筆記 | note_id |
| `notehub_export` | 匯出筆記 | note_id, format |
| `notehub_batch` | 批次操作 | sources[], tags |
| `notehub_stats` | 統計資訊 | — |

### 5.2 技術選型

- **MCP 框架**：`mcp` Python SDK（官方）
- **傳輸**：stdio（本地）或 SSE（遠端）
- **安裝**：uv tool install 或 pip install

## 6. 實作順序

| 順序 | 任務 | 依賴 | 預估時間 |
|------|------|------|---------|
| 1 | 建立 `notehub/` 目錄結構 + `__init__.py` | 無 | 5 min |
| 2 | 實作 `extractors/base.py`（BaseExtractor + ExtractResult） | 無 | 10 min |
| 3 | 實作 `extractors/youtube.py`（從現有程式碼搬過來） | 2 | 10 min |
| 4 | 實作 `extractors/url.py`（web_extract） | 2 | 15 min |
| 5 | 實作 `extractors/pdf.py`（PyMuPDF） | 2 | 15 min |
| 6 | 實作 `extractors/text.py`（直接讀取） | 2 | 5 min |
| 7 | 實作 `core/llm.py`（rate limiter + fallback） | 無 | 10 min |
| 8 | 實作 `core/pipeline.py`（統一 pipeline） | 3-7 | 20 min |
| 9 | 實作 `db/models.py`（SQLite schema） | 無 | 10 min |
| 10 | 實作 `db/search.py`（搜尋 API） | 9 | 15 min |
| 11 | 搬移 generators（podcast/ppt/visual） | 8 | 10 min |
| 12 | 實作 `mcp/server.py`（MCP 工具） | 10 | 20 min |
| 13 | CLI 入口改寫 + 向後相容 | 8, 11 | 10 min |
| 14 | 整合測試 | 1-13 | 15 min |

**總預估：~3 小時**

## 7. 向後相容

- 現有 CLI 用法完全保留：`python yt2md_pipeline.py "YouTube URL" --podcast dual`
- 新增 `notehub` CLI 入口：`python -m notehub "any source" --podcast dual`
- 舊的 `podcast.py` / `ppt_gen.py` / `visual_gen.py` 保留不動，新架構從它們 import
- SQLite 資料庫預設放在 `~/.notehub/notes.db`

## 8. 依賴

| 套件 | 用途 | 安裝方式 |
|------|------|---------|
| pymupdf4llm | PDF 解析 | uv pip install pymupdf4llm |
| mcp | MCP Server | uv pip install mcp |
| （已有）openai | NVIDIA API | 已安裝 |
| （已有）edge-tts | TTS | 已安裝 |
| （已有）python-pptx | PPT | 已安裝 |
| （已有）Pillow | 視覺圖 | 已安裝 |

## 9. 風險

| 風險 | 影響 | 緩解 |
|------|------|------|
| NVIDIA 限流 | LLM 整理失敗 | rate limiter + fallback（已實作） |
| PDF 解析品質 | 表格/圖片丟失 | pymupdf4llm 保留表格結構 |
| 網頁反爬蟲 | URL 提取失敗 | 用 Anysearch extract（已有） |
| SQLite 併發 | 資料損毀 | WAL mode + 單寫入者 |
| MCP 伺服器穩定性 | AI 助手連線中斷 | 自動重連 + 本地 stdio |
