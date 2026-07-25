# Vault Audit Quick-Reference

Shell commands used during the 2026-07-08 vault audit. Run these in order for a complete vault triage.

## 1. Inventory

```bash
# File count, dir sizes, structure
find /opt/data/obsidian-vault -not -path '*/\\..*' -type f | wc -l
du -sh /opt/data/obsidian-vault/*/
find /opt/data/obsidian-vault -not -path '*/\\..*' -maxdepth 1 -type d | sort
```

## 2. Cache & Tool Spillover

```bash
du -sh /opt/data/obsidian-vault/.cache/
ls -la /opt/data/obsidian-vault/.local/
```

## 3. Syncthing Remnants

```bash
find /opt/data/obsidian-vault -maxdepth 1 -name '.stfolder*' -type d
du -sh /opt/data/obsidian-vault/.stversions/
find /opt/data/obsidian-vault/.stversions/ -type f
```

## 4. Cross-Directory Duplicates

```bash
for f in $(find /opt/data/obsidian-vault -not -path '*/\\..*' -name '*.md' -exec basename {} \\; | sort -u); do
  count=$(find /opt/data/obsidian-vault -not -path '*/\\..*' -name "$f" | wc -l)
  [ "$count" -gt 1 ] && echo "DUPLICATE ($count): $f" && \
    find /opt/data/obsidian-vault -not -path '*/\\..*' -name "$f"
done
```

## 5. MOC Wikilink Integrity

```bash
# Extract links
grep -oP '\\[\\[[^\\]]+\\]\\]' /opt/data/obsidian-vault/首頁\\ MOC.md | tr -d '[]'
# Verify each resolves
for link in $(grep -oP '\\[\\[[^\\]]+\\]\\]' /opt/data/obsidian-vault/首頁\\ MOC.md | tr -d '[]'); do
  found=$(find /opt/data/obsidian-vault -not -path '*/\\..*' -name "${link}.md" 2>/dev/null | head -1)
  [ -z "$found" ] && echo "BROKEN: [[${link}]]"
done
```

## 6. Hermes/ Skills Overlap

```bash
ls /opt/data/obsidian-vault/Hermes/新技能/
# Check frontmatter for skill_name: or name: fields
grep -l 'skill_name:\\|^name:' /opt/data/obsidian-vault/Hermes/新技能/*.md
```

## 7. Duplicate Resolution

```bash
# Compare timestamps
stat -c '%y' /opt/data/obsidian-vault/Hermes/設定/主人偏好.md
stat -c '%y' /opt/data/obsidian-vault/Holographic/主人偏好.md
# Compare content
diff /opt/data/obsidian-vault/Hermes/設定/主人偏好.md /opt/data/obsidian-vault/Holographic/主人偏好.md
```

## 8. Holographic → Root Directory Merge

When `Holographic/<dir>/` duplicates a root-level directory:

```bash
# Check filename collisions first
diff <(find /opt/data/obsidian-vault/Holographic/<dir> -type f -exec basename {} \\;) \
     <(find /opt/data/obsidian-vault/<dir> -type f -exec basename {} \\;)

# If clear, move files and clean up
mv /opt/data/obsidian-vault/Holographic/<dir>/<subdir>/* /opt/data/obsidian-vault/<dir>/<subdir>/
rmdir /opt/data/obsidian-vault/Holographic/<dir>/<subdir>
rmdir /opt/data/obsidian-vault/Holographic/<dir>

# Fix permissions
chmod -R a+rX /opt/data/obsidian-vault/<dir>/<subdir>/
```

## 9. Final Verification (Healthy Baseline)

```bash
# Total file count (expect ~29 after cleanup)
find /opt/data/obsidian-vault -not -path '*/\\..*' -type f | wc -l
# Total size (expect <500 KB)
du -sh /opt/data/obsidian-vault/
# Root .md files only (expect 0-2)
find /opt/data/obsidian-vault -maxdepth 1 -name '*.md' | sort
# No leftover cache
ls -d /opt/data/obsidian-vault/.cache/ 2>/dev/null && echo "STILL PRESENT" || echo "absent"
# No Syncthing remnants beyond active .stfolder
find /opt/data/obsidian-vault -maxdepth 1 -name '.stfolder*' -type d
```

## Cleanup Commands

```bash
# Cache (biggest win)
rm -rf /opt/data/obsidian-vault/.cache/

# Syncthing remnants
rm -rf /opt/data/obsidian-vault/.stfolder.removed-*/
rm -rf /opt/data/obsidian-vault/.stversions/
rm -f /opt/data/obsidian-vault/.local/bin/coder

# Hermes stale skill/ memory copies (ask user first!)
# rm -rf /opt/data/obsidian-vault/Hermes/新技能
# rm -rf /opt/data/obsidian-vault/Hermes/記憶庫

# Fix permissions after any write
chmod -R a+rX /opt/data/obsidian-vault/
```
