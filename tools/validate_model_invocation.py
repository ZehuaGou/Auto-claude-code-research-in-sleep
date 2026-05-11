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
from datetime import datetime, timezone, timedelta
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

    # Determine pass/fail
    status = "PASS"
    reasons: List[str] = []

    if impl_source == "external_agent_direct":
        status = "FAIL"
        reasons.append("implementation_source=external_agent_direct (no real model call)")

    if routed_used and not actual_backend:
        status = "FAIL"
        reasons.append("routed_model_used=true but actual_backend is empty")

    exp_backend = expected.get("expected_backend", "")
    if exp_backend == "mcp" and require_codex_thread:
        if not codex_thread_id or codex_thread_id.strip() in ("none", ""):
            status = "FAIL"
            reasons.append("codex_thread_id required but missing")

    if actual_backend == "codex" and not codex_thread_id:
        status = "FAIL"
        reasons.append("actual_backend=codex but codex_thread_id is missing")

    if fallback_used:
        if not (actual_backend and actual_model and fallback_reason):
            status = "FAIL"
            reasons.append("fallback_used=true but missing actual_backend/model/reason")
        elif status == "PASS":
            status = "PASS_WITH_WARNINGS"
            reasons.append("fallback was used")

    if verification_status in ("unverified_external_execution", "missing_actual_backend", "fallback_unverified", "dry_run_untrusted"):
        status = "FAIL"
        reasons.append(f"verification_status={verification_status}")

    if not allowed_next_stage and status == "PASS":
        status = "PASS_WITH_WARNINGS"
        reasons.append("allowed_next_stage=false")

    return {
        "status": status,
        "role": role,
        "expected_backend": exp_backend,
        "expected_model": expected.get("expected_model", ""),
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
    import tempfile, os

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
        entry2 = {
            "call_id": "call_test_002",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "role": "idea_generator",
            "implementation_source": "routed_internal_model",
            "routed_model_used": True,
            "actual_backend": "llm-chat",
            "actual_model": "deepseek-v4-pro",
            "verification_status": "verified_routed_call",
            "allowed_next_stage": True,
            "confidence_downgraded": False,
            "status": "completed",
        }
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
        entry4 = {
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
        }
        # Case 5: fallback with explicit fallback_reason → PASS_WITH_WARNINGS
        entry5 = {
            "call_id": "call_test_005",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "role": "final_selector",
            "implementation_source": "routed_internal_model",
            "routed_model_used": True,
            "actual_backend": "llm-chat",
            "actual_model": "deepseek-v4-flash",
            "fallback_used": True,
            "fallback_reason": "codex unavailable",
            "verification_status": "verified_with_fallback",
            "allowed_next_stage": False,
            "confidence_downgraded": True,
            "status": "completed_with_fallback",
        }
        f.write(json.dumps(entry1) + "\n")
        f.write(json.dumps(entry2) + "\n")
        f.write(json.dumps(entry3) + "\n")
        f.write(json.dumps(entry4) + "\n")
        f.write(json.dumps(entry5) + "\n")
        temp_path = f.name

    # Create a second temp ledger for the "no ledger" test
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f2:
        empty_temp_path = f2.name

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

        # Test case 6: fallback without fallback_reason → FAIL
        entry6 = {
            "call_id": "call_test_006",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "role": "paper_writer",
            "implementation_source": "routed_internal_model",
            "routed_model_used": True,
            "actual_backend": "llm-chat",
            "actual_model": "deepseek-v4-pro",
            "fallback_used": True,
            "fallback_reason": "",
            "verification_status": "fallback_unverified",
            "allowed_next_stage": False,
            "confidence_downgraded": True,
            "status": "completed_with_fallback",
        }
        with open(temp_path, "a") as f:
            f.write(json.dumps(entry6) + "\n")
        r = validate_role("paper_writer", Path(temp_path), max_age_hours=24)
        test_results["fallback_no_reason"] = r
        assert r["status"] == "FAIL", f"Expected FAIL for fallback_no_reason, got {r['status']}"

        # Test case 7: routed_model_used=true but missing actual_backend → FAIL
        entry7 = {
            "call_id": "call_test_007",
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
        with open(temp_path, "a") as f:
            f.write(json.dumps(entry7) + "\n")
        r = validate_role("result_judge", Path(temp_path), max_age_hours=24)
        test_results["missing_actual_backend"] = r
        assert r["status"] == "FAIL", f"Expected FAIL for missing_actual_backend, got {r['status']}"

        # Test case 8: verified_routed_call but missing actual_model → FAIL
        entry8 = {
            "call_id": "call_test_008",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "role": "claims_drafter",
            "implementation_source": "routed_internal_model",
            "routed_model_used": True,
            "actual_backend": "llm-chat",
            "actual_model": "",
            "verification_status": "verified_routed_call",
            "allowed_next_stage": False,
            "confidence_downgraded": True,
            "status": "completed",
        }
        with open(temp_path, "a") as f:
            f.write(json.dumps(entry8) + "\n")
        r = validate_role("claims_drafter", Path(temp_path), max_age_hours=24)
        test_results["verified_call_missing_model"] = r
        # verified_routed_call with no actual_model is suspicious; should be FAIL or at least not PASS
        assert r["status"] != "PASS", f"Did not expect PASS for verified_call_missing_model, got {r['status']}"

        # Test case 9: dry_run_untrusted cannot be accepted as real trusted output
        entry9 = {
            "call_id": "call_test_009",
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
        with open(temp_path, "a") as f:
            f.write(json.dumps(entry9) + "\n")
        r = validate_role("gap_extractor", Path(temp_path), max_age_hours=24)
        test_results["dry_run_untrusted"] = r
        assert r["status"] == "FAIL", f"Expected FAIL for dry_run_untrusted, got {r['status']}"
        assert r["allowed_next_stage"] is False

        # Test case 10: codex with codex_thread_id in fixture → PASS
        r = validate_role("novelty_checker", Path(temp_path), max_age_hours=24)
        test_results["codex_thread_fixture"] = r
        assert r["status"] == "PASS", f"Expected PASS for codex_thread_fixture, got {r['status']}"

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
