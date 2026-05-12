#!/usr/bin/env python3
"""
Literature Evidence Landing Tool.

Handles structured storage and validation of raw literature search results.
Does NOT access the network, does NOT call models, does NOT download PDFs.

Usage:
    python tools/literature_evidence_landing.py validate-raw --file <path> [--json]
    python tools/literature_evidence_landing.py append-raw --input <path> --run-dir <dir>
    python tools/literature_evidence_landing.py build-candidates --run-dir <dir> [--json]
    python tools/literature_evidence_landing.py validate-candidates --file <path> [--json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ALLOWED_SOURCES = frozenset([
    "arxiv", "semantic_scholar", "openalex", "crossref", "openreview", "webfetch", "manual"
])
ALLOWED_ORIGINS = frozenset([
    "websearch", "webfetch", "manual", "api_export"
])


# ---- Shared JSONL helpers ----

def _parse_jsonl(path: Path):
    """Parse a JSONL file, yield each record. Track line-level errors."""
    if not path.exists():
        return [], []

    records = []
    errors = []
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception as e:
        errors.append({"type": "read_error", "message": str(e)})
        return [], errors

    for lineno, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as e:
            errors.append({
                "type": "json_parse_error",
                "lineno": lineno,
                "message": str(e)
            })
    return records, errors


def _write_jsonl(path: Path, records: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ---- Raw validation ----

def _validate_records(records: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """Returns (errors, warnings, record_results)."""
    all_errors = []
    all_warnings = []
    results = []

    for idx, rec in enumerate(records):
        r_errors = []
        r_warnings = []
        rec_result = {
            "index": idx,
            "source": rec.get("source", ""),
            "title": rec.get("title", ""),
            "authors": rec.get("authors", ""),
            "year": rec.get("year", ""),
            "url": rec.get("url", ""),
            "evidence_origin": rec.get("evidence_origin", ""),
            "has_stable_id": bool(rec.get("doi") or rec.get("arxiv_id")
                                  or rec.get("semantic_scholar_id") or rec.get("openalex_id")),
            "has_abstract": bool(rec.get("abstract", "").strip()),
            "has_pdf_url": bool(rec.get("pdf_url", "").strip()),
        }

        for field in ("source", "title", "year", "url", "evidence_origin"):
            if not rec.get(field):
                r_errors.append(f"missing required field: {field}")

        source = rec.get("source", "")
        if source and source not in ALLOWED_SOURCES:
            r_errors.append(f"source '{source}' not in allowed list: {sorted(ALLOWED_SOURCES)}")

        origin = rec.get("evidence_origin", "")
        if origin and origin not in ALLOWED_ORIGINS:
            r_errors.append(f"evidence_origin '{origin}' not in allowed list: {sorted(ALLOWED_ORIGINS)}")

        if not rec.get("authors"):
            r_warnings.append("missing optional field: authors")
        if not rec.get("retrieved_at"):
            r_warnings.append("missing optional field: retrieved_at")
        if rec.get("authors") and not isinstance(rec["authors"], list):
            r_warnings.append("authors should be a list, not a string")
        if not rec.get("abstract", "").strip():
            r_warnings.append("missing optional field: abstract")
        if not rec.get("doi") and not rec.get("arxiv_id") and not rec.get("semantic_scholar_id") and not rec.get("openalex_id"):
            r_warnings.append("no stable identifier (doi/arxiv_id/semantic_scholar_id/openalex_id)")

        if rec.get("pdf_url") and source not in ("arxiv", "openalex", "openreview"):
            r_warnings.append("pdf_url present but source is not open — do not auto-download; confirm manually")

        rec_result["errors"] = r_errors
        rec_result["warnings"] = r_warnings
        results.append(rec_result)
        all_errors.extend(r_errors)
        all_warnings.extend(r_warnings)

    return all_errors, all_warnings, results


def validate_raw(file_path: Path, json_output: bool) -> dict:
    records, parse_errors = _parse_jsonl(file_path)

    if parse_errors:
        result = {"status": "invalid", "total_records": 0, "valid_records": 0,
                  "errors": parse_errors, "warnings": []}
        if json_output:
            print(json.dumps(result, indent=2))
        else:
            _print_validate_human(result)
        return result

    if not records:
        result = {"status": "empty", "total_records": 0, "valid_records": 0,
                  "errors": [], "warnings": []}
        if json_output:
            print(json.dumps(result, indent=2))
        else:
            _print_validate_human(result)
        return result

    errors, warnings, record_results = _validate_records(records)
    valid_count = sum(1 for r in record_results if not r["errors"])

    if errors:
        status = "invalid"
    elif warnings:
        status = "valid_with_warnings"
    else:
        status = "valid"

    result = {
        "status": status,
        "total_records": len(records),
        "valid_records": valid_count,
        "errors": errors[:20],
        "warnings": warnings[:20],
        "record_details": record_results,
    }

    if json_output:
        print(json.dumps(result, indent=2))
    else:
        _print_validate_human(result)
    return result


def _print_validate_human(result: dict) -> None:
    print(f"Status: {result['status']}")
    print(f"Total records: {result['total_records']}")
    print(f"Valid records: {result['valid_records']}")
    if result["errors"]:
        print(f"Errors ({len(result['errors'])}):")
        for e in result["errors"][:10]:
            print(f"  - {e}")
    if result["warnings"]:
        print(f"Warnings ({len(result['warnings'])}):")
        for w in result["warnings"][:10]:
            print(f"  - {w}")


def append_raw(input_path: Path, run_dir: Path, json_output: bool) -> None:
    records, parse_errors = _parse_jsonl(input_path)

    if parse_errors:
        msg = f"Failed to read input JSONL: {parse_errors}"
        print(msg, file=sys.stderr)
        sys.exit(1)

    if not records:
        print("Input file has no valid JSON records.", file=sys.stderr)
        sys.exit(1)

    errors, warnings, record_results = _validate_records(records)
    invalid_count = sum(1 for r in record_results if r["errors"])
    valid_records = [rec for rec, res in zip(records, record_results) if not res["errors"]]

    if invalid_count > 0:
        print(f"Warning: {invalid_count} record(s) have critical errors and will not be appended.", file=sys.stderr)
        for rec, res in zip(records, record_results):
            if res["errors"]:
                title = rec.get("title", "(untitled)")
                print(f"  Skipping '{title}': {res['errors']}", file=sys.stderr)

    if not valid_records:
        print("No valid records to append.", file=sys.stderr)
        sys.exit(1)

    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    output_path = run_dir / "raw_results.jsonl"

    with open(output_path, "a", encoding="utf-8") as f:
        for rec in valid_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"Appended {len(valid_records)} record(s) to {output_path}")
    all_records, _ = _parse_jsonl(output_path)
    print(f"Total records in file now: {len(all_records)}")


# ---- Candidate building ----

def _normalize_title(title: str) -> str:
    """Lowercase, trim, collapse whitespace, remove trailing punctuation."""
    t = title.lower().strip()
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"[^\w\s]", "", t)
    return t.strip()


def _canonical_identity(rec: dict, normalized_title: str, year: str) -> str:
    """Return a stable canonical identity string for dedup."""
    doi = rec.get("doi", "").strip()
    arxiv = rec.get("arxiv_id", "").strip()
    ss = rec.get("semantic_scholar_id", "").strip()
    oa = rec.get("openalex_id", "").strip()
    if doi:
        return f"doi:{doi.lower()}"
    if arxiv:
        return f"arxiv:{arxiv}"
    if ss:
        return f"semantic_scholar:{ss}"
    if oa:
        return f"openalex:{oa}"
    return f"title_year:{normalized_title}|{year}"


def _candidate_id_from_identity(identity: str) -> str:
    """Stable candidate ID from canonical identity (no raw index)."""
    h = hashlib.md5(identity.encode(), usedforsecurity=False).hexdigest()[:12]
    return f"cand_{h}"


def _build_stable_ids(rec: dict) -> dict:
    return {
        "doi": rec.get("doi") or "",
        "arxiv_id": rec.get("arxiv_id") or "",
        "semantic_scholar_id": rec.get("semantic_scholar_id") or "",
        "openalex_id": rec.get("openalex_id") or "",
    }


def _authors_to_list(authors):
    if isinstance(authors, list):
        return authors
    if isinstance(authors, str):
        return [a.strip() for a in authors.split(",") if a.strip()]
    return []


def build_candidates(run_dir: Path, json_output: bool) -> dict:
    run_dir = Path(run_dir)
    raw_path = run_dir / "raw_results.jsonl"

    records, parse_errors = _parse_jsonl(raw_path)

    if parse_errors:
        result = {"status": "invalid", "message": "Failed to read raw_results.jsonl",
                  "errors": parse_errors}
        if json_output:
            print(json.dumps(result, indent=2))
        else:
            print(f"Status: invalid")
            for e in parse_errors:
                print(f"  {e}")
        return result

    if not records:
        print("raw_results.jsonl is empty or does not exist. Nothing to build.", file=sys.stderr)
        sys.exit(1)

    # Compute normalized titles and canonical identities for all
    enriched = []
    for idx, rec in enumerate(records):
        nt = _normalize_title(rec.get("title", ""))
        yr = str(rec.get("year", ""))
        identity = _canonical_identity(rec, nt, yr)
        stable_ids = _build_stable_ids(rec)

        enriched.append({
            "original": rec,
            "normalized_title": nt,
            "year": yr,
            "identity": identity,
            "canonical_cid": _candidate_id_from_identity(identity),
            "stable_ids": stable_ids,
            "is_duplicate": False,
            "duplicate_of": "",
            "raw_index": idx,
        })

    # Deterministic dedup: later entries marked duplicate of first seen
    # Priority: doi > arxiv > ss > oa > normalized_title+year
    seen_keys: dict[str, dict] = {}
    for entry in enriched:
        identity = entry["identity"]
        if identity in seen_keys:
            entry["is_duplicate"] = True
            entry["duplicate_of"] = seen_keys[identity]["canonical_cid"]
        else:
            seen_keys[identity] = entry

    # Count how many times each canonical_cid is duplicated
    dup_counter: dict[str, int] = {}
    for entry in enriched:
        if entry["is_duplicate"]:
            canonical = entry["duplicate_of"]
            dup_counter[canonical] = dup_counter.get(canonical, 0) + 1

    # Assign final candidate IDs: canonical = cand_<hash>, dup entries = cand_<hash>_dup1, _dup2, ...
    dup_suffix_count: dict[str, int] = {}
    for entry in enriched:
        if entry["is_duplicate"]:
            canonical = entry["duplicate_of"]
            dup_suffix_count[canonical] = dup_suffix_count.get(canonical, 0) + 1
            entry["candidate_id"] = f"{canonical}_dup{dup_suffix_count[canonical]}"
        else:
            entry["candidate_id"] = entry["canonical_cid"]

    # Build output records
    output_records = []
    for entry in enriched:
        rec = entry["original"]
        output = {
            "candidate_id": entry["candidate_id"],
            "title": rec.get("title", ""),
            "normalized_title": entry["normalized_title"],
            "authors": _authors_to_list(rec.get("authors", "")),
            "year": entry["year"],
            "source": rec.get("source", ""),
            "url": rec.get("url", ""),
            "evidence_origin": rec.get("evidence_origin", ""),
            "retrieved_at": rec.get("retrieved_at", ""),
            "duplicate_of": entry["duplicate_of"],
            "stable_ids": entry["stable_ids"],
            "abstract": rec.get("abstract", ""),
            "venue": rec.get("venue", ""),
            "notes": rec.get("notes", ""),
        }
        output_records.append(output)

    # Write candidates.jsonl
    candidates_path = run_dir / "candidates.jsonl"
    _write_jsonl(candidates_path, output_records)

    canonical = [r for r in output_records if not r["duplicate_of"]]
    dup = [r for r in output_records if r["duplicate_of"]]
    total = len(output_records)

    print(f"Built {total} candidate(s) -> {candidates_path}")
    print(f"  Canonical: {len(canonical)}, Duplicates: {len(dup)}")

    result = {
        "status": "built",
        "total": total,
        "canonical": len(canonical),
        "duplicates": len(dup),
        "output": str(candidates_path),
    }
    if json_output:
        print(json.dumps(result, indent=2))
    return result


def validate_candidates(file_path: Path, json_output: bool) -> dict:
    records, parse_errors = _parse_jsonl(file_path)

    if parse_errors:
        result = {"status": "invalid", "total_records": 0, "canonical_records": 0,
                  "duplicate_records": 0, "errors": parse_errors, "warnings": []}
        if json_output:
            print(json.dumps(result, indent=2))
        else:
            _print_validate_candidates_human(result)
        return result

    if not records:
        result = {"status": "empty", "total_records": 0, "canonical_records": 0,
                  "duplicate_records": 0, "errors": [], "warnings": []}
        if json_output:
            print(json.dumps(result, indent=2))
        else:
            _print_validate_candidates_human(result)
        return result

    all_errors = []
    all_warnings = []
    canonical_count = 0
    dup_count = 0

    for rec in records:
        r_errors = []
        r_warnings = []

        for field in ("candidate_id", "title", "year", "source", "url", "evidence_origin"):
            if not rec.get(field):
                r_errors.append(f"missing required field: {field}")

        if rec.get("duplicate_of"):
            dup_count += 1
        else:
            canonical_count += 1

        if not rec.get("abstract"):
            r_warnings.append("missing optional field: abstract")
        if not rec.get("retrieved_at"):
            r_warnings.append("missing optional field: retrieved_at")
        ids = rec.get("stable_ids", {})
        if not any(ids.get(k) for k in ("doi", "arxiv_id", "semantic_scholar_id", "openalex_id")):
            r_warnings.append("no stable identifiers in stable_ids")

        all_errors.extend(r_errors)
        all_warnings.extend(r_warnings)

    if all_errors:
        status = "invalid"
    elif all_warnings:
        status = "valid_with_warnings"
    else:
        status = "valid"

    result = {
        "status": status,
        "total_records": len(records),
        "canonical_records": canonical_count,
        "duplicate_records": dup_count,
        "errors": all_errors[:20],
        "warnings": all_warnings[:20],
    }

    if json_output:
        print(json.dumps(result, indent=2))
    else:
        _print_validate_candidates_human(result)
    return result


def _print_validate_candidates_human(result: dict) -> None:
    print(f"Status: {result['status']}")
    print(f"Total records: {result['total_records']}")
    print(f"Canonical: {result['canonical_records']}, Duplicates: {result['duplicate_records']}")
    if result["errors"]:
        print(f"Errors ({len(result['errors'])}):")
        for e in result["errors"][:10]:
            print(f"  - {e}")
    if result["warnings"]:
        print(f"Warnings ({len(result['warnings'])}):")
        for w in result["warnings"][:10]:
            print(f"  - {w}")


# ---- Top-K building ----

def _score_candidate(rec: dict) -> tuple[int, int, str]:
    """Score a canonical candidate. Returns (score, year_int, title_lower)."""
    score = 0

    stable_ids = rec.get("stable_ids", {})
    has_stable = any(stable_ids.get(k) for k in ("doi", "arxiv_id", "semantic_scholar_id", "openalex_id"))
    if has_stable:
        score += 2
    else:
        score -= 1

    if rec.get("abstract", "").strip():
        score += 2
    else:
        score -= 2

    if rec.get("retrieved_at"):
        score += 1

    source = rec.get("source", "")
    if source in ("arxiv", "openreview", "openalex"):
        score += 1

    if rec.get("authors"):
        score += 1

    if rec.get("venue"):
        score += 1

    if source == "manual" and not rec.get("url", "").strip():
        score -= 1

    try:
        year_int = int(str(rec.get("year", "")).strip())
    except (ValueError, TypeError):
        year_int = 0

    title_lower = rec.get("title", "").lower().strip()
    return (score, year_int, title_lower)


def build_top_k(run_dir: Path, k: int, json_output: bool) -> dict:
    run_dir = Path(run_dir)
    candidates_path = run_dir / "candidates.jsonl"

    records, parse_errors = _parse_jsonl(candidates_path)

    if parse_errors:
        result = {"status": "invalid", "message": "Failed to read candidates.jsonl",
                  "errors": parse_errors}
        if json_output:
            print(json.dumps(result, indent=2))
        else:
            print(f"Status: invalid")
            for e in parse_errors:
                print(f"  {e}")
        return result

    if not records:
        print("candidates.jsonl is empty or does not exist. Nothing to build.", file=sys.stderr)
        sys.exit(1)

    canonical = [r for r in records if not r.get("duplicate_of")]
    duplicates = [r for r in records if r.get("duplicate_of")]

    scored = []
    for rec in canonical:
        score, year_int, title_lower = _score_candidate(rec)
        scored.append((score, year_int, title_lower, rec))

    scored.sort(key=lambda x: (-x[0], -x[1], x[3]))
    top_k_records = scored[:k]

    dup_of_counter: dict[str, int] = {}
    for rec in duplicates:
        canonical_id = rec.get("duplicate_of", "")
        if canonical_id:
            dup_of_counter[canonical_id] = dup_of_counter.get(canonical_id, 0) + 1

    output_path = run_dir / "top_k.md"
    _write_top_k_md(output_path, top_k_records, duplicates, dup_of_counter, len(canonical), len(records), k)

    print(f"Built top_k={k} from {len(records)} total / {len(canonical)} canonical -> {output_path}")

    result = {
        "status": "built",
        "total": len(records),
        "canonical": len(canonical),
        "duplicates": len(duplicates),
        "top_k": len(top_k_records),
        "output": str(output_path),
    }
    if json_output:
        print(json.dumps(result, indent=2))
    return result


def _write_top_k_md(path: Path, top_k_records: list, duplicates: list,
                    dup_of_counter: dict[str, int], canonical_count: int,
                    total_count: int, k: int) -> None:
    lines = [
        "# Top-K Literature Evidence",
        "",
        "Status: populated_by_tool",
        "",
        "## Search Summary",
        f"- Source file: candidates.jsonl",
        f"- Generated by: tools/literature_evidence_landing.py build-top-k",
        "- Selection method: deterministic metadata completeness score",
        f"- Total candidates: {total_count}",
        f"- Canonical candidates: {canonical_count}",
        f"- Duplicate records: {len(duplicates)}",
        f"- Selected top_k: {len(top_k_records)}",
        "- Warning: This file is literature evidence summary, not a novelty verdict.",
        "",
        "## Candidate Papers",
    ]

    for rank, (score, year_int, title_lower, rec) in enumerate(top_k_records, 1):
        stable_ids = rec.get("stable_ids", {})
        doi = stable_ids.get("doi", "") or ""
        arxiv_id = stable_ids.get("arxiv_id", "") or ""
        ss_id = stable_ids.get("semantic_scholar_id", "") or ""
        oa_id = stable_ids.get("openalex_id", "") or ""

        source = rec.get("source", "")
        url = rec.get("url", "") or ""

        has_abstract = bool(rec.get("abstract", "").strip())
        has_stable_id = any(stable_ids.get(k) for k in ("doi", "arxiv_id", "semantic_scholar_id", "openalex_id"))

        if has_abstract and has_stable_id:
            evidence_strength = "medium"
        else:
            evidence_strength = "low"

        if source in ("arxiv", "openreview") and url:
            full_text_available = "unknown"
        else:
            full_text_available = "unknown"

        fetched_or_manual = rec.get("evidence_origin", "") or ""

        method_note = ""
        if has_abstract:
            method_note = "abstract available; full method not assessed"
        else:
            method_note = ""

        lines.extend([
            "",
            f"### Paper {rank}",
            f"title: {rec.get('title', '')}",
            f"authors: {rec.get('authors', '')}",
            f"year: {rec.get('year', '')}",
            f"source: {source}",
            f"url: {url}",
            f"doi: {doi}",
            f"arxiv_id: {arxiv_id}",
            f"semantic_scholar_id: {ss_id}",
            f"openalex_id: {oa_id}",
            f"fetched_or_manual: {fetched_or_manual}",
            f"full_text_available: {full_text_available}",
            f"evidence_strength: {evidence_strength}",
            "relevance_to_research_contract: not assessed by tool",
            f"method_or_finding_relevant_to_claim: {method_note}",
            "evidence_gap: full text not verified; relevance not manually assessed",
        ])

    lines.extend([
        "",
        "## Duplicate Records",
        f"- Total duplicate records: {len(duplicates)}",
    ])
    if dup_of_counter:
        for cid, cnt in sorted(dup_of_counter.items()):
            lines.append(f"  - {cid}: {cnt} duplicate(s)")
    else:
        lines.append("  - (none)")

    lines.extend([
        "",
        "## Evidence Gaps",
        "- Full text is not verified by this tool.",
        "- Relevance to research contract is not semantically judged by this tool.",
        "- This file must pass validate_literature_evidence.py before novelty_check.",
        "",
        "## Notes for Novelty Check",
        "- This file is not a novelty verdict.",
        "- confirmed_novel must not be inferred from metadata completeness alone.",
        "- If validator returns valid_with_gaps, novelty_check must be cautious or require manual confirmation.",
    ])

    path.write_text("\n".join(lines), encoding="utf-8")


# ---- CLI ----

def main():
    parser = argparse.ArgumentParser(description="Literature Evidence Landing Tool")
    sub = parser.add_subparsers(dest="command")

    v = sub.add_parser("validate-raw", help="Validate raw_results.jsonl")
    v.add_argument("--file", required=True, help="Path to raw_results.jsonl")
    v.add_argument("--json", action="store_true", help="Output JSON")

    a = sub.add_parser("append-raw", help="Append records from a local JSONL to raw_results.jsonl")
    a.add_argument("--input", required=True, help="Path to local JSONL evidence file")
    a.add_argument("--run-dir", required=True, help="Target run directory")
    a.add_argument("--json", action="store_true", help="Output JSON result")

    b = sub.add_parser("build-candidates", help="Build candidates.jsonl from raw_results.jsonl")
    b.add_argument("--run-dir", required=True, help="Run directory (contains raw_results.jsonl)")
    b.add_argument("--json", action="store_true", help="Output JSON")

    c = sub.add_parser("validate-candidates", help="Validate candidates.jsonl")
    c.add_argument("--file", required=True, help="Path to candidates.jsonl")
    c.add_argument("--json", action="store_true", help="Output JSON")

    t = sub.add_parser("build-top-k", help="Build top_k.md from candidates.jsonl")
    t.add_argument("--run-dir", required=True, help="Run directory (contains candidates.jsonl)")
    t.add_argument("--k", type=int, default=10, help="Number of top candidates to select (default: 10)")
    t.add_argument("--json", action="store_true", help="Output JSON")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "validate-raw":
        validate_raw(Path(args.file), args.json)
    elif args.command == "append-raw":
        append_raw(Path(args.input), Path(args.run_dir), args.json)
    elif args.command == "build-candidates":
        build_candidates(Path(args.run_dir), args.json)
    elif args.command == "validate-candidates":
        validate_candidates(Path(args.file), args.json)
    elif args.command == "build-top-k":
        build_top_k(Path(args.run_dir), args.k, args.json)


if __name__ == "__main__":
    main()
