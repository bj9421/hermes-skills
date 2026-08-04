# NVIDIA NIM Free Models — Tested 2026-08-04

## Quick Reference

| Model | Status | Notes |
|-------|--------|-------|
| `stepfun-ai/step-3.7-flash` | ✅ Works | VLM, reasoning model, 198B/11B active |
| `minimaxai/minimax-m3` | ✅ Works | 456B MoE, slower |
| `nvidia/nemotron-mini-4b-instruct` | ✅ Works | Fast but weak |
| `meta/llama-3.2-1b-instruct` | ✅ Works | Very fast, very weak |
| `deepseek-ai/deepseek-v4-flash` | ⚠️ 529 | Rate limited, avoid |
| `nvidia/nemotron-3-super-14b` | ⚠️ Empty | Weird responses |

## Important Notes

1. **40 RPM limit** — every request counts, batch carefully
2. **Models rotate** — NVIDIA may remove models without notice
3. **Reasoning models need `max_tokens >= 200`** — otherwise content is null
4. **Free tier = prototyping only** — not for production workloads

## step-3.7-flash Configuration

```yaml
providers:
  nvidia:
    models:
      stepfun-ai/step-3.7-flash:
        stale_timeout_seconds: 600
        timeout_seconds: 300
```

Vision uses this model:
```yaml
auxiliary:
  vision:
    provider: nvidia
    model: stepfun-ai/step-3.7-flash
    base_url: https://integrate.api.nvidia.com/v1
```

## API Test Script

```bash
KEY=$(grep '^NVIDIA_API_KEY=' /opt/data/.env | cut -d= -f2)
curl -s -X POST "https://integrate.api.nvidia.com/v1/chat/completions" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"stepfun-ai/step-3.7-flash","messages":[{"role":"user","content":"hi"}],"max_tokens":500}'
```

## Context

- NVIDIA NIM free tier: 40 RPM, no credit system
- `nimType_preview` filter on build.nvidia.com = free endpoints
- Step-3.7-flash: 198B total params, 11B active per token (MoE)
- Supports: text, images, video, tool calling, 256K context
- License: Apache 2.0 (commercial use OK)
