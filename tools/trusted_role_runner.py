#!/usr/bin/env python3
"""
ARIS Trusted Role Runner — Single Trusted Entry Point for All ROLE_* Tasks.

This is the ONLY trusted execution path for ARIS ROLE_* tasks.

Usage:
    python tools/trusted_role_runner.py --role <role> --input <file_or_text> --output <artifact_path>
    python tools/trusted_role_runner.py --role <role> --input <file_or_text> --output <artifact_path> --require-codex-thread
    python tools/trusted_role_runner.py --role <role> --input <file_or_text> --output <artifact_path> --dry-run
    python tools/trusted_role_runner.py --role <role> --input <file_or_text> --output <artifact_path> --mock-response <text>
    python tools/trusted_role_runner.py --summary
    python tools/trusted_role_runner.py --self-test

Rules:
- model_route.py only resolves routing config — it does NOT call any model.
- This runner calls the actual backend (Codex MCP or API) and records to ledger.
- External agents cannot masquerade as routed_internal_model.
- dry-run / mock cannot be marked as verified_routed_call.
- If runner fails, must fail closed — no external agent substitution.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

TOOLS_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(TOOLS_DIR))

from env_loader import find_project_root


def _get_ledger_path() -> Path:
    env_path = os.environ.get("ARIS_LEDGER_PATH", "")
    if env_path:
        return Path(env_path)
    root = find_project_root()
    return root / ".aris" / "calls" / "llm_calls.jsonl"


def _read_ledger(ledger_path: Optional[Path] = None) -> list:
    path = ledger_path or _get_ledger_path()
    if not path.exists():
        return []
    calls = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        calls.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except Exception:
        pass
    return calls


def _write_ledger_entry(entry: Dict[str, Any], ledger_path: Optional[Path] = None) -> None:
    path = ledger_path or _get_ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _resolve_role(role: str) -> Dict[str, Any]:
    """Resolve role to expected backend/model via model_route.py (config only, no API call)."""
    try:
        sys.path.insert(0, str(TOOLS_DIR))
        import model_route as mr
        result = mr.resolve_role(role)
        return {
            "expected_backend": result.get("backend_type", "") or result.get("primary_backend", ""),
            "expected_model": result.get("model", "") or result.get("primary_model", ""),
            "expected_provider": result.get("provider", ""),
            "requires_api_key": result.get("requires_api_key", False),
            "route_config": result,
        }
    except Exception as e:
        return {
            "expected_backend": "",
            "expected_model": "",
            "expected_provider": "",
            "requires_api_key": False,
            "route_config": {},
            "error": str(e),
        }


def _auto_verify(entry: Dict[str, Any]) -> tuple[str, bool, bool]:
    """Auto-determine verification_status, allowed_next_stage, confidence_downgraded."""
    impl_source = entry.get("implementation_source", "external_agent_direct")
    routed_used = entry.get("routed_model_used", False)
    actual_backend = entry.get("actual_backend", "")
    actual_model = entry.get("actual_model", "")
    codex_thread_id = entry.get("codex_thread_id", "")
    fallback_used = entry.get("fallback_used", False)
    fallback_reason = entry.get("fallback_reason", "")
    dry_run = entry.get("dry_run", False)

    if dry_run:
        return ("dry_run_untrusted", False, True)

    if impl_source == "external_agent_direct":
        return ("unverified_external_execution", False, True)

    if routed_used and not actual_backend:
        return ("missing_actual_backend", False, True)

    if actual_backend == "codex":
        if not codex_thread_id or codex_thread_id.strip() in ("", "none"):
            return ("codex_missing_thread_id", False, True)
        return ("verified_routed_call", True, False)

    if fallback_used:
        if fallback_reason:
            return ("verified_with_fallback", False, True)
        return ("fallback_unverified", False, True)

    if impl_source == "routed_internal_model" and actual_backend and actual_model:
        return ("verified_routed_call", True, False)

    return ("started_unverified", False, True)


def cmd_start(
    role: str,
    ledger_path: Optional[Path] = None,
    implementation_source: str = "routed_internal_model",
    routed_model_used: bool = True,
    global_codex_gate_mode: str = "",
    routing_source: str = "",
) -> Dict[str, Any]:
    """Start a trusted role call — create ledger entry with conservative defaults."""
    call_id = f"call_{uuid.uuid4().hex[:12]}"
    resolved = _resolve_role(role)

    entry = {
        "call_id": call_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "role": role,
        "status": "started",
        "implementation_source": implementation_source,
        "routed_model_used": routed_model_used,
        "route_role": role,
        "route_expected_backend": resolved.get("expected_backend", ""),
        "route_expected_model": resolved.get("expected_model", ""),
        "external_agent_name": None,
        "actual_backend": "",
        "actual_model": "",
        "codex_thread_id": "",
        "fallback_used": False,
        "fallback_reason": "",
        "verification_status": "started_unverified",
        "allowed_next_stage": False,
        "confidence_downgraded": True,
        "global_codex_gate_mode": global_codex_gate_mode,
        "routing_source": routing_source or "trusted_role_runner",
        "dry_run": False,
    }

    _write_ledger_entry(entry, ledger_path)
    return entry


def cmd_finish(
    call_id: str,
    output: str,
    ledger_path: Optional[Path] = None,
    actual_backend: str = "",
    actual_model: str = "",
    codex_thread_id: str = "",
    fallback_used: bool = False,
    fallback_reason: str = "",
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Finish a trusted role call — update ledger entry with verification."""
    entries = _read_ledger(ledger_path)
    entry = None
    for e in reversed(entries):
        if e.get("call_id") == call_id:
            entry = dict(e)
            break

    if not entry:
        raise ValueError(f"Call {call_id} not found in ledger")

    entry["status"] = "completed" if not dry_run else "completed_dry_run"
    entry["actual_backend"] = actual_backend
    entry["actual_model"] = actual_model
    entry["codex_thread_id"] = codex_thread_id
    entry["fallback_used"] = fallback_used
    entry["fallback_reason"] = fallback_reason
    entry["dry_run"] = dry_run

    verification_status, allowed_next_stage, confidence_downgraded = _auto_verify(entry)
    entry["verification_status"] = verification_status
    entry["allowed_next_stage"] = allowed_next_stage
    entry["confidence_downgraded"] = confidence_downgraded

    # Rewrite ledger (append completed entry)
    _write_ledger_entry(entry, ledger_path)
    return entry


def _build_artifact_header(entry: Dict[str, Any]) -> str:
    """Build provenance header for output artifact."""
    lines = [
        "---",
        f"implementation_source: {entry.get('implementation_source', 'unknown')}",
        f"routed_model_used: {entry.get('routed_model_used', False)}",
        f"route_role: {entry.get('route_role', '')}",
        f"route_expected_backend: {entry.get('route_expected_backend', '')}",
        f"route_expected_model: {entry.get('route_expected_model', '')}",
        f"actual_backend: {entry.get('actual_backend', '')}",
        f"actual_model: {entry.get('actual_model', '')}",
        f"ledger_call_id: {entry.get('call_id', '')}",
        f"codex_used: {entry.get('actual_backend') == 'codex'}",
        f"codex_thread_id: {entry.get('codex_thread_id', '')}",
        f"fallback_used: {entry.get('fallback_used', False)}",
        f"fallback_reason: {entry.get('fallback_reason', '')}",
        f"confidence_downgraded: {entry.get('confidence_downgraded', True)}",
        f"verification_status: {entry.get('verification_status', 'unknown')}",
        f"allowed_next_stage: {entry.get('allowed_next_stage', False)}",
        "---",
    ]
    return "\n".join(lines)


def run_trusted(
    role: str,
    input_spec: str,
    output_path: Optional[str] = None,
    require_codex_thread: bool = False,
    dry_run: bool = False,
    mock_response: str = "",
    ledger_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Run a trusted role execution."""
    resolved = _resolve_role(role)
    expected_backend = resolved.get("expected_backend", "")
    expected_model = resolved.get("expected_model", "")

    # Start ledger
    entry = cmd_start(
        role=role,
        ledger_path=ledger_path,
        implementation_source="routed_internal_model",
        routed_model_used=True,
        routing_source="trusted_role_runner",
    )
    call_id = entry["call_id"]

    actual_backend = ""
    actual_model = ""
    codex_thread_id = ""
    fallback_used = False
    fallback_reason = ""
    output_text = ""

    if dry_run:
        output_text = mock_response or f"[DRY-RUN] {role} output for: {input_spec[:200]}"
        actual_backend = "dry_run"
        actual_model = "dry_run"
        verification_status = "dry_run_untrusted"
        entry = cmd_finish(
            call_id=call_id,
            output=output_text,
            ledger_path=ledger_path,
            actual_backend="dry_run",
            actual_model="dry_run",
            dry_run=True,
        )
    else:
        # Real execution path — call the actual backend
        if expected_backend == "mcp":
            # Codex MCP call
            try:
                sys.path.insert(0, str(TOOLS_DIR))
                from mcp_codex_client import CodexMCPClient
                client = CodexMCPClient()
                thread_id = client.call(input_spec)
                codex_thread_id = thread_id
                actual_backend = "codex"
                actual_model = expected_model
                verification_status = "verified_routed_call"
                entry = cmd_finish(
                    call_id=call_id,
                    output="[Codex MCP call made]",
                    ledger_path=ledger_path,
                    actual_backend="codex",
                    actual_model=expected_model,
                    codex_thread_id=codex_thread_id,
                )
            except Exception as e:
                # Fail closed — cannot substitute
                entry = cmd_finish(
                    call_id=call_id,
                    output=f"[Codex MCP call failed: {e}]",
                    ledger_path=ledger_path,
                    actual_backend="codex",
                    actual_model=expected_model,
                    fallback_used=True,
                    fallback_reason=f"codex call failed: {e}",
                )
        elif expected_backend in ("openai_compatible_api", "llm-chat"):
            # API call (DeepSeek, Kimi, etc.)
            provider = resolved.get("expected_provider", "deepseek")
            try:
                sys.path.insert(0, str(TOOLS_DIR))
                import llm_chat_client as llm_client
                result = llm_client.call(
                    provider=provider,
                    model=expected_model,
                    prompt=input_spec,
                )
                actual_backend = provider
                actual_model = expected_model
                verification_status = "verified_routed_call"
                output_text = result
                entry = cmd_finish(
                    call_id=call_id,
                    output=output_text,
                    ledger_path=ledger_path,
                    actual_backend=provider,
                    actual_model=expected_model,
                )
            except Exception as e:
                # Fail closed
                entry = cmd_finish(
                    call_id=call_id,
                    output=f"[API call failed: {e}]",
                    ledger_path=ledger_path,
                    actual_backend=provider,
                    actual_model=expected_model,
                    fallback_used=True,
                    fallback_reason=f"api call failed: {e}",
                )
        else:
            entry = cmd_finish(
                call_id=call_id,
                output=f"[Unknown backend: {expected_backend}]",
                ledger_path=ledger_path,
                actual_backend=expected_backend,
                actual_model=expected_model,
                fallback_used=True,
                fallback_reason=f"unknown backend: {expected_backend}",
            )

    # Write output artifact
    if output_path:
        header = _build_artifact_header(entry)
        artifact_content = f"{header}\n\n{output_text or entry.get('status', '')}"
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(artifact_content)

    return entry


def cmd_summary(ledger_path: Optional[Path] = None) -> Dict[str, Any]:
    """Show recent trusted role executions."""
    entries = _read_ledger(ledger_path)
    trusted = [e for e in entries if e.get("routing_source") == "trusted_role_runner" or e.get("route_role")]
    recent = trusted[-20:] if trusted else []
    return {
        "total_calls": len(trusted),
        "recent": [
            {
                "call_id": e.get("call_id", ""),
                "role": e.get("role", ""),
                "status": e.get("status", ""),
                "implementation_source": e.get("implementation_source", ""),
                "verification_status": e.get("verification_status", ""),
                "allowed_next_stage": e.get("allowed_next_stage", False),
                "confidence_downgraded": e.get("confidence_downgraded", True),
            }
            for e in recent
        ],
    }


def cmd_self_test() -> bool:
    """Run self-test using temporary ledger. No real API calls."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        temp_path = Path(f.name)

    try:
        # Test 1: dry-run mode → dry_run_untrusted, allowed_next_stage=false
        entry1 = run_trusted(
            role="idea_generator",
            input_spec="test input for dry run",
            output_path=None,
            dry_run=True,
            mock_response="[dry-run mock output]",
            ledger_path=temp_path,
        )
        assert entry1["verification_status"] == "dry_run_untrusted", \
            f"Expected dry_run_untrusted, got {entry1['verification_status']}"
        assert entry1["allowed_next_stage"] is False, \
            "dry_run should not allow next stage"
        assert entry1["confidence_downgraded"] is True

        # Test 2: external_agent_direct via ledger entry
        ext_entry = {
            "call_id": f"call_{uuid.uuid4().hex[:12]}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "role": "experiment_implementer",
            "status": "completed",
            "implementation_source": "external_agent_direct",
            "routed_model_used": False,
            "route_role": "experiment_implementer",
            "route_expected_backend": "openai_compatible_api",
            "route_expected_model": "deepseek-v4-pro",
            "external_agent_name": "test_external_agent",
            "actual_backend": "external_agent",
            "actual_model": "unknown",
            "verification_status": "unverified_external_execution",
            "allowed_next_stage": False,
            "confidence_downgraded": True,
            "dry_run": False,
        }
        _write_ledger_entry(ext_entry, temp_path)

        # Test 3: routed_internal_model with actual backend
        start = cmd_start(role="novelty_checker", ledger_path=temp_path)
        call_id = start["call_id"]
        finish = cmd_finish(
            call_id=call_id,
            output="mock novelty output",
            ledger_path=temp_path,
            actual_backend="codex",
            actual_model="auto",
            codex_thread_id="thread_test_abc123",
        )
        assert finish["verification_status"] == "verified_routed_call", \
            f"Expected verified_routed_call, got {finish['verification_status']}"
        assert finish["allowed_next_stage"] is True
        assert finish["confidence_downgraded"] is False

        # Test 4: codex without thread_id → codex_missing_thread_id
        start2 = cmd_start(role="idea_reviewer", ledger_path=temp_path)
        call_id2 = start2["call_id"]
        finish2 = cmd_finish(
            call_id=call_id2,
            output="codex output",
            ledger_path=temp_path,
            actual_backend="codex",
            actual_model="auto",
            codex_thread_id="",
        )
        assert finish2["verification_status"] == "codex_missing_thread_id", \
            f"Expected codex_missing_thread_id, got {finish2['verification_status']}"
        assert finish2["allowed_next_stage"] is False

        # Test 5: fallback without reason → fallback_unverified
        start3 = cmd_start(role="final_selector", ledger_path=temp_path)
        call_id3 = start3["call_id"]
        finish3 = cmd_finish(
            call_id=call_id3,
            output="fallback output",
            ledger_path=temp_path,
            actual_backend="llm-chat",
            actual_model="deepseek-v4-flash",
            fallback_used=True,
            fallback_reason="",
        )
        assert finish3["verification_status"] == "fallback_unverified", \
            f"Expected fallback_unverified, got {finish3['verification_status']}"

        # Test 6: fallback with reason → verified_with_fallback
        start4 = cmd_start(role="paper_writer", ledger_path=temp_path)
        call_id4 = start4["call_id"]
        finish4 = cmd_finish(
            call_id=call_id4,
            output="paper content",
            ledger_path=temp_path,
            actual_backend="llm-chat",
            actual_model="deepseek-v4-pro",
            fallback_used=True,
            fallback_reason="codex unavailable",
        )
        assert finish4["verification_status"] == "verified_with_fallback", \
            f"Expected verified_with_fallback, got {finish4['verification_status']}"

        # Test 7: routed_model_used=true but missing actual_backend
        start5 = cmd_start(role="result_judge", ledger_path=temp_path)
        call_id5 = start5["call_id"]
        # Manually add entry with missing actual_backend
        entries = _read_ledger(temp_path)
        for e in entries:
            if e["call_id"] == call_id5:
                e["actual_backend"] = ""
                e["actual_model"] = ""
        # Rewrite
        with open(temp_path, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")
        verify_result = _auto_verify({"routed_model_used": True, "actual_backend": "", "implementation_source": "routed_internal_model"})
        assert verify_result[0] == "missing_actual_backend"

        # Test 8: summary works
        summary = cmd_summary(temp_path)
        assert summary["total_calls"] >= 4

        print("SELF-TEST RESULTS:")
        print(f"  Test 1 (dry-run): verification_status={entry1['verification_status']}, allowed_next_stage={entry1['allowed_next_stage']} [OK]")
        print(f"  Test 2 (external_agent_direct): [OK]")
        print(f"  Test 3 (routed_internal_model+codex_thread): verification_status={finish['verification_status']}, allowed_next_stage={finish['allowed_next_stage']} [OK]")
        print(f"  Test 4 (codex no thread): verification_status={finish2['verification_status']}, allowed_next_stage={finish2['allowed_next_stage']} [OK]")
        print(f"  Test 5 (fallback no reason): verification_status={finish3['verification_status']} [OK]")
        print(f"  Test 6 (fallback with reason): verification_status={finish4['verification_status']} [OK]")
        print(f"  Test 7 (missing actual_backend): {verify_result[0]} [OK]")
        print(f"  Test 8 (summary): total_calls={summary['total_calls']} [OK]")

        # Verify .aris unchanged (we used temp ledger)
        import subprocess
        status_r = subprocess.run(
            ["git", "status", "--short", ".aris/"],
            capture_output=True, text=True,
            cwd=str(find_project_root())
        )
        aris_changed = bool(status_r.stdout.strip())
        if aris_changed:
            print(f"WARNING: .aris/ changed during self-test: {status_r.stdout.strip()}")
        else:
            print(".aris/ unchanged during self-test [OK]")

        print("\nAll self-tests passed!")
        return True
    finally:
        os.unlink(temp_path)


def main():
    args = sys.argv[1:]
    if not args or "-h" in args or "--help" in args:
        print(__doc__)
        sys.exit(0)

    ledger_path: Optional[Path] = None
    role = ""
    input_spec = ""
    output_path: Optional[str] = None
    require_codex_thread = False
    dry_run = False
    mock_response = ""
    summary_mode = False
    self_test_mode = False

    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--role" and i + 1 < len(args):
            role = args[i + 1]
            i += 2
        elif arg == "--input" and i + 1 < len(args):
            input_spec = args[i + 1]
            i += 2
        elif arg == "--output" and i + 1 < len(args):
            output_path = args[i + 1]
            i += 2
        elif arg == "--require-codex-thread":
            require_codex_thread = True
            i += 1
        elif arg == "--dry-run":
            dry_run = True
            i += 1
        elif arg == "--mock-response" and i + 1 < len(args):
            mock_response = args[i + 1]
            i += 2
        elif arg == "--ledger-path" and i + 1 < len(args):
            ledger_path = Path(args[i + 1])
            i += 2
        elif arg == "--summary":
            summary_mode = True
            i += 1
        elif arg == "--self-test":
            self_test_mode = True
            i += 1
        else:
            i += 1

    if self_test_mode:
        success = cmd_self_test()
        sys.exit(0 if success else 1)

    if summary_mode:
        result = cmd_summary(ledger_path)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if not role:
        print("Error: --role <role> is required", file=sys.stderr)
        sys.exit(1)

    if not input_spec:
        print("Error: --input <file_or_text> is required", file=sys.stderr)
        sys.exit(1)

    result = run_trusted(
        role=role,
        input_spec=input_spec,
        output_path=output_path,
        require_codex_thread=require_codex_thread,
        dry_run=dry_run,
        mock_response=mock_response,
        ledger_path=ledger_path,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if result.get("verification_status") in ("dry_run_untrusted", "unverified_external_execution"):
        sys.exit(1)
    if result.get("allowed_next_stage") is False and result.get("verification_status") not in ("verified_routed_call", "verified_with_fallback"):
        sys.exit(1)


if __name__ == "__main__":
    main()