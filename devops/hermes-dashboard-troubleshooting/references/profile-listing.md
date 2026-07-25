# Profile Listing & Visibility

## How the Dashboard Discovers Profiles

The dashboard's `/api/profiles` endpoint calls `profiles_mod.list_profiles()`, which scans:

1. **Default profile**: `$HERMES_HOME` directory (e.g., `/opt/data`)
2. **Named profiles**: `$HERMES_HOME/profiles/` subdirectories

The regex filter for valid profile names: `^[a-z0-9][a-z0-9_-]{0,63}$`

## Key Code Path

```
get_default_hermes_root()  →  $HERMES_HOME (e.g., /opt/data)
_get_profiles_root()       →  $HERMES_HOME/profiles/ (e.g., /opt/data/profiles/)
list_profiles()            →  scan profiles/ dir, filter by _PROFILE_ID_RE
```

## Docker Deployment Note

In Docker, `HERMES_HOME=/opt/data` (mounted volume). Named profiles live under `/opt/data/profiles/<name>/`.

Removing a profile: `rm -rf /opt/data/profiles/<name>` — no need to touch `~/.hermes/profiles/` (that's the native default, not used in Docker).

## Hidden Profiles

The profile switcher only shows profiles with `name != currentProfile`. If only one profile exists, the switcher is hidden entirely.

## Session Notes

- 2026-07-14: Found "ghost" research profile appearing in dashboard despite `~/.hermes/profiles/` being empty. Root cause: profiles live under `/opt/data/profiles/` in Docker, not `~/.hermes/profiles/`.
