---
name: filesystem-cleanup
description: "Technique for auditing, classifying, and safely cleaning up scattered code across filesystem locations."
version: 1.2.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [cleanup, organization, filesystem, cron-audit]
    related_skills: [ha-powers, git-worktrees]
---

# Filesystem Cleanup & Organization

When code is scattered across multiple locations (root, scripts/, overlapping project dirs), use this technique to classify and safely clean up.

## Step 1: Check Cron References

```python
# Check if any file is referenced by cron jobs
import json, os, glob
all_prompts = []
for path in glob.glob('/opt/data/**/cron/jobs.json', recursive=True):
    if os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
            for j in data.get('jobs', []):
                prompt = j.get('prompt', '') or ''
                all_prompts.append((j.get('name',''), prompt))

# For each candidate file:
for fname in ['update_daily.py', 'test_twse_openapi.py', 'render_heatmap.py']:
    refs = [name for name, prompt in all_prompts if fname in prompt]
    if refs:
        print(f"  📌 {fname} ← {', '.join(refs)}")
    else:
        print(f"  ?  {fname} (未引用)")
```

## Step 2: Group by Lifecycle Stage

| Category | Description | Action |
|----------|-------------|--------|
| **Active** | Referenced by cron or currently running | Keep, possibly relocate |
| **Abandoned** | Old versions (v1, v2, v3...) superseded by current | Archive (mv to /opt/data/archive/) |
| **Experimental** | Test files from a single investigation session | Archive (mv to /opt/data/archive/) |
| **Independent** | Standalone tools not in any category | Keep in organized subdir |

## Step 3: mv to Archive (Never Delete)

```bash
# Move suspected-unused files to /opt/data/archive/ (mv only, no rm)
mkdir -p /opt/data/archive/$(date +%F)
mv -v /opt/data/old_project_dir /opt/data/archive/$(date +%F)/
mv -v /opt/data/script.py       /opt/data/archive/$(date +%F)/
```

Archive is the **permanent recycle bin** — not temporary staging. Observe for
several days; the user decides when (or if) to purge. Never `rm`, never `cp + rm`.
`mv` is atomic and trivially reversible.

## Step 4: Archive in Batches (Not Delete)

Group files from the same investigation session (same creation date) and move
them to archive together. Never `rm`:

```bash
# API comparison tests from a session
mkdir -p /opt/data/archive/session-cleanup-$(date +%F)
mv -v test_twse_*.py test_tpex_*.py test_finmind_*.py  /opt/data/archive/session-cleanup-$(date +%F)/
mv -v test_tdcc_*.py compare_*.py final_*.py           /opt/data/archive/session-cleanup-$(date +%F)/
```

## Step 5: Organize Remaining Files

Move active-but-scattered files into logical subdirectories:

```
scripts/
├── stock-update/       ← Daily update scripts
├── stock-tools/        ← TWSE/TPEX utility scripts
├── dashboard/          ← Dashboard rendering scripts
└── (root)              ← Cron wrappers only
```

## Step 6: Update Cron Paths After Moving

**Always** update every cron job that references moved files. Check ALL profiles:

```python
import json, os, glob
for path in glob.glob('/opt/data/**/cron/jobs.json', recursive=True):
    if os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
            for j in data.get('jobs', []):
                old = j.get('prompt', '')
                new = old.replace('/old/path/', '/new/path/')
                if old != new:
                    j['prompt'] = new
        with open(path, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
```

Also check wrapper scripts (`.sh`) that may hardcode paths — update those too.

## Step 7: Verify Post-Move

After moving + updating, grep to catch any remaining references to old paths:

```bash
grep -r "old-path" /opt/data/scripts/ /opt/data/profiles/*/cron/jobs.json 2>/dev/null
```

## Step 8: Update Skills After Path Changes

When you restructure project directories, **skills that reference project paths become stale**. This is the most commonly forgotten step — cron jobs get updated but skills don't, causing future sessions to generate code at wrong locations.

**Always check these skills after moving files:**

| Skill | What to Check |
|-------|--------------|
| `ha-powers` | `docs/specs/`, `docs/plans/`, `<project>/` references |
| `brainstorming` | Spec save path |
| `writing-plans` | Plan save path |
| `subagent-driven-development` | Plan read path |

**Patch pattern:** Replace bare `docs/specs/` / `docs/plans/` with `<project>/docs/specs/` / `<project>/docs/plans/` to reflect that these are relative to the project root, not `/opt/data/`.

**Verify with:**
```bash
grep -rn "docs/specs\|docs/plans" /opt/data/skills/software-development/*/SKILL.md
```

Any match NOT prefixed with `<project>/` needs updating.

## Key Rules

1. **Always check cron references before moving anything.** A file may look unused but be called from a cron prompt by filename.
2. **Always update cron paths after moving.** If you move a file, every cron job and wrapper script referencing it must be updated.
3. **Verify with grep after moving.** Catch stale references before the next cron run fails.
4. **New projects go in `/opt/data/projects/<name>/`.** This is the workspace convention for all new codebases.
5. **Always update skills after restructuring.** Stale skill paths cause future sessions to generate code at wrong locations — worse than stale cron refs because they silently propagate.