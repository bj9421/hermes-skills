# Agnes Provider: Full Service Collapse (2026-07-22)

## Timeline

### Jul 13 — Model Deprecation
- `agnes-2.0-flash` returned HTTP 404 (NotFoundError)
- `agnes-1.5-flash` confirmed as active alternative by provider's model listing
- Multi-model config migration performed: single-model → multi-model models: dict

### Jul 22 — Full Service Collapse
All chat models became unusable:

| Model | Status | Error |
|-------|--------|-------|
| `agnes-2.0-flash` | ❌ Timeout | Read operation timed out (>20s) |
| `agnes-1.5-flash` | ❌ 503 | No available channel for model under group cachellm |
| `qwen/qwen3-32b` | ❌ 503 | No available channel |
| `agnes-image-2.1-flash` | ? Untested | Listed but untested |
| `agnes-video-v2.0` | ? Untested | Listed but untested |

**Only listing endpoint works:** GET /v1/models returns 200 with model IDs, but none of the chat models actually serve requests.

### Root Cause

Error reveals backend infrastructure collapse:
- **cachellm** = Agnes backend caching/distribution layer that routes to GPU channels
- All GPU channels exhausted (free-tier overload)
- Last GitHub push: **2026-06-29** (23+ days without updates as of Jul 22)
- Single contributor (agnesai-admin), no activity since late June

### Verdict

> **Agnes AI is in prolonged infrastructure crisis.** The free tier attracted massive usage the backend cannot sustain. With zero GitHub activity for 23+ days and all chat models dead, **do not rely on Agnes for any production or fallback needs.** Keep the custom_providers entry for historical reference but remove from fallback chains.

## Config History

**Before** (single-model + inline api_key):
```yaml
custom_providers:
  - name: agnes
    base_url: https://apihub.agnes-ai.com/v1/chat/completions
    api_key: sk-X7d...V04F
    api_mode: chat_completions
    model: agnes-2.0-flash
```

**After** (multi-model + key_env, kept for reference):
```yaml
custom_providers:
  - name: agnes
    base_url: https://apihub.agnes-ai.com/v1/chat/completions
    key_env: AGNES_API_KEY
    api_mode: chat_completions
    models:
      agnes-2.0-flash:
        context_length: 256000
      agnes-1.5-flash:
        context_length: 256000
      agnes-video-v2.0:
        context_length: 256000
      agnes-image-2.1-flash:
        context_length: 256000
      agnes-image-2.0-flash:
        context_length: 256000
```

## Key Facts

- **Agnes API endpoint:** `https://apihub.agnes-ai.com/v1/chat/completions`
- **API key length:** 13 chars on display (Hermes masking); actual 50+ chars
- **key_env vs api_key:** Use `key_env: AGNES_API_KEY` to read from .env
- **Both profiles** need separate config entries

## Error Signatures

| Error | Meaning |
|-------|---------|
| HTTP 503 No available channel for model under group cachellm | Backend GPU capacity exhausted |
| Read timeout (>20s) | Server overloaded |
| HTTP 200 + model listing only | Discovery works, inference doesn't |
| HTTP 404 NotFoundError | Model name deprecated/renamed |
| HTTP 401 invalid token | API key wrong or expired |