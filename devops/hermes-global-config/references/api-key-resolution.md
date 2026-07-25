# Hermes API Key Resolution

How API keys flow from storage to the provider at runtime.

## Resolution Priority (per profile)

```
config.yaml → model.api_key    (highest, profile-scoped)
  OR
config.yaml → providers.<name>.api_key    (provider-scoped)
  OR
Environment variable (from merged .env files)    (lowest, cross-profile)
```

Profile `.env` files are merged at startup: global `/opt/data/.env` first, then profile-specific `/opt/data/profiles/<name>/.env` — profile values override global ones for duplicate variable names.

## Provider Env Var Requirements

Some providers **require** a specific env var and ignore `config.yaml` keys:

| Provider | Env Var | Notes |
|----------|---------|-------|
| `opencode-zen` (alias `opencode`) | `OPENCODE_ZEN_API_KEY` | Plugin defined at `providers/opencode-zen/__init__.py` |
| `opencode-go` | `OPENCODE_GO_API_KEY` | Separate endpoint (open models) |
| `custom` (generic) | — | Reads `config.yaml` `model.api_key` directly |
| `nvidia` | `NVIDIA_API_KEY` | Used by the NVIDIA provider plugin |
| `openrouter` | `OPENROUTER_API_KEY` | Standard env var |

To check a provider plugin's env var requirement:

```bash
grep "env_vars" /opt/hermes/plugins/model-providers/<provider>/__init__.py
```

Or for Hermes built-in providers:

```bash
grep -rn "env_vars" /opt/hermes/agent/providers/ 2>/dev/null | grep -v ".pyc"
```

## Common Patterns Seen in Practice

### Pattern A: Key in both config.yaml and .env
The `config.yaml` key wins for `provider: custom`; the env var is ignored by that provider. But the env var is still useful if another profile uses a different provider that reads it.

### Pattern B: Key only in config.yaml, provider reads env var
The provider fails silently or returns auth errors. **Fix:** add the env var to the profile's `.env`.

### Pattern C: Key only in .env, provider expects config key
Works for `provider: custom` only if `base_url` and `api_mode` are also in `config.yaml`.

## Persistence

All files under `/opt/data/` (the Docker mount) survive:

| Operation | Keys survive? |
|-----------|--------------|
| `docker restart` | ✅ Yes |
| `docker stop` → `docker start` | ✅ Yes |
| `docker rm` + re-create with same volume | ✅ Yes |
| Delete the host volume (`/home/hermes_data/`) | ❌ No |

## Quick Audit

Check a specific key's presence across all profiles in one command:

```bash
echo "=== ENV FILES ===" && for f in /opt/data/.env /opt/data/profiles/*/.env; do
  [ -f "$f" ] && echo "$f: $(grep -c 'OPENCODE_ZEN_API_KEY' "$f" || echo 0)"
done && echo "=== CONFIG FILES ===" && for f in /opt/data/profiles/*/config.yaml; do
  [ -f "$f" ] && echo "$f: $(grep -c 'api_key' "$f" || echo 0)"
done
```
