#!/usr/bin/env python3
"""Emit heartbeat and delta alerts for Codex session and git topology state."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class ActiveSession:
    session_id: str
    role: str
    branch: str
    parent_thread_id: str
    started_at: str
    last_timestamp: str
    last_summary: str
    log_path: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Heartbeat monitor for Codex sessions + git topology")
    parser.add_argument("--project-root", default=str(Path.cwd()))
    parser.add_argument("--repo-root", default="")
    parser.add_argument("--codex-home", default="")
    parser.add_argument("--recent", type=int, default=300)
    parser.add_argument("--active-minutes", type=int, default=30)
    parser.add_argument("--poll-interval", type=float, default=5.0)
    parser.add_argument("--heartbeat-interval", type=float, default=20.0)
    parser.add_argument("--main-branch", default="auto")
    parser.add_argument("--once", action="store_true")
    return parser.parse_args()


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_json(cmd: List[str]) -> dict:
    raw = subprocess.check_output(cmd, text=True)
    return json.loads(raw)


def load_active_sessions(args: argparse.Namespace, script_dir: Path) -> List[ActiveSession]:
    session_script = script_dir / "session_monitor.py"
    inventory_cmd = [
        "python3",
        str(session_script),
        "inventory",
        "--project-root",
        args.project_root,
        "--recent",
        str(args.recent),
        "--active-minutes",
        str(args.active_minutes),
        "--json",
    ]
    activity_cmd = [
        "python3",
        str(session_script),
        "activity",
        "--project-root",
        args.project_root,
        "--recent",
        str(args.recent),
        "--json",
    ]
    if args.codex_home:
        inventory_cmd.extend(["--codex-home", args.codex_home])
        activity_cmd.extend(["--codex-home", args.codex_home])

    inventory = run_json(inventory_cmd)
    activity = run_json(activity_cmd)
    activity_by_id = {row.get("session_id", ""): row for row in activity.get("activity", [])}

    active: List[ActiveSession] = []
    for row in inventory.get("recent", []):
        if not row.get("active"):
            continue
        sid = str(row.get("session_id", ""))
        arow = activity_by_id.get(sid, {})
        active.append(
            ActiveSession(
                session_id=sid,
                role=str(row.get("role", "")),
                branch=str(row.get("git_branch", "")),
                parent_thread_id=str(row.get("parent_thread_id", "")),
                started_at=str(row.get("started_at", "")),
                last_timestamp=str(arow.get("last_timestamp", "")),
                last_summary=str(arow.get("last_summary", "")),
                log_path=str(row.get("log_path", "")),
            )
        )
    active.sort(key=lambda item: item.started_at, reverse=True)
    return active


def normalize_topology(raw: dict) -> dict:
    status_lines = [line for line in str(raw.get("repo_root_status", "")).splitlines() if line.strip()]
    dirty_worktrees = sorted(
        f"{row.get('branch', '')}@{row.get('path', '')}"
        for row in raw.get("worktrees", [])
        if row.get("dirty")
    )
    prunable_worktrees = sorted(
        str(row.get("path", ""))
        for row in raw.get("worktrees", [])
        if row.get("prunable")
    )
    diverged = sorted(
        str(row.get("branch", ""))
        for row in raw.get("branch_deltas", [])
        if int(row.get("ahead_of_base", 0)) > 0 and int(row.get("behind_base", 0)) > 0
    )
    return {
        "base_ref": str(raw.get("base_ref", "")),
        "root_dirty": len(status_lines) > 1,
        "dirty_worktrees": dirty_worktrees,
        "prunable_worktrees": prunable_worktrees,
        "diverged": diverged,
    }


def load_topology(args: argparse.Namespace, script_dir: Path) -> dict:
    git_script = script_dir / "git_coordination.py"
    repo_root = args.repo_root or args.project_root
    cmd = [
        "python3",
        str(git_script),
        "--repo-root",
        repo_root,
        "--main-branch",
        args.main_branch,
        "--json",
    ]
    return normalize_topology(run_json(cmd))


def summarize_roles(active: List[ActiveSession]) -> Tuple[int, int]:
    primary = sum(1 for item in active if item.role == "primary")
    subagent = sum(1 for item in active if item.role == "subagent")
    return primary, subagent


def emit_session_delta(ts: str, prev_ids: List[str], cur_ids: List[str], active: List[ActiveSession]) -> None:
    prev = set(prev_ids)
    cur = set(cur_ids)
    added = sorted(cur - prev)
    removed = sorted(prev - cur)
    print(
        f"{ts} | delta.sessions | total={len(cur_ids)} | "
        f"added={','.join(added) if added else '-'} | removed={','.join(removed) if removed else '-'}"
    )
    active_by_id = {item.session_id: item for item in active}
    for sid in added[:8]:
        item = active_by_id[sid]
        print(
            f"{ts} | delta.sessions.detail | {item.session_id} | role={item.role} | "
            f"branch={item.branch} | started={item.started_at} | last={item.last_timestamp}"
        )


def emit_heartbeat(ts: str, active: List[ActiveSession], topology: dict) -> None:
    primary, subagent = summarize_roles(active)
    print(
        f"{ts} | heartbeat | active={len(active)} | primary={primary} | subagent={subagent} | "
        f"base={topology['base_ref']} | root_dirty={topology['root_dirty']} | "
        f"dirty_worktrees={len(topology['dirty_worktrees'])} | diverged={len(topology['diverged'])}"
    )
    hot = active[:5]
    if not hot:
        print(f"{ts} | heartbeat.sessions | none")
        return
    pieces = []
    for item in hot:
        marker = "p" if item.role == "primary" else "s"
        pieces.append(f"{item.session_id[:8]}:{marker}:{item.branch}")
    print(f"{ts} | heartbeat.sessions | {', '.join(pieces)}")


def main() -> int:
    args = parse_args()
    script_dir = Path(__file__).resolve().parent

    prev_session_ids: List[str] = []
    prev_topology: Optional[Dict[str, object]] = None
    next_heartbeat = 0.0

    while True:
        loop_start = time.monotonic()
        ts = now_utc()

        try:
            active = load_active_sessions(args, script_dir)
            topology = load_topology(args, script_dir)
        except Exception as exc:  # noqa: BLE001
            print(f"{ts} | error | {exc}")
            sys.stdout.flush()
            if args.once:
                return 2
            time.sleep(max(args.poll_interval, 0.5))
            continue

        session_ids = [item.session_id for item in active]
        if session_ids != prev_session_ids:
            emit_session_delta(ts, prev_session_ids, session_ids, active)
            prev_session_ids = session_ids

        if prev_topology != topology:
            print(f"{ts} | delta.git | {json.dumps(topology, sort_keys=True)}")
            prev_topology = topology

        now_mono = time.monotonic()
        if now_mono >= next_heartbeat:
            emit_heartbeat(ts, active, topology)
            next_heartbeat = now_mono + max(args.heartbeat_interval, 1.0)

        sys.stdout.flush()
        if args.once:
            return 0

        elapsed = time.monotonic() - loop_start
        sleep_for = max(args.poll_interval - elapsed, 0.5)
        time.sleep(sleep_for)


if __name__ == "__main__":
    raise SystemExit(main())
