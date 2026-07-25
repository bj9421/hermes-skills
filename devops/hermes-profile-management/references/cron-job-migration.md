# Cron Job Migration Between Profiles

## When to Use
- Moving cron jobs from one profile to another (e.g., research → default).
- Consolidating jobs into a single profile to avoid duplicates.
- Rebuilding cron jobs after a profile was deleted or corrupted.

## Step 1: Inventory Source Profile Jobs
```bash
# List all jobs in a profile
cat /opt/data/profiles/<source>/cron/jobs.json 2>/dev/null || echo "No jobs.json"

# Or via CLI
hermes cron list
```

## Step 2: Decide Migration Strategy
| Scenario | Action |
|----------|--------|
| Jobs use shared resources (DB, scripts, vault) | Move workdir to target profile |
| Jobs are profile-specific (use profile-only skills) | Keep in source or recreate |
| Duplicate jobs exist in both profiles | Pause source, test target, then remove source |

## Step 3: Copy Scripts (if needed)
If the cron job references scripts in the source profile's `scripts/` directory:
```bash
mkdir -p /opt/data/profiles/<target>/scripts
cp /opt/data/profiles/<source>/scripts/*.sh /opt/data/profiles/<target>/scripts/
cp /opt/data/profiles/<source>/scripts/*.py /opt/data/profiles/<target>/scripts/
```

## Step 4: Update Job Configuration
### Method A: Edit jobs.json directly (recommended)
```bash
# Read existing jobs
cat /opt/data/profiles/<target>/cron/jobs.json

# Edit to change workdir or other fields
# Save the file — Hermes auto-reloads on next tick
```

### Method B: Use `cronjob update`
```bash
# Change workdir of existing job
cronjob(action='update', job_id='<job_id>', workdir='/opt/data/profiles/<target>')
```

## Step 5: Pause/Remove Source Job
```bash
# Pause (safe, reversible)
cronjob(action='pause', job_id='<job_id>')

# Remove (permanent)
cronjob(action='remove', job_id='<job_id>')
```

## Step 6: Verify
```bash
# Manual test
cd /opt/data/profiles/<target> && bash scripts/<script>.sh

# Check cron list
hermes cron list
```

## Pitfalls
- **`cronjob create` may fail** with `'<=' not supported between instances of 'str' and 'int'` — this is a known bug. Use `write_file` to create `jobs.json` directly instead.
- **Shared DB paths**: Cron jobs that read SQLite DBs (e.g., holographic memory) will read whatever DB path is configured in the profile's config.yaml. Verify `plugins.hermes-memory-store.db_path` points to the correct DB.
- **Duplicate execution**: If both source and target have the same job, both will fire. Always pause/remove the source before relying on the target.
- **Script paths**: `workdir` determines relative paths in `script:` field. If job says `script: sync_holographic_to_obsidian.sh`, the file must exist in the workdir's root or `scripts/` subdirectory.
- **Python venv**: Jobs that run `.venv/bin/python3` need the venv to exist in the workdir. If the venv is at `/opt/data/.venv`, use absolute paths in scripts or set `workdir: /opt/data`.
