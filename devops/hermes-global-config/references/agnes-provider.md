# Agnes Provider Reference

## Endpoint
- Base URL: `https://apihub.agnes-ai.com/v1/chat/completions`
- API Key Environment Variable: `AGNES_API_KEY`
- API Mode: `chat_completions`

## Known Models
- `agnes-2.0-flash` (default model used in this session)
- Other models may be available; check the Agnes API documentation for the full list.

## Configuration in Hermes
To use Agnes as a custom provider in a Hermes profile:

```yaml
model:
  default: agnes-2.0-flash
  provider: custom
providers:
  custom:
    base_url: https://apihub.agnes-ai.com/v1/chat/completions
    api_mode: chat_completions
    # The API key is read from the environment variable AGNES_API_KEY
```

## Notes
- Agnes appears to be an OpenAI-compatible API endpoint.
- The API key must be set in the environment (via `.env` or system environment) for the provider to work.
- If you encounter authentication errors, verify that the `AGNES_API_KEY` is correctly set and not expired.
- **401 "无效的令牌" (invalid token)**: If the API returns this error, the key has been revoked or expired. Contact the provider or generate a new key.
- **Gateway can't find the provider**: If `hermes config show` reports `custom:agnes` but gateway still fails, check that `config.yaml`'s `custom_providers:` section includes `- name: agnes`. Mismatch causes silent 401 cascades.

## Source
Information gathered from the user's Hermes configuration during the session on 2025-07-04. Updated 2026-07-13 with custom provider mismatch diagnosis.