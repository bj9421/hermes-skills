# Provider Status Testing Workflow

Quick-check which providers/models are actually working before changing fallback order.

## Parallel curl test (all providers at once)

Run these in parallel via `terminal()` — each is independent:

```bash
# 1. OpenCode Zen (big-pickle, deepseek-v4-flash-free, etc.)
curl -s -w "\nHTTP:%{http_code}" https://opencode.ai/zen/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENCODE_ZEN_API_KEY" \
  -d '{"model":"big-pickle","messages":[{"role":"user","content":"say hi in 2 words"}],"max_tokens":10}' | tail -3

# 2. Agnes (custom provider)
curl -s -w "\nHTTP:%{http_code}" https://apihub.agnes-ai.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AGNES_API_KEY" \
  -d '{"model":"agnes-2.0-flash","messages":[{"role":"user","content":"say hi in 2 words"}],"max_tokens":10}' | tail -3

# 3. Groq (custom provider)
curl -s -w "\nHTTP:%{http_code}" https://api.groq.com/openai/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $GROQ_API_KEY" \
  -d '{"model":"llama-4-scout-17b-16e-instruct","messages":[{"role":"user","content":"say hi in 2 words"}],"max_tokens":10}' | tail -3

# 4. OpenRouter
curl -s -w "\nHTTP:%{http_code}" https://openrouter.ai/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  -d '{"model":"anthropic/claude-sonnet-4","messages":[{"role":"user","content":"say hi in 2 words"}],"max_tokens":10}' | tail -3
```

## What the HTTP codes mean

| Code | Meaning | Action |
|------|---------|--------|
| 200 | Working | ✅ Safe to use |
| 401 | Auth failure | Key missing/wrong — check `.env` |
| 404 | Model not found | Model name changed/deprecated — check provider model list |
| 500 | Upstream error | Provider having issues — check GitHub/status page |
| 503 | No capacity | Provider overloaded — may recover later |
| 000 | Connection failed | DNS/network issue or endpoint changed |

## Fallback order logic

- **Different providers first**: if OpenCode goes down, deepseek-v4-flash-free (same provider) goes too. Put Agnes first in fallbacks for true redundancy.
- **Test both directions**: a working model can go 404→200 when the provider fixes things. Don't assume yesterday's status — re-test.
- **No fallback is valid**: when all fallbacks fail, remove them entirely. An empty chain with a stable main model is better than a chain that hits 401/404 on every entry.

## Quick model list check

```bash
# OpenCode Zen model list
curl -s https://opencode.ai/zen/v1/models -H "Authorization: Bearer $OPENCODE_ZEN_API_KEY" | \
  python3 -c "import json,sys; [print(m['id']) for m in json.load(sys.stdin)['data']]"

# Agnes model list (may not be available — test known models individually)
```
