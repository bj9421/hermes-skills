# AnySearch REST API — Direct cURL Usage

When the bundled CLI scripts (`anysearch_cli.py`, `.js`, `.sh`) are unavailable or not on `$PATH`, the AnySearch API can be called directly via HTTP.

## Base URL

```
https://api.anysearch.com/v1/search
```

## Authentication

Pass the API key as a Bearer token:

```
Authorization: Bearer $ANYSEARCH_API_KEY
```

Anonymous access works with lower rate limits (omit the header).

## Search Request

```bash
curl -s "https://api.anysearch.com/v1/search" \
  -H "Authorization: Bearer $ANYSEARCH_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query":"your search terms","max_results":5}'
```

| Field         | Type   | Required | Default | Description |
|---------------|--------|----------|---------|-------------|
| `query`       | string | yes      | —       | Search query |
| `max_results` | int    | no       | 10      | Results to return (1–10) |

## Response Shape

```json
{
  "data": {
    "results": [
      {
        "title": "Result Title",
        "url": "https://example.com/page",
        "snippet": "Description or excerpt..."
      }
    ]
  }
}
```

## Parse in Python

```python
import subprocess, json

def anysearch(query, max_results=5):
    cmd = [
        "curl", "-s", "https://api.anysearch.com/v1/search",
        "-H", "Authorization: Bearer $ANYSEARCH_API_KEY",
        "-H", "Content-Type: application/json",
        "-d", json.dumps({"query": query, "max_results": max_results})
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(result.stdout)
    return data["data"]["results"]

# Usage
for r in anysearch("台灣觀光資訊"):
    print(f"{r['title']} → {r['url']}")
```

> **Note:** The `$ANYSEARCH_API_KEY` environment variable must be set. On Hermes, test with `echo $ANYSEARCH_API_KEY`. If empty, export it first or pass the raw key in the `-H` header.

## Pitfalls

- **Trailing slash:** The path `/v1/search` — NOT `/v1/search/` — is the correct endpoint.
- **Not `/v1/chat/completions`:** That endpoint returns 404. This is **not** an OpenAI-compatible chat API.
- **HTTP/1.1 vs HTTP/2:** Some networks (Cloudflare) may block HTTP/2 from `urllib` — always use `curl -s` which defaults to HTTP/1.1 over modern libcurl.
- **`ANYSEARCH_API_KEY` env var:** Set it in `.env` for background/cron jobs; dashboard keys don't propagate to cron sessions.
- **Results may be truncated:** `snippet` is usually short. Use `mcp_duckduckgo_fetch_content` or the `extract` subcommand for full-page content.
