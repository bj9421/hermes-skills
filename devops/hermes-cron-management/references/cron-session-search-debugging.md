# Cron Job Debugging via session_search

When you need to inspect what a cron job actually did (its full prompt, tool calls, output) but `hermes cron inspect` or `cronjob list` only shows a truncated prompt preview.

## The Pattern

Cron sessions are stored in the same SQLite session DB as regular conversations. Their session IDs follow the format:

```
cron_{job_id}_{YYYYMMDD}_{HHmmss}
```

Example: `cron_7806a3f41013_20260721_235543`

### Step 1: Find the cron session ID

```python
# From cronjob list, get the job_id and last_run_at
# Then search session DB:
import sqlite3, datetime
from datetime import timezone
TZ = timezone(datetime.timedelta(hours=8))

conn = sqlite3.connect('/opt/data/state.db')
rows = conn.execute("""
    SELECT id, title, started_at, message_count
    FROM sessions
    WHERE id LIKE 'cron_{job_id}_%'
    ORDER BY started_at DESC
    LIMIT 5
""", ('cron_7806a3f41013%',)).fetchall()
for r in rows:
    ts = datetime.datetime.fromtimestamp(r[2], TZ).strftime('%Y-%m-%d %H:%M')
    print(f"{r[0]}  {ts}  msgs={r[3]}  {r[1]}")
conn.close()
```

### Step 2: Read the full session

```
session_search(session_id="cron_7806a3f41013_20260721_235543")
```

This returns ALL messages including:
- The full cron prompt (user message at index 0)
- Every tool call and response
- The final assistant output

### Step 3: Analyze

From the session you can extract:
- **Exact prompt text** — what the cron job was told to do
- **SQL queries used** — the actual database queries
- **Tool call sequence** — which tools were called and in what order
- **Errors** — any tool failures or exceptions
- **Output** — what was actually written/delivered

## Use Cases

| Scenario | What to look for |
|----------|-----------------|
| Cron job not producing expected output | Read the prompt → is the SQL correct? |
| Cron job format doesn't match skill spec | Compare prompt template with skill's SKILL.md |
| Cron job missing sessions | Check the SQL `WHERE` clause source filter |
| Cron job failing silently | Look for tool call errors in the session |

## Real Example (2026-07-22)

The daily log cron job (`7806a3f41013`) was investigated because user reported logs weren't being compiled. Reading the session revealed:
1. The SQL filter `source IN ('telegram', 'tui', 'cli')` excludes cron sessions
2. The prompt used Format B (結構摘要) while the skill specified Format A (content-enriched)
3. Only 1 human session existed that day, so the log was technically correct but sparse

This diagnosis would have been impossible from `cronjob list` alone (which only shows a truncated prompt preview).
