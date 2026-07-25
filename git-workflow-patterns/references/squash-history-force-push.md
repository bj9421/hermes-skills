# Squash History & Force Push

Pattern for cleaning up a messy git history by squashing all commits into one, then force-pushing to GitHub. Useful for documentation repos, proof-of-concept repos, or when a long series of iterative commits should be presented as a single clean initial commit.

## Steps

### 1. Squash all commits into one

```bash
# Option A: Soft reset to merge-base (squashes everything below)
git reset --soft $(git merge-base HEAD main)
git commit -m "feat: clean initial commit — <brief description>"

# Option B: Orphan branch (full clean slate)
git checkout --orphan temp-branch
git add -A
git commit -m "feat: clean initial commit — <brief description>"
git branch -D main
git branch -m main
```

### 2. Handle the remote

**Standard bare remote (GitHub/GitLab):**
```bash
git push --force origin main
```

**Non-bare remote (local worktree cloned from remote):**
```bash
# Allow pushing to checked-out branch on the remote
git -C /path/to/remote-repo config receive.denyCurrentBranch ignore

# Then force push
git push --force origin main

# Restore safe default
git -C /path/to/remote-repo config receive.denyCurrentBranch update
```

### 3. Verify

```bash
git fetch origin
git log --oneline origin/main  # Should show only the squashed commit
```

## Pitfalls

- **Never force push to shared repos** without confirming no one else is contributing. This permanently destroys history.
- **Non-bare remote gotcha**: If `git push --force` says "Everything up-to-date" but the remote still shows old commits, the remote is a non-bare repo. Set `receive.denyCurrentBranch=ignore` first, then force push again.
- **GitHub web/mobile UI caches**: After force push, the UI might still show old commits for a few minutes. Refresh or wait.

## When to Use

- Documentation-only repos with no contributors
- Initial commit for a newly created repo that went through many iterations
- Cleaning up accidental commits with typos, wrong names, etc.
- Reducing noise in a personal/proxy repo

## When NOT to Use

- Active collaboration repos
- Repos with open PRs or forks
- Any repo where history matters for compliance/audit
