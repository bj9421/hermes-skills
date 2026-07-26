---
name: notehub-multisource-pipeline
description: "NoteHub — multi-source note pipeline (YouTube/URL/PDF/text → SQLite search + MCP Server). Replaces yt2md as the unified entry point."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [pipeline, notes, mcp, sqlite, multi-source]
    related_skills: [youtube-note-pipeline]
---

# NoteHub — Multi-Source Note Pipeline

> Upgraded from yt2md pipeline. Supports YouTube, web URLs, PDFs, and local text files.
> All sources → extract → LLM organize → output (script.md + podcast + PPT + visual).
> SQLite FTS5 search + 9 MCP tools for AI agent integration.

## Architecture

```
notehub/
├── extractors/     # 4 source extractors (Strategy Pattern)
│   ├── youtube.py  # 3-strategy: api → vtt → whisper
│   ├── url.py      # HTML strip + readability
│   ├── pdf.py      # pymupdf4llm → markdown
│   └── text.py     # Local .md/.txt files
├── core/
│   ├── llm.py      # NVIDIA API + rate limiter (2s) + 3-model fallback
│   └── pipeline.py # Unified pipeline
├── db/
│   └── models.py   # SQLite FTS5 + tags + date filters
├── generators/     # Wrappers around existing generators
│   ├── podcast.py  # → podcast.py (Edge-TTS)
│   ├── ppt.py      # → ppt_gen.py (python-pptx)
│   └── visual.py   # → visual_gen.py (Pillow + iansui font)
└── mcp/
    └── server.py   # 9 MCP tools
```

## Usage

```bash
# Text file
python -m notehub ./notes.txt --podcast dual

# Web URL
python -m notehub "https://example.com" --organize --visual

# PDF
python -m notehub ./doc.pdf --organize --ppt

# YouTube (backward compatible)
python -m notehub "https://youtube.com/watch?v=xxx" --podcast dual --ppt --visual --lang zh

# Search
python -m notehub --search "AI"
python -m notehub --list
python -m notehub --stats
```

## CLI Flags

| Flag | Description |
|------|-------------|
| `--organize` | LLM-organized structured notes |
| `--podcast solo\|dual` | Generate podcast audio |
| `--ppt` | Generate PowerPoint |
| `--visual` | Generate visual summary image |
| `--lang zh\|en` | Target language for translation |
| `--voice-a\|--voice-b` | TTS voice selection |
| `--search "query"` | Full-text search mode |
| `--list` | List all notes |
| `--stats` | Show statistics |

## MCP Tools (9)

| Tool | Function |
|------|----------|
| `notehub_add` | Add note from any source |
| `notehub_search` | FTS5 search with tag/date filters |
| `notehub_list` | List all notes |
| `notehub_get` | Get single note by ID |
| `notehub_update` | Update note fields |
| `notehub_delete` | Delete a note |
| `notehub_export` | Export as Markdown/text |
| `notehub_batch` | Batch add from multiple sources |
| `notehub_stats` | Statistics |

## Dependencies

| Package | Purpose | Install |
|---------|---------|---------|
| pymupdf4llm | PDF parsing | `uv pip install pymupdf4llm` |
| mcp | MCP Server SDK | `uv pip install mcp` |
| (existing) openai | NVIDIA API | Already installed |
| (existing) edge-tts | TTS | Already installed |
| (existing) python-pptx | PPT | Already installed |
| (existing) Pillow | Visual images | Already installed |

## Database

- Location: `/opt/data/.notehub/notes.db`
- SQLite with FTS5 full-text search
- Schema: notes + tags + note_tags + notes_fts
- WAL mode for concurrent reads

## Rate Limiting

- 2s minimum between API calls (40 RPM free tier = 1.5s baseline)
- 3-retry exponential backoff per model
- 3-model fallback: deepseek-v4-flash → llama-3.3-70b → nemotron-70b

## Files

- Source: `/opt/data/skills/media/youtube-note-pipeline/scripts/notehub/`
- Spec: `docs/specs/2026-07-26-multisource-design.md`
- Plan: `docs/plans/2026-07-26-multisource-plan.md`

## Pitfalls

1. **Python version**: Must use `/opt/data/.venv/bin/python3` (system python3 lacks pptx, pymupdf4llm)
2. **DB path**: `/opt/data/.notehub/notes.db` (not ~/.notehub — permission denied in Docker)
3. **PDF extraction**: pymupdf4llm preserves tables as Markdown; large PDFs may hit LLM token limits
4. **URL extraction**: JS-heavy sites may return empty — fallback to browser tool
5. **FTS5 syntax**: Use simple keywords; complex queries need FTS5 boolean syntax (AND/OR/NOT)
