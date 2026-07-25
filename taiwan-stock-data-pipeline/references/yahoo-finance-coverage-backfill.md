# Yahoo Coverage & FinMind Backfill (measured 2026-07-11)

## Measured coverage (full run)

`yf_fetcher.py` was repaired 2026-07-11 (transpose + reversed field MAP + `len(df)>0`
+ cashflow_analyzer Yahoo path). A full background run over the **1880-stock active
universe** (`get_active_universe()` — filters out finance/insurance/securities/ETF)
gave:

| Table | Success |
|-------|---------|
| Income | 1012/1880 (53.8%) |
| Balance | 1011/1880 (53.8%) |
| Cashflow | 1011/1880 (53.8%) |
| **ALL 3** | **1011/1880 (53.8%)** |

➡️ **869 stocks (46.2%) have NO Yahoo data for ≥1 table → must fall back to FinMind.**

Earlier "5/5 big caps worked" was survivor bias (2330/2317/2454 all happen to be covered).

## FinMind fallback verification

Stocks missing from Yahoo were sampled (30 stocks) with the *correct* analyzer call
(`finmind_client.fetch("TaiwanStockFinancialStatements", stock_code, start)` etc.):
**30/30 returned all three tables True.** So FinMind CAN fill the gap — the old
"0/20 empty" conclusion was a test-script bug (wrong param shape), not a real failure.

## The quota math problem

869 missing × 3 tables = **2607 FinMind calls ≫ 600/day Free quota**.

Mitigations already built into `screening/finmind_client.py`:
- **Disk cache** (sqlite, 7-day TTL): first fill persists; daily cron only hits Yahoo
  (free) afterwards, FinMind only on cache expiry.
- **Daily quota guard**: stops gracefully when ≤20 requests remain (avoids 402 → ban).
- **Circuit breaker**: on 403 ip-banned, one 30-min wait, then single retry — never
  per-stock `sleep(300)`.

## Recommended backfill plan

| Option | How | Risk |
|--------|-----|------|
| **A. Batched** | ~100 stocks/day (≈300 calls < 600), ~9 days to fill 869 | Safest, zero ban risk |
| B. One-shot hard run | Quota guard auto-stops at ~580, remainder next day | Auto, multi-day |
| C. Yahoo-only | Accept 53.8% coverage, abandon the other 46.2% | Zero FinMind use, smaller screen universe |

**Prefer A**: a daily cron that processes the next N stocks not yet cached in
`finmind_cache.db`, stopping at the quota guard. After the cache is warm, normal
runs are Yahoo-only.

## Measuring coverage yourself

```bash
cd /opt/data/projects/taiwan-stock-cashflow-api
.venv/bin/python3 /opt/data/skills/taiwan-stock-data-pipeline/scripts/measure_yahoo_coverage.py
```

The script blocks `requests.get` (FinMind) so it measures Yahoo-only success, prints
per-checkpoint progress, and pickles `/tmp/yahoo_cov_progress.pkl` (keys: `inc/bal/cf`
bools). Parse with:

```python
import pickle
d = pickle.load(open("/tmp/yahoo_cov_progress.pkl","rb"))
all3 = sum(1 for v in d.values() if v["inc"] and v["bal"] and v["cf"])
print(f"{all3}/{len(d)} = {all3/len(d)*100:.1f}%")
```
