# Vision (Auxiliary) Configuration Troubleshooting

## Diagnostic Flow

When vision_analyze returns HTTP 401 `Missing Authentication Header`, follow this flow instead of guessing fixes:

```
Step 1. Is the API key valid?
  → curl test (see below)
  ├─ 200 → key is fine, go to Step 2
  └─ 401 → key expired/revoked, get a new one

Step 2. Which config file is Hermes actually reading?
  → hermes config path
  ├─ Check if auxiliary.vision exists in THAT file
  │  ├─ YES → go to Step 3
  │  └─ NO  → use `hermes config set` to write it,
  │           then go to Step 4
  
Step 3. Does an empty top-level `vision:` block exist in the active config?
  → grep -n "^vision:" "$(hermes config path)"
  ├─ YES → delete that block, go to Step 4
  └─ NO  → go to Step 4 (settings should be correct)

Step 4. Restart gateway and test vision_analyze again
```

**Session example (2026-07-13):** Step 1 passed (key valid), Step 3 found an empty block and deleted it → still 401. Step 2 revealed the root cause: `auxiliary.vision` with full NVIDIA settings existed in `/opt/data/profiles/default/config.yaml` but the **active** config (`/opt/data/config.yaml`) had no `auxiliary` section at all. Fix: `hermes config set auxiliary.vision.*` wrote to the active config.

## Config Conflict: `auxiliary.vision` vs top-level `vision:`

Hermes has **two** vision config sections that interact:

```yaml
# 1. Primary config — where the actual provider settings go
auxiliary:
  vision:
    provider: nvidia
    model: meta/llama-3.2-90b-vision-instruct
    base_url: https://integrate.api.nvidia.com/v1
    api_key: nvapi-...              # inline key
    timeout: 120

# 2. Top-level fallback — may be auto-generated, usually empty
vision:
  base_url: ''
  model: ''
  provider: ''
```

**⚠️ If the top-level `vision:` block exists (even with empty strings), it may override or conflict with `auxiliary.vision`**, causing the vision tool to send requests without the API key → HTTP 401 `Missing Authentication Header`.

### Detection

The 401 error message is the key giveaway:
```
Error code: 401 - {'error': {'message': 'Missing Authentication header', 'code': 401}}
```

Compare with a genuine auth-failure 401 (different shape):
```json
{"error": {"message": "Incorrect API key", "code": 401}}
```

`Missing Authentication Header` means the request was sent **without any Authorization header** at all — not that the key was rejected.

### Fix

**Option A: Remove the empty top-level `vision:` block entirely**

```yaml
# Delete these lines:
vision:
  base_url: ''
  model: ''
  provider: ''
```

**Option B: Use `key_env` + `base_url_env` instead of inline `api_key`**

This follows the same pattern as `custom_providers` and avoids key-reloading issues:

```yaml
auxiliary:
  vision:
    provider: nvidia
    model: meta/llama-3.2-90b-vision-instruct
    base_url_env: NVIDIA_BASE_URL    # reads from .env
    key_env: NVIDIA_API_KEY          # reads from .env
    timeout: 120
```

The `.env` file:
```
NVIDIA_API_KEY=nvapi-...
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
```

## Full Config Walkthrough

1. Check both config sections exist:
   ```bash
   grep -A6 "auxiliary:" /opt/data/config.yaml | head -12
   grep -n "^vision:" /opt/data/config.yaml
   ```

2. If `^vision:` appears at top level AND also inside `auxiliary:` → potential conflict

3. Fix by either deleting the empty top-level block OR migrating to `key_env`/`base_url_env`

## Verifying Vision API Key Independently

To confirm the key itself is valid (not expired/quota-exhausted), test the models endpoint:
```bash
curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer $NVIDIA_API_KEY" \
  "https://integrate.api.nvidia.com/v1/models"
# → 200 = key valid; 401 = key expired/revoked
```

## Performance Note

`hermes config set` takes **5–15 seconds per command** on Raspberry Pi 4 (normal — the CLI does config validation and file rewriting). Do not interrupt it; it still succeeds despite appearing hung. If working in batch, chain commands together with `&&` to reduce total wall-clock time.

## Known Vision Providers

| Provider | base_url | Auth | Notes |
|----------|----------|------|-------|
| NVIDIA | `https://integrate.api.nvidia.com/v1` | `NVIDIA_API_KEY` env var | Used by default in config |
| OpenAI | `https://api.openai.com/v1` | `OPENAI_API_KEY` env var | GPT-4o vision |
| Anthropic | `https://api.anthropic.com/v1` | `ANTHROPIC_API_KEY` env var | Claude vision |
| Custom | Any OpenAI-compatible endpoint | `key_env` or inline `api_key` | e.g. agnes-1.5-flash (also supports vision) |
