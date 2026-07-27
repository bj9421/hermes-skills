---
name: agnes-image-generation
description: Generate images using Agnes AI Image API (agnes-image-2.1-flash). Text-to-image and image-to-image.
version: 1.0.0
triggers:
  - image generation
  - agnes image
  - generate image
  - text to image
  - 圖片生成
  - 生成圖片
---

# Agnes Image Generation

Generate images via Agnes AI's free image API.

## Endpoint

```
POST https://apihub.agnes-ai.com/v1/images/generations
```

## Authentication

```
Authorization: Bearer $AGNES_API_KEY
```

API key from `.env` file (`AGNES_API_KEY`).

## Required Parameters

| Param | Type | Description |
|-------|------|-------------|
| `model` | string | `agnes-image-2.1-flash` |
| `prompt` | string | Image description |
| `size` | string | `1K`, `2K`, `3K`, `4K` or exact like `1024x1024` |

## Optional Parameters

| Param | Type | Description |
|-------|------|-------------|
| `ratio` | string | `1:1`, `3:4`, `4:3`, `16:9`, `9:16`, `2:3`, `3:2`, `21:9` |
| `return_base64` | bool | `true` → returns base64 in `data[0].b64_json` |
| `extra_body.response_format` | string | `"url"` or `"b64_json"` — **must be inside `extra_body`** |

## ⚠️ Critical Rules

1. **`response_format` goes inside `extra_body`**, NOT at the top level — top-level placement causes 400 error
2. **`size` is required** — omitting it causes request to hang/timeout
3. For image-to-image: pass input images via `extra_body.image` array (not top-level `image`)
4. Timeout: 60–360 seconds depending on complexity

## Curl Examples

### Text-to-image (URL output)
```bash
source /opt/data/.env
curl -s -o output.png \
  -X POST "https://apihub.agnes-ai.com/v1/images/generations" \
  -H "Authorization: Bearer $AGNES_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "agnes-image-2.1-flash",
    "prompt": "A luminous floating city above a misty canyon at sunrise",
    "size": "1K",
    "ratio": "16:9",
    "extra_body": {
      "response_format": "url"
    }
  }'
# URL is at data[0].url in response
```

### Text-to-image (Base64 output)
```bash
source /opt/data/.env
curl -s response.json \
  -X POST "https://apihub.agnes-ai.com/v1/images/generations" \
  -H "Authorization: Bearer $AGNES_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "agnes-image-2.1-flash",
    "prompt": "A clean product photo on white background",
    "size": "1K",
    "return_base64": true
  }'
# Base64 at data[0].b64_json
```

### Image-to-image
```bash
source /opt/data/.env
curl -s response.json \
  -X POST "https://apihub.agnes-ai.com/v1/images/generations" \
  -H "Authorization: Bearer $AGNES_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "agnes-image-2.1-flash",
    "prompt": "Transform into cyberpunk night with neon reflections",
    "size": "1K",
    "extra_body": {
      "image": ["https://example.com/input.png"],
      "response_format": "url"
    }
  }'
```

## Response Format

```json
{
  "created": 1785123143,
  "data": [{
    "url": "https://platform-outputs.agnes-ai.space/images/xxx.png",
    "b64_json": null
  }],
  "usage": { "total_tokens": 0 }
}
```

## Pricing

$0.003/image (effectively free for personal use).

## Models

| Model | Best for |
|-------|----------|
| `agnes-image-2.1-flash` | Complex scenes, high detail, image editing |
| `agnes-image-2.0-flash` | Multi-image composition, creative design |
