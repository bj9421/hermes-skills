# Rebuilding Cron Jobs from Scratch

When cron jobs are deleted and need to be recreated (e.g., after profile migration or cleanup).

## Prerequisites

1. **Locate all referenced scripts** — verify they exist at their declared paths
2. **Check dependencies** — Python modules, venv paths, environment variables
3. **Confirm deliver target** — `deliver: "origin"` sends to the profile's connected chat

## Reconstruction Procedure

### 1. Audit existing scripts
```bash
find /opt/data -name "*.py" -path "*/screening/*" | head -20
find /opt/data/scripts -name "*.sh" | head -20
```

### 2. Inspect each script
- Check imports for missing modules (`ModuleNotFoundError`)
- Verify DB paths and env vars
- Confirm workdir requirements

### 3. Write jobs.json
Create `/opt/data/profiles/default/cron/jobs.json` with job definitions.

**Template for agent-mode jobs:**
```json
{
  "name": "job-name",
  "schedule": "0 16 * * *",
  "repeat": "forever",
  "prompt": "Run the task.\nExecute: cd /opt/data && .venv/bin/python3 path/to/script.py\nReport results: ...",
  "no_agent": false,
  "workdir": "/opt/data",
  "deliver": "origin",
  "enabled_toolsets": ["terminal"]
}
```

**Template for no_agent jobs:**
```json
{
  "name": "job-name",
  "schedule": "0 16 * * *",
  "repeat": "forever",
  "script": "script_name.sh",
  "no_agent": true,
  "workdir": "/opt/data/profiles/default",
  "deliver": "origin"
}
```

### 4. Manual test each script
```bash
cd /opt/data && .venv/bin/python3 path/to/script.py
```

### 5. Verify cron picks up the jobs
```bash
/opt/hermes/bin/hermes cron list
```

## Common Pitfalls

- **Missing Python modules** — e.g., `yfinance`, `twstock`. Check each script's imports.
- **Wrong workdir** — scripts using relative paths will fail. Always use absolute paths in prompts.
- **Duplicate jobs** — after rebuilding, check that old jobs weren't left in another profile.
- **Schedule collisions** — multiple jobs at the same time may compete for the same DB.

## Example: Rebuilding Taiwan Stock Cron Suite

| Job | Schedule | Script | Notes |
|-----|----------|--------|-------|
| taiwan-tech-strategy-daily | 0 16 * * * | update_all_tech_indicators.py + auto_screen_and_notify.py | Two-step pipeline |
| finmind-batch-financial-update | 0 15 * * * | batch_evaluate_financial.py | Needs yfinance |
| ohlc-verification | 5 16 * * 1-5 | verify_daily_prices.py | Sample mode (fast) |
| ohlc-verification-full | 0 2 * * 6 | verify_daily_prices.py --full | Full mode (slow) |
| 補完股票缺漏資料 | 0 18 * * 1-5 | fix_incomplete_v3.py | Data completeness |
