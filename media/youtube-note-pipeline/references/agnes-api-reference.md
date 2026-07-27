# Agnes AI Image API — Session Reference

Collected 2026-07-27 during integration into yt2md pipeline.

## API Surface

- **Endpoint:** `POST https://apihub.agnes-ai.com/v1/images/generations`
- **Auth:** `Authorization: Bearer $AGNES_API_KEY`
- **Models:** `agnes-image-2.1-flash` (recommended), `agnes-image-2.0-flash` (multi-image)
- **Pricing:** $0.003/image (effectively free)

## Required Params

| Param | Type | Notes |
|-------|------|-------|
| `model` | string | `agnes-image-2.1-flash` |
| `prompt` | string | English recommended. CJK in prompt is OK but output text will be garbled. |
| `size` | string | **REQUIRED.** Omit = silent timeout. Use tiers: `1K`, `2K`, `3K`, `4K`. |

## Optional Params

| Param | Type | Notes |
|-------|------|-------|
| `ratio` | string | `1:1`, `3:4`, `4:3`, `16:9`, `9:16`, `2:3`, `3:2`, `21:9` |
| `return_base64` | bool | Top-level. Returns `data[0].b64_json`. |
| `extra_body.response_format` | string | `"url"` or `"b64_json"`. **MUST be inside `extra_body`.** |
| `extra_body.image` | string[] | For image-to-image. Public URLs or Data URI Base64. |

## Size → Actual Output Mapping

Tested 2026-07-27:

| Request | Actual Pixels | Notes |
|---------|--------------|-------|
| `1920x1080` | 1312×736 | **Normalized!** Exact pixels not supported. |
| `1K` + `16:9` | ~1312×736 | Same as above. |
| `2K` + `16:9` | 2624×1472 | ✅ Best landscape option. |
| `2K` + `3:4` | 1728×2304 | ✅ Best portrait option. |
| `2K` + `1:1` | ~2048×2048 | Square. |
| `3K` + `16:9` | ~3936×2208 | Very large. |
| `4K` + `16:9` | ~5248×2944 | Maximum. |

**Rule:** Always use tier-based `size` + explicit `ratio`. Never use exact pixel dimensions.

## Error Patterns

### HTTP 400: `UnsupportedParamsError`
```
Setting 'response_format' is not supported by openai
```
**Cause:** `response_format` placed at top level of request body.
**Fix:** Move to `extra_body.response_format`.

### Silent Timeout (no response)
**Cause:** `size` parameter missing from request.
**Fix:** Always include `size` (e.g. `"size": "2K"`).

### HTTP 404: `Function not found for account`
**Cause:** Model endpoint not available for your account tier.
**Note:** NVIDIA NIM free-tier image models all return this as of 2026-06. Agnes is the working alternative.

## CJK Text Limitation

All current image generation models (Agnes, NVIDIA NIM, Google Gemini) produce garbled/gibberish Chinese characters in generated images. The text appears as random strokes or incorrect characters.

**Workaround pattern:**
1. Generate text-free illustration via Agnes (English-only prompt, no text/letters/numbers in prompt)
2. Overlay Chinese text via Pillow with NotoSansSC font
3. Composite into final infographic

Implemented in `visual_gen.py` as `_composite_infographic()`.

## Response Format

```json
{
  "created": 1785123143,
  "data": [{
    "url": "https://platform-outputs.agnes-ai.space/images/xxx.png",
    "b64_json": null,
    "revised_prompt": null
  }],
  "usage": {"total_tokens": 0, "input_tokens": 0, "input_tokens_details": {"image_tokens": 0, "text_tokens": 0}}
}
```

**URL is temporary** — download immediately. `data[0].url` contains the image URL.

## Curl Template

```bash
source /opt/data/.env
curl -s -o output.png \
  -X POST "https://apihub.agnes-ai.com/v1/images/generations" \
  -H "Authorization: Bearer $AGNES_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "agnes-image-2.1-flash",
    "prompt": "TEXT-FREE illustration description in English",
    "size": "2K",
    "ratio": "16:9",
    "extra_body": {
      "response_format": "url"
    }
  }'
```

## Official Docs

- Image 2.1: https://wiki.agnes-ai.com/en/docs/agnes-image-21-flash.md
- Image 2.0: https://wiki.agnes-ai.com/en/docs/agnes-image-20-flash.md
- Model catalog: https://github.com/AgnesAI-Labs/AgnesAI-Models/blob/main/MODEL_CATALOG.md
- API reference: https://github.com/Selenium39/agnes-ai-skill/blob/master/agnes-ai-media/references/agnes-media-api.md
