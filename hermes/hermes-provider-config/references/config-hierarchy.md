# Hermes Config File Hierarchy (Profile Mode)

When Hermes runs under a profile (the common case in this RPi4 Docker deployment), **three config files can exist but only one is actually read at runtime**. Confusing them caused the vision 401 in session 2026-07-13.

## The Three Files

| Priority | File | `hermes config path` | When it matters |
|----------|------|---------------------|-----------------|
| **1 (active)** | `/opt/data/config.yaml` | ✅ Returns this path | **This is what Hermes reads at runtime.** If minimal/cleaned, settings from other files are invisible. |
| **2 (profile)** | `/opt/data/profiles/<name>/config.yaml` | ❌ Not returned | Full config with all providers, auxiliary settings, etc. Only used when `--profile` is explicitly set and the profile is active. |
| **3 (legacy)** | `/opt/data/.hermes/config.yaml` | ❌ Not returned | Stale copy. Contains `custom_providers`, memory config, etc. but is NOT loaded at runtime. |

## How Settings Get Orphaned

The profile `config.yaml` (`/opt/data/profiles/default/config.yaml`) can have settings that **look correct** (e.g., `auxiliary.vision` with provider, model, base_url, api_key) but if the **active** config (`/opt/data/config.yaml`) is a minimal/cleaned version that lacks those settings, Hermes can't see them.

**Real example (session 2026-07-13):**

```
/opt/data/config.yaml              → 41 lines, NO auxiliary.vision (← ACTIVE, what Hermes reads)
/opt/data/profiles/default/config.yaml → 709 lines, HAS auxiliary.vision with NVIDIA config (← NOT read)
```

Result: `vision_analyze` → HTTP 401 `Missing Authentication Header` because runtime Hermes sees no vision config.

## How to Resolve

### Safe fix (recommended)

Use `hermes config set` — it writes to the ACTIVE config (`/opt/data/config.yaml`):

```bash
source /opt/data/.env
hermes config set auxiliary.vision.provider nvidia
hermes config set auxiliary.vision.model "meta/llama-3.2-90b-vision-instruct"
hermes config set auxiliary.vision.base_url "https://integrate.api.nvidia.com/v1"
hermes config set auxiliary.vision.api_key "$NVIDIA_API_KEY"
hermes config set auxiliary.vision.timeout 120
```

This is always safe because `hermes config path` shows the active config.

### Diagnostic: Check which config file has the setting

```bash
for f in /opt/data/config.yaml /opt/data/profiles/default/config.yaml /opt/data/.hermes/config.yaml; do
  [ -f "$f" ] && echo "=== $f ===" && grep -A3 "auxiliary.vision\|vision:" "$f" | head -5
done
echo "---"
echo "Active config path: $(/opt/hermes/bin/hermes config path 2>/dev/null)"
```

### Sync fix (when profile config has the real settings)

If the profile config has the right settings but the active config doesn't, the root cause is usually that the active config was overwritten/reduced. Don't try to copy the profile config — use `hermes config set` to write each key, or compare the two files and merge manually.

## Key Principle

**`hermes config path` is truth.** Always check it first before editing. If you edit a file that `hermes config path` does NOT return, the changes are invisible at runtime.
