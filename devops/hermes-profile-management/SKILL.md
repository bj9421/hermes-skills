---
name: hermes-profile-management
description: Manage multiple isolated Hermes Agent profiles for different workflows.
---

# Hermes Profile Management

Manage multiple isolated Hermes Agent profiles for different workflows (e.g., research, coding, testing). Each profile has its own config, `.env`, SOUL.md, skills, and cron jobs.

## When to Use
- You need separate environments with different API keys, models, or personas.
- You want to run multiple agents simultaneously without interference.
- You wish to experiment with a new configuration while keeping a stable default.

### Cross-Profile Cron Job Migration

When moving cron jobs between profiles (e.g., research → default), `cronjob(action='create')` WORKS in current env (verified 3× this session) — use it for single jobs. For bulk moves, write the **live** store directly: the active gateway (PID 146, `cwd=/opt/data`, no `-p`) reads **`/opt/data/cron/jobs.json`**, NOT `profiles/<name>/cron/jobs.json`. Writing to the legacy path silently fails to surface the job. See `hermes-cron-management` → `references/cron-live-store-and-migration.md` for the full recipe and the botched-migration failure pattern. Also fix schedule/model drift at migration time (e.g. re-pin unpinned jobs, switch daily→weekly FinMind).

See `references/cron-job-migration.md` for the full workflow: inventory → copy scripts → update workdir → pause source → verify.

### Cross-Profile Skill Sharing

When a skill exists in one profile (e.g., `research`) but not another (e.g., `default`), copy only the skill directory — never copy entire profile directories.

**Safe pattern:**

> ⚠️ **Catch nested skill directories.** Skills can be nested under subdirectories (e.g. `devops/hermes-cron-management/`). A top-level `ls` shows only the subdirectory name, not the actual skills. Always use recursive `find` to enumerate actual skill folders, then compare by basename + dirname.

```bash
# 1. List ALL skills (including nested) in both profiles
find /opt/data/profiles/<source>/skills -name "SKILL.md" -exec dirname {} \; | sort > /tmp/source_skills.txt
find /opt/data/profiles/<target>/skills -name "SKILL.md" -exec dirname {} \; | sort > /tmp/target_skills.txt

# 2. Find skills in source but NOT in target (by basename)
for src_path in $(cat /tmp/source_skills.txt); do
  basename=$(basename "$src_path")
  if ! grep -q "/$basename$" /tmp/target_skills.txt; then
    rel_path="${src_path#/opt/data/profiles/<source>/skills/}"
    mkdir -p "/opt/data/profiles/<target>/skills/$(dirname "$rel_path")"
    cp -r "$src_path" "/opt/data/profiles/<target>/skills/$rel_path"
    echo "✅ Copied $rel_path → target"
  fi
done

# 3. Reload skills in target profile
hermes --profile <target> reload-skills
```

> 💡 **Why basename matching?** The same skill name may live under different category directories in different profiles (e.g. `research/devops/skill` vs `default/devops/skill`). Matching by basename avoids false positives from category drift.

**What NOT to copy between profiles:**
- `config.yaml` — per-profile settings (cron timeouts, web backend, etc.) differ intentionally
- `cron/jobs.json` — cron jobs are profile-scoped; copying merges unintended tasks
- `state.db`, `memory_store.db` — independent session/memory stores
- `logs/`, `sessions/` — historical data, not portable
- `gateway.pid`, `gateway.lock`, `gateway_state.json` — runtime state
- `auth.json`, `auth.lock` — per-profile OAuth state

**Pitfall — AnySearch `.env` location:** The AnySearch CLI reads `.env` from `<skill_dir>/.env`, NOT from the profile's `.env` file. If the API key is in the profile `.env` but missing from `<skill_dir>/.env`, the CLI silently falls back to anonymous access. Fix:
```bash
grep ANYSEARCH_API_KEY /opt/data/.env | tee /opt/data/profiles/default/skills/anysearch/.env
```

**Mandatory cross-profile search before reporting unavailable:** When any tool, skill, CLI, or feature is reported as missing/not-found, the agent MUST search across ALL profile skill directories before concluding it doesn't exist. Check both `~/.hermes/profiles/*/skills/` and `/opt/data/profiles/*/skills/`. Also check `session_search` for prior mentions. This is a hard requirement — not optional.

**Memory capacity management:** When memory exceeds 90%, single-add/replace operations will fail. Use `operations` array (batch remove+add) in ONE call. If `memory_char_limit` in config.yaml seems inconsistent with actual usage, the `holographic` provider may calculate differently — increase the limit in config.yaml to prevent repeated failures.

## Steps

### 1. List Existing Profiles
```bash
hermes profile list
```
Shows current profiles, their models, gateway status, and aliases.

### 2. Create a New Profile (Clone from Default or Another)
```bash
# Clone from the active profile (default if none set)
hermes profile create <profile-name> --clone

# To clone from a specific existing profile:
hermes profile create <profile-name> --clone-from <source-profile>
```
- `--clone` copies `config.yaml`, `.env`, `SOUL.md`, and skills from the source.
- A wrapper script is created at `~/.local/bin/<profile-name>` (add `~/.local/bin` to your `$PATH` for easy use).

### 3. Use a Profile
#### Direct Wrapper (if `$PATH` includes `~/.local/bin`)
```bash
<profile-name> chat          # start interactive chat
<profile-name> dashboard     # start the web dashboard
<profile-name> cron list     # view cron jobs for this profile
```
#### Explicit Profile Flag
```bash
hermes --profile <profile-name> chat
hermes --profile <profile-name> config show
```

### 4. Switch Default (Sticky) Profile
```bash
hermes profile use <profile-name>
```
After this, plain `hermes <command>` uses `<profile-name>` until changed.

### 5. Edit Profile Configuration
#### Edit config.yaml
```bash
hermes --profile <profile-name> config edit
```
#### Edit .env (API keys, model overrides)
```bash
hermes --profile <profile-name> config edit   # .env is edited via the same command
```
> **Note**: The `.env` file is secret‑bearing; the editor will open it but content is not displayed in tool outputs.

### 6. Customize SOUL.md (Persona / Instructions)
```bash
hermes --profile <profile-name> config edit   # then edit the SOUL.md file under the profile directory
```
Or directly:
```bash
$EDITOR /opt/data/profiles/<profile-name>/SOUL.md
```

### 7. Install / Sync Skills
Skills bundled with Hermes are synced automatically on `hermes update`.  
To add extra skills to a profile:
```bash
hermes --profile <profile-name> skills install <skill-name>
```
To view installed skills:
```bash
hermes --profile <profile-name> skills list
```

### 8. Delete a Profile (When No Longer Needed)
\`\`\`bash
hermes profile delete <profile-name>
\`\`\`
This removes the profile directory and its wrapper script.  
**Warning**: This action cannot be undone.

#### Verification: Confirm a Profile Was Fully Deleted

`hermes profile delete` removes the main profile directory under `~/.hermes/profiles/`, but residual files often survive in other locations. After deletion, run this checklist:

```bash
# 1. Main profile directory gone?
ls ~/.hermes/profiles/<name>/       # should fail

# 2. Alternative profile location?
ls /opt/data/profiles/<name>/       # should fail (manually-created)

# 3. Skill dir named after the profile?
ls /opt/data/skills/<name>/         # should fail
ls /opt/data/skills/*/<name>/       # should fail (nested category)

# 4. No running processes?
ps aux | grep <name>

# 5. No cron jobs referencing it?
grep -r "<name>" /opt/data/cron/jobs.json 2>/dev/null
# Also check per-profile cron stores
find /opt/data -path "*/cron/jobs.json" -exec grep -l "<name>" {} \;

# 6. No config references?
grep "<name>" /opt/data/config.yaml 2>/dev/null
```

**⚠️ Common false positive — three patterns:** All three are NORMAL skill-category directories that happen to share the profile name. They are NOT profile artifacts. Do NOT touch them during cleanup unless the user explicitly confirms.

  1. `/opt/data/profiles/default/skills/<name>/` — skills installed under the default profile sharing the deleted profile's name
  2. `/opt/data/skills/<name>/` — a top-level skill category (e.g., `research/`) that shares the profile name
  3. `/opt/data/skills/<category>/<name>/` — a nested skill category (e.g., `mlops/research/`) that shares the profile name

  **What makes these false positives:** The Hermes skill library organizes skills into category directories (`skills/creative/`, `skills/devops/`, `skills/research/`, etc.). These directories exist because skills exist in those categories — NOT because a profile named `research` was ever created. Deleting them removes skills that work fine under any profile.

**📌 What to do with residuals:**
- Move to archive (never `rm`): `mv /path/to/residual /opt/data/archive/<name>-$(date +%F)/`
- Delete stale memory entries separately (see below)

#### Post-Deletion: Clean Up Stale Memory

`hermes profile delete` removes files on disk but does **not** remove the agent's memory entries about that profile. Stale entries (model settings, gateway status, usage notes) persist and the agent will reference them in future sessions.

After deleting a profile, manually purge related memory entries:

```bash
# 1. At session start, scan the MEMORY section for references to the deleted profile.
#    Typical stale entries to look for:
#    - "Research/profile X ... has NO config.yaml…"
#    - "User expects profile X to mirror profile Y's settings…"
#    - "profile X gateway (PID N) is stuck 'retrying'…"
#    - "profile X: model=... fallback=…"
#    - "Maintains two profiles: 'default' and 'X'…"

# 2. Remove each with the memory tool. If batch (operations array) fails due to
#    exact-text mismatch, remove entries one at a time — the old_text must match
#    the stored entry exactly. Start with a short unique substring and iterate.

# 3. Also clean entries that reference the deleted profile *inline* (e.g.
#    "備援模型守則…Research: …" or "Custom provider …兩個 profile 均已更新").
#    Replace them to remove the stale reference.
```

For profiles managed under `~/.hermes/profiles/`, `hermes profile delete` suffices for the filesystem. For manually-created profiles (outside `~/.hermes/profiles/`), erase with `rm -rf /path/to/profile/dir`.

> 💡 **File deletion and memory deletion are independent operations.** Removing the directory does not purge the agent's memory — this must be done as a separate step after deletion.

## Pitfalls & Troubleshooting
- **Wrapper not found**: Ensure `~/.local/bin` is in your `$PATH`. Add `export PATH="$HOME/.local/bin:$PATH"` to your shell rc file.
- **Multi‑gateway processes are normal**: Each profile with a gateway (default, research, coder) runs its own `hermes gateway run` process. `ps aux | grep hermes` will show multiple gateway PIDs — this is correct, not a leak.
- **Telegram token conflict between profiles sharing config**: If two profiles use the SAME `config.yaml` (e.g., research profile has no separate config, inherits from root), they will share the same Telegram bot token and fight for ownership. The first one to start wins; the second gets "Token already in use (PID XXX)". **Fix**: Kill the competing gateway (`kill <pid>`) and restart only the one you want active. If a profile doesn't need Telegram, don't run its gateway — or give it a separate config with no Telegram token.
  - **⚠️ Dashboard stuck is a common downstream symptom**: The competing gateway's retries corrupt the original gateway's internal routing state. The dashboard UI loads fine (HTTP 200) but shows stale/empty data, models appear broken, and Telegram goes silent. Users often interpret this as "dashboard is broken" or "API keys died" — the real fix is killing the competing gateway, not restarting the dashboard. See `hermes-dashboard-troubleshooting` → dual-gateway Telegram token conflict pitfall.
- **Gateway token ownership**: The first gateway to successfully authenticate with Telegram owns the token. Subsequent gateways with the same token will fail with `Telegram gateway token already in use`. To resolve: identify the owner with `ps aux | grep hermes | grep gateway`, kill the non-owner, then the owner will regain control.
- **Profiles may live outside `~/.hermes/profiles/`**: `hermes profile list` only shows Hermes-managed profiles under `~/.hermes/profiles/`. Legacy or manually-created profiles can exist elsewhere (e.g., `/opt/data/profiles/`), invisible to the CLI until referenced by path. To discover ALL Hermes profile directories on disk:
  ```bash
  find /opt/data -name "profile.yaml" -not -path "*/skills/*" -not -path "*/.hermes/skills/*"
  ```
  Each result is a valid standalone profile directory with its own `config.yaml`, `SOUL.md`, `.env`, and `skills/`. Note the path and decide whether to keep, migrate, or delete.
- **Dashboard profile panel lists EVERY directory under the profiles dir — including legacy empty shells**: the dashboard scans on-disk profile directories, not just the active profile. After migrating a profile's cron + gateway away but leaving the directory behind (e.g. `/opt/data/profiles/research/` holding only an empty `state.db` (0 sessions, schema re-initialized by an upgrade) + an old `home/.hermes/memory_store.db`), the dashboard still shows it as a selectable profile. Diagnose shell vs active profile: config.yaml present? gateway process running (`ps aux | grep hermes`)? cron store present? sessions in `state.db`? All no + 0 sessions = legacy shell (safe to archive). To hide it from the dashboard: `mv /opt/data/profiles/<name> /opt/data/archive/<name>-$(date +%F)/`.
- **`hermes profile list` can crash with `PermissionError: [Errno 13] ... '/root/.local/bin'`** (observed after the v0.19.1 upgrade): the CLI's alias-map builder (`build_alias_map`) stats the wrapper dir and dies when it's not readable inside the container. Don't conclude profiles are gone — enumerate on disk instead: `ls /opt/data/profiles/` or `find /opt/data -maxdepth 3 -name profile.yaml`, then inspect each directory directly.
- **Dashboard "API" light vs gateways**: The "API" indicator on the dashboard lights up for `hermes serve`, NOT for profile gateways. An absent API light is normal in Telegram-only workflows. See `hermes-dashboard-troubleshooting` skill → `references/service-topology.md`.
- **Dashboard binds only to localhost**: By default the dashboard refuses to bind to `0.0.0.0` unless an auth provider is configured or `--insecure` is set. For external access (e.g., via Tailscale) set:
  ```bash
  export HERMES_DASHBOARD_INSECURE=1   # only on trusted networks
  export HERMES_DASHBOARD_PORT=8501
  export HERMES_DASHBOARD_HOST=0.0.0.0
  ```
  Then restart the dashboard service (`hermes dashboard --stop` then `hermes dashboard`).
- **Environment variables not persisting**: Variables set in the shell do not affect the supervised dashboard service. To make them permanent, edit the profile's `.env` or configure via `hermes config set` inside the profile.
- **Cloning from wrong source**: Verify the source profile with `hermes profile list` before using `--clone-from`.
- **Forgot to reload after SOUL.md changes**: Restart the chat session or run `hermes profile use <name>` again to pick up updates.
- **Memory isolation despite sharing config.yaml**: A profile with a `config.yaml` that lacks an explicit `plugins.hermes-memory-store.db_path` may silently use a separate SQLite DB in `$HOME/.hermes/` under that profile's runtime, NOT the root config's `db_path`. Always set `db_path` explicitly — and use an **absolute path**— in every profile's config to avoid this. Verify with `find /opt/data -name "memory_store.db" -not -path "*/state/*"`.
- **Export scripts break after memory consolidation**: After merging two profiles' memory stores, any export or pipeline scripts that read from the old per-profile DB paths will silently produce stale/empty output. Always update the DB path in those scripts and run a test export after consolidation. See `references/memory-to-obsidian-export.md` for the common memory→Obsidian pipeline pattern.
- **`cronjob create` works** in current env (verified this session, 3×) — the older `'<=' not supported` bug claim does NOT reproduce. Use it freely for single jobs; for bulk migration write the **live** store (`/opt/data/cron/jobs.json`), NOT the legacy `profiles/<name>/cron/jobs.json` (writing there silently fails to surface the job in `cronjob list`). See `hermes-cron-management` → `references/cron-live-store-and-migration.md`.
- **`cronjob list` only shows the ACTIVE profile's jobs.** If you run it from `default` you will NOT see jobs in `research` (e.g. taiwan-tech-strategy-daily, ohlc-verification, finmind-batch all live in `research`). To audit every profile, read the stores on disk: `find /opt/data -path "*/cron/jobs.json"` (default at `/opt/data/cron/jobs.json`, named at `/opt/data/profiles/<name>/cron/jobs.json`). See `hermes-cron-management` → "PROFILE-SCOPED" + `references/cron-drift-and-jobs-json-locations.md`.
- **Cron jobs silently skip after a global model change (drift).** Switching the global provider/model (e.g. `custom`→`opencode-zen`) blocks any *unpinned* job with "Skipped to prevent unintended spend … config drifted". Fix: re-pin via `cronjob action=update job_id=<id> model={"model":...,"provider":...}`. Always pin LLM-driven jobs at creation. Details in `hermes-cron-management`.
- **Stale memory entries survive profile deletion.** `hermes profile delete` removes the profile directory but NOT the agent's memory. The agent will continue referencing the deleted profile (its settings, gateway status, usage notes) in future sessions. After deletion, manually clean memory: scan the MEMORY section at session start for references to the deleted profile and remove/replace them with the `memory` tool. This is especially important when the deleted profile was referenced inline in other entries (e.g. "兩個 profile 均已更新").

## Verification
After creating a profile, confirm isolation:
```bash
# Check that .env differs
diff /opt/data/.hermes/.env /opt/data/profiles/<profile-name>/.env

# Ensure skills directory is separate
ls /opt/data/profiles/<profile-name>/skills/
```

## References
- See `hermes profile --help` for all subcommands.
- For dashboard external access troubleshooting, refer to the skill `hermes-dashboard-troubleshooting` (if available) or the Hermes docs on `HERMES_DASHBOARD_INSECURE`.
- For deep-dive on per-profile memory architecture, sharing strategies, and holographic provider settings: `references/memory-architecture.md`.
- For the automated memory-to-Obsidian export pipeline (no_agent cron, vault permission strategy, export script patterns): `references/memory-to-obsidian-export.md`.
- For discovering profiles that exist outside the official `~/.hermes/profiles/` directory (legacy/migrated/manually created): `references/profile-discovery.md`.
- For memory capacity troubleshooting and consolidation patterns: `references/memory-capacity.md`.
- For Telegram model picker behavior with custom providers: `references/telegram-model-picker-custom-providers.md`.