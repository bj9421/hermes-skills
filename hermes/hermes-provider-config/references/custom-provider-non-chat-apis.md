# Using Custom Provider Non-Chat APIs (Image Gen, TTS, Embeddings, etc.)

Custom providers defined via `custom_providers:` (e.g. Agnes, Groq, local Ollama) may expose OpenAI-compatible APIs **beyond chat completions** — image generation, text-to-speech, embeddings, etc. However, Hermes built-in tools (`image_generate`, `tts`, etc.) only support a **fixed set of plugin-registered backends** — custom providers registered as `api_mode: chat_completions` are **not** automatically available for these tools.

## The Pattern

When you want to use a custom provider's non-chat capabilities:

1. **Identify the provider's API endpoint** for that capability (usually `/v1/images/generations`, `/v1/audio/speech`, `/v1/embeddings`, etc.)
2. **Write a shell script** that calls the API directly via `curl`, using the same `Authorization: Bearer $KEY` header and OpenAI-compatible request body
3. **Save the script** under `/opt/data/scripts/` for reuse
4. **Run from terminal** or ask the agent to run it

## Worked Example: Agnes Image Generation

### Background

The user has `agnes` configured as a `custom_providers:` entry with `agnes-image-2.1-flash` and `agnes-image-2.0-flash` models. But `image_generate` tool doesn't support `custom:agnes` as an image gen backend — it only supports plugin-registered backends (openai-codex, fal, krea, openai, xai).

### Solution

Script at `/opt/data/scripts/agnes_image.sh`:

```bash
#!/bin/bash
# Usage: ./scripts/agnes_image.sh "prompt" [model]
PROMPT="$1"
MODEL="${2:-agnes-image-2.1-flash}"
API_KEY="${AGNES_API_KEY}"

curl -s https://apihub.agnes-ai.com/v1/images/generations \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"model\": \"$MODEL\", \"prompt\": \"$PROMPT\", \"n\": 1, \"size\": \"1024x1024\"}"
```

### Response Format

Agnes returns OpenAI-compatible format:

```json
{
  "data": [
    {"url": "https://platform-outputs.agnes-ai.space/images/t2i/..."}
  ]
}
```

The script downloads the URL to `/opt/data/agnes_images/<timestamp>.png`.

### Image Storage

- Output directory: `/opt/data/agnes_images/`
- Filename pattern: `agnes_YYYYMMDD_HHMMSS.png`
- Created automatically by the script

### Invoking from Chat

User can say "用 Agnes 生一張..." and the agent runs:
```bash
cd /opt/data && ./scripts/agnes_image.sh "prompt in Chinese"
```

## Known `image_gen` Supported Backends

Only these plugin-registered backends work with the `image_generate` tool:

| Plugin | Provider Config | Models |
|--------|----------------|--------|
| `openai-codex` | `provider: openai-codex` | `gpt-image-2-medium` |
| `openai` | `provider: openai` | DALL-E 3 |
| `fal` | `provider: fal` | flux-2-klein, flux-2-pro, nano-banana, gpt-image-1.5 |
| `krea` | `provider: krea` | Krea 2 Large, Medium, Turbo |
| `xai` | `provider: xai` | (video generation) |

None of these are free — all are pay-per-use or subscription-based.

## Extending the Pattern

The same approach works for any OpenAI-compatible non-chat endpoint:

| API | Typical Endpoint | Example Use |
|-----|-----------------|-------------|
| Image Gen | `/v1/images/generations` | DALL-E compatible providers |
| TTS | `/v1/audio/speech` | ElevenLabs, OpenAI-compatible TTS |
| Embeddings | `/v1/embeddings` | text-embedding-3-small compatible |
| STT | `/v1/audio/transcriptions` | Whisper-compatible providers |

## Pitfalls

- **Rate limits**: Custom provider image APIs may have stricter rate limits than chat endpoints
- **Auth**: Always use `key_env` pattern in config and reference in scripts via `$KEY_ENV_VAR`
- **No streaming**: Image gen is always a single POST request → wait for response (5-30s typical)
- **Cost**: Verify pricing before heavy use; most image gen APIs are not free
