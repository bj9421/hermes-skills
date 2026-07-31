---
name: knowledge-graph-pipeline
description: "Use when building a knowledge graph from a local corpus of code files, documents, markdown notes, or an Obsidian vault. Covers Graphify setup and configuration with custom LLM providers (Groq, OpenRouter, NVIDIA NIM), RPi4/Docker environment setup, rate-limit tuning, and output format generation (Obsidian vault, HTML, JSON)."
tags: ["graphify", "knowledge-graph", "obsidian", "rpi4", "llm-provider"]
related_skills: ["graphify"]
---

# Knowledge Graph Pipeline

Build a persistent, queryable knowledge graph from a local folder of code, markdown documents, PDFs, images, or an entire Obsidian vault. Uses [Graphify](https://github.com/Graphify-Labs/graphify) under the hood.

## When to use

- User has a codebase or document collection and wants a navigable knowledge graph with community detection
- User wants to convert an Obsidian vault into an interconnected knowledge graph with `[[wikilinks]]`
- User wants to query a codebase structurally without reading every file
- User asks "can this tool work on RPi4/Docker?" — this skill covers the platform-specific setup

## Environment setup (RPi4 / Docker)

The Hermes Docker container needs explicit environment variables because HOME is not writable. **Proven working invocation on this machine** (binary at `/opt/data/.xdg/bin/graphify`):

```bash
export HOME=/opt/data
export XDG_DATA_HOME=/opt/data/.xdg
export XDG_CACHE_HOME=/opt/data/.xdg/cache
export XDG_STATE_HOME=/opt/data/.xdg/state
export PATH="/opt/data/.xdg/bin:$PATH"
```

The binary installs via `uv tool install graphifyy` under the hermes user's XDG dirs — do NOT rely on the system python (`No module named 'graphify'` in `/opt/hermes/.venv` is expected; the tool lives in the uv tool dir). Check `ls /opt/data/.xdg/bin/graphify` first.

## Install Graphify

```bash
# Install with API extras (needed for LLM-based semantic extraction)
uv tool uninstall graphifyy 2>/dev/null
uv tool install "graphifyy[openai]" --force
```

The `[openai]` extra is required for any OpenAI-compatible backend (Groq, OpenRouter, NVIDIA).

## Quick start — code-only (free, no API key)

```bash
cd /path/to/repo
graphify . --code-only --no-viz
```

Output: `graphify-out/graph.json`, `graphify-out/.graphify_analysis.json`

**Then run cluster-only to generate the report + name communities** (the code-only run stops after graph.json and explicitly prints "next: run `graphify cluster-only` to generate GRAPH_REPORT.md"):

```bash
graphify cluster-only /path/to/repo
```

Output: `graphify-out/GRAPH_REPORT.md` with God Nodes, Surprising Connections, Suggested Questions, and per-community cohesion scores.

No API key needed. Works on any corpus of supported languages (36 via Tree-sitter AST). For code-improvement analysis (not vault semantic extraction), `--code-only` is the right choice — AST gives the full function-dependency graph and community cohesion, which is exactly what refactoring decisions need.

## Recommended provider: Agnes 2.5-flash (fast, free, proven)

For semantic extraction on vault-sized corpora, Agnes 2.5-flash is the best tested option:

```json
{
  "agnes": {
    "base_url": "https://apihub.agnes-ai.com/v1",
    "default_model": "agnes-2.5-flash",
    "env_key": "AGNES_API_KEY",
    "model_env_key": "GRAPHIFY_AGNES_MODEL",
    "max_tokens": 32768,
    "temperature": 0,
    "vision": true
  }
}
```

**Proven performance:** 82 Obsidian notes extracted in ~2 minutes, producing 118 nodes and 176 edges with no rate-limit issues. Use `--max-concurrency 3` for optimal throughput.

Agnes 2.0-flash is a reliable fallback if 2.5 is unavailable. The API key lives in a standard env var (`AGNES_API_KEY`).

## Custom LLM provider setup (for docs/papers/images)

Docs, papers, and images need an LLM for semantic entity extraction. Create `~/.graphify/providers.json`:

```json
{
  "mygroq": {
    "base_url": "https://api.groq.com/openai/v1",
    "default_model": "llama-3.3-70b-versatile",
    "env_key": "GROQ_API_KEY",
    "max_tokens": 16384,
    "temperature": 0,
    "vision": true
  }
}
```

Required fields:
- `base_url` — any OpenAI-compatible API endpoint
- `default_model` — model identifier
- `env_key` — env var name holding the API key (read via `os.environ[env_key]`)
- `max_tokens` — max output tokens
- `vision` — set `true` if model supports image input (avoids 400 errors on images)

### Provider alternatives

| Provider | Key env var | TPM limit (free) | Notes |
|----------|-------------|-----------------|-------|
| **Groq** | `GROQ_API_KEY` | 12k (70B), 6k (8B) | Fast inference, very tight TPM |
| **OpenRouter** | `OPENROUTER_API_KEY` | varies | Key must be complete (not truncated) |
| **NVIDIA NIM** | `NVIDIA_API_KEY` | unknown higher | Untested on this setup |

## Rate limit tuning

Groq free tier TPM limits cause 413 errors on vault-sized corpora. **Switch to Agnes 2.5-flash instead** — no rate limit issues on vault-scale extraction.

If you must use a rate-limited provider, tune with these flags:

```bash
graphify . --backend <name> \
  --model "model-id" \
  --token-budget 2000 \
  --max-concurrency 1 \
  --api-timeout 120
```

| Parameter | Effect |
|-----------|--------|
| `--token-budget N` | Controls chunk size (2000 recommended for TPM-limited APIs) |
| `--max-concurrency 1` | Serializes requests to avoid burst rate limits |
| `--api-timeout 120` | Prevents timeout on slow model responses |

Even with tuning, Groq free tier is insufficient for vaults with ~50+ files. Use Agnes for vault-scale work.

## Obsidian vault knowledge graph

```bash
cd /opt/data/obsidian-vault

# Full semantic extraction (requires configured provider)
graphify . --obsidian --backend agnes \
  --model "agnes-2.5-flash" \
  --max-concurrency 3

# Name communities (separate step after extraction)
graphify cluster-only . --backend agnes \
  --model "agnes-2.5-flash" --no-viz
```

Output:
- `graphify-out/graph.json` — raw graph data for querying (118+ nodes)
- `graphify-out/GRAPH_REPORT.md` — community analysis with god nodes, surprising connections
- `graphify-out/.graphify_labels.json` — community name mapping
- `graphify-out/manifest.json` — file change tracking for incremental updates

No HTML or Canvas is generated by default when using CLI directly (use `graphify` full pipeline for those).

## Graphify-driven refactoring workflow (code improvement loop)

Proven on bookmark-manager (app.py 766 lines → 18-line entry, cohesion 0.10 → 0.21~0.31). Use when the goal is *improving* a codebase, not just mapping it:

1. **Full code-only scan** (no API key):
   ```bash
   graphify . --code-only --no-viz
   graphify cluster-only /path/to/repo     # generates GRAPH_REPORT.md with cohesion scores
   ```
2. **Read GRAPH_REPORT.md** — the refactoring candidate is the community with the LOWEST cohesion (e.g. app.py at 0.10). Ignore minified third-party files (htmx.min.js etc.) that pollute god-node lists; the real signal is per-community cohesion on your own modules. `bookmark.py` at 0.39 was the "good example" to imitate.
3. **User workflow requirement (this user demands it):** BEFORE touching code — (a) open/verify git, (b) commit a baseline snapshot (`git add -A && git commit` including graphify-out + verification scripts), (c) present a written split plan, (d) build a checkpoint list with the todo tool, (e) get explicit user confirmation. Never start a refactor without this gate.
4. **Split pattern for Flask monoliths** (keep original logic byte-identical, only change import sources):
   - `db.py` — data layer (get_db, row mappers, query helpers, filters)
   - `<service>.py` — one service module per concern (e.g. llm_enhance.py)
   - `routes_*.py` — Flask Blueprints, one per domain (bookmarks, tags)
   - `app.py` — slim entry: create app + register blueprints + startup (<50 lines)
5. **Verify no regression BEFORE committing:** curl sweep every endpoint — GET pages, POST create, PUT/PATCH update, DELETE, batch, export — all must return 200. Use a test bookmark and delete it after. This catches import/blueprint mistakes immediately.
6. **Re-scan and prove improvement:** `graphify update .` (NOTE: `update` does NOT accept `--no-viz` — "unknown update option"). Compare per-community cohesion before/after; expect 2–3x improvement and more communities (monolith nodes get distributed).
7. **Commit** with descriptive Traditional Chinese message, listing the split + cohesion delta.

## Incremental updates

When vault content changes, only re-extract new/changed files:

```bash
graphify . --update --obsidian --backend agnes --model "agnes-2.5-flash"
```

## Queries against the built graph

Once `graphify-out/graph.json` exists, query it directly without re-extraction:

```bash
graphify query "台股資料來源有哪些"    # BFS traversal
graphify path "東港" "小琉球"         # Shortest path
graphify explain "Hermes Agent"       # Node explanation
graphify god-nodes                    # Most connected concepts
```

## Troubleshooting

| Error | Likely cause | Fix |
|-------|-------------|-----|
| `ModuleNotFoundError: openai` | Missing extra | Reinstall with `uv tool install "graphifyy[openai]" --force` |
| `401 Unauthorized` | API key missing/wrong | Check `env_key` in providers.json matches exported env var |
| `413 Request too large (TPM)` | Rate limited | Switch to Agnes; or add `--token-budget 2000 --max-concurrency 1` |
| `500 Internal Server Error: unknown variant` | Vision sent to non-vision model | Set `vision: false` in provider config (NVIDIA NIM) |
| `400 messages[1].content must be a string` | Image content misformatted | Verify `vision: true` in provider config |
| `backend X requires X_API_KEY to be set` | Env var not exported | Read + export key inline before `graphify` |
| Permission denied on `/root/` | HOME not set | `export HOME=/opt/data` |
| `No module named 'graphify'` | Graphify not installed | Run install step above |

## Pitfalls

- **Don't** pass `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` — Graphify only reads `GEMINI_API_KEY` (for built-in Gemini backend) or custom providers via `providers.json`
- **Don't** run `graphify install --platform hermes` — it writes to `~/.hermes/` ignoring `$HERMES_HOME`. Manually copy the skill from site-packages instead
- **Don't** expect Groq free tier to handle vaults with 50+ files — TPM limits make extraction impractical without paying
- **Don't** forget the environment variables — every invocation needs `HOME=/opt/data` and `PATH` set
- **Don't** pipe the API key into a background process without exporting it inline — background shells don't inherit aliases or prior `export` commands. Use `export X_KEY=$(grep ...); graphify ...` in the same command string