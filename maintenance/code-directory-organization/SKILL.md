---
name: code-directory-organization
description: >-
  Standards and conventions for organizing code projects, scripts, and
  experimental files in the Hermes Agent environment. Covers when to
  create new directories, how to name them, and the standard project
  structure conventions.
version: 1.0.0
author: Hermes Agent
tags: [organization, directory, project-structure, conventions, maintenance]
---

# Code Directory Organization

## Overview

Hermes Agent environment has no automatic directory creation. All code placement
follows these conventions:

## Standard Placement Rules

| Scenario | Location | Example |
|----------|----------|---------|
| **New feature/project** | `/opt/data/<project-name>/` | `taiwan-stock-cashflow-api/` |
| **Script with cron** | `/opt/data/scripts/` | `auto_memory_scan.py` |
| **One-time utility** | `/opt/data/*.py` | `update_daily.py` |
| **Skill scripts** | `skills/<name>/scripts/` | `polymarket.py` |
| **Plans/specs** | `docs/plans/` / `docs/specs/` | `2026-07-10-xxx.md` |
| **Isolated dev** | `.worktrees/feat/<name>/` | Feature branches |

## Project Structure Convention

When creating a new project directory:

```
/opt/data/<project-name>/
├── core/              # Main logic modules
├── scripts/           # Utility scripts
├── tests/             # Test files
├── app.py             # Entry point (if applicable)
├── .venv/             # Virtual environment
├── requirements.txt   # Dependencies
└── README.md          # Usage notes
```

## Directory Lifecycle

### Creation
1. User requests a new feature/project
2. Agent creates `/opt/data/<project-name>/` with standard structure
3. Plans go in `docs/plans/`, specs in `docs/specs/`

### Consolidation
When multiple overlapping directories exist:
1. **Identify** which directory is actively referenced (check cron jobs)
2. **Verify** the active version works (dry-run)
3. **Rename** inactive directories to `archive_*` (not delete)
4. **Observe** for one week before deleting archives

### Cleanup
When scripts accumulate:
1. Check which files are referenced by cron jobs
2. Classify into: keep, archive, or delete
3. Delete same-night test files and old iterations
4. Preserve only the latest version of iterative scripts

## Naming Conventions

- **Projects:** kebab-case (`taiwan-stock-cashflow-api`)
- **Scripts:** snake_case (`update_daily.py`)
- **Tests:** `test_<target>_<feature>.py` (e.g., `test_twse_openapi.py`)
- **Archives:** `archive_<original-name>/`
- **Plans:** `YYYY-MM-DD-<feature>.md`

## Pitfalls

1. **No default directory creation** — The system does NOT auto-create directories for new projects. The agent must explicitly create them.
2. **Multiple screening directories** — Historically, `/opt/data/ai_stock_tw/`, `/opt/data/ai_stock_tw_dashboard/`, and `/opt/data/taiwan-stock-cashflow-api/` all contained `screening/` subdirectories. Always verify which one is referenced by cron before acting.
3. **Test file proliferation** — API comparison sessions produce dozens of test files in one night. Clean them up after the comparison is done.
4. **Wrapper scripts** — Shell scripts like `run_daily_incremental_update.sh` may not be directly named in cron prompts but call other scripts. Check their content before deleting.

## Related Skills

- `legacy-script-cleanup` — Process for identifying and removing obsolete scripts
- `git-worktrees` — Isolated development for feature work
- `writing-plans` — Structured development prevents legacy accumulation
- `taiwan-stock-data-pipeline` — Has accumulated legacy scripts from API comparisons
