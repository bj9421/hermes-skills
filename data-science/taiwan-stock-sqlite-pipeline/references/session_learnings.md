# Session Learnings: Taiwan Stock SQLite Pipeline

## Key Discoveries

### 1. twstock API Usage
- `twstock.Stock.fetch()` does NOT exist - method requires `year` and `month` parameters
- Correct usage: `stock.fetch_from(start_year, start_month)` to get data from that point to present
- Example: `stock.fetch_from(2023, 1)` gets data from Jan 2023 to today

### 2. SQL Column Name Issues
- `transaction` is a reserved SQL keyword in SQLite
- Using it as a column name causes: `sqlite3.OperationalError: near "transaction": syntax error`
- Solution: Rename to `transaction_count` (or use quoted identifier)

### 3. Stock Code Sources
- After calling `twse.update()` and `tpex.update()`, the combined stock codes are available in `twstock.codes`
- NOT in `twse.codes` or `tpex.codes` individually after updates
- Filter for stocks: `[code for code, info in twstock.codes.items() if info.type == '股票']`

### 4. Rate Limiting Observations
- TWSE historical data limit: ~60 requests/minute
- Conservative rate: 50 requests/minute (1.2 seconds between requests) prevents 429 errors
- When 429 occurs, honor `Retry-After` header and use exponential backoff
- Best practice: Run downloads outside market hours (after 15:00 TW time)

### 5. Data Characteristics
- `volume` field from twstock is in shares; divide by 1000 to get "lots" (張) commonly used in Taiwan
- `turnover` is in thousands of New Taiwan Dollars (千元)
- `amplitude` field may be None for some records - handle gracefully
- Date format from twstock: datetime.date object → format as '%Y-%m-%d' for SQLite

### 6. Efficient Update Strategies
- Full historical download (e.g., from 2000-01) takes several hours for ~1900 stocks
- For daily operations, use incremental update: fetch only current month's data and filter to today
- This reduces daily update time to ~10-20 minutes

### 7. Error Handling Patterns
- Network errors and HTTP 429s require retry logic with exponential backoff
- Maximum 3 retries recommended before skipping a stock
- Log failures but continue processing other stocks

## Recommended Production Settings
```
Rate Limiter: max_per_minute = 50
Batch Size: 100 stocks per DB commit
Historical Start: 2023-01 (adjust based on needs)
Daily Update: Run after 15:30 TW time via cron
Backup: Daily copy of .db file
```

## Verification Queries
```sql
-- Check for duplicates (should return zero rows)
SELECT date, stock_code, COUNT(*) as cnt 
FROM daily_prices 
GROUP BY date, stock_code 
HAVING cnt > 1;

-- Check data integrity for a sample stock
SELECT 
  MIN(date) as first_date,
  MAX(date) as last_date,
  COUNT(*) as trading_days,
  AVG(close) as avg_close
FROM daily_prices 
WHERE stock_code = '2330';

-- Check for impossible OHLC relationships
SELECT * FROM daily_prices 
WHERE high < low OR high < open OR high < close 
   OR low > open OR low > close;
```