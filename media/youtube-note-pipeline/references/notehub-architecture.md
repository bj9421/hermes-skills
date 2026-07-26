# NoteHub Architecture Reference

> Multi-source note pipeline — upgraded from YouTube-only yt2md_pipeline.

## Directory Structure

```
notehub/
├── __init__.py
├── __main__.py          # CLI entry: python -m notehub
├── extractors/
│   ├── base.py          # BaseExtractor + ExtractResult
│   ├── detector.py      # Auto-detect source type
│   ├── youtube.py       # YouTube (3 strategies: api/vtt/whisper)
│   ├── url.py           # Web articles (HTML strip)
│   ├── pdf.py           # PDF (pymupdf4llm → markdown)
│   └── text.py          # Local .md/.txt files
├── core/
│   ├── llm.py           # LLM calls (rate limiter + 3-model fallback)
│   └── pipeline.py      # Unified pipeline orchestrator
├── db/
│   └── models.py        # SQLite FTS5 + tags + stats
├── generators/
│   ├── podcast.py       # Wrapper → existing podcast.py
│   ├── ppt.py           # Wrapper → existing ppt_gen.py
│   └── visual.py        # Wrapper → existing visual_gen.py
└── mcp/
    └── server.py        # 9 MCP tools (CRUD + search + batch + stats)
```

## Data Flow

```
Source (YouTube/URL/PDF/text)
    ↓
SourceDetector.detect_source(input) → BaseExtractor subclass
    ↓
Extractor.extract(input) → ExtractResult(text, metadata, source_type, source_id)
    ↓
_translate_title() → dir_title (if --lang set)
    ↓
_create output dir: {obsidian}/{dir_title} [{source_id}]/
    ↓
Save raw: {dir_title}_raw.md
    ↓
Organize via LLM (if --organize): {dir_title}_notes.md
    ↓
Index to SQLite (auto)
    ↓
Generate outputs (if flagged): podcast / ppt / visual
    ↓
chmod -R 777 (for Syncthing)
```

## SQLite Schema

```sql
notes (id, title, source_type, source_id, source_url, content, raw_content,
       tags JSON, created_at, updated_at, dir_path, UNIQUE(source_type, source_id))

notes_fts (FTS5 virtual table on title, content, tags)
    -- Auto-synced via triggers (INSERT/UPDATE/DELETE on notes)

tags (id, name UNIQUE)
note_tags (note_id, tag_id) -- many-to-many
```

DB location: `/opt/data/.notehub/notes.db` (env override: `NOTEBOOK_DB_DIR`)

## MCP Tools (9)

| Tool | Function |
|------|----------|
| notehub_add | Add note from any source (auto-extract + organize) |
| notehub_search | FTS5 search + tag/date/source_type filters |
| notehub_list | List notes (newest first) |
| notehub_get | Get single note by ID |
| notehub_update | Update title/content/tags |
| notehub_delete | Delete note |
| notehub_export | Export as Markdown or text |
| notehub_batch | Batch add from newline-separated sources |
| notehub_stats | Total notes + by-source breakdown |

## Key Design Decisions

1. **Strategy Pattern for extractors** — Each source type is a separate class with `detect()` + `extract()`. Adding new sources = add one file.
2. **Unified ExtractResult** — All extractors return the same dataclass. Pipeline doesn't care about source type after extraction.
3. **Generators are wrappers** — `notehub/generators/` imports from existing `podcast.py`, `ppt_gen.py`, `visual_gen.py`. No code duplication.
4. **LLM module is shared** — `notehub/core/llm.py` provides `call_llm()` with rate limiter + fallback. All modules use it.
5. **SQLite with FTS5** — Zero external dependencies. WAL mode for concurrent reads. Triggers keep FTS in sync.
6. **Backward compatible** — Old `python yt2md_pipeline.py "URL"` still works. Notehub is additive.

## Backward Compatibility

- `python yt2md_pipeline.py "YouTube URL" --podcast dual` → still works (old entry point)
- `python -m notehub "YouTube URL" --podcast dual` → new entry point (recommended)
- All existing output formats preserved (script.md, podcast.mp3, .pptx, _summary.png)
- SQLite database is NEW — old pipeline didn't index notes
