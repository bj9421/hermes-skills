# Publishing a Skill for Dual Audience (Human + Agent)

When publishing a skill to a public repo (README.md + SKILL.md), both humans and agents will visit. Structure for each.

## Convention: Three-File Layout

| File | For | Purpose |
|------|-----|---------|
| `README.md` | Humans | Design philosophy, usage, architecture, comparison tables |
| `SKILL.md` | Agents | Complete skill definition — copy into `skills/` to deploy |
| `zh-TW.md` (optional) | Humans | Localized documentation |

## Installation Section: Always Include Agent Link

In the `## Installation` section, add this block for agents:

```markdown
> 🤖 **For Agents:** [Download SKILL.md](SKILL.md) — copy this file into your `skills/software-development/<name>/` directory to deploy the complete skill definition.
```

And always clarify it's NOT built-in:

```markdown
> ⚠️ **Not built into Hermes Agent.** This is a community-contributed skill authored by the Hermes user. It is not part of the Hermes Agent core distribution.
```

## Design Philosophy Section

Every published skill should have `## 🧠 Design Philosophy` explaining:

1. **Problems being solved** (failure modes without the skill)
2. **Why N phases/steps** (each maps to a specific failure)
3. **What's added on top of upstream** (e.g., Superpowers)
4. **The guiding principle** (one-liner mantra)

## References Directory

When the SKILL.md references supporting files (architecture docs, contracts, templates), the `references/` directory must be published alongside:

| Directory | For | Purpose |
|-----------|-----|---------|
| `SKILL.md` | Agents | Complete skill definition |
| `references/*.md` | Agents | Supporting docs referenced from SKILL.md |
| `README.md` | Humans | Design philosophy, usage, architecture |
| `zh-TW.md` | Humans | Localized documentation |

Deployment instructions must tell agents to copy the **entire directory** (SKILL.md + references/), not just SKILL.md alone.

## Git History Cleanup

When a repo accumulates messy commit history (renames, typos, incremental fixes), squash into ONE clean initial commit:

```bash
# 1. Clone to temp dir
git clone <repo-url> /tmp/workdir
cd /tmp/workdir

# 2. Soft reset to initial commit (keeps all files)
git reset --soft <initial-commit-hash>

# 3. Amend into one clean commit
git commit --amend -m "feat: <clean summary>"

# 4. Force push
git push --force origin main
```

## Commit & Push

```bash
git add -A
git commit -m "docs: <summary>"
git push
```

Commit message format: `docs: add <thing> — <brief why>`

## Common Pitfalls

- **Double-s typo in `@skill:` command** — e.g., `@skill:ha-powerss` instead of `@skill:ha-powers`. Always verify spelling before showing to user. Has caused broken references in docs multiple times.
- **Publishing SKILL.md without references/** — agents that copy only SKILL.md miss supporting files and the skill is incomplete.
- **Not clarifying the skill is NOT built-in** — users assume all skills come with Hermes Agent. Always add the disclaimer.
