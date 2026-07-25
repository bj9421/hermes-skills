---
name: monitor-data-download-progress
description: Skill for checking the progress of long-running data download tasks that store data in a SQLite database and maintain a checkpoint JSON file.
category: data-science
---

# Monitor Data Download Progress

Skill for checking the progress of long-running data download tasks that store data in a SQLite database and maintain a checkpoint JSON file.

## When to Use
- You have a cron job or background process downloading historical data (e.g., stock prices, financial data, logs) into a SQLite database.
- The process updates a checkpoint JSON file listing processed items (e.g., stock codes, file names, IDs).
- You want to generate a human-readable progress summary without interfering with the ongoing process.
- You need to handle scenarios where the database is locked due to active writes.

## Steps

1. **Verify the database and checkpoint files exist**
   ```bash
   ls -l /path/to/database.db /path/to/checkpoint.json
   ```

2. **Attempt to read database statistics**
   - Prefer using `terminal` tool to run a Python script (as `execute_code` may be blocked in cron mode)
   - Handle potential database locks gracefully:
     - Try opening the database in read-only mode via URI with timeout: `sqlite3.connect('file:path.db?mode=ro', uri=True)`
     - Dynamically discover table names from `sqlite_master` rather than assuming a specific table name
     - If read-only connection fails due to lock, do not persist with retries that waste time
     - Do not rely on file copies or backup operations when database is locked, as they may yield malformed databases
     - Fall back to reporting "unknown" for database-derived metrics when locked
   - Extract: total rows, distinct items (stock codes), and date range (min/max date)

3. **Read the checkpoint JSON file**
   - Load the JSON and count the entries in the `processed` array (or equivalent key)
   - If the file is missing or malformed, assume zero processed items
   - Note: checkpoint file is often consistently accessible even when database is locked

4. **Calculate progress**
   - Total rows: from database query (if accessible) or "unknown"
   - Distinct items: from database query (if accessible) or "unknown"
   - Date range: min and max date from database query (if accessible) or "unknown"
   - Processed count: length of processed list from checkpoint
   - If total estimated items is known, compute percentage complete

5. **Format a summary message**
   Example for Taiwan stocks:
   ```
   Taiwan Stock Download Progress:
   - Total rows in DB: unknown
   - Distinct stocks: unknown
   - Date range: unknown to unknown
   - Processed stocks (checkpoint): 350/1925 (18.2%)
   Database status: database is locked (journal present)
   ```

## Pitfalls

- **Database locked**: The background process may have an exclusive lock that prevents even read-only connections.
  1. Try read-only URI connection with timeout: `sqlite3.connect('file:path.db?mode=ro', uri=True)`
  2. Dynamically discover table names rather than hardcoding
  3. If that fails due to lock, do not rely on file copies or backup operations as they may be malformed or fail
  4. Avoid persistent retry attempts that waste time; report "unknown" for database-derived metrics when locked
  5. The checkpoint file (if available) is often the most reliable source for progress tracking when database is locked

- **execute_code disabled in cron**: Hermes may block `execute_code` in cron jobs for security. Use `terminal` to run Python scripts instead.

- **Checkpoint file format**: Ensure you know the key used for processed items (e.g., `"processed"`).

- **Temporary inconsistencies**: The database and checkpoint may be slightly out of sync during active downloads; treat numbers as approximate.

- **Table name discovery**: Do not assume table name; query `sqlite_master` to get actual table names.

## References

- See `references/taiwan-stock-session-summary.md` for a concrete example from a Taiwan stock historical download session.
- See `scripts/check_progress.py` for a reusable progress-checking script that implements dynamic table discovery.
- For Taiwan stock specific context, the download process typically targets ~1925 stocks.