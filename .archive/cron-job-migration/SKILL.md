---
name: cron-job-migration
description: Move, duplicate, or consolidate Hermes cron jobs across profiles safely. Handles script copying, workdir changes, and duplicate detection.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [cron, migration, profiles, deduplication]
---

# Cron Job Migration

Move, duplicate, or consolidate Hermes cron jobs across profiles safely.

## When to use

- Migrating a cron job from one profile to another
- Consolidating duplicate jobs that write to the same output
- Changing which profile's scripts a job uses
- Auditing which jobs belong in which profile

## Quick Reference

- **List jobs**: `cronjob(action='list')`
- **Move a job** (change workdir): `cronjob(action='update', job_id='<id>', workdir='/new/path')`
- **Delete a job**: `cronjob(action='remove', job_id='<id>')`
- **Pause temporarily**: `cronjob(action='pause', job_id='<id>')`
- **Resume**: `cronjob(action='resume', job_id='<id>')`

## Migration Checklist

When moving a cron job from one profile to another:

1. **Copy scripts** to target profile's `scripts/` directory
2. **Update `workdir`** via `cronjob(action='update', job_id=..., workdir='/path/to/target')` — this moves the job without deleting/recreating
3. **Test manually** before relying on schedule: `bash scripts/<script>.sh`
4. **Remove duplicates** — if source and target both trigger the same job, one is redundant. Ask user whether to disable source, not leave both running.

### Why This Matters
- Same DB → same output, two runs = wasted resources + unnecessary file overwrites
- Always confirm with user before leaving duplicate functionality
- The `workdir` field determines which profile's `scripts/` directory the cron job reads from

### Example: Moving holographic-to-obsidian-sync
```
# Step 1: Copy scripts
mkdir -p /opt/data/profiles/default/scripts
cp /opt/data/profiles/research/scripts/*.sh /opt/data/profiles/default/scripts/
cp /opt/data/profiles/research/scripts/*.py /opt/data/profiles/default/scripts/

# Step 2: Move workdir (no need to delete/recreate)
cronjob(action='update', job_id='...', workdir='/opt/data/profiles/default')

# Step 3: Test
bash /opt/data/profiles/default/scripts/sync_holographic_to_obsidian.sh

# Step 4: Confirm with user about removing the duplicate
```

## Pitfalls
- `cronjob(action='create')` with `job_id` on an existing job = update, not duplicate
- `workdir` must be an absolute path that exists
- `no_agent=true` jobs run scripts directly — ensure the script is executable and paths are correct
- Shared DBs across profiles mean identical exports — running the same job twice is pointless
- Script paths in cron jobs are relative to `workdir`