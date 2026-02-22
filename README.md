# git-session-orchestrator

`git-session-orchestrator` gives you live Codex session visibility (including subagents) plus git-safe coordination guidance from current repo state.

## Value

- Track primary and subagent sessions with lineage and recent activity.
- Inspect git topology and get ordered next-step commands.
- Monitor changes continuously with a heartbeat loop for active coordination.

## Install (Quick)

```bash
git clone https://github.com/KyleJKistner/git-session-orchestrator-skill.git
cd git-session-orchestrator-skill
./install.sh
```

## Verify

```bash
ls "$HOME/.codex/skills/git-session-orchestrator"
```

Expected files:
- `SKILL.md`
- `agents/openai.yaml`
- `references/git-ops-playbook.md`
- `scripts/session_monitor.py`
- `scripts/git_coordination.py`
- `scripts/heartbeat_monitor.py`

## Update

```bash
cd git-session-orchestrator-skill
git pull --ff-only
./install.sh --force
```

## Command Quickstart

Session inventory:

```bash
python3 "$HOME/.codex/skills/git-session-orchestrator/scripts/session_monitor.py" inventory --project-root "$PWD" --recent 20 --active-minutes 30
```

Recent activity:

```bash
python3 "$HOME/.codex/skills/git-session-orchestrator/scripts/session_monitor.py" activity --project-root "$PWD" --recent 10
```

Git topology:

```bash
python3 "$HOME/.codex/skills/git-session-orchestrator/scripts/git_coordination.py" --repo-root "$PWD" --main-branch auto
```

Continuous heartbeat:

```bash
python3 "$HOME/.codex/skills/git-session-orchestrator/scripts/heartbeat_monitor.py" --project-root "$PWD" --repo-root "$PWD" --active-minutes 30 --poll-interval 5 --heartbeat-interval 20
```

One-shot heartbeat:

```bash
python3 "$HOME/.codex/skills/git-session-orchestrator/scripts/heartbeat_monitor.py" --project-root "$PWD" --repo-root "$PWD" --once
```

## Troubleshooting

- Existing install blocks setup:

```bash
./install.sh --force
```

- Preview actions without changes:

```bash
./install.sh --dry-run
```

- `./install.sh: permission denied`:

```bash
chmod +x ./install.sh
```

- Install to a custom skills root:

```bash
./install.sh --path "$HOME/.codex/skills"
```

## Links

- Share kit: [`docs/share-kit.md`](docs/share-kit.md)
- Skill entrypoint: [`git-session-orchestrator/SKILL.md`](git-session-orchestrator/SKILL.md)
- Repo: `https://github.com/KyleJKistner/git-session-orchestrator-skill`
- CI smoke workflow: `.github/workflows/smoke.yml`
