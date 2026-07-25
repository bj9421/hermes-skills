---
name: obsidian-vault-cleanup
description: Systematic process for deduplicating, merging, and cleaning up Obsidian vault files — MOC consolidation, orphan removal, duplicate detection.
---

# Obsidian Vault Cleanup

Use when the user asks to clean up, deduplicate, merge, or organize their Obsidian vault. Covers MOC merging, duplicate note removal, and structural audits.

## Prerequisites

Resolve the vault path first. Convention: `OBSIDIAN_VAULT_PATH` env var → `/opt/data/obsidian-vault`. Never pass unresolved shell variables to file tools.

## MOC Consolidation

When two MOC files exist (e.g. `首頁 MOC.md` and `Holographic/MOC.md`):

1. **Compare timestamps** — `stat -c '%y'` both files to determine which is newer
2. **Compare content** — `diff` to see what changed
3. **Merge into the canonical location** — usually the root-level MOC (`首頁 MOC.md`)
   - Keep the root file's structure and sections
   - Inject newer content (updated dates, fact counts, new entries)
   - Preserve all sections from BOTH files (don't lose unique content)
4. **Delete the redundant copy** — remove the Holographic/ or orphan version

**Rule:** Always merge INTO the user-facing MOC, not the other way around. The root-level MOC is the navigation hub.

## Duplicate Detection Workflow

1. **Find candidates** — search for same basenames across directories:
   ```bash
   for f in $(find VAULT_ROOT -name '*.md' -exec basename {} \; | sort | uniq -d); do
     echo "Duplicate: $f"
     find VAULT_ROOT -name "$f"
   done
   ```

2. **Compare** — `diff -q` both copies, then `stat -c '%y'` for timestamps

3. **Resolution rules:**
   | Scenario | Action |
   |----------|--------|
   | Same content, one in Holographic/ | Delete non-Holographic copy |
   | Test/temporary files (e.g. "GitHub同步測試") | Delete both copies |
   | Different content, different dirs | Ask user before deleting |
   | Root vs Holographic with same name | Keep root (user-facing), delete Holographic |

## Orphan File Identification

Files that are clearly test artifacts or temporary notes:
- Names containing "測試", "test", "temp"
- Content with "待填寫" or empty sections
- Single-purpose verification notes with no ongoing value

These can be deleted without asking if the content is clearly ephemeral.

## Post-Cleanup Verification

After any deletion:
1. Confirm file count decreased as expected
2. Check MOC wikilinks still resolve (no broken links)
3. Run `chmod -R a+rX` on vault to fix Syncthing visibility

## Pitfalls

1. **Never delete user-written content** — `我的筆記/` files are sacred. Only clean Hermes-generated or test files.
2. **Holographic/ is cron-exported** — files there can be regenerated. Prefer keeping root-level user-facing copies.
3. **Check wikilinks before deleting** — a deleted note may break MOC navigation.
4. **Permissions** — after any vault write, always `chmod -R a+rX` so Syncthing can sync (UID 10000 vs host UID 1000 issue).
