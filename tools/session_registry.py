#!/usr/bin/env python3
"""
ARIS Session Registry — Manage multi-session research workflow.

Commands:
  init                          Initialize session registry and tasks
  register <role>               Register a new session
  list                          List all registered sessions
  close <session_id>            Close a session
  assign <session_id> <desc>    Assign a task to a session
  tasks                         List all tasks
  handoff <task_id> [status]    Generate handoff file (default: draft; auto-downgrades to needs_review if TODO remains)
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

TOOLS_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(TOOLS_DIR))

from env_loader import find_project_root


def get_sessions_dir() -> Path:
    root = find_project_root()
    sess_dir = root / ".aris" / "sessions"
    sess_dir.mkdir(parents=True, exist_ok=True)
    return sess_dir


def get_handoffs_dir() -> Path:
    sess_dir = get_sessions_dir()
    handoffs_dir = sess_dir / "HANDOFFS"
    handoffs_dir.mkdir(parents=True, exist_ok=True)
    return handoffs_dir


def _read_json(path: Path) -> Any:
    """Read JSON file or return empty dict."""
    if not path.exists():
        return {} if path.name.endswith("current_call.json") else {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"_corrupt": True, "_path": str(path)}


def _write_json(path: Path, data: Any):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def cmd_init():
    """Initialize session registry and active tasks."""
    sess_dir = get_sessions_dir()
    registry_file = sess_dir / "SESSION_REGISTRY.json"
    tasks_file = sess_dir / "ACTIVE_TASKS.json"
    handoffs_dir = get_handoffs_dir()

    if not registry_file.exists():
        _write_json(registry_file, {"sessions": []})
    if not tasks_file.exists():
        _write_json(tasks_file, {"tasks": []})

    print(json.dumps({
        "registry": str(registry_file),
        "tasks": str(tasks_file),
        "handoffs": str(handoffs_dir),
    }, ensure_ascii=False, indent=2))


def cmd_register(args: List[str]):
    """Register a new session."""
    role = args[0] if args else "unknown"
    sess_dir = get_sessions_dir()
    registry_file = sess_dir / "SESSION_REGISTRY.json"

    registry = _read_json(registry_file)
    if isinstance(registry, dict) and registry.get("_corrupt"):
        registry = {"sessions": []}
        _write_json(registry_file, registry)

    session_id = f"sess_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"

    session = {
        "session_id": session_id,
        "role": role,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "active",
        "input_files": [],
        "output_files": [],
        "owner": "manual",
        "current_task": None,
        "last_handoff": None,
    }

    if "sessions" not in registry:
        registry["sessions"] = []
    registry["sessions"].append(session)
    _write_json(registry_file, registry)

    print(json.dumps(session, ensure_ascii=False, indent=2))


def cmd_list():
    """List all registered sessions."""
    sess_dir = get_sessions_dir()
    registry_file = sess_dir / "SESSION_REGISTRY.json"
    registry = _read_json(registry_file)

    sessions = registry.get("sessions", [])
    summary = []
    for s in sessions:
        summary.append({
            "session_id": s.get("session_id", ""),
            "role": s.get("role", ""),
            "status": s.get("status", ""),
            "current_task": s.get("current_task"),
            "created_at": s.get("created_at", ""),
        })
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def cmd_close(args: List[str]):
    """Close a session by ID."""
    session_id = args[0] if args else ""
    if not session_id:
        print("Usage: session_registry.py close <session_id>", file=sys.stderr)
        sys.exit(1)

    sess_dir = get_sessions_dir()
    registry_file = sess_dir / "SESSION_REGISTRY.json"
    registry = _read_json(registry_file)

    sessions = registry.get("sessions", [])
    for s in sessions:
        if s.get("session_id") == session_id:
            s["status"] = "closed"
            _write_json(registry_file, registry)
            print(f"Session {session_id} closed.")
            return

    print(f"Session {session_id} not found.", file=sys.stderr)
    sys.exit(1)


def cmd_assign(args: List[str]):
    """Assign a task to a session.

    Supports --input <file> and --output <file> flags for specifying
    input/output files in the task record.
    """
    if len(args) < 2:
        print("Usage: session_registry.py assign <session_id> <task_description> [--input <file> ...] [--output <file> ...]", file=sys.stderr)
        sys.exit(1)

    session_id = args[0]

    # Parse --input and --output flags
    input_files: List[str] = []
    output_files: List[str] = []
    desc_parts: List[str] = []
    i = 1
    while i < len(args):
        a = args[i]
        if a == "--input" and i + 1 < len(args):
            i += 1
            input_files.append(args[i])
        elif a == "--output" and i + 1 < len(args):
            i += 1
            output_files.append(args[i])
        else:
            desc_parts.append(a)
        i += 1

    task_desc = " ".join(desc_parts) if desc_parts else "(no description)"
    sess_dir = get_sessions_dir()
    registry_file = sess_dir / "SESSION_REGISTRY.json"
    tasks_file = sess_dir / "ACTIVE_TASKS.json"

    # Validate session exists
    registry = _read_json(registry_file)
    if isinstance(registry, dict) and registry.get("_corrupt"):
        print("SESSION_REGISTRY.json corrupt. Run init first.", file=sys.stderr)
        sys.exit(1)

    sessions = registry.get("sessions", [])
    target_session = None
    for s in sessions:
        if s.get("session_id") == session_id:
            target_session = s
            break

    if target_session is None:
        print(f"Error: session {session_id} not found. Register the session first.", file=sys.stderr)
        sys.exit(1)

    # Read tasks
    tasks = _read_json(tasks_file)
    if isinstance(tasks, dict) and tasks.get("_corrupt"):
        tasks = {"tasks": []}
        _write_json(tasks_file, tasks)

    now = datetime.now(timezone.utc)
    task_id = f"task_{now.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"

    task = {
        "task_id": task_id,
        "description": task_desc,
        "assigned_session": session_id,
        "role": target_session.get("role", ""),
        "status": "pending",
        "input_files": input_files,
        "expected_output_files": output_files,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "handoff": None,
    }

    if "tasks" not in tasks:
        tasks["tasks"] = []
    tasks["tasks"].append(task)
    _write_json(tasks_file, tasks)

    # Update session
    target_session["current_task"] = task_id
    target_session["status"] = "active"
    target_session["updated_at"] = now.isoformat()
    _write_json(registry_file, registry)

    print(json.dumps(task, ensure_ascii=False, indent=2))


def cmd_tasks(args: List[str]):
    """List all active tasks."""
    sess_dir = get_sessions_dir()
    tasks_file = sess_dir / "ACTIVE_TASKS.json"
    tasks = _read_json(tasks_file)

    task_list = tasks.get("tasks", [])
    summary = []
    for t in task_list:
        summary.append({
            "task_id": t.get("task_id", ""),
            "description": t.get("description", ""),
            "status": t.get("status", ""),
            "assigned_session": t.get("assigned_session", ""),
        })
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def cmd_handoff(args: List[str]):
    """Generate handoff file for a task.

    Default status is "draft". Use "done" only after filling all TODO fields.
    If handoff still contains TODO when status=done is requested,
    status is downgraded to "needs_review" automatically.
    Existing handoff files are never overwritten.
    """
    if len(args) < 1:
        print("Usage: session_registry.py handoff <task_id> [status]", file=sys.stderr)
        sys.exit(1)

    task_id = args[0]
    requested_status = args[1] if len(args) > 1 else "draft"
    sess_dir = get_sessions_dir()
    handoffs_dir = get_handoffs_dir()
    tasks_file = sess_dir / "ACTIVE_TASKS.json"
    registry_file = sess_dir / "SESSION_REGISTRY.json"

    # Find task
    tasks_data = _read_json(tasks_file)
    if isinstance(tasks_data, dict) and tasks_data.get("_corrupt"):
        print("ACTIVE_TASKS.json corrupt. Run init first.", file=sys.stderr)
        sys.exit(1)

    task = None
    for t in tasks_data.get("tasks", []):
        if t.get("task_id") == task_id:
            task = t
            break

    if task is None:
        print(f"Task {task_id} not found.", file=sys.stderr)
        sys.exit(1)

    session_id = task.get("assigned_session", "")
    role = task.get("role", "")

    # Find session
    registry = _read_json(registry_file)
    target_session = None
    for s in registry.get("sessions", []):
        if s.get("session_id") == session_id:
            target_session = s
            break

    now = datetime.now(timezone.utc)
    handoff_file = handoffs_dir / f"{task_id}.md"

    # Create or read handoff file
    if handoff_file.exists():
        handoff_content = handoff_file.read_text(encoding="utf-8")
    else:
        handoff_md = f"""# Handoff: {task_id}

## Metadata
- task_id: {task_id}
- role: {role}
- session_id: {session_id}
- created_at: {task.get("created_at", "")}
- status: {requested_status}

## Input Files
{_format_list(task.get("input_files", []))}

## Output Files
{_format_list(task.get("expected_output_files", []))}

## Decision
TODO: Fill decision.

## Evidence
TODO: Add evidence files, metrics, logs, or paper sections.

## Failure Modes
TODO: Add likely failure modes.

## Unresolved Questions
TODO: Add unresolved questions.

## Next Action
TODO: Add next action for main_architect.

## Do Not Assume
- Do not assume this handoff is complete until evidence is filled.
- Do not infer claims not supported by listed evidence.
"""
        handoffs_dir.mkdir(parents=True, exist_ok=True)
        handoff_file.write_text(handoff_md, encoding="utf-8")
        handoff_content = handoff_md

    # Determine actual status based on TODO content
    has_todo = "TODO:" in handoff_content

    if requested_status == "done" and has_todo:
        actual_status = "needs_review"
        print("⚠️  handoff contains TODO fields; status downgraded from done to needs_review", file=sys.stderr)
    else:
        actual_status = requested_status

    terminal_statuses = {"done", "failed", "blocked"}
    non_idle_statuses = {"failed", "blocked"}

    # Update task
    task["status"] = actual_status
    task["updated_at"] = now.isoformat()
    task["handoff"] = str(handoff_file)
    _write_json(tasks_file, tasks_data)

    # Update session if found
    if target_session:
        target_session["last_handoff"] = str(handoff_file)
        if actual_status in terminal_statuses:
            target_session["current_task"] = None
        else:
            target_session["current_task"] = task_id
        if actual_status == "done":
            target_session["status"] = "idle"
        elif actual_status == "failed":
            target_session["status"] = "failed"
        elif actual_status == "blocked":
            target_session["status"] = "blocked"
        else:
            target_session["status"] = "active"
        target_session["updated_at"] = now.isoformat()
        _write_json(registry_file, registry)

    result = {
        "task_id": task_id,
        "handoff": str(handoff_file),
        "status": actual_status,
        "session_id": session_id,
        "role": role,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _format_list(items: list) -> str:
    if not items:
        return "- (none)"
    return "\n".join(f"- {i}" for i in items)


def main():
    if len(sys.argv) < 2:
        cmd_list()
        return

    cmd = sys.argv[1]
    args = sys.argv[2:]

    if cmd == "init":
        cmd_init()
    elif cmd == "register":
        cmd_register(args)
    elif cmd == "list":
        cmd_list()
    elif cmd == "close":
        cmd_close(args)
    elif cmd == "assign":
        cmd_assign(args)
    elif cmd == "tasks":
        cmd_tasks(args)
    elif cmd == "handoff":
        cmd_handoff(args)
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        print("Usage: session_registry.py <init|register|list|close|assign|tasks|handoff> [args...]", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)
    main()
