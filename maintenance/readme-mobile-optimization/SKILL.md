---
name: readme-mobile-optimization
description: >-
  Pattern for optimizing README.md files when GitHub mobile apps fail to render
  them (blank screen). Covers diagnosis, splitting strategy, and file-size thresholds.
version: 1.0.0
author: Hermes Agent
tags: [github, mobile, rendering, readme, documentation]
---

# README Mobile Optimization

## Problem

GitHub mobile App shows blank README when:
- File exceeds ~15KB or ~300 lines
- Contains complex Markdown (tables, mermaid diagrams, ASCII art)
- Multiple large tables cause rendering engine crash

## Diagnosis Checklist

1. **Check file size** via GitHub API:
   ```
   curl -s https://api.github.com/repos/{owner}/{repo}/readme | python3 -c "import sys,json;d=json.load(sys.stdin);print(f'Size: {d.get(\"size\",\"?\")} bytes')"
   ```
2. **Compare with browser** — open `github.com/{owner}/{repo}` in mobile browser
3. If browser renders fine but App doesn't → confirmed App rendering limit

## Solution: Split Strategy

When README exceeds thresholds, split into:

| File | Content | Target Size |
|------|---------|-------------|
| `README.md` | Quick Start, Installation, How to Use, Pipeline Overview, Key Takeaways | <100 lines, <5KB |
| `ARCHITECTURE.md` | Design philosophy, Progress Tracker, Phase Gates, diagrams, architecture trees | Unlimited |
| `zh-TW.md` | (Optional) Localized translation | As needed |

### README.md Template (minimal)

```markdown
# <Project Name> — <Tagline>

> Short description (2-3 lines)

## 🚀 Quick Start
[Core usage instructions]

## 📦 Installation
[Setup steps]

## 📋 Overview
[Brief pipeline/feature summary]

## 🔧 When to Use
[Decision criteria]

## ⚡ Key Takeaways
[1-6 bullet points]

---
> **Full details:** [ARCHITECTURE.md](ARCHITECTURE.md) | [API docs](...) | [Examples](...)
```

### ARCHITECTURE.md Template (full)

```markdown
# <Project> — Architecture & Design

> 📖 **Quick Start?** Go back to [README.md](README.md).

[Full design philosophy, progress trackers, phase gates, diagrams,
common mistakes, related skills, comparisons, etc.]
```

## Splitting Procedure (numbered steps)

1. Read current README.md fully
2. Identify sections that are **reference material** (detailed, for lookup) vs **onboarding material** (for first-time readers)
3. Create `ARCHITECTURE.md` with all reference sections
4. Rewrite `README.md` to ~80-100 lines keeping only onboarding sections
5. Cross-link both files (README → ARCH, ARCH → README)
6. Verify both render correctly in browser
7. Commit and push

## Verification

After splitting:
- [ ] README.md < 100 lines, < 5KB
- [ ] README.md renders in GitHub mobile App
- [ ] ARCHITECTURE.md accessible via link from README
- [ ] No orphaned links (broken references)
- [ ] Original content fully preserved (just relocated)

## When NOT to Split

- README is already < 100 lines
- No mobile rendering issue reported
- Content is genuinely cohesive (splitting hurts navigation)

## Pitfalls

1. **Don't split too aggressively** — one extra doc (ARCHITECTURE.md) is enough. Don't create 10 micro-docs.
2. **Always cross-link** — README must link to ARCH, ARCH must link back to README.
3. **Preserve all content** — splitting is relocation, not deletion. Verify line count totals match.
4. **Mermaid diagrams in README** — even if file size is OK, mermaid charts often trigger mobile rendering bugs. Move them to ARCHITECTURE.md.
5. **Large ASCII art / diagrams** — same as mermaid. These are the #1 cause of blank renders even at modest file sizes.
