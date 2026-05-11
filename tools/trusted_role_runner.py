#!/usr/bin/env python3
"""
ARIS Trusted Role Runner - Single trusted entry point for ROLE_* execution.

Rules:
- model_route.py declares routing only; it does not call any backend.
- Real ROLE_* trust requires a backend call through tools/model_backends/.
- Codex trust requires a real codex_thread_id from backend metadata.
- Dry-run/mock are self-test helpers only and can never enter the next stage.
- If the runner cannot verify the backend call, it fails closed.
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
from model_backends import BackendResult, call_codex_mcp, call_openai_compatible


def _get_ledger_path() -> Path:
    env_path = os.environ.get("ARIS_LEDGER_PATH", "")
    if env_path:
        return Path(env_path)
    root = find_project_root()
    return root / ".aris" / "calls" / "llm_calls.jsonl"


def _read_ledger(ledger_path: Optional[Path] = None) -> list[Dict[str, Any]]:
    path = ledger_path or _get_ledger_path()
    if not path.exists():
        return []
    calls: list[Dict[str, Any]] = []
    try:
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
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
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _resolve_role(role: str) -> Dict[str, Any]:
    try:
        import model_route as mr

        route_config = mr.resolve_role(role)
        return {
            "expected_backend": route_config.get("backend_type", "") or route_config.get("primary_backend", ""),
            "expected_model": route_config.get("model", "") or route_config.get("primary_model", ""),
            "expected_provider": route_config.get("provider", ""),
            "route_config": route_config,
        }
    except Exception as exc:
        return {
            "expected_backend": "",
            "expected_model": "",
            "expected_provider": "",
            "route_config": {},
            "error": str(exc),
        }


def _load_input_spec(input_spec: str) -> str:
    candidate = Path(input_spec)
    if candidate.exists() and candidate.is_file():
        return candidate.read_text(encoding="utf-8", errors="ignore")
    return input_spec


def _build_started_entry(role: str, resolved: Dict[str, Any]) -> Dict[str, Any]:
    call_id = f"call_{uuid.uuid4().hex[:12]}"
    return {
        "call_id": call_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "role": role,
        "status": "started",
        "implementation_source": "routed_internal_model",
        "routed_model_used": True,
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
        "routing_source": "trusted_role_runner",
        "global_codex_gate_mode": "",
        "dry_run": False,
        "error": None,
        "error_code": None,
        "raw_metadata": {},
        "allow_fallback_next_stage": False,
    }


def _auto_verify(entry: Dict[str, Any]) -> tuple[str, bool, bool]:
    impl_source = entry.get("implementation_source", "external_agent_direct")
    routed_used = entry.get("routed_model_used", False)
    actual_backend = str(entry.get("actual_backend", "") or "")
    actual_model = str(entry.get("actual_model", "") or "")
    codex_thread_id = str(entry.get("codex_thread_id", "") or "")
    fallback_used = bool(entry.get("fallback_used", False))
    fallback_reason = str(entry.get("fallback_reason", "") or "")
    dry_run = bool(entry.get("dry_run", False))
    status = str(entry.get("status", "") or "")
    error_code = str(entry.get("error_code", "") or "")

    if dry_run:
        return ("dry_run_untrusted", False, True)

    if status == "failed":
        if error_code == "unsupported_runtime_backend":
            return ("unsupported_runtime_backend", False, True)
        if error_code == "codex_missing_thread_id":
            return ("codex_missing_thread_id", False, True)
        return ("call_failed", False, True)

    if impl_source == "external_agent_direct":
        return ("unverified_external_execution", False, True)

    if routed_used and not actual_backend:
        return ("missing_actual_backend", False, True)

    if actual_backend == "codex":
        if not codex_thread_id or codex_thread_id.strip().lower() == "none":
            return ("codex_missing_thread_id", False, True)

    if fallback_used:
        if actual_backend and actual_model and fallback_reason:
            allowed = bool(entry.get("allow_fallback_next_stage", False))
            return ("verified_with_fallback", allowed, True)
        return ("fallback_unverified", False, True)

    if impl_source == "routed_internal_model" and actual_backend and actual_model:
        return ("verified_routed_call", True, False)

    return ("started_unverified", False, True)


def _finalize_entry(
    entry: Dict[str, Any],
    *,
    ledger_path: Optional[Path],
    status: str,
    output_text: str,
    actual_backend: str = "",
    actual_model: str = "",
    codex_thread_id: str = "",
    fallback_used: bool = False,
    fallback_reason: str = "",
    dry_run: bool = False,
    error: Optional[str] = None,
    error_code: Optional[str] = None,
    raw_metadata: Optional[Dict[str, Any]] = None,
    allow_fallback_next_stage: bool = False,
) -> Dict[str, Any]:
    finished = dict(entry)
    finished["status"] = status
    finished["completed_at"] = datetime.now(timezone.utc).isoformat()
    finished["actual_backend"] = actual_backend
    finished["actual_model"] = actual_model
    finished["codex_thread_id"] = codex_thread_id
    finished["fallback_used"] = fallback_used
    finished["fallback_reason"] = fallback_reason
    finished["dry_run"] = dry_run
    finished["error"] = error
    finished["error_code"] = error_code
    finished["raw_metadata"] = raw_metadata or {}
    finished["allow_fallback_next_stage"] = allow_fallback_next_stage

    verification_status, allowed_next_stage, confidence_downgraded = _auto_verify(finished)
    finished["verification_status"] = verification_status
    finished["allowed_next_stage"] = allowed_next_stage
    finished["confidence_downgraded"] = confidence_downgraded
    finished["output_text"] = output_text

    _write_ledger_entry(finished, ledger_path)
    return finished


def _build_artifact_header(entry: Dict[str, Any]) -> str:
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
        f"status: {entry.get('status', '')}",
        f"error_code: {entry.get('error_code', '') or ''}",
        f"error: {entry.get('error', '') or ''}",
        "---",
    ]
    return "\n".join(lines)


def _write_artifact(output_path: Optional[str], entry: Dict[str, Any], body: str) -> None:
    if not output_path:
        return
    header = _build_artifact_header(entry)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(f"{header}\n\n{body}".rstrip() + "\n")


def _call_backend(route_config: Dict[str, Any], prompt: str) -> BackendResult:
    backend_type = str(route_config.get("backend_type", "") or route_config.get("primary_backend", ""))
    if backend_type == "mcp":
        return call_codex_mcp(route_config, prompt)
    if backend_type in ("openai_compatible_api", "llm-chat"):
        return call_openai_compatible(route_config, prompt)
    return BackendResult(
        ok=False,
        actual_backend=str(route_config.get("provider", "") or ""),
        actual_model=str(route_config.get("model", "") or ""),
        output_text="",
        error="call_failed",
        raw_metadata={"reason": f"unknown backend_type {backend_type}"},
    )


def _resolve_explicit_fallback_route(route_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    fallback = route_config.get("fallback_route_config")
    if isinstance(fallback, dict) and fallback:
        return fallback
    return None


def run_trusted(
    role: str,
    input_spec: str,
    output_path: Optional[str] = None,
    require_codex_thread: bool = False,
    dry_run: bool = False,
    mock_response: str = "",
    ledger_path: Optional[Path] = None,
    allow_fallback_next_stage: bool = False,
    *,
    _resolved_override: Optional[Dict[str, Any]] = None,
    _forced_primary_result: Optional[BackendResult] = None,
    _forced_fallback_result: Optional[BackendResult] = None,
    _fallback_route_override: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    resolved = _resolved_override or _resolve_role(role)
    route_config = dict(resolved.get("route_config", {}))
    input_text = _load_input_spec(input_spec)

    entry = _build_started_entry(role, resolved)
    entry["route_expected_backend"] = resolved.get("expected_backend", "")
    entry["route_expected_model"] = resolved.get("expected_model", "")
    if require_codex_thread:
        entry["route_requires_codex_thread"] = True
    _write_ledger_entry(entry, ledger_path)

    if dry_run:
        finished = _finalize_entry(
            entry,
            ledger_path=ledger_path,
            status="completed_dry_run",
            output_text=mock_response or f"[DRY-RUN] {role} output for: {input_text[:200]}",
            actual_backend="dry_run",
            actual_model="dry_run",
            dry_run=True,
        )
        _write_artifact(output_path, finished, finished["output_text"])
        finished["exit_code"] = 1
        return finished

    primary_result = _forced_primary_result or _call_backend(route_config, input_text)
    if primary_result.ok:
        finished = _finalize_entry(
            entry,
            ledger_path=ledger_path,
            status="completed",
            output_text=primary_result.output_text,
            actual_backend=primary_result.actual_backend,
            actual_model=primary_result.actual_model,
            codex_thread_id=primary_result.codex_thread_id or "",
            raw_metadata=primary_result.raw_metadata,
        )
        _write_artifact(output_path, finished, primary_result.output_text)
        finished["exit_code"] = 0 if finished.get("allowed_next_stage") else 1
        return finished

    fallback_route = _fallback_route_override or _resolve_explicit_fallback_route(route_config)
    if fallback_route is not None:
        fallback_reason = (
            "primary backend failed"
            if primary_result.error in ("call_failed", "api_call_failed")
            else f"primary backend unavailable: {primary_result.error or 'unknown'}"
        )
        fallback_result = _forced_fallback_result or _call_backend(fallback_route, input_text)
        if fallback_result.ok:
            finished = _finalize_entry(
                entry,
                ledger_path=ledger_path,
                status="completed_with_fallback",
                output_text=fallback_result.output_text,
                actual_backend=fallback_result.actual_backend,
                actual_model=fallback_result.actual_model,
                codex_thread_id=fallback_result.codex_thread_id or "",
                fallback_used=True,
                fallback_reason=fallback_reason,
                raw_metadata={
                    "primary_failure": primary_result.raw_metadata,
                    "fallback_success": fallback_result.raw_metadata,
                },
                allow_fallback_next_stage=allow_fallback_next_stage,
            )
            _write_artifact(output_path, finished, fallback_result.output_text)
            finished["exit_code"] = 0 if finished.get("allowed_next_stage") else 1
            return finished

        primary_result = BackendResult(
            ok=False,
            actual_backend=primary_result.actual_backend or fallback_result.actual_backend,
            actual_model=primary_result.actual_model or fallback_result.actual_model,
            output_text="",
            error="call_failed",
            raw_metadata={
                "primary_failure": primary_result.raw_metadata,
                "fallback_failure": fallback_result.raw_metadata,
                "fallback_error": fallback_result.error,
            },
        )

    error_code = primary_result.error or "call_failed"
    if error_code == "config_missing":
        error_code = "call_failed"
    if error_code not in ("unsupported_runtime_backend", "codex_missing_thread_id", "call_failed"):
        error_code = "call_failed"

    error_body = json.dumps(primary_result.raw_metadata, ensure_ascii=False, indent=2)
    finished = _finalize_entry(
        entry,
        ledger_path=ledger_path,
        status="failed",
        output_text="",
        actual_backend=primary_result.actual_backend,
        actual_model=primary_result.actual_model,
        codex_thread_id=primary_result.codex_thread_id or "",
        error=primary_result.error or "call_failed",
        error_code=error_code,
        raw_metadata=primary_result.raw_metadata,
    )
    _write_artifact(output_path, finished, error_body)
    finished["exit_code"] = 1
    return finished


def cmd_summary(ledger_path: Optional[Path] = None) -> Dict[str, Any]:
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
                "verification_status": e.get("verification_status", ""),
                "allowed_next_stage": e.get("allowed_next_stage", False),
                "error_code": e.get("error_code"),
            }
            for e in recent
        ],
    }


def cmd_self_test() -> bool:
    before_status = None
    try:
        import subprocess

        before_status = subprocess.run(
            ["git", "status", "--short", ".aris/"],
            capture_output=True,
            text=True,
            cwd=str(find_project_root()),
            timeout=30,
        ).stdout.strip()
    except Exception:
        before_status = None

    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as handle:
        ledger_path = Path(handle.name).resolve()

    with tempfile.TemporaryDirectory() as tmp_dir:
        artifact_path = str(Path(tmp_dir) / "trusted_output.md")
        try:
            dry_run_result = run_trusted(
                role="idea_generator",
                input_spec="dry-run input",
                ledger_path=ledger_path,
                dry_run=True,
                mock_response="dry-run output",
            )
            assert dry_run_result["verification_status"] == "dry_run_untrusted"
            assert dry_run_result["allowed_next_stage"] is False
            assert dry_run_result["exit_code"] == 1

            unsupported_result = run_trusted(
                role="idea_reviewer",
                input_spec="codex task",
                ledger_path=ledger_path,
                _resolved_override={
                    "expected_backend": "mcp",
                    "expected_model": "auto",
                    "expected_provider": "codex",
                    "route_config": {
                        "backend_type": "mcp",
                        "provider": "codex",
                        "model": "auto",
                    },
                },
            )
            assert unsupported_result["verification_status"] == "unsupported_runtime_backend"
            assert unsupported_result["exit_code"] == 1

            config_missing_result = run_trusted(
                role="paper_writer",
                input_spec="api task",
                ledger_path=ledger_path,
                _resolved_override={
                    "expected_backend": "openai_compatible_api",
                    "expected_model": "deepseek-v4-pro",
                    "expected_provider": "deepseek",
                    "route_config": {
                        "backend_type": "openai_compatible_api",
                        "provider": "deepseek",
                        "model": "deepseek-v4-pro",
                        "api_key_env": "DEEPSEEK_API_KEY",
                        "base_url": "",
                    },
                },
            )
            assert config_missing_result["verification_status"] == "call_failed"
            assert config_missing_result["exit_code"] == 1

            codex_success = run_trusted(
                role="novelty_checker",
                input_spec="codex fixture",
                output_path=artifact_path,
                ledger_path=ledger_path,
                _resolved_override={
                    "expected_backend": "mcp",
                    "expected_model": "auto",
                    "expected_provider": "codex",
                    "route_config": {
                        "backend_type": "mcp",
                        "provider": "codex",
                        "model": "auto",
                    },
                },
                _forced_primary_result=BackendResult(
                    ok=True,
                    actual_backend="codex",
                    actual_model="auto",
                    output_text="codex success",
                    codex_thread_id="fixture-thread-001",
                    raw_metadata={"threadId": "fixture-thread-001"},
                ),
            )
            assert codex_success["verification_status"] == "verified_routed_call"
            assert codex_success["allowed_next_stage"] is True
            assert codex_success["exit_code"] == 0
            artifact_text = Path(artifact_path).read_text(encoding="utf-8")
            assert "ledger_call_id:" in artifact_text
            assert "verification_status: verified_routed_call" in artifact_text

            missing_thread = run_trusted(
                role="idea_reviewer",
                input_spec="codex missing thread",
                ledger_path=ledger_path,
                _resolved_override={
                    "expected_backend": "mcp",
                    "expected_model": "auto",
                    "expected_provider": "codex",
                    "route_config": {
                        "backend_type": "mcp",
                        "provider": "codex",
                        "model": "auto",
                    },
                },
                _forced_primary_result=BackendResult(
                    ok=False,
                    actual_backend="codex",
                    actual_model="auto",
                    output_text="",
                    codex_thread_id=None,
                    error="codex_missing_thread_id",
                    raw_metadata={"metadata": {"threadId": ""}},
                ),
            )
            assert missing_thread["verification_status"] == "codex_missing_thread_id"
            assert missing_thread["exit_code"] == 1

            fallback_blocked = run_trusted(
                role="final_selector",
                input_spec="fallback blocked",
                ledger_path=ledger_path,
                _resolved_override={
                    "expected_backend": "mcp",
                    "expected_model": "auto",
                    "expected_provider": "codex",
                    "route_config": {
                        "backend_type": "mcp",
                        "provider": "codex",
                        "model": "auto",
                    },
                },
                _forced_primary_result=BackendResult(
                    ok=False,
                    actual_backend="codex",
                    actual_model="auto",
                    output_text="",
                    error="unsupported_runtime_backend",
                    raw_metadata={"reason": "self-test unsupported runtime"},
                ),
                _fallback_route_override={
                    "backend_type": "openai_compatible_api",
                    "provider": "deepseek",
                    "model": "deepseek-v4-pro",
                    "api_key_env": "DEEPSEEK_API_KEY",
                    "base_url": "https://api.deepseek.com",
                },
                _forced_fallback_result=BackendResult(
                    ok=True,
                    actual_backend="deepseek",
                    actual_model="deepseek-v4-pro",
                    output_text="fallback success",
                    raw_metadata={"self_test": True},
                ),
            )
            assert fallback_blocked["verification_status"] == "verified_with_fallback"
            assert fallback_blocked["allowed_next_stage"] is False
            assert fallback_blocked["exit_code"] == 1

            fallback_allowed = run_trusted(
                role="final_selector",
                input_spec="fallback allowed",
                ledger_path=ledger_path,
                allow_fallback_next_stage=True,
                _resolved_override={
                    "expected_backend": "mcp",
                    "expected_model": "auto",
                    "expected_provider": "codex",
                    "route_config": {
                        "backend_type": "mcp",
                        "provider": "codex",
                        "model": "auto",
                    },
                },
                _forced_primary_result=BackendResult(
                    ok=False,
                    actual_backend="codex",
                    actual_model="auto",
                    output_text="",
                    error="unsupported_runtime_backend",
                    raw_metadata={"reason": "self-test unsupported runtime"},
                ),
                _fallback_route_override={
                    "backend_type": "openai_compatible_api",
                    "provider": "deepseek",
                    "model": "deepseek-v4-pro",
                    "api_key_env": "DEEPSEEK_API_KEY",
                    "base_url": "https://api.deepseek.com",
                },
                _forced_fallback_result=BackendResult(
                    ok=True,
                    actual_backend="deepseek",
                    actual_model="deepseek-v4-pro",
                    output_text="fallback success",
                    raw_metadata={"self_test": True},
                ),
            )
            assert fallback_allowed["verification_status"] == "verified_with_fallback"
            assert fallback_allowed["allowed_next_stage"] is True
            assert fallback_allowed["exit_code"] == 0

            summary = cmd_summary(ledger_path)
            assert summary["total_calls"] >= 6

            print("SELF-TEST RESULTS:")
            print(f"  dry-run: verification_status={dry_run_result['verification_status']} exit={dry_run_result['exit_code']} [OK]")
            print(f"  unsupported runtime: verification_status={unsupported_result['verification_status']} exit={unsupported_result['exit_code']} [OK]")
            print(f"  config missing: verification_status={config_missing_result['verification_status']} exit={config_missing_result['exit_code']} [OK]")
            print(f"  codex fixture success: verification_status={codex_success['verification_status']} exit={codex_success['exit_code']} [OK]")
            print(f"  codex missing thread: verification_status={missing_thread['verification_status']} exit={missing_thread['exit_code']} [OK]")
            print(f"  fallback blocked by default: allowed_next_stage={fallback_blocked['allowed_next_stage']} exit={fallback_blocked['exit_code']} [OK]")
            print(f"  fallback allowed only with flag: allowed_next_stage={fallback_allowed['allowed_next_stage']} exit={fallback_allowed['exit_code']} [OK]")
            print(f"  summary total_calls={summary['total_calls']} [OK]")

            try:
                import subprocess

                after_status = subprocess.run(
                    ["git", "status", "--short", ".aris/"],
                    capture_output=True,
                    text=True,
                    cwd=str(find_project_root()),
                    timeout=30,
                ).stdout.strip()
                if before_status == after_status:
                    print(".aris/ unchanged during self-test [OK]")
                else:
                    print(f"WARNING: .aris/ status changed during self-test: before={before_status!r} after={after_status!r}")
            except Exception as exc:
                print(f"WARNING: could not compare .aris/ git status: {exc}")

            print("\nAll self-tests passed!")
            return True
        finally:
            try:
                ledger_path.unlink()
            except FileNotFoundError:
                pass


def main() -> None:
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
    allow_fallback_next_stage = False

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
        elif arg == "--allow-fallback-next-stage":
            allow_fallback_next_stage = True
            i += 1
        else:
            i += 1

    if self_test_mode:
        sys.exit(0 if cmd_self_test() else 1)

    if summary_mode:
        print(json.dumps(cmd_summary(ledger_path), ensure_ascii=False, indent=2))
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
        allow_fallback_next_stage=allow_fallback_next_stage,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("allowed_next_stage") is False:
        sys.exit(1)
    if result.get("verification_status") == "verified_with_fallback" and not allow_fallback_next_stage:
        sys.exit(1)
    sys.exit(int(result.get("exit_code", 1)))


if __name__ == "__main__":
    main()
