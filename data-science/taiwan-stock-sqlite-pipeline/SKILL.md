---
name: taiwan-stock-sqlite-pipeline
description: Build a SQLite-based pipeline for downloading Taiwan stock daily price data with rate limit handling and incremental updates.
version: 1.2
author: Hermes Agent
---

# Taiwan Stock Daily Price Data Pipeline (SQLite)

This skill outlines a robust, rate-limit-friendly approach to download historical and daily Taiwan stock price data (TWSE & TPEX) into a SQLite database for analysis.

## Overview
- Data source: `twstock` Python library (wrapper for TWSE/TPEX APIs)
- Storage: SQLite database with table `daily_prices`
- Key concerns: Respect TWSE rate limits, avoid IP bans, support incremental daily updates.
- **CRITICAL**: TWSE/TPEX APIs have NO documented rate limit. As of 2026-07, real-world testing showed zero 429 errors up to 300 rpm. Always verify empirically before bulk scraping.
- Output: Queryable SQLite file usable via SQL, pandas, or any SQLite client.

## Prerequisites
- Python 3.8+
- Packages: `twstock`, `pandas`
- Optional: `openpyxl` for Excel export (not required)

Install:
```bash
pip install twstock pandas
```

## Database Schema
```sql
CREATE TABLE IF NOT EXISTS daily_prices (
    date TEXT NOT NULL,          -- YYYY-MM-DD
    stock_code TEXT NOT NULL,    -- e.g., 2330
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume INTEGER,              -- 成交股數 (張)
    turnover REAL,               -- 成交金額 (千元)
    transaction_count INTEGER,   -- 成交筆數 (note: renamed from 'transaction' to avoid SQL keyword)
    amplitude REAL,
    PRIMARY KEY (date, stock_code)
);
CREATE INDEX IF NOT EXISTS idx_stock ON daily_prices(stock_code);
CREATE INDEX IF NOT EXISTS idx_date  ON daily_prices(date);
```

## Step‑by‑Step Procedure

### 1. Initialize DB (run once)
```python
import sqlite3
from pathlib import Path

def init_db(db_path: Path = Path("taiwan_stocks.db")):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS daily_prices (
            date TEXT NOT NULL,
            stock_code TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            turnover REAL,
            transaction_count INTEGER,
            amplitude REAL,
            PRIMARY KEY (date, stock_code)
        );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_stock ON daily_prices(stock_code);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_date ON daily_prices(date);")
    conn.commit()
    conn.close()
```

### 2. Rate‑Limiter Wrapper
```python
import time

class TWSERateLimiter:
    def __init__(self, max_per_minute: int = 120):  # Empirical: 300 rpm tested OK 2026-07
        self.min_interval = 60.0 / max_per_minute
        self.last_request = 0.0
    def wait(self):
        elapsed = time.time() - self.last_request
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_request = time.time()
```

### 3. Download Single Stock (with retries)
```python
import requests
from twstock import Stock
from datetime import datetime

def fetch_stock_data(stock_code: str, limiter: TWSERateLimiter, start_year: int, start_month: int, max_retries: int = 3):
    """
    Fetch historical data for a single stock from a given start year/month to present.
    Returns list of dicts ready for SQLite upsert.
    """
    for attempt in range(max_retries):
        try:
            limiter.wait()
            stock = Stock(stock_code)
            data = stock.fetch_from(start_year, start_month)
            if not data:
                return []
            # Convert to list of dicts
            records = []
            for d in data:
                records.append({
                    "date": d.date.strftime("%Y-%m-%d"),
                    "stock_code": stock_code,
                    "open": float(d.open) if d.open is not None else None,
                    "high": float(d.high) if d.high is not None else None,
                    "low": float(d.low) if d.low is not None else None,
                    "close": float(d.close) if d.close is not None else None,
                    "volume": int(d.capacity) if d.capacity is not None else None,
                    "turnover": float(d.turnover) if d.turnover is not None else None,
                    "transaction_count": int(d.transaction) if d.transaction is not None else None,
                    "amplitude": float(getattr(d, "amplitude", None)) if getattr(d, "amplitude", None) is not None else None
                })
            return records
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                retry_after = int(e.response.headers.get("Retry-After", 60))
                time.sleep(retry_after * (attempt + 1))  # exponential backoff
                continue
            else:
                raise
        except Exception:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)
    return []
```

### 4. Batch Upsert into SQLite
```python
def upsert_records(conn, records):
    if not records:
        return 0
    cur = conn.cursor()
    cols = ", ".join(records[0].keys())
    placeholders = ", ".join(["?"] * len(records[0]))
    sql = f"""
        INSERT OR REPLACE INTO daily_prices ({cols})
        VALUES ({placeholders});
    """
    data = [tuple(r[c] for c in records[0].keys()) for r in records]
    cur.executemany(sql, data)
    conn.commit()
    return len(data)
```

### 5. Full Market Download (Historical Bootstrap)
```python
from twstock import twse, tpex
import time

def download_all_historical(db_path: Path = Path("taiwan_stocks.db"), start_year: int = 2000, start_month: int = 1):
    """
    Download historical data for all stocks from a fixed start date (e.g., 2000-01).
    Warning: This may take several hours depending on number of stocks and network speed.
    For regular updates, prefer the incremental daily update function.
    """
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    limiter = TWSERateLimiter(max_per_minute=50)

    # Update code lists once
    twse.update()
    tpex.update()
    # After update, twstock.codes contains all codes from both exchanges
    all_codes = {code: info for code, info in twstock.codes.items() if info.type == "股票"}

    total = len(all_codes)
    success = 0
    for idx, (code, info) in enumerate(all_codes.items(), start=1):
        try:
            records = fetch_stock_data(code, limiter, start_year, start_month)
            if records:
                inserted = upsert_records(conn, records)
                success += 1
                print(f"[{idx}/{total}] {code} ({info.name}): {inserted} records")
            else:
                print(f"[{idx}/{total}] {code}: No data")
        except Exception as e:
            print(f"[{idx}/{total}] {code}: Error - {e}")
        # Optional: progress logging every 50 stocks
        if idx % 50 == 0:
            print(f"  Progress: {idx}/{total} stocks processed")
    conn.close()
    print(f"Completed: {success}/{total} stocks processed")
```

### 6. Incremental Daily Update (Recommended for daily runs)
```python
from twstock import twse, tpex, Stock
from datetime import datetime

def download_today_only(db_path: Path = Path("taiwan_stocks.db")):
    """
    Download only today's trading data for all stocks.
    Ideal for daily automated runs (e.g., via cron after 15:30 TW time).
    """
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    limiter = TWSERateLimiter(max_per_minute=50)

    # Update code lists once
    twse.update()
    tpex.update()
    all_codes = {code: info for code, info in twstock.codes.items() if info.type == "股票"}

    today = datetime.now().date()
    processed = 0
    updated = 0
    for code, info in all_codes.items():
        try:
            limiter.wait()
            stock = Stock(stock_code=code)
            # Fetch from current month to get today's data
            data = stock.fetch_from(today.year, today.month)
            # Keep only today's record
            today_data = [d for d in data if d.date == today]
            if not today_data:
                # No trading today (e.g., holiday)
                continue
            records = [{
                "date": d.date.strftime("%Y-%m-%d"),
                "stock_code": code,
                "open": float(d.open) if d.open is not None else None,
                "high": float(d.high) if d.high is not None else None,
                "low": float(d.low) if d.low is not None else None,
                "close": float(d.close) if d.close is not None else None,
                "volume": int(d.capacity) if d.capacity is not None else None,
                "turnover": float(d.turnover) if d.turnover is not None else None,
                "transaction_count": int(d.transaction) if d.transaction is not None else None,
                "amplitude": float(getattr(d, "amplitude", None)) if getattr(d, "amplitude", None) is not None else None
            } for d in today_data]
            upsert_records(conn, records)
            updated += 1
        except Exception as e:
            print(f"Error for {code}: {e}")
        processed += 1
        if processed % 100 == 0:
            print(f"  Processed {processed}/{len(all_codes)} stocks...")
    conn.close()
    print(f"Finished. Updated {updated} stocks with today's data.")
```

## Rate‑Limit Guidelines (Empirical)

**TWSE/TPEX public historical data endpoints have NO documented rate limit.** As of July 2026, real-world testing showed:
- 60 rpm (1s/stock) → ✅ 0 errors
- 120 rpm (0.5s/stock) → ✅ 0 errors
- 180 rpm (0.33s/stock) → ✅ 0 errors
- 240 rpm (0.25s/stock) → ✅ 0 errors
- 300 rpm (0.2s/stock) → ✅ 0 errors (sustained 5 min)

**Recommendation**: Use 120 rpm for daily incremental updates (safe margin). Use up to 300 rpm for one-time historical backfill (test first). Use 60 rpm for `fix_incomplete_v3.py` backfill runs (API response time dominates, higher rates waste CPU on waits).

- Always verify empirically before bulk scraping. Do NOT assume documented limits exist — test with a ramp-up sequence (60→120→180→240→300 rpm, 10 stocks each) and check for 429 responses.
- If you do receive HTTP 429, honor `Retry-After` header and back‑off exponentially. Then reduce target rate by 20%.
- Re-test rate limits every 3-6 months — they may change without notice.
- Avoid running during peak market hours (09:00–13:30 TW) if possible; schedule after 15:00 for daily updates.

## Verification
After any download, run:
```sql
SELECT COUNT(*) AS total_rows,
       COUNT(DISTINCT stock_code) AS stock_count
FROM daily_prices;
```
Expect `total_rows` ≈ (number of stocks) × (average trading days). 
Check for duplicates:
```sql
SELECT date, stock_code, COUNT(*) AS cnt
FROM daily_prices
GROUP BY date, stock_code
HAVING cnt > 1;
```
Should return zero rows.

## Maintenance
- **Backup**: Copy the `.db` file; SQLite is single‑file.
- **Vacuum**: Periodically run `VACUUM;` to reclaim space.
- **Data retention**: To keep only recent N years, delete older rows:
  ```sql
  DELETE FROM daily_prices WHERE date < date('now', '-5 year');
  VACUUM;
  ```
- **Schedule**: Use `cron` (Linux) or Task Scheduler (Windows) to run `download_today_only` each trading day after 15:30.

## FinMind API Integration (Alternative Data Source)

For financial statement analysis (income, balance sheet, cash flow), use FinMind API instead of TWSE/TPEX.

### CRITICAL: Token Authentication Required
FinMind free tier uses **IP-based rate limiting**. Without token, rapid requests trigger 25-28 minute bans. Every API call MUST include the token.

#### Token Loading Pattern
```python
import os

# Load from env var or .env file (check in order)
_FINMIND_TOKEN = os.environ.get("FINMIND_API_KEY")
if not _FINMIND_TOKEN:
    _env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    try:
        with open(_env_path, "r") as _f:
            for _line in _f:
                if _line.startswith("FINMIND_API_KEY="):
                    _FINMIND_TOKEN = _line.split("=", 1)[1].strip()
                    break
    except Exception:
        pass
```

#### Parameter Helper (use in EVERY API call)
```python
def _make_params(**kwargs):
    params = kwargs
    if _FINMIND_TOKEN:
        params["token"] = _FINMIND_TOKEN
    return params

# Usage:
r = requests.get(FINMIND_URL, params=_make_params(
    dataset="TaiwanStockFinancialStatements",
    data_id="2330",
    start_date="2020-01-01"
), timeout=15, verify=False)
```

### Ban Detection
```python
def is_ip_banned():
    """Return retry_after seconds if banned, 0 if OK."""
    try:
        r = requests.get(FINMIND_URL, params=_make_params(
            dataset="TaiwanStockFinancialStatements", data_id="2330", start_date="2024-01-01"
        ), timeout=10, verify=False)
        if r.status_code == 403:
            return r.json().get("retry_after", 300)
        return 0
    except Exception:
        return 0
```

### Key Datasets
| Dataset | Token Required? | Notes |
|---------|----------------|-------|
| `TaiwanStockInfo` | No | Lightweight metadata, no rate limit |
| `TaiwanStockFinancialStatements` | Yes | Income statement |
| `TaiwanStockBalanceSheet` | Yes | Balance sheet |
| `TaiwanStockCashFlowsStatement` | Yes | Cash flow |
| `TaiwanStockDividend` | Yes | Dividend data |
| `TaiwanStockPrice` | Yes | Historical prices |

### Pitfalls
- **`.env` path**: From `screening/screener.py`, token file is at `../.env` (one level up), NOT `../../.env` (resolves to `/opt/.env` which doesn't exist).
- **Consistency**: Every file that calls FinMind must define its own `_make_*_params()` helper — don't share across modules.
- **403 response**: FinMind returns `{"success": null, "retry_after": 1700}` — parse `retry_after` for wait time.

## References
- `twstock` documentation: https://twstock.readthedocs.io/
- TWSE OpenAPI: https://openapi.twse.com.tw/
- FinMind API: https://finmind.github.io/
- Session-specific learnings: references/session_learnings.md
- Rate limit probe script: scripts/rate_limit_test.py (run before any bulk download)
- Checkpoint mechanism: references/checkpoint_pattern.md
- Retry reconciliation for cron-based batch downloads: references/retry_reconciliation.md
- OHLC cross-verification tool (verify_daily_prices.py, timing, result interpretation): references/ohlc_verification.md
- Cron deployment guide (path resolution, timeout budgeting, error layers): references/cron_deployment.md
- Ready-to-use template: templates/batch_download_with_timeout.py
- FinMind token auth fix: references/finmind_token_fix.md
- fix_incomplete_v3.py rate limit fix (MAX_RUNTIME/per_minute tuning): references/fix_incomplete_v3_rate_limit.md

## Notes
- This skill was distilled from a live session where the user requested a step‑by‑step plan for downloading Taiwan stock data into SQLite while avoiding API bans.
- Key pitfalls discovered:
  1. The `twstock.Stock.fetch()` method requires `year` and `month` arguments; there is no no‑argument variant. Use `fetch_from(start_year, start_month)` to get data from that point to present.
  2. `transaction` is an SQL reserved keyword; rename column to `transaction_count` (or quote it) to avoid syntax errors.
  3. After calling `twse.update()` and `tpex.use()`, the combined stock codes are available in `twstock.codes` (not `twse.codes` or `tpex.codes` individually).
  4. The `amplitude` field may be `None` for some records; handle gracefully.
  5. **`twstock.Stock(code)` constructor can throw `TooManyRedirects` exceptions** — these are TWSE transient network failures, not invalid stock codes. Wrap BOTH `Stock(code)` and `stock.fetch_from()` in try/except. Never let `Stock()` throw uncaught; the stock is still valid on retry.
  6. **Batch downloads over Cron require correct timeout budgeting.** At 120 rpm (0.5s/stock), each stock takes ~2.2s (rate-limit wait + TWSE fetch + DB write). For a 300s cron timeout, budget max ~120 stocks/run with a 30s buffer. With the previous conservative 50 rpm (~25s/stock), only 4-5 stocks/run fit in 120s — performance improved 10× with actual rate limit testing.
  7. **Retry candidates pattern:** When a stock fails with `TooManyRedirects` during `Stock()`, it's marked as "processed" in the checkpoint to avoid infinite retries. But the actual data may be valid. After the main run finishes, do a reconciliation pass: query `daily_prices` for stocks in the checkpoint with < 100 records — these are retry candidates. Re-add them to the todo list on the next run.
  8. **Stale WAL journal files cause "database is locked":** If a background data download is killed (SIGTERM/KILL) without clean SQLite shutdown, stale `.db-wal` and `.db-shm` files persist. Subsequent connections get `sqlite3.OperationalError: database is locked`. Fix: kill orphaned Python processes, `rm -f *.db-wal *.db-shm`, then reconnect. For resilience, always set `PRAGMA busy_timeout=60000;` after connecting so concurrent writers wait rather than fail immediately.
  - 9. **⛔ MANDATORY: Verify API limits before bulk scraping.** Do NOT start a bulk download without first probing the API's actual rate limit. The user explicitly expects this check ("爬資料前有先搜尋api rpm 限制嗎"). Run a ramp-up test (60→120→180→240→300 rpm, 10 stocks per level, check for 429 after each level). If limits are found, respect them. If none found (like TWSE/TPEX), use 120 rpm for daily runs. Document the test date in your notes so future sessions know when it was last verified.
  - 10. **⚠️ screen_cache.price vs daily_prices.close date mismatch.** When debugging OHLC verification discrepancies, NEVER compare `screen_cache.price` against `daily_prices.close` for a specific historical date. `update_all_tech_indicators.py` populates `screen_cache.price` from the LATEST available date in `daily_prices`, while OHLC verify queries a SPECIFIC date (yesterday). This causes ~50% of stocks to show >1% price difference even when both sources are correct. See `references/ohlc-missing-data-investigation-2026-07-24.md` in the `taiwan-stock-data-pipeline` skill.
- The approach prioritises safety (rate limiting) and simplicity (SQLite) over raw speed.
- For higher‑frequency data (intraday/tick), consider a dedicated time‑series database or message queue.

---