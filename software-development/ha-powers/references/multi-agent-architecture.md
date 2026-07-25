# HA·Power Multi-Agent Architecture (Corrected)

> **How subagents collaborate across the development pipeline.**  
> Key insight: **One profile, 0–2 transient subagents.** Everything else is done directly by the Orchestrator.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│               ONE HERMES PROFILE (default)                    │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              ORCHESTRATOR (Main Session)                │  │
│  │  • Handles all 7 phases directly                       │  │
│  │  • Only Phase 4 optionally spawns subagents            │  │
│  │  • You talk to THIS, never to subagents                │  │
│  │  • Has memory, session history, full context           │  │
│  └────────────────────────┬───────────────────────────────┘  │
│                           │                                   │
│               delegate_task (Phase 4 only)                    │
│                           │                                   │
│  ┌────────────────────────▼──────────────────────────────┐  │
│  │             SUBAGENT POOL (temporary)                  │  │
│  │                                                       │  │
│  │  ┌──────────────────┐  ┌──────────────────────────┐  │  │
│  │  │   Developer      │  │   Reviewer (optional)     │  │  │
│  │  │   • Implements   │  │   • Verifies spec         │  │  │
│  │  │   • TDD loop     │  │   • Checks quality        │  │  │
│  │  │   • Commits      │  │   • Returns PASS/FAIL     │  │  │
│  │  └──────────────────┘  └──────────────────────────┘  │  │
│  │                                                       │  │
│  │  • Born from delegate_task, die after report          │  │
│  │  • Same profile as Orchestrator                       │  │
│  │  • No persistent memory, no independent config         │  │
│  │  • Max 3 concurrent (Hermes limit)                    │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │          SHARED FILESYSTEM (Artifact Bus)              │  │
│  │  specs/ → plans/ → worktrees/ → code → PR → merged    │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

## Subagents: The Only Two You'll Ever Need

| "Role" (old name) | Actual Actor | Why |
|-------------------|-------------|-----|
| Architect | **Orchestrator + You** — discuss spec directly | Brainstorming is conversation, not code |
| Planner | **Orchestrator** — writes the plan | Fast enough to do yourself |
| **Developer** | **🟢 Subagent (delegate_task)** — actual coding | Isolated TDD workload |
| **Reviewer** | **🟢 Subagent (delegate_task, optional)** — audit quality | Only for large features |
| DevOps | **Orchestrator** — git push + gh pr | One-liner CLI commands |
| Cleanup | **Orchestrator** — git worktree remove | One-liner CLI command |

> ⚠️ **Historical note:** Earlier documentation listed "6 agent roles." That was wrong. The pipeline has 7 phases, only 1 of which (Phase 4) may use subagents. The other "roles" are just task types the Orchestrator handles directly.

## When to Spawn Subagents

| Feature Size | Files Changed | Subagents | Pattern |
|-------------|---------------|-----------|---------|
| Fix / config | 1 file | **0** — Orchestrator does everything | Direct |
| Small feature | 1–3 files | **1** Developer (no reviewer) | Dev-only |
| Large feature | 4+ files, cross-module | **2** Developer + Reviewer | Dev + Review |
| Full pipeline | Any | Same as above + Kanban tracking | + Kanban |

## Subagent Contracts

### Developer Subagent

```
GOAL: Implement Task N from plan: <exact task>
CONTEXT:
  - Worktree path: .worktrees/feat/<name>/
  - Files to create/modify: <list>
  - TDD: write failing test → implement → test passes → commit
  - Commit convention: feat: <description>

OUTPUT (report):
  ## Developer Report — Task N
  Files created: <paths>
  Files modified: <paths>
  Tests: <N> passed, <N> failed
  Commits: <summary>
  Issues: <any>
```

### Reviewer Subagent

```
GOAL: Verify implementation against spec + code quality
CONTEXT:
  - Spec path: docs/specs/<file>.md
  - Files changed: <list>
  - Check: spec compliance + naming + error handling + security

OUTPUT (report):
  ## Reviewer Report
  Spec compliance: ✅ PASS / ❌ <specific gaps>
  Code quality: ✅ APPROVED / ⚠️ <minor> / ❌ <changes requested>
  Issues:
    - Critical: <none>
    - Important: <list>
    - Minor: <list>
```

## Communication Protocol

Subagents don't "talk" — they produce reports:

| Channel | Purpose | Example |
|---------|---------|---------|
| **Reports** | Subagent → Orchestrator | Developer report with test results |
| **Filesystem** | Shared state | `.worktrees/`, `docs/specs/`, `docs/plans/` |
| **Git commits** | Change history | `feat: add user model` |
| **Terminal output** | Execution results | `pytest tests/ -q` |

### Report Contract

Every subagent report MUST contain:

```markdown
## <Role> Report
**Status:** ✅ COMPLETE / ❌ FAILED
**Deliverables:** <files>
**Key results:** <test counts, decisions>
**Issues:** <blockers>
```

## Practical Limits

| Constraint | Limit | Mitigation |
|------------|-------|------------|
| Concurrent subagents | 3 per user | Batch independent tasks, serialise dependent ones |
| Subagent nesting | 1 level only | Orchestrator handles all delegation |
| Subagent durability | Not persistent | Use `cronjob` for durable background work |
| Context size | System context limit | Reference files instead of copying content |

## Example Run (Realistic)

```
USER: "Add login rate limiter"

ORCHESTRATOR (same profile, handles everything directly):
  Phase 1: Talks to user → spec written ✅
  Phase 2: Writes plan with 5 tasks ✅
  Phase 3: git worktree add -b feat/rate-limiter ✅
  Phase 4: Delegates Tasks 1-3 (parallel, different files)
           → 1 Developer subagent → code + tests ✅
           Delegates Task 4-5 (sequential)
           → 1 Developer subagent → code + tests ✅
           Optional: 1 Reviewer subagent → PASS ✅
  Phase 5: Runs pytest + ruff → clean ✅
  Phase 6: git push + gh pr create → merged ✅
  Phase 7: git worktree remove ✅

Total: 0-2 subagents spawned, all disposable, same profile.
```

## Key Takeaway

> **1 profile (default) + 0–2 transient subagents = full HA·Power pipeline.**  
> No profile isolation needed. No "6 agents." Just one Orchestrator and optional disposable workers.
