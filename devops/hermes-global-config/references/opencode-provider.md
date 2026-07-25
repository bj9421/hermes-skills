# OpenCode Provider Family (Built-in Plugins)

OpenCode Zen and OpenCode Go are **built-in Hermes provider plugins** — no `custom_providers`
registration needed. They ship with Hermes and are auto-discovered.

## Quick Setup

```bash
# 1. Ensure env var is set in the profile's .env (already done for global keys)
echo 'OPENCODE_ZEN_API_KEY=sk-...' >> /opt/data/profiles/<profile>/.env

# 2. Switch to the provider (no base_url needed)
hermes config set model.default big-pickle
hermes config set model.provider opencode
hermes config set model.api_mode chat_completions
```

## Plugin Source

| Detail | OpenCode Zen | OpenCode Go |
|--------|-------------|-------------|
| Plugin path | `/opt/hermes/plugins/model-providers/opencode-zen/__init__.py` | (same file) |
| Env var | `OPENCODE_ZEN_API_KEY` (line 112) | `OPENCODE_GO_API_KEY` (line 120) |
| Default base URL | `https://opencode.ai/zen/v1` | `https://opencode.ai/zen/go/v1` |
| Aliases | `opencode`, `opencode_zen`, `zen` | `opencode_go`, `go`, `opcode-go-sub` |

To verify which env var a provider reads:

```bash
grep "env_vars" /opt/hermes/plugins/model-providers/opencode-zen/__init__.py
```

## Per-model Wire Format Routing

OpenCode Zen automatically selects the right API shape per model:

- **`anthropic_messages`** — Claude-family models (Claude Opus, Sonnet, Haiku)
- **`codex_responses`** — GPT-5 and Codex models
- **`chat_completions`** — Everything else: big-pickle, GLM-4/5, Kimi K2, MiniMax, etc.

You do NOT need to set `api_mode` per model — the plugin handles this.

## Config Hierarchy Note

The `model` section in `/opt/data/config.yaml` (main config) provides defaults that profile
configs inherit. If you set `provider: opencode` in a profile config but omit `base_url`
and `api_key`, the main config's values fill the gap. To fully isolate a profile:

```yaml
# /opt/data/profiles/<name>/config.yaml
model:
  default: big-pickle
  provider: opencode
  api_mode: chat_completions
# No base_url/api_key needed — plugin reads env var
# No custom_providers entry needed — built-in plugin
```

## Testing

```bash
hermes status | head -15
# Look for: Provider: OpenCode Zen
#           Model:   big-pickle (or your chosen model)
```

For a quick chat test:
```bash
hermes chat "Hello, what model are you?"
```
