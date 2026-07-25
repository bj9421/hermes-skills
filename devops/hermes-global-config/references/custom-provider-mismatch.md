# Custom Provider Mismatch Failure

## Problem
`hermes config show` reports `provider: custom:agnes` as active, but `config.yaml`'s `custom_providers:` section has no entry with `name: agnes`. Result: gateway fails with cascading 401/429 errors despite valid API keys.

## Symptoms
- Gateway log shows: `HTTP 401: Missing Authentication header` or `无效的令牌`
- Fallback chain triggers repeatedly (opencode → openrouter → fail)
- `hermes config show` says model/provider is set correctly
- But `grep -A50 "custom_providers:" ~/.hermes/config.yaml | grep "name: agnes"` returns nothing

## Root Cause
Two configuration sources can diverge:
1. `hermes config set model.provider custom:agnes` — sets the *active* provider name
2. `config.yaml` `custom_providers:` list — defines *which* custom providers exist

If (2) is missing the entry, (1) points to a ghost provider.

## Fix
Add the provider definition to `config.yaml`:
```yaml
custom_providers:
  - name: agnes
    base_url: https://apihub.agnes-ai.com/v1
    key_env: AGNES_API_KEY
    models:
      agnes-2.0-flash:
        context_length: 128000
```

## Prevention
After any `hermes config set model.provider custom:<name>`, verify:
```bash
grep -A50 "custom_providers:" ~/.hermes/config.yaml | grep -q "name: <name>"
```
If the grep fails, the provider is unregistered.

## Source
Session 2026-07-13: user reported gateway model switching failures. Investigation revealed `custom:agnes` was set as active provider but missing from `config.yaml` custom_providers list.