# Taiwan Stock Historical Download Session Summary (2026-06-05)

## Context
This session monitored the progress of a Taiwan stock historical data download process that stores daily price data in a SQLite database (`/opt/data/taiwan_stocks.db`) and maintains a checkpoint JSON file (`/opt/data/step2_checkpoint.json`).

## What Was Learned
1. **Database Locking Issues**: The background download process holds an exclusive lock on the SQLite database, preventing direct queries. Attempts to query the database resulted in `sqlite3.OperationalError: database is locked`.

2. **Workarounds Attempted**:
   - Using read-only mode via URI: `sqlite3.connect('file:path.db?mode=ro', uri=True)` - still failed due to lock
   - Copying the database file: `cp /opt/data/taiwan_stocks.db /tmp/taiwan_stocks_copy.db` - resulted in malformed database error, suggesting the copy happened mid-transaction
   - Using SQLite backup API: Also failed due to active lock

3. **Checkpoint File Reliable**: Despite database locking issues, the checkpoint JSON file (`step2_checkpoint.json`) was consistently accessible and provided reliable progress tracking.

4. **Progress Metrics Available from Checkpoint**:
   - Processed stocks count: 350 (from `len(checkpoint['processed'])`)
   - Estimated total stocks: ~1925
   - Progress percentage: ~18.2%

5. **Database Stats Unavailable During Active Download**: Due to locking, row counts, distinct stock counts, and date ranges could not be retrieved during the session.

## Concrete Example Output
The following progress message was generated:
```
Taiwan Stock Download Progress:
- Total rows in DB: unknown
- Distinct stocks: unknown
- Date range: unknown to unknown
- Processed stocks (checkpoint): 350/1925 (18.2%)
Database status: database is locked (journal present)
```

## Files Involved
- Database: `/opt/data/taiwan_stocks.db` (locked during active download)
- Checkpoint: `/opt/data/step2_checkpoint.json` (accessible, contains `"processed": [...]` array)
- Temporary scripts created for querying:
  - Multiple attempts in `/tmp/` directory

## Key Takeaway
When monitoring long-running data download processes that use SQLite databases:
1. **Always have a secondary progress tracking mechanism** (like a checkpoint file)
2. **Expect database locks during active writes** - design monitoring to handle this gracefully
3. **Checkpoint files can provide meaningful progress** even when database queries fail
4. **Report "unknown" for database-derived metrics** when locks prevent access, rather than blocking the entire progress report
5. **Do not rely on file copies or backup operations** when database is locked, as they may yield malformed databases
6. **Use read-only URI connections with timeout** as the first attempt, but accept that they may still fail under heavy write load
7. **Discover table names dynamically** rather than hardcoding table names in queries