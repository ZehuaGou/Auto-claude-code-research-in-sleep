#!/usr/bin/env python3
"""
Literature Evidence Validator.

Reads top_k.md and checks whether its content is suitable for novelty evidence.
Does NOT call models, does NOT write files, does NOT read .env, does NOT access the network.

Usage:
    python tools/validate_literature_evidence.py
    python tools/validate_literature_evidence.py --file literature/search_runs/current/top_k.md
    python tools/validate_literature_evidence.py --json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).parent.resolve()
ROOT = TOOLS_DIR.parent.resolve()

# Indicators that the file is a template and not real evidence
TEMPLATE_INDICATORS = [
    "template_only",
    "No verified candidate papers yet",
    "Not populated yet",
    "Novelty check must not treat this template as evidence",
]

# Required fields per candidate paper entry
BASE_REQUIRED_FIELDS = [
    "title",
    "authors",
    "year",
    "source",
    "fetched_or_manual",
    "full_text_available",
    "evidence_strength",
    "relevance_to_research_contract",
    "method_or_finding_relevant_to_claim",
    "evidence_gap",
]

ALLOWED_EVIDENCE_STRENGTH = ("high", "medium", "low")

# HTML comment pattern — content inside these blocks is template, not real data
HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->", re.MULTILINE)


def has_template_indicator(text: str) -> bool:
    for indicator in TEMPLATE_INDICATORS:
        if indicator in text:
            return True
    return False


def remove_html_comments(text: str) -> str:
    """Strip HTML comments so template content inside them is not parsed as real entries."""
    return HTML_COMMENT_RE.sub("", text)


def parse_paper_blocks(text: str) -> list[dict]:
    """Parse paper blocks starting with ### Paper N."""
    # Split on ### Paper headings (at start of line)
    blocks = re.split(r"(?=^###\s+Paper\s+\d+)", text, flags=re.MULTILINE | re.IGNORECASE)
    entries = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        # Check this block starts with ### Paper
        if not re.match(r"^###\s+Paper\s+\d+", block, re.IGNORECASE):
            continue
        # Remove block title line
        lines = block.split("\n")
        if lines[0].strip().startswith("###"):
            lines = lines[1:]
        entry: dict = {}
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Skip section headers (## lines) mid-block
            if line.startswith("##"):
                continue
            if ": " in line:
                key, val = line.split(": ", 1)
                entry[key.strip().lower().replace(" ", "_")] = val.strip()
        if entry:
            entries.append(entry)
    return entries


def check_entry_fields(entry: dict) -> tuple[list[str], list[str], bool]:
    """Return (missing_base, issues, is_critical)."""
    missing = []
    issues = []
    is_critical = False
    for field in BASE_REQUIRED_FIELDS:
        if field not in entry or not entry[field]:
            missing.append(field)

    # url or doi at least one
    has_url = entry.get("url", "").strip()
    has_doi = entry.get("doi", "").strip()
    if not has_url and not has_doi:
        missing.append("url_or_doi")

    # evidence_strength rules
    es = entry.get("evidence_strength", "").lower()
    if es and es not in ALLOWED_EVIDENCE_STRENGTH:
        issues.append(f"evidence_strength must be high/medium/low, got '{es}'")
        is_critical = True

    ft = entry.get("full_text_available", "").lower()
    if ft in ("no", "unknown", "") and es == "high":
        issues.append("evidence_strength=high but full_text_available is no/unknown")
        is_critical = True

    if es == "high" and not entry.get("method_or_finding_relevant_to_claim", "").strip():
        issues.append("evidence_strength=high but method_or_finding_relevant_to_claim is empty")
        is_critical = True

    return missing, issues, is_critical


def check_full_text_availability(entry: dict) -> bool:
    val = entry.get("full_text_available", "").lower()
    return val in ("yes", "true", "available", "yes_available")


def validate_top_k(file_path: Path) -> dict:
    """Run validation checks on top_k.md."""
    if not file_path.exists():
        return {
            "status": "file_not_found",
            "error": f"File not found: {file_path}",
        }

    try:
        text = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return {
            "status": "read_error",
            "error": str(e),
        }

    # Remove HTML comments before parsing so template content is not treated as entries
    clean_text = remove_html_comments(text)

    # Check for template indicators (before removing HTML comments so we catch the real file)
    if has_template_indicator(text):
        return {
            "status": "template_only",
            "message": "File contains template markers and cannot be used as novelty evidence.",
            "template_indicators": [i for i in TEMPLATE_INDICATORS if i in text],
        }

    # Parse entries
    entries = parse_paper_blocks(clean_text)

    if not entries:
        return {
            "status": "insufficient_evidence",
            "message": "No candidate paper entries found.",
            "entries_found": 0,
            "entries_status": [],
        }

    # Check each entry
    all_entries_status = []
    all_issues = []
    critical_count = 0
    for idx, entry in enumerate(entries):
        missing, entry_issues, is_critical = check_entry_fields(entry)
        has_full_text = check_full_text_availability(entry)
        all_entries_status.append({
            "index": idx,
            "title": entry.get("title", ""),
            "missing_fields": missing,
            "issues": entry_issues,
            "full_text_available": has_full_text,
            "evidence_strength": entry.get("evidence_strength", ""),
        })
        all_issues.extend(entry_issues)
        if is_critical:
            critical_count += 1

    # Determine overall status
    any_missing_base = any(e["missing_fields"] for e in all_entries_status)
    all_no_full_text = all(not e["full_text_available"] for e in all_entries_status)
    any_no_full_text = any(not e["full_text_available"] for e in all_entries_status)

    if all_no_full_text:
        status = "insufficient_evidence"
        message = "All entries have no full text available."
    elif critical_count > 0:
        status = "insufficient_evidence"
        message = f"{critical_count} critical issue(s) found in entries (see issues list)."
    elif any_missing_base:
        status = "insufficient_evidence"
        message = "Some entries are missing required base fields."
    elif any_no_full_text:
        status = "valid_with_gaps"
        message = "Entries have required fields but some entries lack full text."
    elif all_issues:
        status = "valid_with_gaps"
        message = "Entries have required fields but some gaps or minor issues exist."
    else:
        status = "valid"
        message = "All entries pass validation checks."

    return {
        "status": status,
        "message": message,
        "entries_found": len(entries),
        "entries_status": all_entries_status,
        "issues": all_issues,
    }


def format_human(result: dict) -> str:
    status = result["status"]
    message = result["message"]
    lines = [f"Status: {status}", f"Message: {message}"]

    if "template_indicators" in result:
        lines.append(f"Template indicators found: {result['template_indicators']}")

    if "entries_status" in result and result["entries_status"]:
        lines.append(f"Entries found: {result['entries_found']}")
        for e in result["entries_status"]:
            missing = e["missing_fields"]
            issues = e["issues"]
            ft = e["full_text_available"]
            es = e["evidence_strength"]
            title = e["title"][:60] if e["title"] else "(untitled)"
            lines.append(
                f"  - {title}: "
                f"missing={missing if missing else 'none'}, "
                f"issues={issues if issues else 'none'}, "
                f"full_text={ft}, "
                f"evidence_strength={es}"
            )

    if result.get("issues"):
        lines.append(f"Overall issues: {result['issues']}")

    return "\n".join(lines)


def format_json_output(result: dict) -> str:
    return json.dumps(result, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Literature Evidence Validator"
    )
    parser.add_argument(
        "--file",
        default="literature/search_runs/current/top_k.md",
        help="Path to top_k.md",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON instead of human-readable",
    )
    args = parser.parse_args()

    file_path = Path(ROOT / args.file)
    result = validate_top_k(file_path)

    if args.json:
        print(format_json_output(result))
    else:
        print(format_human(result))

    # Exit code: 0 for valid, 1 for template_only/insufficient, 2 for error
    if result["status"] in ("valid", "valid_with_gaps"):
        sys.exit(0)
    elif result["status"] in ("template_only", "insufficient_evidence"):
        sys.exit(1)
    else:
        sys.exit(2)


if __name__ == "__main__":
    main()
