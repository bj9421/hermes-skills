# UID Mismatch Debugging — Cross-Container File Access

## Symptom
- Syncthing shows "Local Additions" or "REVERT LOCAL CHANGES"
- New files created in one container don't appear in another
- File permissions show different UID/GID than expected
- Container logs show permission denied errors

## Root Cause
Multiple containers share the same bind-mounted directory but run under different UIDs. The lower-UID container cannot read/write files created by the higher-UID container.

## Debugging Steps

### 1. Check container PUID/PGID settings
```bash
# In Portainer: Container → Configuration → Environment Variables
# Look for PUID and PGID values
```

### 2. Check file ownership in the shared directory
```bash
# On the host (NAS), check actual file ownership
ls -la /path/to/shared/directory/
stat -c '%U:%G %a' /path/to/shared/directory/file
```

### 3. Check directory traversal permissions
```bash
# Even with matching UIDs, directory permissions matter
ls -ld /path/to/shared/directory/
# If mode is 700, only owner can traverse (enter) the directory
```

### 4. Verify the bind mount target exists on host
```bash
# Check if the host path actually exists
ls -la /home/hermes_data/obsidian-vault/
# If it doesn't exist, the container sees an empty directory
```

### 5. Compare UIDs across containers
```bash
# Hermes container UID
id hermes  # e.g., uid=10000(hermes) gid=10000(hermes)

# Syncthing container PUID (from env vars)
# PUID=1000, PGID=1000 (default for linuxserver.io images)
```

## Resolution

### Option A: Match Syncthing PUID to Hermes UID
Change Syncthing container PUID/PGID from 1000 → 10000 in Portainer.

### Option B: Match Hermes PUID to Syncthing UID
Change Hermes container PUID/PGID from 10000 → 1000.

### Option C: Use shared group + setgid
Create a shared group, add both containers' UIDs, set group ownership on shared directory.

## Prevention

- **Standardize PUID/PGID:** All containers sharing bind mounts should use the same PUID/PGID
- **Set umask 0022:** In containers that create files, so new files are world-readable
- **Verify after changes:** After modifying PUID/PGID, create a test file and confirm it's readable by other containers

## Reference: Common PUID Values
| Value | Meaning |
|-------|---------|
| 0 | root (not recommended) |
| 1000 | Default first user on many Linux distros |
| 10000 | Common Docker container user UID |
| 999 | Service accounts (nginx, postgres, etc.) |

## 2026-07-09 Case Study: RPi4 Docker UID Mismatch

**Scenario:** Syncthing container (PUID=1000) couldn't read files created by Hermes container (PUID=10000).

**Symptom:** Mobile Syncthing showed "REVERT LOCAL CHANGES" for 3 days. Test files didn't appear.

**Debug:**
1. `id hermes` → uid=10000(hermes) gid=10000(hermes)
2. Syncthing container env → PUID=1000, PGID=1000
3. Files created with mode 600 → unreadable by UID 1000

**Fix:** Changed Syncthing PUID/PGID to 10000 in Portainer.

**Lesson:** Always verify PUID/PGID match when multiple containers share bind mounts. The `docker-port-mapping-troubleshooting` skill now includes this as a pitfall.