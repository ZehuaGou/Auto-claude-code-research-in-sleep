#!/usr/bin/env python3
"""
Literature Evidence Validator.

Reads top_k.md and checks whether its content is suitable for novelty evidence.
Does NOT call models, does NOT write files, does NOT read .env, does NOT联网.

Usage:
    python tools/validate_literature_evidence.py
    python tools/validate_literature_evidence.py --file literature/search_runs/current/top_k.md
    python tools/validate_literature_evidence.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
import os
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
REQUIRED_FIELDS = [
    "title",
    "authors",
    "year",
    "source",
    "url",
    "fetched_or_manual",
]


def has_template_indicator(text: str) -> bool:
    for indicator in TEMPLATE_INDICATORS:
        if indicator in text:
            return True
    return False


def parse_paper_entries(text: str) -> list[dict]:
    """Parse paper entries from top_k.md. Looks for bulleted or numbered entries."""
    entries = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # Detect a paper entry: starts with - or * and followed by title/author lines
        if line.startswith("- ") or line.startswith("* "):
            entry_text = line[2:].strip()
            entry: dict = {}
            # If the first line looks like a title field
            if ":" not in entry_text:
                entry["title"] = entry_text
                i += 1
                # Collect continuation lines until next bullet or empty-then-next-bullet
                while i < len(lines):
                    next_line = lines[i].strip()
                    if not next_line:
                        break
                    if next_line.startswith("- ") or next_line.startswith("* "):
                        break
                    entry_text += " " + next_line
                    i += 1
            else:
                # Multi-field entry
                # Collect this bullet and any continuation lines
                collected = [entry_text]
                i += 1
                while i < len(lines):
                    next_line = lines[i].strip()
                    if not next_line:
                        break
                    if next_line.startswith("- ") or next_line.startswith("* "):
                        break
                    collected.append(next_line)
                    i += 1
                entry_text = " ".join(collected)

                # Parse key: value pairs
                for part in entry_text.split(";"):
                    part = part.strip()
                    if ":" in part:
                        key, val = part.split(":", 1)
                        entry[key.strip().lower().replace(" ", "_")] = val.strip()

            if entry:
                entries.append(entry)
        else:
            i += 1
    return entries


def check_entry_fields(entry: dict) -> list[str]:
    """Return list of missing required fields."""
    missing = []
    for field in REQUIRED_FIELDS:
        if field not in entry or not entry[field]:
            missing.append(field)
    return missing


def check_full_text_availability(entry: dict) -> bool:
    """Return True if full_text_available is indicated as yes/true/available."""
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

    # Check for template indicators
    if has_template_indicator(text):
        return {
            "status": "template_only",
            "message": "File contains template markers and cannot be used as novelty evidence.",
            "indicators": [i for i in TEMPLATE_INDICATORS if i in text],
        }

    # Parse entries
    entries = parse_paper_entries(text)

    if not entries:
        return {
            "status": "insufficient_evidence",
            "message": "No candidate paper entries found.",
        }

    # Check each entry for required fields
    entries_status = []
    for idx, entry in enumerate(entries):
        missing = check_entry_fields(entry)
        has_full_text = check_full_text_availability(entry)
        entries_status.append({
            "index": idx,
            "title": entry.get("title", ""),
            "missing_fields": missing,
            "full_text_available": has_full_text,
        })

    # Determine overall status
    all_have_full_text = all(e["full_text_available"] for e in entries_status)
    any_missing_fields = any(e["missing_fields"] for e in entries_status)

    if all_have_full_text and not any_missing_fields:
        status = "valid"
        message = "All entries have required fields and full text availability."
    elif not any_missing_fields:
        status = "valid_with_gaps"
        message = "Entries have required fields but full text is not confirmed for all."
    else:
        status = "insufficient_evidence"
        message = "Some entries are missing required fields."

    return {
        "status": status,
        "message": message,
        "entries_found": len(entries),
        "entries_status": entries_status,
    }


def format_human(result: dict) -> str:
    status = result["status"]
    message = result["message"]
    lines = [f"Status: {status}", f"Message: {message}"]

    if "entries_status" in result:
        lines.append(f"Entries found: {result['entries_found']}")
        for e in result["entries_status"]:
            missing = e["missing_fields"]
            ft = e["full_text_available"]
            title = e["title"][:60] if e["title"] else "(untitled)"
            lines.append(
                f"  - {title}: "
                f"missing={missing if missing else 'none'}, "
                f"full_text={ft}"
            )

    if "indicators" in result:
        lines.append(f"Template indicators found: {result['indicators']}")

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
