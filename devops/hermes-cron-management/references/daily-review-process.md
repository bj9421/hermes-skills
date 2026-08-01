# Daily Review（每日工作檢討）— Process & Data Sources

The 22:00 `daily-review` cron job produces a 5W1H report at `/opt/data/obsidian-vault/Holographic/每日檢討/YYYY-MM-DD-工作檢討.md`. Verified working process (2026-08-01 run).

## Data sources (in order)

1. **`/opt/data/cron/jobs.json`** — read with `read_file` (NOT `cat | python3`: triggers the tirith `pipe_to_interpreter` security scan and gets blocked — the original daily-review prompt literally contains this blocked form). ⚠️ `last_status` is UNRELIABLE: it can be `null` even when a run failed (2026-08-01: twse_daily_update failed `-15` with last_status null). Use jobs.json for the job list/schedule, NOT for failure truth.
2. **`/opt/data/cron/executions.db`** — THE authoritative per-run history. Schema + query + status meanings in SKILL.md (`executions` table). Catches what jobs.json hides: `failed` (with error column carrying captured stdout), `unknown` (restart-interrupted, "whether side effects ran is unknown"), `running`. For daily reviews, group by status and read the error column; identical started_at timestamps across many jobs = catch-up burst after a scheduler stall.
3. **git log** — projects at `/opt/data/projects/<name>` (bookmark-manager etc.), skills at `/opt/data/skills` (auto-backup commits). Use precise timestamps for the report:
   ```bash
   git -C /opt/data/projects/bookmark-manager log --since="2026-08-01 00:00" --format='%h %ad %s' --date=format:'%m-%d %H:%M'
   ```
   Note: `git -C /opt/data/projects` fails (not a git repo at that level) — go one level deeper per project. Docker dubious-ownership errors are common; `git -C <dir> -c safe.directory=<dir>` or repo-local config works around it.
4. **session_search** — find user corrections. PITFALL: overnight Telegram sessions START on a previous date and continue past midnight (2026-08-01 example: session `20260730_154052_9a6f3050` ran 07-30 15:40 → 08-01 05:00+, carrying most of the day's code work + user corrections). Querying "today's sessions" by `date(started_at)` MISSES these. Instead query state.db by session_id + timestamp window with epoch bounds computed from the local date:
   ```sql
   SELECT m.timestamp, m.role, m.content FROM messages m
   WHERE m.session_id='<id>' AND m.timestamp BETWEEN <epoch_start> AND <epoch_end>
   ORDER BY m.timestamp
   ```
   Epoch bounds: `int(datetime(y,m,d,tz=+8).timestamp())`. Compaction summaries inside long sessions are gold for finding corrections the live window missed.

## Report format

- 5W1H per problem; **系統錯誤 (cron failures, API limits) + 代碼錯誤 (my mistakes corrected by user) are BOTH mandatory** — user corrected this on 2026-07-31 (first version recorded only system errors).
- 代碼錯誤 entries must carry the user's actual words in the How field (from session history), the fix commit(s), and a lesson.
- End with 修復記錄 table, 待辦事項, 經驗教訓, 明日重點.
- `chmod 777` the output file (Obsidian sync reads it from another UID context).

## Key 2026-08-01 findings (worked example of the chain)

- One root cause (scheduler stall 08:06→20:23 + gateway restarts at 20:25/20:31/20:40) produced 6 system-error symptoms: `-15` kill, `KeyError: HERMES_KANBAN_BOARD`, `unknown`-state interruptions, missed jobs, watchdog re-alerts. → Grep restart logs FIRST when a review shows several unrelated-looking failures.
- Watchdog repeated alerts (4×: 20:33/20:43/20:54/21:05) = stale `last_status:error` not cleared after diagnosis. Clear state promptly or users get spam.
- Executions.db records `bookmark-bot-watchdog failed: Script execution failed: 'HERMES_KANBAN_BOARD'` even though jobs.json showed last_status ok — the DB is the only complete view.
