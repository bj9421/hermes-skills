# Multi-Provider Cascade Failure — Diagnostic Record

**Date:** 2026-07-22  
**Trigger:** Auto Memory Scanner cron job failed with "HTTP 401: Missing Authentication header"

## Symptoms

Three providers failing simultaneously with different error codes:

| Provider | Model | Error | Frequency |
|----------|-------|-------|-----------|
| opencode-zen | big-pickle | HTTP 500 Internal Server Error | 18x in one day |
| custom:agnes | agnes-1.5-flash | HTTP 503 No available channel | Repeated |
| openrouter | claude-sonnet-4 | HTTP 401 Missing Authentication header | Each retry |

## Root Cause Analysis

### Primary: opencode/big-pickle (HTTP 500)
- **Upstream issue.** OpenCode Zen server crash confirmed via GitHub issues.
- Issue #28141 (May 2026): "Big Pickle model returns AI_APICallError"
- Issue #35149 (Jul 3, 2026): "Insufficient Balance" on free models — backend routing bug where free track hit paid wallet gate. Closed by @fwang after ~2 days.
- This is NOT a config problem.

### Secondary: agnes-1.5-flash (HTTP 503)
- Agnes API returning "No available channel for model under group cachellm"
- Model may be deprecated or overloaded.

### Tertiary: openrouter (HTTP 401)
- **Config problem.** `OPENROUTER_API_KEY` exists in `/opt/data/.env` but is NOT loaded into cron job environment.
- Cron jobs run in isolated sessions that do NOT inherit `.env`.
- Gateway process also missing `OPENROUTER_API_KEY` in its environment.
- Fix needed: set key in Docker container env or systemd service file.

## Resolution Steps Taken

### First attempt (2026-07-22 morning)
1. Searched web for "opencode big-pickle down" → confirmed widespread issue since May 2026
2. Verified agnes-2.0-flash works via direct curl test → ✅ OK
3. Adjusted fallback order in config.yaml:
   - 1st: agnes-2.0-flash (custom:agnes) ← NEW FIRST FALLBACK
   - 2nd: big-pickle (opencode)
   - Removed duplicate agnes-1.5-flash entry
4. Updated Auto Memory Scanner cron job to use `custom:agnes:agnes-2.0-flash` directly
5. Re-ran cron job → status changed to `ok`

### Second attempt (2026-07-22 evening) — Agnes also dead
By evening, even agnes-2.0-flash was timing out and agnes-1.5-flash returned 503. Follow-up diagnosis:
1. Tested agnes-1.5-flash → HTTP 503 "No available channel"
2. Tested agnes-2.0-flash → Timeout (>20s)
3. Searched web for Agnes AI outage → discovered full infrastructure collapse (23 days no GitHub activity)
4. Removed all fallback_providers entirely → config now clean with no dead fallbacks

**Resolution:** User chose to run with NO fallback — just the main model (deepseek-v4-flash-free via OpenCode Zen). This is valid when:
- Main model is stable and reliable
- ALL fallback providers are confirmed dead (not just slow)
- There's no functional alternative to migrate to

### When to remove vs rotate fallbacks
| Situation | Action |
|-----------|--------|
| One fallback dead, others work | Remove only the dead one, keep chain |
| All fallbacks dead, main works | Remove all fallbacks (empty chain) |
| Main also unstable | Add a different provider entirely (e.g. Groq, NVIDIA) |
| Fallback intermittently slow | Keep but move to lowest priority |

## Key Learnings

- When multiple providers fail with DIFFERENT error codes, upstream is likely down — don't debug configs blindly
- Always search web first before assuming it's your problem
- Cron jobs DO NOT inherit `.env` — API keys must be set in container/service env for cron access
- Test each provider independently via curl when fallback chain fails

## Related Issues Found

- https://github.com/anomalyco/opencode/issues/28141 — Big Pickle returns AI_APICallError
- https://github.com/anomalyco/opencode/issues/35149 — Free models show "Insufficient Balance"
- https://github.com/anomalyco/opencode/issues/28138 — Big Pickle not working after v1.15.4 update (format mapping bug)
- https://github.com/anomalyco/opencode/issues/28146 — "Model big-pickle not supported for format anthropic" (desktop app v1.15.4)

## Big Pickle Status Update (2026-07-22)

**Status: BROKEN — upstream issue confirmed.**

Diagnosis from this session:
- `api.opencode.ai` responds HTTP 200 but body is literally `"Not Found"` for ALL endpoints (`/v1/models`, `/v1/chat/completions`)
- Tested with all model name variations: `big-pickle`, `bigpickle`, `BigPickle`, `opencode/big-pickle` — all return "Not Found"
- API key is valid (connection succeeds), but the model endpoint itself is down
- Multiple GitHub issues confirm this is a known issue since May 2026

Workaround: Remove `big-pickle` from `fallback_providers` until upstream fixes it. As of Jul 22, even the previous fallback alternative (agnes-2.0-flash) is also dead — the recommended configuration is **no fallback chain** when both big-pickle and agnes are down simultaneously.

## Diagnostic Procedure: Testing Provider Connectivity

When a provider/model seems broken, follow this exact sequence:

### Step 1: Check config references
```bash
# See what model/provider is configured
python3 -c "
import yaml
with open('/opt/data/config.yaml') as f:
    c = yaml.safe_load(f)
print('model.default:', c.get('model',{}).get('default'))
print('model.provider:', c.get('model',{}).get('provider'))
print('fallback_providers:', c.get('fallback_providers'))
print('custom_providers:', [p.get('name') for p in c.get('custom_providers',[])])
"

# Check .env has the key
grep 'KEY' /opt/data/.env | grep -v '^#' | sed 's/=.*/=***/'
```

### Step 2: Test TCP/TLS connectivity
```bash
# Quick check if the host resolves and accepts TLS
curl -sv --max-time 15 https://api.example.com/v1/models \
  -H "Authorization: Bearer $API_KEY" 2>&1 | grep -E '(Connected|Could resolve|SSL)'
```

### Step 3: Test the actual chat endpoint
```bash
# Direct curl test — this bypasses Hermes internals
curl -s --max-time 15 https://api.example.com/v1/chat/completions \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"MODEL_NAME","messages":[{"role":"user","content":"hi"}],"max_tokens":5}'
```

### Step 4: Interpret results
| Response | Meaning | Action |
|----------|---------|--------|
| HTTP 200 + valid JSON response | Provider OK | Check Hermes config routing |
| HTTP 200 + "Not Found" | Model deprecated/down | Search web, update model name or remove from fallback |
| HTTP 401/403 | Invalid/expired API key | Check .env, re-authenticate |
| Connection refused / timeout | Server down or network issue | Check server status page |
| DNS resolution failed | Wrong base_url or domain changed | Verify base_url in config |

### Step 5: Search for widespread issues
```bash
web_search("PROVIDER MODEL down 2026")
web_search("PROVIDER MODEL API error")
```

Check GitHub issues for the provider's repo — many have public issue trackers.
