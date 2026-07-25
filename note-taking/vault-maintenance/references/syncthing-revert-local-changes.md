# Syncthing "REVERT LOCAL CHANGES" — Diagnosis & Fix

## When This Applies

Persistent `REVERT LOCAL CHANGES` alerts on a mobile Syncthing client connected to an rpi4-hosted Obsidian vault, where Hermes writes files inside a Docker container (UID 10000) and Syncthing runs on the host (UID 1000).

## Diagnosis Checklist

### 1. Identify folder mode

Check Syncthing config to see if the rpi4 folder is `sendonly`:

```bash
cat ~/.local/state/syncthing/config.xml | grep -A5 'folder id='
```

If `type="sendonly"`, the phone cannot push changes back — every local edit on the phone creates a "pending revert" conflict.

### 2. Find the conflicting files

The phone's Syncthing UI shows which file is triggering the alert. The most common culprits are `.obsidian/workspace-mobile.json` and `.obsidian/workspace.json`.

### 3. Check for existing `.stignore`

```bash
ls -la /path/to/vault/.stignore
```

### 4. Check `.stignore` ownership (the hidden trap)

```bash
stat -c '%A %U(%u) %G(%g)' /path/to/vault/.stignore
```

**If owner is NOT Syncthing's UID (typically 1000), the `.stignore` is effectively a no-op.**  
Syncthing silently skips `.stignore` files it doesn't own — no error, no warning.

### 5. Check for `.stfolder.removed-*` dirs

These are abandoned folder markers from prior re-initializations:

```bash
find /path/to/vault/ -name '.stfolder*' -type d
```

If multiple exist, Syncthing may be confused about which is the active marker (but this is less common as a cause of REVERT LOCAL CHANGES).

## Fix Sequence

### Step A — rpi4 side (Hermes can do this)

Write `.stignore`:

```
.obsidian/workspace.json
.obsidian/workspace-mobile.json
.obsidian/cache/
```

Then **flag ownership** — Hermes cannot `chown` to UID 1000 from inside the container.  
Write the file and instruct the user: `sudo chown 1000:1000 /path/to/vault/.stignore`

### Step B — Phone side (user must do this)

Open Syncthing app -> tap the folder -> tap `...` -> Edit -> scroll to Ignore Patterns -> paste:

```
.obsidian/workspace.json
.obsidian/workspace-mobile.json
.obsidian/cache/
```

This works immediately regardless of rpi4 `.stignore` ownership.

## Verification

After applying the fix:

1. Obsidian on phone changes workspace-mobile.json -> Syncthing ignores it
2. No more "REVERT LOCAL CHANGES" alerts
3. All other files (notes in `Hermes/`, `我的筆記/`, `Holographic/`) still sync normally

## Architectural Note

| Component | UID | Can write .stignore? | Notes |
|-----------|-----|---------------------|-------|
| Hermes (this container) | 10000 | Yes (file) | Cannot `chown` to 1000 |
| Syncthing daemon (host) | 1000 | Reads only | Skips .stignore not owned by 1000 |
| Phone Syncthing app | N/A | Reads ignore patterns | Also needs its own ignore config |
