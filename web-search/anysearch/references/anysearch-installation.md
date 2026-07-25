# AnySearch Skill Installation

Installed 2026-07-14 from https://github.com/anysearch-ai/anysearch-skill/releases/tag/v2.1.0

## Installation Steps

1. Clone the repo:
   ```bash
   cd /opt/data && git clone --depth 1 --branch v2.1.0 https://github.com/anysearch-ai/anysearch-skill.git /tmp/anysearch-skill
   ```

2. Copy to skills directory:
   ```bash
   mkdir -p /opt/data/skills/web-search/anysearch
   cp /tmp/anysearch-skill/SKILL.md /opt/data/skills/web-search/anysearch/
   cp -r /tmp/anysearch-skill/scripts /opt/data/skills/web-search/anysearch/
   cp /tmp/anysearch-skill/runtime.conf.example /opt/data/skills/web-search/anysearch/runtime.conf
   cp /tmp/anysearch-skill/.env.example /opt/data/skills/web-search/anysearch/.env.example
   ```

3. Auto-detect runtime and write `runtime.conf`:
   ```bash
   cat > /opt/data/skills/web-search/anysearch/runtime.conf << 'EOF'
   Runtime: python3
   Command: python3 /opt/data/skills/web-search/anysearch/scripts/anysearch_cli.py
   EOF
   ```

4. Verify:
   ```bash
   python3 scripts/anysearch_cli.py doc 2>&1 | head -10
   ```

## API Key Setup

AnySearch supports anonymous access (lower rate limits) or API key via:
- `.env` file: `ANYSEARCH_API_KEY=<key>` in skill directory
- Environment variable: `export ANYSEARCH_API_KEY=<key>`
- CLI flag: `--api_key <key>`

Key priority: `--api_key` > `.env` > env var > anonymous

## Key Files

- `SKILL.md` — full skill specification
- `scripts/anysearch_cli.py` — Python CLI (primary runtime)
- `scripts/anysearch_cli.js` — Node.js CLI (fallback)
- `scripts/anysearch_cli.sh` — Bash CLI (tertiary fallback)
- `scripts/anysearch_cli.ps1` — PowerShell CLI (Windows fallback)
- `runtime.conf` — detected runtime configuration
- `.env.example` — template for API key
- `scripts/shared/` — shared domain constants and doc specs

## Known Issues

- Anonymous access works but has lower rate limits
- API key must be in `.env` or env var for cron jobs (dashboard input is NOT sufficient)
