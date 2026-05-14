"""Slash command adapter — Agent-facing parser for user-facing slash commands.

Maps user slash commands to underlying research_cli plans.
No model calls, no trusted runner execution, no trusted_outputs changes.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


# ---- Supported commands and their mappings ----

COMMAND_MAP = {
    "research-intake": {
        "description": "输入研究方向和约束",
        "maps_to": "research_cli_start",
        "internal_stages": ["raw_user_input", "input_normalization", "brief_generation", "candidate_idea_extraction", "payload_parsing"],
        "flags": [],
    },
    "literature-intake": {
        "description": "文献调研与领域理解",
        "maps_to": "continue_literature_search",
        "internal_stages": ["query_planning", "multi_source_search", "dedup_ranking", "top_k_selection", "full_text_acquisition", "full_text_review", "evidence_map"],
        "flags": [],
    },
    "idea-synthesis": {
        "description": "创新点生成",
        "maps_to": "continue_idea_pivot",
        "internal_stages": ["idea_discovery", "idea_pivot", "transfer_hypothesis_generation", "contribution_chain_construction"],
        "flags": ["--num-candidates"],
    },
    "idea-audit": {
        "description": "创新点验证、查新与研究边界锁定",
        "maps_to": "continue_novelty_check",
        "internal_stages": ["novelty_check", "transfer_check", "method_refinement", "research_contract"],
        "flags": [],
    },
    "experiment": {
        "description": "实验与结果分析",
        "maps_to": "experiment_plan",
        "internal_stages": ["experiment_plan", "implementation_plan", "experiment_bridge", "code_review", "lightweight_experiment", "full_experiment", "result_judge", "claim_boundary_update"],
        "flags": ["--mode"],
        "modes": ["lightweight", "full", "analyze", "revise"],
    },
    "paper-writing": {
        "description": "论文撰写",
        "maps_to": "paper_writing",
        "internal_stages": ["paper_outline", "contribution_framing", "related_work", "method_writing", "experiment_writing", "limitation_writing", "auto_review_loop"],
        "flags": [],
    },
    "status": {
        "description": "显示当前研究状态",
        "maps_to": "research_cli_status",
        "internal_stages": [],
        "flags": [],
    },
}


# ---- Parser ----

def parse_slash_command(input_text: str) -> dict:
    """Parse a slash command string into structured components.

    Returns:
        {
            "command": str,
            "payload": str,
            "flags": dict,
            "raw": str,
            "valid": bool,
            "error": str | None,
        }
    """
    raw = input_text.strip()
    if not raw.startswith("/"):
        return {"command": "", "payload": "", "flags": {}, "raw": raw, "valid": False, "error": "must start with /"}

    # Extract command name (before first space or quote)
    parts = raw[1:].split(None, 1)
    if not parts:
        return {"command": "", "payload": "", "flags": {}, "raw": raw, "valid": False, "error": "empty command"}

    command = parts[0].lower()
    rest = parts[1] if len(parts) > 1 else ""

    if command not in COMMAND_MAP:
        return {"command": command, "payload": rest, "flags": {}, "raw": raw, "valid": False, "error": f"unknown command: /{command}"}

    # Parse quoted payload and flags
    payload, flags = _extract_payload_and_flags(rest)

    return {"command": command, "payload": payload, "flags": flags, "raw": raw, "valid": True, "error": None}


def _extract_payload_and_flags(text: str) -> tuple[str, dict]:
    """Extract quoted payload and --flag value pairs from text."""
    payload = ""
    flags = {}

    # Try to extract quoted payload
    m = re.match(r'"([^"]*)"', text)
    if m:
        payload = m.group(1)
        remainder = text[m.end():].strip()
    elif text.startswith("'"):
        m = re.match(r"'([^']*)'", text)
        if m:
            payload = m.group(1)
            remainder = text[m.end():].strip()
        else:
            remainder = text
    else:
        # No quotes — everything before first --flag is payload
        flag_match = re.search(r'\s+--', text)
        if flag_match:
            payload = text[:flag_match.start()].strip()
            remainder = text[flag_match.start():].strip()
        else:
            payload = text.strip()
            remainder = ""

    # Parse --flag value pairs
    flag_pattern = re.findall(r'--(\S+)(?:\s+(\S+))?', remainder)
    for name, value in flag_pattern:
        flags[name] = value if value else "true"

    return payload, flags


# ---- Payload persistence ----

def save_payload(command: str, payload: str, output_dir: Path) -> Path:
    """Save command payload to a markdown file. Returns the file path."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{command.replace('-', '_')}.md"
    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / filename

    content = f"""---
command: /{command}
timestamp: {datetime.now(timezone.utc).isoformat()}
raw_payload: |
  {payload}
---

# Command Payload: /{command}

## User Input

{payload}

## Parsed Fields

- command: /{command}
- timestamp: {datetime.now(timezone.utc).isoformat()}
"""
    filepath.write_text(content, encoding="utf-8")
    return filepath


# ---- Plan generation ----

def generate_plan(parsed: dict, run_dir: Path | None = None) -> dict:
    """Generate a structured plan from a parsed slash command.

    Returns a plan dict with command info, mapped CLI action, and status.
    Does NOT execute anything.
    """
    if not parsed["valid"]:
        return {
            "status": "FAIL",
            "command": parsed["command"],
            "error": parsed["error"],
            "raw": parsed["raw"],
        }

    command = parsed["command"]
    payload = parsed["payload"]
    flags = parsed["flags"]
    spec = COMMAND_MAP[command]

    plan = {
        "status": "PASS",
        "command": f"/{command}",
        "description": spec["description"],
        "payload": payload,
        "flags": flags,
        "maps_to": spec["maps_to"],
        "internal_stages": spec["internal_stages"],
        "dry_run": True,
    }

    # Generate specific CLI action based on command
    if command == "research-intake":
        plan["cli_action"] = {
            "command": "python tools/research_cli.py start",
            "args": ["--idea", payload, "--mode", "novelty_risk", "--dry-run"],
            "description": "Start a new research workflow with the given idea",
        }
    elif command == "literature-intake":
        plan["cli_action"] = {
            "command": "python tools/research_cli.py continue",
            "args": ["--stage", "literature_search", "--dry-run"],
            "description": "Continue to literature search stage",
        }
    elif command == "idea-synthesis":
        num_candidates = flags.get("num-candidates", "5")
        plan["cli_action"] = {
            "command": "python tools/research_cli.py continue",
            "args": ["--stage", "idea_pivot", "--dry-run"],
            "description": f"Generate {num_candidates} candidate ideas via idea pivot",
        }
    elif command == "idea-audit":
        plan["cli_action"] = {
            "command": "python tools/research_cli.py continue",
            "args": ["--stage", "novelty_check", "--dry-run"],
            "description": "Run novelty check and method refinement",
        }
    elif command == "experiment":
        mode = flags.get("mode", "lightweight")
        if mode not in spec.get("modes", []):
            plan["status"] = "FAIL"
            plan["error"] = f"invalid mode '{mode}'; valid modes: {spec['modes']}"
            return plan
        plan["cli_action"] = {
            "command": "python tools/research_cli.py continue",
            "args": ["--stage", "experiment_plan", "--dry-run"],
            "description": f"Run experiment plan in '{mode}' mode",
            "mode": mode,
        }
        if mode == "lightweight":
            plan["note"] = "Lightweight mode: quick signal check, small data, small model"
        elif mode == "full":
            plan["note"] = "Full mode: complete baseline, ablation, robustness"
        elif mode == "analyze":
            plan["note"] = "Analyze mode: review existing results, determine next action"
        elif mode == "revise":
            plan["note"] = "Revise mode: adjust method based on failure analysis"
    elif command == "paper-writing":
        plan["cli_action"] = {
            "command": "python tools/research_cli.py continue",
            "args": ["--stage", "paper_writing", "--dry-run"],
            "description": "Write paper based on verified results",
        }
        plan["note"] = "Paper writing requires verified experiment results and approved claim boundary"
    elif command == "status":
        plan["cli_action"] = {
            "command": "python tools/research_cli.py status",
            "args": [],
            "description": "Display current research status",
        }
        plan["note"] = flags.get("note", "")

    # If command is not yet fully implemented, mark it
    plan_only = {"idea-synthesis", "experiment", "paper-writing"}
    if command in plan_only:
        plan["implementation_status"] = "plan_only"
        plan["note"] = plan.get("note", "") + " [plan_only — generates execution plan, no live execution]"

    return plan


# ---- Self-test ----

def _self_test() -> bool:
    """Run self-tests for the slash command adapter."""
    tests_passed = 0
    tests_failed = 0

    def check(name: str, condition: bool, detail: str = ""):
        nonlocal tests_passed, tests_failed
        if condition:
            print(f"  [PASS] {name}")
            tests_passed += 1
        else:
            print(f"  [FAIL] {name} — {detail}")
            tests_failed += 1

    # Test 1: Parse quoted payload
    p = parse_slash_command('/research-intake "我想做时间序列异常检测"')
    check("1. parse quoted payload", p["valid"] and p["command"] == "research-intake" and p["payload"] == "我想做时间序列异常检测",
          f"got command={p['command']}, payload={p['payload']}")

    # Test 2: Parse flags
    p = parse_slash_command('/experiment "先做轻量实验" --mode lightweight')
    check("2. parse flags", p["valid"] and p["flags"].get("mode") == "lightweight",
          f"got flags={p['flags']}")

    # Test 3: Reject unknown command
    p = parse_slash_command('/unknown-command "test"')
    check("3. reject unknown command", not p["valid"] and "unknown" in (p["error"] or ""),
          f"got valid={p['valid']}, error={p['error']}")

    # Test 4: Status command
    p = parse_slash_command('/status')
    check("4. status command", p["valid"] and p["command"] == "status" and p["payload"] == "",
          f"got command={p['command']}, payload={p['payload']}")

    # Test 5: Status with note
    p = parse_slash_command('/status "只告诉我当前卡在哪里"')
    check("5. status with note", p["valid"] and p["payload"] == "只告诉我当前卡在哪里",
          f"got payload={p['payload']}")

    # Test 6: Experiment lightweight mode
    p = parse_slash_command('/experiment "先做轻量实验" --mode lightweight')
    plan = generate_plan(p)
    check("6. experiment lightweight mode", plan["status"] == "PASS" and plan["flags"].get("mode") == "lightweight",
          f"got status={plan['status']}, mode={plan['flags'].get('mode')}")

    # Test 7: Experiment invalid mode
    p = parse_slash_command('/experiment "test" --mode invalid')
    plan = generate_plan(p)
    check("7. experiment invalid mode", plan["status"] == "FAIL" and "invalid mode" in (plan.get("error") or ""),
          f"got status={plan['status']}, error={plan.get('error')}")

    # Test 8: Payload persistence uses safe path
    with tempfile.TemporaryDirectory() as td:
        safe_dir = Path(td) / "test_payloads"
        filepath = save_payload("research-intake", "test payload content", safe_dir)
        check("8. payload persistence", filepath.exists() and "research_intake" in filepath.name,
              f"path={filepath}, exists={filepath.exists()}")
        content = filepath.read_text(encoding="utf-8")
        check("8b. payload content", "test payload content" in content,
              f"content snippet={content[:100]}")

    # Test 9: Generate plan for research-intake
    p = parse_slash_command('/research-intake "Chain-of-Thought prompting"')
    plan = generate_plan(p)
    check("9. research-intake plan", plan["status"] == "PASS" and plan["maps_to"] == "research_cli_start",
          f"got maps_to={plan['maps_to']}")

    # Test 10: Generate plan for literature-intake
    p = parse_slash_command('/literature-intake "重点查 diffusion"')
    plan = generate_plan(p)
    check("10. literature-intake plan", plan["status"] == "PASS" and plan["maps_to"] == "continue_literature_search",
          f"got maps_to={plan['maps_to']}")

    # Test 11: Generate plan for idea-synthesis (plan_only)
    p = parse_slash_command('/idea-synthesis "不要只想单点创新" --num-candidates 8')
    plan = generate_plan(p)
    check("11. idea-synthesis plan", plan["status"] == "PASS" and plan.get("implementation_status") == "plan_only",
          f"got status={plan['status']}, impl={plan.get('implementation_status')}")

    # Test 12: Generate plan for idea-audit
    p = parse_slash_command('/idea-audit "重点检查 diffusion"')
    plan = generate_plan(p)
    check("12. idea-audit plan", plan["status"] == "PASS" and plan["maps_to"] == "continue_novelty_check",
          f"got maps_to={plan['maps_to']}")

    # Test 13: Generate plan for paper-writing (plan_only)
    p = parse_slash_command('/paper-writing "按保守论文风格写"')
    plan = generate_plan(p)
    check("13. paper-writing plan", plan["status"] == "PASS" and plan.get("implementation_status") == "plan_only",
          f"got status={plan['status']}, impl={plan.get('implementation_status')}")

    # Test 14: Reject empty command
    p = parse_slash_command('/')
    check("14. reject empty command", not p["valid"],
          f"got valid={p['valid']}")

    # Test 15: Reject non-slash input
    p = parse_slash_command('research-intake "test"')
    check("15. reject non-slash input", not p["valid"] and "must start with /" in (p["error"] or ""),
          f"got valid={p['valid']}, error={p['error']}")

    # Test 16: Experiment analyze mode
    p = parse_slash_command('/experiment "分析结果" --mode analyze')
    plan = generate_plan(p)
    check("16. experiment analyze mode", plan["status"] == "PASS" and plan["flags"].get("mode") == "analyze",
          f"got mode={plan['flags'].get('mode')}")

    # Test 17: Experiment revise mode
    p = parse_slash_command('/experiment "根据失败原因调整方法" --mode revise')
    plan = generate_plan(p)
    check("17. experiment revise mode", plan["status"] == "PASS" and plan["flags"].get("mode") == "revise",
          f"got mode={plan['flags'].get('mode')}")

    # Test 18: Plan includes internal stages
    p = parse_slash_command('/research-intake "test idea"')
    plan = generate_plan(p)
    check("18. plan includes internal stages", len(plan["internal_stages"]) > 0,
          f"stages={plan['internal_stages']}")

    # Test 19: All commands have plans
    all_ok = True
    for cmd in COMMAND_MAP:
        p = parse_slash_command(f'/{cmd} "test"')
        plan = generate_plan(p)
        if plan["status"] != "PASS":
            all_ok = False
            break
    check("19. all commands generate plans", all_ok)

    # Test 20: CLI help
    p = parse_slash_command('/experiment "test" --mode full')
    plan = generate_plan(p)
    check("20. experiment full mode plan", plan["status"] == "PASS" and plan["flags"].get("mode") == "full",
          f"got mode={plan['flags'].get('mode')}")

    # Test 21: plan_only status for idea-synthesis, experiment, paper-writing
    for cmd in ("idea-synthesis", "experiment", "paper-writing"):
        p = parse_slash_command(f'/{cmd} "test"')
        plan = generate_plan(p)
        check(f"21. {cmd} plan_only", plan.get("implementation_status") == "plan_only",
              f"got impl={plan.get('implementation_status')}")
    # research-intake should NOT have plan_only
    p = parse_slash_command('/research-intake "test"')
    plan = generate_plan(p)
    check("21b. research-intake not plan_only", plan.get("implementation_status") is None,
          f"got impl={plan.get('implementation_status')}")

    # Test 22: plan includes payload_file when save_payload used
    with tempfile.TemporaryDirectory() as td:
        from io import StringIO
        import contextlib
        f = StringIO()
        with contextlib.redirect_stdout(f):
            parsed = parse_slash_command('/research-intake "test idea"')
            plan = generate_plan(parsed)
            # Simulate what CLI does with --save-payload-dir
            safe_dir = Path(td) / " payloads"
            filepath = save_payload(parsed["command"], parsed["payload"], safe_dir)
            plan["payload_file"] = str(filepath)
        check("22. plan has payload_file", "payload_file" in plan and plan["payload_file"].endswith(".md"),
              f"payload_file={plan.get('payload_file')}")

    # Test 23: dry-run print line does NOT claim no files written
    src = Path(__file__).read_text(encoding="utf-8")
    dry_run_lines = [l for l in src.split("\n") if "DRY-RUN:" in l and "print(" in l]
    has_old = any("No files written" in l for l in dry_run_lines)
    has_new = any("Payload files are only written" in l for l in dry_run_lines)
    check("23. dry-run message accurate", not has_old and has_new,
          f"old_msg_present={has_old}, new_msg_present={has_new}")

    print(f"\nSelf-test results: {tests_passed} passed, {tests_failed} failed")
    return tests_failed == 0


# ---- CLI ----

def main():
    parser = argparse.ArgumentParser(description="Slash command adapter — Agent-facing parser for user commands")
    parser.add_argument("command", nargs="?", help="Slash command to parse (e.g., /research-intake \"...\")")
    parser.add_argument("--self-test", action="store_true", help="Run self-tests")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--save-payload-dir", type=str, default=None, help="Directory to save payload files")

    args = parser.parse_args()

    if args.self_test:
        ok = _self_test()
        sys.exit(0 if ok else 1)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    parsed = parse_slash_command(args.command)
    plan = generate_plan(parsed)

    # Save payload if requested
    if args.save_payload_dir and parsed["valid"] and parsed["payload"]:
        payload_dir = Path(args.save_payload_dir)
        filepath = save_payload(parsed["command"], parsed["payload"], payload_dir)
        plan["payload_file"] = str(filepath)

    if args.json:
        print(json.dumps(plan, indent=2, ensure_ascii=False))
    else:
        if plan["status"] == "FAIL":
            print(f"ERROR: {plan.get('error', 'unknown error')}")
            print(f"Raw input: {plan.get('raw', '')}")
            sys.exit(1)

        print(f"=== Slash Command Plan ===")
        print(f"Command:    {plan['command']}")
        print(f"Payload:    {plan['payload']}")
        print(f"Maps to:    {plan['maps_to']}")
        print(f"Stages:     {' → '.join(plan['internal_stages'])}")
        if plan.get("note"):
            print(f"Note:       {plan['note']}")
        if plan.get("implementation_status"):
            print(f"Status:     {plan['implementation_status']}")
        if plan.get("cli_action"):
            cli = plan["cli_action"]
            args_str = " ".join(cli["args"]) if cli["args"] else ""
            print(f"CLI:        {cli['command']} {args_str}")
            print(f"  → {cli['description']}")
        if plan.get("payload_file"):
            print(f"Payload:    saved to {plan['payload_file']}")
        print(f"\nDRY-RUN: No model calls, no trusted runner executed, no trusted_outputs changed. Payload files are only written when --save-payload-dir is provided.")


if __name__ == "__main__":
    main()
