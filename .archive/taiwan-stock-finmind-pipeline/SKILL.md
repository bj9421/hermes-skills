---
name: taiwan-stock-finmind-pipeline
description: Build a SQLite-based pipeline for downloading Taiwan stock financial data (income, balance sheet, cash flow) via FinMind API with token authentication and IP ban prevention.
version: 1.0
author: Hermes Agent
---

# Taiwan Stock FinMind Data Pipeline

This skill covers integrating FinMind API for Taiwan stock financial analysis — proper token authentication, rate limit handling, and IP ban prevention.

## Overview
- **Data source**: FinMind API (`https://api.finmindtrade.com/api/v4/data`)
- **Key datasets**: `TaiwanStockFinancialStatements`, `TaiwanStockBalanceSheet`, `TaiwanStockCashFlowsStatement`, `TaiwanStockDividend`, `TaiwanStockPrice`
- **Storage**: SQLite database (`taiwan_stocks.db`)
- **Critical concern**: FinMind free tier uses IP-based rate limiting. Without a token, rapid sequential requests trigger 25-28 minute IP bans.

## Prerequisites
- Python 3.8+
- FinMind API token (free tier available at https://finmind.github.io/)
- Packages: `pandas`, `requests`

## Step 1: API Token Configuration

### CRITICAL: Always use token authentication
FinMind free tier without token = IP-based banning. Every API call MUST include the token.

```python
import os

# Load API token from .env or environment variable
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

### Token file locations (check in order)
1. Environment variable `FINMIND_API_KEY`
2. `{project_root}/.env` — e.g., `/opt/data/.env`
3. **Never** use `../../.env` from project root — that resolves to wrong path

## Step 2: Parameter Helper Function

Every API call must use a helper that injects the token:

```python
def _make_params(**kwargs):
    """Build API params dict with token automatically included."""
    params = kwargs
    if _FINMIND_TOKEN:
        params["token"] = _FINMIND_TOKEN
    return params
```

Usage:
```python
r = requests.get(
    "https://api.finmindtrade.com/api/v4/data",
    params=_make_params(
        dataset="TaiwanStockFinancialStatements",
        data_id="2330",
        start_date="2020-01-01",
    ),
    timeout=15,
    verify=False,  # Self-signed cert on some proxies
)
```

## Step 3: Available Datasets

| Dataset | Description | Typical Use |
|---------|-------------|-------------|
| `TaiwanStockFinancialStatements` | Income statement (營收、毛利率、EPS) | Revenue analysis, margin trends |
| `TaiwanStockBalanceSheet` | Balance sheet (資產負債表) | Debt ratio, current ratio |
| `TaiwanStockCashFlowsStatement` | Cash flow statement | Operating cash flow, free cash flow |
| `TaiwanStockDividend` | Dividend distribution | Cash dividend, stock dividend |
| `TaiwanStockPrice` | Historical stock prices | Technical analysis, moving averages |
| `TaiwanStockInfo` | Stock metadata (name, industry) | Stock list, NO token needed |
| `TaiwanStockTradingVolume` | Daily trading volume | Volume analysis |

**Note**: `TaiwanStockInfo` is a lightweight metadata endpoint that does NOT get rate-limited. It can be called without token.

## Step 4: Ban Detection and Prevention

### Check if IP is banned
```python
def is_ip_banned():
    """Return retry_after seconds if banned, 0 if OK."""
    try:
        r = requests.get(
            FINMIND_URL,
            params=_make_params(
                dataset="TaiwanStockFinancialStatements",
                data_id="2330",
                start_date="2024-01-01"
            ),
            timeout=10,
            verify=False
        )
        if r.status_code == 403:
            d = r.json()
            return d.get("retry_after", 300)
        return 0
    except Exception:
        return 0
```

### Before each batch job:
1. **Check ban status first** — don't start a batch if already banned
2. **If banned, wait for `retry_after` seconds**
3. **Re-check after wait** — if still banned, stop the job
4. **Add 1.2s delay between requests** — even with token, be respectful

## Step 5: Batch Processing Pattern

```python
import time
import threading

def batch_evaluate(stocks, per_stock_timeout=30):
    success = failed = skipped = banned_count = 0
    
    for idx, code in enumerate(stocks):
        # Check ban before each request
        retry_after = is_ip_banned()
        if retry_after > 0:
            banned_count += 1
            time.sleep(retry_after)
            if is_ip_banned() > 0:
                print(f"Ban still active. Stopping.")
                break
        
        # Throttle: 1.2s between requests
        time.sleep(1.2)
        
        # Evaluate with timeout
        result = evaluate_one(code)
        # ... process result
```

## Step 6: File Structure Convention

For a FinMind-based project, organize as:
```
taiwan-stock-finmind-api/
├── .env                          # FINMIND_API_KEY=xxx
├── financial_analyzers.py        # Core analyzers (Income, Balance, CF)
├── cashflow_analyzer.py          # Standalone cash flow analysis
├── screening/
│   ├── screener.py               # evaluate_one + cache
│   ├── screener_db.py            # DB schema + bootstrap
│   ├── batch_evaluate_financial.py  # Batch processor
│   └── api_cache.py              # TTL cache utility
├── app.py                        # Flask API wrapper
└── taiwan_stocks.db              # SQLite database
```

Each file that makes FinMind API calls MUST:
1. Load token from `.env`
2. Define a `_make_*_params()` helper
3. Use the helper in ALL `requests.get()` calls

## Pitfalls

1. **Token path resolution**: From `screening/screener.py`, the `.env` is at `../.env` (one level up), NOT `../../.env` (two levels). Double-check path resolution per file location.
2. **Import order matters**: Token loading happens at module level. If `.env` is missing, token will be `None` and requests will be unauthenticated.
3. **`verify=False`**: FinMind API sometimes behind reverse proxy with self-signed cert. Don't enable verification unless you have the CA bundle.
4. **Cache stale data**: Financial statements change quarterly. Use 24-hour TTL for cache keys.
5. **Thread safety**: If using threading for batch jobs, each thread should have its own requests session or use proper locking.
6. **403 response structure**: FinMind returns `{"success": null, "msg": "...", "retry_after": 1700}` — parse `retry_after` for wait time.
7. **Never mix token and no-token calls**: Some endpoints (TaiwanStockInfo) work without token. But financial statement endpoints MUST have token. Always use the helper function consistently.

## Verification

After implementing, verify with:
```python
# Quick smoke test
from financial_analyzers import IncomeAnalyzer
analyzer = IncomeAnalyzer()
data = analyzer.fetch_income_statement("2330")
assert len(data) > 0, "Failed to fetch 2330 income statement"
print(f"✅ Token auth working. Got {len(data)} records.")
```

## References
- FinMind documentation: https://finmind.github.io/
- Session-specific learnings: references/finmind_token_fix.md
- Batch evaluation pattern: references/batch_processing_pattern.md

---