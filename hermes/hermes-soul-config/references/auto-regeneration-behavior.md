# SOUL.md Auto-Regeneration Discovery (Confirmed — 2026-07-16)

## Observation

After cleaning up stale SOUL.md copies from `/opt/data/` (moving them to archive at 12:05), a new `SOUL.md` containing the **default English Hermes identity** (513 bytes) appeared at `/opt/data/SOUL.md` at **12:06** — one minute later.

**Key facts:**
- Content is exactly the hardcoded `DEFAULT_AGENT_IDENTITY` text from Hermes source
- Different inode from the one moved (new file, not a rename)
- The file kept reappearing across 3+ cleanup attempts
- `.hermes/SOUL.md` (Chinese version) was unchanged throughout

## Confirmed Root Cause

The code path is in `config.py`:

```python
def _ensure_default_soul_md(home: Path) -> None:
    soul_path = home / "SOUL.md"
    if soul_path.exists():
        try:
            existing = soul_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return
        if not is_legacy_template_soul(existing):
            return    # ← Custom content: skip write
    soul_path.write_text(DEFAULT_SOUL_MD, encoding="utf-8")
```

Called from `ensure_hermes_home()` at every startup. **The guard only checks for legacy empty templates — any other missing file gets replaced with the default.**

On a Docker container where the volume mount is quirky:
- Container shell `ls` couldn't list `/home/hermes_data/` (volume mount quirk on RPi4)
- But `read_file` worked on the same path — pointing to a Docker `ls` bug, not actual file absence
- After cleanup (moving the file), `_ensure_default_soul_md` saw it as "missing" and wrote the default

**The confusion was amplified by two SOUL.md files at different paths:**
- `/opt/data/SOUL.md` = auto-generated default (English, 513 bytes)
- `/opt/data/.hermes/SOUL.md` = user's Chinese identity (1955 bytes, not read by Hermes)

## Permanent Fix

Write custom content to the correct path (`$HERMES_HOME/SOUL.md`). The `is_legacy_template_soul` check means custom content is never overwritten.

## Lessons

1. When a file keeps coming back, **read the code that writes it** — don't just keep moving it
2. Docker volume mounts can confuse `ls` — use `read_file` as cross-check
3. Two SOUL.md files at different paths is the classic trap — one is read, one is dead
4. Custom content in SOUL.md is permanent — `_ensure_default_soul_md` only writes for missing/legacy files
