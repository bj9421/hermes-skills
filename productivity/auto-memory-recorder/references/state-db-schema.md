# State DB Schema (`/opt/data/state.db`)

The Hermes session database — stores all conversation sessions, messages, and FTS search indexes. Used by `auto_memory_scan.py` to extract facts from recent conversations.

## Tables

### `sessions`

| Column | Type | Notes |
|--------|------|-------|
| `id` | TEXT | PK. Format: `<prefix>_<datetime>_<random>` (e.g. `20260712_015937_d7ccb00a` or `cron_7ebd14dcb4bd_20260712_144850`) |
| `title` | TEXT | Session title. Can be `NULL`. Cron sessions often have title like `"Auto Memory Scanner · Jul 12 11:48"` |
| `started_at` | REAL | Unix timestamp of session creation |
| `archived` | INTEGER | `0` = active, `1` = archived. Scanner filters `WHERE archived = 0` |

### `messages`

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER | PK |
| `session_id` | TEXT | FK → `sessions.id` |
| `role` | TEXT | One of: `user`, `assistant`, `tool`, `session_meta` |
| `content` | TEXT | The message text. **Can be empty (zero-length)** — see pitfalls below |
| `tool_call_id` | TEXT | For tool role messages: ID of the tool call |
| `tool_calls` | TEXT | JSON array of tool calls (assistant → tool invocation) |
| `tool_name` | TEXT | For tool messages: name of the tool invoked |
| `timestamp` | REAL | Unix timestamp |
| `token_count` | INTEGER | Token usage for this message |
| `finish_reason` | TEXT | e.g. `stop`, `tool_calls`, `length` |
| `reasoning` | TEXT | For reasoning-capable models |
| `reasoning_content` | TEXT | Full reasoning chain from the model |
| `reasoning_details` | TEXT | Structured reasoning breakdown |
| `active` | INTEGER | **CRITICAL FOR SCANNER:** `1` = visible to scanner queries, `0` = hidden (compacted/pruned). Scanner queries `WHERE active = 1` |
| `compacted` | INTEGER | `0` = normal message, `1` = replaced by context compaction summary |
| `observed` | INTEGER | Default `0`. Observation tracking |
| `platform_message_id` | TEXT | Platform-specific message ID |
| `codex_reasoning_items` | TEXT | OpenCode Codex reasoning items (JSON) |
| `codex_message_items` | TEXT | OpenCode Codex message items (JSON) |

### FTS Tables

- `messages_fts` — FTS5 virtual table on `messages.content`
- `messages_fts_data`, `messages_fts_idx`, `messages_fts_content` — FTS5 internal tables
- `messages_fts_trigram`, `messages_fts_trigram_data`, `messages_fts_trigram_idx`, `messages_fts_trigram_content`, `messages_fts_trigram_docsize`, `messages_fts_trigram_config` — Trigram FTS5 indexes for substring search

### Other Tables

| Table | Purpose |
|-------|---------|
| `schema_version` | DB schema migration version |
| `state_meta` | Key-value metadata store (e.g. `ghost_session_prune_v1`, `orphaned_compression_finalize_v1`) |
| `compression_locks` | Session compression state tracking (usually empty) |
| `sqlite_sequence` | SQLite autoincrement tracking |

## Key Scanner-Relevant Facts

### 1. Assistant Content is Empty in Cron Sessions

In cron sessions (`id` prefixed with `cron_`), **all assistant messages have `content = ''` (zero-length)**. The scanner's filter `WHERE role IN ('user', 'assistant')` will only match the user message (the task instruction), never find facts in assistant responses.

**Why this happens:** The assistant's actual response text is either stored in `reasoning_content`/`reasoning` columns or delivered via the cron delivery mechanism without being written to `messages.content`. This is a framework-level behavior, not a bug.

**Impact on scanning:** If you need facts from cron execution results, you must either:
- Include `role = 'tool'` messages (tool output contains JSON-serialized terminal results and API responses)
- Check `reasoning_content` for the assistant's actual output

### 2. Session Compaction Removes Messages

The `active` flag controls visibility. After context compaction:
- Old messages get `active = 0`
- The scanner's `WHERE active = 1` filter skips them
- Sessions can have vastly different total vs active counts (e.g. 143 total, 39 active)

**Detection:** Compare `COUNT(*)` vs `SUM(CASE WHEN active=1 THEN 1 ELSE 0 END)` per session.

### 3. Cron Session ID Format

```
cron_<random_hash>_<YYYYMMDD>_<HHMMSS>
```

Example: `cron_7ebd14dcb4bd_20260712_144850`

Non-cron (user) sessions use:
```
<YYYYMMDD>_<HHMMSS>_<random_hash>
```

Example: `20260712_015937_d7ccb00a`

### 4. Session Message Count Discrepancies

Sessions that exist in `sessions` table may have **zero messages** in the `messages` table. This happens when:
- The session was pruned/cleaned up
- The session never generated persistent messages (very short interactions)
- DB maintenance operation removed the message rows

## Useful Diagnostic Queries

```sql
-- Count messages by session (active vs total)
SELECT session_id, COUNT(*) as total,
       SUM(CASE WHEN active=1 THEN 1 ELSE 0 END) as active
FROM messages
GROUP BY session_id
ORDER BY total DESC;

-- Find sessions with actively searching messages
SELECT session_id, COUNT(*) as cnt FROM messages
WHERE active=1 AND role='assistant' AND LENGTH(content) > 0
GROUP BY session_id
ORDER BY cnt DESC;

-- Check cron sessions for non-empty content
SELECT session_id, role, LENGTH(content) as clen
FROM messages WHERE session_id LIKE 'cron_%'
  AND role = 'assistant'
GROUP BY session_id, role;

-- Find sessions with message count mismatch
SELECT s.id, s.title, s.started_at,
       (SELECT COUNT(*) FROM messages WHERE session_id = s.id) as total_msgs,
       (SELECT SUM(CASE WHEN active=1 THEN 1 ELSE 0 END)
        FROM messages WHERE session_id = s.id) as active_msgs
FROM sessions s
WHERE s.archived = 0
ORDER BY s.started_at DESC;

-- Get FTS match count
SELECT COUNT(*) FROM messages_fts;

-- Filter out cron sessions (find real user conversations)
SELECT s.id, s.title, s.started_at, s.message_count,
       datetime(s.started_at, 'unixepoch') as started_iso
FROM sessions s
WHERE s.archived = 0 AND s.id NOT LIKE 'cron_%'
ORDER BY s.started_at DESC
LIMIT 20;

-- Sample first user message of each session (to identify cron vs real)
SELECT m.session_id,
       SUBSTR(m.content, 1, 80) as first_80_chars,
       LENGTH(m.content) as content_len
FROM messages m
WHERE m.role = 'user' AND m.active = 1
  AND m.id IN (
    SELECT MIN(m2.id) FROM messages m2
    WHERE m2.session_id = m.session_id AND m2.role = 'user'
    GROUP BY m2.session_id
  )
ORDER BY m.rowid DESC
LIMIT 20;

-- All sessions in a time range, ordered with newest first
SELECT s.id, s.title, datetime(s.started_at, 'unixepoch') as started,
       s.message_count
FROM sessions s
WHERE s.archived = 0 AND s.started_at > strftime('%s', 'now', '-24 hours')
ORDER BY s.started_at DESC;
```
