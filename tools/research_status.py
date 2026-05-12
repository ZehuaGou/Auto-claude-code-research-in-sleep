#!/usr/bin/env python3
"""
ARIS Trusted Research Workflow Status Viewer.

Reads configs/workflows/research_default.yaml and artifact headers to report
the current state of each workflow stage.

Usage:
    python tools/research_status.py
    python tools/research_status.py --config configs/workflows/research_default.yaml
    python tools/research_status.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

TOOLS_DIR = Path(__file__).parent.resolve()
ROOT = TOOLS_DIR.parent.resolve()


def load_workflow_config(config_path: Path) -> dict:
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def read_artifact_header(output_path: Path) -> dict:
    """Read the YAML-like artifact header from the first --- block.

    Only accepts headers where the very first line of the file is ---.
    This prevents plain markdown section dividers from being misidentified.
    """
    if not output_path.exists():
        return {}

    try:
        lines = output_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return {}

    # First line must be ---
    if not lines or lines[0].strip() != "---":
        return {}

    # Find the closing --- starting from line 2
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return {}

    header_text = "\n".join(lines[1:end_idx]).strip()
    if not header_text:
        return {}

    # Parse as YAML
    try:
        import io
        return yaml.safe_load(io.StringIO(header_text)) or {}
    except Exception:
        return {}


def get_field(header: dict, *keys, default=None):
    """Try multiple keys, return first match or default."""
    for k in keys:
        if k in header and header[k] not in (None, "", False):
            return header[k]
    return default


def stage_status(stage_name: str, stage_cfg: dict) -> dict:
    """Compute status for a single stage."""
    output_file = stage_cfg.get("output_file", "")
    allowed_inputs = stage_cfg.get("allowed_input_files", [])
    role = stage_cfg.get("role", "unknown")

    # Check which inputs are missing
    missing_inputs = []
    present_inputs = []
    for inp in allowed_inputs:
        p = Path(ROOT / inp)
        if p.exists():
            present_inputs.append(inp)
        else:
            missing_inputs.append(inp)

    # Check if output exists
    output_path = Path(ROOT / output_file) if output_file else None
    output_exists = output_path is not None and output_path.exists()

    # Read artifact header if output exists
    header = {}
    header_missing = False
    if output_exists:
        header = read_artifact_header(output_path)
        if not header:
            header_missing = True

    # Determine status
    if not output_exists and missing_inputs:
        status = "blocked_missing_inputs"
    elif not output_exists and not missing_inputs:
        status = "ready_to_prepare"
    elif output_exists and header_missing:
        status = "untrusted_output_missing_header"
    elif output_exists:
        verif = get_field(header, "verification_status", default="")
        allowed_next = get_field(header, "allowed_next_stage", default=False)
        # Treat both verified_routed_call and verified_with_fallback as OK
        if verif not in ("verified_routed_call", "verified_with_fallback"):
            status = "output_unverified"
        elif not allowed_next:
            status = "blocked_not_allowed_next_stage"
        else:
            status = "completed_trusted"
    else:
        status = "unknown"

    # Gather header fields
    if output_exists and header:
        ledger_call_id = get_field(header, "ledger_call_id", "call_id", default="")
        actual_backend = get_field(header, "actual_backend", default="")
        actual_model = get_field(header, "actual_model", default="")
        fallback_used = get_field(header, "fallback_used", default=False)
        verification_status = get_field(header, "verification_status", default="")
        contamination_scan_status = get_field(header, "contamination_scan_status", default="")
        impl_source = get_field(header, "implementation_source", default="")
        allowed_next = get_field(header, "allowed_next_stage", default=False)
    else:
        ledger_call_id = ""
        actual_backend = ""
        actual_model = ""
        fallback_used = False
        verification_status = ""
        contamination_scan_status = ""
        impl_source = ""
        allowed_next = False

    return {
        "stage": stage_name,
        "role": role,
        "status": status,
        "output_file": output_file,
        "output_exists": output_exists,
        "header_missing": header_missing if output_exists else False,
        "present_inputs": present_inputs,
        "missing_inputs": missing_inputs,
        "ledger_call_id": ledger_call_id,
        "actual_backend": actual_backend,
        "actual_model": actual_model,
        "fallback_used": fallback_used,
        "verification_status": verification_status,
        "contamination_scan_status": contamination_scan_status,
        "implementation_source": impl_source,
        "allowed_next_stage": allowed_next,
    }


def recommended_next_command(stages: list[dict]) -> str:
    """Find the first non-completed stage and suggest next action."""
    for s in stages:
        st = s["status"]
        if st == "blocked_missing_inputs":
            missing = s["missing_inputs"]
            return (
                f"blocked_missing_inputs — missing: {', '.join(missing)}. "
                "Create or place these files before running prepare."
            )
        elif st == "ready_to_prepare":
            return (
                f"ready_to_prepare — run:\n"
                f"  python tools/research_workflow.py prepare {s['stage']}"
            )
        elif st in ("untrusted_output_missing_header", "output_unverified", "blocked_not_allowed_next_stage"):
            output = s["output_file"]
            return (
                f"{st} — check {output} and re-run "
                f"validate_model_invocation before continuing."
            )
    return "workflow_ready_for_next_phase"


def format_markdown(stages: list[dict]) -> str:
    lines = ["# Trusted Research Workflow Status\n"]
    lines.append(f"{'Stage':<25} {'Role':<30} {'Status':<35} {'Output':<50}")
    lines.append("-" * 145)

    for s in stages:
        stage = s["stage"]
        role = s["role"]
        status = s["status"]
        output = s["output_file"] or "(none)"
        # Truncate output for display
        if len(output) > 48:
            output = "..." + output[-45:]
        lines.append(f"{stage:<25} {role:<30} {status:<35} {output:<50}")

    lines.append("")
    lines.append("## Missing Inputs\n")
    has_missing = False
    for s in stages:
        if s["missing_inputs"]:
            lines.append(f"- **{s['stage']}**: {', '.join(s['missing_inputs'])}")
            has_missing = True
    if not has_missing:
        lines.append("(none)")

    lines.append("")
    lines.append("## Trusted Output Verification\n")
    for s in stages:
        if s["output_exists"]:
            verif = s["verification_status"] or "(none)"
            allowed = s["allowed_next_stage"]
            backend = s["actual_backend"] or "(none)"
            model = s["actual_model"] or "(none)"
            ledger = s["ledger_call_id"] or "(none)"
            header_note = " [MISSING HEADER]" if s["header_missing"] else ""
            lines.append(
                f"- **{s['stage']}**: "
                f"verif={verif}, allowed_next={allowed}, "
                f"backend={backend}, model={model}, ledger={ledger}{header_note}"
            )

    lines.append("")
    lines.append("## Recommended Next Action\n")
    lines.append(f"```\n{recommended_next_command(stages)}\n```")

    return "\n".join(lines)


def format_json(stages: list[dict]) -> str:
    output = {
        "stages": stages,
        "recommended_next": recommended_next_command(stages),
    }
    return json.dumps(output, indent=2)


def main():
    parser = argparse.ArgumentParser(description="ARIS Trusted Research Workflow Status Viewer")
    parser.add_argument(
        "--config",
        default="configs/workflows/research_default.yaml",
        help="Path to workflow config YAML",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON instead of markdown",
    )
    args = parser.parse_args()

    config_path = Path(ROOT / args.config)
    if not config_path.exists():
        print(f"ERROR: config not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    try:
        cfg = load_workflow_config(config_path)
    except Exception as e:
        print(f"ERROR: failed to parse config: {e}", file=sys.stderr)
        sys.exit(1)

    stages_cfg = cfg.get("stages", {})
    stage_names = list(stages_cfg.keys())

    # Preserve order from config
    stages = []
    for name in stage_names:
        stages.append(stage_status(name, stages_cfg[name]))

    if args.json:
        print(format_json(stages))
    else:
        print(format_markdown(stages))


if __name__ == "__main__":
    main()
