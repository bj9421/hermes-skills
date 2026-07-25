# Provider Status Reference — Updated 2026-07-23

## OpenCode Zen (opencode.ai/zen)

### big-pickle Model
- **Status:** ✅ **RESTORED** as of 2026-07-23. Was dead since ~May 2026 (HTTP 200 "Not Found"). Now returns valid chat completions with reasoning_content.
- **Primary model** for this deployment since 2026-07-23.
- **Endpoint:** `https://opencode.ai/zen/v1/chat/completions`
- **Model list endpoint:** `https://opencode.ai/zen/v1/models`

### deepseek-v4-flash-free
- **Status:** ✅ Working (free tier, no cost)
- Used as fallback #2 in provider chain

---

## Agnes AI (apihub.agnes-ai.com)

**Mass outage started ~2026-06-29.** Cause: cachellm-py v0.2.0 distributor overloaded after June 1 free-tier announcement.

### Affected Models (Still Down)
- `agnes-1.5-flash` → 503 "No available channel" — **still down as of 2026-07-23**
- `qwen/qwen3-32b` → 503 — same issue

### Recovered Models
- **`agnes-2.0-flash` → ✅ RESTORED as of 2026-07-23.** Was timing out (>40s) on 07-22. Now returns HTTP 200 with valid completions. Used as fallback #1.
- context_length: 256000

### Surviving Models (non-chat)
- `agnes-image-2.1-flash` → Image generation works
- `agnes-video-v2.0` → Video generation works

### Status Timeline
| Date | Event |
|------|-------|
| 2026-06-01 | Announced 3 core models permanently free |
| 2026-06-23 | agnes-2.0-flash timeout rate hit 38% |
| 2026-06-25 | Official docs show "system busy, retry later" |
| 2026-06-28 | Last GitHub update (troubleshooting doc) |
| 2026-06-29 | Last push to repo |
| 2026-07-22 | All chat models down or timing out; image/video survive |
| **2026-07-23** | **agnes-2.0-flash RESTORED. big-pickle also RESTORED. Major status shift.** |

### Workaround
No chat model workaround needed anymore — agnes-2.0-flash restored. Monitor for recurrence.

---

## Groq

### llama-4-scout-17b-16e-instruct
- **Status:** ❌ 404 model_not_found
- **Error:** `"The model \`llama-4-scout-17b-16e-instruct\` does not exist or you do not have access to it."`
- **Action:** Remove from fallback chain. Try alternative model names if Groq is still desired.

---

## OpenRouter

### Claude Sonnet 4 Fallback
- **Status:** ❌ Key broken (stored as 13 chars `sk-or-...886f`)
- **Expected length:** 50+ chars for OpenRouter keys
- **Error:** "Missing Authentication header" (401)
- **Root cause:** Key was truncated when originally written to `.env`, not Hermes redaction artifact
- **Action:** Re-obtain full key from OpenRouter dashboard and rewrite `.env`. Until then, exclude from fallback.

---

## Active Provider Chain (2026-07-23)

```
1. opencode/big-pickle          ← 主力 (was dead since May 2026, RESTORED)
2. custom:agnes/agnes-2.0-flash ← 第一冗餘 (was timeout, RESTORED)
3. opencode/deepseek-v4-flash-free ← 免費兜底
```

**Excluded providers:**
- `agnes-1.5-flash` (503), `qwen/qwen3-32b` (503) — Agnes distributor issue
- `llama-4-scout-17b-16e-instruct` (Groq, 404)
- `claude-sonnet-4` (OpenRouter, 401)
