# Graphify Installation on Hermes RPi4 Docker

## Quick Reference

| Item | Value |
|------|-------|
| CLI binary | `/opt/data/.xdg/bin/graphify` |
| Skill path | `/opt/data/skills/graphify/SKILL.md` |
| Version | 0.9.29 (as of 2026-07-29) |
| Python deps | 30 packages (networkx, numpy, tree-sitter +20 language parsers) |
| Author | safishamsi (YC S26) |
| License | Apache 2.0 |
| URL | https://github.com/Graphify-Labs/graphify |

## Features

- **Code → Knowledge Graph** — Tree-sitter AST parses 36 languages locally, free, no API key
- **Docs/PDF/Image/Video** — LLM semantic extraction (needs API key)
- **Obsidian Export** — `--obsidian` flag produces a vault-ready folder with wikilinks
- **3 Outputs:** `graph.html` (interactive), `graph.json` (queryable), `GRAPH_REPORT.md` (summary)
- **Confidence Tags:** Every edge tagged `EXTRACTED` / `INFERRED` / `AMBIGUOUS`

## Usage on RPi4

**Setup environment first (every new shell):**
```bash
export HOME=/opt/data
export XDG_DATA_HOME=/opt/data/.xdg/data
export XDG_CACHE_HOME=/opt/data/.xdg/cache
export PATH="/opt/data/.xdg/bin:$PATH"
```

**Build graph (code only, no API key):**
```bash
cd /path/to/project
graphify . --code-only
# Output in ./graphify-out/
```

**Build graph with docs (needs API key):**
```bash
export GEMINI_API_KEY="your-key-here"   # or ANTHROPIC_API_KEY, OPENAI_API_KEY
graphify /opt/data/obsidian-vault --obsidian
```

**Incremental update (code changes only, fast):**
```bash
graphify update /path/to/project
```

**Query existing graph (zero tokens):**
```bash
graphify query "how does auth connect to the database"
graphify path "ModuleA" "ModuleB"
graphify explain "APIRouter"
```

## Hermes Skill Integration

The skill at `/opt/data/skills/graphify/SKILL.md` is based on `skill-claw.md` from the graphifyy package. It registers the `/graphify` command handler. When you type `/graphify .` in a conversation, Hermes will:

1. Run the graphify CLI to build/extract
2. Read `graphify-out/GRAPH_REPORT.md` for highlights
3. Answer follow-up queries using `graph.json` instead of re-reading files

**Known issue (fixed in v0.8.50+):** Earlier versions of the Hermes skill would loop asking for an API key. Current version (0.9.29) has an explicit "no API key needed" preamble for code-only projects.

## Obsidian Export Details

```bash
graphify /opt/data/obsidian-vault --obsidian
```

Produces `graphify-out/obsidian/` containing:
- Each concept = one `.md` file with wikilinks to related concepts
- `graph.canvas` = Obsidian Canvas visual file
- Backlinks automatically created for all `EXTRACTED` / `INFERRED` relationships

**Integration patterns:**
1. **Standalone vault** — open `graphify-out/obsidian/` as its own vault
2. **Quarantine dump** — copy into main vault as `graph-imports/<project>/` subfolder
3. **Full redistribution** — merge concept stubs + source docs into main vault

## Pitfalls

- `graphify install --platform hermes` tries to write to `/root/.hermes/skills/` — cannot use. Manual copy only.
- `graphify .` without `--code-only` errors if no API key is set on a mixed-codebase
- Tool version `0.9.29` was latest as of 2026-07-29 — check for newer releases (doubled in version number since 0.4.9 in 2 months)
