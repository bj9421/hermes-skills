---
name: hermes-global-config
category: devops
description: Manage Hermes Agent API keys and provider settings globally across all profiles.
---

# Hermes Global Configuration Management

## Description
Manage Hermes Agent API keys and provider settings globally across all profiles. This skill provides a safe, repeatable workflow to:
- Extract API keys from a source profile (e.g., `research`)
- Propagate keys to global `.env` and other profiles
- Set a custom provider (e.g., Agnes) as the default for the active profile
- Verify configuration without exposing secrets

## When to Use
- You have configured API keys and providers in one profile and want to reuse them in others.
- After a container restart or profile recreation, you need to restore global access to keys.
- You wish to switch the default model/provider (e.g., to a custom endpoint like Agnes or OpenCode Zen) while keeping keys available everywhere.
- You need to audit which keys exist across all profiles and which are missing.

## Prerequisites
- Hermes CLI available (`hermes` in PATH).
- Access to profile directories under `/opt/data/profiles/<name>/`.
- Basic understanding of Hermes config structure (model, providers, .env).

## Key Architecture: config.yaml vs .env

Hermes resolves API keys through two channels that are merged at runtime:

| Channel | Location | Scope | Example |
|---------|----------|-------|---------|
| **config.yaml** `model.api_key` | Per-profile config | Active profile only | Used when `provider: custom` |
| **Environment variable** | Global + per-profile `.env` (merged) | All profiles reading that var | `OPENCODE_ZEN_API_KEY` |

**Resolution order:** An explicit `api_key` in `config.yaml` takes precedence for generic providers. Some provider plugins (e.g., OpenCode Zen, OpenCode Go) *require* a specific env var (`OPENCODE_ZEN_API_KEY`, `OPENCODE_GO_API_KEY`) and do not read the config key — check the provider plugin's `env_vars` tuple to confirm.

**Persistence:** Both `config.yaml` and `.env` files live under the Docker-mounted volume (`/opt/data/`), surviving `docker restart` / `docker stop+start`. Only a volume delete destroys them.

## Workflow

### 0. Pre-flight: Audit Current State

Before propagating keys, check which targets already have them to avoid redundant work:

```bash
# Check .env files for a specific key
for f in /opt/data/.env /opt/data/profiles/*/.env; do
  [ -f "$f" ] && echo "=== $f ===" && grep 'OPENCODE_ZEN_API_KEY' "$f" || echo "(not found)"
done

# Check config.yaml for inline api_key
for f in /opt/data/profiles/*/config.yaml; do
  [ -f "$f" ] && echo "=== $f ===" && sed -n '/^model:/,/^[a-z]/{/api_key/p}' "$f"
done
```

### 1. List Available Profiles
```bash
hermes profile list
```
Identify the source profile containing the desired API keys (e.g., `research`).

### 2. Extract API Keys from Source Profile
Read the source profile's `.env` file (non-commented lines containing `_API_KEY=`):
```bash
grep -v '^#' /opt/data/profiles/<source>/.env | grep '_API_KEY='
```
Example output:
```
NVIDIA_API_KEY=...
OPENROUTER_API_KEY=...
ANYSEARCH_API_KEY=...
OPENCODE_ZEN_API_KEY=...
AGNES_API_KEY=...
```

### 3. Propagate Keys to Target Profiles
For each target profile (or global), append missing keys to its `.env`:
```bash
# NOTE: config.yaml and .env paths vary by system
# Default config: /opt/data/config.yaml (NOT /opt/data/.hermes/config.yaml)
# Research config: /opt/data/profiles/research/config.yaml (NOT /opt/data/.hermes/profiles/research/)
TARGETS=(
  "/opt/data/.env"
  "/opt/data/profiles/default/.env"
  "/opt/data/profiles/research/.env"
)
for target in "${TARGETS[@]}"; do
  # Ensure file exists
  touch "$target"
  # Add each key if not already present
  while IFS= read -r line; do
    grep -qxF "$line" "$target" || echo "$line" >> "$target"
  done < <(grep -v '^#' /opt/data/profiles/<source>/.env | grep '_API_KEY=')
done
```
> **Note:** Direct writes to `/opt/data/.env` may be blocked by Hermes protections; in that case, rely on profile-specific `.env` files (they are merged with global at runtime).

### 4. Comprehensive Audit: Compare All .env Files (Optional)

For a full comparison table across all 4 locations (global + N profiles), use `execute_code`:

```python
from hermes_tools import terminal

paths = {
    "global":   "/opt/data/.env",
    "default":  "/opt/data/profiles/default/.env",
    "coder":    "/opt/data/profiles/coder/.env",
    "research": "/opt/data/profiles/research/.env",
}
# ... (iterate each file, grep '^[A-Z][A-Z_]+=', build table)
```

This produces a side-by-side view:
```
  Key Name                global    default   coder     research
  OPENCODE_ZEN_API_KEY    sk-7...   sk-7...   sk-7...   sk-7...
  AGNES_API_KEY           —         sk-X...   sk-X...   sk-X...
  OPENROUTER_API_KEY      —         sk-o...   sk-o...   sk-o...
```

Each `—` marks a profile missing that key. This is the most reliable way to spot gaps before propagating.

### 5a. Set OpenCode Zen (Built-in Plugin) as Default

OpenCode Zen is a **built-in Hermes provider plugin** — no `custom_providers` registration needed.
It reads the `OPENCODE_ZEN_API_KEY` env var automatically. Set it in every profile's `.env`.

```bash
# For each profile, just set provider + model name
# NOTE: hermes config set CANNOT append to empty lists (e.g., fallback_providers: [])
# Use Python+YAML for list modifications
hermes config set model.default big-pickle
hermes config set model.provider opencode
hermes config set model.api_mode chat_completions
```

No `base_url` or `api_key` in `config.yaml` required — the plugin reads `OPENCODE_ZEN_API_KEY`
from the environment. The `big-pickle` model is their default offering.

**Per-model routing** (handled automatically by the plugin):
| Wire format | Models |
|-------------|--------|
| `anthropic_messages` | Claude-family |
| `codex_responses` | GPT-5 / Codex |
| `chat_completions` | Everything else (big-pickle, GLM, Kimi, MiniMax) |

### 5b. Set a Custom Provider (e.g., Agnes) as Default
Switch to the profile you wish to configure (or stay in current):
```bash
hermes profile use <target-profile>   # optional
```
Then configure the model and provider:
```bash
hermes config set model.default <model-name>   # e.g., agnes-2.0-flash
hermes config set model.provider custom
hermes config set providers.custom.base_url <base-url>   # e.g., https://apihub.agnes-ai.com/v1/chat/completions
hermes config set providers.custom.api_mode chat_completions
```
### 6. Verify Configuration

Check that the settings are active using the correct command:

```bash
# Show active model config (NOT 'hermes config get' — that doesn't exist)
hermes config show | head -10
```

For a custom provider (e.g., Agnes), expect:
```
Model:        {'default': 'agnes-2.0-flash', 'provider': 'custom', ...}
```

For a built-in plugin provider (e.g., OpenCode Zen), expect:
```bash
hermes status | head -15
```
```
Model:        big-pickle
Provider:     OpenCode Zen
```

### 6. Test the Provider (Optional)
Send a simple chat request to confirm the provider works:
```bash
hermes chat "Hello, are you using Agnes?"
```
(Adjust based on your Hermes version; may use `/model set` or direct chat.)

## Pitfalls & Safety Notes
- **Do not edit `/opt/data/.env` directly** if Hermes blocks it; use profile `.env` files instead—they are automatically merged.
- **Never expose API keys in logs or output**; the `grep` commands above only match lines, not values, but avoid printing them to shared terminals.
- **Protected config:** The main `config.yaml` cannot be overwritten by arbitrary writes; always use `hermes config set` to modify it.
- **Profile isolation:** Changes to one profile’s `.env` do not affect others unless you explicitly propagate.
- **Restart not required:** Configuration changes take effect immediately for new chat sessions.
- **Config hierarchy:** `/opt/data/config.yaml` (main config) provides model defaults that profile configs inherit. If a profile's `config.yaml` omits `base_url` / `api_key` but the main config has them, the main config values are used. To fully isolate profiles, ensure each profile's config is self-contained.
- **Built-in plugins vs custom:** `opencode-zen`, `opencode-go`, and `nvidia` are built-in providers that read specific env vars (`OPENCODE_ZEN_API_KEY`, `OPENCODE_GO_API_KEY`, `NVIDIA_API_KEY`) — no `custom_providers` entry needed, no `base_url` or `api_key` in `config.yaml`. Just set `provider: opencode` and the env var.
- **`api_key` in config.yaml vs .env:** A key in `config.yaml` takes effect only for that profile; an env var in `.env` is available to all profiles. Provider plugins that read env vars exclusively (OpenCode Zen, OpenCode Go, NVIDIA) will ignore a key buried in `config.yaml`.
- **⚠️ CRITICAL: `custom_providers` list must match `hermes config show` provider name.** If `hermes config show` reports `provider: custom:agnes` but `config.yaml`'s `custom_providers:` section lacks an entry with `name: agnes`, the gateway will silently fail with cascading 401/429 errors. Always verify: `grep -A50 "custom_providers:" ~/.hermes/config.yaml | grep -q "name: <provider>"` after setting a custom provider. If the name is missing, the provider is UNREGISTERED and will never work regardless of valid API keys.
- **⚠️ CRITICAL: Gateway runtime config is the SOURCE OF TRUTH.** Never assume a profile is blank just because config.yaml doesn't exist — runtime config may have been set via dashboard. Always use `hermes config show` and `hermes config show --profile <name>` to verify current settings.
- **⚠️ CRITICAL: Always check BOTH default and research profiles.** When setting up models/providers, verify both profiles have the same configuration. Use `hermes config show` for default and `hermes config show --profile research` for research.
- **⚠️ CRITICAL: Config.yaml paths are NOT under `.hermes/`.** On this system, default config is `/opt/data/config.yaml` and research config is `/opt/data/profiles/research/config.yaml`. The `.hermes/` subdirectory does NOT contain profile configs.
- **⚠️ CRITICAL: `hermes config set` cannot append to empty lists.** When `fallback_providers: []` is empty, `hermes config set fallback_providers.0.xxx` throws `IndexError`. Use Python + PyYAML to edit directly.
- **⚠️ CRITICAL: NEVER blindly overwrite config.yaml.** The `write_file` tool has a security guard that blocks writes to `config.yaml`, BUT terminal commands like `cp` bypass this guard entirely. Copying a profile config over the main config WILL succeed but DESTROYS any settings unique to the main config (e.g., custom_providers, auxiliary configs, vision settings). **Always diff before cp:** `diff /opt/data/config.yaml /opt/data/profiles/default/config.yaml` and verify the main config has everything the profile config is missing.
- **⚠️ CRITICAL: custom_providers must be in the RIGHT file.** The main config (`/opt/data/config.yaml`) is what the gateway reads for `custom_providers`. If you define a custom provider in `.hermes/config.yaml` but NOT in the main config, the model selector may show it but the gateway will fail at runtime. **Always define custom_providers in both places** (or verify which file the gateway actually reads for your setup).
- **⚠️ CRITICAL: custom_providers models list must be complete.** If the main config's `custom_providers` only lists one model (e.g., `llama-4-scout-17b-16e-instruct`) but `.hermes/config.yaml` lists more (e.g., `llama-3.3-70b-versatile`), the `/model` command will fail with "Unknown provider" for any model not in the main config. **Always sync the models list** between both files.
- **⚠️ CRITICAL: config.yaml paths are NOT under `.hermes/`.** On this system, default config is `/opt/data/config.yaml` and research config is `/opt/data/profiles/research/config.yaml`. The `.hermes/` subdirectory does NOT contain profile configs.

## References
- See `references/agnes-provider.md` for details on the Agnes endpoint and model naming.
- See `references/api-key-resolution.md` for how Hermes resolves API keys across profiles, providers, and env vars.
- See `references/opencode-provider.md` for OpenCode Zen/Go setup (built-in plugin, no registration needed).
- See `references/custom-provider-mismatch.md` for diagnosing when `hermes config show` reports a custom provider that isn't registered in `config.yaml`.
- See `templates/global-env-template.env` for a starter `.env` file layout.
- See `scripts/propagate_api_keys.sh` for a ready-to-use script to propagate API keys from a source profile to targets.
- See `scripts/set_fallback.py` for safely setting fallback_providers when `hermes config set` fails on empty lists.
- See `references/config-file-safety.md` for safe restore patterns when config.yaml is accidentally overwritten.

## Related Skills
- `hermes-agent` (bundled) – for overall Hermes setup and troubleshooting.
- `hermes-profile-management` – for creating, listing, and switching profiles.

## Changelog
- Added OpenCode Zen/Go as built-in plugin provider with per-model routing documentation.
- Added comprehensive audit workflow (execute_code comparison table across all .env files).
- Added config hierarchy pitfall (main config.yaml vs profile config.yaml inheritance).
- Updated verification commands to show both `hermes config show` and `hermes status` patterns.
- Initial capture from session where user requested global API key propagation and Agnes provider setup.