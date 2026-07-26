# NoteHub Pipeline 升級 — 實作計畫

> 日期：2026-07-26
> 依賴 Spec：`docs/specs/2026-07-26-multisource-design.md`
> 總任務數：14 | 預估時間：~3 小時

---

## Task 1：建立目錄結構
- **目標：** 建立 `notehub/` 套件目錄 + 所有 `__init__.py`
- **檔案：** 建立 `notehub/__init__.py`, `notehub/extractors/__init__.py`, `notehub/core/__init__.py`, `notehub/db/__init__.py`, `notehub/generators/__init__.py`, `notehub/mcp/__init__.py`
- **驗證：** `python -c "import notehub"` 成功

## Task 2：BaseExtractor 抽象基類
- **目標：** 定義 `BaseExtractor` + `ExtractResult` 資料類別
- **建立：** `notehub/extractors/base.py`
- **內容：**
  ```python
  @dataclass
  class ExtractResult:
      text: str
      metadata: dict
      source_type: str  # youtube/url/pdf/text
      source_id: str
  
  class BaseExtractor:
      def detect(self, input_path: str) -> bool: ...
      def extract(self, input_path: str) -> ExtractResult: ...
  ```
- **驗證：** `python -c "from notehub.extractors.base import BaseExtractor, ExtractResult"` 成功

## Task 3：YouTube Extractor
- **目標：** 從現有 `yt2md_pipeline.py` 搬出 YouTube 提取邏輯
- **搬移：** `_extract_transcript()`, `_get_video_id()`, `_get_video_title()` → `notehub/extractors/youtube.py`
- **改寫：** 繼承 `BaseExtractor`，實作 `detect()` + `extract()` + `get_metadata()`
- **依賴：** Task 2
- **驗證：** `python -c "from notehub.extractors.youtube import YouTubeExtractor; YouTubeExtractor().detect('https://youtube.com/watch?v=xxx')"` 回傳 True

## Task 4：URL Extractor
- **目標：** 實作網頁文章提取器
- **建立：** `notehub/extractors/url.py`
- **方法：** 用 `urllib.request` 抓網頁 + `html.parser` 去 HTML 標籤（或用現有 web_extract）
- **依賴：** Task 2
- **驗證：** `python -c "from notehub.extractors.url import URLExtractor; r = URLExtractor().extract('https://example.com'); print(r.text[:100])"` 回傳文字

## Task 5：PDF Extractor
- **目標：** 實作 PDF 提取器（保留表格結構）
- **建立：** `notehub/extractors/pdf.py`
- **方法：** `pymupdf4llm.to_markdown()` 解析 PDF → Markdown
- **依賴：** Task 2, 安裝 pymupdf4llm
- **驗證：** `uv pip install pymupdf4llm && python -c "from notehub.extractors.pdf import PDFExtractor; print('OK')"` 成功

## Task 6：Text Extractor
- **目標：** 實作本地文字檔提取器
- **建立：** `notehub/extractors/text.py`
- **方法：** 直接讀取 `.md` / `.txt` 檔案
- **依賴：** Task 2
- **驗證：** `python -c "from notehub.extractors.text import TextExtractor; print('OK')"` 成功

## Task 7：SourceDetector 自動偵測
- **目標：** 實作來源類型自動偵測
- **建立：** `notehub/extractors/detector.py`
- **邏輯：**
  ```python
  def detect_source(input_path: str) -> BaseExtractor:
      # 1. YouTube regex → YouTubeExtractor
      # 2. http/https → URLExtractor
      # 3. .pdf → PDFExtractor
      # 4. .md/.txt → TextExtractor
      # 5. raise ValueError
  ```
- **依賴：** Task 3, 4, 5, 6
- **驗證：** 每種輸入型態回傳正確的 Extractor 類別

## Task 8：LLM 模組（rate limiter + fallback）
- **目標：** 從現有程式碼抽出 LLM 呼叫邏輯
- **搬移：** `_get_llm_client()`, `_rate_limit()`, fallback models → `notehub/core/llm.py`
- **建立：** `notehub/core/llm.py`
- **依賴：** 無
- **驗證：** `python -c "from notehub.core.llm import call_llm; print('OK')"` 成功

## Task 9：統一 Pipeline
- **目標：** 建立統一 pipeline，串接 Extractor → LLM → Output
- **建立：** `notehub/core/pipeline.py`
- **流程：**
  ```python
  def run_pipeline(source, podcast=None, ppt=False, visual=False, lang="auto"):
      # 1. detect_source → extractor
      # 2. extractor.extract() → ExtractResult
      # 3. _translate_title() → dir_title
      # 4. _organize_via_llm() → structured_notes
      # 5. Save script.md
      # 6. Optionally: podcast, ppt, visual
  ```
- **依賴：** Task 7, 8
- **驗證：** `python -m notehub "https://example.com" --organize` 產出 script.md

## Task 10：SQLite Schema + FTS5
- **目標：** 建立資料庫層
- **建立：** `notehub/db/models.py`, `notehub/db/search.py`
- **Schema：** notes 表 + notes_fts 虛擬表 + tags 表 + note_tags 關聯
- **依賴：** 無
- **驗證：** `python -c "from notehub.db.models import NoteDB; db = NoteDB(); db.add_note('test', 'text', 'test1', 'content', [], '/tmp'); print(db.search('test'))"` 回傳結果

## Task 11：搬移 Generators
- **目標：** 從現有檔案搬移生成器到新架構
- **搬移：** podcast.py → `notehub/generators/podcast.py`, ppt_gen.py → `notehub/generators/ppt.py`, visual_gen.py → `notehub/generators/visual.py`
- **改寫：** 改 import 路徑，保留原有功能
- **依賴：** Task 8
- **驗證：** `python -c "from notehub.generators.podcast import produce_podcast; print('OK')"` 成功

## Task 12：MCP Server
- **目標：** 實作 MCP 工具
- **建立：** `notehub/mcp/server.py`
- **工具：** notehub_add, notehub_search, notehub_list, notehub_get, notehub_update, notehub_delete, notehub_export, notehub_batch, notehub_stats
- **依賴：** Task 10
- **驗證：** `python -c "from notehub.mcp.server import mcp; print('OK')"` 成功

## Task 13：CLI 入口改寫
- **目標：** 建立 `notehub` CLI + 保留舊 CLI 相容
- **建立：** `notehub/__main__.py`（新入口）
- **改寫：** `yt2md_pipeline.py` 改為从 notehub import（向後相容）
- **依賴：** Task 9, 11
- **驗證：** `python -m notehub "YouTube URL" --podcast dual` 成功

## Task 14：整合測試
- **目標：** 端到端測試所有功能
- **測試：**
  1. YouTube + podcast + ppt + visual
  2. URL + organize + visual
  3. PDF + organize + ppt
  4. Text + podcast
  5. Search: `notehub_search("YouTube")`
  6. MCP: `notehub_list`
  7. Stats: `notehub_stats`
- **依賴：** Task 1-13
- **驗證：** 所有測試通過

---

## 執行順序（依賴圖）

```
Task 1 (目錄)
  └→ Task 2 (BaseExtractor)
       ├→ Task 3 (YouTube) ─┐
       ├→ Task 4 (URL) ─────┤
       ├→ Task 5 (PDF) ─────┤
       └→ Task 6 (Text) ────┘
            └→ Task 7 (Detector) ─┐
Task 8 (LLM) ────────────────────┤
                                  └→ Task 9 (Pipeline) ─┐
Task 10 (SQLite) ──────────────────→ Task 12 (MCP) ─────┤
Task 11 (Generators) ──────────────→ Task 13 (CLI) ─────┤
                                                          └→ Task 14 (Test)
```

## 每任務 TDD 週期

每個任務遵循：
1. **RED** — 寫一個會失敗的測試（或驗證命令）
2. **GREEN** — 實作最小代碼讓測試通過
3. **REFACTOR** — 整理代碼（如有必要）
4. **COMMIT** — `git commit -m "feat(notehub): Task N — <描述>"`
