---
name: vault-maintenance
description: Clean up duplicate files, resolve Syncthing conflicts, and manage vault structure in an Obsidian vault synced between Hermes (RPi) and user devices.
platforms: [linux]
related_skills: [obsidian, youtube-note-pipeline]
---

# Vault Maintenance

> For Syncthing-synced Obsidian vaults where both Hermes and the user write files.

## When to Use

- User asks about duplicate files or "整理 vault"
- Syncthing shows `REVERT LOCAL CHANGES` or conflict markers
- Vault has accumulated orphan/root `.md` files that duplicate `Holographic/` content
- After Hermes has been writing notes to the vault for a while and cleanup is needed

## Vault Directory Roles (This User's Setup)

| Directory | Source | Purpose |
|-----------|--------|---------|
| `Hermes/` | Hermes agent writings | Skills, settings, internal memory docs. `新技能/` subdir may overlap registered skills — cross-reference before assuming unique. |
| `Holographic/` | Hermes cron export | Memory DB → Markdown export for human reading |
| `我的筆記/` | User / yt2md pipeline | Personal notes, research, learning |
| Root `.md` files | Mixed | May be old/orphan copies of `Holographic/` files |
| `.stfolder` / `.stversions` | Syncthing internal | Ignore — do not touch |

**Key insight:** `Holographic/` is a **memory export destination** — files there are refreshed periodically by cron. They are often the **newer** copies compared to root-level orphans.

## Export Pipeline Verification

> The export pipeline: Holographic Memory Store DB → `export_holographic_to_md.py` → `Holographic/*.md` files. Entry point: `/opt/data/sync_holographic_to_obsidian.sh`. Export script: `/opt/data/export_holographic_to_md.py`.

### Fact-Count Verification (Source-of-Truth Check)

The pre-run script reports fact counts from the memory DB, but **the DB can be cleared/rotated between the pre-run and the agent execution**. Always verify by reading the DB directly:

```bash
/opt/hermes/.venv/bin/python3 -c "
import sys
sys.path.insert(0, '/opt/hermes/plugins/memory/holographic')
from store import MemoryStore
db = '/opt/data/profiles/research/home/.hermes/memory_store.db'
store = MemoryStore(db_path=db)
facts = store.list_facts(limit=500)
print(f'Total facts: {len(facts)}')
cats = {}
for f in facts:
    cat = f.get('category', 'general')
    cats.setdefault(cat, []).append(f)
for cat, items in sorted(cats.items()):
    print(f'  {cat}: {len(items)} facts')
store.close()
"
```

**Pattern (observed 2026-07-15):** Pre-run reports 147 facts; agent run minutes later finds 0 facts. The Holographic Memory Store was cleared in between — this is memory rotation, not a script defect.

### Handling the Empty-DB Edge Case

When the DB has 0 facts, the export script **gracefully produces skeleton files** (headers/frontmatter only, no fact content). The files are smaller but still valid Markdown:

| File | With 147 facts | Empty DB (skeleton) |
|------|---------------|-------------------|
| 主人偏好.md | ~1134 bytes | ~152 bytes |
| 環境設定.md | ~2109 bytes | ~404 bytes |
| Cron排程.md | ~2313 bytes | ~486 bytes |
| 台股資料.md | ~6679 bytes | ~1129 bytes (static content survives) |

Skeleton files still have valid YAML frontmatter and section headers — they just lack fact-level content.

### MOC State Reporting

When the source DB is empty, the MOC should **explicitly note the stale state** so the user doesn't trust skeleton files as current data:

```yaml
> ⚠️ Holographic DB 目前無 facts（已清空/輪替），檔案內容為先前匯出快照
> 上次成功同步：YYYY-MM-DD HH:MM — N facts
```

Include both the warning AND the last-known-good fact count so the user has a reference point. The last-known-good count can be taken from the pre-run script's stdout (which runs before the agent).

### Cross-Reference Cheat

| Source | What it tells you | Caveat |
|--------|------------------|--------|
| Pre-run stdout (from cronjob prefix) | Fact count at start of cron cycle | May be stale by time agent runs |
| Direct DB read (`list_facts()`) | Current DB state | Always authoritative |
| File sizes in Holographic/ | Whether export was full or skeleton | 152-byte 主人偏好.md = empty DB |
| MOC.md header | Last-known-good count | Falls behind when DB rotates |

**Action rule:** If pre-run reports N facts but Direct DB read reports 0, DON'T trust the pre-run count. Update MOC with a warning about the rotation and note the last-known-good count from the previous successful sync (visible in the pre-run output).

## Duplicate Detection

### Step 1: Find potential duplicates

Use `search_files` or `find` to look for files with identical basenames across root/ and Holographic/:

```bash
# Check root-level .md vs Holographic/ copies
for f in MOC 主人偏好 台股資料 環境設定 記憶庫架構 Cron排程; do
  root="VAULT_ROOT/${f}.md"
  holo="VAULT_ROOT/Holographic/${f}.md"
  [ -f "$root" ] && [ -f "$holo" ] && echo "Duplicate: ${f}.md"
done

# Check for duplicate YouTube notes
find VAULT_ROOT -name '*.md' | sed 's|.*/||' | sort | uniq -d
```

### Step 2: Compare timestamps (NEVER assume)

```bash
stat -c '%y' VAULT_ROOT/MOC.md
stat -c '%y' VAULT_ROOT/Holographic/MOC.md
```

**Rules:**
- Holographic/ files are cron-exported from memory DB → usually newer → keep these
- Root-level `.md` files with matching names are often old orphans → can delete
- `Hermes/` is generally unique, but check `新技能/` subdir against registered skills — stale drafts may exist there
- YouTube/ within Holographic duplicates `我的筆記/yt2md/` — the yt2md version is canonical

### Step 3: Check content before removing

```bash
diff -q VAULT_ROOT/file1.md VAULT_ROOT/Holographic/file1.md
# If different, see what changed:
diff VAULT_ROOT/file1.md VAULT_ROOT/Holographic/file1.md | head -20
```

### Step 4: Clean up

```bash
# Delete orphan root duplicates (Holographic keeps the authoritative copy)
rm VAULT_ROOT/old-orphan.md

# Delete YouTube/ from Holographic (content exists in 我的筆記/yt2md/)
rm -rf VAULT_ROOT/Holographic/YouTube/

# Delete test artifacts
rm VAULT_ROOT/Holographic/syncthing-test.md

# Keep duplicate versions of yt2md output only when they differ
# (e.g., whisper-tiny without timestamps vs whisper-small with timestamps)
# Ask user which they prefer before deleting
```

## Syncthing Conflict Handling

**`REVERT LOCAL CHANGES`** in the mobile Syncthing app means:
- The RPi (server) has a newer version of the file
- The mobile device has local edits that conflict
- No `.sync-conflict-*` file is created until the user explicitly resolves

**DO NOT dismiss as "safe to ignore":** The user finds the persistent nag disruptive. Always pursue a permanent fix.

### Root Cause: Obsidian workspace files

The #1 cause of recurring `REVERT LOCAL CHANGES` on mobile:

| File | Why it changes |
|------|---------------|
| `.obsidian/workspace-mobile.json` | Mobile Obsidian rewrites this on every app open/close, note switch, or layout change |
| `.obsidian/workspace.json` | Desktop Obsidian does the same |
| `.obsidian/cache/` | Various metadata caches change per-device |

Each device has its own workspace layout — these files MUST NOT be synced. Syncthing sees phone's version != rpi4's version (in sendonly mode, rpi4's version is authoritative) and flags phone's as "local change to revert".

### The Fix: `.stignore`

Create a `.stignore` in the vault root to exclude per-device workspace files:

```
// 排除各裝置專屬的 Obsidian workspace 設定檔
// 每台裝置各自管理自己的視窗佈局，不需同步
.obsidian/workspace.json
.obsidian/workspace-mobile.json
.obsidian/cache/
```

**CRITICAL — .stignore ownership must match Syncthing's UID:**
- Syncthing **silently skips** `.stignore` files not owned by its own UID
- Even with `644` permissions (world-readable), if UID != Syncthing's UID -> ignore rules not applied
- rpi4 Syncthing typically runs as UID 1000; Hermes container writes as UID 10000
- If Hermes writes `.stignore`, UID mismatch causes silent failure
- **Fix on the host:** `sudo chown 1000:1000 /path/to/vault/.stignore`

**Dual-approach strategy (especially for sendonly folders):**
1. **rpi4 side** (Hermes can do): write the `.stignore` file + remind user to `chown` on host
2. **Phone side** (user must do in Syncthing app): tap folder -> ... -> Edit -> Ignore Patterns -> paste the same rules
   - Phone-side ignore works immediately regardless of rpi4 `.stignore` ownership
   - This is the fallback when Hermes can't `chown` the file

**To resolve on mobile (one-off):**
- **"Use Device Version"** — keep the phone's version, push to RPi
- **"REVERT LOCAL CHANGES"** — discard phone edits, pull RPi version

## Memory Impact

Deleting **any** `.md` files from the vault does NOT affect Hermes persistent memory:

| Vault file | Hermes counterpart | Impact when deleted |
|:-----------|:-------------------|:-------------------|
| `Holographic/*.md` | `memory_store.db` (SQLite) | ❌ None — cron re-exports from DB next run |
| `Hermes/新技能/*.md` | `skills/<name>/SKILL.md` | ❌ None — skill is loaded from `/opt/data/skills/` |
| `Hermes/記憶庫/*.md` | `memory_store.db` | ❌ None — static notes, not read by Hermes agent |
| `Hermes/設定/*.md` | `hermes config` + `.env` | ❌ None — static reference copy |

**Real memory architecture:**
```
memory_store.db ────→ injected into every session as MEMORY block
      │
      ├── cron export ──→ Holographic/*.md (human-readable snapshot)
      │
skills/<name>/SKILL.md ──→ loaded on session start as procedural knowledge
```

The vault `.md` files are **read-only snapshots for human browsing through Syncthing**. The agent never reads them. Deleting them frees space but loses nothing functional — the next cron export regenerates Holographic/ content, and registered skills remain in `/opt/data/skills/`.

**Exception:** `我的筆記/` files are user-written content — always ask before deleting.

## Preventing Syncthing-Invisible Files

**Problem:** `write_file` creates files with `-rw-------` (600) permissions owned by hermes (UID 10000). Syncthing (running as host UID 1000) silently skips these — no error, no sync. The user sees "沒有檔案" even though the file exists on disk.

**Fix — always apply after every vault write:**

```bash
chmod -R a+rX /path/to/obsidian-vault/target/
```

This flattens permissions to `-rw-r--r--` (644) for files and `drwxr-xr-x` (755) for directories. Verify with:

```bash
stat -c '%A' /path/to/note.md
# Expected: -rw-r--r--
```

The pattern is triggered whenever `write_file` targets a Syncthing-synced path where Hermes UID ≠ host UID. Apply even for brand-new subdirectories (which inherit hermes ownership).

## Comprehensive Vault Audit (Triage)

When the user asks to "整理 vault" or you're doing a systematic review, run this full audit before touching anything.

### Step 1: Map the territory

```bash
# Total file count
find VAULT_ROOT -not -path '*/\..*' -type f | wc -l

# Directory inventory + sizes
du -sh VAULT_ROOT/*/ 2>/dev/null | sort -rh

# Every top-level dir
find VAULT_ROOT -not -path '*/\..*' -maxdepth 1 -type d | sort
```

### Step 2: Check for cache/tool spillover

```bash
# uv pip cache leaking into vault (common — Hermes ran uv here at some point)
du -sh VAULT_ROOT/.cache/ 2>/dev/null

# Other .local artifacts (shell scripts, old profile switchers)
ls -la VAULT_ROOT/.local/ 2>/dev/null
```

**Pattern:** `.cache/uv/` inside a vault is always accidental — uv stores pip downloads there. These are not Obsidian files and can be safely deleted.

### Step 3: Check Syncthing remnants

```bash
# stale .stfolder.removed-* dirs (Syncthing folder was removed and recreated)
find VAULT_ROOT -maxdepth 1 -name '.stfolder*' -type d

# old versioned backups (if months old, safe to delete)
du -sh VAULT_ROOT/.stversions/ 2>/dev/null
find VAULT_ROOT/.stversions/ -type f
```

**Pattern:** `.stfolder.removed-YYYYMMDD-HHMMSS/` are empty marker dirs from folder re-creation — safe to delete. `.stversions/` with conflict backups older than 2 weeks are safe to prune.

### Step 4: Detect cross-directory duplicates

```bash
# Find any basename that appears in multiple non-hidden directories
for f in $(find VAULT_ROOT -not -path '*/\..*' -name '*.md' -exec basename {} \; | sort -u); do
  count=$(find VAULT_ROOT -not -path '*/\..*' -name "$f" | wc -l)
  if [ "$count" -gt 1 ]; then
    echo "DUPLICATE ($count): $f"
    find VAULT_ROOT -not -path '*/\..*' -name "$f"
  fi
done
```

For each duplicate:
1. `stat -c '%y'` both copies → who is newer
2. `diff -q` both copies → are they identical
3. If different → `diff` to see what changed

**Resolution rules:**
| Scenario | Action |
|----------|--------|
| Same content, one in `Holographic/` | Delete the non-Holographic copy |
| Same content, one in user-written dir | Keep whichever has better timestamps |
| Different content, different dirs | Ask user; likely both have unique value |
| `Hermes/設定/` vs `Holographic/` | Holographic is cron-exported → newer → authoritative |

### Step 5: Check MOC wikilink integrity

If a `MOC.md` or `首頁 MOC.md` exists, verify its `[[wikilinks]]` resolve:

```bash
# Extract all [[links]] from the MOC
grep -oP '\[\[[^\]]+\]\]' VAULT_ROOT/MOC.md 2>/dev/null || grep -oP '\[\[[^\]]+\]\]' VAULT_ROOT/首頁\ MOC.md 2>/dev/null

# For each link, check it exists somewhere in the vault
for link in $(grep -oP '\[\[[^\]]+\]\]' VAULT_ROOT/首頁\ MOC.md 2>/dev/null | tr -d '[]'); do
  found=$(find VAULT_ROOT -not -path '*/\..*' -name "${link}.md" 2>/dev/null | head -1)
  if [ -z "$found" ]; then echo "BROKEN: [[${link}]] — no file found"; fi
done
```

Broken wikilinks are stale navigation entries — the target note was deleted or renamed. Either remove the link or restore the note.

### Step 6: Check Hermes/ skills section against registered skills

```bash
# List all files in Hermes/新技能/
ls VAULT_ROOT/Hermes/新技能/

# Cross-reference: if a note has YAML frontmatter with `skill_name:` or `name:`
# that matches a registered Hermes skill (from skills_list), the note is likely
# an outdated copy — the skill itself is the source of truth.
```

**Pattern:** Notes in `Hermes/新技能/` that map to registered skills are historical drafts. Delete when the skill is mature. Keep only notes that contain *supplementary* information not in the skill definition.

### Step 7: Present a decision table

Summarize findings for the user so they can confirm before executing:

| # | Item | Size | Verdict | Action |
|---|------|------|---------|--------|
| 1 | `.cache/uv/` | 153 MB | 🗑️ Delete | `rm -rf` |
| 2 | `.stfolder.removed-*` | 8 KB | 🗑️ Delete | `rmdir` |
| 3 | `Hermes/新技能/AI選股.md` | 2.6 KB | 🤔 Stale? | duplicates registered skill — ask user |

## Holographic Directory Merge

When `Holographic/` contains a subdirectory that duplicates a root-level directory (e.g. `Holographic/我的筆記/` duplicates `我的筆記/`), the Holographic copy is a cron-exported snapshot that should be merged into the authoritative root directory.

**Pattern:** `Holographic/<dir>/<subdir>/<file>` → `/<dir>/<subdir>/<file>`

### Procedure

```bash
VAULT="/opt/data/obsidian-vault"

# 1. Check for filename collisions
diff <(find "$VAULT/Holographic/<dir>" -type f -exec basename {} \;) \
     <(find "$VAULT/<dir>" -type f -exec basename {} \;)

# 2. If no collisions, move files and clean empty dirs
mv "$VAULT/Holographic/<dir>/<subdir>/"* "$VAULT/<dir>/<subdir>/"
rmdir "$VAULT/Holographic/<dir>/<subdir>" 2>/dev/null
rmdir "$VAULT/Holographic/<dir>" 2>/dev/null

# 3. Fix permissions for Syncthing
chmod -R a+rX "$VAULT/<dir>/<subdir>/"
```

### Resolution rules

| Situation | Action |
|-----------|--------|
| No filename conflicts | Move files directly, clean empty Holographic dirs |
| Filename conflict, same content (`diff -q`) | Keep whichever is newer; delete the other |
| Filename conflict, different content | Ask user — Holographic copy is cron-exported (can re-export), root copy is user-edited |
| `Holographic/我的筆記/` → `我的筆記/` | Always safe to merge — `我的筆記/` is the canonical user notes directory |

### Verification

```bash
# Confirm Holographic/ no longer has the merged subdirectory
ls -la "$VAULT/Holographic/"
# Confirm files landed in correct location
ls -la "$VAULT/<dir>/<subdir>/"
```

## Healthy Vault Baseline

After a full cleanup, a well-maintained vault looks like:

| Metric | Clean reference |
|--------|:---------------:|
| Total size | **< 500 KB** |
| Total `.md` files | **~25–35** |
| Hidden + system dirs | `.obsidian/`, `.stfolder/`, `.stignore` only |
| User content dirs | `我的筆記/`, `Hermes/設定/`, `Holographic/` |
| Root `.md` files | Only MOC / 首頁 MOC (0–2 files) |
| `.cache/` | ❌ absent |
| `.stfolder.removed-*` | ❌ absent |
| `.stversions/` | ❌ absent or < 2-week-old content only |

**Target state (this system):** after full cleanup, expect ~29 files and ~312 KB.

## Verification After Cleanup

```bash
# Confirm no accidental deletions of unique content
find VAULT_ROOT/ -not -path '*/\\\\.*' -type f | wc -l
# Should match pre-cleanup count minus intentional removals

# Check root level
find VAULT_ROOT/ -maxdepth 1 -name '*.md' | sort
# Only intentional root files remain

# Confirm Syncthing still shows green 100%
# (use browser or Syncthing API if accessible)
```

## Pitfalls

1. **Don't assume root is authoritative** — Holographic/ exports are cron-refreshed, often newer
2. **Always `diff -q` before deleting** — same basename != same content; identical size != identical file
3. **Don't delete `.stfolder`** — Syncthing internal state. `.stfolder.removed-*` markers and 2+ week old `.stversions/` content CAN be cleaned.
4. **Hermes/新技能/ CAN overlap with registered skills** — cross-reference before assuming uniqueness. A note with a `skill_name:` frontmatter matching a registered Hermes skill is likely a stale draft.
5. **Obsidian app locks on mobile**
6. **`.stignore` ownership trumps permissions** — Syncthing silently ignores `.stignore` not owned by its own UID. Even `644` (world-readable) won't help if the owner is wrong. After creating `.stignore`, either `sudo chown` to match Syncthing's UID or configure ignore patterns on the phone side instead. This is the most common reason `.stignore` "doesn't work".
