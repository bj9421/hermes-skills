"""NoteHub MCP Server — tools for AI agents to manage notes.

Tools:
  notehub_add     — Add a note from any source (YouTube/URL/PDF/text)
  notehub_search  — Full-text search with tag/date filters
  notehub_list    — List all notes
  notehub_get     — Get a single note by ID
  notehub_update  — Update note fields
  notehub_delete  — Delete a note
  notehub_export  — Export note as Markdown/text
  notehub_batch   — Batch add from multiple sources
  notehub_stats   — Get statistics
"""

import json
import os
import sys

from mcp.server.fastmcp import FastMCP

# Import NoteDB
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.models import NoteDB

mcp = FastMCP("NoteHub", instructions="NoteHub — multi-source note management with search, tags, and export.")


def _get_db():
    return NoteDB()


@mcp.tool()
def notehub_add(source: str, tags: str = "") -> str:
    """Add a note from any source (YouTube URL, web URL, PDF path, text file path).

    Args:
        source: Input path or URL
        tags: Comma-separated tags (e.g. "research,ai")
    Returns:
        Summary of the added note.
    """
    from extractors.detector import detect_source
    from core.pipeline import _organize_content

    extractor = detect_source(source)
    result = extractor.extract(source)
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else [result.source_type]

    # Organize content
    organized = _organize_content(result.text, result.metadata.get("title", ""))

    db = _get_db()
    note_id = db.add_note(
        title=result.metadata.get("title", "Untitled"),
        source_type=result.source_type,
        source_id=result.source_id,
        content=organized or result.text,
        raw_content=result.text,
        tags=tag_list,
        source_url=source,
    )
    db.close()

    return json.dumps({
        "status": "ok",
        "note_id": note_id,
        "title": result.metadata.get("title", ""),
        "source_type": result.source_type,
        "chars": len(result.text),
        "tags": tag_list,
    }, ensure_ascii=False)


@mcp.tool()
def notehub_search(query: str, tags: str = "", date_from: str = "", date_to: str = "",
                   source_type: str = "", limit: int = 10) -> str:
    """Search notes with full-text search, tag filters, and date range.

    Args:
        query: Search query (FTS5 syntax)
        tags: Comma-separated tag filters
        date_from: Start date (YYYY-MM-DD)
        date_to: End date (YYYY-MM-DD)
        source_type: Filter by source (youtube/url/pdf/text)
        limit: Max results (default 10)
    Returns:
        JSON array of matching notes.
    """
    db = _get_db()
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    results = db.search(query, tags=tag_list, date_from=date_from or None,
                        date_to=date_to or None, source_type=source_type or None, limit=limit)
    db.close()
    return json.dumps(results, ensure_ascii=False, default=str)


@mcp.tool()
def notehub_list(limit: int = 50, offset: int = 0) -> str:
    """List all notes, newest first.

    Args:
        limit: Max results (default 50)
        offset: Pagination offset
    Returns:
        JSON array of notes.
    """
    db = _get_db()
    notes = db.list_notes(limit=limit, offset=offset)
    db.close()
    return json.dumps(notes, ensure_ascii=False, default=str)


@mcp.tool()
def notehub_get(note_id: int) -> str:
    """Get a single note by ID.

    Args:
        note_id: Note ID
    Returns:
        Full note content.
    """
    db = _get_db()
    note = db.get_note(note_id)
    db.close()
    if not note:
        return json.dumps({"error": f"Note {note_id} not found"})
    return json.dumps(note, ensure_ascii=False, default=str)


@mcp.tool()
def notehub_update(note_id: int, title: str = "", content: str = "", tags: str = "") -> str:
    """Update note fields.

    Args:
        note_id: Note ID
        title: New title (optional)
        content: New content (optional)
        tags: New comma-separated tags (optional)
    Returns:
        Status message.
    """
    db = _get_db()
    kwargs = {}
    if title:
        kwargs["title"] = title
    if content:
        kwargs["content"] = content
    if tags:
        kwargs["tags"] = [t.strip() for t in tags.split(",") if t.strip()]
    ok = db.update_note(note_id, **kwargs)
    db.close()
    return json.dumps({"status": "ok" if ok else "failed", "note_id": note_id})


@mcp.tool()
def notehub_delete(note_id: int) -> str:
    """Delete a note.

    Args:
        note_id: Note ID
    Returns:
        Status message.
    """
    db = _get_db()
    ok = db.delete_note(note_id)
    db.close()
    return json.dumps({"status": "ok" if ok else "failed", "note_id": note_id})


@mcp.tool()
def notehub_export(note_id: int, format: str = "markdown") -> str:
    """Export a note as formatted text.

    Args:
        note_id: Note ID
        format: Output format ("markdown" or "txt")
    Returns:
        Formatted note text.
    """
    db = _get_db()
    text = db.export_note(note_id, fmt=format)
    db.close()
    if not text:
        return json.dumps({"error": f"Note {note_id} not found"})
    return text


@mcp.tool()
def notehub_batch(sources: str, tags: str = "") -> str:
    """Batch add notes from multiple sources.

    Args:
        sources: Newline-separated list of source URLs/paths
        tags: Comma-separated tags applied to all
    Returns:
        Summary of batch operation.
    """
    from extractors.detector import detect_source
    from core.pipeline import _organize_content

    db = _get_db()
    results = []
    for line in sources.strip().split("\n"):
        source = line.strip()
        if not source:
            continue
        try:
            extractor = detect_source(source)
            result = extractor.extract(source)
            tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else [result.source_type]
            organized = _organize_content(result.text, result.metadata.get("title", ""))
            note_id = db.add_note(
                title=result.metadata.get("title", "Untitled"),
                source_type=result.source_type,
                source_id=result.source_id,
                content=organized or result.text,
                raw_content=result.text,
                tags=tag_list,
                source_url=source,
            )
            results.append({"source": source, "note_id": note_id, "status": "ok"})
        except Exception as e:
            results.append({"source": source, "status": "error", "error": str(e)})

    db.close()
    return json.dumps({"total": len(results), "results": results}, ensure_ascii=False)


@mcp.tool()
def notehub_stats() -> str:
    """Get statistics — total notes, by source type, etc.

    Returns:
        JSON stats object.
    """
    db = _get_db()
    stats = db.get_stats()
    db.close()
    return json.dumps(stats, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run(transport="stdio")
