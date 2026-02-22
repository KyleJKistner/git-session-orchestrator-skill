#!/usr/bin/env python3
"""Summarize git topology and coordination actions for any repository."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

DEFAULT_MAIN_CANDIDATES = ("main", "master", "trunk")


@dataclass(frozen=True)
class BranchDelta:
    branch: str
    ahead_of_base: int
    behind_base: int


@dataclass(frozen=True)
class WorktreeState:
    path: str
    branch: str
    detached: bool
    prunable: bool
    dirty: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Git coordination summary")
    parser.add_argument("--repo-root", default=str(Path.cwd()))
    parser.add_argument(
        "--main-branch",
        default="auto",
        help="Base branch/ref to compare against. Use 'auto' to detect automatically.",
    )
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def run_git(repo_root: str, args: List[str], check: bool = True) -> str:
    proc = subprocess.run(
        ["git", "-C", repo_root, *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def ref_exists(repo_root: str, ref: str) -> bool:
    proc = subprocess.run(
        ["git", "-C", repo_root, "rev-parse", "--verify", "--quiet", ref],
        text=True,
        capture_output=True,
        check=False,
    )
    return proc.returncode == 0


def list_local_branches(repo_root: str) -> List[str]:
    out = run_git(repo_root, ["for-each-ref", "--format=%(refname:short)", "refs/heads"])
    branches = [line.strip() for line in out.splitlines() if line.strip()]
    return sorted(branches)


def normalize_base_branch_name(base_ref: str) -> str:
    if base_ref.startswith("origin/"):
        return base_ref.removeprefix("origin/")
    return base_ref


def detect_base_ref(repo_root: str) -> str:
    branches = set(list_local_branches(repo_root))

    for candidate in DEFAULT_MAIN_CANDIDATES:
        if candidate in branches:
            return candidate

    for candidate in DEFAULT_MAIN_CANDIDATES:
        remote_ref = f"origin/{candidate}"
        if ref_exists(repo_root, remote_ref):
            return remote_ref

    remote_head = run_git(
        repo_root,
        ["symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"],
        check=False,
    )
    prefix = "refs/remotes/"
    if remote_head.startswith(prefix):
        candidate = remote_head.removeprefix(prefix)
        if ref_exists(repo_root, candidate):
            return candidate

    current = run_git(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"], check=False)
    if current and current != "HEAD":
        return current

    raise RuntimeError("Unable to detect a base branch/ref. Pass --main-branch explicitly.")


def choose_base_ref(repo_root: str, requested: str) -> str:
    requested = requested.strip()
    if requested and requested.lower() != "auto":
        if ref_exists(repo_root, requested):
            return requested
        remote_requested = f"origin/{requested}"
        if ref_exists(repo_root, remote_requested):
            return remote_requested
        raise RuntimeError(
            f"Base branch/ref '{requested}' does not exist locally or as '{remote_requested}'."
        )
    return detect_base_ref(repo_root)


def branch_deltas(repo_root: str, base_ref: str) -> List[BranchDelta]:
    branches = list_local_branches(repo_root)
    base_branch_name = normalize_base_branch_name(base_ref)
    deltas: List[BranchDelta] = []
    for branch in branches:
        if branch == base_branch_name:
            continue
        out = run_git(repo_root, ["rev-list", "--left-right", "--count", f"{branch}...{base_ref}"])
        parts = out.split()
        if len(parts) != 2:
            continue
        ahead = int(parts[0])
        behind = int(parts[1])
        deltas.append(BranchDelta(branch=branch, ahead_of_base=ahead, behind_base=behind))
    deltas.sort(key=lambda d: (d.behind_base, d.ahead_of_base, d.branch), reverse=True)
    return deltas


def parse_worktree_porcelain(output: str) -> List[Dict[str, str]]:
    blocks: List[Dict[str, str]] = []
    current: Dict[str, str] = {}
    for line in output.splitlines():
        if not line.strip():
            if current:
                blocks.append(current)
                current = {}
            continue
        if " " in line:
            key, value = line.split(" ", 1)
        else:
            key, value = line, ""
        current[key] = value
    if current:
        blocks.append(current)
    return blocks


def is_dirty(path: str) -> bool:
    proc = subprocess.run(
        ["git", "-C", path, "status", "--porcelain"],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return False
    return bool(proc.stdout.strip())


def collect_worktrees(repo_root: str) -> List[WorktreeState]:
    output = run_git(repo_root, ["worktree", "list", "--porcelain"])
    blocks = parse_worktree_porcelain(output)
    states: List[WorktreeState] = []
    for block in blocks:
        path = block.get("worktree", "")
        branch_ref = block.get("branch", "")
        detached = "detached" in block
        prunable = "prunable" in block
        branch = ""
        if branch_ref.startswith("refs/heads/"):
            branch = branch_ref.removeprefix("refs/heads/")
        elif detached:
            branch = "(detached)"
        else:
            branch = branch_ref
        dirty = is_dirty(path) if path else False
        states.append(
            WorktreeState(
                path=path,
                branch=branch,
                detached=detached,
                prunable=prunable,
                dirty=dirty,
            )
        )
    return states


def categorize_branch(delta: BranchDelta) -> str:
    if delta.ahead_of_base == 0 and delta.behind_base > 0:
        return "stale: rebase before new work"
    if delta.ahead_of_base > 0 and delta.behind_base > 0:
        return "diverged: rebase before merge"
    if delta.ahead_of_base > 0 and delta.behind_base == 0:
        return "ahead only: candidate to merge"
    return "in sync with base"


def recommendations(
    base_ref: str,
    repo_dirty: bool,
    deltas: List[BranchDelta],
    worktrees: List[WorktreeState],
) -> List[str]:
    recs: List[str] = []

    if repo_dirty:
        recs.append(
            "Repository root worktree has local changes. Commit or stash before coordinating merges."
        )

    diverged = [d for d in deltas if d.ahead_of_base > 0 and d.behind_base > 0]
    stale = [d for d in deltas if d.ahead_of_base == 0 and d.behind_base > 0]
    ahead_only = [d for d in deltas if d.ahead_of_base > 0 and d.behind_base == 0]

    if diverged:
        names = ", ".join(d.branch for d in diverged[:8])
        recs.append(f"Rebase diverged branches onto {base_ref} before merge: {names}.")
    if stale:
        names = ", ".join(d.branch for d in stale[:8])
        recs.append(f"Rebase stale branches on top of {base_ref} before new commits: {names}.")
    if ahead_only:
        names = ", ".join(d.branch for d in ahead_only[:8])
        recs.append(
            f"Branches ahead of {base_ref} and not behind can be validated then merged/cherry-picked: {names}."
        )

    dirty = [w for w in worktrees if w.dirty]
    if dirty:
        names = ", ".join(f"{w.branch}@{w.path}" for w in dirty[:6])
        recs.append(f"Dirty worktrees detected. Stash or commit before branch switching: {names}.")

    prunable = [w for w in worktrees if w.prunable]
    if prunable:
        recs.append("Prunable worktrees exist. Run `git worktree prune` after validating no needed data.")

    if len(worktrees) > 10:
        recs.append(
            "High worktree count. Reuse or prune worktrees before creating new ones to reduce coordination risk."
        )

    if not recs:
        recs.append(f"Topology looks clean. Continue with normal branch validation against {base_ref}.")

    return recs


def as_json(
    base_ref: str,
    repo_status: str,
    deltas: List[BranchDelta],
    worktrees: List[WorktreeState],
    recs: List[str],
) -> str:
    payload = {
        "base_ref": base_ref,
        "repo_root_status": repo_status,
        "branch_deltas": [
            {
                "branch": d.branch,
                "ahead_of_base": d.ahead_of_base,
                "behind_base": d.behind_base,
                "category": categorize_branch(d),
            }
            for d in deltas
        ],
        "worktrees": [
            {
                "path": w.path,
                "branch": w.branch,
                "detached": w.detached,
                "prunable": w.prunable,
                "dirty": w.dirty,
            }
            for w in worktrees
        ],
        "recommendations": recs,
    }
    return json.dumps(payload, indent=2)


def print_table(headers: List[str], rows: List[List[str]]) -> None:
    if not rows:
        print("(no rows)")
        return
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    print(" | ".join(headers[i].ljust(widths[i]) for i in range(len(headers))))
    print("-+-".join("-" * widths[i] for i in range(len(headers))))
    for row in rows:
        print(" | ".join(row[i].ljust(widths[i]) for i in range(len(headers))))


def main() -> int:
    args = parse_args()
    repo_root = str(Path(args.repo_root).expanduser().resolve())

    try:
        repo_status = run_git(repo_root, ["status", "-sb"])
        base_ref = choose_base_ref(repo_root, args.main_branch)
        repo_dirty = is_dirty(repo_root)
        deltas = branch_deltas(repo_root, base_ref)
        worktrees = collect_worktrees(repo_root)
        recs = recommendations(base_ref, repo_dirty, deltas, worktrees)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.json:
        print(as_json(base_ref, repo_status, deltas, worktrees, recs))
        return 0

    print("Base branch/ref:")
    print(base_ref)
    print()

    print("Repo root status:")
    print(repo_status)
    print()

    print(f"Branch deltas vs {base_ref}:")
    branch_rows = [
        [
            d.branch,
            str(d.ahead_of_base),
            str(d.behind_base),
            categorize_branch(d),
        ]
        for d in deltas
    ]
    print_table(["branch", "ahead", "behind", "category"], branch_rows)
    print()

    print("Worktrees:")
    worktree_rows = [
        [
            w.branch,
            "yes" if w.dirty else "no",
            "yes" if w.prunable else "no",
            w.path,
        ]
        for w in worktrees
    ]
    print_table(["branch", "dirty", "prunable", "path"], worktree_rows)
    print()

    print("Recommended actions:")
    for idx, item in enumerate(recs, start=1):
        print(f"{idx}. {item}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
