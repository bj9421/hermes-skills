# Gateway Restart / Scheduler Stall — 2026-08-01 Incident

Real incident captured during the daily cron inventory (盤查). Four symptoms, one root cause chain: gateway restarts + a scheduler ticker that silently stalled for 12 hours.

## Timeline (2026-08-01, Asia/Taipei)

| Time | Event |
|------|-------|
| 08:06 | Gateway starts (container-boot.log `action=started`) — then **scheduler ticker goes quiet for 12h** |
| 08:04→20:23 | NO job runs at all (bookmark-watchdog every-5m output gap proves it) |
| 20:23:11 | **Catch-up burst**: scheduler fires all missed jobs at once (`Running job ... 20:23:11` × many in agent.log) |
| 20:23–20:24 | `twse_daily_update` starts full scan → killed with `Script exited with code -15` (SIGTERM) at 20:24 |
| 20:23:11 | `Auto Memory Scanner` fails `KeyError: 'HERMES_KANBAN_BOARD'` |
| 20:25 / 20:31 / 20:40 | Gateway restarts again (`--replace`; container-boot.log `action=started`) |
| 20:40+ | Stable — 5-min bookmark-watchdog, 10-min bookmark-enrich, 21:00 盤查 job all run normally |

## Evidence commands (reusable)

```bash
# 1. Restart proof
grep -n "Shutdown context: signal=SIGTERM" /opt/data/logs/errors.log | tail -5
tail -20 /opt/data/logs/gateway-exit-diag.log     # gateway.start entries with PID + timestamps
tail -20 /opt/data/logs/container-boot.log        # action=started lines
grep -n "Hermes Gateway Starting" /opt/data/logs/gateways/default/current | tail

# 2. Scheduler heartbeat — output files of a high-frequency no_agent job
ls -l /opt/data/cron/output/cc30b2d53079/*.md | tail -60     # bookmark-watchdog (every 5m)
# 2026-08-01 gap: files jump 08:04 → 20:23

# 3. Per-hour scheduler activity from agent.log
grep "Running job" /opt/data/logs/agent.log | awk '{print $2}' | cut -d: -f1 | sort | uniq -c
# hour 08 shows only 1 run (the 08:06 startup burst), hours 09–19 zero or near-zero = stall

# 4. Kill proof for the -15 job
cat /opt/data/cron/output/d8379e951943/<latest>.md   # "Script exited with code -15"
```

## What was verified healthy (before clearing error state)

- `update_daily.py --batch 5` → exit 0, "寫入: 0 筆" (Saturday = non-trading day, DB already at 2026-07-31, no 08-01 residue)
- DB intact: `MAX(date)=2026-07-31`, 1,563,035 rows, no partial writes
- `auto_memory_scan.py 3` → exit 0, scanned 7 sessions, 8 facts
- `cron_watchdog.py` after clearing errors → exit 0 + empty stdout (quiet)

## Fix applied

```bash
cp /opt/data/cron/jobs.json /opt/data/cron/jobs.json.bak.pre-inventory-20260801
# set last_status=null, last_error=null for twse_daily_update + Auto Memory Scanner
python3 -c "import json; json.load(open('/opt/data/cron/jobs.json')); print('JSON OK')"
python3 /opt/data/scripts/cron_watchdog.py; echo $?   # 0 = quiet again
```

Why: the no_agent watchdog (`cron-watchdog-fast`, every 10m) exits 1 every cycle while `last_status:error` sits in jobs.json — it was re-alerting the same stale error at 20:33/20:43/20:54/21:05 until the state was cleared.

## Follow-ups / open items

- **Scheduler-stall root cause NOT fully confirmed** (suspected hung ticker thread during the 08:06 start; no smoking gun in logs). Watch for a recurrence: heartbeat-gap check is now the standard probe.
- `ohlc-verification` had failed the previous weekday with `TimeoutError: idle for 602s (limit 600s) — waiting for non-streaming API response` — LLM idle watchdog at 600s. Re-check next Mon-Fri run.
- `twse_daily_update` scheduled `0 16 * * *` runs on weekends: non-trading days still trigger a full 1925-stock scan ("無股票有 <today> 資料，將全量更新") with 0 writes. Consider `0 16 * * 1-5` (pending user confirmation).
- `taiwan-tech-strategy-daily` 17:00 run was missed; a 20:23 catch-up attempt was itself interrupted by the 20:25 restart. No data loss — scripts re-ran fine next tick.

## Lesson distilled

When a cron inventory shows several unrelated-looking failures at once, grep restart logs first — one `--replace` chain can explain SIGTERM kills, env-race KeyErrors, catch-up bursts, and (by leaving the scheduler wedged) hours of missed jobs. The 5-minute no_agent watchdog output dir doubles as the cheapest scheduler-liveness heartbeat available.
