# GitHub API File Upload — No Git Repo Needed

## When to use

Files are on disk but:
- No local git repo
- `gh` CLI not installed
- Need to push one or two files quickly

## Quick pattern

```bash
# 1. Find the token (names vary by environment)
PAT=$(grep -E "^GITHUB_(PAT|TOKEN)=" /opt/data/.env 2>/dev/null | grep -v "^#" | head -1 | cut -d= -f2)

# 2. Upload (new file — no sha needed)
python3 -c "
import base64, json, urllib.request
pat = '$PAT'
with open('myfile.md', 'rb') as f:
    content_b64 = base64.b64encode(f.read()).decode()
data = json.dumps({
    'message': 'Add myfile.md',
    'content': content_b64
}).encode()
req = urllib.request.Request(
    'https://api.github.com/repos/OWNER/REPO/contents/myfile.md',
    data=data,
    headers={'Authorization': f'token {pat}', 'Accept': 'application/vnd.github.v3+json', 'Content-Type': 'application/json'},
    method='PUT'
)
resp = urllib.request.urlopen(req)
print(json.loads(resp.read())['commit']['sha'][:8])
"

# 3. Upload (update existing — need current sha)
CURRENT_SHA=$(curl -s -H "Authorization: token $PAT" \
  "https://api.github.com/repos/OWNER/REPO/contents/myfile.md" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['sha'])")

python3 -c "
import base64, json, urllib.request
pat = '$PAT'
with open('myfile.md', 'rb') as f:
    content_b64 = base64.b64encode(f.read()).decode()
data = json.dumps({
    'message': 'Update myfile.md',
    'content': content_b64,
    'sha': '$CURRENT_SHA'
}).encode()
req = urllib.request.Request(
    'https://api.github.com/repos/OWNER/REPO/contents/myfile.md',
    data=data,
    headers={'Authorization': f'token {pat}', 'Accept': 'application/vnd.github.v3+json', 'Content-Type': 'application/json'},
    method='PUT'
)
resp = urllib.request.urlopen(req)
print(json.loads(resp.read())['commit']['sha'][:8])
"
```

## Pitfalls

- **Token variable names vary** — some use `GITHUB_TOKEN`, others `GITHUB_PAT`. Search both with `grep -E "^GITHUB_(PAT|TOKEN)=" .env`.
- **Commented-out tokens are traps** — `# GITHUB_TOKEN=ghp_xx...` is NOT a valid token. Only use uncommented lines.
- **Base64 in shell `-d` JSON breaks** — special chars in base64 can corrupt the JSON payload. Use Python `base64.b64encode()` instead.
- **New files omit `sha`** — only include `"sha"` when updating an existing file.
- **Non-default branch** — add `"branch": "master"` to payload if repo uses master instead of main.
- **Rate limits** — unauthenticated API calls: 60/hr, authenticated: 5000/hr.
