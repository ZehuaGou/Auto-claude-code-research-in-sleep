#!/usr/bin/env python3
"""
ARIS Exec Review — One-shot independent review on a specific file.

Role types: idea_reviewer, contract_reviewer, result_judge, paper_relevance_reviewer

Reads env_loader for model routing, writes current_call.json and llm_calls.jsonl.

Note: This tool prepares the review context and records the ledger.
Actual Codex/LLM calls are made by the SKILL.md workflow; this tool
provides directory management and ledger integration.

Commands: init, complete, status
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


def get_review_dir() -> Path:
    root = find_project_root()
    review_dir = root / "review-stage" / "exec_reviews"
    review_dir.mkdir(parents=True, exist_ok=True)
    return review_dir


def init_review(
    input_file: str,
    role: str = "idea_reviewer",
    primary: str = "codex",
    fallback_model: str = "",
    skill: str = "exec-review",
    extra_inputs: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Initialize a review and return context."""
    review_id = f"review_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    root = find_project_root()

    inputs = [input_file] + (extra_inputs or [])
    inputs_abs = []
    for inp in inputs:
        p = Path(inp)
        if not p.is_absolute():
            p = root / inp
        inputs_abs.append(str(p.resolve()))

    review = {
        "review_id": review_id,
        "role": role,
        "input_file": input_file,
        "input_files": inputs_abs,
        "primary_backend": "codex" if primary == "codex" else "llm-chat",
        "fallback_model": fallback_model,
        "status": "initialized",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "skill": skill,
    }

    review_dir = get_review_dir()
    (review_dir / f"{review_id}.json").write_text(
        json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return review


def complete_review(
    review_id: str,
    verdict: str = "",
    score: Optional[float] = None,
    major_issues: Optional[List[str]] = None,
    minimum_fixes: Optional[List[str]] = None,
    confidence: str = "medium",
    backend_used: str = "codex",
    fallback_used: bool = False,
) -> Dict[str, Any]:
    """Complete a review and write output."""
    review_dir = get_review_dir()
    review_file = review_dir / f"{review_id}.json"

    if not review_file.exists():
        print(f"Review not found: {review_id}", file=sys.stderr)
        return {}

    review = json.loads(review_file.read_text(encoding="utf-8"))
    review.update({
        "verdict": verdict,
        "score": score,
        "major_issues": major_issues or [],
        "minimum_fixes": minimum_fixes or [],
        "confidence": confidence,
        "reviewer_backend": backend_used,
        "fallback_used": fallback_used,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "status": "completed",
    })

    (review_dir / f"{review_id}.json").write_text(
        json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Write markdown output
    md_lines = [
        f"# Review: {review_id}",
        f"",
        f"- **Role**: {review['role']}",
        f"- **Input**: {review.get('input_file', 'N/A')}",
        f"- **Verdict**: {verdict}",
        f"- **Score**: {score}" if score else "",
        f"- **Reviewer Backend**: {backend_used}",
        f"- **Fallback Used**: {fallback_used}",
        f"- **Confidence**: {confidence}",
        f"",
        f"## Major Issues",
    ]
    for issue in (major_issues or []):
        md_lines.append(f"- {issue}")
    md_lines.extend(["", "## Minimum Fixes"])
    for fix in (minimum_fixes or []):
        md_lines.append(f"- {fix}")

    (review_dir / f"{review_id}.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    return review


def status():
    """Show all reviews."""
    review_dir = get_review_dir()
    reviews = []
    for f in sorted(review_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            reviews.append({
                "review_id": data.get("review_id", f.stem),
                "role": data.get("role", ""),
                "status": data.get("status", "unknown"),
                "verdict": data.get("verdict", ""),
                "input_file": str(data.get("input_file", "")),
            })
        except Exception:
            pass
    print(json.dumps(reviews, ensure_ascii=False, indent=2))


def main():
    if len(sys.argv) < 2:
        print("Usage: exec_review.py <init|complete|status> [args...]", file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]
    cmd_args = sys.argv[2:]

    if cmd == "init":
        input_file = cmd_args[0] if cmd_args else ""
        role = cmd_args[1] if len(cmd_args) > 1 else "idea_reviewer"
        primary = cmd_args[2] if len(cmd_args) > 2 else "codex"
        result = init_review(input_file, role, primary)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd == "complete":
        review_id = cmd_args[0] if cmd_args else ""
        verdict = cmd_args[1] if len(cmd_args) > 1 else ""
        result = complete_review(review_id, verdict)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd == "status":
        status()

    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)
    main()
