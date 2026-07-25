---
name: provider-failure-diagnosis
category: devops
description: Diagnose and document LLM provider outages, fallback chain failures, and single-provider dependency states in Hermes deployments.
version: 1.0.0
author: Hermes Agent
platforms: [linux]
---

# Provider Failure Diagnosis

When multiple LLM providers fail simultaneously or a provider silently stops responding, diagnose systematically to avoid false conclusions about credentials or config.

## Trigger Conditions

- Primary model returns errors but `.env` keys appear valid
- Fallback providers all fail (503, timeout, "Not Found")
- User reports "model not working" after previously working
- Multiple providers show issues simultaneously
- Session runs on a single provider with no functional fallback

## Common Provider Failure Patterns

### Pattern A: Mass Outage (Distributor Overload)

**Symptom:** Multiple models from same provider all fail (503 + "no available channel", timeouts >40s)

**Example (2026-07-22):** Agnes AI — agnes-1.5-flash 503, agnes-2.0-flash timeout, qwen/qwen3-32b 503. Root cause: cachellm-py distributor overloaded by mass free-tier user influx after June 2026 announcement.

**Diagnostic:**
```bash
# Test each model individually
curl -s -H "Authorization: Bearer $AGNES_API_KEY" \
  "https://apihub.agnes-ai.com/v1/chat/completions" \
  -d '{"model":"agnes-1.5-flash","messages":[{"role":"user","content":"hi"}],"max_tokens":5}'

curl -s -H "Authorization: Bearer $AGNES_API_KEY" \
  "https://apihub.agnes-ai.com/v1/chat/completions" \
  -d '{"model":"agnes-2.0-flash","messages":[{"role":"user","content":"hi"}],"max_tokens":5}'
```

**Check available models:**
```bash
curl -s -H "Authorization: Bearer $AGNES_API_KEY" \
  "https://apihub.agnes-ai.com/v1/models" | python3 -c "import json,sys; [print(m['id']) for m in json.load(sys.stdin).get('data',[])]"
```

### Pattern B: Silent "Not Found" (HTTP 200 but body="Not Found")

**Symptom:** TCP/TLS connects fine, HTTP 200 returned, but response body is literally "Not Found". Model exists in list but completions fail.

**Example (2026-05-18 → 2026-07-22):** OpenCode Zen big-pickle — all requests returned HTTP 200 "Not Found". v1.15.4 has format mapping bugs too. **RESTORED as of 2026-07-23.**

**Diagnostic:**
```bash
# Check if model appears in /v1/models
curl -s "https://api.opencode.ai/v1/models" -H "Authorization: Bearer $OPENCODE_ZEN_API_KEY" | grep pickle

# Test completion endpoint
curl -s -w "\nHTTP_CODE:%{http_code}" \
  "https://api.opencode.ai/zen/v1/chat/completions" \
  -H "Authorization: Bearer $OPENCODE_ZEN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"big-pickle","messages":[{"role":"user","content":"hi"}],"max_tokens":5}'
```

### Pattern C: Truncated API Key

**Symptom:** Key appears short (e.g., 13 chars instead of 50+), authentication fails with "Missing Authentication header" or similar.

**Example (2026-07-22):** OpenRouter key stored as `sk-or-...886f` (13 chars). This was NOT Hermes redaction — the `.env` file itself contained the truncated value.

**Diagnostic:**
```bash
python3 -c "
with open('/opt/data/.env') as f:
    for line in f:
        if 'OPENROUTER' in line:
            val = line.split('=',1)[1].strip()
            print(f'len={len(val)}, full={repr(val)}')
"
```

**Fix:** Re-obtain the full key from the provider dashboard and rewrite `.env`.

### Pattern D: Single Provider Running Solo (No Fallback)

**Symptom:** After removing dead providers from `fallback_providers`, no functional fallback remains. Session runs on primary only.

**Diagnostic:**
```bash
grep -A5 'fallback_providers:' /opt/data/config.yaml
grep 'default:' /opt/data/config.yaml
```

**Action:** Add a working provider to `fallback_providers` or accept single-provider dependency.

## Provider-Specific Reference Cards

See `references/provider-status-jul2026.md` for current status of known providers.

## Systematic Diagnostic Workflow

```
1. Confirm which providers are configured
   → hermes config show | grep -A10 'providers\|custom_providers\|fallback'

2. Test primary model directly
   → curl to /chat/completions with minimal payload

3. If primary fails, test each fallback in order
   → Same curl pattern per provider

4. If ALL fail, check:
   a. API keys in .env (length, format)
   b. Provider status pages / GitHub issues
   c. Network connectivity (can we reach the host?)

5. Document findings and update fallback config
   → Remove dead providers
   → Add working alternatives
```

### Pattern E: Model Deprecation (HTTP 404 / 400)

**Symptom:** Specific model returns 404 or 400 while other models from same provider work fine. Key is valid, base URL responds.

**Example (2026-07-23):** Groq — `llama-4-scout-17b-16e-instruct` → 404, `qwen/qwen3-32b` → 404, `mixtral-8x7b-32768` → 400, `deepseek-r1-distill-llama-70b` → 400, `gemma2-9b-it` → 400. All share one root cause: deprecated by provider.

**Diagnostic:**
```bash
# Test the specific model vs a known-good model from same provider
curl -s -w "\nHTTP:%{http_code}" https://api.groq.com/openai/v1/chat/completions \
  -H "Authorization: Bearer $GROQ_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"DEPRECATED_MODEL","messages":[{"role":"user","content":"hi"}],"max_tokens":1}'

curl -s -w "\nHTTP:%{http_code}" https://api.groq.com/openai/v1/chat/completions \
  -H "Authorization: Bearer $GROQ_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"openai/gpt-oss-120b","messages":[{"role":"user","content":"hi"}],"max_tokens":1}'
```

If one model 404/400 but another from same provider returns 200 → **model deprecation**, not key/network issue.

**Check deprecation announcements:**
```bash
# Provider often has a deprecation page
# Groq: https://console.groq.com/docs/deprecations
# Check if model appears in current /v1/models list
curl -s "https://api.groq.com/openai/v1/models" -H "Authorization: Bearer $GROQ_API_KEY" | python3 -c "import json,sys; [print(m['id']) for m in json.load(sys.stdin).get('data',[])]"
```

**Fix:** Remove deprecated model from config, add replacement from provider's current production models.

**Key insight:** A 404/400 on ONE model does NOT mean the provider is down. Always test a known-good model first before concluding provider outage.

---

## Known Provider Status (as of 2026-07-23)

| Provider | Model | Status | Notes |
|----------|-------|--------|-------|
| **opencode** | **big-pickle** | **✅ WORKING** | **Primary model since 2026-07-23. Was dead since ~May 2026 — RESTORED.** |
| custom:agnes | agnes-2.0-flash | ✅ working | Fallback #1. Was timeout on 07-22 — RESTORED. context_length=256000 |
| opencode | deepseek-v4-flash-free | ✅ working | Fallback #2. Free tier. |
| custom:groq | openai/gpt-oss-120b | ✅ working | Production. 128K ctx. $0.15/$0.60 per 1M tokens |
| custom:groq | openai/gpt-oss-20b | ✅ working | Production. 128K ctx. $0.075/$0.30 per 1M tokens |
| custom:groq | qwen/qwen3.6-27b | ✅ working | Production. 128K ctx. $0.60/$3.00 per 1M tokens |
| custom:groq | llama-3.3-70b-versatile | ⚠️ working | Deprecated 8/16/26 — migrate to gpt-oss-120b or qwen3.6-27b |
| Agnes AI | agnes-1.5-flash | ❌ 503 | cachellm-py no channels — still down |
| Agnes AI | qwen/qwen3-32b | ❌ 503 | Same distributor issue |
| Agnes AI | agnes-image-2.1-flash | ✅ alive | Image gen only (not chat) |
| Agnes AI | agnes-video-v2.0 | ✅ alive | Video gen only (not chat) |
| Groq | llama-4-scout-17b-16e-instruct | ❌ 404 | Deprecated 7/17/26 |
| Groq | qwen/qwen3-32b | ❌ 404 | Deprecated 7/17/26 |
| Groq | mixtral-8x7b-32768 | ❌ 400 | Deprecated |
| Groq | deepseek-r1-distill-llama-70b | ❌ 400 | Deprecated |
| Groq | gemma2-9b-it | ❌ 400 | Deprecated |
| Groq | llama-3.3-70b-versatile | ⚠️ 200 | Will be deprecated 8/16/26 — migrate to gpt-oss-120b or qwen3.6-27b |
| OpenRouter | claude-sonnet-4 | ❌ 401 | Key broken (13 chars in .env) |

**Active fallback chain (2026-07-23):**
```
1. opencode/big-pickle          ← 主力
2. custom:agnes/agnes-2.0-flash ← 第一冗餘
3. opencode/deepseek-v4-flash-free ← 免費兜底
```

**Excluded from fallback:**
- `agnes-1.5-flash` — 503 no available channel
- `llama-4-scout-17b-16e-instruct` (Groq) — 404 deprecated
- `claude-sonnet-4` (OpenRouter) — 401 auth error
- All Groq deprecated models — check references/groq-deprecated-models.md for full list

## Change Log

| Date | Change |
|------|--------|
| 2026-07-23 | **MAJOR STATUS SHIFT:** big-pickle restored (was dead since May 2026). agnes-2.0-flash restored (was timeout). Updated active fallback chain. |
| 2026-07-23 | Added Groq 404 and OpenRouter 401 to excluded providers. |
| 2026-07-22 | Initial version. Captures Agnes AI mass outage, OpenCode Zen big-pickle death, OpenRouter key truncation patterns. |