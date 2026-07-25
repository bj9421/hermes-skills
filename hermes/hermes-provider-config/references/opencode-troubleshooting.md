# OpenCode Zen Provider — Troubleshooting Guide

## Overview

OpenCode Zen (`OPENCODE_ZEN_API_KEY`) is a built-in Hermes provider offering curated models including the free **big-pickle** model (alias for GLM-4.6 from Zhipu AI).

**Endpoint:** `https://api.opencode.ai/v1`
**Env var:** `OPENCODE_ZEN_API_KEY`

## Known Issues

### big-pickle Model Down (2026-05-18 onwards)

The `big-pickle` model has been unresponsive since May 2026. Multiple GitHub issues confirm:

| Issue | Description |
|-------|-------------|
| [#28138](https://github.com/anomalyco/opencode/issues/28138) | After upgrading v1.14→1.15.4, big-pickle throws "not supported for format anthropic" |
| [#28141](https://github.com/anomalyco/opencode/issues/28141) | Big Pickle returns `AI_APICallError`, stopped responding entirely |
| [#28146](https://github.com/anomalyco/opencode/issues/28146) | Desktop app v1.15.4: "Model big-pickle not supported for format anthropic" |

**Symptoms in Hermes:**
- HTTP 200 response but body is literally `"Not Found"`
- All model name variations fail: `big-pickle`, `bigpickle`, `opencode/big-pickle`
- API key is valid (TCP/TLS connection succeeds), but model endpoint is down

**Workaround:** Remove `big-pickle` from `fallback_providers` until upstream fixes it. Use alternative models like DeepSeek or other paid models via OpenCode Zen.

## Configuration

### Built-in Provider (no custom_providers entry needed)

OpenCode Zen is a built-in Hermes provider — no `custom_providers:` YAML entry required. Just set the env var:

```bash
export OPENCODE_ZEN_API_KEY=sk-...
```

Then reference it as `provider: opencode` in config:
```yaml
model:
  default: big-pickle
  provider: opencode
```

Or in fallback chain:
```yaml
fallback_providers:
  - model: big-pickle
    provider: opencode
```

## Diagnostic Checklist

1. **API key valid?** → `curl -s https://api.opencode.ai/v1/models -H "Authorization: Bearer $OPENCODE_ZEN_API_KEY"`
2. **Model available?** → If returns "Not Found", model may be deprecated/down
3. **Check GitHub issues** → anomalyco/opencode repo for known outages
4. **Try alternative model** → Test with a different model name to isolate if it's provider-wide or model-specific
