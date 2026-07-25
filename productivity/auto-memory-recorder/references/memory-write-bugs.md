# memory_write.py — Known Bugs & Failure Patterns

## Bug: `fact_exists()` 100-row window — ✅ FIXED (2026-07-17)

**Status:** ✅ Fixed. The fix was applied during a cron auto-memory-scan session on 2026-07-17.

### Root Cause (Historical)

In `memory_write.py`, the `fact_exists()` function queried only the last 100 rows:

```python
cursor = conn.execute(
    "SELECT fact_id, content FROM facts ORDER BY fact_id DESC LIMIT 100"
)
```

Once the memory store exceeded 100 facts (~212 as of 2026-07-17), content-duplicate facts with `fact_id < (max_id - 100)` were **invisible** to this check. The function returned `None`, and the subsequent `INSERT` hit the SQLite UNIQUE constraint on `facts.content`, crashing with:

```
sqlite3.IntegrityError: UNIQUE constraint failed: facts.content
```

### Failure Transcript (Historical — 2026-07-16)

Using `--bulk` with 4 entries — the crash happened on entry #2 because the existing match (fact #70) was 127 rows back, outside the 100-row window:

| # | Content | f_id match | Within 100? | Result |
|---|---------|------------|-------------|--------|
| 1 | "Hermes dashboard accessible at dietpi4:5000" | #151 (fits) | ✅ Yes | ✅ Updated |
| 2 | "Cron job definitions stored in /opt/data/cron/jobs.json" | #70 (stale) | ❌ No (127 rows back) | 💥 UNIQUE crash |
| 3-4 | (remaining entries) | — | — | Never reached |

### Fix Applied (2026-07-17)

**What changed:** The LIMIT-100 query was replaced with a full table scan:

```python
# BEFORE (broken):
cursor = conn.execute(
    "SELECT fact_id, content FROM facts ORDER BY fact_id DESC LIMIT 100"
)

# AFTER (fixed):
cursor = conn.execute("SELECT fact_id, content FROM facts")
```

**Why this works:** The table is bounded (~212 facts, ~19K chars) — a full scan is O(n) but n is tiny. The UNIQUE constraint on `facts.content` already guarantees no two rows share content, so the loop over all rows is guaranteed to catch the match. There is no performance concern at the current or foreseeable scale.

**Verification:** Ran `--bulk` with 5 JSON lines (4 existing + 1 new) against a 212-fact store:
- 4 existing entries → correctly identified as duplicates, `updated_at` refreshed
- 1 new entry → saved as fact #213
- No crashes, no IntegrityErrors

### Recovery Steps (Legacy — pre-fix)

These steps were used to work around the bug before the fix was applied. No longer needed but kept for reference:

1. **Identify the crashing entry** — it's the one that would have been processed next. Entries before it succeeded; it and everything after it failed.
2. **Verify survivors** — run `memory_write.py --list 10` and check that entries #1..N actually landed.
3. **Retry remaining entries individually** — call `memory_write.py` once per entry, catching and skipping UNIQUE errors.
4. **Alternative: `INSERT OR IGNORE`** — patch the script's SQL and handle the zero-rowcount case with a timestamp update.
