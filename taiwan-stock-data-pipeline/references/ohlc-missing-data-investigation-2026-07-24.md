# OHLC Verification Missing Data Investigation (2026-07-24)

## Problem

On 2026-07-24, the OHLC verification cron (ohlc-verification-full, 16:35 Mon-Fri) reported:
- **1925 sampled, 774 matched, 1146 missing_data, 5 api_fetch_failed**
- 1146/1925 = 59.6% "missing_data" seems abnormally high

## Root Cause Analysis

### What "missing_data" means
In `compare_prices(db_close, api_close)`:
```python
if db_close is None or api_close is None:
    return False, "missing_data"
```
Since `api_data` exists (otherwise it would be `api_fetch_failed`), `api_close` is not None.
Therefore, `db_close` IS None for all 1146 stocks.

### Database check
```sql
-- How many stocks have 2026-07-23 data?
SELECT COUNT(DISTINCT stock_code) FROM daily_prices WHERE date = '2026-07-23';
-- Result: 1917 (out of 1925)
```

So only ~8 stocks should genuinely lack 2026-07-23 data. Where do the other 1138 come from?

### Key discovery: screen_cache.price vs daily_prices.close mismatch
```sql
SELECT COUNT(*) FROM screen_cache sc
INNER JOIN daily_prices dp ON sc.stock_code = dp.stock_code AND dp.date = '2026-07-23'
WHERE sc.price IS NOT NULL AND dp.close IS NOT NULL
AND ABS(sc.price - dp.close) / sc.price > 0.01;
-- Result: 960 stocks have >1% price difference
```

**Why?** `screen_cache.price` is populated by `update_all_tech_indicators.py` which reads from the LATEST date in `daily_prices` (2026-07-24). But the verify script queries `daily_prices WHERE date = '2026-07-23'`. The prices differ because they're from different dates.

This is NOT the cause of missing_data — the verify script reads from `daily_prices`, not `screen_cache`. But it explains why manual price comparison shows large discrepancies.

### Most likely explanation
The verify script ran at 16:09 on 2026-07-24. At that time:
1. `twse_daily_update` (16:00) had populated daily_prices for 2026-07-24 but NOT yet committed 2026-07-23 data for all stocks
2. OR twstock/yfinance API returned data for dates OTHER than 2026-07-23
3. OR the `get_yesterday()` function returned a different date than expected

### Verification needed
To confirm which explanation is correct:
```sql
-- Check if 2026-07-23 data exists NOW (post-update)
SELECT date, COUNT(DISTINCT stock_code) 
FROM daily_prices 
WHERE date IN ('2026-07-23', '2026-07-24')
GROUP BY date;

-- Check screen_cache cached_at timestamp
SELECT MAX(cached_at) FROM screen_cache;
-- Result: 2026-07-24T17:00:47 (AFTER the verify ran at 16:09)
```

## Lessons Learned

1. **Timing matters:** OHLC verify runs at 16:35, but twse_daily_update finishes around 16:24. There may be a race condition where some stocks haven't been written to daily_prices yet.

2. **screen_cache.price reflects latest date, not target date.** Don't compare screen_cache.price against daily_prices.close for a specific historical date — they may be from different dates.

3. **The empty stock_data.db (0 bytes) at screening/ is a red herring.** All scripts correctly resolve to `/opt/data/taiwan_stocks.db` via DB_PATH logic. Never confuse it with the real DB.

4. **Missing data rate improved over time:**
   - 2026-07-14: 31.6% missing_data (608/1925)
   - 2026-07-16: 1.09% missing_data (21/1925)  
   - 2026-07-20: 65% missing_data (52/80 sample) — pipeline lag
   - 2026-07-23: 59.6% missing_data (1146/1925) — timing/race condition suspected

## Diagnostic Queries

```sql
-- Check data coverage per recent date
SELECT date, COUNT(DISTINCT stock_code) AS stocks_with_data
FROM daily_prices
WHERE date >= date('now', '-7 days')
GROUP BY date
ORDER BY date DESC;

-- Find stocks in screen_cache but without a specific date
SELECT sc.stock_code
FROM screen_cache sc
LEFT JOIN daily_prices dp ON sc.stock_code = dp.stock_code AND dp.date = '2026-07-23'
WHERE sc.price IS NOT NULL AND dp.stock_code IS NULL;

-- Check which stocks have both prices but differ by >1%
SELECT sc.stock_code, sc.price AS cache_price, dp.close AS db_price,
       ROUND(ABS(sc.price - dp.close) / sc.price * 100, 2) AS diff_pct
FROM screen_cache sc
INNER JOIN daily_prices dp ON sc.stock_code = dp.stock_code AND dp.date = '2026-07-23'
WHERE ABS(sc.price - dp.close) / sc.price > 0.01
LIMIT 10;
```
