#!/usr/bin/env python3
"""
ARIS Stage State Checker — Resume/Checkpoint for interrupted staged workflows.

Detects where an interrupted research workflow left off by examining artifact
files on disk (not chat context). Supports all 4 staged skills + intent detection.

Commands:
  detect-intent "<message>"   — detect resume intent from user message
  research-lit                — check Phase 1 literature survey artifacts
  idea-creator                — check Phase 2 idea generation artifacts
  exec-review "CAND_XXX"      — check Phase 3 review artifacts for a candidate
  novelty-check "CAND_XXX"    — check Phase 4 novelty check artifacts for a candidate

Exit code: 0 if actionable state found, 1 if no state / unrecoverable.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).parent.parent.resolve()
IDEA_STAGE = ROOT / "idea-stage" / "AGENTIC"

# ---------------------------------------------------------------------------
# Intent detection — Chinese + English keywords
# ---------------------------------------------------------------------------

# Chinese resume keywords (in priority order)
CN_RESUME_PATTERNS = [
    r"继续",
    r"接着做",
    r"下一步",
    r"恢复",
    r"从.*中断.*恢复",
    r"继续.*工作",
    r"接.*之前",
    r"接着.*做",
]

# English resume keywords
EN_RESUME_PATTERNS = [
    r"\bcontinue\b",
    r"\bresume\b",
    r"\bnext step\b",
    r"\bnext stage\b",
    r"\bwhat.*next\b",
    r"\bpick.*up\b",
    r"\bwhere.*left\b",
    r"\bcarry on\b",
    r"\bproceed\b",
    r"\bgo ahead\b",
]

# Stage keywords — what stage does the user want to resume?
STAGE_KEYWORDS: Dict[str, List[str]] = {
    "research-lit": ["literature", "survey", "research lit", "文献", "调研", "gap", "literature index"],
    "idea-creator": ["idea", "create", "generat", "brainstorm", "idea bank", "想法", "idea生成"],
    "exec-review": ["review", "exec review", "审查", "评审"],
    "novelty-check": ["novelty", "查新", "novelty check"],
}

STAGE_ALIASES: Dict[str, List[str]] = {
    "research-lit": ["phase 1", "第一阶段", "lit review", "p1"],
    "idea-creator": ["phase 2", "第二阶段", "generation", "p2"],
    "exec-review": ["phase 3", "第三阶段", "p3"],
    "novelty-check": ["phase 4", "第四阶段", "p4"],
}


def detect_resume_intent(message: str) -> Dict[str, Any]:
    """Detect if a user message expresses intent to resume work.

    Returns dict with:
      has_resume_intent: bool
      confidence: low|medium|high
      matched_pattern: str (the pattern that matched)
      hinted_stage: str|None (which stage the user mentioned)
      stage_confidence: low|medium|high
    """
    result: Dict[str, Any] = {
        "has_resume_intent": False,
        "confidence": "low",
        "matched_pattern": None,
        "hinted_stage": None,
        "stage_confidence": "low",
    }

    msg_lower = message.lower().strip()

    # Check resume patterns
    matched_en = None
    for pat in EN_RESUME_PATTERNS:
        if re.search(pat, msg_lower):
            matched_en = pat
            result["matched_pattern"] = f"en:{pat}"
            result["has_resume_intent"] = True
            break

    matched_cn = None
    if not result["has_resume_intent"]:
        for pat in CN_RESUME_PATTERNS:
            if re.search(pat, message):
                matched_cn = pat
                result["matched_pattern"] = f"cn:{pat}"
                result["has_resume_intent"] = True
                break

    if not result["has_resume_intent"]:
        return result

    result["confidence"] = "high" if result["matched_pattern"] else "medium"

    # Detect which stage is hinted
    hinted = _detect_stage(message, msg_lower)
    if hinted:
        result["hinted_stage"] = hinted
        result["stage_confidence"] = "high"
    else:
        result["stage_confidence"] = "low"

    return result


def _detect_stage(message: str, msg_lower: str) -> Optional[str]:
    """Detect which stage the user is referring to."""
    for stage, keywords in STAGE_KEYWORDS.items():
        for kw in keywords:
            if kw in msg_lower or kw in message:
                return stage
    for stage, aliases in STAGE_ALIASES.items():
        for alias in aliases:
            if alias in msg_lower:
                return stage
    return None


# ---------------------------------------------------------------------------
# Artifact checking per stage
# ---------------------------------------------------------------------------

def _check_file(path: Path, required: bool = True) -> Dict[str, Any]:
    """Check if a file exists and has non-trivial content."""
    result = {"exists": False, "size": 0, "present": False}
    if path.exists():
        result["exists"] = True
        result["size"] = path.stat().st_size
        result["present"] = result["size"] > 50  # non-trivial
    if required and not result["present"]:
        result["missing"] = str(path.relative_to(ROOT) if path.is_relative_to(ROOT) else path)
    return result


def check_phase_research_lit() -> Dict[str, Any]:
    """Check Phase 1 (research-lit) artifacts.

    Required artifacts: LITERATURE_INDEX.md, GAP_MAP.md
    Gate artifact: PHASE1_EVIDENCE_AUDIT.md
    """
    agentic_dir = IDEA_STAGE / "RUNS"
    result: Dict[str, Any] = {
        "stage": "research-lit",
        "status": "not_started",
        "required_artifacts": [],
        "gate_artifacts": [],
        "missing_required": [],
        "missing_gate": [],
        "next_action": "run research-lit",
    }

    # Check required outputs (LITERATURE_INDEX.md + GAP_MAP.md)
    lit_index = _check_file(IDEA_STAGE / "LITERATURE_INDEX.md", required=False)
    gap_map = _check_file(IDEA_STAGE / "GAP_MAP.md", required=False)
    evidence_audit = _check_file(IDEA_STAGE / "EVIDENCE_AUDIT" / "PHASE1_EVIDENCE_AUDIT.md", required=False)

    result["required_artifacts"] = [
        {"name": "LITERATURE_INDEX.md", **lit_index},
        {"name": "GAP_MAP.md", **gap_map},
    ]
    result["gate_artifacts"] = [
        {"name": "PHASE1_EVIDENCE_AUDIT.md", **evidence_audit},
    ]

    # Also check RUNS/<run_id>/ versions
    runs_lit = None
    runs_gap = None
    if agentic_dir.exists():
        runs = sorted(agentic_dir.iterdir())
        if runs:
            latest = runs[-1]
            rl = latest / "LITERATURE_INDEX.md"
            rg = latest / "GAP_MAP.md"
            if rl.exists():
                runs_lit = {"run": latest.name, **{k: v for k, v in _check_file(rl, required=False).items()}}
            if rg.exists():
                runs_gap = {"run": latest.name, **{k: v for k, v in _check_file(rg, required=False).items()}}

    if runs_lit:
        result["required_artifacts"].append({"name": f"RUNS/{runs_lit['run']}/LITERATURE_INDEX.md", **runs_lit})
    if runs_gap:
        result["required_artifacts"].append({"name": f"RUNS/{runs_gap['run']}/GAP_MAP.md", **runs_gap})

    # Determine status
    has_lit = lit_index["present"] or (runs_lit and runs_lit["present"])
    has_gap = gap_map["present"] or (runs_gap and runs_gap["present"])
    has_audit = evidence_audit["present"]

    missing_required = []
    missing_gate = []

    if not has_lit:
        missing_required.append("LITERATURE_INDEX.md (or RUNS/<run_id>/LITERATURE_INDEX.md)")
    if not has_gap:
        missing_required.append("GAP_MAP.md (or RUNS/<run_id>/GAP_MAP.md)")
    if not has_audit:
        missing_gate.append("PHASE1_EVIDENCE_AUDIT.md")

    result["missing_required"] = missing_required
    result["missing_gate"] = missing_gate

    if not has_lit and not has_gap:
        result["status"] = "not_started"
        result["next_action"] = "Run /research-lit to begin literature survey"
    elif has_lit and has_gap and not has_audit:
        result["status"] = "needs_gate"
        result["next_action"] = "LITERATURE_INDEX.md and GAP_MAP.md exist but PHASE1_EVIDENCE_AUDIT.md missing — the Codex evidence integrity gate was not completed. Run the gate or re-run /research-lit with --run-gate"
    elif has_lit and has_gap and has_audit:
        result["status"] = "completed"
        result["next_action"] = "Phase 1 complete. Proceed to Phase 2: /idea-creator"
    else:
        result["status"] = "partial"
        result["next_action"] = "Partial artifacts found. Re-run /research-lit to ensure completeness"

    return result


def check_phase_idea_creator() -> Dict[str, Any]:
    """Check Phase 2 (idea-creator) artifacts.

    Required: IDEA_BANK.md, IDEA_BANK.json, CANONICAL_IDEAS/CAND_*.md
    Gate: PHASE2_IDEA_SHORTLIST_AUDIT.md
    """
    result: Dict[str, Any] = {
        "stage": "idea-creator",
        "status": "not_started",
        "required_artifacts": [],
        "gate_artifacts": [],
        "missing_required": [],
        "missing_gate": [],
        "active_candidates": [],
        "next_action": "run idea-creator",
    }

    # Check IDEA_BANK
    bank_md = _check_file(IDEA_STAGE / "IDEA_BANK.md", required=False)
    bank_json = _check_file(IDEA_STAGE / "IDEA_BANK.json", required=False)
    result["required_artifacts"].extend([
        {"name": "IDEA_BANK.md", **bank_md},
        {"name": "IDEA_BANK.json", **bank_json},
    ])

    # Check CANONICAL_IDEAS
    cand_dir = IDEA_STAGE / "CANONICAL_IDEAS"
    cand_files = []
    if cand_dir.exists():
        cand_files = sorted(cand_dir.glob("CAND_*.md"))
    has_cands = len(cand_files) > 0

    result["required_artifacts"].append({
        "name": "CANONICAL_IDEAS/",
        "present": has_cands,
        "candidate_count": len(cand_files),
        "candidates": [f.stem for f in cand_files],
    })

    # Check shortlist audit
    audit_phase2 = _check_file(IDEA_STAGE / "SHORTLIST_AUDIT" / "PHASE2_SHORTLIST_AUDIT.md", required=False)
    result["gate_artifacts"].append({"name": "PHASE2_SHORTLIST_AUDIT.md", **audit_phase2})

    # Determine status
    has_bank = bank_md["present"]
    has_gate = audit_phase2["present"]

    missing_required = []
    missing_gate = []
    active_candidates = []

    if not has_bank:
        missing_required.append("IDEA_BANK.md")
    if not has_cands:
        missing_required.append("CANONICAL_IDEAS/CAND_*.md (no candidates generated)")
    if not has_gate:
        missing_gate.append("PHASE2_SHORTLIST_AUDIT.md")

    result["missing_required"] = missing_required
    result["missing_gate"] = missing_gate

    # Find active candidates (not killed)
    if cand_files:
        for cf in cand_files:
            status = _parse_cand_status(cf)
            active_candidates.append({"candidate": cf.stem, "status": status or "unknown"})
    result["active_candidates"] = active_candidates

    if not has_bank or not has_cands:
        result["status"] = "not_started"
        result["next_action"] = "Run /idea-creator to generate ideas"
    elif has_bank and has_cands and not has_gate:
        result["status"] = "needs_gate"
        result["next_action"] = "IDEA_BANK and candidates exist but shortlist audit missing. Run the Phase 2 Codex gate or re-run /idea-creator"
    elif has_bank and has_cands and has_gate:
        result["status"] = "completed"
        result["next_action"] = "Phase 2 complete. Proceed to Phase 3: /exec-review CAND_XXX"
    else:
        result["status"] = "partial"
        result["next_action"] = "Partial artifacts found. Re-run /idea-creator"

    return result


def check_phase_exec_review(candidate: Optional[str] = None) -> Dict[str, Any]:
    """Check Phase 3 (exec-review) artifacts.

    Required per candidate: REVIEWS/CAND_XXX_review.md
    If no candidate specified, checks all active candidates.
    """
    result: Dict[str, Any] = {
        "stage": "exec-review",
        "status": "not_started",
        "reviews_found": [],
        "reviews_missing": [],
        "next_action": "run exec-review",
    }

    cand_dir = IDEA_STAGE / "CANONICAL_IDEAS"
    reviews_dir = IDEA_STAGE / "REVIEWS"

    if not cand_dir.exists():
        result["status"] = "blocked"
        result["next_action"] = "No CANONICAL_IDEAS directory — run /idea-creator first"
        return result

    all_cands = sorted(cand_dir.glob("CAND_*.md"))

    if candidate:
        # Check specific candidate
        target_cands = [cand_dir / f"{candidate}.md"] if not candidate.endswith(".md") else [cand_dir / candidate]
    else:
        # Check all active (non-killed) candidates
        target_cands = all_cands

    found = []
    missing = []

    for cand_path in target_cands:
        if not cand_path.exists():
            missing.append({"candidate": cand_path.stem, "reason": "candidate file not found"})
            continue
        cand_stem = cand_path.stem
        review_file = reviews_dir / f"{cand_stem}_review.md"
        if review_file.exists():
            found.append({"candidate": cand_stem, "review_file": str(review_file.relative_to(ROOT))})
        else:
            status = _parse_cand_status(cand_path)
            if status != "killed":
                missing.append({"candidate": cand_stem, "reason": "review not found"})

    result["reviews_found"] = found
    result["reviews_missing"] = missing

    if len(found) == 0 and len(missing) > 0:
        result["status"] = "not_started"
        result["next_action"] = "No reviews found. Run /exec-review CAND_XXX for each candidate"
    elif len(found) > 0 and len(missing) > 0:
        result["status"] = "partial"
        result["next_action"] = f"Reviews found for {len(found)} candidate(s), missing for {len(missing)}. Continue with: {' '.join(m['candidate'] for m in missing)}"
    elif len(found) > 0 and len(missing) == 0:
        result["status"] = "completed"
        result["next_action"] = "All reviews complete. Proceed to Phase 4: /novelty-check CAND_XXX"
    else:
        result["status"] = "not_started"
        result["next_action"] = "No review candidates found"

    return result


def check_phase_novelty_check(candidate: Optional[str] = None) -> Dict[str, Any]:
    """Check Phase 4 (novelty-check) artifacts.

    Required per candidate: NOVELTY/CAND_XXX_novelty.md
    If no candidate specified, checks all active candidates.
    """
    result: Dict[str, Any] = {
        "stage": "novelty-check",
        "status": "not_started",
        "novelty_found": [],
        "novelty_missing": [],
        "next_action": "run novelty-check",
    }

    cand_dir = IDEA_STAGE / "CANONICAL_IDEAS"
    novelty_dir = IDEA_STAGE / "NOVELTY"

    if not cand_dir.exists():
        result["status"] = "blocked"
        result["next_action"] = "No CANONICAL_IDEAS directory — run /idea-creator first"
        return result

    if candidate:
        target_cands = [cand_dir / f"{candidate}.md"] if not candidate.endswith(".md") else [cand_dir / candidate]
    else:
        # Check candidates that have reviews (Phase 3 must be done first)
        reviews_dir = IDEA_STAGE / "REVIEWS"
        target_cands = []
        for cf in sorted(cand_dir.glob("CAND_*.md")):
            cand_stem = cf.stem
            if (reviews_dir / f"{cand_stem}_review.md").exists():
                target_cands.append(cf)

    found = []
    missing = []

    for cand_path in target_cands:
        if not cand_path.exists():
            continue
        cand_stem = cand_path.stem
        novelty_file = novelty_dir / f"{cand_stem}_novelty.md"
        if novelty_file.exists():
            found.append({"candidate": cand_stem, "novelty_file": str(novelty_file.relative_to(ROOT))})
        else:
            status = _parse_cand_status(cand_path)
            if status != "killed":
                missing.append({"candidate": cand_stem, "reason": "novelty report not found"})

    result["novelty_found"] = found
    result["novelty_missing"] = missing

    if len(found) == 0 and len(missing) > 0:
        result["status"] = "not_started"
        result["next_action"] = "No novelty checks found. Run /novelty-check CAND_XXX for each candidate"
    elif len(found) > 0 and len(missing) > 0:
        result["status"] = "partial"
        result["next_action"] = f"Novelty checks done for {len(found)} candidate(s), missing for {len(missing)}. Continue with: {' '.join(m['candidate'] for m in missing)}"
    elif len(found) > 0 and len(missing) == 0:
        result["status"] = "completed"
        result["next_action"] = "All novelty checks complete. Ready for final selection"
    else:
        result["status"] = "not_started"
        result["next_action"] = "No novelty check candidates found"

    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_cand_status(filepath: Path) -> Optional[str]:
    """Extract Status from a CAND_*.md file."""
    if not filepath.exists():
        return None
    text = filepath.read_text(encoding="utf-8", errors="ignore")
    for line in text.splitlines():
        lower = line.lower()
        if "**status**" in lower or "status:" in lower or "**status**: " in lower:
            # Check normalized
            if "killed" in lower:
                return "killed"
            if "active" in lower:
                return "active"
            if "backup" in lower:
                return "backup_baseline"
            if "exploratory" in lower or "hold" in lower:
                return "exploratory_hold"
            if "revised" in lower:
                return "revised_active"
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]

    if command == "detect-intent":
        if len(sys.argv) < 3:
            print(json.dumps({"error": "detect-intent requires a message argument", "has_resume_intent": False}))
            sys.exit(1)
        message = sys.argv[2]
        result = detect_resume_intent(message)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result["has_resume_intent"] else 1)

    elif command == "research-lit":
        result = check_phase_research_lit()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result["status"] in ("completed", "partial", "needs_gate") else 1)

    elif command == "idea-creator":
        result = check_phase_idea_creator()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result["status"] in ("completed", "partial", "needs_gate") else 1)

    elif command == "exec-review":
        candidate = sys.argv[2] if len(sys.argv) > 2 else None
        result = check_phase_exec_review(candidate)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result["status"] in ("completed", "partial") else 1)

    elif command == "novelty-check":
        candidate = sys.argv[2] if len(sys.argv) > 2 else None
        result = check_phase_novelty_check(candidate)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result["status"] in ("completed", "partial") else 1)

    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
