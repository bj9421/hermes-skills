---
name: hermes-cron-management
description: "Manage Hermes Agent cron jobs: audit, migrate between profiles, rebuild, diagnose failures, and coordinate multi-profile scheduling."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [cron, scheduling, multi-profile, migration, audit]
    related_skills:
      - ha-powers
      - hermes-agent
      - hermes-env-troubleshooting
---

# 📅 Hermes Cron Job Management

Manage scheduled cron jobs for Hermes Agent: audit existing jobs, migrate between profiles, rebuild after cleanup, and diagnose failures.

## Quick Reference

### List all jobs (across all profiles)
```bash
/opt/hermes/bin/hermes cron list
```

### Check a specific job
```bash
# Get job details by ID
/opt/hermes/bin/hermes cron inspect <job_id>
```

### Create a new job
```bash
# cronjob(action='create') WORKS in current env (verified this session, 3× uses).
# Prefer it for single jobs. For bulk migration, write the live store directly (below).
cronjob action=create name=<name> schedule="0 16 * * *" prompt="..." \
  model='{"model":"hy3-free","provider":"opencode-zen"}' deliver=origin
```

### Pause / Resume / Remove
```bash
hermes cron pause <job_id>
hermes cron resume <job_id>
hermes cron remove <job_id>
```

## ⚠️ Bulk migration: write the LIVE store directly

For moving many jobs at once, write the live store JSON directly (faster than N `create` calls). **But the path MUST be the live store — see the PROFILE-SCOPED / live-store warning below.** The active gateway reads `/opt/data/cron/jobs.json` (HERMES_HOME root), NOT `profiles/<name>/cron/jobs.json`.

```python
import json, copy
LIVE = '/opt/data/cron/jobs.json'          # ← LIVE store (gateway reads this)
raw = json.load(open(LIVE))
jobs = raw['jobs'] if isinstance(raw, dict) else raw
# append migrated job dicts (full schema), then:
json.dump(raw, open(LIVE, 'w'), ensure_ascii=False, indent=2)
```
⚠️ Confirm the path with `find /opt/data -path "*/cron/jobs.json"` before writing. Writing to the wrong path (e.g. `profiles/default/cron/jobs.json`) leaves the live store untouched and the job invisible to `cronjob list` — this is exactly how a prior "migration" silently failed.

## ⚠️ CRITICAL: Model / Provider Drift Protection (auto-blocks jobs)

When the **global** inference config (model or provider) changes after a job was created, Hermes **silently skips** any job that is *unpinned* on the next run, instead of spending on the new (possibly paid) model. Symptom in `last_error`:

```
Skipped to prevent unintended spend: global inference config drifted
since this job was created (provider 'custom' -> 'opencode-zen';
model 'agnes-2.0-flash' -> 'hy3-free'), and this job is unpinned.
No inference call was made. To run on the new config, pin it explicitly:
cronjob action=update job_id=<id> provider=<provider> model=<model>
```

This is a **safety gate, not a bug** — do NOT "fix" by blindly forcing runs. The job simply won't execute until re-pinned.

**Fix (one command):** re-pin the job to the current global config (or any valid model):
```bash
cronjob action=update job_id=<id> model='{"model":"hy3-free","provider":"opencode-zen"}'
```
Then verify with `cronjob action=run job_id=<id>` → expect `execution_success: true`.

**⚠️ Alternative when CLI needs TTY approval (cron / no-user context):**
`cronjob action=update` requires TTY approval (security hooks), which is unavailable in automated cron runs or CI. In those contexts, patch the live JSON store directly:

1. **Locate the live store:** `find /opt/data -path "*/cron/jobs.json"` — the active gateway reads `/opt/data/cron/jobs.json` (HERMES_HOME root), NOT `profiles/&lt;name&gt;/cron/jobs.json`.
2. **Pin model/provider:** Edit the job's `"model"` and `"provider"` fields (e.g. `"model": "big-pickle"`, `"provider": "opencode"`).
3. **Clear error state:** Also set `"last_status": null` and `"last_error": null` — otherwise the scheduler still sees the error condition and won't re-attempt.
4. **Verify JSON:** `python3 -c "import json; json.load(open('/opt/data/cron/jobs.json')); print('OK')"`
5. **Next scheduled run picks up the fix automatically.** No need to force-run.

Troubleshooting: if the job still errors after the fix, grep the active gateway log for the job id:
```bash
grep -n -i -e "drift" -e "&lt;job_id&gt;" /opt/data/logs/gateways/default/current | tail -25
```

**Best practice:** Pin every LLM-driven job explicitly at creation (`cronjob action=create model=...` or write `model`/`provider` into `jobs.json`). Unpinned jobs break on every global-model switch.

**Detect drift across all jobs:** any job whose `last_status: "error"` and `last_error` contains `drifted` needs re-pinning. (See audit checklist below.)

## ⚠️ CRITICAL: Custom Provider Naming — `custom:<name>`, NOT bare `custom`

When a job targets an entry under `custom_providers` in `config.yaml`, the `provider` field MUST be the qualified form **`custom:<name>`** (e.g. `custom:agnes`), where `<name>` is the `name:` key in the YAML block. Using **bare `custom`** is a silent failure:

- Hermes does NOT error at creation. It **auto-re-maps** bare `custom` to the current global provider (e.g. `opencode-zen`).
- At run time it then calls the global provider with the custom model name → `HTTP 401: Model <name> is not supported`.

Correct (verified working) form when creating/updating:
```bash
cronjob action=update job_id=<id> model='{"model":"agnes-2.0-flash","provider":"custom:agnes"}'
# creation:
cronjob action=create model='{"model":"agnes-2.0-flash","provider":"custom:agnes"}' ...
```

After creating, **verify the stored provider did not get re-mapped** by listing the job — if `provider` shows `opencode-zen` (or anything other than `custom:agnes`), the name was rejected and the job will fail at run.

**Liveness probe (bypasses cron entirely):** to confirm a custom provider's API is actually up before wiring it into a job, curl its `base_url` directly (read the key + URL from `config.yaml`):
```bash
cd /opt/data
API_KEY=$(grep -A2 "name: agnes" profiles/default/config.yaml | grep api_key | awk '{print $2}')
BASE_URL=$(grep -A2 "name: agnes" profiles/default/config.yaml | grep base_url | awk '{print $2}')
curl -s -o /tmp/resp.txt -w "HTTP_CODE=%{http_code} TIME=%{time_total}s\n" \
  "$BASE_URL" -H "Authorization: Bearer $API_KEY" -H "Content-Type: application/json" \
  -d '{"model":"agnes-2.0-flash","messages":[{"role":"user","content":"say OK"}]}' --max-time 45
cat /tmp/resp.txt | head -c 600
```
⚠️ **Pitfall:** put the key in the `Authorization: Bearer` header, NOT as the curl URL positional arg — passing the key as the URL yields `HTTP 401 ... 未提供令牌` (token missing) even though the key is valid.

**Pitfall — don't assume custom_providers diverge between profiles.** Both `profiles/default/config.yaml` and `profiles/research/config.yaml` carried an *identical* `custom_providers: agnes` block in this environment. Grepping both files before concluding "settings weren't migrated" avoids a wasted copy. (If they DO differ, copy the whole `custom_providers:` YAML block between the two `config.yaml` files.)

## ⚠️ CRITICAL: Diagnosing a Pinned-Model Cron Failure

`cronjob action=run` on a mis-pinned job returns a **cleared/empty job object** with `execution_success: false` and writes **nothing to `profiles/<p>/logs/agent.log`** — the failure happens at the **scheduler/gateway layer**, before the agent initializes. To get the REAL error:

1. Find the active gateway log. The live gateway is the one with `cwd=/opt/data` and **no** `-p` flag (typically PID 146, profile `default`); a second `-p research` gateway may exist in `retrying` state (telegram token lock) and is inert. Cron is served by the active gateway.
2. Grep its current log for the job id / model / provider:
   ```bash
   grep -n -i -e "agnes" -e "<job_id>" -e "drift" -e "not supported" \
     /opt/data/logs/gateways/default/current | tail -25
   ```
3. Real error in this session (bare `custom` re-mapped to global):
   ```
   🔌 Provider: opencode-zen  Model: agnes-2.0-flash
   📝 Error: HTTP 401: Model agnes-2.0-flash is not supported
   📋 Details: {'type': 'ModelError', 'message': 'Model agnes-2.0-flash is not supported'}
   ```
   This points straight at the `custom:<name>` naming fix above.

**Two-gateway reality:** `profiles/research/gateway_state.json` may show `telegram-bot-token_lock` / `already in use (PID 146)`. That means the research gateway is a zombie; PID 146 (default) owns the token and runs cron. Don't trust a `retrying` gateway's logs for cron diagnosis — use the `default` gateway log.

**Telegram token conflict between profiles sharing config**: If two profiles share the same `config.yaml` (research has no separate config, inherits from root), they will share the same Telegram bot token. The first gateway to start wins; the second gets "Token already in use". **Fix**: Kill the competing gateway (`kill <pid>`) and restart only the one you want active. If a profile doesn't need Telegram, don't run its gateway — or give it a separate config with no Telegram token.

**Prevention tip**: Only run gateways for profiles that actively need messaging platforms. The `default` profile gateway handles Telegram + cron; the `research` profile can run without a gateway if it doesn't need Telegram. Use `ps aux | grep "hermes.*gateway" | grep -v grep` to check for conflicts.

## ⚠️ CRITICAL: `cronjob list` is PROFILE-SCOPED

`cronjob action=list` ONLY returns jobs for the **currently active profile**. Jobs in other profiles are invisible to it — they will not show up and you will wrongly conclude they don't exist (e.g., strategy crons in the `research` profile were invisible from `default`).

**To audit ALL cron jobs across every profile, read the on-disk stores directly:**
```bash
# Default profile (profile=None) lives at HERMES_HOME root — THIS IS THE LIVE STORE:
/opt/data/cron/jobs.json
# Named profiles live under:
/opt/data/profiles/<name>/cron/jobs.json
# Enumerate every store at once:
find /opt/data -path "*/cron/jobs.json"
```
⚠️ **LIVE store vs legacy path (caused a real botched migration):** The active gateway (PID 146, `cwd=/opt/data`, no `-p` flag) reads **`/opt/data/cron/jobs.json`**. A second copy at `/opt/data/profiles/default/cron/jobs.json` also exists but is a **legacy/secondary store** — writing there does NOT update what `cronjob list` shows. Always verify which path the gateway serves via `find` before editing. If you write to the legacy path, the job stays invisible until also written to the root path.

**⚠️ PITFALL — removing a job by ID also wipes every job sharing that `name`:** `cronjob action=remove job_id=<id>` matches on `name`, not just the id. In this session, removing a paused duplicate `holographic-to-obsidian-sync` (id `5cbdacd487ad`) also deleted the live migration copy (`55577d395747`) of the same name. If two jobs share a name, remove the unwanted one by editing the live store JSON directly (delete only that dict), or rename one first. After any remove, immediately `cronjob list` to confirm siblings survived, and rebuild a lost sibling via `cronjob create` from a backup of `jobs.json`.

## ⚠️ 備援模型守則 (User-explicit failover rule, 2026-07-11)

**規則（用戶明確要求）：** 當任何 **cron job 或對話** 的主要模型失效（drift / 401 / timeout / 報錯）時，
**立刻切換到以下兩個免費模型做備援** —— 不要卡住，也不要花錢用付費模型：

| 順位 | 模型 | provider 寫法 | 備註 |
|:----:|:-----|:-------------|:------|
| 1 | opencode **big-pickle** | `{"model":"big-pickle","provider":"opencode"}` | 優先試，免費且穩定 |
| 2 | agnes **agnes-2.0-flash** | `{"model":"agnes-2.0-flash","provider":"custom:agnes"}` | 注意 `custom:agnes` 帶後綴（見命名章節），裸 `custom` 會被重對映成 401 |

**觸發場景：**
- cron `last_error` 含 `drifted` / `ModelError` / `HTTP 401` → 先 `cronjob update` 把該 job 的 `model/provider` 重 pin 到上表其一，再 `cronjob run` 驗證。
- 對話中模型報錯 → 直接切換當下對話模型到 big-pickle，再不行換 agnes。
- 模型名要帶進報告（見 taiwan-stock-data-pipeline 技能的「報告必須註記產生模型」章節），
  讓備援切換在產出上可見。

**注意：** 這兩個備援模型在 default 與 research 的 `config.yaml` 都已有定義（agnes 在兩 profile 第 679 行逐字相同；big-pickle 在 default 第 2 行），無需複製設定。agnes API 仍活著（curl 直打 HTTP 200，見下方命名章節 liveness probe）。

## References

- `references/cron-live-store-and-migration.md` — Verified live-store path (`/opt/data/cron/jobs.json`), the botched-migration failure pattern, and a working research→default migration recipe.
- `references/cron-drift-and-jobs-json-locations.md` — Drift-protection deep dive + full jobs.json enumeration recipe and a model-liveness probe.
- `references/cron-custom-provider-and-diagnosis.md` — Custom-provider naming (`custom:<name>`), curl liveness probe, and gateway-log diagnosis of pinned-model cron failures.
- `references/cron-session-search-debugging.md` — Inspect cron job execution history via `session_search(session_id="cron_{job_id}_{ts}")` when CLI can't show the full prompt. Includes SQL to find cron session IDs and real diagnostic example.

## Core Concepts

### Cron Job Anatomy
| Field | Description |
|-------|-------------|
| `job_id` | Unique hash identifier (e.g., `d8379e951943`) |
| `name` | Human-readable name |
| `schedule` | Cron expression (e.g., `0 2 * * *` = daily 02:00) |
| `script` | Path to executable script (relative to workdir) |
| `workdir` | Working directory for the job |
| `no_agent` | `true` = runs script directly, no LLM involvement |
| `deliver` | Where to send output: `origin` (current chat), `local` (save only) |
| `enabled` | Whether the job is active |
| `last_run_at` | When it last executed |
| `last_status` | `ok` / `error` |

### Profile Isolation
- Each profile has its own cron engine
- Jobs defined in one profile only run in that profile
- `deliver: "origin"` sends to the profile's connected chat
- **Cross-profile sharing**: scripts use absolute paths, so a job in any profile can run any script at `/opt/data/scripts/...`

## Migration Procedure (Profile A → Profile B)

When moving cron jobs between profiles:

1. **Identify the job** — list all jobs, find the one to move
2. **Copy required scripts** — copy scripts referenced by the job to the target profile's `scripts/` dir
3. **Update workdir** — change `workdir` to the target profile's directory
4. **Test manually** — run the script from the new workdir before relying on cron
5. **Pause/remove source** — pause or remove the original job to avoid duplicate execution

### Pitfall: Duplicate Execution
If two profiles trigger the same job at the same time and write to the same output, the second run silently overwrites the first. **Always pause the source job after migrating.**

### Pitfall: Shared DB Writes
Multiple profiles reading/writing the same SQLite DB simultaneously can cause lock contention. Schedule overlapping jobs at different times or add file locks.

## Audit Checklist

When auditing cron jobs:

1. List all jobs: `hermes cron list`
2. Group by schedule time — look for clustering
3. Check `last_status` for errors
4. Identify redundant jobs (same script, same purpose)
5. Verify scripts exist at their declared paths
6. Confirm `workdir` is correct for each job
7. Check if any jobs are paused but should be active (or vice versa)
8. Check `last_error` for `drifted` → model/provider drift block (see CRITICAL section above). These need re-pin, not deletion.
9. **Read every profile's `cron/jobs.json` directly** (see PROFILE-SCOPED warning) — `cron list` hides other profiles.

## Script Path & Dependency Audit

LLM-driven cron jobs (no `script` + `no_agent`) reference scripts via their `prompt`. These are **brittle**: a renamed file, wrong venv, or stale path causes silent failure. Always test the actual shell commands the LLM would run:

### 1. Resolve the prompt's path to the real script

Cross-reference the cron job's prompt against the filesystem:

```bash
# For a job referencing "cd /path && python3 script.py" — confirm both
ls -la /path/script.py
ls -la /path/
```

**Common pattern:** prompts reference `/opt/data/update_daily.py` but the real file is `/opt/data/scripts/stock-update/update_daily.py`. Or reference `screening/verification_compare.py` but the real file is `screening/verify_daily_prices.py`.

### 2. Find the correct Python venv

Not all scripts work with `python3` (system Python). Test imports:

```bash
# System python (no extra packages)
python3 -c "import twstock" 2>&1  # may fail

# Main .venv (stock pipeline packages)
/opt/data/.venv/bin/python3 -c "import twstock" 2>&1  # ✅ if installed

# Project-specific venv
/opt/data/projects/taiwan-stock-cashflow-api/.venv/bin/python3 \
  -c "import twstock" 2>&1  # may also lack twstock
```

**Rule of thumb:** If the script imports `twstock` / `yfinance` / `pandas` / `finmind`, use `/opt/data/.venv/bin/python3`. If it imports `apify_client`, use the project's `.venv`.

### 3. Test the exact command sequence

Run the exact commands from the prompt with a short timeout:

```bash
timeout 15 /opt/data/.venv/bin/python3 /path/to/script.py --dry-run 2>&1
timeout 15 bash /path/to/script.sh 2>&1
```

Look for:
- `ModuleNotFoundError` → wrong venv
- `FileNotFoundError` or `ls: cannot access` → wrong path
- `No such file or directory` → missing script
- `command not found` → missing tool in PATH

### 4. For LLM jobs that need refactoring to no_agent

If the prompt is essentially "run this script", consider converting:

**Convert LLM-driven → no_agent:**
```bash
cronjob action=update job_id=<id> script="relative/or/absolute/path.sh" no_agent=true
```

**Convert no_agent → LLM-driven (needs reasoning):**
No change needed — leave as-is if the job does analysis/reporting.

### Categorization matrix

| Job pattern | Best mode | Reason |
|-------------|-----------|--------|
| `script.sh` → collects data, produces self-contained output | `no_agent=true` | No LLM reasoning needed |
| `script.py` → same as above | `no_agent=true` | Pure data pipeline |
| `prompt: "run script then summarize"` | LLM-driven or `no_agent` with injection | Evaluate whether summary adds value |
| `prompt: "analyze data, pick winners, write report"` | LLM-driven | Needs reasoning |
| `prompt: "check if X happened, then Y"` | LLM-driven | Conditional logic |

## ⏱️ Script Hardening: Timeout Protection for no_agent Jobs

When a no_agent cron job runs a multi-step shell script, **one hanging step can kill the entire job** — the cron engine has a hard cap and will SIGKILL the whole script after the timeout, wasting all prior progress.

**The pattern:** wrap every potentially-blocking step with `timeout N` + exit code handling.

### Shell script template with timeout protection

```bash
#!/bin/bash
cd /opt/data

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 📈 Step 1..."
.venv/bin/python3 /opt/data/scripts/stock-update/update_daily.py --force
STEP1_EXIT=$?
if [ $STEP1_EXIT -ne 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ Step 1 failed (exit: $STEP1_EXIT)"
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 📊 Step 2 (timeout 10 min)..."
timeout 600 .venv/bin/python3 /opt/data/projects/taiwan-stock-cashflow-api/screening/update_all_tech_indicators.py
STEP2_EXIT=$?
case $STEP2_EXIT in
    0)   echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ Step 2 completed" ;;
    124) echo "[$(date '+%Y-%m-%d %H:%M:%S')] ⚠️ Step 2 timed out (600s), killed" ;;
    *)   echo "[$(date '+%Y-%m-%d %H:%M:%S')] ⚠️ Step 2 failed (exit: $STEP2_EXIT)" ;;
esac

echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ Pipeline done"
```

### Exit codes to know

| Code | Meaning | Action |
|------|---------|--------|
| 0 | Success | Normal |
| 124 | `timeout` killed the command | Increase timeout or fix the hanging step |
| 137 | SIGKILL (128+9) | OOM killer or manual kill |
| 143 | SIGTERM (128+15) | Graceful shutdown signal |

### Why this matters for no_agent cron

- Without `timeout`, a hung process (e.g. SQLite lock contention, external API stall) blocks the whole script until the **cron engine's hard cap** (2400s default) — that's 40 minutes of nothing.
- With `timeout`, the hanging step is killed after N seconds, exit code 124 is logged, and subsequent steps can still run.
- **Without exit code handling**, `timeout 600 cmd; echo "done"` still prints "done" even when the command was killed — masking the failure.

### Triggers (when to add this)

Your no_agent script needs timeout protection if any step:
- Makes network requests (API calls — especially FinMind, twstock)
- Writes to a shared SQLite that other cron jobs or the dashboard also access
- Processes 1000+ items in a loop
- Has been seen with `database is locked` errors in prior runs

### Diagnosing `database is locked` across scripts

When a no_agent cron job crashes with `database is locked`, the root cause is often a script that connects to the shared DB *without* setting `timeout` or `busy_timeout` — it never waits for the lock to release. Diagnose quickly:

```bash
# List every sqlite3.connect() call that is missing timeout= (the common culprit)
grep -rn "sqlite3\.connect(" /opt/data/scripts/ /opt/data/projects/ --include="*.py" \
  | grep -v "timeout="
```

Every match needs `timeout=60` + `PRAGMA busy_timeout=30000` + `PRAGMA journal_mode=WAL` added. See `taiwan-stock-data-pipeline` skill's "database is locked" section for the fix pattern and a full production example.

### Related: SQLite lock contention between cron jobs

`database is locked` happens when two processes write to the same SQLite concurrently. Common causes on this system:
- `twstock-daily-scan` (16:00) + `twse_daily_update` (16:06) + `ohlc-verification` (16:00) + `taiwan-tech-strategy-daily` (16:00) — all hitting the same DB between 16:00–16:10
- Dashboard webserver (persistent SQLite read connection)

**Mitigations (in order of preference):**
1. **Stagger cron schedules** — give each job a 5–15 min buffer instead of clustering at :00
2. **Add `timeout` protection** (above) so a lock-waiting process doesn't hang forever
3. **Use WAL mode** — `PRAGMA journal_mode=WAL;` on the DB allows concurrent reads + writes
4. **Retry in script** — simple 3-attempt retry loop with exponential backoff for transient locks

### Script path resolution for cron

⚠️ **Crucial Hermes cron gotcha:** The `script` field in a cron job resolves relative to `~/.hermes/scripts/` — NOT the current directory or `/opt/data/scripts/`. To see what's actually available:

```bash
ls -la ~/.hermes/scripts/
```

If you update a script at `/opt/data/scripts/foo.sh`, you MUST also copy it to `~/.hermes/scripts/foo.sh` (and `chmod +x`) for the cron job to pick up changes:

```bash
cp /opt/data/scripts/foo.sh ~/.hermes/scripts/foo.sh
chmod +x ~/.hermes/scripts/foo.sh
```

Verification: `cronjob action=list` shows the script name. The actual file read at run-time is `~/.hermes/scripts/<script_name>`.

## 🐕 no_agent Watchdog Pattern（正常安靜，異常才叫）

For **periodic health checks / watchdogs** (e.g., API health checks every 5 min), the user explicitly wants:

> **正常時完全安靜，異常時才發通知。**

This is how no_agent handles it:

| 腳本行為 | no_agent 反應 | 使用者收到 |
|---------|--------------|---------|
| `exit 0` + **無 stdout** | ✅ exit 0 + 空輸出 = **安靜（不發任何訊息）** | 🤐 沒事就是最好的消息 |
| `exit ≠ 0` + stderr/訊息 | ⚠️ 排程器自動通知 | 錯誤通知送達 |

### 實作方式

```bash
#!/bin/bash
# watchdog pattern: silent on success, noisy on failure

result=$(curl -s -o /dev/null -w "%{http_code}" "$URL" 2>/dev/null)
if [ "$result" = "200" ]; then
  # exit 0 + empty stdout = no notification in no_agent mode
  exit 0
else
  echo "⚠️ Service returned HTTP $result at $(date)"
  exit 1
fi
```

### 關鍵細節

- **不要**在正常時 echo "✅ healthy" — 即使 exit 0，有 stdout 就會觸發發送
- 錯誤時**務必** exit ≠ 0，排程器才會知道失敗了
- exit 1 + 錯誤訊息 → 使用者收到 raw error，沒有 LLM 幫忙分析
- 如果你的 watchdog 需要錯誤時智慧處理（retry、判斷嚴重性、摘要），請保留 LLM 模式

### 適用場景

| 適合此模式 | 不適合 |
|-----------|-------|
| API health check（每 5 分鐘） | 需要錯誤分析 + retry 邏輯 |
| 磁碟空間監控 | 需要摘要多個服務狀態 |
| 程序存活檢查 | 需要條件式通知（「前 3 次失敗才警報」） |
| 固定時間點檢查 | 跨多個資料來源的綜合健康報告 |

### Pitfall: 沒有 LLM 幫忙分析錯誤

```
# LLM 模式（現狀）：
錯誤 → LLM 分析 → 「twstock 503，API 維護中，預計 15 分鐘後重試」

# no_agent watchdog（轉換後）：
錯誤 → raw stdout → ⚠️ Job 異常退出 (exit 1) [raw error message]
```

使用者接受這個 trade-off — 如果腳本本身的錯誤訊息就夠清楚（HTTP 503、disk full），不需要 LLM 翻譯。如果需要智慧處理，保留 LLM 模式或把錯誤處理邏輯寫進腳本本身。

## no_agent Conversion Assessment

When evaluating whether an LLM-driven cron job can be converted to pure script (`no_agent=true` + `script`), use these criteria:

### ✅ Good no_agent candidates (pure data pipeline)

The job's prompt is essentially: *"run script X, report output"* with no reasoning or conditional logic. **Convert instantly.**

- Job has no `skills` attached
- Prompt commands are a fixed sequence of shell/python invocations
- Output is deterministic (same input → same output)
- No LLM-generated summary, analysis, or decision needed

### ❌ Keep as LLM-driven (needs reasoning)

- Reports require analysis/summarization of script output
- Output varies based on data content (e.g., "which stocks to watch")
- Cross-references multiple data sources
- Produces human-readable briefings with commentary

### 🔄 Hybrid pattern (partial conversion)

**Before** (LLM-driven, wasteful):
```yaml
prompt: "Run update_daily.py, then run scan.py, then report"
```

**After** (no_agent runs script that collects data, LLM-only when needed):
```yaml
script: collect_and_scan.sh      # pure data
no_agent: true
```
+ an LLM job on a different schedule that reads the results.

### Conversion procedure

```bash
# 1. Create a wrapper script (if needed)
cat > /opt/data/scripts/some_pipeline.sh << 'SCRIPT'
#!/bin/bash
set -euo pipefail
cd /opt/data
/opt/data/.venv/bin/python3 /opt/data/scripts/stock-update/update_daily.py --force
/opt/data/.venv/bin/python3 /opt/data/projects/taiwan-stock-cashflow-api/screening/update_all_tech_indicators.py
SCRIPT
chmod +x /opt/data/scripts/some_pipeline.sh

# 2. Update the cron job
cronjob action=update job_id=<id> \
  script="some_pipeline.sh" \
  no_agent=true \
  workdir="/opt/data" \
  model='{}'  # clear model/provider for no_agent jobs (they don't use LLM)
```

### Pitfall: cleared prompt + model on update

When updating to `no_agent=true`, the existing `prompt` and `model`/`provider` may persist. The `no_agent` flag makes them inert, but set them to empty for cleanliness:

```bash
cronjob action=update job_id=<id> \
  script="new_script.sh" \
  no_agent=true \
  prompt="" \        # clear the old LLM prompt
  model='{}'         # clear model/provider
```

Verify with `cronjob list` — the job should show `no_agent: true`, empty `prompt_preview`, and no `model`/`provider`.

### Pitfall: script path in prompt vs actual path mismatch

When the cron job is LLM-driven (no `script` field), the script path lives only inside the `prompt` text. This is a single point of failure — renamed or moved files break silently with no error logged (the LLM just produces `FileNotFoundError` in its output).

**Detection:**
```bash
# Extract script paths from every cron job's prompt
hermes cron list | grep -E "(python3|bash) /opt/data" | head -20
# Then stat each path
for f in $(hermes cron list | grep -oP '/opt/data/[^ ]+\.py|/opt/data/[^ ]+\.sh'); do
  [ -f "$f" ] && echo "✅ $f" || echo "❌ MISSING: $f"
done
```

**Best practice:** Migrate any cron job whose prompt is purely "run script X" to `script: X.sh` + `no_agent=true`. This moves the script reference from free-text to a structured field that Hermes validates at schedule time.

## ⚠️ FinMind Rate Limit Pitfall

FinMind Free Tier has strict rate limits (IP ban at ~403 Forbidden). **Never schedule batch financial updates more than weekly.**

- `finmind-batch-financial-update` → **Weekly Monday 15:00** (not daily)
- If job hangs for >30 min, it's likely waiting on 403 backoff
- Scripts have built-in ban detection but daily runs exceed quota

## Profile Skills Divergence

Hermes profiles maintain **independent** `skills/` directories. There is NO global auto-sync — each profile must carry its own copy.

**Symptoms:**
- A skill works in one profile but not another (e.g., `anysearch` in research but not default)
- Same script path fails in one profile's cron job
- `skills_list` returns different results per profile
- `hermes skills list` shows different counts

**Detection:**
```bash
# Compare skills between two profiles
comm -23 \
  <(cd /opt/data/profiles/<src>/skills && find . -name "SKILL.md" | sed 's|^\./||;s|/SKILL.md$||' | tr '/' ':' | sort) \
  <(cd /opt/data/profiles/<dst>/skills && find . -name "SKILL.md" | sed 's|^\./||;s|/SKILL.md$||' | tr '/' ':' | sort)
```

**Sync procedure:**
1. Identify which skills are needed in the target profile (e.g., 台股 skills → default, research tools → research)
2. Copy entire skill directories preserving structure:
   ```bash
   cp -r /opt/data/profiles/<src>/skills/<category>/<skill-name> /opt/data/profiles/<dst>/skills/<category>/
   ```
3. Verify with `hermes skills list` in the target profile
4. Test the skill works (e.g., `skill_view(name='anysearch')`)

**Key insight:** Both profiles can share the same global `/opt/data/skills/` directory for bundled skills, but profile-specific skills must be copied individually. The `config.yaml` `skills.external_dirs` setting is empty by default — no external skill directories are mounted.

**Best practice:** Keep `default` as the canonical operational profile. Copy missing skills from other profiles to `default` after migration. Keep research-specific skills (MLOps, autonomous agents, dev tools) in the research profile only.

### ⚠️ Research Profile Is Empty — No Config, No Skills, No Env

The `research` profile at `/opt/data/.hermes/profiles/research/` exists but has **no `config.yaml`**, no `.env`, and only a `skills/` directory. It cannot run any model, gateway, or cron job.

**Detection:** `ls -la /opt/data/.hermes/profiles/research/` — if only `skills/` exists, the profile is non-functional.

**Impact:** Any cron jobs targeting research profile will silently fail. Always verify profile completeness before assigning jobs to it.

## Missing Dependencies

Some scripts import packages not in the venv (e.g., `yfinance` for `batch_evaluate_financial.py`).

**Fix (shared venv):**
```bash
cd /opt/data && uv pip install <package> -p .venv/bin/python3
```

**Fix (project-local venv):** If the package is project-specific (e.g., `apify_client` for Instagram scrapers), create a venv in the project directory:
```bash
cd /path/to/project
python3 -m venv venv
./venv/bin/python -m pip install <package>
./venv/bin/python script.py
```

**Rule of thumb:** If the script imports `twstock` / `yfinance` / `pandas` → use `/opt/data/.venv/bin/python3`. If it imports a project-specific package like `apify_client` → create a project-local venv. See `apify-data-collection` skill for the full pattern.

Always test scripts manually after installing dependencies before relying on cron.

### Data Pipeline (no_agent)
```yaml
name: daily-stock-update
schedule: "0 16 * * *"   # 16:00 daily
script: run_daily_incremental_update.sh
workdir: /opt/data
no_agent: true
```

### LLM-Assisted Report (agent)
```yaml
name: taiwan-tech-strategy-daily
schedule: "0 16 * * *"
prompt: "Run the tech strategy analysis..."
skills: [taiwan-stock-data-pipeline]
```

### Periodic Maintenance
```yaml
name: auto-memory-scanner
schedule: "every 180m"   # every 3 hours
prompt: "Run the auto memory scanner..."
```

## Troubleshooting

### Can't see what a cron job actually did (full prompt, tool calls, output)
`cronjob list` only shows a truncated `prompt_preview`. To see the full execution:
1. Find the cron session ID: `cron_{job_id}_{YYYYMMDD}_{HHmmss}` format in `state.db`
2. Call `session_search(session_id="cron_7806a3f41013_20260721_235543")` — returns ALL messages including the full prompt, every tool call, and final output.
3. See `references/cron-session-search-debugging.md` for the full SQL query and real example.

### Job never executed
- Check if job is `enabled: true`
- Verify `last_run_at` is null (never ran) or stale
- Check if `workdir` exists and script is executable
- Look at `last_delivery_error` for clues

### Job running but failing
- Check `last_status` for `error`
- Verify script path is correct and executable
- Check Python venv exists at declared path
- Look at cron output logs

### Duplicate notifications
- Multiple profiles may have the same job
- Same job delivering to the same chat from different profiles
- Solution: pause redundant jobs, keep one

## References

- `references/cron-job-migration-checklist.md` — Detailed migration steps
- `references/hermes-cron-scheduling-best-practices.md` — Scheduling guidelines
- `references/cron-job-reconstruction.md` — How to rebuild deleted cron jobs from scratch
- `references/cron-script-audit.md` — Real session audit of 14 cron jobs showing path mismatches, venv discoveries, and no_agent conversion candidates
