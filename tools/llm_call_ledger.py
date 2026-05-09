#!/usr/bin/env python3
"""
ARIS Model Call Ledger — Track Codex / LLM Chat / reviewer calls.

Directory: .aris/calls/
Files:
  - current_call.json  — single current/last active call
  - llm_calls.jsonl    — append-only call history

Commands: start, finish, fail, fallback, status, summary
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


def get_calls_dir() -> Path:
    root = find_project_root()
    calls_dir = root / ".aris" / "calls"
    calls_dir.mkdir(parents=True, exist_ok=True)
    return calls_dir


def generate_call_id() -> str:
    return f"call_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


def create_call_entry(
    skill: str = "",
    role: str = "",
    primary_backend: str = "llm-chat",
    primary_model: str = "",
    input_files: Optional[List[str]] = None,
    output_files: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        "call_id": generate_call_id(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "skill": skill,
        "role": role,
        "primary_backend": primary_backend,
        "primary_model": primary_model,
        "actual_backend": primary_backend,
        "actual_model": primary_model,
        "status": "started",
        "fallback_used": False,
        "fallback_reason": None,
        "duration_sec": 0,
        "input_files": input_files or [],
        "output_files": output_files or [],
        "env_source": ".env",
        "thinking": None,
        "reasoning_effort": None,
        "cache_hit_tokens": None,
        "cache_miss_tokens": None,
        "error": None,
    }


def cmd_start(args: List[str]):
    """Start a new call."""
    entry = create_call_entry(
        skill=args[0] if len(args) > 0 else "",
        role=args[1] if len(args) > 1 else "",
        primary_backend=args[2] if len(args) > 2 else "llm-chat",
        primary_model=args[3] if len(args) > 3 else "",
    )
    call_id = entry["call_id"]
    calls_dir = get_calls_dir()
    (calls_dir / "current_call.json").write_text(
        json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(call_id)
    return call_id


def cmd_finish(args: List[str]):
    """Mark current call as completed."""
    calls_dir = get_calls_dir()
    current_file = calls_dir / "current_call.json"
    if not current_file.exists():
        print("No current call to finish.", file=sys.stderr)
        return

    try:
        entry = json.loads(current_file.read_text(encoding="utf-8"))
    except Exception:
        print("current_call.json corrupt.", file=sys.stderr)
        return

    now = datetime.now(timezone.utc)
    start = datetime.fromisoformat(entry.get("timestamp", now.isoformat()))
    entry["completed_at"] = now.isoformat()
    entry["duration_sec"] = int((now - start).total_seconds())
    entry["status"] = "completed"

    # Append to JSONL
    jsonl_file = calls_dir / "llm_calls.jsonl"
    with open(jsonl_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # Clear current
    current_file.write_text("{}", encoding="utf-8")
    print(f"Call {entry['call_id']} completed.")
    return entry["call_id"]


def cmd_fail(args: List[str]):
    """Mark current call as failed."""
    error = " ".join(args) if args else "unknown error"
    calls_dir = get_calls_dir()
    current_file = calls_dir / "current_call.json"
    if not current_file.exists():
        print("No current call to fail.", file=sys.stderr)
        return

    try:
        entry = json.loads(current_file.read_text(encoding="utf-8"))
    except Exception:
        print("current_call.json corrupt.", file=sys.stderr)
        return

    now = datetime.now(timezone.utc)
    start = datetime.fromisoformat(entry.get("timestamp", now.isoformat()))
    entry["completed_at"] = now.isoformat()
    entry["duration_sec"] = int((now - start).total_seconds())
    entry["status"] = "failed"
    entry["error"] = error

    jsonl_file = calls_dir / "llm_calls.jsonl"
    with open(jsonl_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    current_file.write_text("{}", encoding="utf-8")
    print(f"Call {entry['call_id']} failed: {error}")


def cmd_fallback(
    fallback_model: str, reason: str = "codex unavailable", backend: str = "llm-chat"
):
    """Mark current call as fallback."""
    calls_dir = get_calls_dir()
    current_file = calls_dir / "current_call.json"
    if not current_file.exists():
        print("No current call to fallback.", file=sys.stderr)
        return

    try:
        entry = json.loads(current_file.read_text(encoding="utf-8"))
    except Exception:
        print("current_call.json corrupt.", file=sys.stderr)
        return

    entry["actual_backend"] = backend
    entry["actual_model"] = fallback_model
    entry["fallback_used"] = True
    entry["fallback_reason"] = reason
    entry["status"] = "completed_with_fallback"

    now = datetime.now(timezone.utc)
    start = datetime.fromisoformat(entry.get("timestamp", now.isoformat()))
    entry["completed_at"] = now.isoformat()
    entry["duration_sec"] = int((now - start).total_seconds())

    jsonl_file = calls_dir / "llm_calls.jsonl"
    with open(jsonl_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    current_file.write_text("{}", encoding="utf-8")
    print(f"REVIEWER_DOWNGRADED_FROM_CODEX_TO_LLM_FALLBACK")
    print(f"Call {entry['call_id']} completed with fallback to {fallback_model}")


def cmd_status():
    """Show current call status."""
    calls_dir = get_calls_dir()
    current_file = calls_dir / "current_call.json"
    if not current_file.exists():
        print(json.dumps({"status": "no_call"}, ensure_ascii=False))
        return

    try:
        entry = json.loads(current_file.read_text(encoding="utf-8"))
    except Exception:
        print(json.dumps({"status": "corrupt"}, ensure_ascii=False))
        return

    if not entry or entry == {}:
        print(json.dumps({"status": "idle"}, ensure_ascii=False))
        return

    print(json.dumps(entry, ensure_ascii=False, indent=2))


def cmd_summary(args: List[str]):
    """Show summary of all calls."""
    calls_dir = get_calls_dir()
    jsonl_file = calls_dir / "llm_calls.jsonl"
    if not jsonl_file.exists():
        print(json.dumps({"total_calls": 0, "by_status": {}, "by_backend": {}, "by_skill": {}}, ensure_ascii=False))
        return

    limit = 999999
    if args and args[0].isdigit():
        limit = int(args[0])

    calls: List[Dict] = []
    with open(jsonl_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    calls.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    # Statistics
    total = len(calls)
    by_status: Dict[str, int] = {}
    by_backend: Dict[str, int] = {}
    by_skill: Dict[str, int] = {}
    fallback_count = 0
    failed_count = 0

    for c in calls:
        status = c.get("status", "unknown")
        by_status[status] = by_status.get(status, 0) + 1
        backend = c.get("actual_backend", "unknown")
        by_backend[backend] = by_backend.get(backend, 0) + 1
        skill = c.get("skill", "unknown")
        by_skill[skill] = by_skill.get(skill, 0) + 1
        if c.get("fallback_used"):
            fallback_count += 1
        if status == "failed":
            failed_count += 1

    result = {
        "total_calls": total,
        "fallback_count": fallback_count,
        "failed_count": failed_count,
        "by_status": by_status,
        "by_backend": by_backend,
        "by_skill": by_skill,
    }

    # Recent calls
    recent = calls[-limit:] if limit > 0 else calls
    result["recent_calls"] = [
        {
            "timestamp": c.get("timestamp", ""),
            "skill": c.get("skill", ""),
            "role": c.get("role", ""),
            "primary_backend": c.get("primary_backend", ""),
            "actual_backend": c.get("actual_backend", ""),
            "actual_model": c.get("actual_model", ""),
            "status": c.get("status", ""),
            "fallback_used": c.get("fallback_used", False),
            "error": c.get("error", None),
        }
        for c in recent[-20:]  # last 20
    ]

    print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    if len(sys.argv) < 2:
        print("Usage: llm_call_ledger.py <start|finish|fail|fallback|status|summary> [args...]", file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]
    args = sys.argv[2:]

    if cmd == "start":
        cmd_start(args)
    elif cmd == "finish":
        cmd_finish(args)
    elif cmd == "fail":
        cmd_fail(args)
    elif cmd == "fallback":
        fallback_model = args[0] if args else "deepseek-v4-flash"
        reason = args[1] if len(args) > 1 else "codex unavailable"
        backend = args[2] if len(args) > 2 else "llm-chat"
        cmd_fallback(fallback_model, reason, backend)
    elif cmd == "status":
        cmd_status()
    elif cmd == "summary":
        cmd_summary(args)
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)
    main()
