# README Split Convention for Mobile Compatibility

> **Class of problem:** GitHub mobile App renders README.md as blank when the file is too large (>15KB / >300 lines) or contains heavy Markdown (Mermaid diagrams, many tables, ASCII art).

## Symptoms

- GitHub mobile App shows empty/blank README
- Browser view works fine (confirms it's an App rendering issue, not a file problem)
- Raw file content is valid

## Root Cause

The GitHub mobile App's Markdown renderer has limits:
- Files >~15KB or >~300 lines often fail silently
- Mermaid diagrams, large tables, and ASCII art compound the problem
- Caching may serve stale/empty renders

## Solution: Split into README + ARCHITECTURE

| File | Content | Target Size |
|------|---------|-------------|
| `README.md` | Quick Start, Installation, How to Use, Pipeline overview, When to Use, Key Takeaways | ~80-100 lines, <5KB |
| `ARCHITECTURE.md` | Design philosophy, Progress Tracker, Phase Gates, Architecture diagrams, Kanban mapping, Common mistakes, Related skills | Deep dive, linked from README |

### README.md template structure
```markdown
# Project Name — Tagline
> Short intro, links to full docs

## 🚀 Quick Start
One-liner + code block

## 📦 Installation
Minimal steps

## 📋 Overview
Brief pipeline/features table (not the full diagram)

## 🔧 When to Use
Simple YES/NO bullets

## ⚡ Key Takeaways
Numbered list of 5-7 points

## 📖 Full Documentation
See [ARCHITECTURE.md](ARCHITECTURE.md) for design philosophy, progress tracker, diagrams, and deep dive.
```

### ARCHITECTURE.md template structure
```markdown
# Project Name — Architecture & Design
> 📖 **Quick Start?** Go back to [README.md](README.md).

## Design Philosophy
(Why this exists, problems solved)

## Progress Tracker
(Full checkbox lists per phase)

## Phase Gates
(Detailed tables)

## Architecture
(Diagrams, subagent models, etc.)

## Kanban Integration
(Mapping, commands)

## Common Mistakes
(List with fixes)

## Related Skills
(Table)

## Comparison
(Any comparisons)
```

## Prevention Checklist

Before committing a README:
- [ ] File size < 5KB (~100 lines)
- [ ] No Mermaid diagrams (move to ARCHITECTURE.md)
- [ ] Tables are minimal (2-3 cols, <10 rows)
- [ ] No large ASCII art blocks
- [ ] Links to deep-dive doc exist for complex sections

## Tools

- Check size: `wc -c README.md` (bytes) or `wc -l README.md` (lines)
- Preview on mobile: open `github.com/user/repo` in Safari/Chrome mobile

## When NOT to Split

Don't split if:
- The doc is genuinely short (<200 lines, <10KB)
- It's a simple project with no deep architecture
- The audience is primarily desktop users
