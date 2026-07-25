# Hermes Cron Scheduling Best Practices

## Time Clustering

Group related jobs to minimize notification spam:

| Cluster | Window | Jobs |
|---------|--------|------|
| Nightly sync | 02:00 | Obsidian sync, full OHLC check |
| Post-market | 15:00-16:30 | Stock data, indicators, strategy report |
| Catch-up | 18:00 | Missing data补漏 |

**Rule of thumb**: Keep related jobs within a 30-minute window so they arrive as one coherent batch.

## Avoiding Conflicts

### Shared DB Access
When multiple jobs read/write the same SQLite DB:
- Stagger start times by 1-2 minutes
- Use `no_agent: true` for pure data jobs (faster, no LLM overhead)
- Consider adding `LOCK_TIMEOUT` or file-based locks in scripts

### Shared Output Directory
When multiple jobs write to the same directory:
- Only ONE job should write to a given directory at a time
- If two profiles both trigger the same sync, pause one

### Notification Fatigue
- Maximum 3-4 notifications per day is sustainable
- Combine independent data updates into a single report script
- Use `deliver: "local"` for diagnostic jobs (no Telegram spam)

## Scheduling Conventions

| Convention | Format | Example |
|------------|--------|---------|
| Cron expression | Standard 5-field | `0 16 * * *` |
| Interval | Human-readable | `every 180m` |
| Weekly | Day-specific | `0 2 * * 6` (Saturday) |
| Weekday | Mon-Fri | `0 18 * * 1-5` |

## Script Naming

| Pattern | Purpose |
|---------|---------|
| `run_*.sh` | Wrapper scripts (entry points for cron) |
| `*_update.py` | Data update scripts |
| `*_verify.py` | Validation/check scripts |
| `*_push.py` | Report/notification scripts |
