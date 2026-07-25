# Memory → Obsidian Export Pipeline

## Overview

Automated export of Hermes memory facts to Obsidian as human-readable Markdown.
Runs as a `no_agent` cron job: reads facts from the shared SQLite DB, groups by
category, and writes structured `.md` files to a vault subdirectory the user can
browse on their phone or desktop via Syncthing.

## Flow

```
Memory tool writes facts → SQLite DB (shared `/opt/data/.hermes/memory_store.db`)
                                │
                   cron (no_agent, daily 02:00)
                                │
                                ▼
                  export_holographic_to_md.py
                                │
                                ▼
           /opt/data/obsidian-vault/Holographic/   (container-writable)
           ├── 主人偏好.md         (user preference facts)
           ├── 環境設定.md         (environment / hardware facts)
           ├── Cron排程.md         (cron job facts)
           ├── 台股資料.md         (stock market facts)
           ├── 記憶庫架構.md       (memory architecture doc)
           └── MOC.md             (index / map of content)
                                │
                      Syncthing (Pi sendonly → phone)
                                │
                                ▼
                      Obsidian on phone / desktop
```

## Components

### 1. Export Script
**Type:** Python, stdlib only (sqlite3, os, datetime)
**Location:** `profiles/research/scripts/export_holographic_to_md.py`

Key structure:
```python
SHARED_DB = '/opt/data/.hermes/memory_store.db'
OUTDIR = '/opt/data/obsidian-vault/Holographic'

def get_facts():
    # Reads all facts from SHARED_DB, returns list of dicts

def main():
    facts = get_facts()
    # Group by fact category → one .md per category
```

### 2. Sync Wrapper
**Location:** `profiles/research/scripts/sync_holographic_to_obsidian.sh`
**Purpose:** Bash wrapper that runs the Python export and verifies output count.
Falls back from venv python3 to system python3 if venv doesn't exist.

### 3. Cron Job
Created via `cronjob` with these params:
- **Name:** `holographic-to-obsidian-sync`
- **Schedule:** `0 2 * * *` (daily at 02:00)
- **Mode:** `no_agent=true` — script runs without LLM, zero token cost
- **Script:** `sync_holographic_to_obsidian.sh`
- **Workdir:** the profile directory where scripts live

## Why `Holographic/` in the Vault?

The export writes to `/opt/data/obsidian-vault/Holographic/` instead of the vault
root because:

- **Permission-safe**: Created at runtime by the container user (UID 10000),
  inherits 777 from vault root. No UID 1000 permission conflicts.
- **Synced normally**: Syncthing treats it like any other vault subdirectory.
- **Read-only after export**: The source of truth is the SQLite DB — vault notes
  are a derived archive.

## After Memory Consolidation

When the memory DB path changes (e.g. after merging two profiles' stores):

1. Update `SHARED_DB` in the export script to the new path
2. Run the sync script to verify it works: `bash sync_holographic_to_obsidian.sh`
3. Check the generated files have the correct fact count
4. The exported vault notes will show the new fact count on the next cron run

## Pitfalls

- **Hardcoded date strings** in the export script — always use `date.today()`
  instead of literal dates. Grep for `202[0-9]-` in the script to find any.
- **Vault path changes** — update `OUTDIR` if the vault moves
- **Syncthing latency** — about 60s delay before phone sees the new notes
- **no_agent cron with empty output**: if the script produces no stdout,
  nothing is delivered to the user — the job runs silently
- **no_agent cron delivery**: Result goes to the origin conversation; update
  `deliver` if you want it sent elsewhere
- **MOC drift**: When adding a new exported category, update the MOC template
  inside the export script so the index file stays current
