#!/usr/bin/env python3
"""
ARIS Model Call Ledger — Track Codex / LLM Chat / reviewer calls.

Directory: .aris/calls/
Files:
  - current_call.json  — single current/last active call
  - llm_calls.jsonl  — append-only call history

Commands: start, finish, fail, fallback, status, summary

Trust Tracking Fields:
  implementation_source: external_agent_direct | routed_internal_model
  routed_model_used: true | false
  route_role, route_expected_backend, route_expected_model
  external_agent_name
  verification_status: started_unverified | unverified_external_execution |
    verified_routed_call | verified_with_fallback |
    missing_actual_backend | codex_missing_thread_id |
    fallback_unverified | completed_with_warnings
  allowed_next_stage: true | false
  confidence_downgraded: true | false
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
    # New trust fields
    implementation_source: str = "external_agent_direct",
    routed_model_used: bool = False,
    route_role: str = "",
    route_expected_backend: str = "",
    route_expected_model: str = "",
    external_agent_name: Optional[str] = None,
    global_codex_gate_mode: Optional[str] = None,
    routing_source: str = "env",
) -> Dict[str, Any]:
    entry = {
        "call_id": generate_call_id(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "skill": skill,
        "role": role,
        "primary_backend": primary_backend,
        "primary_model": primary_model,
        "actual_backend": "",   # MUST be empty — not primary_backend
        "actual_model": "",      # MUST be empty — not primary_model
        "status": "started",
        "fallback_used": False,
        "fallback_reason": None,
        "duration_sec": 0,
        "input_files": input_files or [],
        "output_files": output_files or [],
        "env_source": ".env",
        "routing_source": routing_source,
        "global_codex_gate_mode": global_codex_gate_mode,
        "thinking": None,
        "reasoning_effort": None,
        "cache_hit_tokens": None,
        "cache_miss_tokens": None,
        "error": None,
        # Trust fields
        "implementation_source": implementation_source,
        "routed_model_used": routed_model_used,
        "route_role": route_role or role,
        "route_expected_backend": route_expected_backend or primary_backend,
        "route_expected_model": route_expected_model or primary_model,
        "external_agent_name": external_agent_name,
        "verification_status": "started_unverified",
        "allowed_next_stage": False,
        "confidence_downgraded": True,
        # Legacy-compatible fields
        "codex_used": None,
        "codex_thread_id": None,
    }
    return entry


def cmd_start(args: List[str]):
    """Start a new call.

    Positional: skill role backend model
    Named: --implementation-source --routed-model-used --route-role
           --route-expected-backend --route-expected-model --external-agent-name
           --global-codex-gate-mode --routing-source
    """
    kwargs = _parse_kwargs(args)
    pos = [a for a in args if not a.startswith("--")]
    skill = pos[0] if len(pos) > 0 else ""
    role = pos[1] if len(pos) > 1 else ""
    primary_backend = pos[2] if len(pos) > 2 else "llm-chat"
    primary_model = pos[3] if len(pos) > 3 else ""

    impl_source = kwargs.get("implementation_source", "external_agent_direct")
    routed_used_str = kwargs.get("routed_model_used", "false")
    routed_used = routed_used_str.lower() in ("true", "1", "yes")
    route_role = kwargs.get("route_role", "")
    route_backend = kwargs.get("route_expected_backend", "")
    route_model = kwargs.get("route_expected_model", "")
    ext_agent = kwargs.get("external_agent_name")
    gate_mode = kwargs.get("global_codex_gate_mode")
    routing_src = kwargs.get("routing_source", "env")

    entry = create_call_entry(
        skill=skill,
        role=role,
        primary_backend=primary_backend,
        primary_model=primary_model,
        implementation_source=impl_source,
        routed_model_used=routed_used,
        route_role=route_role or role,
        route_expected_backend=route_backend or primary_backend,
        route_expected_model=route_model or primary_model,
        external_agent_name=ext_agent,
        global_codex_gate_mode=gate_mode,
        routing_source=routing_src,
    )
    call_id = entry["call_id"]
    calls_dir = get_calls_dir()
    (calls_dir / "current_call.json").write_text(
        json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(call_id)
    return call_id


def _parse_kwargs(args: List[str]) -> dict:
    """Extract --key value pairs from args list."""
    kwargs = {}
    i = 0
    while i < len(args):
        if args[i].startswith("--"):
            key = args[i][2:].replace("-", "_")
            if i + 1 < len(args) and not args[i + 1].startswith("--"):
                val = args[i + 1]
                if key == "output_file":
                    kwargs.setdefault("output_files", []).append(val)
                else:
                    kwargs[key] = val
                i += 2
            else:
                kwargs[key] = True
                i += 1
        else:
            i += 1
    return kwargs


def cmd_finish(args: List[str]):
    """Mark current call as completed.

    Optional named params (parsed from args):
      --codex-thread-id <id>
      --isolation-mode <codex_thread|manual_subsession|protocol_only>
      --actual-backend <codex|llm-chat|api>
      --actual-model <model or DEFAULT>
      --output-file <path>  (may repeat)
      --selection-mode <codex_gate|llm_fallback_gate|manual_override>
      --codex-used <true|false>
      --confidence-downgraded <true|false>
      --routing-source <env|manual>
      --global-codex-gate-mode <codex_required|codex_preferred|deepseek_only>
      --implementation-source <external_agent_direct|routed_internal_model>
      --routed-model-used <true|false>
      --verification-status <status>
      --allowed-next-stage <true|false>
      --external-agent-name <name>
      --route-role <role>
      --route-expected-backend <backend>
      --route-expected-model <model>
    """
    kwargs = _parse_kwargs(args)
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

    ext_agent = kwargs.get("external_agent_name")

    now = datetime.now(timezone.utc)
    start = datetime.fromisoformat(entry.get("timestamp", now.isoformat()))
    entry["completed_at"] = now.isoformat()
    entry["duration_sec"] = int((now - start).total_seconds())

    # Apply optional overrides
    codex_thread_id = kwargs.get("codex_thread_id") or entry.get("codex_thread_id")
    isolation_mode = kwargs.get("isolation_mode") or entry.get("isolation_mode")
    actual_backend = kwargs.get("actual_backend") or entry.get("actual_backend")
    actual_model = kwargs.get("actual_model") or entry.get("actual_model")
    output_files = kwargs.get("output_files") or entry.get("output_files", [])
    selection_mode = kwargs.get("selection_mode") or entry.get("selection_mode")
    codex_used = kwargs.get("codex_used") or entry.get("codex_used")
    routing_source = kwargs.get("routing_source") or entry.get("routing_source", "env")
    global_codex_gate_mode = kwargs.get("global_codex_gate_mode") or entry.get("global_codex_gate_mode")
    impl_source = kwargs.get("implementation_source") or entry.get("implementation_source", "external_agent_direct")
    routed_used_str = kwargs.get("routed_model_used")
    if routed_used_str is not None:
        entry["routed_model_used"] = routed_used_str.lower() in ("true", "1", "yes")
    if codex_thread_id:
        entry["codex_thread_id"] = codex_thread_id
    if isolation_mode:
        entry["isolation_mode"] = isolation_mode
    if actual_backend:
        entry["actual_backend"] = actual_backend
    if actual_model:
        entry["actual_model"] = actual_model
    if output_files:
        entry["output_files"] = output_files
    if selection_mode:
        entry["selection_mode"] = selection_mode
    if codex_used:
        entry["codex_used"] = codex_used
    if routing_source:
        entry["routing_source"] = routing_source
    if global_codex_gate_mode:
        entry["global_codex_gate_mode"] = global_codex_gate_mode
    if impl_source:
        entry["implementation_source"] = impl_source
    ext_agent = kwargs.get("external_agent_name")
    if ext_agent:
        entry["external_agent_name"] = ext_agent
    route_role = kwargs.get("route_role")
    if route_role:
        entry["route_role"] = route_role
    route_backend = kwargs.get("route_expected_backend")
    if route_backend:
        entry["route_expected_backend"] = route_backend
    route_model = kwargs.get("route_expected_model")
    if route_model:
        entry["route_expected_model"] = route_model

    # NOTE: verification_status and allowed_next_stage are determined ONLY by _auto_verify.
    # Caller CANNOT override them — they are security-critical fields.
    # confidence_downgraded is also determined by _auto_verify.
    # Do NOT pass --verification-status or --allowed-next-stage from caller.

    # Auto-verification: determine verification_status and allowed_next_stage
    _auto_verify(entry)

    # Legacy: keep actual_backend in sync for backward compat
    eff_backend = entry.get("actual_backend", "")
    if eff_backend == "codex" and not entry.get("codex_thread_id"):
        entry["status"] = "completed_with_warnings"
    elif entry.get("codex_used") is not None:
        cu = str(entry.get("codex_used")).lower().strip()
        if cu in ("false", "0", "no"):
            entry["status"] = "completed_with_warnings"
    else:
        entry["status"] = "completed"

    # Append to JSONL
    jsonl_file = calls_dir / "llm_calls.jsonl"
    with open(jsonl_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    current_file.write_text("{}", encoding="utf-8")
    print(f"Call {entry['call_id']} completed.")
    return entry["call_id"]


def _auto_verify(entry: Dict[str, Any]):
    """Auto-determine verification_status and allowed_next_stage based on trust fields.

    This ALWAYS determines the final value — caller CANNOT override.
    """
    impl_source = entry.get("implementation_source", "external_agent_direct")
    routed_used = entry.get("routed_model_used", False)
    actual_backend = entry.get("actual_backend", "")
    actual_model = entry.get("actual_model", "")
    fallback_used = entry.get("fallback_used", False)
    fallback_reason = entry.get("fallback_reason")
    codex_thread_id = entry.get("codex_thread_id", "")
    dry_run = entry.get("dry_run", False)
    call_failed = entry.get("status") == "failed"

    # call_failed always wins
    if call_failed:
        entry["verification_status"] = "call_failed"
        entry["allowed_next_stage"] = False
        entry["confidence_downgraded"] = True
        return

    if dry_run:
        entry["verification_status"] = "dry_run_untrusted"
        entry["allowed_next_stage"] = False
        entry["confidence_downgraded"] = True
        return

    if impl_source == "external_agent_direct":
        entry["verification_status"] = "unverified_external_execution"
        entry["confidence_downgraded"] = True
        entry["allowed_next_stage"] = False
        return

    if routed_used and not actual_backend:
        entry["verification_status"] = "missing_actual_backend"
        entry["allowed_next_stage"] = False
        entry["confidence_downgraded"] = True
        return

    if impl_source == "routed_internal_model" and actual_backend:
        if actual_backend == "codex":
            if not codex_thread_id or codex_thread_id.strip() in ("none", ""):
                entry["verification_status"] = "codex_missing_thread_id"
                entry["status"] = "completed_with_warnings"
                entry["allowed_next_stage"] = False
                entry["confidence_downgraded"] = True
            else:
                entry["verification_status"] = "verified_routed_call"
                entry["allowed_next_stage"] = True
                entry["confidence_downgraded"] = False
        elif fallback_used:
            if actual_backend and actual_model and fallback_reason:
                entry["verification_status"] = "verified_with_fallback"
                entry["confidence_downgraded"] = True
                # allowed_next_stage is caller-decided; keep False unless explicitly set
                if entry.get("allowed_next_stage") is None:
                    entry["allowed_next_stage"] = False
            else:
                entry["verification_status"] = "fallback_unverified"
                entry["allowed_next_stage"] = False
                entry["confidence_downgraded"] = True
        else:
            entry["verification_status"] = "verified_routed_call"
            entry["allowed_next_stage"] = True
            entry["confidence_downgraded"] = False


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
    entry["verification_status"] = "call_failed"
    entry["allowed_next_stage"] = False

    jsonl_file = calls_dir / "llm_calls.jsonl"
    with open(jsonl_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    current_file.write_text("{}", encoding="utf-8")
    print(f"Call {entry['call_id']} failed: {error}")


def cmd_fallback(
    fallback_model: str, reason: str = "codex unavailable", backend: str = "llm-chat",
    codex_thread_id: str = "",
    selection_mode: str = "",
    codex_used: str = "",
    confidence_downgraded: str = "",
    routing_source: str = "",
    global_codex_gate_mode: str = "",
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

    role = entry.get("role", "")
    if role == "final_selector":
        entry["status"] = "completed_with_warnings"
    else:
        entry["status"] = "completed_with_fallback"

    if codex_thread_id:
        entry["codex_thread_id"] = codex_thread_id
    entry["isolation_mode"] = "protocol_only"

    if selection_mode:
        entry["selection_mode"] = selection_mode
    if codex_used:
        entry["codex_used"] = codex_used
    if confidence_downgraded:
        entry["confidence_downgraded"] = confidence_downgraded
    else:
        entry["confidence_downgraded"] = True
    if routing_source:
        entry["routing_source"] = routing_source
    if global_codex_gate_mode:
        entry["global_codex_gate_mode"] = global_codex_gate_mode

    _auto_verify(entry)

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

    recent = calls[-limit:] if limit > 0 else calls
    result["recent_calls"] = [
        {
            "timestamp": c.get("timestamp", ""),
            "call_id": c.get("call_id", ""),
            "skill": c.get("skill", ""),
            "role": c.get("role", ""),
            "primary_backend": c.get("primary_backend", ""),
            "actual_backend": c.get("actual_backend", ""),
            "actual_model": c.get("actual_model", ""),
            "status": c.get("status", ""),
            "fallback_used": c.get("fallback_used", False),
            "fallback_reason": c.get("fallback_reason"),
            "codex_used": c.get("codex_used", None),
            "codex_thread_id": c.get("codex_thread_id", None),
            "confidence_downgraded": c.get("confidence_downgraded", None),
            "selection_mode": c.get("selection_mode", None),
            "error": c.get("error", None),
            # Trust fields
            "implementation_source": c.get("implementation_source", ""),
            "routed_model_used": c.get("routed_model_used", False),
            "route_role": c.get("route_role", ""),
            "route_expected_backend": c.get("route_expected_backend", ""),
            "route_expected_model": c.get("route_expected_model", ""),
            "verification_status": c.get("verification_status", ""),
            "allowed_next_stage": c.get("allowed_next_stage", None),
        }
        for c in recent[-20:]
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
        fallback_model = args[0] if args and not args[0].startswith("--") else "deepseek-v4-flash"
        reason = args[1] if len(args) > 1 and not args[1].startswith("--") else "codex unavailable"
        backend = args[2] if len(args) > 2 and not args[2].startswith("--") else "llm-chat"
        fw_kwargs = _parse_kwargs(args)
        codex_thread_id = fw_kwargs.get("codex_thread_id", "")
        selection_mode = fw_kwargs.get("selection_mode", "")
        codex_used = fw_kwargs.get("codex_used", "")
        confidence_downgraded = fw_kwargs.get("confidence_downgraded", "")
        routing_source = fw_kwargs.get("routing_source", "")
        global_codex_gate_mode = fw_kwargs.get("global_codex_gate_mode", "")
        cmd_fallback(fallback_model, reason, backend, codex_thread_id=codex_thread_id,
                     selection_mode=selection_mode, codex_used=codex_used,
                     confidence_downgraded=confidence_downgraded,
                     routing_source=routing_source,
                     global_codex_gate_mode=global_codex_gate_mode)
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
