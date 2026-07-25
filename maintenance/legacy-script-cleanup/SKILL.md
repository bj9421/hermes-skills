---
name: legacy-script-cleanup
description: >-
  Systematic process to identify, classify, and safely remove
  obsolete test scripts, duplicate iterations, and abandoned
  API comparison files from project directories.
version: 1.2.0
author: Hermes Agent
tags: [cleanup, scripts, legacy, maintenance, organization]
---

# Legacy Script Cleanup

## When to Use

- Scripts directory has accumulated test files (test_*.py, compare_*.py)
- Multiple versions of the same tool exist (fix_incomplete_v1.py → v5.py)
- Unclear which scripts are actively used vs experimentally abandoned
- Before merging or consolidating project directories

## Step-by-Step Procedure

### 1. Inventory All Files

```bash
ls -lh /opt/data/scripts/
ls -lh /opt/data/projects/*/screening/   # Check for duplicates in project subdirs
```

### 2. Check References

Use `grep -rl` or the Hermes search_files tool across the whole filesystem to find every reference — covers cron prompts, shell wrappers, and other scripts:

```bash
grep -rl "target_file.py" /opt/data/ --include="*.py" --include="*.sh" --include="*.md" 2>/dev/null | grep -v __pycache__
```

Also list all Hermes cron jobs via the cron tool — it shows script paths, prompt text, and job names:

```
Use cronjob(action='list') and inspect every job's `script` field and `prompt_preview`.
```

### 3. Detect Functional Duplicates

Before classifying individual files, identify pairs/groups of scripts that **do the same thing under different names**. Key signals:

| Signal | Example |
|--------|---------|
| Same purpose, one says "all" | `update_tech_indicators.py` vs `update_all_tech_indicators.py` |
| Same import chain, similar output | Two scripts both write to `screen_cache` table |
| Same cron wrapper targets | Two jobs running against same DB with similar logic |
| Same pattern, different age | Old `archive_*` dirs mirroring live `projects/` dir |

**Default rule: keep the newer version, archive the older one.** When in doubt, diff the two files — if they share >80% structure, they're duplicates. Check which one is referenced by cron (that's the live one).

### 4. Classify Files

| Category | Pattern | Action |
|----------|---------|--------|
| **Keep** | Referenced by cron | ✅ Retain |
| **Keep** | Latest version in series (e.g., fix_incomplete_v3.py) | ✅ Retain |
| **Keep** | Live project dir (projects/&lt;name&gt;/) | ✅ Retain |
| **Archive** | Functional duplicate, older (e.g., script vs script_all) | ❌ mv to archive/ |
| **Archive** | Old project copies in root (archive_*) | ❌ mv to archive/ |
| **Archive** | Old iterations (v1, v2, v4...) | ❌ mv to archive/ |
| **Archive** | Same-session test files (test_twse_*.py, test_tpex_*.py) | ❌ mv to archive/ |
| **Archive** | Comparison/report scripts (compare_*.py, final_*.py) | ❌ mv to archive/ |
| **Archive** | One-time manual scripts (manual_update_*.py) | ❌ mv to archive/ |
| **Review** | Root-level .py not in cron | ⚠️ Check individually |

### 5. Archive Only — mv, Never Delete

**User mandate: archive IS the permanent recycle bin. Never `rm`. Use `mv` only.**

```bash
# ✅ Always mv to archive (archive = safety net, not temporary backup)
mkdir -p /opt/data/archive/<descriptive-name>-$(date +%F)
mv -v /path/to/script.py        /opt/data/archive/<descriptive-name>/
mv -v /path/to/old_project_dir  /opt/data/archive/<descriptive-name>/
```

Observe for **several days** before deciding whether to purge. If something breaks
after the move, trivially revert with `mv` back. The archive is not a temporary
backup — it's the new home until the user decides otherwise.

**Bad pattern (DO NOT use):**
```bash
cp -v /path/to/file /opt/data/archive/  # ← still leaves original
rm -v /path/to/file                      # ← defeats safety net
```

### 6. Detect Cron Job Duplicates

After cleaning files, check if **cron jobs are also duplicating work**. Two LLM-driven jobs that both fill data gaps (same target, different time slots) are redundant:

```
cronjob(action='list')  # compare prompt_preview for conceptual overlap
```

When removing a duplicate cron job:
```
cronjob(action='remove', job_id='<id>')
```

### 7. Verify Post-Cleanup

```bash
# Run a dry-run on the primary update script
python3 /opt/data/scripts/stock-update/update_daily.py --dry-run
```

Also grep for stale references to deleted paths:
```bash
grep -rl "deleted_file.py\|archive_old_project" /opt/data/ --include="*.sh" --include="*.py" 2>/dev/null | grep -v __pycache__ | grep -v /opt/data/archive/
```

## Common Patterns

### API Source Comparison Sessions
Users often run a batch of API tests comparing multiple data sources (TWSE, TPEX, FinMind, TDCC). This produces:
- `test_<source>_<feature>.py` files (gzip, brotli, csrf, openapi, redirect...)
- `compare_*.py` and `final_*.py` reports
- `rate_limit_test.py`
- **All are disposable after the comparison is done.**

### Iterative Script Development
When debugging a script, users create multiple versions:
- `fix_incomplete_dates.py` → `fix_incomplete_fast.py` → `fix_incomplete_parallel.py` → `fix_incomplete_targeted.py` → `fix_incomplete_v3.py` → `fix_incomplete_v4.py`
- **Keep only the latest version that's in use.**

### Root-Level Scripts
Files in `/opt/data/*.py` are often:
- One-time utilities (fetch_stocks.py, test_twse.py)
- Dashboard components (dashboard.py, render_heatmap.py)
- **Check if referenced by cron before deleting.**

## Pitfalls

1. **Don't delete wrapper scripts** — `run_daily_incremental_update.sh` calls other scripts and may not be directly named in cron prompts.
2. **Check shebang lines** — Some scripts may be invoked indirectly via `python3 script.py` in cron prompts that don't include the filename literally.
3. **Functional duplicates aren't always versions** — `update_tech_indicators.py` vs `update_all_tech_indicators.py` are unrelated filenames that do the same job. Always diff scripts that share purpose before deciding.
4. **Don't forget cron job dedup** — Two cron jobs doing the same logical work (e.g., both filling data gaps) waste LLM tokens. After cleaning files, check for redundant jobs.
5. **Never `rm` — `mv` only to archive** — Even `cp + rm` is forbidden. Archive is the permanent recycle bin, not a temporary backup. `mv` to a dated subdirectory under `/opt/data/archive/` and observe for several days. User explicitly rejected deletion.
6. **Preserve the latest version** — When cleaning iterative development, always keep the newest numbered/lettered version.

## Related Skills

- `taiwan-stock-data-pipeline` — Has accumulated many legacy scripts from API comparisons
- `git-worktrees` — For safe experimentation without polluting main workspace
- `writing-plans` — Structured development prevents legacy accumulation
- `filesystem-cleanup` — **Overlaps significantly** (same core workflow). The curator may consolidate these two.

## Scripts

- `scripts/legacy_script_cleaner.py` — Automated scanner that checks cron references and classifies files. Usage: `python3 legacy_script_cleaner.py` (report mode) or `python3 legacy_script_cleaner.py --delete test_twse_*.py` (delete mode)
