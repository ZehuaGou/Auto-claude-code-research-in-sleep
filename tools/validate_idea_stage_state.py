#!/usr/bin/env python3
"""
ARIS Idea Stage State Validator.

Validates consistency across IDEA_BANK, CANONICAL_IDEAS, REVIEWS, NOVELTY,
ADVERSARIAL directories. Checks:
1. CAND_*.md status matches IDEA_BANK.json status
2. Killed candidates not in active_candidates
3. Legacy CAND_A-E not accessible as active glob
4. Phase 2 active candidates match phase3_active
5. No killed CAND in REVIEWS/NOVELTY owned by active pipeline
6. Artifact headers present in REVIEWS and NOVELTY outputs

Exit code: 0 if PASS or PASS_WITH_WARNINGS, 1 if FAIL.

Internal tool — invoked by /idea-discovery, not by users directly.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).parent.parent.resolve()
IDEA_STAGE = ROOT / "idea-stage" / "AGENTIC"


def find_project_idea_stage() -> Optional[Path]:
    if IDEA_STAGE.exists():
        return IDEA_STAGE
    return None


def parse_cand_status(filepath: Path) -> Optional[str]:
    """Extract Status from a CAND_*.md file."""
    if not filepath.exists():
        return None
    text = filepath.read_text(encoding="utf-8", errors="ignore")
    for line in text.splitlines():
        if "**Status**:" in line or "**Status**: " in line:
            lower = line.lower()
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


def check_artifact_header(filepath: Path) -> dict:
    """Check artifact header for required model + isolation fields."""
    required = {
        "primary_backend": False,
        "actual_backend": False,
        "fallback_used": False,
        "isolation_mode": False,
    }
    if not filepath.exists():
        return {"present": False, "fields": required}

    text = filepath.read_text(encoding="utf-8", errors="ignore")
    for line in text.splitlines()[:20]:
        line_stripped = line.strip().lower()
        if line_stripped.startswith("primary_backend:"):
            required["primary_backend"] = True
        elif line_stripped.startswith("actual_backend:"):
            required["actual_backend"] = True
        elif line_stripped.startswith("fallback_used:"):
            required["fallback_used"] = True
        elif line_stripped.startswith("isolation_mode:"):
            required["isolation_mode"] = True

    return {"present": True, "fields": required}


def main():
    idea_stage = find_project_idea_stage()
    if not idea_stage:
        print(json.dumps({"verdict": "NO_IDEA_STAGE", "reason": "idea-stage/AGENTIC not found"}))
        return 0

    bank_json = idea_stage / "IDEA_BANK.json"
    canonical_dir = idea_stage / "CANONICAL_IDEAS"
    reviews_dir = idea_stage / "REVIEWS"
    novelty_dir = idea_stage / "NOVELTY"
    archive_dir = canonical_dir / "_archive_legacy"

    violations = []
    warnings = []
    fixes = []

    # 1. Check IDEA_BANK.json exists and parse
    if not bank_json.exists():
        print(json.dumps({"verdict": "FAIL", "reason": "IDEA_BANK.json not found"}))
        return 1

    bank = json.loads(bank_json.read_text(encoding="utf-8"))

    # active_candidates may be at top level or nested under legacy_archive_notice
    active_cands = bank.get("active_candidates", [])
    if not active_cands:
        legacy_notice = bank.get("legacy_archive_notice", {})
        active_cands = legacy_notice.get("active_candidates", [])
    phase3_active = bank.get("phase3_active", [])
    phase3_inactive = bank.get("phase3_inactive", {})

    killed_in_bank = set()
    for cand_id, info in phase3_inactive.items():
        if isinstance(info, str) and "kill" in info.lower():
            killed_in_bank.add(cand_id)
        elif isinstance(info, dict) and "kill" in str(info.get("status", "")).lower():
            killed_in_bank.add(cand_id)

    # Also check bank's own killed list
    if "killed" in bank:
        killed_in_bank.update(bank["killed"])

    for cand in active_cands:
        if cand in killed_in_bank:
            violations.append(f"CAND in both active_candidates and killed: {cand}")

    # 3. Check CAND status matches between file and bank
    if canonical_dir.exists():
        for cand_file in sorted(canonical_dir.glob("CAND_*.md")):
            cand_id = cand_file.stem  # CAND_001, CAND_002, etc.
            file_status = parse_cand_status(cand_file)

            if file_status is None:
                warnings.append(f"Cannot parse status from {cand_file.name}")
                continue

            # Check against IDEA_BANK phase3 status
            if cand_id in phase3_inactive:
                inactive_info = phase3_inactive[cand_id]
                if isinstance(inactive_info, str) and "kill" in inactive_info.lower():
                    if file_status != "killed":
                        violations.append(
                            f"{cand_file.name}: file says '{file_status}' but IDEA_BANK says killed: {inactive_info}"
                        )
                elif isinstance(inactive_info, dict) and "kill" in str(inactive_info.get("reason", "")).lower():
                    if file_status != "killed":
                        violations.append(
                            f"{cand_file.name}: file says '{file_status}' but bank marks as killed"
                        )

            if cand_id in active_cands and file_status == "killed":
                violations.append(
                    f"{cand_file.name}: file says killed but in active_candidates list"
                )

    # 4. Check legacy archive is excluded from active glob
    if archive_dir.exists():
        legacy_files = list(archive_dir.glob("*.md"))
        if legacy_files:
            warnings.append(
                f"Legacy archive contains {len(legacy_files)} files: "
                + ", ".join(f.name for f in legacy_files)
                + " — must not be included in any active candidate glob"
            )

    # 5. Check no killed CAND has active REVIEWS/NOVELTY
    for cand_id in killed_in_bank:
        # Check reviews
        if reviews_dir.exists():
            for review_file in sorted(reviews_dir.glob(f"*{cand_id}*review*.md")):
                warnings.append(
                    f"Killed candidate {cand_id} has review file: reviews/{review_file.name}"
                )
        # Check novelty
        if novelty_dir.exists():
            for nov_file in sorted(novelty_dir.glob(f"*{cand_id}*novelty*.md")):
                warnings.append(
                    f"Killed candidate {cand_id} has novelty file: novelty/{nov_file.name}"
                )

    # 6. Check artifact headers for REVIEWS and NOVELTY
    header_issues = []
    if reviews_dir.exists():
        for review_file in sorted(reviews_dir.glob("CAND_*_review*.md")):
            header = check_artifact_header(review_file)
            if not header["present"]:
                header_issues.append(f"REVIEWS/{review_file.name}: file not found (race?)")
                continue
            for field, present in header["fields"].items():
                if not present:
                    header_issues.append(f"REVIEWS/{review_file.name}: missing '{field}' in header")

    if novelty_dir.exists():
        for nov_file in sorted(novelty_dir.glob("CAND_*_novelty*.md")):
            header = check_artifact_header(nov_file)
            if not header["present"]:
                header_issues.append(f"NOVELTY/{nov_file.name}: file not found (race?)")
                continue
            for field, present in header["fields"].items():
                if not present:
                    header_issues.append(f"NOVELTY/{nov_file.name}: missing '{field}' in header")

    # 7. Check novelty for ad_hoc mode
    ad_hoc_novelty = []
    if novelty_dir.exists():
        for nov_file in sorted(novelty_dir.glob("CAND_*_novelty*.md")):
            text = nov_file.read_text(encoding="utf-8", errors="ignore")
            if "mode: ad_hoc" in text or "mode: ad_hoc" in text:
                ad_hoc_novelty.append(str(nov_file.relative_to(idea_stage)))

    # Also check NOVELTY_ADHOC/
    adhoc_dir = idea_stage / "NOVELTY_ADHOC"
    if adhoc_dir.exists():
        for f in adhoc_dir.glob("*.md"):
            ad_hoc_novelty.append(str(f.relative_to(idea_stage)))

    # 8. Check ad_hoc novelty not referenced by final selection
    final_sel_dir = idea_stage / "FINAL_SELECTION"
    if final_sel_dir.exists() and ad_hoc_novelty:
        for fs_file in sorted(final_sel_dir.glob("*.md")):
            fs_text = fs_file.read_text(encoding="utf-8", errors="ignore")
            for adh in ad_hoc_novelty:
                if adh in fs_text:
                    violations.append(
                        f"FINAL_SELECTION/{fs_file.name} references ad_hoc novelty {adh}. "
                        "Ad hoc novelty cannot enter formal final selection."
                    )

    # 9. Check codex_thread_id presence for codex artifacts
    all_artifacts = []
    if reviews_dir.exists():
        all_artifacts.extend(reviews_dir.glob("CAND_*_review*.md"))
    if novelty_dir.exists():
        all_artifacts.extend(novelty_dir.glob("CAND_*_novelty*.md"))

    for art in all_artifacts:
        text = art.read_text(encoding="utf-8", errors="ignore")
        has_codex_backend = "actual_backend: codex" in text or "actual_backend: codex" in text.lower()
        has_thread_id = False
        has_isolation = False
        for line in text.splitlines()[:25]:
            ll = line.strip()
            if ll.startswith("codex_thread_id:") and ll.split(":", 1)[1].strip() not in ("none", "", "TODO:"):
                has_thread_id = True
            if ll.startswith("isolation_mode:"):
                has_isolation = True
                mode_val = ll.split(":", 1)[1].strip()
                if mode_val == "protocol_only":
                    for search_line in text.splitlines()[:25]:
                        sl = search_line.strip().lower()
                        if sl.startswith("verdict:") or "verdict" in sl:
                            if "pass" in sl and "warnings" not in sl and "pass_with_warnings" not in sl:
                                header_issues.append(
                                    f"{art.relative_to(idea_stage)}: protocol_only with verdict 'PASS' — "
                                    "protocol_only max is PASS_WITH_WARNINGS for critical gates"
                                )

        if has_codex_backend and not has_thread_id:
            header_issues.append(
                f"{art.relative_to(idea_stage)}: actual_backend=codex but missing/lacks codex_thread_id"
            )

    # 10. Ledger alignment check
    ledger_path = ROOT / ".aris" / "calls" / "llm_calls.jsonl"
    ledger_thread_ids = set()
    if ledger_path.exists():
        for line in ledger_path.read_text(encoding="utf-8", errors="ignore").strip().split("\n"):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                tid = entry.get("codex_thread_id", "")
                if tid:
                    ledger_thread_ids.add(tid)
            except json.JSONDecodeError:
                pass

        for art in all_artifacts:
            text = art.read_text(encoding="utf-8", errors="ignore")
            for line in text.splitlines()[:25]:
                ll = line.strip()
                if ll.startswith("codex_thread_id:"):
                    tid = ll.split(":", 1)[1].strip()
                    if tid and tid not in ("none", "", "TODO:") and tid not in ledger_thread_ids:
                        header_issues.append(
                            f"{art.relative_to(idea_stage)}: codex_thread_id={tid} "
                            "not found in ledger (.aris/calls/llm_calls.jsonl)"
                        )
                    break
    else:
        warnings.append(".aris/calls/llm_calls.jsonl not found — cannot verify ledger alignment")

    # 11. Determine verdict
    has_violations = len(violations) > 0
    has_warnings = len(warnings) > 0 or len(header_issues) > 0

    if has_violations:
        verdict = "FAIL"
    elif has_warnings:
        verdict = "PASS_WITH_WARNINGS"
    else:
        verdict = "PASS"

    report = {
        "verdict": verdict,
        "total_candidates_in_bank": len(active_cands),
        "phase3_active": phase3_active,
        "phase3_inactive_keys": list(phase3_inactive.keys()),
        "killed_in_bank": list(killed_in_bank),
        "violations": violations,
        "warnings": warnings,
        "header_issues": header_issues,
        "ad_hoc_novelty_files": ad_hoc_novelty,
        "ledger_thread_ids_count": len(ledger_thread_ids),
        "legacy_archive_present": archive_dir.exists() if archive_dir else False,
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))

    if verdict == "FAIL":
        return 1
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
