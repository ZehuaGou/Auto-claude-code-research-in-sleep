# ARIS Research Workflow Controller
# Disallows external agents from directly invoking models or organizing prompts.
# All research flow must route through this controller.
#
# Usage:
#   python tools/research_workflow.py list-stages
#   python tools/research_workflow.py plan <stage> --config <yaml>
#   python tools/research_workflow.py prepare <stage> --config <yaml>
#   python tools/research_workflow.py run <stage> --config <yaml> [--dry-run]
#
# Workflow stages are defined in configs/workflows/<name>.yaml.
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import uuid
from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent.resolve()
TRUSTED_RUNNER = ROOT / "tools" / "trusted_role_runner.py"
MODEL_ROUTE = ROOT / "tools" / "model_route.py"


def list_stages(config_path: Path) -> None:
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    print("Available stages:")
    for name in cfg.get("stages", {}):
        stage = cfg["stages"][name]
        print(f"  {name:<25} # {stage.get('description', '')}")


def plan_stage(stage_name: str, config_path: Path) -> None:
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    stages = cfg.get("stages", {})
    if stage_name not in stages:
        print(f"ERROR: stage '{stage_name}' not found in config")
        sys.exit(1)

    stage = stages[stage_name]
    role = stage.get("role", "")

    # Resolve model route
    result = subprocess.run(
        [sys.executable, str(MODEL_ROUTE), role],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"ERROR: model_route failed for role '{role}'")
        sys.exit(1)

    route = json.loads(result.stdout)

    print(f"Stage:          {stage_name}")
    print(f"Description:    {stage.get('description', '')}")
    print(f"Role:           {role}")
    print(f"Output:         {stage.get('output_file', '(none)')}")
    print(f"Require validate: {stage.get('require_validate', False)}")
    print()
    print(f"Provider:       {route.get('provider','')}")
    print(f"Backend:        {route.get('backend_type','')}")
    print(f"Model:          {route.get('model','')}")
    print(f"fallback_used:  {route.get('fallback_used', True)}")
    print()

    allowed = stage.get("allowed_input_files", [])
    print(f"Allowed input files ({len(allowed)}):")
    for f in allowed:
        exists = Path(ROOT / f).exists()
        status = "EXISTS" if exists else "MISSING"
        print(f"  [{status}] {f}")

    print()
    forbidden = stage.get("forbidden_context", [])
    print(f"Forbidden context ({len(forbidden)} items):")
    for item in forbidden:
        print(f"  - {item}")

    if route.get("fallback_used"):
        print()
        print("ERROR: fallback_used=true — stopping before any model call")
        sys.exit(1)


CONTEXT_CHECK = ROOT / "tools" / "context_isolation_check.py"


VALIDATOR = ROOT / "tools" / "validate_literature_evidence.py"


def _run_stage_prechecks(stage_name: str, config_path: Path) -> None:
    """Run stage-specific prechecks before any model call. Currently only for novelty_check."""
    if stage_name != "novelty_check":
        return

    result = subprocess.run(
        [sys.executable, str(VALIDATOR), "--file", "literature/search_runs/current/top_k.md", "--json"],
        capture_output=True, text=True
    )

    status = "unknown"
    message = ""
    try:
        if result.returncode in (0, 1):
            # Even exit 1 has JSON body
            data = json.loads(result.stdout)
            status = data.get("status", "unknown")
            message = data.get("message", "")
    except Exception:
        pass

    if status == "valid":
        return  # passed

    # Block for any non-valid status
    print()
    print("=" * 60)
    print("LITERATURE EVIDENCE PRECHECK FAILED for novelty_check")
    print("=" * 60)
    print(f"status: {status}")
    print(f"reason: {message}")
    print()
    if status == "template_only":
        print("top_k.md is template_only and cannot support confirmed_novel.")
        print("Fix: populate literature/search_runs/current/top_k.md with validated evidence,")
        print("     then rerun: python tools/validate_literature_evidence.py --json")
    elif status == "insufficient_evidence":
        print("Evidence is insufficient — confirmed_novel is not permitted.")
        print("Fix: improve literature evidence quality and coverage,")
        print("     then rerun: python tools/validate_literature_evidence.py --json")
    elif status == "valid_with_gaps":
        print("Evidence is valid_with_gaps.")
        print("Manual confirmation for valid_with_gaps is not implemented yet.")
        print("Stopping before novelty_check to avoid false confirmed_novel.")
    else:
        print("Evidence validator failed or returned an unknown status.")
        print("Fix: run manually: python tools/validate_literature_evidence.py --json")
    print()
    print("ERROR: LITERATURE EVIDENCE PRECHECK FAILED — stopping before model call.")
    sys.exit(1)


def _load_stage(stage_name: str, config_path: Path):
    """Load stage config, resolve route, check inputs. Returns (stage, route)."""
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    stages = cfg.get("stages", {})
    if stage_name not in stages:
        print(f"ERROR: stage '{stage_name}' not found in config")
        sys.exit(1)

    stage = stages[stage_name]
    role = stage.get("role", "")
    allowed_inputs = stage.get("allowed_input_files", [])
    forbidden_context = stage.get("forbidden_context", [])

    # Check for missing input files before doing anything
    missing = [f for f in allowed_inputs if not (Path(ROOT) / f).exists()]
    if missing:
        print(f"ERROR: {len(missing)} required input file(s) missing — aborting before model call:")
        for f in missing:
            print(f"  MISSING: {f}")
        print()
        print("The workflow correctly blocked a call without required inputs.")
        print("Fix: provide the missing files or update allowed_input_files in the config.")
        sys.exit(1)

    # Resolve model route
    result = subprocess.run(
        [sys.executable, str(MODEL_ROUTE), role],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"ERROR: model_route failed for role '{role}'")
        sys.exit(1)

    route = json.loads(result.stdout)

    if route.get("fallback_used"):
        print(f"ERROR: fallback_used=true for role '{role}' — stopping before model call")
        sys.exit(1)

    return stage, route


def prepare_stage(stage_name: str, config_path: Path) -> None:
    """Generate context manifest and input file, print the trusted_role_runner command.

    This is the prepare step: checks inputs, builds manifest, writes files.
    Does NOT call the model — the external agent runs the printed command.
    """
    stage, route = _load_stage(stage_name, config_path)

    role = stage.get("role", "")
    output_file = stage.get("output_file", "")
    allowed_inputs = stage.get("allowed_input_files", [])
    forbidden_context = stage.get("forbidden_context", [])
    require_validate = stage.get("require_validate", False)

    # Run stage-specific prechecks (e.g. literature evidence precheck for novelty_check)
    _run_stage_prechecks(stage_name, config_path)

    provider = route.get("provider", "")
    backend = route.get("backend_type", "")

    print(f"STAGE: {stage_name}")
    print(f"role: {role}")
    print(f"provider: {provider}")
    print(f"backend: {backend}")
    print(f"model: {route.get('model','')}")
    print(f"require_validate: {require_validate}")
    print(f"output: {output_file}")
    print()

    # Build context manifest
    input_content = ""
    for f in allowed_inputs:
        p = Path(ROOT) / f
        if p.exists():
            input_content += p.read_text(errors="ignore")

    context_hash = hashlib.sha256(input_content.encode()).hexdigest()
    task_id = f"wf_{stage_name}_{uuid.uuid4().hex[:8]}"

    context_manifest = {
        "isolation_mode": "context_manifest",
        "task_id": task_id,
        "allowed_input_files": [str(Path(f)) for f in allowed_inputs],
        "forbidden_context": forbidden_context,
        "forbidden_context_checked": True,
        "context_hash": context_hash,
        "source_boundary": f"workflow_{stage_name}_minimal_allowed_inputs_only",
        "contamination_scan_status": "pending"
    }

    manifest_path = Path(ROOT) / "tmp" / f"wf_{stage_name}_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(context_manifest, indent=2), encoding="utf-8")
    print(f"Context manifest written: {manifest_path}")

    # Build input.md from allowed inputs
    input_path = Path(ROOT) / "tmp" / f"wf_{stage_name}_input.md"
    input_lines = []
    for f in allowed_inputs:
        p = Path(ROOT) / f
        if p.exists():
            input_lines.append(f"# File: {f}\n")
            input_lines.append(p.read_text(errors="ignore"))
            input_lines.append("\n---\n")
    input_path.write_text("\n".join(input_lines), encoding="utf-8")
    print(f"Input written: {input_path}")

    # Run context isolation check
    print()
    print("Running context isolation check...")
    check_result = subprocess.run(
        [sys.executable, str(CONTEXT_CHECK), "--manifest", str(manifest_path), "--input", str(input_path)],
        capture_output=True, text=True
    )
    check_output = json.loads(check_result.stdout)

    if check_output.get("status") == "PASS":
        context_manifest["contamination_scan_status"] = "checked"
        manifest_path.write_text(json.dumps(context_manifest, indent=2), encoding="utf-8")
        print(f"  contamination_scan_status: checked")
    else:
        context_manifest["contamination_scan_status"] = "failed"
        context_manifest["contamination_fail_reason"] = check_output.get("reason", "")
        manifest_path.write_text(json.dumps(context_manifest, indent=2), encoding="utf-8")
        print(f"  contamination_scan_status: failed")
        print(f"  Reason: {check_output.get('reason', '')}")
        if check_output.get("forbidden_hits"):
            print(f"  Forbidden hits: {check_output['forbidden_hits']}")
        print()
        print("ERROR: Context isolation check FAILED — stopping before model call.")
        print("The input file contains forbidden context or unexpected file references.")
        print("Fix the input or update allowed_input_files in the workflow config.")
        sys.exit(1)

    # Generate output path
    if output_file:
        output_path = Path(ROOT) / output_file
        output_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        output_path = Path(ROOT) / "tmp" / f"wf_{stage_name}_output.md"

    # Print the trusted_role_runner command
    is_codex = (provider == "codex" and backend == "mcp")

    print()
    if is_codex:
        print("CODEX MCP HANDOFF REQUIRED")
        print("The outer Agent must call mcp__codex__codex directly with the prompt")
        print("from the ledger entry, then call --complete-external-mcp.")
        print()
        cmd = (
            f"python tools/trusted_role_runner.py "
            f"--role {role} "
            f"--input {input_path} "
            f"--output {output_path} "
            f"--context-manifest {manifest_path} "
            f"--prepare-external-mcp "
            f"--require-codex-thread"
        )
    else:
        cmd = (
            f"python tools/trusted_role_runner.py "
            f"--role {role} "
            f"--input {input_path} "
            f"--output {output_path} "
            f"--context-manifest {manifest_path}"
        )

    print("TRUSTED_ROLE_RUNNER COMMAND:")
    print(f"  {cmd}")
    print()
    print("Execute the above command to call the model. After completion,")
    print("run: python tools/validate_model_invocation.py --role {role} --max-age-hours 1")


def run_stage(stage_name: str, config_path: Path, dry_run: bool) -> None:
    """Run a stage. --dry-run shows plan without writing files."""
    stage, route = _load_stage(stage_name, config_path)

    role = stage.get("role", "")
    output_file = stage.get("output_file", "")
    allowed_inputs = stage.get("allowed_input_files", [])
    require_validate = stage.get("require_validate", False)

    provider = route.get("provider", "")
    backend = route.get("backend_type", "")

    print(f"STAGE: {stage_name}")
    print(f"role: {role}")
    print(f"provider: {provider}")
    print(f"backend: {backend}")
    print(f"model: {route.get('model','')}")
    print(f"dry_run: {dry_run}")
    print(f"require_validate: {require_validate}")
    print(f"output: {output_file}")
    print()

    if dry_run:
        # dry-run: just show what would happen, no files written
        allowed = stage.get("allowed_input_files", [])
        print(f"Allowed input files ({len(allowed)}):")
        for f in allowed:
            exists = Path(ROOT / f).exists()
            status = "EXISTS" if exists else "MISSING"
            print(f"  [{status}] {f}")
        print()
        print("DRY-RUN: no manifest written, no model called.")
        return

    # Real run: delegate to prepare (writes files + prints command)
    print("For real execution, use: python tools/research_workflow.py prepare <stage>")
    print("Then execute the printed command.")
    print()
    print("This command (run without --dry-run) currently delegates to prepare.")
    print()
    prepare_stage(stage_name, config_path)


def main():
    parser = argparse.ArgumentParser(description="ARIS Research Workflow Controller")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list-stages", help="List all stages in the default workflow")

    p_plan = sub.add_parser("plan", help="Show plan for a stage (no files written)")
    p_plan.add_argument("stage", help="Stage name")
    p_plan.add_argument("--config", default="configs/workflows/research_default.yaml",
                        help="Workflow config file")

    p_prepare = sub.add_parser("prepare", help="Prepare stage: check inputs, write manifest+input, print command")
    p_prepare.add_argument("stage", help="Stage name")
    p_prepare.add_argument("--config", default="configs/workflows/research_default.yaml",
                            help="Workflow config file")

    p_run = sub.add_parser("run", help="Run a stage (use --dry-run to test without writing files)")
    p_run.add_argument("stage", help="Stage name")
    p_run.add_argument("--config", default="configs/workflows/research_default.yaml",
                       help="Workflow config file")
    p_run.add_argument("--dry-run", action="store_true",
                       help="Print plan but do not write any files")

    args = parser.parse_args()

    config_path = Path(ROOT / args.config) if hasattr(args, 'config') else Path(ROOT / "configs/workflows/research_default.yaml")

    if args.command == "list-stages":
        list_stages(config_path)
    elif args.command == "plan":
        plan_stage(args.stage, config_path)
    elif args.command == "prepare":
        prepare_stage(args.stage, config_path)
    elif args.command == "run":
        run_stage(args.stage, config_path, args.dry_run)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()