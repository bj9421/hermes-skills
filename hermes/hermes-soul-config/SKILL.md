---
name: hermes-soul-config
description: Manage Hermes Agent SOUL.md — the primary agent identity file. Covers where it lives, how Hermes loads it, verification, editing, and cleanup of stale copies.
---

# Hermes SOUL.md Configuration

## Description

SOUL.md is the agent's identity — slot #1 in the system prompt. It defines who the agent is, how it speaks, and what it avoids. This skill covers the SOUL.md loading architecture, verification, editing, and cleanup of orphaned copies.

---

## Where SOUL.md Lives

Hermes reads SOUL.md **only** from **`$HERMES_HOME/SOUL.md`** (the root of the Hermes home dir).
⚠️ **NOT** `$HERMES_HOME/.hermes/SOUL.md` — the code does `get_hermes_home() / "SOUL.md"`.

| Path | Read by Hermes? | Notes |
|------|:--------------:|-------|
| `$HERMES_HOME/SOUL.md` | ✅ **Yes** | Slot #1 identity. Read by `load_soul_md()` in `prompt_builder.py`. |
| `$HERMES_HOME/.hermes/SOUL.md` | ❌ **No** | Common trap — file exists but Hermes never reads it. |
| `./SOUL.md` (when cwd == HERMES_HOME) | ✅ **Yes** | It *is* the real one when working dir === HERMES_HOME. |
| `./SOUL.md` (when cwd ≠ HERMES_HOME) | ❌ No | CWD not equal to HERMES_HOME → ignored. |
| Profile (`profiles/<name>/SOUL.md`) | ❌ No | Only read if that profile has its own `HERMES_HOME`. |

**How to find the active one:**
```bash
echo "HERMES_HOME=$HERMES_HOME"
# The active SOUL.md is at:
ls -la "$HERMES_HOME/SOUL.md"
# NOT at: $HERMES_HOME/.hermes/SOUL.md
```

---

## How Hermes Loads SOUL.md

- SOUL.md occupies **slot #1** in the cached system prompt (agent identity).
- If SOUL.md exists and has content → injected verbatim after security scanning (prompt injection check + truncation, default cap 20K chars).
- If SOUL.md is empty, whitespace-only, or missing → Hermes falls back to hardcoded `DEFAULT_AGENT_IDENTITY` ("You are Hermes Agent, an intelligent AI assistant created by Nous Research...").
- The `build_context_files_prompt()` function is called with `skip_soul=True` to prevent SOUL.md from appearing twice (once as identity, once as a context file).
- When `skip_context_files` is set (e.g., subagent delegation), SOUL.md is **not** loaded and the hardcoded fallback is used instead.

**Prompt assembly order:**
```
stable: identity (SOUL.md or fallback) → tool/model guidance → skills prompt → env hints → platform hints
context: caller system_message + project context files (AGENTS.md, etc.)
volatile: memory snapshot, user profile, timestamp/session/model line
```

---

## What Should Go in SOUL.md

**Good for SOUL.md (durable identity):**
- Tone and communication style
- Level of directness (concise vs explanatory)
- Default interaction style
- What to avoid stylistically
- How the agent should handle uncertainty/disagreement
- Model-specific behavior guidance (e.g., preference for Chinese output)

**NOT for SOUL.md (belongs in AGENTS.md or memory):**
- One-off project instructions
- File paths and repo conventions
- Temporary workflow details
- Task-specific instructions

**Key distinction:** SOUL.md defines *who the agent is*; AGENTS.md defines *what the project needs*. If it should follow you everywhere, it belongs in SOUL.md. If it belongs to a project, it belongs in AGENTS.md.

---

## Stale Copy Detection & Cleanup

Multiple SOUL.md files can accumulate in different directories. Most are **not read by Hermes** and will confuse anyone looking for the active one.

**To audit:**
```bash
# Find all SOUL.md files
find "$HERMES_HOME" -name 'SOUL.md' -o -name 'soul.md' 2>/dev/null

# Identify the active one
echo "HERMES_HOME=$HERMES_HOME"
ls -la "$HERMES_HOME/SOUL.md"
# ⚠️ The file at $HERMES_HOME/.hermes/SOUL.md is NOT read by Hermes
```

**To clean up stale copies:**
```bash
mv /path/to/stale/SOUL.md /path/to/stale/SOUL.md.nouse
```
Never delete — always rename to `.nouse` so recovery is possible if the user later wants it.

---

## Verification

After editing SOUL.md, verify it loads correctly:
1. Start a new session (SOUL.md is read at session start, not mid-session)
2. The agent's voice should reflect the changes in the first response
3. Or check the prompt assembly logs if available

---

## Pitfalls

- **⚠️ SOUL.md location trap:** The code reads `$HERMES_HOME/SOUL.md`, **not** `$HERMES_HOME/.hermes/SOUL.md`. A common mistake is placing SOUL.md inside `.hermes/` and wondering why the identity doesn't take effect. Always edit `$HERMES_HOME/SOUL.md` (the root of HERMES_HOME).
- **⚠️ Auto-regeneration after cleanup (confirmed root cause):** `_ensure_default_soul_md()` in `config.py` writes `DEFAULT_SOUL_MD` (English identity, 513 bytes) to `$HERMES_HOME/SOUL.md` whenever the file is missing. This is called at every startup via `ensure_hermes_home()`. So moving/removing `$HERMES_HOME/SOUL.md` is temporary — the init path will rewrite it. To stop regeneration, write custom content to `$HERMES_HOME/SOUL.md` (the presence check is: if file exists and is NOT a legacy empty template, skip write). See `references/auto-regeneration-behavior.md`.
- **⚠️ Profile SOUL.md is NOT read by default:** A SOUL.md in `profiles/<name>/` is only active if that profile has its own `HERMES_HOME` environment variable pointing to a different base directory. Unless you explicitly set that up, profile SOUL.md files are dead files.
- **⚠️ Stale copies confuse debugging:** If the user asks "which SOUL.md is being used" and there are multiple copies, always check `$HERMES_HOME` first before reading any file.
- **⚠️ Recurring symptoms = investigate root cause, don't just move the file:** When a file reappears after cleanup, read the source code that writes it (`_ensure_default_soul_md` in `config.py`, called from `ensure_hermes_home` at startup). Moving/renaming is temporary — writing custom content to the correct path is permanent. This lesson applies broadly: any system artifact that keeps regenerating needs code-level investigation, not surface-level treatment.
- **⚠️ SOUL.md ≠ /personality:** SOUL.md is the durable default identity. `/personality` is a session-level overlay (temporary mode switch). They coexist — SOUL.md is the baseline, `/personality` tweaks it for one session.
- **⚠️ SOUL.md ≠ AGENTS.md:** SOUL.md is for identity/voice. AGENTS.md is for project-specific instructions. Putting file paths and task instructions in SOUL.md is a misuse and will make the identity unstable across contexts.

## SOUL.md Content Patterns

Based on real usage, here are the categories of content that belong in SOUL.md:

| Category | What to put | Example |
|----------|-------------|---------|
| **Identity & Tone** | How the agent should present itself | Name, role, communication style |
| **Style Rules** | Formatting preferences, output structure | "Concise, bullet points, avoid filler" |
| **Behavioral Guardrails** | Verification requirements, refusals | "Verify before answering uncertain Qs" |
| **Safety Gates** | Approval gates, denied actions | "Ask before shell commands" |
| **Technical Constraints** | Hardware limits, environment rules | "No sustained 100% CPU > 5 min" |

**Key insight:** behavioral guardrails belong in SOUL.md, not just memory. SOUL.md is read every session into the stable identity slot. Verification rules like "cross-check 1-2 sources before answering uncertain questions" are more reliable in SOUL.md than in memory alone (memory can be stale, reorganized, or capped).

## Docker Container Pitfalls

In Docker environments, `Path.home()` resolves to the **container user's home**, which may differ from what one expects:

```
Container user `hermes`, home=`/home/hermes_data`:
  Path.home() = /home/hermes_data
  get_hermes_home() = /home/hermes_data/.hermes
  Real SOUL.md = /home/hermes_data/.hermes/SOUL.md
```

**The `.hermes/` subdirectory assumption is the #1 trap:** `get_hermes_home()` already returns a path that ends with `.hermes` (it's `Path.home() / ".hermes"`), so appending `.hermes/` again would be wrong. Always verify with:

```python
python3 -c "from hermes_constants import get_hermes_home; print(get_hermes_home() / 'SOUL.md')"
```

## Auto-Regeneration Detail

When `$HERMES_HOME/SOUL.md` is missing at startup, `_ensure_default_soul_md()` in `config.py` writes the hardcoded 513-byte English default (`DEFAULT_SOUL_MD`). The guard is:

```python
if not is_legacy_template_soul(existing):
    return  # Custom content → left alone
```

So writing your own content to the correct path is a permanent fix — `_ensure_default_soul_md` won't overwrite it.

## References
- See `references/location-discovery.md` for the original SOUL.md location discovery (corrected).
- See `references/auto-regeneration-behavior.md` for the confirmed auto-regeneration root cause.
- See `references/soul-content-patterns.md` for a full SOUL.md example with verification guardrails.
- Official docs: https://hermes-agent.nousresearch.com/docs/user-guide/features/personality/
- Related: `hermes-provider-config` for model/provider settings, `hermes-global-config` for API keys.
