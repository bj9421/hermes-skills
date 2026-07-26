"""SQLite database layer for NoteHub — notes storage with FTS5 full-text search."""

import json
import os
import sqlite3
import sys
from datetime import datetime

DB_DIR = os.environ.get("NOTEBOOK_DB_DIR", "/opt/data/.notehub")
DB_PATH = os.path.join(DB_DIR, "notes.db")


class NoteDB:
    """SQLite-backed note storage with FTS5 search."""

    def __init__(self, db_path: str = DB_PATH):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def _init_schema(self):
        c = self.conn
        c.executescript("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_id TEXT NOT NULL,
                source_url TEXT,
                content TEXT,
                raw_content TEXT,
                tags TEXT DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                dir_path TEXT,
                UNIQUE(source_type, source_id)
            );

            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            );

            CREATE TABLE IF NOT EXISTS note_tags (
                note_id INTEGER REFERENCES notes(id) ON DELETE CASCADE,
                tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
                PRIMARY KEY (note_id, tag_id)
            );
        """)

        # FTS5 virtual table (skip if already exists)
        try:
            c.execute("""
                CREATE VIRTUAL TABLE notes_fts USING fts5(
                    title, content, tags,
                    content=notes,
                    content_rowid=id
                )
            """)
            # Triggers to keep FTS in sync
            c.executescript("""
                CREATE TRIGGER IF NOT EXISTS notes_ai AFTER INSERT ON notes BEGIN
                    INSERT INTO notes_fts(rowid, title, content, tags)
                    VALUES (new.id, new.title, new.content, new.tags);
                END;
                CREATE TRIGGER IF NOT EXISTS notes_ad AFTER DELETE ON notes BEGIN
                    INSERT INTO notes_fts(notes_fts, rowid, title, content, tags)
                    VALUES ('delete', old.id, old.title, old.content, old.tags);
                END;
                CREATE TRIGGER IF NOT EXISTS notes_au AFTER UPDATE ON notes BEGIN
                    INSERT INTO notes_fts(notes_fts, rowid, title, content, tags)
                    VALUES ('delete', old.id, old.title, old.content, old.tags);
                    INSERT INTO notes_fts(rowid, title, content, tags)
                    VALUES (new.id, new.title, new.content, new.tags);
                END;
            """)
        except Exception:
            pass  # FTS table already exists

        self.conn.commit()

    def add_note(self, title: str, source_type: str, source_id: str,
                 content: str, tags: list[str] = None, raw_content: str = None,
                 dir_path: str = None, source_url: str = None) -> int:
        """Add a note. Returns note ID."""
        now = datetime.now().isoformat()
        tags_json = json.dumps(tags or [])

        try:
            c = self.conn
            cur = c.execute(
                """INSERT OR REPLACE INTO notes
                   (title, source_type, source_id, source_url, content, raw_content,
                    tags, created_at, updated_at, dir_path)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (title, source_type, source_id, source_url, content, raw_content,
                 tags_json, now, now, dir_path)
            )
            note_id = cur.lastrowid

            # Handle tags
            if tags:
                for tag in tags:
                    c.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag,))
                    tag_row = c.execute("SELECT id FROM tags WHERE name = ?", (tag,)).fetchone()
                    if tag_row:
                        c.execute("INSERT OR IGNORE INTO note_tags (note_id, tag_id) VALUES (?, ?)",
                                  (note_id, tag_row[0]))

            c.commit()
            return note_id
        except Exception as e:
            print(f"[ERROR] add_note failed: {e}", file=sys.stderr)
            return -1

    def search(self, query: str, tags: list[str] = None,
               date_from: str = None, date_to: str = None,
               source_type: str = None, limit: int = 20) -> list[dict]:
        """Full-text search with optional filters."""
        try:
            # FTS5 search
            sql = """
                SELECT n.id, n.title, n.source_type, n.source_id, n.source_url,
                       n.tags, n.created_at, n.dir_path,
                       snippet(notes_fts, 1, '<b>', '</b>', '...', 32) as snippet
                FROM notes_fts f
                JOIN notes n ON n.id = f.rowid
                WHERE notes_fts MATCH ?
            """
            params = [query]

            if source_type:
                sql += " AND n.source_type = ?"
                params.append(source_type)
            if date_from:
                sql += " AND n.created_at >= ?"
                params.append(date_from)
            if date_to:
                sql += " AND n.created_at <= ?"
                params.append(date_to + "T23:59:59")

            sql += " ORDER BY rank LIMIT ?"
            params.append(limit)

            rows = self.conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            print(f"[ERROR] search failed: {e}", file=sys.stderr)
            return []

    def list_notes(self, limit: int = 50, offset: int = 0) -> list[dict]:
        """List all notes, newest first."""
        rows = self.conn.execute(
            "SELECT id, title, source_type, source_id, tags, created_at, dir_path "
            "FROM notes ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_note(self, note_id: int) -> dict | None:
        """Get a single note by ID."""
        row = self.conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
        return dict(row) if row else None

    def update_note(self, note_id: int, **kwargs) -> bool:
        """Update note fields."""
        allowed = {"title", "content", "tags", "dir_path", "source_url"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return False
        updates["updated_at"] = datetime.now().isoformat()
        if "tags" in updates and isinstance(updates["tags"], list):
            updates["tags"] = json.dumps(updates["tags"])
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [note_id]
        self.conn.execute(f"UPDATE notes SET {set_clause} WHERE id = ?", values)
        self.conn.commit()
        return True

    def delete_note(self, note_id: int) -> bool:
        """Delete a note."""
        self.conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        self.conn.commit()
        return True

    def get_stats(self) -> dict:
        """Get statistics."""
        total = self.conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
        by_type = self.conn.execute(
            "SELECT source_type, COUNT(*) as cnt FROM notes GROUP BY source_type"
        ).fetchall()
        return {
            "total_notes": total,
            "by_source": {r["source_type"]: r["cnt"] for r in by_type},
        }

    def export_note(self, note_id: int, fmt: str = "markdown") -> str | None:
        """Export a note as formatted text."""
        note = self.get_note(note_id)
        if not note:
            return None
        content = note["content"] or ""
        title = note["title"]
        if fmt == "markdown":
            return f"# {title}\n\n{content}"
        elif fmt == "txt":
            return f"{title}\n{'='*len(title)}\n\n{content}"
        return content

    def close(self):
        self.conn.close()
