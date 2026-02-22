# git-session-orchestrator skill

Codex skill for monitoring Codex session logs (including subagent lineage/live activity) and coordinating safe git actions across active work.

## Install

```bash
mkdir -p ~/.codex/skills
git clone git@github.com:KyleJKistner/git-session-orchestrator-skill.git /tmp/git-session-orchestrator-skill
rm -rf ~/.codex/skills/git-session-orchestrator
cp -R /tmp/git-session-orchestrator-skill/git-session-orchestrator ~/.codex/skills/git-session-orchestrator
```

## Verify

```bash
ls ~/.codex/skills/git-session-orchestrator
```

You should see `SKILL.md`, `scripts/`, `references/`, and `agents/`.

## Skill quick commands

```bash
python3 ~/.codex/skills/git-session-orchestrator/scripts/session_monitor.py inventory --project-root "$PWD" --recent 20 --active-minutes 30
python3 ~/.codex/skills/git-session-orchestrator/scripts/session_monitor.py activity --project-root "$PWD" --recent 10
python3 ~/.codex/skills/git-session-orchestrator/scripts/git_coordination.py --repo-root "$PWD" --main-branch auto
```
