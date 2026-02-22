# Share Kit

Use these copy/paste blocks for Slack, PRs, docs, or release notes.

## Short Blurb

`git-session-orchestrator` gives you a live view of Codex agent activity and safe next-step git commands based on current repo state.

## Medium Blurb

`git-session-orchestrator` is a Codex skill for teams running parallel agents. It shows who is active (including subagents), summarizes recent session activity, and reports branch/worktree status so git operations happen in the right order.

## Long Blurb

`git-session-orchestrator` is a practical Codex skill for multi-agent repositories. It combines session monitoring and git coordination in one workflow:

- inventory active primary/subagent sessions with log paths
- summarize recent activity for faster handoffs
- inspect branch divergence and dirty worktrees
- suggest safe next git commands from actual repository state

Use it when you need clean coordination before rebasing, merging, cherry-picking, or worktree cleanup.

Repo: `https://github.com/KyleJKistner/git-session-orchestrator-skill`

## Install Snippet

```bash
git clone https://github.com/KyleJKistner/git-session-orchestrator-skill.git
cd git-session-orchestrator-skill
./install.sh
```

## Update Snippet

```bash
cd git-session-orchestrator-skill
git pull --ff-only
./install.sh --force
```

## First Run (Tiny)

```bash
python3 ~/.codex/skills/git-session-orchestrator/scripts/session_monitor.py inventory --project-root "$PWD" --recent 20 --active-minutes 30
python3 ~/.codex/skills/git-session-orchestrator/scripts/git_coordination.py --repo-root "$PWD" --main-branch auto
```
