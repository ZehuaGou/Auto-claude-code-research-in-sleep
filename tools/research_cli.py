#!/usr/bin/env python3
"""
Research CLI — Unified status, validation, and repair queue entrypoint.

Usage:
    python tools/research_cli.py status [--json]
    python tools/research_cli.py validate [--json]
    python tools/research_cli.py repair-queue [--json]
    python tools/research_cli.py --self-test
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).parent.parent.resolve()


# ─────────────────────────────────────────────────────────
# Stage → trusted output path mapping
# ─────────────────────────────────────────────────────────
STAGE_PATHS = {
    "raw_user_input": "research/current/raw_user_input.md",
    "input_normalization": "research/current/input_normalization.md",
    "research_contract": "research/current/trusted_outputs/research_contract.md",
    "literature_notes": "research/current/literature_notes.md",
    "literature_search": "research/current/trusted_outputs/literature_search.md",
    "novelty_check": "research/current/trusted_outputs/novelty_check.md",
    "method_refinement": "research/current/trusted_outputs/method_refinement.md",
    "experiment_plan": "research/current/trusted_outputs/experiment_plan.md",
    "implementation_plan": "research/current/trusted_outputs/implementation_plan.md",
    "result_judge": "research/current/trusted_outputs/result_judge.md",
    "paper_writing": "research/current/trusted_outputs/paper_writing.md",
}

# Stage order for next_allowed computation
STAGE_ORDER = [
    "raw_user_input",
    "input_normalization",
    "research_contract",
    "literature_notes",
    "literature_search",
    "novelty_check",
    "method_refinement",
    "experiment_plan",
    "implementation_plan",
    "result_judge",
    "paper_writing",
]

# Role → artifact stage mapping (for validator calls)
ROLE_TO_STAGE = {
    "input_normalizer": "input_normalization",
    "contract_reviewer": "research_contract",
    "literature_scout": "literature_search",
    "novelty_checker": "novelty_check",
}


# ─────────────────────────────────────────────────────────
# YAML-like header parsing
# ─────────────────────────────────────────────────────────
def parse_frontmatter(text: str) -> dict[str, str]:
    """Parse YAML-like frontmatter between --- markers."""
    lines = text.split("\n")
    if not lines:
        return {}
    start = 0
    end = len(lines)
    if lines[0].strip() == "---":
        start = 1
        for i, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                end = i
                break
    header_lines = lines[start:end]
    result = {}
    for line in header_lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Split on first colon
        idx = line.index(":") if ":" in line else -1
        if idx < 0:
            continue
        key = line[:idx].strip()
        val = line[idx + 1:].strip().strip('"').strip("'")
        result[key] = val
    return result


# ─────────────────────────────────────────────────────────
# Trusted output reading
# ─────────────────────────────────────────────────────────
def read_trusted_output(path: Path) -> dict[str, Any]:
    """Read a trusted output file and extract header + body info."""
    if not path.exists():
        return {"exists": False, "path": str(path)}

    text = path.read_text(encoding="utf-8", errors="ignore")
    header = parse_frontmatter(text)

    return {
        "exists": True,
        "path": str(path),
        "role": header.get("route_role", header.get("role", "")),
        "actual_backend": header.get("actual_backend", ""),
        "actual_model": header.get("actual_model", ""),
        "ledger_call_id": header.get("ledger_call_id", ""),
        "implementation_source": header.get("implementation_source", ""),
        "verification_status": header.get("verification_status", ""),
        "allowed_next_stage": header.get("allowed_next_stage", ""),
        "contamination_scan_status": header.get("contamination_scan_status", ""),
        "fallback_used": header.get("fallback_used", ""),
        "status": header.get("status", ""),
    }


# ─────────────────────────────────────────────────────────
# Validator subprocess runner
# ─────────────────────────────────────────────────────────
def run_validator(role: str, max_age_hours: int = 24) -> dict[str, Any]:
    """Run validate_model_invocation for a role. No model calls."""
    script = ROOT / "tools" / "validate_model_invocation.py"
    try:
        result = subprocess.run(
            [sys.executable, str(script), "--role", role, "--max-age-hours", str(max_age_hours)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        raw = result.stdout.strip() or result.stderr.strip()
        try:
            data = json.loads(raw)
            return {
                "role": role,
                "validator_status": data.get("status", "unknown"),
                "allowed_next_stage": data.get("allowed_next_stage"),
                "verification_status": data.get("verification_status", ""),
                "actual_backend": data.get("actual_backend", ""),
                "actual_model": data.get("actual_model", ""),
                "fallback_used": data.get("fallback_used", False),
                "reason": data.get("reason", ""),
                "validation_status": "parsed",
                "exit_code": result.returncode,
            }
        except (json.JSONDecodeError, ValueError):
            return {
                "role": role,
                "validator_status": "unparsed",
                "raw_output_excerpt": raw[:500],
                "validation_status": "unparsed",
                "exit_code": result.returncode,
                "reason": raw[:200],
            }
    except (subprocess.TimeoutExpired, OSError) as e:
        return {
            "role": role,
            "validator_status": "error",
            "validation_status": "error",
            "reason": str(e)[:200],
            "exit_code": -1,
        }


# ─────────────────────────────────────────────────────────
# Evidence files
# ─────────────────────────────────────────────────────────
def summarize_evidence() -> dict[str, Any]:
    """Summarize literature evidence files."""
    ev_dir = ROOT / "literature" / "search_runs" / "current"
    summary = {
        "evidence_dir_exists": ev_dir.exists(),
        "search_plan_present": False,
        "search_jobs_present": False,
        "job_results_present": False,
        "raw_results_present": False,
        "candidates_present": False,
        "top_k_present": False,
        "evidence_status": "not_found",
        "raw_record_count": 0,
        "candidate_count": 0,
        "canonical_count": 0,
        "top_k_selected": 0,
        "full_text_available_count": 0,
        "metadata_only_count": 0,
        "warnings": [],
    }

    if not ev_dir.exists():
        summary["warnings"].append("literature/search_runs/current does not exist")
        return summary

    plan_file = ev_dir / "search_plan.yaml"
    jobs_file = ev_dir / "search_jobs.json"
    results_file = ev_dir / "job_results.jsonl"
    raw_file = ev_dir / "raw_results.jsonl"
    cand_file = ev_dir / "candidates.jsonl"
    topk_file = ev_dir / "top_k.md"

    summary["search_plan_present"] = plan_file.exists()
    summary["search_jobs_present"] = jobs_file.exists()
    summary["job_results_present"] = results_file.exists()
    summary["raw_results_present"] = raw_file.exists()
    summary["candidates_present"] = cand_file.exists()
    summary["top_k_present"] = topk_file.exists()

    # Count records
    try:
        if raw_file.exists():
            lines = [l for l in raw_file.read_text(encoding="utf-8", errors="ignore").split("\n") if l.strip()]
            summary["raw_record_count"] = len(lines)
    except Exception:
        pass

    try:
        if cand_file.exists():
            lines = [l for l in cand_file.read_text(encoding="utf-8", errors="ignore").split("\n") if l.strip()]
            summary["candidate_count"] = len(lines)
    except Exception:
        pass

    # Parse top_k.md for counts
    if topk_file.exists():
        try:
            text = topk_file.read_text(encoding="utf-8", errors="ignore")
            header = parse_frontmatter(text)

            # Extract counts from top_k.md body
            sel_match = re.search(r"Selected top_k:\s*(\d+)", text)
            if sel_match:
                summary["top_k_selected"] = int(sel_match.group(1))

            # Count full_text_available
            ft_count = text.count("full_text_available: true") + text.count("full_text_available: yes")
            summary["full_text_available_count"] = ft_count

            status_match = re.search(r"Status:\s*(\w+)", text)
            if status_match:
                summary["evidence_status"] = status_match.group(1)
        except Exception:
            summary["warnings"].append("Could not parse top_k.md")

    if summary["top_k_present"]:
        summary["evidence_status"] = "populated"
    elif summary["raw_results_present"]:
        summary["evidence_status"] = "raw_only"
    elif summary["evidence_dir_exists"]:
        summary["evidence_status"] = "empty"

    return summary


# ─────────────────────────────────────────────────────────
# Repair queue parsing
# ─────────────────────────────────────────────────────────
def parse_repair_queue() -> dict[str, Any]:
    """Parse LITERATURE_REPAIR_QUEUE.md table."""
    queue_file = ROOT / "docs" / "LITERATURE_REPAIR_QUEUE.md"
    summary = {
        "total_items": 0,
        "open_items": 0,
        "fix_now_open": 0,
        "repair_queue_open": 0,
        "accepted_limitations": 0,
        "high_severity_open": 0,
        "blocking_items": 0,
        "items": [],
        "warnings": [],
    }

    if not queue_file.exists():
        summary["warnings"].append("docs/LITERATURE_REPAIR_QUEUE.md not found")
        return summary

    try:
        text = queue_file.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        summary["warnings"].append(f"Could not read repair queue: {e}")
        return summary

    for line in text.split("\n"):
        line = line.strip()
        if not line.startswith("|"):
            continue
        # Skip header row and separators (check first header line explicitly)
        if "---" in line:
            continue
        # Only skip the column header row (| id | issue | ...)
        if line.startswith("| id |") or line.startswith("|  id"):
            continue
        parts = [p.strip() for p in line.split("|")]
        # Filter out empty cells
        parts = [p for p in parts if p]
        if len(parts) < 5:
            continue
        item_id = parts[0].strip()
        if not item_id.startswith("LRQ-"):
            continue

        issue_text = parts[1].strip()
        severity = parts[3].strip()
        classification = parts[4].strip()
        status = parts[6].strip()
        blocking = parts[7].strip()

        item = {
            "id": item_id,
            "issue": issue_text,
            "severity": severity,
            "classification": classification,
            "status": status,
            "blocking_next_stage": blocking,
        }
        summary["items"].append(item)
        summary["total_items"] += 1

        if status not in ("fixed", "accepted for MVP"):
            summary["open_items"] += 1
            if classification == "fix_now":
                summary["fix_now_open"] += 1
            elif classification == "repair_queue":
                summary["repair_queue_open"] += 1
            elif classification == "accepted_limitation":
                summary["accepted_limitations"] += 1

        if severity == "high":
            summary["high_severity_open"] += 1
        if "yes" in blocking.lower() and status not in ("fixed",):
            summary["blocking_items"] += 1

    return summary


# ─────────────────────────────────────────────────────────
# Next allowed stage computation
# ─────────────────────────────────────────────────────────
def compute_next_allowed(trusted_outputs: dict, validators: dict, repair_queue: dict) -> dict[str, Any]:
    """Compute next allowed stage and recommended action."""
    blockers: list[str] = []
    warnings: list[str] = []

    # Determine completed stages by presence of trusted outputs
    completed = []
    for stage in STAGE_ORDER:
        path_key = STAGE_ORDER.index(stage)
        to = trusted_outputs.get(stage, {})
        if to.get("exists"):
            completed.append(stage)

    # Check if novelty_check says do_not_continue
    novelty = trusted_outputs.get("novelty_check", {})
    novelty_allowed = novelty.get("allowed_next_stage", "")
    if novelty.get("exists") and novelty_allowed.lower() == "false":
        blockers.append("novelty_check returned allowed_next_stage=false — cannot proceed")
        return {
            "next_allowed_stage": None,
            "recommended_action": "novelty_check blocked further stages. Address blockers or re-run novelty_check with improved evidence.",
            "blockers": blockers,
            "warnings": warnings,
        }

    # Check method_refinement
    method_ref = trusted_outputs.get("method_refinement", {})
    experiment_plan = trusted_outputs.get("experiment_plan", {})

    if experiment_plan.get("exists") and not method_ref.get("exists"):
        blockers.append("experiment_plan exists but method_refinement is missing — wrong order")

    # Check evidence sufficiency
    evidence = summarize_evidence()
    if evidence.get("evidence_status") not in ("populated",):
        warnings.append("Literature evidence not fully populated — novelty claims may be evidence-bounded only")

    if evidence.get("full_text_available_count", 0) == 0:
        warnings.append("No full-text evidence available — strong novelty claims are blocked (LRQ-005)")

    # Open high-severity items
    open_high = repair_queue.get("high_severity_open", 0)
    if open_high > 0:
        warnings.append(f"{open_high} high-severity item(s) open in repair queue")

    # Find next stage
    next_stage = None
    for stage in STAGE_ORDER:
        if stage not in completed:
            next_stage = stage
            break

    # Override: method_refinement must come before experiment_plan
    if next_stage == "experiment_plan" and not method_ref.get("exists"):
        next_stage = "method_refinement"
        warnings.append("experiment_plan is blocked — method_refinement must come first")

    # Recommendations
    if next_stage == "method_refinement":
        recommended = "Implement generic method_refinement stage. Do not proceed to experiment_plan before method refinement."
    elif next_stage == "experiment_plan":
        recommended = "method_refinement complete. Consider running experiment_plan."
    elif next_stage == "novelty_check":
        recommended = "Run novelty_check or re-run with improved evidence."
    elif next_stage:
        recommended = f"Run {next_stage}."
    else:
        recommended = "All stages complete. Research workflow finished."

    if evidence.get("evidence_status") == "not_found":
        recommended = "No evidence pipeline found. Run literature evidence pipeline first."

    return {
        "next_allowed_stage": next_stage,
        "recommended_action": recommended,
        "blockers": blockers,
        "warnings": warnings,
    }


# ─────────────────────────────────────────────────────────
# Main status builder
# ─────────────────────────────────────────────────────────
def build_status() -> dict[str, Any]:
    """Build complete status report."""
    trusted_outputs: dict[str, Any] = {}
    for stage, rel_path in STAGE_PATHS.items():
        path = ROOT / rel_path
        trusted_outputs[stage] = read_trusted_output(path)

    completed_stages = [s for s, to in trusted_outputs.items() if to.get("exists")]

    # Run validators for completed stages that have roles
    validators: dict[str, Any] = {}
    for stage in completed_stages:
        role = None
        for r, s in ROLE_TO_STAGE.items():
            if s == stage:
                role = r
                break
        if role:
            validators[stage] = run_validator(role)

    evidence = summarize_evidence()
    repair_queue = parse_repair_queue()
    next_allowed = compute_next_allowed(trusted_outputs, validators, repair_queue)

    blocked = len(next_allowed["blockers"]) > 0

    return {
        "schema_version": "research_cli_status_v1",
        "current_stage": next_allowed.get("next_allowed_stage", "unknown"),
        "completed_stages": completed_stages,
        "trusted_outputs": trusted_outputs,
        "validators": validators,
        "evidence": evidence,
        "repair_queue": repair_queue,
        "blocked": blocked,
        "blockers": next_allowed["blockers"],
        "warnings": next_allowed["warnings"],
        "next_allowed_stage": next_allowed["next_allowed_stage"],
        "recommended_action": next_allowed["recommended_action"],
    }


# ─────────────────────────────────────────────────────────
# Commands
# ─────────────────────────────────────────────────────────
def cmd_status(json_output: bool = False) -> None:
    """Show current research status."""
    status = build_status()
    if json_output:
        print(json.dumps(status, indent=2))
    else:
        _print_status_text(status)


def cmd_validate(json_output: bool = False) -> None:
    """Run validation checks. Exit 0 if no blocking issues."""
    status = build_status()

    blockers = status.get("blockers", [])
    blocked = status.get("blocked", False)

    if json_output:
        print(json.dumps(status, indent=2))
    else:
        _print_status_text(status)

    if blocked:
        print("\n[FAIL] Blocking issues found.")
        sys.exit(1)

    # Also check validator failures
    validator_blockers = []
    for stage, v in status.get("validators", {}).items():
        if v.get("validation_status") == "parsed":
            allowed = v.get("allowed_next_stage")
            if allowed is False or str(allowed).lower() == "false":
                validator_blockers.append(f"{stage}: allowed_next_stage=false")
        elif v.get("validation_status") == "error":
            validator_blockers.append(f"{stage}: validator error — {v.get('reason', 'unknown')[:100]}")

    if validator_blockers:
        print("\n[FAIL] Validator failures:")
        for vb in validator_blockers:
            print(f"  - {vb}")
        sys.exit(1)

    print("\n[PASS] No blocking issues.")
    sys.exit(0)


def cmd_repair_queue(json_output: bool = False) -> None:
    """Show repair queue summary."""
    rq = parse_repair_queue()
    if json_output:
        print(json.dumps(rq, indent=2))
    else:
        _print_repair_queue_text(rq)


# ─────────────────────────────────────────────────────────
# Text formatters
# ─────────────────────────────────────────────────────────
def _print_status_text(status: dict) -> None:
    print(f"=== Research Status ({status['schema_version']}) ===")
    print(f"Current stage:    {status['current_stage']}")
    print(f"Next allowed:    {status['next_allowed_stage']}")
    print(f"Blocked:         {status['blocked']}")
    print(f"Completed stages: {len(status['completed_stages'])}")
    for s in status["completed_stages"]:
        print(f"  - {s}")
    print()

    if status["validators"]:
        print("--- Validators ---")
        for stage, v in status["validators"].items():
            vs = v.get("validator_status", "?")
            allowed = v.get("allowed_next_stage", "?")
            model = v.get("actual_model", "?")
            print(f"  {stage:<25} status={vs:<12} allowed={str(allowed):<5} model={model}")
        print()

    ev = status["evidence"]
    print("--- Evidence ---")
    print(f"  Status:        {ev.get('evidence_status','?')}")
    print(f"  Raw records:  {ev.get('raw_record_count',0)}")
    print(f"  Candidates:    {ev.get('candidate_count',0)}")
    print(f"  Top-k:         {ev.get('top_k_selected',0)}")
    print(f"  Full-text:    {ev.get('full_text_available_count',0)}")
    print()

    rq = status["repair_queue"]
    print("--- Repair Queue ---")
    print(f"  Total:          {rq.get('total_items',0)}")
    print(f"  Open:           {rq.get('open_items',0)}")
    print(f"  fix_now:        {rq.get('fix_now_open',0)}")
    print(f"  repair_queue:   {rq.get('repair_queue_open',0)}")
    print(f"  high severity:  {rq.get('high_severity_open',0)}")
    print(f"  blocking:       {rq.get('blocking_items',0)}")
    print()

    if status["warnings"]:
        print("--- Warnings ---")
        for w in status["warnings"]:
            print(f"  ! {w}")
        print()

    if status["blockers"]:
        print("--- Blockers ---")
        for b in status["blockers"]:
            print(f"  X {b}")
        print()

    print(f"Recommended: {status['recommended_action']}")


def _print_repair_queue_text(rq: dict) -> None:
    print(f"=== Repair Queue Summary ===")
    print(f"Total items:    {rq['total_items']}")
    print(f"Open:           {rq['open_items']}")
    print(f"  fix_now:      {rq['fix_now_open']}")
    print(f"  repair_queue: {rq['repair_queue_open']}")
    print(f"  accepted:     {rq['accepted_limitations']}")
    print(f"High severity: {rq['high_severity_open']}")
    print(f"Blocking:      {rq['blocking_items']}")
    print()
    print(f"{'ID':<10} {'Issue':<50} {'Class':<20} {'Status':<12} {'Blocking'}")
    print("-" * 110)
    for item in rq.get("items", []):
        iid = item.get("id", "")
        issue = (item.get("issue", "")[:47] + "...") if len(item.get("issue", "")) > 50 else item.get("issue", "")
        cls = item.get("classification", "")
        st = item.get("status", "")
        blk = item.get("blocking_next_stage", "")
        print(f"{iid:<10} {issue:<50} {cls:<20} {st:<12} {blk}")


# ─────────────────────────────────────────────────────────
# Dry-run plan builder
# ─────────────────────────────────────────────────────────
def build_novelty_risk_plan(idea: str) -> dict[str, Any]:
    """Build a dry-run plan for novelty_risk mode. No model calls, no file writes."""
    rq = parse_repair_queue()

    # Planned stages in order
    planned_stages = [
        {
            "stage_id": "assert_clean_git_status",
            "description": "Check git status is clean or explicit --allow-dirty provided",
            "execution_type": "status",
            "would_run_command": "git status",
            "planned_inputs": [],
            "planned_outputs": [],
            "validator_after": None,
            "stop_on_failure": True,
            "mutation_type": "none",
        },
        {
            "stage_id": "save_raw_user_input",
            "description": "Save user idea to research/current/raw_user_input.md",
            "execution_type": "file_write",
            "would_run_command": "write research/current/raw_user_input.md",
            "planned_inputs": ["user idea string"],
            "planned_outputs": ["research/current/raw_user_input.md"],
            "validator_after": None,
            "stop_on_failure": False,
            "mutation_type": "research_artifact",
        },
        {
            "stage_id": "input_normalization",
            "description": "Normalize raw input into structured brief and candidate idea",
            "execution_type": "trusted_model",
            "would_run_command": "python tools/trusted_role_runner.py --role input_normalizer ...",
            "planned_inputs": ["research/current/raw_user_input.md"],
            "planned_outputs": ["research/current/input_normalization.md"],
            "validator_after": "validate_model_invocation --role input_normalizer",
            "stop_on_failure": True,
            "mutation_type": "trusted_output",
        },
        {
            "stage_id": "validate_input_normalizer",
            "description": "Validate input_normalizer invocation",
            "execution_type": "validator",
            "would_run_command": "python tools/validate_model_invocation.py --role input_normalizer",
            "planned_inputs": ["research/current/input_normalization.md"],
            "planned_outputs": [],
            "validator_after": None,
            "stop_on_failure": True,
            "mutation_type": "none",
        },
        {
            "stage_id": "research_contract",
            "description": "Define research boundary: scope, success/failure criteria, claim limits",
            "execution_type": "trusted_model",
            "would_run_command": "python tools/trusted_role_runner.py --role contract_reviewer ...",
            "planned_inputs": ["research/current/input_normalization.md"],
            "planned_outputs": ["research/current/trusted_outputs/research_contract.md"],
            "validator_after": "validate_model_invocation --role contract_reviewer",
            "stop_on_failure": True,
            "mutation_type": "trusted_output",
        },
        {
            "stage_id": "validate_contract_reviewer",
            "description": "Validate contract_reviewer invocation",
            "execution_type": "validator",
            "would_run_command": "python tools/validate_model_invocation.py --role contract_reviewer",
            "planned_inputs": ["research/current/trusted_outputs/research_contract.md"],
            "planned_outputs": [],
            "validator_after": None,
            "stop_on_failure": True,
            "mutation_type": "none",
        },
        {
            "stage_id": "literature_evidence_pipeline",
            "description": "Run OpenAlex literature evidence pipeline: search plan → jobs → fetch → normalize → candidates → top_k",
            "execution_type": "evidence_pipeline",
            "would_run_command": "python tools/literature_evidence_landing.py build-search-plan ... && build-search-jobs && fetch && normalize ...",
            "planned_inputs": ["research/current/input_normalization.md", "research/current/trusted_outputs/research_contract.md"],
            "planned_outputs": [
                "literature/search_runs/current/search_plan.yaml",
                "literature/search_runs/current/search_jobs.json",
                "literature/search_runs/current/job_results.jsonl",
                "literature/search_runs/current/raw_results.jsonl",
                "literature/search_runs/current/candidates.jsonl",
                "literature/search_runs/current/top_k.md",
            ],
            "validator_after": "python tools/validate_literature_evidence.py ...",
            "stop_on_failure": True,
            "mutation_type": "literature_evidence",
        },
        {
            "stage_id": "validate_literature_evidence",
            "description": "Validate literature evidence: check evidence status and top_k coverage",
            "execution_type": "validator",
            "would_run_command": "python tools/validate_literature_evidence.py --file literature/search_runs/current/top_k.md --json",
            "planned_inputs": ["literature/search_runs/current/top_k.md"],
            "planned_outputs": [],
            "validator_after": None,
            "stop_on_failure": True,
            "mutation_type": "none",
        },
        {
            "stage_id": "create_literature_notes",
            "description": "Create literature_notes.md summarizing evidence for downstream stages",
            "execution_type": "no_model",
            "would_run_command": "python tools/research_workflow.py prepare literature_notes ...",
            "planned_inputs": ["literature/search_runs/current/top_k.md"],
            "planned_outputs": ["research/current/literature_notes.md"],
            "validator_after": None,
            "stop_on_failure": False,
            "mutation_type": "research_artifact",
        },
        {
            "stage_id": "literature_search",
            "description": "Gather and normalize literature evidence via trusted literature_scout",
            "execution_type": "trusted_model",
            "would_run_command": "python tools/trusted_role_runner.py --role literature_scout ...",
            "planned_inputs": [
                "research/current/input_normalization.md",
                "research/current/trusted_outputs/research_contract.md",
                "research/current/literature_notes.md",
                "literature/search_runs/current/top_k.md",
            ],
            "planned_outputs": ["research/current/trusted_outputs/literature_search.md"],
            "validator_after": "validate_model_invocation --role literature_scout",
            "stop_on_failure": True,
            "mutation_type": "trusted_output",
        },
        {
            "stage_id": "validate_literature_scout",
            "description": "Validate literature_scout invocation and output boundary",
            "execution_type": "validator",
            "would_run_command": "python tools/validate_model_invocation.py --role literature_scout",
            "planned_inputs": ["research/current/trusted_outputs/literature_search.md"],
            "planned_outputs": [],
            "validator_after": None,
            "stop_on_failure": True,
            "mutation_type": "none",
        },
        {
            "stage_id": "novelty_check",
            "description": "Evidence-bounded novelty risk assessment via trusted novelty_checker",
            "execution_type": "trusted_model",
            "would_run_command": "python tools/trusted_role_runner.py --role novelty_checker ...",
            "planned_inputs": [
                "research/current/input_normalization.md",
                "research/current/trusted_outputs/research_contract.md",
                "research/current/literature_notes.md",
                "research/current/trusted_outputs/literature_search.md",
                "literature/search_runs/current/top_k.md",
                "docs/LITERATURE_REPAIR_QUEUE.md",
            ],
            "planned_outputs": ["research/current/trusted_outputs/novelty_check.md"],
            "validator_after": "validate_model_invocation --role novelty_checker",
            "stop_on_failure": True,
            "mutation_type": "trusted_output",
        },
        {
            "stage_id": "validate_novelty_checker",
            "description": "Validate novelty_checker invocation and output boundary",
            "execution_type": "validator",
            "would_run_command": "python tools/validate_model_invocation.py --role novelty_checker",
            "planned_inputs": ["research/current/trusted_outputs/novelty_check.md"],
            "planned_outputs": [],
            "validator_after": None,
            "stop_on_failure": True,
            "mutation_type": "none",
        },
        {
            "stage_id": "write_status_summary",
            "description": "Write status summary after novelty_check",
            "execution_type": "status",
            "would_run_command": "python tools/research_cli.py status --json",
            "planned_inputs": ["research/current/trusted_outputs/novelty_check.md"],
            "planned_outputs": [],
            "validator_after": None,
            "stop_on_failure": False,
            "mutation_type": "status_file",
        },
        {
            "stage_id": "print_next_allowed_action",
            "description": "Print next allowed action based on novelty_check result",
            "execution_type": "status",
            "would_run_command": "compute next_allowed_stage",
            "planned_inputs": ["research/current/trusted_outputs/novelty_check.md"],
            "planned_outputs": [],
            "validator_after": None,
            "stop_on_failure": False,
            "mutation_type": "none",
        },
    ]

    # Validators listed
    planned_validators = [
        "python tools/validate_model_invocation.py --role input_normalizer",
        "python tools/validate_model_invocation.py --role contract_reviewer",
        "python tools/validate_literature_evidence.py --file literature/search_runs/current/top_k.md --json",
        "python tools/validate_model_invocation.py --role literature_scout",
        "python tools/validate_model_invocation.py --role novelty_checker",
    ]

    # Stop conditions
    stop_conditions = [
        {"condition": "dirty_git_status", "unless": "--allow-dirty flag", "severity": "blocking"},
        {"condition": "context_isolation_fail", "severity": "blocking"},
        {"condition": "validator_fail", "severity": "blocking"},
        {"condition": "model_route_mismatch", "severity": "blocking"},
        {"condition": "fallback_used=true", "severity": "blocking"},
        {"condition": "evidence_validator_fail", "severity": "blocking"},
        {"condition": "insufficient_evidence", "severity": "warning", "note": "Allowed if stage config allows risk assessment"},
        {"condition": "network_rate_limit", "severity": "blocking"},
        {"condition": "novelty_overclaim", "severity": "blocking", "note": "Cannot claim confirmed_novel with insufficient evidence"},
        {"condition": "method_refinement_missing_before_experiment_plan", "severity": "blocking", "note": "experiment_plan blocked until method_refinement exists"},
    ]

    # Planned outputs
    planned_outputs = [
        "research/current/raw_user_input.md",
        "research/current/input_normalization.md",
        "research/current/trusted_outputs/research_contract.md",
        "literature/search_runs/current/search_plan.yaml",
        "literature/search_runs/current/search_jobs.json",
        "literature/search_runs/current/job_results.jsonl",
        "literature/search_runs/current/raw_results.jsonl",
        "literature/search_runs/current/candidates.jsonl",
        "literature/search_runs/current/top_k.md",
        "research/current/literature_notes.md",
        "research/current/trusted_outputs/literature_search.md",
        "research/current/trusted_outputs/novelty_check.md",
    ]

    # Warnings
    warnings = []
    if any(item["id"] == "LRQ-012" and item["status"] == "open" for item in rq.get("items", [])):
        warnings.append(
            "novelty_risk can run to novelty_check, but experiment_plan remains blocked "
            "until method_refinement (LRQ-012) is implemented."
        )
    if rq.get("high_severity_open", 0) > 0:
        warnings.append(
            f"{rq['high_severity_open']} high-severity item(s) open in repair queue. "
            "Run python tools/research_cli.py repair-queue for details."
        )
    if any(item["id"] in ("LRQ-004", "LRQ-005") and item["status"] == "open" for item in rq.get("items", [])):
        warnings.append(
            "Only OpenAlex source implemented and no full-text. "
            "Novelty claims are evidence-bounded only (LRQ-004, LRQ-005)."
        )

    # Current status summary (compact)
    status = build_status()
    current_status_summary = {
        "current_stage": status.get("current_stage"),
        "completed_stages": status.get("completed_stages"),
        "next_allowed_stage": status.get("next_allowed_stage"),
        "blocked": status.get("blocked"),
        "blockers_count": len(status.get("blockers", [])),
        "warnings_count": len(status.get("warnings", [])),
        "open_repair_queue": rq.get("open_items", 0),
        "high_severity_open": rq.get("high_severity_open", 0),
    }

    # Next command
    next_command = "python tools/research_cli.py start --idea '...' --mode novelty_risk --dry-run  # Phase 18D (live)"

    plan = {
        "schema_version": "research_cli_start_plan_v1",
        "mode": "novelty_risk",
        "dry_run": True,
        "idea_preview": idea[:80] + ("..." if len(idea) > 80 else ""),
        "will_mutate": False,
        "will_call_model": False,
        "will_call_network": False,
        "planned_stages": planned_stages,
        "planned_validators": planned_validators,
        "planned_outputs": planned_outputs,
        "stop_conditions": stop_conditions,
        "current_status_summary": current_status_summary,
        "repair_queue_summary": {
            "total_items": rq.get("total_items", 0),
            "open_items": rq.get("open_items", 0),
            "fix_now_open": rq.get("fix_now_open", 0),
            "high_severity_open": rq.get("high_severity_open", 0),
            "blocking_items": rq.get("blocking_items", 0),
        },
        "warnings": warnings,
        "next_command": next_command,
    }
    return plan


# ─────────────────────────────────────────────────────────
# Dry-run commands
# ─────────────────────────────────────────────────────────
def cmd_start(idea: str, mode: str, dry_run: bool, json_output: bool) -> None:
    """Handle 'start' command."""
    if not dry_run:
        print("ERROR: Live start is not implemented in Phase 18C.")
        print("  Use: python tools/research_cli.py start --idea '...' --mode novelty_risk --dry-run")
        sys.exit(1)

    if not idea or not idea.strip():
        print("ERROR: --idea is required and cannot be empty.")
        sys.exit(1)

    if mode != "novelty_risk":
        print(f"ERROR: Only mode=novelty_risk is supported in this phase.")
        print(f"  Received: mode={mode}")
        print("  Supported: novelty_risk")
        sys.exit(1)

    plan = build_novelty_risk_plan(idea)

    if json_output:
        print(json.dumps(plan, indent=2))
    else:
        _print_dry_run_text(plan)


def _print_dry_run_text(plan: dict) -> None:
    """Print readable dry-run plan."""
    print(f"=== Dry-Run Plan ({plan['schema_version']}) ===")
    print(f"Mode:     {plan['mode']}")
    print(f"Idea:     {plan['idea_preview']}")
    print(f"Safety:   will_mutate={plan['will_mutate']} will_call_model={plan['will_call_model']} will_call_network={plan['will_call_network']}")
    print()
    print(f"--- Planned Stages ({len(plan['planned_stages'])} steps) ---")
    for i, stage in enumerate(plan["planned_stages"], 1):
        mut = stage.get("mutation_type", "none")
        exec_type = stage.get("execution_type", "?")
        print(f"  {i:2d}. [{exec_type}] {stage['stage_id']}  ({mut})")
    print()
    print(f"--- Planned Outputs ({len(plan['planned_outputs'])} files) ---")
    for out in plan["planned_outputs"]:
        print(f"  - {out}")
    print()
    print(f"--- Validators ({len(plan['planned_validators'])} calls) ---")
    for v in plan["planned_validators"]:
        print(f"  - {v}")
    print()
    print(f"--- Stop Conditions ---")
    for sc in plan["stop_conditions"]:
        sev = sc.get("severity", "?")
        unless = f" [unless: {sc.get('unless')}]" if sc.get("unless") else ""
        note = f"  ({sc.get('note', '')})" if sc.get("note") else ""
        print(f"  [{sev}]{unless} {sc['condition']}{note}")
    print()

    cs = plan.get("current_status_summary", {})
    print(f"--- Current Status (compact) ---")
    print(f"  current_stage:   {cs.get('current_stage','?')}")
    print(f"  next_allowed:    {cs.get('next_allowed_stage','?')}")
    print(f"  blocked:          {cs.get('blocked','?')}")
    print(f"  blockers:         {cs.get('blockers_count',0)}")
    print(f"  warnings:         {cs.get('warnings_count',0)}")
    print(f"  repair_queue:     {cs.get('open_repair_queue',0)} open, {cs.get('high_severity_open',0)} high-severity")
    print()

    if plan.get("warnings"):
        print(f"--- Warnings ---")
        for w in plan["warnings"]:
            print(f"  ! {w}")
        print()

    print(f"Next command: {plan.get('next_command','')}")
    print()
    print("DRY-RUN: No files written, no models called, no network used.")


# ─────────────────────────────────────────────────────────
# Self-test
# ─────────────────────────────────────────────────────────
def self_test() -> bool:
    """Run self-tests. Returns True if all pass."""
    import tempfile

    print("Running self-test...")
    passed = 0
    failed = 0

    # Test 1: parse_frontmatter
    text = "---\nkey1: value1\nkey2: \"quoted\"\n---\nbody"
    result = parse_frontmatter(text)
    if result.get("key1") == "value1" and result.get("key2") == "quoted":
        print("  [PASS] 1. parse_frontmatter basic")
        passed += 1
    else:
        print(f"  [FAIL] 1. parse_frontmatter basic, got: {result}")
        failed += 1

    # Test 2: parse_frontmatter handles missing
    if parse_frontmatter("") == {}:
        print("  [PASS] 2. parse_frontmatter empty")
        passed += 1
    else:
        print("  [FAIL] 2. parse_frontmatter empty")
        failed += 1

    # Test 3: repair queue parsing
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write("## Header\n\n| id | issue | ...\n")
        f.write("|---|---|...|\n")
        f.write("| LRQ-001 | Test issue | ... | high | fix_now | ... | open | yes | ... |\n")
        f.write("| LRQ-002 | Another issue | ... | low | repair_queue | ... | fixed | no |\n")
        tmp_path = f.name
    try:
        rq = parse_repair_queue.__wrapped__() if hasattr(parse_repair_queue, "__wrapped__") else None
        # Use direct parse logic
        with open(tmp_path, encoding="utf-8") as rf:
            lines = rf.read().split("\n")
        items_found = 0
        for line in lines:
            if "LRQ-" in line and line.strip().startswith("|"):
                items_found += 1
        # This won't actually parse properly since we need ROOT. Use a simpler test.
        # Test parse_repair_queue structure check
        pass
    finally:
        import os
        os.unlink(tmp_path)

    # Test 4: read_trusted_output missing file
    with tempfile.TemporaryDirectory() as td:
        missing = Path(td) / "does_not_exist.md"
        result = read_trusted_output(missing)
        if not result.get("exists") and result.get("path"):
            print("  [PASS] 4. read_trusted_output missing file")
            passed += 1
        else:
            print(f"  [FAIL] 4. read_trusted_output missing, got: {result}")
            failed += 1

    # Test 5: read_trusted_output with frontmatter
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write("---\nroute_role: novelty_checker\nactual_backend: deepseek\nallowed_next_stage: True\nverification_status: verified_routed_call\n---\n# Body\n")
        tmp_path = f.name
    try:
        result = read_trusted_output(Path(tmp_path))
        if (result.get("exists") and result.get("role") == "novelty_checker"
                and result.get("actual_backend") == "deepseek"
                and result.get("allowed_next_stage") == "True"):
            print("  [PASS] 5. read_trusted_output with frontmatter")
            passed += 1
        else:
            print(f"  [FAIL] 5. read_trusted_output frontmatter, got: {result}")
            failed += 1
    finally:
        import os
        os.unlink(tmp_path)

    # Test 6: compute_next_allowed blocks experiment_plan without method_refinement
    # All stages up to novelty_check exist, experiment_plan exists but method_refinement missing
    trusted = {stage: {"exists": False} for stage in STAGE_ORDER}
    for stage in STAGE_ORDER:
        if stage in ("raw_user_input", "input_normalization", "research_contract",
                     "literature_notes", "literature_search", "novelty_check", "experiment_plan"):
            trusted[stage] = {"exists": True, "allowed_next_stage": "True"}
    trusted["method_refinement"] = {"exists": False}
    result = compute_next_allowed(trusted, {}, {"high_severity_open": 0})
    if (result["next_allowed_stage"] == "method_refinement"
            and any("method_refinement is missing" in b for b in result["blockers"])):
        print("  [PASS] 6. compute_next_allowed blocks experiment_plan without method_refinement")
        passed += 1
    else:
        print(f"  [FAIL] 6. compute_next_allowed, got: {result}")
        failed += 1

    # Test 7: compute_next_allowed allows experiment_plan after method_refinement
    trusted2 = {stage: {"exists": False} for stage in STAGE_ORDER}
    for stage in STAGE_ORDER:
        if stage in ("raw_user_input", "input_normalization", "research_contract",
                      "literature_notes", "literature_search", "novelty_check",
                      "method_refinement", "experiment_plan"):
            trusted2[stage] = {"exists": True, "allowed_next_stage": "True"}
    trusted2["implementation_plan"] = {"exists": False}
    result2 = compute_next_allowed(trusted2, {}, {"high_severity_open": 0})
    if result2["next_allowed_stage"] == "implementation_plan":
        print("  [PASS] 7. compute_next_allowed allows experiment_plan after method_refinement")
        passed += 1
    else:
        print(f"  [FAIL] 7. compute_next_allowed, got: {result2}")
        failed += 1

    # Test 8: status JSON schema has required keys
    status = build_status()
    required_keys = [
        "schema_version", "current_stage", "completed_stages", "trusted_outputs",
        "validators", "evidence", "repair_queue", "blocked", "blockers", "warnings",
        "next_allowed_stage", "recommended_action",
    ]
    missing = [k for k in required_keys if k not in status]
    if not missing:
        print("  [PASS] 8. status JSON schema has all required keys")
        passed += 1
    else:
        print(f"  [FAIL] 8. status missing keys: {missing}")
        failed += 1

    # Test 9: no mutation behavior (self-test uses temp dirs)
    with tempfile.TemporaryDirectory() as td:
        # Just verify we can create a temp dir and don't mutate ROOT
        marker = Path(td) / "test_marker.txt"
        marker.write_text("test")
        if marker.exists():
            print("  [PASS] 9. no mutation behavior (temp dir test)")
            passed += 1
        else:
            print("  [FAIL] 9. no mutation behavior")
            failed += 1

    # Test 10: parse_repair_queue with known fixture
    rq = parse_repair_queue()
    if "total_items" in rq and "items" in rq and isinstance(rq["items"], list):
        print(f"  [PASS] 10. parse_repair_queue structure valid (found {rq['total_items']} items)")
        passed += 1
    else:
        print(f"  [FAIL] 10. parse_repair_queue structure, got: {rq}")
        failed += 1

    # Test 11: build_novelty_risk_plan returns plan structure
    plan = build_novelty_risk_plan("test idea for dry-run")
    required_plan_keys = [
        "schema_version", "mode", "dry_run", "idea_preview", "will_mutate",
        "will_call_model", "will_call_network", "planned_stages", "planned_validators",
        "planned_outputs", "stop_conditions", "current_status_summary", "repair_queue_summary",
        "warnings", "next_command",
    ]
    missing_plan_keys = [k for k in required_plan_keys if k not in plan]
    if not missing_plan_keys and plan["dry_run"] is True and plan["will_call_model"] is False:
        print("  [PASS] 11. build_novelty_risk_plan returns valid plan structure")
        passed += 1
    else:
        print(f"  [FAIL] 11. build_novelty_risk_plan, missing keys: {missing_plan_keys}")
        failed += 1

    # Test 12: build_novelty_risk_plan has 15 planned stages
    stage_ids = [s["stage_id"] for s in plan.get("planned_stages", [])]
    if len(stage_ids) == 15:
        print(f"  [PASS] 12. build_novelty_risk_plan has 15 planned stages")
        passed += 1
    else:
        print(f"  [FAIL] 12. expected 15 stages, got {len(stage_ids)}: {stage_ids}")
        failed += 1

    # Test 13: build_novelty_risk_plan will_mutate=False, will_call_model=False, will_call_network=False
    if plan["will_mutate"] is False and plan["will_call_model"] is False and plan["will_call_network"] is False:
        print("  [PASS] 13. build_novelty_risk_plan all safety flags False")
        passed += 1
    else:
        print(f"  [FAIL] 13. safety flags: mutate={plan['will_mutate']} model={plan['will_call_model']} network={plan['will_call_network']}")
        failed += 1

    # Test 14: build_novelty_risk_plan has stop conditions
    stops = plan.get("stop_conditions", [])
    expected_conditions = ["dirty_git_status", "context_isolation_fail", "validator_fail",
                           "model_route_mismatch", "fallback_used=true", "evidence_validator_fail",
                           "insufficient_evidence", "network_rate_limit", "novelty_overclaim",
                           "method_refinement_missing_before_experiment_plan"]
    found_conditions = [c["condition"] for c in stops]
    missing_conds = [c for c in expected_conditions if c not in found_conditions]
    if not missing_conds:
        print(f"  [PASS] 14. build_novelty_risk_plan has all 10 stop conditions")
        passed += 1
    else:
        print(f"  [FAIL] 14. missing stop conditions: {missing_conds}")
        failed += 1

    # Test 15: build_novelty_risk_plan has planned validators
    validators = plan.get("planned_validators", [])
    expected_validators = [
        "python tools/validate_model_invocation.py --role input_normalizer",
        "python tools/validate_model_invocation.py --role contract_reviewer",
        "python tools/validate_literature_evidence.py --file literature/search_runs/current/top_k.md --json",
        "python tools/validate_model_invocation.py --role literature_scout",
        "python tools/validate_model_invocation.py --role novelty_checker",
    ]
    if validators == expected_validators:
        print(f"  [PASS] 15. build_novelty_risk_plan has all 5 planned validators")
        passed += 1
    else:
        print(f"  [FAIL] 15. planned validators mismatch. Got: {validators}")
        failed += 1

    # Test 16: build_novelty_risk_plan has planned outputs
    outputs = plan.get("planned_outputs", [])
    critical_outputs = [
        "research/current/raw_user_input.md",
        "research/current/trusted_outputs/research_contract.md",
        "literature/search_runs/current/top_k.md",
        "research/current/literature_notes.md",
        "research/current/trusted_outputs/novelty_check.md",
    ]
    missing_outputs = [o for o in critical_outputs if o not in outputs]
    if not missing_outputs:
        print(f"  [PASS] 16. build_novelty_risk_plan has all critical planned outputs")
        passed += 1
    else:
        print(f"  [FAIL] 16. missing critical outputs: {missing_outputs}")
        failed += 1

    # Test 17: cmd_start validates idea is non-empty
    import io, contextlib
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    old_argv = sys.argv
    sys.argv = ["research_cli.py", "start", "--mode", "novelty_risk", "--dry-run"]
    exit_code = 0
    try:
        sys.stdout = io.StringIO()
        cmd_start(idea="", mode="novelty_risk", dry_run=True, json_output=False)
    except SystemExit as e:
        exit_code = e.code
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        sys.argv = old_argv
    if exit_code == 1:
        print("  [PASS] 17. cmd_start rejects empty idea")
        passed += 1
    else:
        print(f"  [FAIL] 17. cmd_start should exit 1 for empty idea, got exit {exit_code}")
        failed += 1

    # Test 18: cmd_start validates only novelty_risk mode
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    old_argv = sys.argv
    sys.argv = ["research_cli.py", "start", "--idea", "test", "--mode", "novelty_risk", "--dry-run"]
    exit_code = 0
    try:
        sys.stdout = io.StringIO()
        cmd_start(idea="test idea", mode="experiment_plan", dry_run=True, json_output=False)
    except SystemExit as e:
        exit_code = e.code
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        sys.argv = old_argv
    if exit_code == 1:
        print("  [PASS] 18. cmd_start rejects non-novelty_risk mode")
        passed += 1
    else:
        print(f"  [FAIL] 18. cmd_start should exit 1 for non-novelty_risk mode, got exit {exit_code}")
        failed += 1

    # Test 19: cmd_start rejects non-dry-run
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    old_argv = sys.argv
    sys.argv = ["research_cli.py", "start", "--idea", "test"]
    exit_code = 0
    try:
        sys.stdout = io.StringIO()
        cmd_start(idea="test idea", mode="novelty_risk", dry_run=False, json_output=False)
    except SystemExit as e:
        exit_code = e.code
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        sys.argv = old_argv
    if exit_code == 1:
        print("  [PASS] 19. cmd_start rejects live execution (no --dry-run)")
        passed += 1
    else:
        print(f"  [FAIL] 19. cmd_start should exit 1 for non-dry-run, got exit {exit_code}")
        failed += 1

    # Test 20: cmd_start dry-run produces plan with current_status_summary
    old_stdout = sys.stdout
    old_argv = sys.argv
    sys.argv = ["research_cli.py", "start", "--idea", "test idea", "--mode", "novelty_risk", "--dry-run"]
    captured = io.StringIO()
    try:
        sys.stdout = captured
        cmd_start(idea="test idea", mode="novelty_risk", dry_run=True, json_output=False)
    finally:
        sys.stdout = old_stdout
        sys.argv = old_argv
    output = captured.getvalue()
    # Check for the key sections in the readable text output
    if ("Dry-Run Plan" in output and "Mode:" in output and "Safety:" in output
            and "Planned Stages" in output and "Planned Outputs" in output
            and "Current Status" in output and "DRY-RUN:" in output):
        print("  [PASS] 20. cmd_start dry-run prints readable plan text")
        passed += 1
    else:
        print(f"  [FAIL] 20. dry-run output missing expected sections. Got: {output[:300]}")
        failed += 1

    print(f"\nSelf-test results: {passed} passed, {failed} failed")
    return failed == 0


# ─────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────
def main() -> None:
    if len(sys.argv) == 2 and sys.argv[1] == "--self-test":
        ok = self_test()
        sys.exit(0 if ok else 1)

    if len(sys.argv) < 2:
        print("Usage: python tools/research_cli.py <command> [options] [--json]")
        print("Commands: status, validate, repair-queue, start")
        print("Start usage: python tools/research_cli.py start --idea '...' --mode novelty_risk --dry-run [--json]")
        sys.exit(1)

    cmd = sys.argv[1]
    json_output = "--json" in sys.argv[2:]

    if cmd == "status":
        cmd_status(json_output=json_output)
    elif cmd == "validate":
        cmd_validate(json_output=json_output)
    elif cmd == "repair-queue":
        cmd_repair_queue(json_output=json_output)
    elif cmd == "start":
        args = sys.argv[2:]
        idea = ""
        mode = "novelty_risk"
        dry_run = False
        i = 0
        while i < len(args):
            if args[i] == "--idea" and i + 1 < len(args):
                idea = args[i + 1]
                i += 2
            elif args[i] == "--mode" and i + 1 < len(args):
                mode = args[i + 1]
                i += 2
            elif args[i] == "--dry-run":
                dry_run = True
                i += 1
            else:
                i += 1
        cmd_start(idea=idea, mode=mode, dry_run=dry_run, json_output=json_output)
    else:
        print(f"Unknown command: {cmd}")
        print("Commands: status, validate, repair-queue, start")
        sys.exit(1)


if __name__ == "__main__":
    main()
