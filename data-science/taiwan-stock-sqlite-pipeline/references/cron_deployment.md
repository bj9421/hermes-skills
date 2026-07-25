# Deploying Taiwan Stock Pipeline Under Cron (Hermes)

## Key Lessons from Production Deployment

### 1. Cron `script` + `no_agent` Path Resolution

When using `cronjob(action='create', script='run_twse_batch.sh', no_agent=True, workdir='/opt/data')`:

- The `workdir` is the **working directory** of the shell command, NOT the root for script resolution.
- `script` values are resolved **relative to an internal cron scripts directory**, typically under the Hermes home's `scripts/` dir — NOT relative to workdir.
- If your script lives at `$workdir/.hermes/scripts/run_twse_batch.sh`, **do NOT** set `script='.hermes/scripts/run_twse_batch.sh'` — the cron system will prefix it with its own scripts dir and produce a double-path like `scripts/.hermes/scripts/run_twse_batch.sh`.
- **Fix**: Put your script in the cron default scripts path: copy it to `$workdir/scripts/run_twse_batch.sh`, then set `script='run_twse_batch.sh'`.
- Alternatively, use `script` to point at a small shell wrapper that cd's to workdir and invokes the Python script with absolute paths.

### 2. Cron Timeout Budget

- Cron `no_agent` scripts default to a **120-second timeout**.
- For `twstock` batch downloads, each stock takes ~25s (1.5s rate-limit wait + ~20-25s TWSE fetch + DB write).
- **Formula**: `batch_size × 25 ≤ cron_timeout - 10` (leave 10s buffer for checkpoint save).
- Set `TIME_BUDGET_SEC` in the Python script to match, and put a time-check break in the loop:
  ```python
  start_time = time.time()
  for code in batch:
      if time.time() - start_time >= TIME_BUDGET_SEC - 10:
          print(f'Time budget nearly exhausted ({elapsed:.0f}s), stopping batch early')
          break
      # ... process stock
  ```

### 3. Rate Limiter Calculation

- Respect TWSE historical data rate limit: **60 requests/minute**.
- Conservative setting: `40/min` (1.5s interval). Real throughput is lower due to TWSE fetch time.
- The rate limiter wait interval is **per-stock overhead** — actual clock time per stock is `max(1.5s, TWSE_response_time)` which averages ~25s.

### 4. Stock Count

- After `twstock.twse.update()` and `twstock.tpex.update()`, the combined codes are in `twstock.codes`.
- Filter for stocks only: `{c: i for c, i in twstock.codes.items() if i.type == '股票'}`.
- As of mid-2026, there are **~1,925** stocks total.

### 5. Error Handling Layers

| Failure Point | Exception | Recovery |
|---|---|---|
| `twstock.Stock(code)` constructor | `TooManyRedirects`, `ConnectionError` | Wrap in try/except, mark as processed, retry via reconciliation |
| `stock.fetch_from()` | `TooManyRedirects`, HTTP errors | Same — already wrapped |
| Rate limiter `wait()` | `KeyboardInterrupt` (manual stop) | Wrap to prevent unhandled termination |

The `Stock()` constructor is the most common failure point — TWSE can return 30+ redirects for valid stock codes during peak hours. Always wrap **both** `Stock()` and `.fetch_from()` in separate try/except blocks.