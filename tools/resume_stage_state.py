#!/usr/bin/env python3
"""
ARIS Stage State Checker — Resume/Checkpoint for interrupted staged workflows.

Detects where an interrupted research workflow left off by examining artifact
files on disk (not chat context). Supports all 4 staged skills + intent detection.

Commands:
  detect-intent "<message>"   — detect resume/rerun intent from user message
  research-lit                — check Phase 1 literature survey artifacts
  idea-creator                — check Phase 2 idea generation artifacts
  exec-review "CAND_XXX"      — check Phase 3 review artifacts for a candidate
  novelty-check "CAND_XXX"    — check Phase 4 novelty check artifacts for a candidate
  final-selection             — check Phase 5 final selection artifacts

Exit code: 0 if actionable state found, 1 if no state / unrecoverable.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).parent.parent.resolve()
IDEA_STAGE = ROOT / "idea-stage" / "AGENTIC"

# ---------------------------------------------------------------------------
# Intent detection — Chinese + English keywords
# ---------------------------------------------------------------------------

CN_RESUME_PATTERNS = [
    r"继续(?:刚才)?的?",
    r"接着来",
    r"接着做",
    r"继续执行",
    r"继续刚才的",
    r"往下走",
    r"下一步",
    r"继续下一步",
    r"刚才中断了",
    r"从刚刚那里接着",
    r"接上",
    r"恢复",
    r"继续跑",
    r"继续完成",
    r"后面怎么做",
    r"下面继续",
    r"从.*中断.*恢复",
    r"继续.*工作",
    r"接.*之前",
    r"接着.*做",
]

EN_RESUME_PATTERNS = [
    r"\bcontinue\b",
    r"\bgo on\b",
    r"\bproceed\b",
    r"\bresume\b",
    r"\bnext(?: step)?\b",
    r"\bcontinue from last step\b",
    r"\bresume previous task\b",
    r"\bpick up where we left off\b",
    r"\bnext stage\b",
    r"\bwhat.*next\b",
    r"\bpick.*up\b",
    r"\bwhere.*left\b",
    r"\bcarry on\b",
    r"\bgo ahead\b",
]

CN_RERUN_PATTERNS = [
    r"重新跑",
    r"重新执行",
    r"从头开始",
    r"全部重来",
    r"重新开始",
]

EN_RERUN_PATTERNS = [
    r"\brerun\b",
    r"\brun again\b",
    r"\brestart\b",
    r"\bstart over\b",
    r"\bfrom scratch\b",
]

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


# ---------------------------------------------------------------------------
# Artifact header parsing and validation
# ---------------------------------------------------------------------------

def parse_artifact_header(path: Path) -> Dict[str, str]:
    """Parse key-value pairs from the first 30 lines of an artifact file.
    Returns a dict of header fields (lowercased keys).
    """
    result: Dict[str, str] = {}
    if not path.exists():
        return result
    text = path.read_text(encoding="utf-8", errors="ignore")
    for line in text.splitlines()[:30]:
        line_stripped = line.strip()
        if not line_stripped:
            continue
        if ":" in line_stripped and not line_stripped.startswith("#"):
            key, _, val = line_stripped.partition(":")
            result[key.strip().lower()] = val.strip().lower()
    return result


def check_required_header(path: Path, required_fields: List[str]) -> Dict[str, Any]:
    """Check that an artifact file contains required header fields.
    Returns dict with present/absent fields and overall status.
    """
    result: Dict[str, Any] = {
        "present": False,
        "missing_fields": [],
        "header": {},
    }
    if not path.exists():
        return result

    header = parse_artifact_header(path)
    result["header"] = header
    result["present"] = True

    missing = []
    for field in required_fields:
        if field not in header or not header[field]:
            missing.append(field)

    # Special: if actual_backend=codex, codex_thread_id must be non-empty
    if header.get("actual_backend") == "codex":
        tid = header.get("codex_thread_id", "").strip()
        if not tid or tid in ("none", ""):
            if "codex_thread_id" not in missing:
                missing.append("codex_thread_id (required when actual_backend=codex)")

    result["missing_fields"] = missing
    result["header_complete"] = len(missing) == 0
    return result


ARTIFACT_REQUIRED_FIELDS = [
    "isolation_mode",
    "actual_backend",
    "fallback_used",
]


def extract_verdict(path: Path) -> Optional[str]:
    """Extract the verdict from an artifact file.
    Returns the verdict string or None.
    """
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8", errors="ignore")
    for line in text.splitlines():
        lower = line.strip().lower()
        # Match lines like "verdict: PASS", "verdict: GO", "## Verdict: FAIL" etc
        if re.match(r"^#*\s*verdict\s*:", lower):
            val = line.split(":", 1)[1].strip().lower()
            return val
        if re.match(r"^#*\s*verdict\s*$", lower):
            # Could be "## Verdict" as a heading, with value on next line
            pass
    return None


KNOWN_VERDICTS = [
    "pass", "pass_with_warnings", "fail",
    "go", "revise", "kill",
    "confirmed_novel", "likely_incremental", "already_done", "insufficient_evidence",
    "select_cand_001", "select_cand_002", "no_strong_idea", "needs_revision",
    "select_cand_001_with_warnings", "select_cand_002_with_warnings",
]


def is_valid_codex_artifact(path: Path) -> Dict[str, Any]:
    """Comprehensive check for a Codex gate artifact.
    Checks: existence, header completeness, verdict presence.
    """
    result: Dict[str, Any] = {
        "exists": False,
        "header_valid": False,
        "verdict_present": False,
        "verdict": None,
        "issues": [],
    }
    if not path.exists():
        result["issues"].append("file not found")
        return result
    result["exists"] = True

    header_check = check_required_header(path, ARTIFACT_REQUIRED_FIELDS)
    result["header"] = header_check["header"]
    if not header_check["header_complete"]:
        result["issues"].append(f"missing header fields: {header_check['missing_fields']}")
    else:
        result["header_valid"] = True

    verdict = extract_verdict(path)
    if verdict:
        result["verdict"] = verdict
        result["verdict_present"] = True
    else:
        result["issues"].append("verdict not found")

    return result


# ---------------------------------------------------------------------------
# Helpers to find artifacts across multiple paths
# ---------------------------------------------------------------------------

def _find_first_file(candidates: List[Path]) -> Optional[Path]:
    for p in candidates:
        if p.exists() and p.stat().st_size > 50:
            return p
    return None


def _find_latest_runs_dir() -> Optional[Path]:
    agentic_dir = IDEA_STAGE / "RUNS"
    if not agentic_dir.exists():
        return None
    runs = sorted(agentic_dir.iterdir())
    if not runs:
        return None
    return runs[-1]


# ---------------------------------------------------------------------------
# Intent detection
# ---------------------------------------------------------------------------

def _match_any(text: str, patterns: List[str]) -> Optional[str]:
    for pat in patterns:
        try:
            if re.search(pat, text):
                return pat
        except re.error:
            if pat in text:
                return pat
    return None


def detect_resume_intent(message: str) -> Dict[str, Any]:
    """Detect if a user message expresses intent to resume or rerun work.

    Returns dict with:
      has_resume_intent: bool (backward compatible)
      resume_intent: bool
      rerun_intent: bool
      suggested_action: check_current_stage|rerun_stage|ask_clarification
      matched_pattern: str|None
      hinted_stage: str|None
      stage_confidence: low|medium|high
    """
    result: Dict[str, Any] = {
        "has_resume_intent": False,
        "resume_intent": False,
        "rerun_intent": False,
        "suggested_action": "ask_clarification",
        "matched_pattern": None,
        "hinted_stage": None,
        "stage_confidence": "low",
    }

    msg_lower = message.lower().strip()

    # Check rerun patterns first (rerun takes priority over resume)
    matched_rerun = _match_any(message, CN_RERUN_PATTERNS) or _match_any(msg_lower, EN_RERUN_PATTERNS)
    if matched_rerun:
        result["rerun_intent"] = True
        result["has_resume_intent"] = True  # backward compat
        result["matched_pattern"] = f"rerun:{matched_rerun}"
        result["suggested_action"] = "rerun_stage"

        # Still detect hinted stage
        hinted = _detect_stage(message, msg_lower)
        if hinted:
            result["hinted_stage"] = hinted
            result["stage_confidence"] = "high"

        return result

    # Check resume patterns
    matched = None
    # English first (word boundary sensitive)
    for pat in EN_RESUME_PATTERNS:
        if re.search(pat, msg_lower):
            matched = f"en:{pat}"
            break
    # Chinese
    if not matched:
        for pat in CN_RESUME_PATTERNS:
            if re.search(pat, message):
                matched = f"cn:{pat}"
                break

    if not matched:
        return result

    result["resume_intent"] = True
    result["has_resume_intent"] = True
    result["matched_pattern"] = matched
    result["suggested_action"] = "check_current_stage"

    # Detect which stage is hinted
    hinted = _detect_stage(message, msg_lower)
    if hinted:
        result["hinted_stage"] = hinted
        result["stage_confidence"] = "high"
    else:
        result["stage_confidence"] = "low"

    return result


def _detect_stage(message: str, msg_lower: str) -> Optional[str]:
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
# Normalized status
# ---------------------------------------------------------------------------

STATUS_MAP = {
    "no_stage": "no_stage",
    "not_started": "no_stage",
    "needs_resume": "needs_resume",
    "partial": "needs_resume",
    "needs_gate": "needs_resume",
    "completed": "complete",
    "complete": "complete",
    "complete_with_warnings": "complete_with_warnings",
    "failed": "failed",
    "blocked": "blocked",
}


def _add_normalized(result: Dict[str, Any]) -> Dict[str, Any]:
    raw = result.get("status", "not_started")
    result["normalized_status"] = STATUS_MAP.get(raw, "needs_resume")
    return result


# ---------------------------------------------------------------------------
# Phase 1: research-lit
# ---------------------------------------------------------------------------

def _find_evidence_audit() -> Optional[Path]:
    """Search multiple possible paths for evidence audit output."""
    candidates = [
        IDEA_STAGE / "EVIDENCE_AUDIT" / "PHASE1_EVIDENCE_AUDIT.md",
        IDEA_STAGE / "EVIDENCE_AUDIT" / "PHASE1_EVIDENCE_AUDIT_CODEX.md",
    ]
    # Also check inside latest RUNS/
    latest = _find_latest_runs_dir()
    if latest:
        candidates.extend([
            latest / "PHASE1_EVIDENCE_AUDIT.md",
            latest / "PHASE1_EVIDENCE_AUDIT_CODEX.md",
            latest / "EVIDENCE_AUDIT" / "PHASE1_EVIDENCE_AUDIT.md",
        ])
    return _find_first_file(candidates)


def check_phase_research_lit() -> Dict[str, Any]:
    """Check Phase 1 (research-lit) artifacts with header+verdict validation."""
    result: Dict[str, Any] = {
        "stage": "research-lit",
        "status": "not_started",
        "required_artifacts": [],
        "gate_artifacts": [],
        "missing_required": [],
        "missing_gate": [],
        "next_action": "run /research-lit",
    }

    # Check required outputs
    lit_index = IDEA_STAGE / "LITERATURE_INDEX.md"
    gap_map = IDEA_STAGE / "GAP_MAP.md"
    latest = _find_latest_runs_dir()

    has_lit = lit_index.exists() and lit_index.stat().st_size > 50
    has_gap = gap_map.exists() and gap_map.stat().st_size > 50

    # Check RUNS/ versions
    runs_lit_path = None
    runs_gap_path = None
    if latest:
        rl = latest / "LITERATURE_INDEX.md"
        rg = latest / "GAP_MAP.md"
        if rl.exists() and rl.stat().st_size > 50:
            runs_lit_path = rl
            has_lit = True
        if rg.exists() and rg.stat().st_size > 50:
            runs_gap_path = rg
            has_gap = True

    # Find evidence audit
    audit_path = _find_evidence_audit()
    audit_valid = None
    if audit_path:
        audit_valid = is_valid_codex_artifact(audit_path)

    result["required_artifacts"] = [
        {"name": "LITERATURE_INDEX.md", "present": lit_index.exists() and lit_index.stat().st_size > 50, "size": lit_index.stat().st_size if lit_index.exists() else 0},
        {"name": "GAP_MAP.md", "present": gap_map.exists() and gap_map.stat().st_size > 50, "size": gap_map.stat().st_size if gap_map.exists() else 0},
    ]
    if runs_lit_path:
        result["required_artifacts"].append({"name": f"RUNS/{latest.name}/LITERATURE_INDEX.md", "present": True})
    if runs_gap_path:
        result["required_artifacts"].append({"name": f"RUNS/{latest.name}/GAP_MAP.md", "present": True})

    result["gate_artifacts"] = [{
        "name": str(audit_path.relative_to(ROOT)) if audit_path else "EVIDENCE_AUDIT/PHASE1_EVIDENCE_AUDIT.md",
        "present": audit_path is not None,
        "header_valid": audit_valid["header_valid"] if audit_valid else False,
        "verdict": audit_valid["verdict"] if audit_valid else None,
        "issues": audit_valid["issues"] if audit_valid else ["no audit file found"],
    }]

    missing_required = []
    if not has_lit:
        missing_required.append("LITERATURE_INDEX.md")
    if not has_gap:
        missing_required.append("GAP_MAP.md")
    result["missing_required"] = missing_required

    if not has_lit and not has_gap:
        result["status"] = "not_started"
        result["next_action"] = "Run /research-lit to begin literature survey"
        return _add_normalized(result)

    if has_lit and has_gap and not audit_path:
        result["status"] = "needs_gate"
        result["next_action"] = "LITERATURE_INDEX.md and GAP_MAP.md exist but evidence audit missing — the Codex gate was not completed"
        return _add_normalized(result)

    if audit_path:
        if audit_valid["verdict"] == "fail":
            result["status"] = "failed"
            result["next_action"] = "Evidence audit verdict is FAIL — literature survey insufficient. Broaden search and re-run /research-lit"
            return _add_normalized(result)

        if not audit_valid["header_valid"]:
            result["status"] = "needs_resume"
            result["next_action"] = f"Evidence audit exists but header incomplete: {audit_valid['issues']}. Re-run evidence audit gate"
            return _add_normalized(result)

        result["status"] = "completed"
        result["next_action"] = "Phase 1 complete. Proceed to Phase 2: /idea-creator"
        return _add_normalized(result)

    result["status"] = "partial"
    result["next_action"] = "Partial artifacts found. Re-run /research-lit"
    return _add_normalized(result)


# ---------------------------------------------------------------------------
# Phase 2: idea-creator
# ---------------------------------------------------------------------------

def _find_shortlist_audit() -> Optional[Path]:
    """Search multiple possible paths for shortlist audit output."""
    candidates = [
        IDEA_STAGE / "SHORTLIST_AUDIT" / "PHASE2_SHORTLIST_AUDIT.md",
        IDEA_STAGE / "SHORTLIST_AUDIT" / "PHASE2_IDEA_SHORTLIST_AUDIT.md",
        IDEA_STAGE / "SHORTLIST_AUDIT" / "PHASE2_IDEA_SHORTLIST_AUDIT_CODEX.md",
    ]
    latest = _find_latest_runs_dir()
    if latest:
        candidates.extend([
            latest / "PHASE2_IDEA_SHORTLIST_AUDIT.md",
            latest / "PHASE2_IDEA_SHORTLIST_AUDIT_CODEX.md",
        ])
    return _find_first_file(candidates)


def is_active_candidate(filepath: Path) -> bool:
    """Check if a CAND file is truly active (not killed/backup/exploratory)."""
    status = _parse_cand_status(filepath)
    return status in ("active", "revised_active", None)


def _get_active_candidates(cand_dir: Path) -> List[Path]:
    if not cand_dir.exists():
        return []
    result = []
    for cf in sorted(cand_dir.glob("CAND_*.md")):
        if is_active_candidate(cf):
            result.append(cf)
    return result


def check_phase_idea_creator() -> Dict[str, Any]:
    """Check Phase 2 (idea-creator) artifacts with header+verdict validation."""
    result: Dict[str, Any] = {
        "stage": "idea-creator",
        "status": "not_started",
        "required_artifacts": [],
        "gate_artifacts": [],
        "missing_required": [],
        "missing_gate": [],
        "active_candidates": [],
        "next_action": "run /idea-creator",
    }

    # Check IDEA_BANK
    bank_md = IDEA_STAGE / "IDEA_BANK.md"
    bank_json = IDEA_STAGE / "IDEA_BANK.json"
    has_bank = (bank_md.exists() and bank_md.stat().st_size > 50) or (bank_json.exists() and bank_json.stat().st_size > 50)

    result["required_artifacts"] = [
        {"name": "IDEA_BANK.md", "present": bank_md.exists() and bank_md.stat().st_size > 50},
        {"name": "IDEA_BANK.json", "present": bank_json.exists() and bank_json.stat().st_size > 50},
    ]

    # Check CANONICAL_IDEAS
    cand_dir = IDEA_STAGE / "CANONICAL_IDEAS"
    active_cands = _get_active_candidates(cand_dir)
    all_cands = sorted(cand_dir.glob("CAND_*.md")) if cand_dir.exists() else []
    has_active_candidate = len(active_cands) > 0

    result["required_artifacts"].append({
        "name": "CANONICAL_IDEAS/",
        "present": has_active_candidate,
        "total_candidates": len(all_cands),
        "active_candidates_count": len(active_cands),
        "all_candidates": [f.stem for f in all_cands],
        "active": [f.stem for f in active_cands],
    })

    # Check shortlist audit
    audit_path = _find_shortlist_audit()
    audit_valid = None
    if audit_path:
        audit_valid = is_valid_codex_artifact(audit_path)

    result["gate_artifacts"] = [{
        "name": str(audit_path.relative_to(ROOT)) if audit_path else "SHORTLIST_AUDIT/PHASE2_SHORTLIST_AUDIT.md",
        "present": audit_path is not None,
        "header_valid": audit_valid["header_valid"] if audit_valid else False,
        "verdict": audit_valid["verdict"] if audit_valid else None,
        "issues": audit_valid["issues"] if audit_valid else ["no shortlist audit found"],
    }]

    missing_required = []
    if not has_bank:
        missing_required.append("IDEA_BANK.md or IDEA_BANK.json")
    if not has_active_candidate:
        missing_required.append("CANONICAL_IDEAS/CAND_*.md (no active candidate)")
    result["missing_required"] = missing_required

    # Active candidates detail
    result["active_candidates"] = [
        {"candidate": cf.stem, "status": _parse_cand_status(cf) or "unknown"}
        for cf in all_cands
    ]

    if not has_bank or not has_active_candidate:
        result["status"] = "not_started"
        result["next_action"] = "Run /idea-creator to generate ideas"
        return _add_normalized(result)

    if has_bank and has_active_candidate and not audit_path:
        result["status"] = "needs_gate"
        result["next_action"] = "IDEA_BANK and active candidates exist but shortlist audit missing. Re-run /idea-creator or run shortlist gate"
        return _add_normalized(result)

    if audit_path:
        if not audit_valid["header_valid"]:
            result["status"] = "needs_resume"
            result["next_action"] = f"Shortlist audit exists but header incomplete: {audit_valid['issues']}. Re-run shortlist audit gate"
            return _add_normalized(result)

        result["status"] = "completed"
        result["next_action"] = "Phase 2 complete. Proceed to Phase 3: /exec-review CAND_XXX"
        return _add_normalized(result)

    result["status"] = "partial"
    result["next_action"] = "Partial artifacts found. Re-run /idea-creator"
    return _add_normalized(result)


# ---------------------------------------------------------------------------
# Phase 3: exec-review
# ---------------------------------------------------------------------------

def check_phase_exec_review(candidate: Optional[str] = None) -> Dict[str, Any]:
    """Check Phase 3 (exec-review) artifacts with header+verdict validation."""
    result: Dict[str, Any] = {
        "stage": "exec-review",
        "status": "not_started",
        "reviews_found": [],
        "reviews_missing": [],
        "reviews_incomplete": [],
        "next_action": "run /exec-review CAND_XXX",
    }

    cand_dir = IDEA_STAGE / "CANONICAL_IDEAS"
    reviews_dir = IDEA_STAGE / "REVIEWS"

    if not cand_dir.exists():
        result["status"] = "blocked"
        result["next_action"] = "No CANONICAL_IDEAS directory — run /idea-creator first"
        return _add_normalized(result)

    if candidate:
        cand_path = cand_dir / f"{candidate}.md" if not candidate.endswith(".md") else cand_dir / candidate
        target_cands = [cand_path] if cand_path.exists() else []
    else:
        target_cands = _get_active_candidates(cand_dir)  # only truly active

    found = []
    missing = []
    incomplete = []

    for cand_path in target_cands:
        cand_stem = cand_path.stem
        cand_status = _parse_cand_status(cand_path)

        # Skip killed, backup, exploratory unless explicitly requested
        if cand_status in ("killed",) and candidate is None:
            continue
        if cand_status in ("backup_baseline", "exploratory_hold") and candidate is None:
            continue

        review_path = reviews_dir / f"{cand_stem}_review.md"
        if review_path.exists():
            # Validate header + verdict
            header_check = check_required_header(review_path, ARTIFACT_REQUIRED_FIELDS)
            verdict = extract_verdict(review_path)
            issues = []
            if not header_check["header_complete"]:
                issues.append(f"header_missing:{header_check['missing_fields']}")
            if not verdict:
                issues.append("no_verdict")

            entry = {
                "candidate": cand_stem,
                "review_file": str(review_path.relative_to(ROOT)),
                "header_valid": header_check["header_complete"],
                "verdict": verdict,
                "issues": issues,
            }

            if issues:
                incomplete.append(entry)
                result["reviews_incomplete"] = incomplete
            else:
                found.append(entry)
        else:
            if cand_status not in ("killed",):
                missing.append({"candidate": cand_stem, "reason": "review file not found"})

    result["reviews_found"] = found
    result["reviews_missing"] = missing

    if len(found) == 0 and len(incomplete) == 0 and len(missing) > 0:
        result["status"] = "not_started"
        result["next_action"] = "No reviews found. Run /exec-review CAND_XXX for each active candidate"
    elif len(incomplete) > 0:
        result["status"] = "needs_resume"
        result["next_action"] = f"{len(incomplete)} review(s) exist but have incomplete headers or missing verdict. Re-run exec-review for: {' '.join(e['candidate'] for e in incomplete)}"
    elif len(found) > 0 and len(missing) > 0:
        result["status"] = "partial"
        result["next_action"] = f"Reviews complete for {len(found)} candidate(s), missing for {len(missing)}. Continue with: {' '.join(m['candidate'] for m in missing)}"
    elif len(found) > 0 and len(missing) == 0:
        result["status"] = "completed"
        result["next_action"] = "All reviews complete. Proceed to Phase 4: /novelty-check CAND_XXX"
    else:
        result["status"] = "not_started"
        result["next_action"] = "No review candidates found"

    return _add_normalized(result)


# ---------------------------------------------------------------------------
# Phase 4: novelty-check
# ---------------------------------------------------------------------------

def check_phase_novelty_check(candidate: Optional[str] = None) -> Dict[str, Any]:
    """Check Phase 4 (novelty-check) artifacts with mode+header+verdict validation."""
    result: Dict[str, Any] = {
        "stage": "novelty-check",
        "status": "not_started",
        "novelty_found": [],
        "novelty_incomplete": [],
        "novelty_missing": [],
        "next_action": "run /novelty-check CAND_XXX",
    }

    cand_dir = IDEA_STAGE / "CANONICAL_IDEAS"
    novelty_dir = IDEA_STAGE / "NOVELTY"

    if not cand_dir.exists():
        result["status"] = "blocked"
        result["next_action"] = "No CANONICAL_IDEAS directory — run /idea-creator first"
        return _add_normalized(result)

    if candidate:
        cand_path = cand_dir / f"{candidate}.md" if not candidate.endswith(".md") else cand_dir / candidate
        target_cands = [cand_path] if cand_path.exists() else []
    else:
        # Check candidates that have valid Phase 3 reviews
        reviews_dir = IDEA_STAGE / "REVIEWS"
        target_cands = []
        for cf in _get_active_candidates(cand_dir):
            cand_stem = cf.stem
            if (reviews_dir / f"{cand_stem}_review.md").exists():
                target_cands.append(cf)

    found = []
    incomplete = []
    missing = []

    for cand_path in target_cands:
        cand_stem = cand_path.stem
        novelty_path = novelty_dir / f"{cand_stem}_novelty.md"

        if novelty_path.exists():
            # Validate: mode must be canonical_pipeline, header must be complete
            header = parse_artifact_header(novelty_path)
            mode = header.get("mode", "")
            header_check = check_required_header(novelty_path, ARTIFACT_REQUIRED_FIELDS)
            verdict = extract_verdict(novelty_path)
            issues = []

            if mode != "canonical_pipeline":
                issues.append("mode_not_canonical_pipeline")
            if not header_check["header_complete"]:
                issues.append(f"header_missing:{header_check['missing_fields']}")
            if not verdict:
                issues.append("no_verdict")

            entry = {
                "candidate": cand_stem,
                "novelty_file": str(novelty_path.relative_to(ROOT)),
                "mode": mode,
                "header_valid": header_check["header_complete"],
                "verdict": verdict,
                "issues": issues,
            }

            if issues:
                incomplete.append(entry)
            else:
                found.append(entry)
        else:
            missing.append({"candidate": cand_stem, "reason": "novelty report not found"})

    result["novelty_found"] = found
    result["novelty_incomplete"] = incomplete
    result["novelty_missing"] = missing

    if len(found) == 0 and len(incomplete) == 0 and len(missing) > 0:
        result["status"] = "not_started"
        result["next_action"] = "No novelty checks found. Run /novelty-check CAND_XXX for each reviewed candidate"
    elif len(incomplete) > 0:
        result["status"] = "needs_resume"
        result["next_action"] = f"{len(incomplete)} novelty report(s) exist but have incomplete headers, mode not canonical, or missing verdict. Re-run novelty-check for: {' '.join(e['candidate'] for e in incomplete)}"
    elif len(found) > 0 and len(missing) > 0:
        result["status"] = "partial"
        result["next_action"] = f"Novelty checks complete for {len(found)} candidate(s), missing for {len(missing)}. Continue with: {' '.join(m['candidate'] for m in missing)}"
    elif len(found) > 0 and len(missing) == 0:
        result["status"] = "completed"
        result["next_action"] = "All novelty checks complete. Ready for final selection"
    else:
        result["status"] = "not_started"
        result["next_action"] = "No novelty check candidates found"

    return _add_normalized(result)


# ---------------------------------------------------------------------------
# Phase 5: final-selection
# ---------------------------------------------------------------------------

def _check_ledger_for_final_selection(codex_tid: str) -> bool:
    """Check ledger contains a final_selector entry with matching codex_thread_id."""
    ledger_path = ROOT / ".aris" / "calls" / "llm_calls.jsonl"
    if not ledger_path.exists():
        return False
    for line in ledger_path.read_text(encoding="utf-8", errors="ignore").strip().split("\n"):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            entry_role = entry.get("role", "")
            entry_outputs = entry.get("output_files", [])
            entry_tid = entry.get("codex_thread_id", "")
            if entry_role == "final_selector" or any("IDEA_SELECTION_REPORT" in str(o) for o in entry_outputs):
                if entry_tid == codex_tid:
                    return True
        except json.JSONDecodeError:
            pass
    return False

def check_phase_final_selection() -> Dict[str, Any]:
    """Check Phase 5 (final-selection) artifacts with two-tier validation.

    Two completion tiers:
    A. complete (strong): Codex gate success
       - selection_mode: codex_gate
       - actual_backend: codex
       - fallback_used: false
       - codex_thread_id non-empty
       - verdict exists

    B. complete_with_warnings: LLM fallback gate
       - selection_mode: llm_fallback_gate
       - actual_model: deepseek-v4-pro
       - fallback_used: true
       - codex_used: false
       - verdict exists

    C. needs_resume: provisional/manual selection or missing artifact
    """
    result: Dict[str, Any] = {
        "stage": "final-selection",
        "status": "not_started",
        "selection_report": None,
        "provisional_selection_detected": False,
        "prereqs_complete": False,
        "next_action": "run /idea-bank 'final-select CAND_001'",
    }

    # Check prerequisites: exec-review and novelty-check must be complete
    cand_dir = IDEA_STAGE / "CANONICAL_IDEAS"
    reviews_dir = IDEA_STAGE / "REVIEWS"
    novelty_dir = IDEA_STAGE / "NOVELTY"

    prereq_issues = []
    if cand_dir.exists():
        for cand_path in sorted(cand_dir.glob("CAND_*.md")):
            cand_stem = cand_path.stem
            cand_status = _parse_cand_status(cand_path)
            if cand_status in ("killed", "backup_baseline", "exploratory_hold"):
                continue

            review_path = reviews_dir / f"{cand_stem}_review.md"
            novelty_path = novelty_dir / f"{cand_stem}_novelty.md"

            if not review_path.exists():
                prereq_issues.append(f"{cand_stem}: review not found")
            if not novelty_path.exists():
                prereq_issues.append(f"{cand_stem}: novelty-check not found")

    if not prereq_issues:
        result["prereqs_complete"] = True

    # Check final selection report
    selection_dir = IDEA_STAGE / "FINAL_SELECTION"
    report_path = selection_dir / "IDEA_SELECTION_REPORT.md"

    if not report_path.exists():
        if not result["prereqs_complete"]:
            result["status"] = "blocked"
            result["next_action"] = f"Review/novelty incomplete: {'; '.join(prereq_issues)}"
        else:
            result["status"] = "not_started"
            result["next_action"] = "Prerequisites complete. Run /idea-bank 'final-select CAND_001'"
        return _add_normalized(result)

    # Report exists — validate header
    header = parse_artifact_header(report_path)
    result["selection_report"] = str(report_path.relative_to(ROOT))

    mode = header.get("mode", "")
    selection_mode = header.get("selection_mode", "")
    isolation = header.get("isolation_mode", "")
    codex_tid = header.get("codex_thread_id", "")
    backend = header.get("actual_backend", "")
    fallback = header.get("fallback_used", "")
    verdict = extract_verdict(report_path)

    routing_source = header.get("routing_source", "")
    global_gate_mode = header.get("global_codex_gate_mode", "")
    result["header_fields"] = {
        "mode": mode,
        "selection_mode": selection_mode,
        "isolation_mode": isolation,
        "codex_thread_id": codex_tid if codex_tid and codex_tid != "none" else None,
        "actual_backend": backend,
        "fallback_used": fallback,
        "verdict": verdict,
        "routing_source": routing_source,
        "global_codex_gate_mode": global_gate_mode,
    }

    # Detect provisional selection (manual_override or missing Codex fields)
    if selection_mode == "manual_override" or isolation == "protocol_only":
        result["provisional_selection_detected"] = True
        result["status"] = "needs_resume"
        result["next_action"] = "Provisional selection detected. Run /idea-bank 'final-select CAND_XXX' for a formal Codex-gated verdict before proceeding."
        return _add_normalized(result)

    # Check if report itself is marked provisional (e.g., status line in content)
    report_text = report_path.read_text(encoding="utf-8", errors="ignore")
    if "PROVISIONAL" in report_text.upper():
        result["provisional_selection_detected"] = True
        result["status"] = "needs_resume"
        result["next_action"] = "Selection report is marked PROVISIONAL. Run /idea-bank 'final-select CAND_XXX' for a formal Codex-gated verdict."
        return _add_normalized(result)

    # Determine completion tier
    issues = []

    # Tier A: Codex gate (strong)
    if selection_mode == "codex_gate":
        if mode != "final_selection":
            issues.append(f"mode={mode} (expected final_selection)")
        if isolation != "codex_thread":
            issues.append(f"isolation_mode={isolation} (expected codex_thread)")
        if not codex_tid or codex_tid == "none":
            issues.append("codex_thread_id missing or empty")
        if backend != "codex":
            issues.append(f"actual_backend={backend} (expected codex)")
        if fallback != "false":
            issues.append(f"fallback_used={fallback} (expected false)")
        if verdict not in ("select_cand_001", "select_cand_002"):
            issues.append(f"verdict={verdict} (expected select_cand_001 or select_cand_002)")

        if issues:
            result["status"] = "needs_resume"
            result["issues"] = issues
            result["next_action"] = f"Selection report header incomplete: {'; '.join(issues)}"
            return _add_normalized(result)

        # Check ledger alignment for codex gate
        ledger_ok = _check_ledger_for_final_selection(codex_tid)
        if not ledger_ok:
            result["status"] = "needs_resume"
            result["issues"] = ["ledger entry missing role=final_selector or output_files=IDEA_SELECTION_REPORT"]
            result["next_action"] = "Selection report exists but ledger entry missing. Check .aris/calls/llm_calls.jsonl for final_selector entry."
            return _add_normalized(result)

        result["status"] = "completed"
        result["verdict"] = verdict
        result["next_action"] = "Final selection complete. Proceed to research-contract."

    # Tier B: LLM fallback gate or deepseek_only (with warnings)
    elif selection_mode == "llm_fallback_gate":
        if mode != "final_selection":
            issues.append(f"mode={mode} (expected final_selection)")
        if header.get("codex_used", "") != "false":
            issues.append("codex_used must be false for llm_fallback_gate")
        if header.get("confidence_downgraded", "") != "true":
            issues.append("confidence_downgraded must be true for llm_fallback_gate")
        actual_model = header.get("actual_model", "")
        if actual_model != "deepseek-v4-pro":
            issues.append(f"actual_model={actual_model} (expected deepseek-v4-pro)")
        # deepseek_only mode has fallback_used=false; codex_preferred fallback has fallback_used=true
        global_mode = header.get("global_codex_gate_mode", "")
        if global_mode == "deepseek_only":
            if fallback == "true":
                issues.append("fallback_used=true conflicts with global_codex_gate_mode=deepseek_only (expected false)")
            fb_reason = header.get("fallback_reason", "")
            if not fb_reason or fb_reason == "none":
                issues.append("fallback_reason must be non-empty (e.g. 'Codex disabled by ARIS_CODEX_GATE_MODE=deepseek_only')")
        else:
            # codex_preferred fallback or legacy fallback
            if fallback != "true":
                issues.append(f"fallback_used={fallback} (expected true for llm_fallback_gate)")
            fb_reason = header.get("fallback_reason", "")
            if not fb_reason or fb_reason == "none":
                issues.append("fallback_reason must be non-empty for llm_fallback_gate")
        if verdict not in ("select_cand_001_with_warnings", "select_cand_002_with_warnings"):
            issues.append(f"verdict={verdict} (expected select_cand_001_with_warnings or select_cand_002_with_warnings for fallback)")

        if issues:
            result["status"] = "needs_resume"
            result["issues"] = issues
            result["next_action"] = f"Selection report header incomplete: {'; '.join(issues)}"
            return _add_normalized(result)

        result["status"] = "complete_with_warnings"
        result["verdict"] = verdict
        if global_mode == "deepseek_only":
            result["next_action"] = "Final selection via deepseek_only mode (Codex was not used). Can proceed to research-contract."
        else:
            result["next_action"] = "Final selection completed with fallback (Codex was not used). Can proceed to research-contract."

    # Tier C: Unknown selection mode — needs resume
    else:
        result["status"] = "needs_resume"
        result["issues"] = [f"Unknown selection_mode={selection_mode}"]
        result["next_action"] = "Selection report has unknown gate type. Run /idea-bank 'final-select CAND_XXX'."


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_cand_status(filepath: Path) -> Optional[str]:
    if not filepath.exists():
        return None
    text = filepath.read_text(encoding="utf-8", errors="ignore")
    for line in text.splitlines():
        lower = line.lower()
        if "**status**" in lower or "status:" in lower:
            # Extract the status value after the colon
            if ":" in line:
                val = line.split(":", 1)[1].strip().lower()
            else:
                val = lower
            if "killed" in val:
                return "killed"
            if "provisional" in val:
                return "provisional_selected"
            if "backup" in val:
                return "backup_baseline"
            if "exploratory" in val or "hold" in val:
                return "exploratory_hold"
            if "selected" in val:
                return "selected"
            if "active" in val:
                return "active"
            if "revised" in val:
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
        sys.exit(0 if result["status"] not in ("not_started", "blocked") else 1)

    elif command == "idea-creator":
        result = check_phase_idea_creator()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result["status"] not in ("not_started", "blocked") else 1)

    elif command == "exec-review":
        candidate = sys.argv[2] if len(sys.argv) > 2 else None
        result = check_phase_exec_review(candidate)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result["status"] not in ("not_started", "blocked") else 1)

    elif command == "novelty-check":
        candidate = sys.argv[2] if len(sys.argv) > 2 else None
        result = check_phase_novelty_check(candidate)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result["status"] not in ("not_started", "blocked") else 1)

    elif command == "final-selection":
        result = check_phase_final_selection()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result["status"] not in ("not_started", "blocked", "failed") else 1)

    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
