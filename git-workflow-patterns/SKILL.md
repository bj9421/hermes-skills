---
name: git-workflow-patterns
description: "Common git workflow patterns: squashing history, force push, orphan branches, cleanup. Not PR management (see github-pr-workflow). Also covers git initialization for new projects."
version: 1.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [git, workflow, squash, force-push, history-rewrite, init]
---

# Git Workflow Patterns

Reusable patterns for common git operations beyond basic PR workflows.

## Related References

- `references/squash-history-force-push.md` — Squashing history + force push to clean repos
- `references/external-skill-standards.md` — agentskills.io spec and external skill registries
- `references/dubious-ownership-fix.md` — Fix git "dubious ownership" in Docker containers

## Git Init for New Projects

When creating a new project, always initialize git immediately:

```bash
cd /path/to/project
git init --initial-branch=main
git add .
git commit -m "init: initial commit"
```

⚠️ **Docker ownership issue**: If the container UID doesn't match the directory owner, you'll see "fatal: detected dubious ownership". Fix:
```bash
git -c safe.directory=/path/to/dir commit -m "..."
# Or add to global config:
git config --global --add safe.directory /path/to/dir
```
