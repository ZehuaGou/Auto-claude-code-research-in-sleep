#!/usr/bin/env python3
"""
ARIS Model Invocation Validator — Verify declared routes vs actual ledger calls.

Validates that:
1. A role's expected backend (from model_route.py) matches actual ledger calls.
2. implementation_source is correctly set (external_agent_direct vs routed_internal_model).
3. routed_model_used correctly reflects whether an internal model was actually called.
4. Codex calls have codex_thread_id.
5. Fallback calls are explicitly recorded.

Usage:
    python tools/validate_model_invocation.py --role experiment_implementer --max-age-hours 24
    python tools/validate_model_invocation.py --role experiment_code_reviewer --require-codex-thread
    python tools/validate_model_invocation.py --summary
    python tools/validate_model_invocation.py --self-test
    python tools/validate_model_invocation.py --ledger-path <path>
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

TOOLS_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(TOOLS_DIR))

from env_loader import find_project_root


# Roles to show in --summary (all ARIS ROLE_* roles)
SUMMARY_ROLES = [
    "literature_scout",
    "paper_summarizer",
    "gap_extractor",
    "idea_generator",
    "idea_deduplicator",
    "idea_reviewer",
    "novelty_checker",
    "adversarial_reviewer",
    "final_selector",
    "contract_reviewer",
    "baseline_reviewer",
    "experiment_implementer",
    "experiment_code_reviewer",
    "experiment_auditor",
    "result_judge",
    "paper_writer",
    "claims_drafter",
    "final_paper_auditor",
    "paper_claim_auditor",
    "evidence_integrity_auditor",
    "idea_shortlist_auditor",
    "log_summarizer",
]

CRITICAL_CONTEXT_ROLES = {
    "novelty_checker",
    "idea_reviewer",
    "adversarial_reviewer",
    "final_selector",
    "experiment_code_reviewer",
    "experiment_auditor",
    "result_judge",
    "final_paper_auditor",
    "paper_claim_auditor",
    "evidence_integrity_auditor",
    "idea_shortlist_auditor",
}

REQUIRED_CONTEXT_FIELDS = [
    "isolation_mode",
    "task_id",
    "context_manifest",
    "allowed_input_files",
    "forbidden_context",
    "forbidden_context_checked",
    "context_hash",
    "prompt_file",
    "response_file",
    "source_boundary",
    "contamination_scan_status",
]

# Boundary enforcement: forbidden phrases for literature_scout output
# These phrases indicate the literature_search artifact crossed into novelty_check territory
LITERATURE_SCOUT_FORBIDDEN_PHRASES = [
    "novelty check report",
    "role: novelty_check",
    "confirmed_novel",
    "already_done",
    "likely_incremental",
    "potentially novel",
    "no prior work",
    "direct overlap: none",
    "absent from literature",
    "this is novel",
    "novelty judgment",
    "novel framing",
]


def _get_ledger_path() -> Path:
    """Resolve ledger path from env var or default location."""
    env_path = os.environ.get("ARIS_LEDGER_PATH", "")
    if env_path:
        return Path(env_path)
    root = find_project_root()
    return root / ".aris" / "calls" / "llm_calls.jsonl"


def _read_ledger(ledger_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Read all entries from ledger. Returns empty list if file doesn't exist."""
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


def _parse_role(role: str, vars_dict: Dict[str, str]) -> Dict[str, Any]:
    """Get expected route for a role by parsing model_route config (no actual call)."""
    # Import model_route lazily to avoid circular import triggering real API calls
    try:
        sys.path.insert(0, str(TOOLS_DIR))
        import model_route as mr
        result = mr.resolve_role(role)
        return {
            "expected_backend": result.get("backend_type", "") or result.get("primary_backend", ""),
            "expected_model": result.get("model", "") or result.get("primary_model", ""),
            "expected_provider": result.get("provider", ""),
            "requires_api_key": result.get("requires_api_key", False),
            "codex_mode": result.get("codex_required_roles_note", "") != "",
            "route_config": result,
        }
    except Exception:
        return {
            "expected_backend": "",
            "expected_model": "",
            "expected_provider": "",
            "requires_api_key": False,
            "codex_mode": False,
            "route_config": {},
        }


def _age_hours(entry: Dict[str, Any]) -> float:
    """Return age of entry in hours (from timestamp)."""
    try:
        ts = datetime.fromisoformat(entry.get("timestamp", ""))
        delta = datetime.now(timezone.utc) - ts
        return delta.total_seconds() / 3600
    except Exception:
        return 999999.0


def validate_role(
    role: str,
    ledger_path: Optional[Path] = None,
    max_age_hours: float = 24.0,
    require_codex_thread: bool = False,
) -> Dict[str, Any]:
    """Validate the most recent ledger call for a given role."""
    # Load expected route (config-only, no real API call)
    root = find_project_root()
    sys.path.insert(0, str(TOOLS_DIR))
    from env_loader import load_env
    env_info = load_env()
    expected = _parse_role(role, env_info.get("vars", {}))

    ledger_entries = _read_ledger(ledger_path)
    if not ledger_entries:
        return {
            "status": "FAIL",
            "role": role,
            "reason": "no_ledger",
            "expected_backend": expected.get("expected_backend", ""),
            "expected_model": expected.get("expected_model", ""),
        }

    # Find most recent call for this role within max_age_hours
    recent = [e for e in reversed(ledger_entries) if e.get("role") == role]
    if not recent:
        return {
            "status": "FAIL",
            "role": role,
            "reason": "no_call_for_role",
            "expected_backend": expected.get("expected_backend", ""),
            "expected_model": expected.get("expected_model", ""),
        }

    latest = recent[0]
    if _age_hours(latest) > max_age_hours:
        return {
            "status": "FAIL",
            "role": role,
            "reason": "call_too_old",
            "latest_call_id": latest.get("call_id", ""),
            "age_hours": round(_age_hours(latest), 1),
            "expected_backend": expected.get("expected_backend", ""),
            "expected_model": expected.get("expected_model", ""),
        }

    impl_source = latest.get("implementation_source", "external_agent_direct")
    routed_used = latest.get("routed_model_used", False)
    actual_backend = latest.get("actual_backend", "")
    actual_model = latest.get("actual_model", "")
    codex_thread_id = latest.get("codex_thread_id", "")
    fallback_used = latest.get("fallback_used", False)
    fallback_reason = latest.get("fallback_reason", "")
    verification_status = latest.get("verification_status", "")
    allowed_next_stage = latest.get("allowed_next_stage", False)
    confidence_downgraded = latest.get("confidence_downgraded", True)
    routing_source = latest.get("routing_source", "")
    response_file = latest.get("response_file", "")
    ledger_output_text = latest.get("output_text", "")
    forbidden_context_checked = latest.get("forbidden_context_checked", False)
    contamination_scan_status = latest.get("contamination_scan_status", "")
    context_manifest = latest.get("context_manifest", None)
    context_hash = latest.get("context_hash", "")
    context_values = {field: latest.get(field, None) for field in REQUIRED_CONTEXT_FIELDS}

    # Determine pass/fail
    status = "PASS"
    reasons: List[str] = []

    # Historical route resolution: prefer recorded route from ledger over current .env
    recorded_route_backend = latest.get("route_expected_backend", "")
    recorded_route_model = latest.get("route_expected_model", "")
    current_expected_backend = expected.get("expected_backend", "")
    current_expected_model = expected.get("expected_model", "")

    # Effective backend/model for Codex/MCP checks
    exp_backend = recorded_route_backend or current_expected_backend
    exp_model = recorded_route_model or current_expected_model

    # Warn if route config changed since the call was made
    route_changed_warning = ""
    if recorded_route_backend and recorded_route_backend != current_expected_backend:
        route_changed_warning = f"route config changed since call: recorded={recorded_route_backend}/{recorded_route_model} current={current_expected_backend}/{current_expected_model}"
    elif recorded_route_model and recorded_route_model != current_expected_model:
        route_changed_warning = f"route config changed since call: recorded={recorded_route_backend}/{recorded_route_model} current={current_expected_backend}/{current_expected_model}"

    if impl_source == "external_agent_direct":
        status = "FAIL"
        reasons.append("implementation_source=external_agent_direct (no real model call)")

    if routed_used and not actual_backend and verification_status != "pending_external_mcp":
        status = "FAIL"
        reasons.append("routed_model_used=true but actual_backend is empty")

    if exp_backend == "mcp" and require_codex_thread:
        if not codex_thread_id or codex_thread_id.strip() in ("none", ""):
            status = "FAIL"
            reasons.append("codex_thread_id required but missing")
    if exp_backend != "mcp" and require_codex_thread:
        status = "FAIL"
        reasons.append("require_codex_thread used for non-Codex role")

    if actual_backend == "codex" and not codex_thread_id:
        status = "FAIL"
        reasons.append("actual_backend=codex but codex_thread_id is missing")

    if actual_backend and actual_backend != "codex" and not actual_model:
        status = "FAIL"
        reasons.append("actual_backend is set but actual_model is missing")

    if fallback_used:
        if not (actual_backend and actual_model and fallback_reason):
            status = "FAIL"
            reasons.append("fallback_used=true but missing actual_backend/model/reason")
        elif status == "PASS":
            status = "PASS_WITH_WARNINGS"
            reasons.append("fallback was used")
        if not allowed_next_stage:
            reasons.append("fallback cannot enter next stage by default")

    if verification_status == "pending_external_mcp":
        if allowed_next_stage:
            status = "FAIL"
            reasons.append("pending_external_mcp cannot allow next stage")
        elif status == "PASS":
            status = "PASS_WITH_WARNINGS"
            reasons.append("pending_external_mcp")
        reasons.append("pending_external_mcp is not a completed trusted role")

    if routing_source == "trusted_role_runner_external_mcp":
        if response_file:
            response_path = Path(response_file)
            if response_path.exists() and response_path.is_file():
                try:
                    if not response_path.read_text(encoding="utf-8", errors="ignore").strip():
                        status = "FAIL"
                        reasons.append("external MCP response_file empty")
                    # else: PASS, file is fine
                except Exception:
                    status = "FAIL"
                    reasons.append("external MCP response_file unreadable")
            else:
                # File missing — check ledger output_text
                if ledger_output_text:
                    if status == "PASS":
                        status = "PASS_WITH_WARNINGS"
                    reasons.append("external MCP response_file missing but ledger output_text retained")
                else:
                    status = "FAIL"
                    reasons.append("external MCP completion missing both response_file and ledger output_text")
        else:
            # No response_file recorded at all
            if ledger_output_text:
                if status == "PASS":
                    status = "PASS_WITH_WARNINGS"
                reasons.append("external MCP response_file not recorded but ledger output_text retained")
            else:
                status = "FAIL"
                reasons.append("external MCP completion missing both response_file and ledger output_text")

    if verification_status in (
        "unverified_external_execution",
        "missing_actual_backend",
        "fallback_unverified",
        "dry_run_untrusted",
        "unsupported_runtime_backend",
        "call_failed",
        "codex_missing_thread_id",
    ):
        status = "FAIL"
        reasons.append(f"verification_status={verification_status}")

    if verification_status == "verified_routed_call" and actual_backend != "codex" and not actual_model:
        status = "FAIL"
        reasons.append("verified_routed_call requires non-empty actual_model for API backends")

    # Codex thread id check: use effective backend (recorded or current)
    if exp_backend != "mcp" and codex_thread_id:
        if route_changed_warning:
            # Historical artifact: route changed, downgrade to warning
            if status == "PASS":
                status = "PASS_WITH_WARNINGS"
            reasons.append(route_changed_warning)
        else:
            status = "FAIL"
            reasons.append("non-Codex role should not record codex_thread_id")

    # Route config changed warning (always applied when route differs)
    if route_changed_warning and route_changed_warning not in reasons:
        if status == "PASS":
            status = "PASS_WITH_WARNINGS"
        reasons.append(route_changed_warning)

    if verification_status in ("verified_routed_call", "verified_with_fallback", "pending_external_mcp"):
        missing_context_fields = [
            field
            for field, value in context_values.items()
            if value is None or (field == "context_hash" and verification_status != "pending_external_mcp" and not str(value).strip())
        ]
        if missing_context_fields:
            status = "FAIL"
            reasons.append(f"missing context fields: {', '.join(missing_context_fields)}")

        if not forbidden_context_checked:
            if role in CRITICAL_CONTEXT_ROLES:
                status = "FAIL"
                reasons.append("critical role requires forbidden_context_checked=true")
            elif status == "PASS":
                status = "PASS_WITH_WARNINGS"
                reasons.append("forbidden_context_checked=false")

        if contamination_scan_status in ("", "not_checked") and role in CRITICAL_CONTEXT_ROLES and verification_status != "pending_external_mcp":
            status = "FAIL"
            reasons.append("critical role requires contamination_scan_status beyond not_checked")

        if context_manifest in (None, ""):
            status = "FAIL"
            reasons.append("context_manifest missing")

    # Literature scout boundary enforcement: check output for forbidden phrases
    if role == "literature_scout":
        output_text_to_check = ""
        if response_file:
            try:
                rp = Path(response_file)
                if rp.exists() and rp.is_file():
                    output_text_to_check = rp.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                pass
        if not output_text_to_check and ledger_output_text:
            output_text_to_check = ledger_output_text
        if output_text_to_check:
            lower_text = output_text_to_check.lower()
            hits = [p for p in LITERATURE_SCOUT_FORBIDDEN_PHRASES if p in lower_text]
            if hits:
                status = "FAIL"
                reasons.append(
                    f"literature_search output crossed into novelty_check boundary: "
                    f"forbidden phrases found: {hits}"
                )

    if not allowed_next_stage and status == "PASS":
        status = "PASS_WITH_WARNINGS"
        reasons.append("allowed_next_stage=false")

    return {
        "status": status,
        "role": role,
        "expected_backend": exp_backend,
        "expected_model": exp_model,
        "expected_provider": expected.get("expected_provider", ""),
        "latest_call_id": latest.get("call_id", ""),
        "timestamp": latest.get("timestamp", ""),
        "implementation_source": impl_source,
        "routed_model_used": routed_used,
        "actual_backend": actual_backend,
        "actual_model": actual_model,
        "codex_thread_id": codex_thread_id or None,
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason or None,
        "verification_status": verification_status,
        "allowed_next_stage": allowed_next_stage,
        "confidence_downgraded": confidence_downgraded,
        "routing_source": routing_source,
        "response_file": response_file or None,
        "context_manifest": context_manifest,
        "context_hash": context_hash,
        "forbidden_context_checked": forbidden_context_checked,
        "contamination_scan_status": contamination_scan_status,
        "current_expected_backend": current_expected_backend,
        "current_expected_model": current_expected_model,
        "recorded_route_backend": recorded_route_backend,
        "recorded_route_model": recorded_route_model,
        "validation_expected_backend": exp_backend,
        "validation_expected_model": exp_model,
        "reason": "; ".join(reasons) if reasons else "all checks passed",
    }


def cmd_summary(ledger_path: Optional[Path] = None) -> Dict[str, Any]:
    """Show trust status for all key roles."""
    root = find_project_root()
    sys.path.insert(0, str(TOOLS_DIR))
    from env_loader import load_env
    env_info = load_env()
    vars_dict = env_info.get("vars", {})

    results = {}
    for role in SUMMARY_ROLES:
        expected = _parse_role(role, vars_dict)
        ledger_entries = _read_ledger(ledger_path)
        recent = [e for e in reversed(ledger_entries) if e.get("role") == role]
        latest = recent[0] if recent else None

        impl_source = latest.get("implementation_source", "unknown") if latest else "no_ledger"
        routed_used = latest.get("routed_model_used", False) if latest else False
        actual_backend = latest.get("actual_backend", "-") if latest else "-"
        codex_thread_id = latest.get("codex_thread_id", "") if latest else ""
        verification_status = latest.get("verification_status", "-") if latest else "-"
        allowed = latest.get("allowed_next_stage", False) if latest else False
        conf_down = latest.get("confidence_downgraded", True) if latest else True

        results[role] = {
            "expected_backend": expected.get("expected_backend", ""),
            "implementation_source": impl_source,
            "routed_model_used": routed_used,
            "actual_backend": actual_backend,
            "has_codex_thread": bool(codex_thread_id and codex_thread_id.strip() not in ("none", "")),
            "verification_status": verification_status,
            "allowed_next_stage": allowed,
            "confidence_downgraded": conf_down,
        }

    return results


def cmd_self_test():
    """Run self-test using a temporary ledger. Does NOT read real .aris/calls/."""
    import shutil
    import tempfile, os

    def with_context(
        entry: Dict[str, Any],
        *,
        manifest: str = "none",
        checked: bool = False,
        scan_status: str = "not_checked",
        source_boundary: str = "role_input_only",
        prompt_file: str = "",
        response_file: str = "",
        context_hash: str = "fixture-context-hash",
    ) -> Dict[str, Any]:
        enriched = dict(entry)
        enriched.update(
            {
                "isolation_mode": "context_manifest" if manifest != "none" else "not_declared",
                "task_id": f"task_{entry['call_id']}",
                "context_manifest": manifest,
                "allowed_input_files": ["allowed/input.md"] if manifest != "none" else [],
                "forbidden_context": ["old review", "user preference"] if manifest != "none" else [],
                "forbidden_context_checked": checked,
                "context_hash": context_hash,
                "prompt_file": prompt_file,
                "response_file": response_file,
                "source_boundary": source_boundary,
                "contamination_scan_status": scan_status,
            }
        )
        return enriched

    # Create temp ledger
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        # Case 1: external_agent_direct → FAIL, allowed_next_stage=false
        entry1 = {
            "call_id": "call_test_001",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "role": "experiment_implementer",
            "implementation_source": "external_agent_direct",
            "routed_model_used": False,
            "actual_backend": "external_agent",
            "actual_model": "unknown",
            "verification_status": "unverified_external_execution",
            "allowed_next_stage": False,
            "confidence_downgraded": True,
            "status": "completed",
        }
        # Case 2: routed_internal_model + llm-chat → PASS
        entry2 = with_context({
            "call_id": "call_test_002",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "role": "idea_generator",
            "implementation_source": "routed_internal_model",
            "routed_model_used": True,
            "actual_backend": "deepseek",
            "actual_model": "deepseek-v4-pro",
            "verification_status": "verified_routed_call",
            "allowed_next_stage": True,
            "confidence_downgraded": False,
            "status": "completed",
        }, manifest="manifest_idea_generator.json", checked=True, scan_status="passed")
        # Case 3: codex without codex_thread_id → FAIL
        entry3 = {
            "call_id": "call_test_003",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "role": "idea_reviewer",
            "implementation_source": "routed_internal_model",
            "routed_model_used": True,
            "actual_backend": "codex",
            "actual_model": "auto",
            "codex_thread_id": "",
            "verification_status": "codex_missing_thread_id",
            "allowed_next_stage": False,
            "confidence_downgraded": True,
            "status": "completed_with_warnings",
        }
        # Case 4: codex with codex_thread_id → PASS
        entry4 = with_context({
            "call_id": "call_test_004",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "role": "novelty_checker",
            "implementation_source": "routed_internal_model",
            "routed_model_used": True,
            "actual_backend": "codex",
            "actual_model": "auto",
            "codex_thread_id": "thread_test_abc123",
            "verification_status": "verified_routed_call",
            "allowed_next_stage": True,
            "confidence_downgraded": False,
            "status": "completed",
        }, manifest="manifest_novelty_checker.json", checked=True, scan_status="passed", prompt_file="prompt.md")
        # Case 5: fallback with explicit fallback_reason → PASS_WITH_WARNINGS
        entry5 = with_context({
            "call_id": "call_test_005",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "role": "final_selector",
            "implementation_source": "routed_internal_model",
            "routed_model_used": True,
            "actual_backend": "deepseek",
            "actual_model": "deepseek-v4-flash",
            "fallback_used": True,
            "fallback_reason": "codex unavailable",
            "verification_status": "verified_with_fallback",
            "allowed_next_stage": False,
            "confidence_downgraded": True,
            "status": "completed_with_fallback",
        }, manifest="manifest_final_selector.json", checked=True, scan_status="passed")
        # Case 6: external MCP pending
        entry6 = with_context({
            "call_id": "call_test_006",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "role": "adversarial_reviewer",
            "implementation_source": "routed_internal_model",
            "routed_model_used": True,
            "actual_backend": "",
            "actual_model": "",
            "verification_status": "pending_external_mcp",
            "allowed_next_stage": False,
            "confidence_downgraded": True,
            "status": "pending_external_mcp",
            "routing_source": "trusted_role_runner_external_mcp_prepare",
        }, manifest="manifest_adversarial_reviewer.json", checked=False, scan_status="not_checked", prompt_file="pending_prompt.md")
        f.write(json.dumps(entry1) + "\n")
        f.write(json.dumps(entry2) + "\n")
        f.write(json.dumps(entry3) + "\n")
        f.write(json.dumps(entry4) + "\n")
        f.write(json.dumps(entry5) + "\n")
        f.write(json.dumps(entry6) + "\n")
        temp_path = f.name

    # Create a second temp ledger for the "no ledger" test
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f2:
        empty_temp_path = f2.name

    response_dir: Optional[Path] = None
    try:
        test_results: Dict[str, Dict] = {}

        # Test case 0: no ledger → FAIL
        r = validate_role("experiment_implementer", Path(empty_temp_path), max_age_hours=24)
        test_results["no_ledger"] = r
        assert r["status"] == "FAIL", f"Expected FAIL for no_ledger, got {r['status']}"
        assert r["reason"] == "no_ledger", f"Expected reason=no_ledger, got {r.get('reason','')}"

        # Test case 1
        r = validate_role("experiment_implementer", Path(temp_path), max_age_hours=24)
        test_results["external_agent_direct"] = r
        assert r["status"] in ("FAIL", "PASS_WITH_WARNINGS"), f"Expected FAIL for external_agent_direct, got {r['status']}"
        assert r["allowed_next_stage"] is False, f"Expected allowed_next_stage=False for external_agent_direct"

        # Test case 2
        r = validate_role("idea_generator", Path(temp_path), max_age_hours=24)
        test_results["routed_llm"] = r
        assert r["status"] == "PASS", f"Expected PASS for routed_llm, got {r['status']}"

        # Test case 3
        r = validate_role("idea_reviewer", Path(temp_path), max_age_hours=24, require_codex_thread=True)
        test_results["codex_no_thread"] = r
        assert r["status"] == "FAIL", f"Expected FAIL for codex_no_thread, got {r['status']}"

        # Test case 4
        r = validate_role("novelty_checker", Path(temp_path), max_age_hours=24)
        test_results["codex_with_thread"] = r
        assert r["status"] == "PASS", f"Expected PASS for codex_with_thread, got {r['status']}"

        # Test case 5
        r = validate_role("final_selector", Path(temp_path), max_age_hours=24)
        test_results["fallback_explicit"] = r
        assert r["status"] == "PASS_WITH_WARNINGS", f"Expected PASS_WITH_WARNINGS for fallback_explicit, got {r['status']}"

        # Test case 5b: pending_external_mcp cannot be treated as completed trusted output
        r = validate_role("adversarial_reviewer", Path(temp_path), max_age_hours=24)
        test_results["pending_external_mcp"] = r
        assert r["status"] in ("FAIL", "PASS_WITH_WARNINGS"), f"Expected FAIL/PASS_WITH_WARNINGS for pending_external_mcp, got {r['status']}"
        assert r["allowed_next_stage"] is False

        # Test case 6: fallback without fallback_reason → FAIL
        entry7 = {
            "call_id": "call_test_007",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "role": "paper_writer",
            "implementation_source": "routed_internal_model",
            "routed_model_used": True,
            "actual_backend": "deepseek",
            "actual_model": "deepseek-v4-pro",
            "fallback_used": True,
            "fallback_reason": "",
            "verification_status": "fallback_unverified",
            "allowed_next_stage": False,
            "confidence_downgraded": True,
            "status": "completed_with_fallback",
        }
        with open(temp_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry7) + "\n")
        r = validate_role("paper_writer", Path(temp_path), max_age_hours=24)
        test_results["fallback_no_reason"] = r
        assert r["status"] == "FAIL", f"Expected FAIL for fallback_no_reason, got {r['status']}"

        # Test case 7: routed_model_used=true but missing actual_backend → FAIL
        entry8 = {
            "call_id": "call_test_008",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "role": "result_judge",
            "implementation_source": "routed_internal_model",
            "routed_model_used": True,
            "actual_backend": "",
            "actual_model": "",
            "verification_status": "missing_actual_backend",
            "allowed_next_stage": False,
            "confidence_downgraded": True,
            "status": "completed",
        }
        with open(temp_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry8) + "\n")
        r = validate_role("result_judge", Path(temp_path), max_age_hours=24)
        test_results["missing_actual_backend"] = r
        assert r["status"] == "FAIL", f"Expected FAIL for missing_actual_backend, got {r['status']}"

        # Test case 8: verified_routed_call but missing actual_model → FAIL
        entry9 = with_context({
            "call_id": "call_test_009",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "role": "claims_drafter",
            "implementation_source": "routed_internal_model",
            "routed_model_used": True,
            "actual_backend": "deepseek",
            "actual_model": "",
            "verification_status": "verified_routed_call",
            "allowed_next_stage": False,
            "confidence_downgraded": True,
            "status": "completed",
        }, manifest="manifest_claims_drafter.json", checked=True, scan_status="passed")
        with open(temp_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry9) + "\n")
        r = validate_role("claims_drafter", Path(temp_path), max_age_hours=24)
        test_results["verified_call_missing_model"] = r
        # verified_routed_call with no actual_model is suspicious; should be FAIL or at least not PASS
        assert r["status"] != "PASS", f"Did not expect PASS for verified_call_missing_model, got {r['status']}"

        # Test case 9: dry_run_untrusted cannot be accepted as real trusted output
        entry10 = {
            "call_id": "call_test_010",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "role": "gap_extractor",
            "implementation_source": "routed_internal_model",
            "routed_model_used": True,
            "actual_backend": "dry_run",
            "actual_model": "dry_run",
            "verification_status": "dry_run_untrusted",
            "allowed_next_stage": False,
            "confidence_downgraded": True,
            "status": "completed_dry_run",
        }
        with open(temp_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry10) + "\n")
        r = validate_role("gap_extractor", Path(temp_path), max_age_hours=24)
        test_results["dry_run_untrusted"] = r
        assert r["status"] == "FAIL", f"Expected FAIL for dry_run_untrusted, got {r['status']}"
        assert r["allowed_next_stage"] is False

        # Test case 10: codex with codex_thread_id in fixture → PASS
        r = validate_role("novelty_checker", Path(temp_path), max_age_hours=24)
        test_results["codex_thread_fixture"] = r
        assert r["status"] == "PASS", f"Expected PASS for codex_thread_fixture, got {r['status']}"

        # Test case 11: unsupported_runtime_backend → FAIL
        entry11 = {
            "call_id": "call_test_011",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "role": "experiment_code_reviewer",
            "implementation_source": "routed_internal_model",
            "routed_model_used": True,
            "actual_backend": "codex",
            "actual_model": "auto",
            "verification_status": "unsupported_runtime_backend",
            "allowed_next_stage": False,
            "confidence_downgraded": True,
            "status": "failed",
        }
        with open(temp_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry11) + "\n")
        r = validate_role("experiment_code_reviewer", Path(temp_path), max_age_hours=24)
        test_results["unsupported_runtime_backend"] = r
        assert r["status"] == "FAIL", f"Expected FAIL for unsupported_runtime_backend, got {r['status']}"

        # Test case 12: call_failed → FAIL
        entry12 = {
            "call_id": "call_test_012",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "role": "paper_summarizer",
            "implementation_source": "routed_internal_model",
            "routed_model_used": True,
            "actual_backend": "deepseek",
            "actual_model": "deepseek-v4-pro",
            "verification_status": "call_failed",
            "allowed_next_stage": False,
            "confidence_downgraded": True,
            "status": "failed",
        }
        with open(temp_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry12) + "\n")
        r = validate_role("paper_summarizer", Path(temp_path), max_age_hours=24)
        test_results["call_failed"] = r
        assert r["status"] == "FAIL", f"Expected FAIL for call_failed, got {r['status']}"

        # Test case 13: external MCP completed with response file -> PASS
        response_dir = Path(tempfile.mkdtemp())
        response_file = response_dir / "codex_response.md"
        response_file.write_text("trusted external codex response", encoding="utf-8")
        entry13 = with_context({
            "call_id": "call_test_013",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "role": "idea_reviewer",
            "implementation_source": "routed_internal_model",
            "routed_model_used": True,
            "actual_backend": "codex",
            "actual_model": "auto",
            "codex_thread_id": "thread_external_ok",
            "verification_status": "verified_routed_call",
            "allowed_next_stage": True,
            "confidence_downgraded": False,
            "status": "completed",
            "routing_source": "trusted_role_runner_external_mcp",
            "response_file": str(response_file),
        }, manifest="manifest_idea_reviewer.json", checked=True, scan_status="passed", prompt_file="external_prompt.md", response_file=str(response_file))
        with open(temp_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry13) + "\n")
        r = validate_role("idea_reviewer", Path(temp_path), max_age_hours=24)
        test_results["external_mcp_completed"] = r
        assert r["status"] == "PASS", f"Expected PASS for external_mcp_completed, got {r['status']}"

        # Test case 14: external MCP completed but response artifact missing -> FAIL
        entry14 = with_context({
            "call_id": "call_test_014",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "role": "contract_reviewer",
            "route_expected_backend": "mcp",
            "route_expected_model": "auto",
            "implementation_source": "routed_internal_model",
            "routed_model_used": True,
            "actual_backend": "codex",
            "actual_model": "auto",
            "codex_thread_id": "thread_external_missing_response",
            "verification_status": "verified_routed_call",
            "allowed_next_stage": True,
            "confidence_downgraded": False,
            "status": "completed",
            "routing_source": "trusted_role_runner_external_mcp",
            "response_file": str(response_dir / "missing.md"),
        }, manifest="manifest_contract_reviewer.json", checked=True, scan_status="passed", prompt_file="external_prompt_missing.md", response_file=str(response_dir / "missing.md"))
        with open(temp_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry14) + "\n")
        r = validate_role("contract_reviewer", Path(temp_path), max_age_hours=24)
        test_results["external_mcp_missing_response"] = r
        assert r["status"] == "FAIL", f"Expected FAIL for external_mcp_missing_response, got {r['status']}"

        # Test B: external MCP completed, response_file missing, but ledger output_text exists -> PASS_WITH_WARNINGS
        entry14b = with_context({
            "call_id": "call_test_014b",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "role": "contract_reviewer",
            "route_expected_backend": "mcp",
            "route_expected_model": "auto",
            "implementation_source": "routed_internal_model",
            "routed_model_used": True,
            "actual_backend": "codex",
            "actual_model": "auto",
            "codex_thread_id": "thread_external_with_output_text",
            "verification_status": "verified_routed_call",
            "allowed_next_stage": True,
            "confidence_downgraded": False,
            "status": "completed",
            "routing_source": "trusted_role_runner_external_mcp",
            "response_file": str(response_dir / "truly_missing.md"),
            "output_text": "# Research Contract\n\n## Research Question\n\nTrusted output text retained in ledger.",
        }, manifest="manifest_contract_reviewer_b.json", checked=True, scan_status="passed", prompt_file="external_prompt_b.md", response_file=str(response_dir / "truly_missing.md"))
        with open(temp_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry14b) + "\n")
        r = validate_role("contract_reviewer", Path(temp_path), max_age_hours=24)
        test_results["external_mcp_missing_file_with_output_text"] = r
        assert r["status"] == "PASS_WITH_WARNINGS", f"Expected PASS_WITH_WARNINGS for external_mcp_missing_file_with_output_text, got {r['status']}"
        assert r["allowed_next_stage"] is True, f"Expected allowed_next_stage=True for external_mcp_missing_file_with_output_text"

        # Test C: external MCP completed, response_file missing, output_text empty -> FAIL
        entry14c = with_context({
            "call_id": "call_test_014c",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "role": "contract_reviewer",
            "route_expected_backend": "mcp",
            "route_expected_model": "auto",
            "implementation_source": "routed_internal_model",
            "routed_model_used": True,
            "actual_backend": "codex",
            "actual_model": "auto",
            "codex_thread_id": "thread_external_no_output",
            "verification_status": "verified_routed_call",
            "allowed_next_stage": True,
            "confidence_downgraded": False,
            "status": "completed",
            "routing_source": "trusted_role_runner_external_mcp",
            "response_file": str(response_dir / "also_missing.md"),
            "output_text": "",
        }, manifest="manifest_contract_reviewer_c.json", checked=True, scan_status="passed", prompt_file="external_prompt_c.md", response_file=str(response_dir / "also_missing.md"))
        with open(temp_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry14c) + "\n")
        r = validate_role("contract_reviewer", Path(temp_path), max_age_hours=24)
        test_results["external_mcp_missing_file_no_output"] = r
        assert r["status"] == "FAIL", f"Expected FAIL for external_mcp_missing_file_no_output, got {r['status']}"

        # Test case 15: API role with codex_thread_id should fail
        entry15 = with_context({
            "call_id": "call_test_015",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "role": "idea_generator",
            "implementation_source": "routed_internal_model",
            "routed_model_used": True,
            "actual_backend": "deepseek",
            "actual_model": "deepseek-v4-pro",
            "codex_thread_id": "should_not_exist",
            "verification_status": "verified_routed_call",
            "allowed_next_stage": True,
            "confidence_downgraded": False,
            "status": "completed",
        }, manifest="manifest_idea_generator_2.json", checked=True, scan_status="passed")
        with open(temp_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry15) + "\n")
        r = validate_role("idea_generator", Path(temp_path), max_age_hours=24)
        test_results["api_role_with_codex_thread"] = r
        assert r["status"] == "FAIL", f"Expected FAIL for api_role_with_codex_thread, got {r['status']}"

        # Test case 16: historical Codex artifact remains valid after route config changes
        # Simulates: contract_reviewer was Codex when the call was made, but .env now says DS_PRO_HIGH
        entry16 = with_context({
            "call_id": "call_test_016",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "role": "contract_reviewer",
            "route_expected_backend": "mcp",
            "route_expected_model": "auto",
            "implementation_source": "routed_internal_model",
            "routed_model_used": True,
            "actual_backend": "codex",
            "actual_model": "auto",
            "codex_thread_id": "thread_historical_codex",
            "verification_status": "verified_routed_call",
            "allowed_next_stage": True,
            "confidence_downgraded": False,
            "status": "completed",
            "routing_source": "trusted_role_runner_external_mcp",
            "response_file": str(response_dir / "historical_missing.md") if response_dir else "tmp/historical_missing.md",
            "output_text": "# Research Contract\n\nHistorical Codex output retained in ledger.",
        }, manifest="manifest_contract_reviewer_historical.json", checked=True, scan_status="passed", prompt_file="historical_prompt.md", response_file=str(response_dir / "historical_missing.md") if response_dir else "tmp/historical_missing.md")
        with open(temp_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry16) + "\n")
        r = validate_role("contract_reviewer", Path(temp_path), max_age_hours=24)
        test_results["historical_codex_artifact"] = r
        assert r["status"] in ("PASS", "PASS_WITH_WARNINGS"), f"Expected PASS or PASS_WITH_WARNINGS for historical_codex_artifact, got {r['status']}"
        assert r["allowed_next_stage"] is True, f"Expected allowed_next_stage=True for historical_codex_artifact, got {r['allowed_next_stage']}"

        # Test case 17: literature_scout with "Novelty Check Report" in output → FAIL (boundary violation)
        response_boundary1 = response_dir / "boundary_violation1.md"
        response_boundary1.write_text("# Novelty Check Report\n\nThe idea is confirmed_novel.", encoding="utf-8")
        entry17 = with_context({
            "call_id": "call_test_017",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "role": "literature_scout",
            "implementation_source": "routed_internal_model",
            "routed_model_used": True,
            "actual_backend": "deepseek",
            "actual_model": "deepseek-v4-flash",
            "verification_status": "verified_routed_call",
            "allowed_next_stage": True,
            "confidence_downgraded": False,
            "status": "completed",
            "response_file": str(response_boundary1),
        }, manifest="manifest_literature_scout_boundary1.json", checked=True, scan_status="passed", response_file=str(response_boundary1))
        with open(temp_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry17) + "\n")
        r = validate_role("literature_scout", Path(temp_path), max_age_hours=24)
        test_results["literature_scout_boundary_novelty_report"] = r
        assert r["status"] == "FAIL", f"Expected FAIL for literature_scout with 'Novelty Check Report', got {r['status']}"
        assert "boundary" in r["reason"].lower(), f"Expected boundary in reason, got {r['reason']}"

        # Test case 18: literature_scout with "potentially novel" in output_text → FAIL
        entry18 = with_context({
            "call_id": "call_test_018",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "role": "literature_scout",
            "implementation_source": "routed_internal_model",
            "routed_model_used": True,
            "actual_backend": "deepseek",
            "actual_model": "deepseek-v4-flash",
            "verification_status": "verified_routed_call",
            "allowed_next_stage": True,
            "confidence_downgraded": False,
            "status": "completed",
            "output_text": "# Literature Search\n\nThe approach is potentially novel based on available evidence.",
        }, manifest="manifest_literature_scout_boundary2.json", checked=True, scan_status="passed")
        with open(temp_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry18) + "\n")
        r = validate_role("literature_scout", Path(temp_path), max_age_hours=24)
        test_results["literature_scout_boundary_potentially_novel"] = r
        assert r["status"] == "FAIL", f"Expected FAIL for literature_scout with 'potentially novel', got {r['status']}"

        # Test case 19: novelty_checker with novelty words → NOT affected (should PASS)
        entry19 = with_context({
            "call_id": "call_test_019",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "role": "novelty_checker",
            "implementation_source": "routed_internal_model",
            "routed_model_used": True,
            "actual_backend": "codex",
            "actual_model": "auto",
            "codex_thread_id": "thread_novelty_boundary_test",
            "verification_status": "verified_routed_call",
            "allowed_next_stage": True,
            "confidence_downgraded": False,
            "status": "completed",
            "output_text": "# Novelty Check Report\n\nThe idea is confirmed_novel with no prior work found.",
        }, manifest="manifest_novelty_checker_boundary.json", checked=True, scan_status="passed", prompt_file="novelty_prompt.md")
        with open(temp_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry19) + "\n")
        r = validate_role("novelty_checker", Path(temp_path), max_age_hours=24)
        test_results["novelty_checker_boundary_not_affected"] = r
        assert r["status"] == "PASS", f"Expected PASS for novelty_checker with novelty words (not affected), got {r['status']}"

        print("SELF-TEST RESULTS:")
        print(json.dumps(test_results, ensure_ascii=False, indent=2))

        # Verify git status is clean for .aris
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
        os.unlink(empty_temp_path)
        if response_dir is not None:
            shutil.rmtree(response_dir, ignore_errors=True)


def main():
    args = sys.argv[1:]
    if not args or "-h" in args or "--help" in args:
        print(__doc__)
        sys.exit(0)

    ledger_path: Optional[Path] = None
    role: str = ""
    max_age_hours: float = 24.0
    require_codex_thread: bool = False
    summary_mode: bool = False
    self_test_mode: bool = False

    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--role" and i + 1 < len(args):
            role = args[i + 1]
            i += 2
        elif arg == "--ledger-path" and i + 1 < len(args):
            ledger_path = Path(args[i + 1])
            i += 2
        elif arg == "--max-age-hours" and i + 1 < len(args):
            max_age_hours = float(args[i + 1])
            i += 2
        elif arg == "--require-codex-thread":
            require_codex_thread = True
            i += 1
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
        print("Error: --role <role> is required (or use --summary / --self-test)", file=sys.stderr)
        sys.exit(1)

    result = validate_role(role, ledger_path, max_age_hours, require_codex_thread)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if result["status"] == "FAIL":
        sys.exit(1)
    elif result["status"] == "PASS_WITH_WARNINGS":
        sys.exit(0)


if __name__ == "__main__":
    main()
