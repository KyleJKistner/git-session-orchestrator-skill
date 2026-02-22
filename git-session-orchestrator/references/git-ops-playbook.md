# Git Ops Playbook

Use this matrix after collecting session and topology evidence.

## Rebase

Use when:
- Branch is behind the selected base branch (usually `main`) and not yet merged.
- Branch has local commits plus missing base-branch commits (diverged history).
- You need a linear branch for a clean PR merge.

Command pattern:
```bash
git fetch origin
git checkout <branch>
git rebase <base-branch>
```

## Merge

Use when:
- Branch is up to date with the selected base branch.
- Validation for the branch has passed.
- You want complete branch history in the base branch.

Command pattern:
```bash
git checkout <base-branch>
git merge --no-ff <branch>
```

## Cherry-Pick

Use when:
- You need one or a few commits from a branch.
- The source branch contains unrelated or unfinished work.
- You need a quick hotfix without full branch integration.

Command pattern:
```bash
git checkout <target-branch>
git cherry-pick <commit_sha>
```

## Stash

Use when:
- A worktree is dirty and you must switch context quickly.
- Changes are experimental and not ready to commit.

Command pattern:
```bash
git stash push -m "<reason>"
```

## Worktree

Use when:
- You need parallel branch execution without constant branch switching.
- Long-running tests/builds must stay isolated.

Avoid creating more worktrees when:
- Existing worktrees are prunable or stale.
- You can safely reuse a clean worktree.

Command pattern:
```bash
git worktree add ../<dir> <branch>
```

## Safety Rules

- Do not recommend destructive commands unless explicitly requested.
- Resolve dirty worktrees before merge/rebase operations.
- Attach every recommendation to concrete evidence: branch divergence, dirty state, or active session ownership.
