# Cron Script Audit — 2026-07-13 Session

Real-world findings from auditing 14 cron jobs on this Hermes instance.

## Path Mismatches Found

### 1. OHLC verification (2 jobs)

- **Jobs:** `ohlc-verification` (daily) + `ohlc-verification-full` (weekly)
- **Prompt referenced:** `screening/verification_compare.py`
- **Actual file:** `screening/verify_daily_prices.py`
- **Fix:** Updated both prompts to use correct path + `.venv/bin/python3`

### 2. twstock-catchup

- **Job:** `twstock-catchup`
- **Prompt referenced:** `python3 /opt/data/update_daily.py`
- **Actual file:** `/opt/data/scripts/stock-update/update_daily.py`
- **Fix:** Updated prompt to use correct path + `.venv/bin/python3`

## Venv Discovery

| Script | Works with | Fails with | Reason |
|--------|-----------|-----------|--------|
| `fix_incomplete_v3.py` | `/opt/data/.venv/bin/python3` | `python3` (system) | Needs `twstock` |
| `verify_daily_prices.py` | `/opt/data/.venv/bin/python3` | project `.venv` | Needs `twstock` in main venv |
| `daily_collect.py` (IG) | `/opt/data/ig-locations/.venv/bin/python3` | system python | Needs `apify_client` |
| `auto_memory_scan.py` | `python3` (system) | — | stdlib only |

## no_agent Conversion Candidates Identified

The following LLM-driven jobs were pure script wrappers and could be converted to `no_agent=true`:

| Job | Current | Candidate | Notes |
|-----|---------|-----------|-------|
| `holographic-to-obsidian-sync` | LLM+script hybrid | `no_agent=true` | Script is self-contained |
| `twstock-catchup` | LLM "run script" | `no_agent=true` | Plain script call |
| `補完股票缺漏資料` | LLM "run fix_incomplete_v3.py" | `no_agent=true` | Plain script call |
| `IG 台灣景點每日熱門排行` | LLM "run daily_collect.py" | `no_agent=true` | Need wrapper script first |
| `ohlc-verification` | LLM "run verification" | `no_agent=true` | Script is self-contained |
| `ohlc-verification-full` | LLM "run verification" | `no_agent=true` | Script is self-contained |

**Keep LLM-driven (needs reasoning):** `Auto Memory Scanner`, `taiwan-tech-strategy-daily`, `finmind-batch-financial-update`

## Sync Holographic Script Fix

`sync_holographic_to_obsidian.sh` referenced `/opt/data/.hermes/.venv/bin/python3` which doesn't exist. Fixed with a fallback search loop:

```bash
for py in "/opt/hermes/.venv/bin/python3" "/opt/data/.venv/bin/python3" "python3"; do
    if command -v "$py" >/dev/null 2>&1; then
        PYTHON_BIN="$py"
        break
    fi
done
```

This now correctly finds `/opt/hermes/.venv/bin/python3` at runtime.
