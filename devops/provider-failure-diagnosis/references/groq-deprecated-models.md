# Groq Deprecated Models

## Deprecation Dates

### July 17, 2026
- `qwen/qwen3-32b` → 404
- `meta-llama/llama-4-scout-17b-16e-instruct` → 404

### August 16, 2026 (upcoming)
- `llama-3.1-8b-instant` → will be replaced by `openai/gpt-oss-20b`
- `llama-3.3-70b-versatile` → will be replaced by `openai/gpt-oss-120b` or `qwen/qwen3.6-27b`

## Replacement Models (Production, as of 2026-07-23)

| Old Model | Replacement | Context | Max Completion |
|-----------|-------------|---------|----------------|
| llama-3.3-70b-versatile | openai/gpt-oss-120b | 131K | 65,536 |
| llama-3.3-70b-versatile | qwen/qwen3.6-27b | 131K | 16,384 |
| llama-3.1-8b-instant | openai/gpt-oss-20b | 131K | 65,536 |

## Diagnostic Tip

When a model returns 404 or 400 from Groq:
1. Test another known-good model first (e.g., `openai/gpt-oss-120b`)
2. If the other model works → it's a deprecation, not a key/network issue
3. Check https://console.groq.com/docs/deprecations for official list
4. Update config to use replacement model
