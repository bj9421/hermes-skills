# Cron Jobs Structure Reference

## Jobs File Location

Cron jobs are stored per-profile at:
```
/opt/data/profiles/<profile>/cron/jobs.json
```

## File Structure

The `jobs.json` is a **dict** with a `jobs` key containing a list of job objects:

```json
{
  "jobs": [
    {
      "id": "e5f9e642f5c4",
      "name": "Job Display Name",
      "prompt": "Detailed instructions for the agent...",
      "schedule": {
        "kind": "cron",
        "expr": "0 22 * * *"
      },
      "enabled": true,
      "state": "running",
      ...
    }
  ]
}
```

**Key fields:**
| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique job identifier |
| `name` | string | Display name |
| `prompt` | string | Instructions sent to agent on each run |
| `schedule.kind` | string | `"cron"` or `"interval"` |
| `schedule.expr` | string | 5-field cron expression (cron kind) or `"every Xm"` (interval kind) |
| `enabled` | bool | Whether job is active |
| `state` | string | `"scheduled"`, `"paused"`, `"completed"` |
| `deliver` | string | `"origin"` (default), `"all"`, `"local"`, or `platform:chat_id:thread_id` |
| `model` / `provider` | string | Per-job model override (nullable) |
| `no_agent` | bool | If true, runs script only without LLM |
| `enabled_toolsets` | list | Toolset restriction (nullable = all) |

**Parsing tip:** The top-level is a dict, NOT a list. Always access via `data.get("jobs", [])`.

## Profile-Specific Notes (2026-07-10)

- **default profile:** `cron/` directory exists but is empty — no jobs configured.
- **research profile:** Contains all data pipeline and sync cron jobs (9 total).

## Migration: Research → Default

When moving cron jobs between profiles:
1. All script paths use absolute paths (`/opt/data/...`) — no changes needed
2. `deliver: "origin"` works across profiles (same Telegram chat ID)
3. Jobs with `model: "big-pickle"` require the target profile to have the `opencode` provider configured
4. Profile-exclusive jobs (e.g., `holographic-to-obsidian-sync`) should NOT be moved
5. Paused jobs remain paused after migration unless user requests otherwise

## Common Jobs in Research Profile (as of 2026-07-10)

| Name | Schedule | Enabled | Purpose |
|------|----------|---------|---------|
| 補完股票缺漏資料 | `0 18 * * 1-5` | ✓ | Fill missing TWSE stock data |
| taiwan-tech-strategy-daily | `0 16 * * *` | ✓ | Daily tech indicator update + strategy |
| finmind-batch-financial-update | `0 15 * * *` | ✓ | Financial data batch fetch via FinMind |
| holographic-to-obsidian-sync | `0 2 * * *` | ✓ | Export holographic memory → Obsidian (research-only) |
| ohlc-verification | `0 16 * * 1-5` | ✓ | OHLC cross-verification (weekday) |
| ohlc-verification-full | `0 2 * * 6` | ✓ | Weekly full OHLC verification |
| IG台灣景點熱門排行 | `0 22 * * *` | ✗ | Instagram hot spots (paused since 6/9) |
| twstock-catchup | `0 15 * * 1-5` | ✗ | Stock catch-up (paused since 7/3) |
| taiwan-stock-api-watchdog | `every 5m` | ✗ | Port 5000 health check (paused since 7/3) |
