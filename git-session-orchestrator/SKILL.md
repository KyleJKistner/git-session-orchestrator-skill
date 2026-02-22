---
name: git-session-orchestrator
description: Monitor Codex session logs for any project, including subagent lineage and live activity, then coordinate git actions. Use when the user asks who agents are working on and where, wants live tailing of Codex sessions, or needs concrete rebase/merge/cherry-pick/stash/worktree guidance grounded in current repository state.
---

# Git Session Orchestrator

## Workflow

1. Snapshot Codex sessions for the target project root.
2. Split analysis into subagents with non-overlapping scopes.
3. Aggregate findings into one operator report.
4. Provide git coordination actions with explicit commands and ordering.

## Quick Start

Run session inventory:

```bash
python3 scripts/session_monitor.py inventory \
  --recent 20 \
  --active-minutes 30
```

Run recent activity summary:

```bash
python3 scripts/session_monitor.py activity \
  --recent 10
```

Run live tail:

```bash
python3 scripts/session_monitor.py follow \
  --active-minutes 30 \
  --interval 2
```

Run git coordination snapshot:

```bash
python3 scripts/git_coordination.py
```

Run continuous heartbeat monitor (session + git delta alerts):

```bash
python3 scripts/heartbeat_monitor.py \
  --project-root "$PWD" \
  --repo-root "$PWD" \
  --active-minutes 30 \
  --poll-interval 5 \
  --heartbeat-interval 20
```

Run one cycle and exit:

```bash
python3 scripts/heartbeat_monitor.py \
  --project-root "$PWD" \
  --repo-root "$PWD" \
  --once
```

Use explicit roots when not running from the target repository:

```bash
python3 scripts/session_monitor.py inventory \
  --project-root /abs/path/to/repo \
  --recent 20 \
  --active-minutes 30

python3 scripts/git_coordination.py \
  --repo-root /abs/path/to/repo \
  --main-branch auto
```

## Subagent Plan

Use exactly three subagents unless the user asks for more.

Subagent 1: session inventory
- Scope: enumerate project sessions and subagent lineage.
- Command: `python3 scripts/session_monitor.py inventory --project-root "$PWD" --recent 20 --active-minutes 30 --json`.
- Output: recent session table plus active sessions.

Subagent 2: activity inference
- Scope: summarize last meaningful activity per recent session.
- Command: `python3 scripts/session_monitor.py activity --project-root "$PWD" --recent 10 --json`.
- Output: who/what/where list with timestamp and log path.

Subagent 3: git topology
- Scope: branch divergence, dirty worktrees, stale/prunable worktrees.
- Command: `python3 scripts/git_coordination.py --repo-root "$PWD" --main-branch auto --json`.
- Output: decision-ready rebase/merge/cherry-pick/stash/worktree recommendations.

## Coordination Rules

Use `references/git-ops-playbook.md` for decision criteria.

Always include:
- Absolute timestamps for "active now" and "started at".
- Session id and log path for every claim.
- Explicit command suggestions for each git action.

Never:
- Run destructive git commands (`reset --hard`, `checkout --`, forced cleans) unless the user explicitly asks.
- Advise merge operations before reconciling dirty worktrees.
- Recommend adding new worktrees when there are prunable/missing worktrees that should be cleaned first.

## Output Contract

Present results in this order:
1. Active sessions (primary and subagents).
2. Session activity summary (who/what/where).
3. Git topology risks.
4. Recommended next commands in execution order.

If evidence is incomplete, state exactly what is missing and run follow-up commands before advising.
