#!/usr/bin/env python3
"""
ARIS Trusted Role Runner - Single trusted entry point for ROLE_* execution.

Rules:
- model_route.py declares routing only; it does not call any backend.
- Real ROLE_* trust requires a backend call through tools/model_backends/ or a
  verified external Codex MCP handoff completed by the outer Agent.
- Codex trust requires a real codex_thread_id from backend metadata or external
  MCP session metadata.
- Dry-run/mock are self-test helpers only and can never enter the next stage.
- If the runner cannot verify the backend call, it fails closed.
"""

from __future__ import annotations

import json
import os
import hashlib
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


def _get_calls_dir(ledger_path: Optional[Path] = None) -> Path:
    path = ledger_path or _get_ledger_path()
    calls_dir = path.parent
    calls_dir.mkdir(parents=True, exist_ok=True)
    return calls_dir


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


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _header_value(value: Any) -> str:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    return str(value)


def _load_context_manifest(context_manifest_path: Optional[str]) -> Dict[str, Any]:
    if not context_manifest_path:
        return {
            "isolation_mode": "not_declared",
            "task_id": "",
            "context_manifest": "none",
            "allowed_input_files": [],
            "forbidden_context": [],
            "forbidden_context_checked": False,
            "source_boundary": "role_input_only",
            "contamination_scan_status": "not_checked",
        }

    manifest_path = Path(context_manifest_path)
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"context manifest not found: {manifest_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"context manifest is not valid JSON: {manifest_path}") from exc

    allowed_input_files = raw.get("allowed_input_files", [])
    forbidden_context = raw.get("forbidden_context", [])
    if isinstance(allowed_input_files, str):
        allowed_input_files = [allowed_input_files]
    if isinstance(forbidden_context, str):
        forbidden_context = [forbidden_context]

    return {
        "isolation_mode": str(raw.get("isolation_mode", "context_manifest")),
        "task_id": str(raw.get("task_id", "")),
        "context_manifest": str(manifest_path),
        "allowed_input_files": [str(item) for item in allowed_input_files],
        "forbidden_context": [str(item) for item in forbidden_context],
        "forbidden_context_checked": bool(raw.get("forbidden_context_checked", True)),
        "source_boundary": str(raw.get("source_boundary", "manifest_declared")),
        "contamination_scan_status": str(raw.get("contamination_scan_status", "declared_only")),
    }


def _attach_context_fields(
    entry: Dict[str, Any],
    *,
    context_manifest_path: Optional[str],
    context_hash_source: str,
) -> None:
    context_info = _load_context_manifest(context_manifest_path)
    entry.update(context_info)
    entry["context_hash"] = _sha256_text(context_hash_source)


def _find_latest_call(call_id: str, ledger_path: Optional[Path]) -> Optional[Dict[str, Any]]:
    for entry in reversed(_read_ledger(ledger_path)):
        if entry.get("call_id") == call_id:
            return dict(entry)
    return None


def _extract_error_code(error: str) -> str:
    if error in (
        "unsupported_runtime_backend",
        "codex_missing_thread_id",
        "pending_external_mcp",
        "call_failed",
    ):
        return error
    if error in ("config_missing", "api_call_failed"):
        return "call_failed"
    return "call_failed"


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
        "prompt_file": "",
        "response_file": "",
        "output_path": "",
        "response_file_required": False,
        "isolation_mode": "not_declared",
        "task_id": "",
        "context_manifest": "none",
        "allowed_input_files": [],
        "forbidden_context": [],
        "forbidden_context_checked": False,
        "context_hash": "",
        "source_boundary": "role_input_only",
        "contamination_scan_status": "not_checked",
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

    if status == "pending_external_mcp":
        return ("pending_external_mcp", False, True)

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
    routing_source: Optional[str] = None,
    response_file: Optional[str] = None,
    prompt_file: Optional[str] = None,
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
    if routing_source:
        finished["routing_source"] = routing_source
    if response_file is not None:
        finished["response_file"] = response_file
    if prompt_file is not None:
        finished["prompt_file"] = prompt_file

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
        f"routing_source: {entry.get('routing_source', '')}",
        f"isolation_mode: {_header_value(entry.get('isolation_mode', 'not_declared'))}",
        f"task_id: {_header_value(entry.get('task_id', ''))}",
        f"context_manifest: {_header_value(entry.get('context_manifest', 'none'))}",
        f"allowed_input_files: {_header_value(entry.get('allowed_input_files', []))}",
        f"forbidden_context: {_header_value(entry.get('forbidden_context', []))}",
        f"forbidden_context_checked: {_header_value(entry.get('forbidden_context_checked', False))}",
        f"context_hash: {_header_value(entry.get('context_hash', ''))}",
        f"prompt_file: {entry.get('prompt_file', '')}",
        f"response_file: {entry.get('response_file', '')}",
        f"source_boundary: {_header_value(entry.get('source_boundary', 'role_input_only'))}",
        f"contamination_scan_status: {_header_value(entry.get('contamination_scan_status', 'not_checked'))}",
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


def _build_codex_prompt(
    role: str,
    input_text: str,
    route_config: Dict[str, Any],
    call_id: str,
    context_info: Dict[str, Any],
    *,
    context_hash: str,
) -> str:
    return "\n".join(
        [
            f"# ARIS Trusted Role Task: {role}",
            "",
            f"- call_id: {call_id}",
            f"- expected_backend: codex",
            f"- expected_model: {route_config.get('model', 'auto') or 'auto'}",
            "- source: trusted_role_runner external MCP handoff",
            "- requirement: return the role output only; thread metadata is recorded separately by the outer Agent.",
            f"- context_manifest: {context_info.get('context_manifest', 'none')}",
            f"- context_hash: {context_hash}",
            f"- task_id: {context_info.get('task_id', '')}",
            f"- source_boundary: {context_info.get('source_boundary', 'role_input_only')}",
            f"- allowed_input_files: {_header_value(context_info.get('allowed_input_files', []))}",
            f"- forbidden_context: {_header_value(context_info.get('forbidden_context', []))}",
            "",
            "## Input",
            input_text,
        ]
    )


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


def _prepare_external_mcp(
    *,
    role: str,
    input_spec: str,
    output_path: Optional[str],
    ledger_path: Optional[Path],
    require_codex_thread: bool,
    context_manifest_path: Optional[str] = None,
    resolved_override: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    resolved = resolved_override or _resolve_role(role)
    route_config = dict(resolved.get("route_config", {}))
    expected_backend = resolved.get("expected_backend", "")
    if expected_backend != "mcp":
        return {
            "status": "failed",
            "verification_status": "call_failed",
            "allowed_next_stage": False,
            "confidence_downgraded": True,
            "error": (
                f"role '{role}' resolves to backend '{expected_backend or 'unknown'}'; "
                "prepare-external-mcp is only valid for Codex/MCP routes and API roles should run via openai_compatible."
            ),
            "error_code": "call_failed",
            "exit_code": 1,
        }

    input_text = _load_input_spec(input_spec)
    entry = _build_started_entry(role, resolved)
    entry["status"] = "pending_external_mcp"
    entry["verification_status"] = "pending_external_mcp"
    entry["allowed_next_stage"] = False
    entry["confidence_downgraded"] = True
    entry["routing_source"] = "trusted_role_runner_external_mcp_prepare"
    entry["output_path"] = output_path or ""
    entry["response_file_required"] = True
    if require_codex_thread:
        entry["route_requires_codex_thread"] = True
    try:
        context_info = _load_context_manifest(context_manifest_path)
    except ValueError as exc:
        return {
            "status": "failed",
            "verification_status": "call_failed",
            "allowed_next_stage": False,
            "confidence_downgraded": True,
            "error": str(exc),
            "error_code": "call_failed",
            "exit_code": 1,
        }

    prompt_file = _get_calls_dir(ledger_path) / f"{entry['call_id']}_prompt.md"
    prompt_text_without_hash = _build_codex_prompt(
        role,
        input_text,
        route_config,
        entry["call_id"],
        context_info,
        context_hash="pending",
    )
    context_hash = _sha256_text(prompt_text_without_hash)
    prompt_text = _build_codex_prompt(
        role,
        input_text,
        route_config,
        entry["call_id"],
        context_info,
        context_hash=context_hash,
    )
    try:
        prompt_file.write_text(prompt_text, encoding="utf-8")
    except OSError as exc:
        return {
            "status": "failed",
            "verification_status": "call_failed",
            "allowed_next_stage": False,
            "confidence_downgraded": True,
            "error": f"failed to write prompt_file: {exc}",
            "error_code": "call_failed",
            "exit_code": 1,
        }
    entry.update(context_info)
    entry["context_hash"] = context_hash
    entry["prompt_file"] = str(prompt_file)
    entry["raw_metadata"] = {
        "prepare_external_mcp": True,
        "prompt_file": str(prompt_file),
        "output_path": output_path or "",
        "context_hash": context_hash,
    }
    _write_ledger_entry(entry, ledger_path)

    finish_command = (
        f'python tools/trusted_role_runner.py --complete-external-mcp --call-id {entry["call_id"]} '
        f'--codex-thread-id <REAL_CODEX_THREAD_ID> --response-file <CODEX_RESPONSE_FILE> '
        f'--output "{output_path or ""}"'
    ).strip()
    result = {
        "status": "NEEDS_EXTERNAL_MCP_CALL",
        "call_id": entry["call_id"],
        "role": role,
        "prompt_file": str(prompt_file),
        "expected_backend": expected_backend,
        "expected_model": resolved.get("expected_model", ""),
        "output_path": output_path or "",
        "verification_status": "pending_external_mcp",
        "allowed_next_stage": False,
        "context_manifest": entry.get("context_manifest", "none"),
        "context_hash": context_hash,
        "finish_command": finish_command,
        "exit_code": 0,
    }
    return result


def _complete_external_mcp(
    *,
    call_id: str,
    codex_thread_id: str,
    response_file: str,
    output_path: Optional[str],
    ledger_path: Optional[Path],
) -> Dict[str, Any]:
    entry = _find_latest_call(call_id, ledger_path)
    if not entry:
        return {
            "status": "failed",
            "verification_status": "call_failed",
            "allowed_next_stage": False,
            "confidence_downgraded": True,
            "error": f"call_id not found: {call_id}",
            "error_code": "call_failed",
            "exit_code": 1,
        }

    if entry.get("status") != "pending_external_mcp" or entry.get("verification_status") != "pending_external_mcp":
        return {
            "status": "failed",
            "verification_status": "call_failed",
            "allowed_next_stage": False,
            "confidence_downgraded": True,
            "error": f"call_id {call_id} is not pending_external_mcp",
            "error_code": "call_failed",
            "exit_code": 1,
        }

    if entry.get("route_expected_backend") != "mcp":
        return {
            "status": "failed",
            "verification_status": "call_failed",
            "allowed_next_stage": False,
            "confidence_downgraded": True,
            "error": f"call_id {call_id} does not resolve to Codex/MCP",
            "error_code": "call_failed",
            "exit_code": 1,
        }

    if not codex_thread_id.strip():
        finished = _finalize_entry(
            entry,
            ledger_path=ledger_path,
            status="failed",
            output_text="",
            actual_backend="codex",
            actual_model=str(entry.get("route_expected_model", "") or "auto"),
            error="codex_missing_thread_id",
            error_code="codex_missing_thread_id",
            routing_source="trusted_role_runner_external_mcp",
        )
        finished["exit_code"] = 1
        return finished

    response_path = Path(response_file)
    if not response_path.exists() or not response_path.is_file():
        finished = _finalize_entry(
            entry,
            ledger_path=ledger_path,
            status="failed",
            output_text="",
            actual_backend="codex",
            actual_model=str(entry.get("route_expected_model", "") or "auto"),
            codex_thread_id=codex_thread_id.strip(),
            error="response_file_missing",
            error_code="call_failed",
            raw_metadata={"response_file": response_file},
            routing_source="trusted_role_runner_external_mcp",
            response_file=response_file,
        )
        finished["exit_code"] = 1
        return finished

    response_text = response_path.read_text(encoding="utf-8", errors="ignore").strip()
    if not response_text:
        finished = _finalize_entry(
            entry,
            ledger_path=ledger_path,
            status="failed",
            output_text="",
            actual_backend="codex",
            actual_model=str(entry.get("route_expected_model", "") or "auto"),
            codex_thread_id=codex_thread_id.strip(),
            error="response_file_empty",
            error_code="call_failed",
            raw_metadata={"response_file": response_file},
            routing_source="trusted_role_runner_external_mcp",
            response_file=response_file,
        )
        finished["exit_code"] = 1
        return finished

    final_output_path = output_path or str(entry.get("output_path", "") or "")
    finished = _finalize_entry(
        entry,
        ledger_path=ledger_path,
        status="completed",
        output_text=response_text,
        actual_backend="codex",
        actual_model=str(entry.get("route_expected_model", "") or "auto"),
        codex_thread_id=codex_thread_id.strip(),
        raw_metadata={
            "external_mcp_handoff": True,
            "response_file": response_file,
        },
        routing_source="trusted_role_runner_external_mcp",
        response_file=response_file,
    )
    _write_artifact(final_output_path, finished, response_text)
    finished["output_path"] = final_output_path
    finished["exit_code"] = 0 if finished.get("allowed_next_stage") else 1
    return finished


def run_trusted(
    role: str,
    input_spec: str,
    output_path: Optional[str] = None,
    require_codex_thread: bool = False,
    context_manifest_path: Optional[str] = None,
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
    entry["output_path"] = output_path or ""
    if require_codex_thread:
        entry["route_requires_codex_thread"] = True
    try:
        _attach_context_fields(
            entry,
            context_manifest_path=context_manifest_path,
            context_hash_source=input_text,
        )
    except ValueError as exc:
        error_result = _finalize_entry(
            entry,
            ledger_path=ledger_path,
            status="failed",
            output_text="",
            error=str(exc),
            error_code="call_failed",
        )
        _write_artifact(output_path, error_result, json.dumps({"error": str(exc)}, ensure_ascii=False))
        error_result["exit_code"] = 1
        return error_result
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
            if primary_result.error in ("call_failed", "api_call_failed", "config_missing")
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

    error_code = _extract_error_code(primary_result.error or "call_failed")
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
        response_path = Path(tmp_dir) / "codex_response.md"
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

            prepare_codex = _prepare_external_mcp(
                role="novelty_checker",
                input_spec="codex prepare input",
                output_path=artifact_path,
                ledger_path=ledger_path,
                require_codex_thread=True,
                context_manifest_path=None,
                resolved_override={
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
            assert prepare_codex["status"] == "NEEDS_EXTERNAL_MCP_CALL"
            assert prepare_codex["verification_status"] == "pending_external_mcp"
            assert prepare_codex["allowed_next_stage"] is False
            assert prepare_codex["exit_code"] == 0
            assert Path(prepare_codex["prompt_file"]).exists()
            assert prepare_codex["context_manifest"] == "none"
            assert prepare_codex["context_hash"]

            missing_thread = _complete_external_mcp(
                call_id=prepare_codex["call_id"],
                codex_thread_id="",
                response_file=str(response_path),
                output_path=artifact_path,
                ledger_path=ledger_path,
            )
            assert missing_thread["verification_status"] == "codex_missing_thread_id"
            assert missing_thread["exit_code"] == 1

            prepare_missing_response = _prepare_external_mcp(
                role="novelty_checker",
                input_spec="codex prepare missing response",
                output_path=artifact_path,
                ledger_path=ledger_path,
                require_codex_thread=True,
                context_manifest_path=None,
                resolved_override={
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
            missing_response = _complete_external_mcp(
                call_id=prepare_missing_response["call_id"],
                codex_thread_id="fixture-thread-missing-response",
                response_file=str(response_path),
                output_path=artifact_path,
                ledger_path=ledger_path,
            )
            assert missing_response["verification_status"] == "call_failed"
            assert missing_response["exit_code"] == 1

            response_path.write_text("fixture codex response", encoding="utf-8")
            prepare_complete = _prepare_external_mcp(
                role="novelty_checker",
                input_spec="codex prepare complete",
                output_path=artifact_path,
                ledger_path=ledger_path,
                require_codex_thread=True,
                context_manifest_path=None,
                resolved_override={
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
            complete_success = _complete_external_mcp(
                call_id=prepare_complete["call_id"],
                codex_thread_id="fixture-thread-001",
                response_file=str(response_path),
                output_path=artifact_path,
                ledger_path=ledger_path,
            )
            assert complete_success["verification_status"] == "verified_routed_call"
            assert complete_success["allowed_next_stage"] is True
            assert complete_success["exit_code"] == 0
            artifact_text = Path(artifact_path).read_text(encoding="utf-8")
            assert "routing_source: trusted_role_runner_external_mcp" in artifact_text
            assert "response_file:" in artifact_text
            assert "context_manifest: none" in artifact_text
            assert "context_hash:" in artifact_text
            assert "forbidden_context_checked: false" in artifact_text

            non_codex_prepare = _prepare_external_mcp(
                role="paper_writer",
                input_spec="api prepare denied",
                output_path=artifact_path,
                ledger_path=ledger_path,
                require_codex_thread=False,
                context_manifest_path=None,
                resolved_override={
                    "expected_backend": "openai_compatible_api",
                    "expected_model": "deepseek-v4-pro",
                    "expected_provider": "deepseek",
                    "route_config": {
                        "backend_type": "openai_compatible_api",
                        "provider": "deepseek",
                        "model": "deepseek-v4-pro",
                        "api_key_env": "DEEPSEEK_API_KEY",
                        "base_url": "https://api.deepseek.com",
                    },
                },
            )
            assert non_codex_prepare["verification_status"] == "call_failed"
            assert non_codex_prepare["exit_code"] == 1

            api_success = run_trusted(
                role="novelty_checker",
                input_spec="api success fixture",
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
                        "base_url": "https://api.deepseek.com",
                    },
                },
                _forced_primary_result=BackendResult(
                    ok=True,
                    actual_backend="deepseek",
                    actual_model="deepseek-v4-pro",
                    output_text="api success",
                    raw_metadata={"self_test": True},
                ),
            )
            assert api_success["verification_status"] == "verified_routed_call"
            assert api_success["allowed_next_stage"] is True
            assert api_success["exit_code"] == 0

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

            import model_route as mr

            code_route = mr.resolve_role("novelty_checker")
            api_route = mr.resolve_role("idea_generator")
            assert code_route.get("backend_type") == "mcp"
            assert api_route.get("backend_type") == "openai_compatible_api"

            summary = cmd_summary(ledger_path)
            assert summary["total_calls"] >= 8

            print("SELF-TEST RESULTS:")
            print(f"  prepare external MCP: verification_status={prepare_codex['verification_status']} exit={prepare_codex['exit_code']} [OK]")
            print(f"  complete missing thread: verification_status={missing_thread['verification_status']} exit={missing_thread['exit_code']} [OK]")
            print(f"  complete missing response: verification_status={missing_response['verification_status']} exit={missing_response['exit_code']} [OK]")
            print(f"  complete fixture success: verification_status={complete_success['verification_status']} exit={complete_success['exit_code']} [OK]")
            print(f"  non-codex prepare denied: verification_status={non_codex_prepare['verification_status']} exit={non_codex_prepare['exit_code']} [OK]")
            print(f"  API direct success: verification_status={api_success['verification_status']} exit={api_success['exit_code']} [OK]")
            print(f"  API config missing: verification_status={config_missing_result['verification_status']} exit={config_missing_result['exit_code']} [OK]")
            print(f"  direct Codex unsupported without handoff: verification_status={unsupported_result['verification_status']} exit={unsupported_result['exit_code']} [OK]")
            print(f"  fallback blocked by default: allowed_next_stage={fallback_blocked['allowed_next_stage']} exit={fallback_blocked['exit_code']} [OK]")
            print(f"  fallback allowed only with flag: allowed_next_stage={fallback_allowed['allowed_next_stage']} exit={fallback_allowed['exit_code']} [OK]")
            print(f"  route switch check: novelty_checker={code_route.get('backend_type')} idea_generator={api_route.get('backend_type')} [OK]")
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
    prepare_external_mcp = False
    complete_external_mcp = False
    call_id = ""
    codex_thread_id = ""
    response_file = ""
    context_manifest_path: Optional[str] = None

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
        elif arg == "--prepare-external-mcp":
            prepare_external_mcp = True
            i += 1
        elif arg == "--complete-external-mcp":
            complete_external_mcp = True
            i += 1
        elif arg == "--call-id" and i + 1 < len(args):
            call_id = args[i + 1]
            i += 2
        elif arg == "--codex-thread-id" and i + 1 < len(args):
            codex_thread_id = args[i + 1]
            i += 2
        elif arg == "--response-file" and i + 1 < len(args):
            response_file = args[i + 1]
            i += 2
        elif arg == "--context-manifest" and i + 1 < len(args):
            context_manifest_path = args[i + 1]
            i += 2
        else:
            i += 1

    if self_test_mode:
        sys.exit(0 if cmd_self_test() else 1)

    if summary_mode:
        print(json.dumps(cmd_summary(ledger_path), ensure_ascii=False, indent=2))
        return

    if prepare_external_mcp and complete_external_mcp:
        print("Error: choose only one of --prepare-external-mcp or --complete-external-mcp", file=sys.stderr)
        sys.exit(1)

    if prepare_external_mcp:
        if not role:
            print("Error: --role <role> is required for --prepare-external-mcp", file=sys.stderr)
            sys.exit(1)
        if not input_spec:
            print("Error: --input <file_or_text> is required for --prepare-external-mcp", file=sys.stderr)
            sys.exit(1)
        result = _prepare_external_mcp(
            role=role,
            input_spec=input_spec,
            output_path=output_path,
            ledger_path=ledger_path,
            require_codex_thread=require_codex_thread,
            context_manifest_path=context_manifest_path,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(int(result.get("exit_code", 1)))

    if complete_external_mcp:
        if not call_id:
            print("Error: --call-id is required for --complete-external-mcp", file=sys.stderr)
            sys.exit(1)
        result = _complete_external_mcp(
            call_id=call_id,
            codex_thread_id=codex_thread_id,
            response_file=response_file,
            output_path=output_path,
            ledger_path=ledger_path,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(int(result.get("exit_code", 1)))

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
        context_manifest_path=context_manifest_path,
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
