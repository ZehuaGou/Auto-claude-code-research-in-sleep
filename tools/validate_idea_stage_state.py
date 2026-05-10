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
            # Extract the status value after the colon
            if ":" in line:
                val = line.split(":", 1)[1].strip().lower()
            else:
                val = line.lower()
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

    # 9. Check final selection artifact type and validate accordingly
    final_sel_dir = idea_stage / "FINAL_SELECTION"
    has_codex_final_selection = False
    has_llm_fallback_selection = False
    selection_verdict = None

    if final_sel_dir.exists():
        report_path = final_sel_dir / "IDEA_SELECTION_REPORT.md"
        if report_path.exists():
            text = report_path.read_text(encoding="utf-8", errors="ignore")
            header_lines = text.splitlines()[:30]
            selection_mode = ""
            codex_tid = ""
            actual_backend = ""
            fallback_used = ""
            primary_backend = ""
            actual_model = ""
            fallback_reason = ""
            codex_used = ""
            confidence_downgraded = ""
            found_mode = False

            for line in header_lines:
                ll = line.strip().lower()
                if ll.startswith("mode:") and "final_selection" in ll:
                    found_mode = True
                if ll.startswith("selection_mode:"):
                    selection_mode = ll.split(":", 1)[1].strip()
                if ll.startswith("codex_thread_id:"):
                    codex_tid = ll.split(":", 1)[1].strip()
                if ll.startswith("actual_backend:"):
                    actual_backend = ll.split(":", 1)[1].strip()
                if ll.startswith("fallback_used:"):
                    fallback_used = ll.split(":", 1)[1].strip()
                if ll.startswith("primary_backend:"):
                    primary_backend = ll.split(":", 1)[1].strip()
                if ll.startswith("actual_model:"):
                    actual_model = ll.split(":", 1)[1].strip()
                if ll.startswith("fallback_reason:"):
                    fallback_reason = ll.split(":", 1)[1].strip()
                if ll.startswith("codex_used:"):
                    codex_used = ll.split(":", 1)[1].strip()
                if ll.startswith("confidence_downgraded:"):
                    confidence_downgraded = ll.split(":", 1)[1].strip()

            # Case A: codex_gate
            if selection_mode == "codex_gate" and found_mode:
                has_valid_tid = bool(codex_tid) and codex_tid not in ("none", "")
                has_codex_backend = actual_backend == "codex"
                has_no_fallback = fallback_used == "false"
                has_codex_final_selection = all([has_valid_tid, has_codex_backend, has_no_fallback])
                if has_codex_final_selection:
                    for line in text.splitlines():
                        ll = line.strip().lower()
                        if ll.startswith("verdict:"):
                            selection_verdict = ll.split(":", 1)[1].strip()
                            break

            # Case B: llm_fallback_gate
            elif selection_mode == "llm_fallback_gate" and found_mode:
                has_primary_codex = primary_backend == "codex"
                has_fallback_model = actual_model == "deepseek-v4-pro"
                has_fallback_used = fallback_used == "true"
                has_fallback_reason = bool(fallback_reason) and fallback_reason not in ("none", "")
                has_codex_false = codex_used == "false"
                has_confidence_downgrade = confidence_downgraded == "true"

                llm_issues = []
                if not has_primary_codex:
                    llm_issues.append("primary_backend must be codex for llm_fallback_gate")
                if not has_fallback_model:
                    llm_issues.append("actual_model must be deepseek-v4-pro for llm_fallback_gate")
                if not has_fallback_used:
                    llm_issues.append("fallback_used must be true for llm_fallback_gate")
                if not has_fallback_reason:
                    llm_issues.append("fallback_reason must be non-empty for llm_fallback_gate")
                if not has_codex_false:
                    llm_issues.append("codex_used must be false for llm_fallback_gate")
                if not has_confidence_downgrade:
                    llm_issues.append("confidence_downgraded must be true for llm_fallback_gate")

                if llm_issues:
                    header_issues.extend(llm_issues)
                    has_llm_fallback_selection = False
                else:
                    has_llm_fallback_selection = True
                    for line in text.splitlines():
                        ll = line.strip().lower()
                        if ll.startswith("verdict:"):
                            selection_verdict = ll.split(":", 1)[1].strip()
                            break

    # Check IDEA_BANK for selected candidates
    # Data may be at top level or nested under "summary"
    summary = bank.get("summary", {})
    selected_in_bank = bank.get("selected", summary.get("selected", []))
    selected_with_fallback_in_bank = bank.get("selected_with_fallback", summary.get("selected_with_fallback", []))
    provisional_in_bank = bank.get("provisional_selected", summary.get("provisional_selected", []))

    # Selected candidates must have codex_gate artifact
    for cand_id in selected_in_bank:
        cand_file = canonical_dir / f"{cand_id}.md"
        if cand_file.exists() and not has_codex_final_selection:
            violations.append(
                f"{cand_file.name}: marked SELECTED in IDEA_BANK but no Codex final_selector artifact found. "
                "This should be PROVISIONAL_SELECTED until a Codex gate completes."
            )

    # Selected-with-fallback candidates must have llm_fallback_gate artifact
    for cand_id in selected_with_fallback_in_bank:
        if not has_llm_fallback_selection:
            violations.append(
                f"{cand_id}: marked SELECTED_WITH_FALLBACK in IDEA_BANK but no valid llm_fallback_gate artifact found."
            )
        if has_llm_fallback_selection:
            warnings.append(
                f"{cand_id}: selected via llm_fallback_gate (Codex was not used). "
                "Confidence is downgraded. Run Codex final-select when available for a formal verdict."
            )

    for cand_id in provisional_in_bank:
        cand_file = canonical_dir / f"{cand_id}.md"
        if cand_file.exists():
            cand_status = parse_cand_status(cand_file)
            if cand_status and "selected" in cand_status.lower() and "provisional" not in cand_status.lower():
                violations.append(
                    f"{cand_file.name}: IDEA_BANK says provisional_selected but file says '{cand_status}'. "
                    "PROVISIONAL_SELECTED required for manual/provisional selections."
                )

                )

    # 10. Check codex_thread_id presence for codex artifacts
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
                            f"{art.relative_to(idea_stage)}: ledger entry missing codex_thread_id={tid} "
                            "(artifact header has it, but .aris/calls/llm_calls.jsonl entry lacks the field)"
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
