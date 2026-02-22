#!/usr/bin/env python3
"""Monitor Codex session logs for a specific project root."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

DEFAULT_CODEX_HOME = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))


@dataclass(frozen=True)
class SessionRecord:
    session_id: str
    started_at: str
    cwd: str
    role: str
    parent_thread_id: str
    depth: str
    git_branch: str
    log_path: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Codex session monitor")
    subparsers = parser.add_subparsers(dest="command", required=True)

    base = argparse.ArgumentParser(add_help=False)
    base.add_argument("--codex-home", default=str(DEFAULT_CODEX_HOME))
    base.add_argument("--project-root", default=str(Path.cwd()))

    inventory = subparsers.add_parser("inventory", parents=[base])
    inventory.add_argument("--recent", type=int, default=20)
    inventory.add_argument("--active-minutes", type=int, default=30)
    inventory.add_argument("--json", action="store_true")

    activity = subparsers.add_parser("activity", parents=[base])
    activity.add_argument("--recent", type=int, default=10)
    activity.add_argument("--json", action="store_true")

    follow = subparsers.add_parser("follow", parents=[base])
    follow.add_argument("--recent", type=int, default=40)
    follow.add_argument("--interval", type=float, default=2.0)
    follow.add_argument("--active-minutes", type=int, default=30)
    follow.add_argument("--from-start", action="store_true")

    return parser.parse_args()


def parse_iso(ts: str) -> datetime:
    normalized = ts.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized).astimezone(timezone.utc)


def iter_log_files(codex_home: Path) -> Iterable[Path]:
    sessions_root = codex_home / "sessions"
    archived_root = codex_home / "archived_sessions"

    if sessions_root.exists():
        yield from sessions_root.rglob("*.jsonl")
    if archived_root.exists():
        yield from archived_root.glob("*.jsonl")


def read_session_meta(log_path: Path) -> Optional[dict]:
    try:
        with log_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("type") == "session_meta":
                    payload = obj.get("payload", {})
                    if isinstance(payload, dict):
                        return payload
    except OSError:
        return None
    return None


def to_session_record(log_path: Path, meta: dict) -> Optional[SessionRecord]:
    cwd = str(meta.get("cwd", ""))
    session_id = str(meta.get("id", "")).strip()
    started_at = str(meta.get("timestamp", "")).strip()
    if not session_id or not started_at or not cwd:
        return None

    source = meta.get("source", {})
    if not isinstance(source, dict):
        source = {}
    subagent = source.get("subagent", {})
    if not isinstance(subagent, dict):
        subagent = {}
    thread_spawn = subagent.get("thread_spawn", {})
    if not isinstance(thread_spawn, dict):
        thread_spawn = {}

    role = "subagent" if thread_spawn else "primary"
    parent_thread_id = str(thread_spawn.get("parent_thread_id", "") or "")
    depth = str(thread_spawn.get("depth", "") or "")

    git_obj = meta.get("git", {})
    if not isinstance(git_obj, dict):
        git_obj = {}
    git_branch = str(git_obj.get("branch", "") or "")

    return SessionRecord(
        session_id=session_id,
        started_at=started_at,
        cwd=cwd,
        role=role,
        parent_thread_id=parent_thread_id,
        depth=depth,
        git_branch=git_branch,
        log_path=log_path,
    )


def is_within_root(root: str, path: str) -> bool:
    try:
        resolved_root = os.path.realpath(root)
        resolved_path = os.path.realpath(path)
        return os.path.commonpath([resolved_root, resolved_path]) == resolved_root
    except ValueError:
        return False


def discover_sessions(codex_home: Path, project_root: str) -> List[SessionRecord]:
    results: List[SessionRecord] = []

    for path in iter_log_files(codex_home):
        meta = read_session_meta(path)
        if not meta:
            continue
        record = to_session_record(path, meta)
        if not record:
            continue
        if not is_within_root(project_root, record.cwd):
            continue
        results.append(record)

    return sorted(results, key=lambda r: parse_iso(r.started_at), reverse=True)


def is_active(log_path: Path, minutes: int) -> bool:
    try:
        modified = datetime.fromtimestamp(log_path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return False
    return modified >= datetime.now(tz=timezone.utc) - timedelta(minutes=minutes)


def extract_message_text(payload: dict) -> str:
    content = payload.get("content", [])
    if not isinstance(content, list):
        return ""
    for item in content:
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        if isinstance(text, str) and text.strip():
            return normalize_whitespace(text)
    return ""


def normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def truncate(text: str, limit: int = 100) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def summarize_event(obj: dict) -> str:
    event_type = obj.get("type")
    if event_type == "session_meta":
        payload = obj.get("payload", {})
        if isinstance(payload, dict):
            cwd = payload.get("cwd", "")
            return f"session start cwd={cwd}"
        return "session start"

    if event_type == "turn_context":
        payload = obj.get("payload", {})
        if isinstance(payload, dict):
            cwd = payload.get("cwd", "")
            return f"turn cwd={cwd}"
        return "turn context"

    if event_type == "response_item":
        payload = obj.get("payload", {})
        if not isinstance(payload, dict):
            return "response item"
        item_type = payload.get("type")
        if item_type == "function_call":
            name = payload.get("name", "unknown")
            return f"tool call {name}"
        if item_type == "function_call_output":
            return "tool output"
        if item_type == "reasoning":
            return "reasoning item"
        if item_type == "message":
            role = payload.get("role", "unknown")
            snippet = extract_message_text(payload)
            if snippet:
                return f"message {role}: {truncate(snippet)}"
            return f"message {role}"
        return f"response item {item_type}"

    if event_type == "event_msg":
        payload = obj.get("payload", {})
        if isinstance(payload, dict):
            msg_type = payload.get("type", "")
            if msg_type == "token_count":
                return ""
            if msg_type:
                return f"event {msg_type}"
        return "event message"

    if event_type:
        return str(event_type)
    return ""


def last_activity(log_path: Path) -> Dict[str, str]:
    last_ts = ""
    last_summary = ""
    try:
        with log_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                summary = summarize_event(obj)
                if not summary:
                    continue
                ts = str(obj.get("timestamp", ""))
                if ts:
                    last_ts = ts
                last_summary = summary
    except OSError:
        pass

    return {"timestamp": last_ts, "summary": last_summary}


def print_table(headers: List[str], rows: List[List[str]]) -> None:
    if not rows:
        print("(no rows)")
        return
    widths = [len(h) for h in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(cell))

    header_line = " | ".join(headers[idx].ljust(widths[idx]) for idx in range(len(headers)))
    separator = "-+-".join("-" * widths[idx] for idx in range(len(headers)))
    print(header_line)
    print(separator)
    for row in rows:
        print(" | ".join(row[idx].ljust(widths[idx]) for idx in range(len(row))))


def command_inventory(args: argparse.Namespace) -> int:
    codex_home = Path(args.codex_home).expanduser()
    sessions = discover_sessions(codex_home, args.project_root)
    recent = sessions[: max(args.recent, 0)]

    rows = []
    for record in recent:
        rows.append(
            {
                "session_id": record.session_id,
                "started_at": record.started_at,
                "role": record.role,
                "parent_thread_id": record.parent_thread_id,
                "depth": record.depth,
                "git_branch": record.git_branch,
                "cwd": record.cwd,
                "log_path": str(record.log_path),
                "active": is_active(record.log_path, args.active_minutes),
            }
        )

    if args.json:
        print(json.dumps({"count": len(sessions), "recent": rows}, indent=2))
        return 0

    print(f"Matched sessions: {len(sessions)}")
    headers = [
        "session_id",
        "started_at",
        "role",
        "branch",
        "active",
        "log_path",
    ]
    table_rows = [
        [
            item["session_id"],
            item["started_at"],
            item["role"],
            item["git_branch"],
            "yes" if item["active"] else "no",
            item["log_path"],
        ]
        for item in rows
    ]
    print_table(headers, table_rows)
    return 0


def command_activity(args: argparse.Namespace) -> int:
    codex_home = Path(args.codex_home).expanduser()
    sessions = discover_sessions(codex_home, args.project_root)
    recent = sessions[: max(args.recent, 0)]

    rows = []
    for record in recent:
        activity = last_activity(record.log_path)
        rows.append(
            {
                "session_id": record.session_id,
                "started_at": record.started_at,
                "cwd": record.cwd,
                "role": record.role,
                "git_branch": record.git_branch,
                "last_timestamp": activity["timestamp"],
                "last_summary": activity["summary"],
                "log_path": str(record.log_path),
            }
        )

    if args.json:
        print(json.dumps({"count": len(sessions), "activity": rows}, indent=2))
        return 0

    headers = [
        "session_id",
        "role",
        "last_timestamp",
        "activity",
        "log_path",
    ]
    table_rows = [
        [
            item["session_id"],
            item["role"],
            item["last_timestamp"],
            truncate(item["last_summary"], 90),
            item["log_path"],
        ]
        for item in rows
    ]
    print_table(headers, table_rows)
    return 0


def command_follow(args: argparse.Namespace) -> int:
    codex_home = Path(args.codex_home).expanduser()
    offsets: Dict[Path, int] = {}
    cache: Dict[Path, SessionRecord] = {}
    recent_cap = max(args.recent, 1)

    print(
        f"Following sessions under {codex_home} for project root {args.project_root}. "
        f"Polling every {args.interval}s. Press Ctrl-C to stop."
    )
    sys.stdout.flush()

    try:
        while True:
            sessions = discover_sessions(codex_home, args.project_root)[:recent_cap]
            cache = {record.log_path: record for record in sessions}

            for record in sessions:
                if not is_active(record.log_path, args.active_minutes):
                    continue
                if record.log_path not in offsets:
                    try:
                        size = record.log_path.stat().st_size
                    except OSError:
                        continue
                    offsets[record.log_path] = 0 if args.from_start else size

            for path in list(offsets):
                if not path.exists():
                    offsets.pop(path, None)
                    continue
                try:
                    with path.open("r", encoding="utf-8") as handle:
                        handle.seek(offsets[path])
                        for line in handle:
                            try:
                                obj = json.loads(line)
                            except json.JSONDecodeError:
                                continue
                            summary = summarize_event(obj)
                            if not summary:
                                continue
                            ts = str(obj.get("timestamp", ""))
                            record = cache.get(path)
                            if record:
                                print(
                                    f"{ts} | {record.session_id} | {record.role} | "
                                    f"{record.cwd} | {summary} | {path}"
                                )
                            else:
                                print(f"{ts} | unknown | {summary} | {path}")
                        offsets[path] = handle.tell()
                except OSError:
                    offsets.pop(path, None)

            sys.stdout.flush()
            time.sleep(max(args.interval, 0.5))
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0


def main() -> int:
    args = parse_args()
    if args.command == "inventory":
        return command_inventory(args)
    if args.command == "activity":
        return command_activity(args)
    if args.command == "follow":
        return command_follow(args)
    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
