# git-session-orchestrator skill

Codex skill for monitoring Codex session logs (including subagent lineage and live activity) and coordinating safe git actions across active work.

## Share Link

`https://github.com/KyleJKistner/git-session-orchestrator-skill`

## Quick Install

```bash
git clone https://github.com/KyleJKistner/git-session-orchestrator-skill.git
cd git-session-orchestrator-skill
./install.sh
```

## Installer Options

```bash
./install.sh --help
./install.sh --dry-run
./install.sh --force
```

`--dry-run` previews actions without changing files.  
`--force` replaces an existing install without prompting.

## Verify Install

```bash
ls ~/.codex/skills/git-session-orchestrator
```

Expected folders/files:
- `SKILL.md`
- `agents/`
- `references/`
- `scripts/`

## Update to Latest Version

```bash
cd git-session-orchestrator-skill
git pull
./install.sh --force
```

## Quick Commands

Inventory active/recent sessions:

```bash
python3 ~/.codex/skills/git-session-orchestrator/scripts/session_monitor.py inventory --project-root "$PWD" --recent 20 --active-minutes 30
```

Summarize recent session activity:

```bash
python3 ~/.codex/skills/git-session-orchestrator/scripts/session_monitor.py activity --project-root "$PWD" --recent 10
```

Inspect git topology:

```bash
python3 ~/.codex/skills/git-session-orchestrator/scripts/git_coordination.py --repo-root "$PWD" --main-branch auto
```

Run continuous heartbeat monitor:

```bash
python3 ~/.codex/skills/git-session-orchestrator/scripts/heartbeat_monitor.py --project-root "$PWD" --repo-root "$PWD" --active-minutes 30 --poll-interval 5 --heartbeat-interval 20
```

Run one heartbeat cycle and exit:

```bash
python3 ~/.codex/skills/git-session-orchestrator/scripts/heartbeat_monitor.py --project-root "$PWD" --repo-root "$PWD" --once
```
