---
name: github-api-utilities
description: "GitHub API utilities: upload files without git, find tokens, handle edge cases."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [GitHub, API, Utilities, Edge Devices]
    related_skills: [github-repo-management, github-auth]
---

# GitHub API Utilities

Utilities for interacting with GitHub API when `git` and `gh` are not available — especially useful on edge devices like Raspberry Pi.

## Quick Reference

| Situation | Solution |
|-----------|----------|
| No git repo, need to push files | [github-api-upload-no-git.md](references/github-api-upload-no-git.md) |
| Don't know which env var holds the token | Search both `GITHUB_TOKEN` and `GITHUB_PAT` |
| `gh` CLI not installed | Use Python `urllib` with base64 encoding |

## Token Discovery

Token variable names vary across setups. Always search both:

```bash
# Correct: find uncommented GITHUB_TOKEN or GITHUB_PAT
PAT=$(grep -E "^GITHUB_(PAT|TOKEN)=" ~/.hermes/.env 2>/dev/null | grep -v "^#" | head -1 | cut -d= -f2)

# WRONG: this grabs commented-out or placeholder values
PAT=$(grep "^GITHUB_TOKEN=" ~/.hermes/.env | cut -d= -f2)  # may get "# GITHUB_TOKEN=ghp_xx..."
```

**Pitfall:** Commented-out tokens (`# GITHUB_TOKEN=...`) with placeholder values like `ghp_xx...xxxx` are NOT valid. Only use lines WITHOUT `#` prefix.

## See Also

- [github-api-upload-no-git.md](references/github-api-upload-no-git.md) — Full upload patterns for new and existing files
- `github-repo-management` — When you DO have git/gh available (preferred method)
