# Retry Reconciliation Pattern for Cron-Based Batch Downloaders

## Problem
When downloading Taiwan stock data with `twstock`, transient TWSE network failures (`TooManyRedirects`, HTTP 429, timeout) can cause `Stock()` or `stock.fetch_from()` to throw exceptions. To avoid infinite retries, the checkpoint pattern marks these stocks as "processed" — but the data is never actually stored in the DB.

## Pattern: Post-Run Reconciliation

### Option A: Simple Discard (one-shot retry)
Remove retry candidates from the processed set so they're re-processed next run.

### Option B: Retry Counter (production, limits wasted runs)
Track how many times each stock has been retried. After N failed retries, give up permanently. This prevents the same stocks from being retried every single cron run forever.

```python
RETRY_LIMIT = 3
retry_counter_path = Path('/opt/data/step2_retry_counter.json')

# Load counter
retry_count = {}
if retry_counter_path.exists():
    try:
        retry_count = json.loads(retry_counter_path.read_text())
    except Exception:
        retry_count = {}

# Filter retry candidates by remaining retries
retry_candidates = []
for code in processed_set:
    cur.execute('SELECT COUNT(*) FROM daily_prices WHERE stock_code = ?', (code,))
    cnt = cur.fetchone()[0]
    if cnt < 100:
        tries = retry_count.get(code, 0)
        if tries < RETRY_LIMIT:
            retry_candidates.append(code)
            retry_count[code] = tries + 1
        # else: give up, keep in processed_set

# At end of run, save counter
retry_counter_path.write_text(json.dumps(retry_count, ensure_ascii=False, indent=2))
```

### Benefits
- Fully automatic — no manual intervention needed for failed stocks
- Handles transient errors gracefully (TWSE is flaky, not the data's fault)
- Only retries stocks that actually need it (skips stocks with full data)
- Stops retrying once data is successfully stored (next run sees > 100 records)

### Threshold Tuning
- **< 100 records**: Conservative — catches nearly all failures without many false positives
- **< 500 records**: More aggressive — also catches partial failures (e.g., only 6 months fetched)
- **< 1 record**: Only catches stocks that completely failed — misses partial downloads