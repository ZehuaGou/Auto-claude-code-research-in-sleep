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
    python tools/literature_evidence_landing.py build-search-plan --topic <t> --intent <i> --must-include <m> --source <s> --start-year <y> --end-year <y> --max-results-per-source <n> --output <path> [--exclude <e>] [--json]
    python tools/literature_evidence_landing.py validate-search-plan --file <path> [--json]
    python tools/literature_evidence_landing.py build-search-jobs --plan <path> --output <path> [--json]
    python tools/literature_evidence_landing.py validate-search-jobs --file <path> [--json]
    python tools/literature_evidence_landing.py init-run-skeleton --run-dir <dir> --topic <topic> --intent <intent>
    python tools/literature_evidence_landing.py validate-acquisition-status --file <path> [--json]
    python tools/literature_evidence_landing.py build-manual-queue --acquisition-status <file> --output <file>
    python tools/literature_evidence_landing.py summarize-run --run-dir <dir> [--json]
    python tools/literature_evidence_landing.py --self-test
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

ALLOWED_SOURCES = frozenset([
    "arxiv", "semantic_scholar", "openalex", "crossref", "openreview", "webfetch", "manual"
])
ALLOWED_ORIGINS = frozenset([
    "websearch", "webfetch", "manual", "api_export"
])

VALID_SEARCH_INTENTS = frozenset([
    "idea_discovery", "novelty_check", "experiment_plan", "related_work"
])

VALID_PLAN_SOURCES = frozenset([
    "arxiv", "semantic_scholar", "openalex", "crossref", "unpaywall",
    "openreview", "conference_site", "author_homepage", "github", "manual"
])

VALID_FULL_TEXT_STATUSES = frozenset([
    "available", "metadata_only", "manual_required", "failed"
])

VALID_PARSE_STATUSES = frozenset([
    "not_started", "parsed", "failed", "not_applicable"
])

VALID_PARSE_QUALITIES = frozenset([
    "high", "medium", "low", "unknown"
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

    scored.sort(key=lambda x: (-x[0], -x[1], x[2]))
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


# ---- Query variant generation ----

def _generate_query_variants(topic: str, must_include: list[str], exclude: str = "") -> list[str]:
    """Deterministic query variant generation from topic + must_include. No model, no network."""
    variants = []
    seen = set()

    def _add(q: str):
        q = q.strip()
        if q and q.lower() not in seen:
            seen.add(q.lower())
            variants.append(q)

    # 1. Topic itself
    _add(topic)

    # 2. Topic with all must_include terms
    if must_include:
        _add(topic + " " + " ".join(must_include))

    # 3. Each must_include term + topic words
    for term in must_include:
        _add(f"{topic} {term}")

    # 4. Pair combinations of must_include terms
    for i, a in enumerate(must_include):
        for b in must_include[i + 1:]:
            _add(f"{a} {b}")

    # 5. Shortened topic (first 4 words) + first must_include
    topic_words = topic.split()
    if len(topic_words) > 4 and must_include:
        _add(" ".join(topic_words[:4]) + " " + must_include[0])

    # 6. must_include terms reordered
    if len(must_include) >= 2:
        _add(" ".join(reversed(must_include)) + " " + topic)

    # Limit to 10
    return variants[:10]


def build_search_plan(
    topic: str,
    intent: str,
    must_include: list[str],
    sources: list[str],
    start_year: int,
    end_year: int,
    max_results_per_source: int,
    output_path: Path,
    exclude: str = "",
    json_output: bool = False,
) -> dict:
    """Build a search plan with deterministic query variants. No network, no model.
    Fail-closed: only writes output_path if validation passes."""
    # Validate sources
    bad_sources = [s for s in sources if s not in VALID_PLAN_SOURCES]
    if bad_sources:
        result = {"status": "FAIL", "errors": [f"unsupported source: '{s}'" for s in bad_sources]}
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    # Validate intent
    if intent not in VALID_SEARCH_INTENTS:
        result = {"status": "FAIL", "errors": [f"search_intent '{intent}' not in {sorted(VALID_SEARCH_INTENTS)}"]}
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    query_variants = _generate_query_variants(topic, must_include, exclude)

    plan = {
        "topic": topic,
        "search_intent": intent,
        "must_include": must_include,
        "exclude": exclude,
        "sources": sources,
        "time_range": {"start_year": start_year, "end_year": end_year},
        "max_results_per_source": max_results_per_source,
        "query_variants": query_variants,
        "notes": "Generated by build-search-plan (no network, no model). "
                 "Query variants are deterministic and non-exhaustive.",
    }

    # Validate in-memory before writing
    vr = validate_search_plan_dict(plan)
    if vr["status"] != "PASS":
        result = {"status": "FAIL", "errors": vr["errors"]}
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    # Only write output after validation passes
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")

    result = {
        "status": "PASS",
        "output": str(output_path),
        "query_variants": query_variants,
        "query_variant_count": len(query_variants),
    }
    if json_output:
        print(json.dumps(result, indent=2))
    return result


# ---- Search plan validation ----

# Novelty verdict fields that must NOT appear in a search plan
NOVELTY_VERDICT_FIELDS = frozenset([
    "verdict", "novelty_verdict", "confirmed_novel", "already_done", "likely_incremental"
])


def validate_search_plan_dict(plan: dict) -> dict:
    """Validate a search plan dict in memory. No file I/O, no network calls."""
    errors = []
    warnings = []

    # Required fields
    for field in ("topic", "search_intent", "must_include", "sources", "time_range", "max_results_per_source"):
        if field not in plan:
            errors.append(f"missing required field: {field}")

    # topic must be non-empty string
    topic = plan.get("topic", "")
    if isinstance(topic, str) and not topic.strip():
        errors.append("topic is empty")

    # search_intent must be valid
    intent = plan.get("search_intent", "")
    if intent and intent not in VALID_SEARCH_INTENTS:
        errors.append(f"search_intent '{intent}' not in {sorted(VALID_SEARCH_INTENTS)}")

    # must_include must be non-empty list
    must_include = plan.get("must_include", [])
    if not isinstance(must_include, list) or len(must_include) == 0:
        errors.append("must_include must be a non-empty list")

    # sources must be list with valid entries
    sources = plan.get("sources", [])
    if not isinstance(sources, list) or len(sources) == 0:
        errors.append("sources must be a non-empty list")
    else:
        for s in sources:
            if s not in VALID_PLAN_SOURCES:
                errors.append(f"unsupported source: '{s}'")

    # time_range must exist with start_year and end_year
    time_range = plan.get("time_range", {})
    if not isinstance(time_range, dict):
        errors.append("time_range must be a dict")
    else:
        if "start_year" not in time_range:
            errors.append("time_range missing start_year")
        if "end_year" not in time_range:
            errors.append("time_range missing end_year")

    # max_results_per_source must be positive integer
    max_results = plan.get("max_results_per_source")
    if max_results is None:
        errors.append("max_results_per_source is missing")
    elif not isinstance(max_results, int) or max_results <= 0:
        errors.append("max_results_per_source must be a positive integer")

    # start_year <= end_year
    time_range = plan.get("time_range", {})
    if isinstance(time_range, dict):
        sy = time_range.get("start_year")
        ey = time_range.get("end_year")
        if isinstance(sy, int) and isinstance(ey, int) and sy > ey:
            errors.append(f"start_year ({sy}) must be <= end_year ({ey})")

    # query_variants optional, but if present must be list
    qv = plan.get("query_variants")
    if qv is not None and not isinstance(qv, list):
        errors.append("query_variants must be a list if present")

    # No novelty verdict fields allowed
    for field in NOVELTY_VERDICT_FIELDS:
        if field in plan:
            errors.append(f"novelty verdict field not allowed: {field}")

    status = "PASS" if not errors else "FAIL"
    return {"status": status, "errors": errors, "warnings": warnings}


def validate_search_plan(file_path: Path, json_output: bool) -> dict:
    """Validate a search_plan.yaml-like JSON file. No network calls."""
    if not file_path.exists():
        result = {"status": "FAIL", "errors": ["file not found"], "warnings": []}
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    try:
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        plan = json.loads(text)
    except json.JSONDecodeError as e:
        result = {"status": "FAIL", "errors": [f"invalid JSON: {e}"], "warnings": []}
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    result = validate_search_plan_dict(plan)
    if json_output:
        print(json.dumps(result, indent=2))
    return result


# ---- Search job expansion ----

def build_search_jobs(plan_path: Path, output_path: Path, json_output: bool = False) -> dict:
    """Expand a validated search_plan.yaml into explicit per-source search jobs.
    No network, no model, no search execution."""
    # Read and validate plan
    if not plan_path.exists():
        result = {"status": "FAIL", "errors": ["plan file not found"]}
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8", errors="ignore"))
    except json.JSONDecodeError as e:
        result = {"status": "FAIL", "errors": [f"invalid JSON: {e}"]}
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    vr = validate_search_plan_dict(plan)
    if vr["status"] != "PASS":
        result = {"status": "FAIL", "errors": vr["errors"]}
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    topic = plan["topic"]
    intent = plan["search_intent"]
    sources = plan["sources"]
    time_range = plan["time_range"]
    max_results = plan["max_results_per_source"]
    query_variants = plan.get("query_variants", [])
    if not query_variants:
        query_variants = [topic]

    # Expand: sources × query_variants
    jobs = []
    seen_ids = set()
    for source in sources:
        for qi, query in enumerate(query_variants):
            # Deterministic job_id
            hash_input = f"{source}|{query}|{qi}"
            short_hash = hashlib.md5(hash_input.encode(), usedforsecurity=False).hexdigest()[:8]
            job_id = f"job_{source}_{short_hash}"
            # Ensure uniqueness
            while job_id in seen_ids:
                short_hash = hashlib.md5((hash_input + "|").encode(), usedforsecurity=False).hexdigest()[:8]
                job_id = f"job_{source}_{short_hash}"
            seen_ids.add(job_id)

            jobs.append({
                "job_id": job_id,
                "source": source,
                "query": query,
                "time_range": time_range,
                "max_results": max_results,
                "status": "planned",
                "network_required": True,
                "execution_result": "not_started",
                "raw_output_file": "",
                "error": "",
                "notes": "Generated by build-search-jobs (no network, no model).",
            })

    jobs_data = {
        "schema_version": "search_jobs_v1",
        "source_plan": str(plan_path),
        "topic": topic,
        "search_intent": intent,
        "job_count": len(jobs),
        "jobs": jobs,
    }

    # Validate before writing
    vj = validate_search_jobs_dict(jobs_data)
    if vj["status"] != "PASS":
        result = {"status": "FAIL", "errors": vj["errors"]}
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(jobs_data, indent=2, ensure_ascii=False), encoding="utf-8")

    result = {
        "status": "PASS",
        "output": str(output_path),
        "job_count": len(jobs),
        "sources": sources,
        "query_variant_count": len(query_variants),
    }
    if json_output:
        print(json.dumps(result, indent=2))
    return result


def validate_search_jobs_dict(data: dict) -> dict:
    """Validate search_jobs dict in memory. No file I/O, no network."""
    errors = []

    if data.get("schema_version") != "search_jobs_v1":
        errors.append(f"schema_version must be 'search_jobs_v1', got '{data.get('schema_version')}'")

    jobs = data.get("jobs", [])
    if not isinstance(jobs, list) or len(jobs) == 0:
        errors.append("jobs must be a non-empty list")
        return {"status": "FAIL", "errors": errors}

    job_count = data.get("job_count")
    if job_count != len(jobs):
        errors.append(f"job_count ({job_count}) != len(jobs) ({len(jobs)})")

    # Check required top-level fields
    for field in ("topic", "search_intent", "source_plan"):
        if field not in data:
            errors.append(f"missing top-level field: {field}")

    # Check each job
    seen_ids = set()
    for idx, job in enumerate(jobs):
        prefix = f"jobs[{idx}]"

        if not isinstance(job, dict):
            errors.append(f"{prefix}: must be a dict")
            continue

        for field in ("job_id", "source", "query", "time_range", "max_results",
                       "status", "network_required", "execution_result",
                       "raw_output_file", "error", "notes"):
            if field not in job:
                errors.append(f"{prefix}: missing required field: {field}")

        jid = job.get("job_id", "")
        if jid in seen_ids:
            errors.append(f"{prefix}: duplicate job_id: '{jid}'")
        seen_ids.add(jid)

        source = job.get("source", "")
        if source and source not in VALID_PLAN_SOURCES:
            errors.append(f"{prefix}: invalid source '{source}'")

        query = job.get("query", "")
        if not query or not str(query).strip():
            errors.append(f"{prefix}: query is empty")

        max_results = job.get("max_results")
        if not isinstance(max_results, int) or max_results <= 0:
            errors.append(f"{prefix}: max_results must be a positive integer")

        if job.get("status") != "planned":
            errors.append(f"{prefix}: status must be 'planned', got '{job.get('status')}'")

        if job.get("execution_result") != "not_started":
            errors.append(f"{prefix}: execution_result must be 'not_started', got '{job.get('execution_result')}'")

        if job.get("network_required") is not True:
            errors.append(f"{prefix}: network_required must be true")

    status = "PASS" if not errors else "FAIL"
    return {"status": status, "errors": errors}


def validate_search_jobs(file_path: Path, json_output: bool) -> dict:
    """Validate a search_jobs.json file. No network calls."""
    if not file_path.exists():
        result = {"status": "FAIL", "errors": ["file not found"]}
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    try:
        data = json.loads(file_path.read_text(encoding="utf-8", errors="ignore"))
    except json.JSONDecodeError as e:
        result = {"status": "FAIL", "errors": [f"invalid JSON: {e}"]}
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    result = validate_search_jobs_dict(data)
    if json_output:
        print(json.dumps(result, indent=2))
    return result


# ---- Init run skeleton ----

def init_run_skeleton(run_dir: Path, topic: str, intent: str) -> dict:
    """Create empty/template skeleton files for a literature search run."""
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    # search_plan.yaml (JSON content for MVP; full YAML parsing is future work)
    default_must_include = [topic] if topic.strip() else []
    default_sources = ["arxiv", "semantic_scholar", "openalex", "crossref"]
    plan = {
        "topic": topic,
        "search_intent": intent,
        "must_include": default_must_include,
        "sources": default_sources,
        "time_range": {"start_year": 2020, "end_year": 2026},
        "max_results_per_source": 50,
        "query_variants": _generate_query_variants(topic, default_must_include),
        "notes": "Generated by init-run-skeleton (no network, no model).",
    }
    (run_dir / "search_plan.yaml").write_text(
        json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Build search_jobs.json from the plan
    plan_path = run_dir / "search_plan.yaml"
    jobs_path = run_dir / "search_jobs.json"
    build_search_jobs(plan_path, jobs_path, json_output=False)

    # Empty JSONL files
    (run_dir / "raw_results.jsonl").write_text("", encoding="utf-8")
    (run_dir / "candidates.jsonl").write_text("", encoding="utf-8")

    # Template top_k.md
    (run_dir / "top_k.md").write_text(
        "# Top-K Literature Evidence\n\nStatus: template_only\n", encoding="utf-8"
    )

    # Empty acquisition status
    (run_dir / "acquisition_status.json").write_text(
        json.dumps({"papers": []}, indent=2), encoding="utf-8"
    )

    # Empty manual acquisition queue
    (run_dir / "manual_acquisition_queue.md").write_text(
        "# Manual Acquisition Queue\n\nNo papers queued.\n", encoding="utf-8"
    )

    created = [
        "search_plan.yaml", "search_jobs.json", "raw_results.jsonl", "candidates.jsonl",
        "top_k.md", "acquisition_status.json", "manual_acquisition_queue.md"
    ]

    return {"status": "created", "run_dir": str(run_dir), "files": created}


# ---- Acquisition status validation ----

def validate_acquisition_status(file_path: Path, json_output: bool) -> dict:
    """Validate acquisition_status.json schema. No network calls."""
    errors = []

    if not file_path.exists():
        result = {"status": "FAIL", "errors": ["file not found"]}
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    try:
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        data = json.loads(text)
    except json.JSONDecodeError as e:
        result = {"status": "FAIL", "errors": [f"invalid JSON: {e}"]}
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    papers = data.get("papers", [])
    if not isinstance(papers, list):
        result = {"status": "FAIL", "errors": ["papers must be a list"]}
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    for idx, paper in enumerate(papers):
        prefix = f"papers[{idx}]"

        if not isinstance(paper, dict):
            errors.append(f"{prefix}: must be a dict")
            continue

        if not paper.get("paper_id"):
            errors.append(f"{prefix}: missing paper_id")
        if not paper.get("title"):
            errors.append(f"{prefix}: missing title")

        fts = paper.get("full_text_status", "")
        if fts and fts not in VALID_FULL_TEXT_STATUSES:
            errors.append(f"{prefix}: invalid full_text_status '{fts}'")

        ps = paper.get("parse_status", "")
        if ps and ps not in VALID_PARSE_STATUSES:
            errors.append(f"{prefix}: invalid parse_status '{ps}'")

        pq = paper.get("parse_quality", "")
        if pq and pq not in VALID_PARSE_QUALITIES:
            errors.append(f"{prefix}: invalid parse_quality '{pq}'")

        # If full_text is not available, evidence_gap must be non-empty
        if fts in ("metadata_only", "manual_required", "failed"):
            eg = paper.get("evidence_gap", "")
            if not eg or not str(eg).strip():
                errors.append(f"{prefix}: full_text_status='{fts}' but evidence_gap is empty")

    status = "PASS" if not errors else "FAIL"
    result = {"status": status, "errors": errors}
    if json_output:
        print(json.dumps(result, indent=2))
    return result


# ---- Build manual queue ----

def build_manual_queue(acquisition_status_path: Path, output_path: Path) -> dict:
    """Build manual_acquisition_queue.md from acquisition_status.json."""
    if not acquisition_status_path.exists():
        return {"status": "FAIL", "message": "acquisition_status.json not found"}

    try:
        data = json.loads(acquisition_status_path.read_text(encoding="utf-8", errors="ignore"))
    except json.JSONDecodeError as e:
        return {"status": "FAIL", "message": f"invalid JSON: {e}"}

    papers = data.get("papers", [])
    queued = [p for p in papers if p.get("full_text_status") in ("manual_required", "failed")]

    lines = ["# Manual Acquisition Queue", ""]
    if not queued:
        lines.append("No papers require manual acquisition.")
    else:
        for paper in queued:
            title = paper.get("title", "(untitled)")
            doi = paper.get("doi", "")
            arxiv = paper.get("arxiv_id", "")
            oa = paper.get("openalex_id", "")
            gap = paper.get("evidence_gap", "")
            fts = paper.get("full_text_status", "")

            lines.append(f"## {title}")
            if doi:
                lines.append(f"- DOI: {doi}")
            if arxiv:
                lines.append(f"- arXiv: {arxiv}")
            if oa:
                lines.append(f"- OpenAlex: {oa}")
            lines.append(f"- Status: {fts}")
            if gap:
                lines.append(f"- Why needed: {gap}")
            lines.append("- Suggested legal actions:")
            lines.append("  - Check arXiv / OpenReview for open access version")
            lines.append("  - Check author homepage or GitHub")
            lines.append("  - Check institutional access")
            lines.append("  - Manually place PDF under literature/manual_pdf_drop/")
            lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")

    return {"status": "built", "queued_count": len(queued), "output": str(output_path)}


# ---- Summarize run ----

def summarize_run(run_dir: Path, json_output: bool) -> dict:
    """Summarize a literature search run directory. No network calls."""
    run_dir = Path(run_dir)

    plan_present = (run_dir / "search_plan.yaml").exists()

    raw_path = run_dir / "raw_results.jsonl"
    raw_records, _ = _parse_jsonl(raw_path) if raw_path.exists() else ([], [])
    raw_count = len(raw_records)

    cand_path = run_dir / "candidates.jsonl"
    cand_records, _ = _parse_jsonl(cand_path) if cand_path.exists() else ([], [])
    cand_count = len(cand_records)

    top_k_present = (run_dir / "top_k.md").exists()
    top_k_text = ""
    if top_k_present:
        top_k_text = (run_dir / "top_k.md").read_text(encoding="utf-8", errors="ignore")
    top_k_populated = top_k_present and "template_only" not in top_k_text

    acq_present = (run_dir / "acquisition_status.json").exists()
    manual_queue_present = (run_dir / "manual_acquisition_queue.md").exists()

    manual_required_count = 0
    full_text_available_count = 0
    metadata_only_count = 0

    if acq_present:
        try:
            acq_data = json.loads((run_dir / "acquisition_status.json").read_text(encoding="utf-8", errors="ignore"))
            for p in acq_data.get("papers", []):
                fts = p.get("full_text_status", "")
                if fts == "manual_required":
                    manual_required_count += 1
                elif fts == "failed":
                    manual_required_count += 1
                elif fts == "available":
                    full_text_available_count += 1
                elif fts == "metadata_only":
                    metadata_only_count += 1
        except Exception:
            pass

    # Validate search_plan if present
    search_plan_valid = False
    if plan_present:
        vr = validate_search_plan(run_dir / "search_plan.yaml", json_output=False)
        search_plan_valid = vr["status"] == "PASS"

    # Search jobs
    jobs_present = (run_dir / "search_jobs.json").exists()
    search_jobs_valid = False
    search_job_count = 0
    planned_job_count = 0
    executed_job_count = 0
    if jobs_present:
        try:
            jobs_data = json.loads((run_dir / "search_jobs.json").read_text(encoding="utf-8", errors="ignore"))
            vj = validate_search_jobs_dict(jobs_data)
            search_jobs_valid = vj["status"] == "PASS"
            jobs_list = jobs_data.get("jobs", [])
            search_job_count = len(jobs_list)
            for j in jobs_list:
                if j.get("status") == "planned":
                    planned_job_count += 1
                if j.get("execution_result") not in ("", "not_started"):
                    executed_job_count += 1
        except Exception:
            pass

    # Determine status
    if not plan_present:
        status = "FAIL"
    elif not search_plan_valid:
        status = "WARN"
    elif not jobs_present or not search_jobs_valid:
        status = "WARN"
    elif raw_count == 0:
        status = "WARN"
    elif cand_count == 0:
        status = "WARN"
    elif not top_k_populated:
        status = "WARN"
    else:
        status = "PASS"

    result = {
        "search_plan_present": plan_present,
        "search_plan_valid": search_plan_valid,
        "search_jobs_present": jobs_present,
        "search_jobs_valid": search_jobs_valid,
        "search_job_count": search_job_count,
        "planned_job_count": planned_job_count,
        "executed_job_count": executed_job_count,
        "raw_result_count": raw_count,
        "candidate_count": cand_count,
        "top_k_present": top_k_populated,
        "acquisition_status_present": acq_present,
        "manual_queue_present": manual_queue_present,
        "manual_required_count": manual_required_count,
        "full_text_available_count": full_text_available_count,
        "metadata_only_count": metadata_only_count,
        "status": status,
    }

    if json_output:
        print(json.dumps(result, indent=2))
    return result


# ---- Self-test ----

def _self_test() -> bool:
    """Run self-tests. Uses tempfile; no network; no model keys."""
    import shutil

    passed = 0
    failed = 0

    def _write_tmp_json(data: dict, suffix: str = ".json") -> Path:
        f = tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False, encoding="utf-8")
        f.write(json.dumps(data, indent=2))
        f.close()
        return Path(f.name)

    # Test 1: valid search_plan → PASS
    try:
        plan = {
            "topic": "hallucination detection hidden states",
            "search_intent": "novelty_check",
            "must_include": ["hallucination", "hidden states"],
            "sources": ["arxiv", "semantic_scholar", "openalex"],
            "time_range": {"start_year": 2020, "end_year": 2026},
            "max_results_per_source": 50,
        }
        p = _write_tmp_json(plan, ".yaml")
        r = validate_search_plan(p, json_output=False)
        assert r["status"] == "PASS", f"Test 1: Expected PASS, got {r['status']}: {r['errors']}"
        print("  [PASS] 1. valid search_plan → PASS")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] 1. valid search_plan: {e}")
        failed += 1
    finally:
        p.unlink(missing_ok=True)

    # Test 2: missing topic → FAIL
    try:
        plan = {
            "search_intent": "novelty_check",
            "must_include": ["test"],
            "sources": ["arxiv"],
            "time_range": {"start_year": 2020, "end_year": 2026},
            "max_results_per_source": 10,
        }
        p = _write_tmp_json(plan, ".yaml")
        r = validate_search_plan(p, json_output=False)
        assert r["status"] == "FAIL", f"Test 2: Expected FAIL, got {r['status']}"
        assert any("topic" in e for e in r["errors"]), f"Test 2: Expected topic error, got {r['errors']}"
        print("  [PASS] 2. missing topic → FAIL")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] 2. missing topic: {e}")
        failed += 1
    finally:
        p.unlink(missing_ok=True)

    # Test 3: unsupported source → FAIL
    try:
        plan = {
            "topic": "test",
            "search_intent": "novelty_check",
            "must_include": ["test"],
            "sources": ["arxiv", "google_scholar"],
            "time_range": {"start_year": 2020, "end_year": 2026},
            "max_results_per_source": 10,
        }
        p = _write_tmp_json(plan, ".yaml")
        r = validate_search_plan(p, json_output=False)
        assert r["status"] == "FAIL", f"Test 3: Expected FAIL, got {r['status']}"
        assert any("google_scholar" in e for e in r["errors"]), f"Test 3: Expected source error, got {r['errors']}"
        print("  [PASS] 3. unsupported source → FAIL")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] 3. unsupported source: {e}")
        failed += 1
    finally:
        p.unlink(missing_ok=True)

    # Test 4: build-search-plan creates valid plan with query_variants → PASS
    try:
        tmp_dir = Path(tempfile.mkdtemp())
        out_path = tmp_dir / "search_plan.yaml"
        r = build_search_plan(
            topic="hidden state trajectory hallucination detection",
            intent="novelty_check",
            must_include=["hallucination detection", "hidden states", "representation trajectory"],
            sources=["arxiv", "openalex", "semantic_scholar"],
            start_year=2020,
            end_year=2026,
            max_results_per_source=50,
            output_path=out_path,
            exclude="generic anomaly detection unrelated to LLMs",
        )
        assert r["status"] == "PASS", f"Test 4: Expected PASS, got {r['status']}: {r.get('errors', '')}"
        assert out_path.exists(), "Test 4: output file should exist"
        plan = json.loads(out_path.read_text(encoding="utf-8"))
        assert "query_variants" in plan, "Test 4: query_variants should be present"
        assert isinstance(plan["query_variants"], list), "Test 4: query_variants should be list"
        assert len(plan["query_variants"]) >= 3, f"Test 4: Expected >= 3 variants, got {len(plan['query_variants'])}"
        assert plan["exclude"] == "generic anomaly detection unrelated to LLMs", "Test 4: exclude should be set"
        # Validate the generated plan passes validate-search-plan
        vr = validate_search_plan(out_path, json_output=False)
        assert vr["status"] == "PASS", f"Test 4: Generated plan should validate PASS, got {vr['status']}: {vr['errors']}"
        print("  [PASS] 4. build-search-plan creates valid plan with query_variants → PASS")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] 4. build-search-plan: {e}")
        failed += 1
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    # Test 5: build-search-plan rejects unsupported source → FAIL
    try:
        tmp_dir = Path(tempfile.mkdtemp())
        out_path = tmp_dir / "bad_plan.yaml"
        r = build_search_plan(
            topic="test",
            intent="novelty_check",
            must_include=["test"],
            sources=["arxiv", "google_scholar"],
            start_year=2020,
            end_year=2026,
            max_results_per_source=10,
            output_path=out_path,
        )
        assert r["status"] == "FAIL", f"Test 5: Expected FAIL, got {r['status']}"
        print("  [PASS] 5. build-search-plan rejects unsupported source → FAIL")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] 5. build-search-plan bad source: {e}")
        failed += 1
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    # Test 6: build-search-plan with start_year > end_year → FAIL, no output file
    try:
        tmp_dir = Path(tempfile.mkdtemp())
        out_path = tmp_dir / "inverted_years.yaml"
        r = build_search_plan(
            topic="test topic",
            intent="novelty_check",
            must_include=["test"],
            sources=["arxiv"],
            start_year=2026,
            end_year=2020,
            max_results_per_source=10,
            output_path=out_path,
        )
        assert r["status"] == "FAIL", f"Test 6: Expected FAIL, got {r['status']}"
        assert not out_path.exists(), f"Test 6: output file should NOT exist on FAIL"
        print("  [PASS] 6. build-search-plan start_year > end_year → FAIL, no output file")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] 6. build-search-plan inverted years: {e}")
        failed += 1
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    # Test 7: build-search-plan with max_results_per_source=0 → FAIL, no output file
    try:
        tmp_dir = Path(tempfile.mkdtemp())
        out_path = tmp_dir / "zero_max.yaml"
        r = build_search_plan(
            topic="test topic",
            intent="novelty_check",
            must_include=["test"],
            sources=["arxiv"],
            start_year=2020,
            end_year=2026,
            max_results_per_source=0,
            output_path=out_path,
        )
        assert r["status"] == "FAIL", f"Test 7: Expected FAIL, got {r['status']}"
        assert not out_path.exists(), f"Test 7: output file should NOT exist on FAIL"
        print("  [PASS] 7. build-search-plan max_results=0 → FAIL, no output file")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] 7. build-search-plan zero max: {e}")
        failed += 1
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    # Test 8: validate-search-plan rejects novelty verdict fields → FAIL
    try:
        plan = {
            "topic": "test",
            "search_intent": "novelty_check",
            "must_include": ["test"],
            "sources": ["arxiv"],
            "time_range": {"start_year": 2020, "end_year": 2026},
            "max_results_per_source": 10,
            "confirmed_novel": True,
        }
        p = _write_tmp_json(plan, ".yaml")
        r = validate_search_plan(p, json_output=False)
        assert r["status"] == "FAIL", f"Test 8: Expected FAIL, got {r['status']}"
        assert any("confirmed_novel" in e for e in r["errors"]), f"Test 8: Expected verdict error, got {r['errors']}"
        print("  [PASS] 8. validate-search-plan rejects novelty verdict fields → FAIL")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] 8. novelty verdict rejection: {e}")
        failed += 1
    finally:
        p.unlink(missing_ok=True)

    # Test 9: build-search-jobs from valid plan → PASS and job_count == sources × query_variants
    try:
        tmp_dir = Path(tempfile.mkdtemp())
        plan_path = tmp_dir / "plan.yaml"
        jobs_path = tmp_dir / "jobs.json"
        plan = {
            "topic": "test topic",
            "search_intent": "novelty_check",
            "must_include": ["term1", "term2"],
            "sources": ["arxiv", "openalex"],
            "time_range": {"start_year": 2020, "end_year": 2026},
            "max_results_per_source": 10,
            "query_variants": ["query A", "query B", "query C"],
        }
        plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
        r = build_search_jobs(plan_path, jobs_path, json_output=False)
        assert r["status"] == "PASS", f"Test 9: Expected PASS, got {r['status']}: {r.get('errors', '')}"
        assert r["job_count"] == 6, f"Test 9: Expected 6 jobs (2 sources × 3 queries), got {r['job_count']}"
        assert jobs_path.exists(), "Test 9: output file should exist"
        # Validate the generated jobs
        vj = validate_search_jobs(jobs_path, json_output=False)
        assert vj["status"] == "PASS", f"Test 9: Jobs should validate PASS, got {vj['status']}: {vj['errors']}"
        print("  [PASS] 9. build-search-jobs from valid plan → PASS, job_count == sources × queries")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] 9. build-search-jobs: {e}")
        failed += 1
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    # Test 10: validate-search-jobs detects duplicate job_id → FAIL
    try:
        data = {
            "schema_version": "search_jobs_v1",
            "source_plan": "test.yaml",
            "topic": "test",
            "search_intent": "novelty_check",
            "job_count": 2,
            "jobs": [
                {"job_id": "job_arxiv_dup1", "source": "arxiv", "query": "q1",
                 "time_range": {"start_year": 2020, "end_year": 2026}, "max_results": 10,
                 "status": "planned", "network_required": True,
                 "execution_result": "not_started", "raw_output_file": "", "error": "", "notes": ""},
                {"job_id": "job_arxiv_dup1", "source": "arxiv", "query": "q2",
                 "time_range": {"start_year": 2020, "end_year": 2026}, "max_results": 10,
                 "status": "planned", "network_required": True,
                 "execution_result": "not_started", "raw_output_file": "", "error": "", "notes": ""},
            ]
        }
        r = validate_search_jobs_dict(data)
        assert r["status"] == "FAIL", f"Test 10: Expected FAIL, got {r['status']}"
        assert any("duplicate job_id" in e for e in r["errors"]), f"Test 10: Expected dup error, got {r['errors']}"
        print("  [PASS] 10. validate-search-jobs detects duplicate job_id → FAIL")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] 10. duplicate job_id: {e}")
        failed += 1

    # Test 11: validate-search-jobs detects invalid source → FAIL
    try:
        data = {
            "schema_version": "search_jobs_v1",
            "source_plan": "test.yaml",
            "topic": "test",
            "search_intent": "novelty_check",
            "job_count": 1,
            "jobs": [
                {"job_id": "job_bad_1", "source": "google_scholar", "query": "q1",
                 "time_range": {"start_year": 2020, "end_year": 2026}, "max_results": 10,
                 "status": "planned", "network_required": True,
                 "execution_result": "not_started", "raw_output_file": "", "error": "", "notes": ""},
            ]
        }
        r = validate_search_jobs_dict(data)
        assert r["status"] == "FAIL", f"Test 11: Expected FAIL, got {r['status']}"
        assert any("google_scholar" in e for e in r["errors"]), f"Test 11: Expected source error, got {r['errors']}"
        print("  [PASS] 11. validate-search-jobs detects invalid source → FAIL")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] 11. invalid source: {e}")
        failed += 1

    # Test 12: init-run-skeleton creates search_jobs.json and it validates PASS
    try:
        tmp_dir = Path(tempfile.mkdtemp())
        run_dir = tmp_dir / "test_run"
        r = init_run_skeleton(run_dir, "test topic", "novelty_check")
        assert r["status"] == "created", f"Test 12: Expected created, got {r['status']}"
        expected_files = ["search_plan.yaml", "search_jobs.json", "raw_results.jsonl", "candidates.jsonl",
                          "top_k.md", "acquisition_status.json", "manual_acquisition_queue.md"]
        for fname in expected_files:
            assert (run_dir / fname).exists(), f"Test 12: Missing {fname}"
        # Verify search_plan validates PASS
        vr = validate_search_plan(run_dir / "search_plan.yaml", json_output=False)
        assert vr["status"] == "PASS", f"Test 12: search_plan should validate PASS, got {vr['status']}: {vr['errors']}"
        # Verify search_jobs validates PASS
        vj = validate_search_jobs(run_dir / "search_jobs.json", json_output=False)
        assert vj["status"] == "PASS", f"Test 12: search_jobs should validate PASS, got {vj['status']}: {vj['errors']}"
        # Verify content
        plan_content = json.loads((run_dir / "search_plan.yaml").read_text(encoding="utf-8"))
        assert plan_content["topic"] == "test topic"
        assert len(plan_content["must_include"]) > 0, "Test 12: must_include should be non-empty"
        print("  [PASS] 12. init-run-skeleton creates search_jobs.json and it validates PASS")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] 12. init-run-skeleton: {e}")
        failed += 1
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    # Test 13: valid acquisition_status → PASS
    try:
        acq = {
            "papers": [{
                "paper_id": "p1",
                "title": "Test Paper",
                "doi": "10.1234/test",
                "arxiv_id": "",
                "openalex_id": "",
                "full_text_status": "available",
                "source_type": "pdf",
                "parse_status": "parsed",
                "parse_quality": "high",
                "evidence_gap": "",
            }]
        }
        p = _write_tmp_json(acq)
        r = validate_acquisition_status(p, json_output=False)
        assert r["status"] == "PASS", f"Test 13: Expected PASS, got {r['status']}: {r['errors']}"
        print("  [PASS] 13. valid acquisition_status → PASS")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] 13. valid acquisition_status: {e}")
        failed += 1
    finally:
        p.unlink(missing_ok=True)

    # Test 14: metadata_only with empty evidence_gap → FAIL
    try:
        acq = {
            "papers": [{
                "paper_id": "p2",
                "title": "Paywalled Paper",
                "full_text_status": "metadata_only",
                "source_type": "metadata",
                "parse_status": "not_applicable",
                "parse_quality": "unknown",
                "evidence_gap": "",
            }]
        }
        p = _write_tmp_json(acq)
        r = validate_acquisition_status(p, json_output=False)
        assert r["status"] == "FAIL", f"Test 14: Expected FAIL, got {r['status']}"
        assert any("evidence_gap" in e for e in r["errors"]), f"Test 14: Expected evidence_gap error, got {r['errors']}"
        print("  [PASS] 14. metadata_only empty evidence_gap → FAIL")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] 14. metadata_only empty evidence_gap: {e}")
        failed += 1
    finally:
        p.unlink(missing_ok=True)

    # Test 15: build-manual-queue writes queue for manual_required paper
    try:
        tmp_dir = Path(tempfile.mkdtemp())
        acq = {
            "papers": [
                {
                    "paper_id": "p3",
                    "title": "Important Prior Work",
                    "doi": "10.1234/important",
                    "arxiv_id": "2301.00001",
                    "openalex_id": "",
                    "full_text_status": "manual_required",
                    "source_type": "manual",
                    "parse_status": "not_started",
                    "parse_quality": "unknown",
                    "evidence_gap": "likely closest prior work, need method section",
                },
                {
                    "paper_id": "p4",
                    "title": "Available Paper",
                    "full_text_status": "available",
                    "source_type": "pdf",
                    "parse_status": "parsed",
                    "parse_quality": "high",
                    "evidence_gap": "",
                },
            ]
        }
        acq_path = tmp_dir / "acquisition_status.json"
        acq_path.write_text(json.dumps(acq, indent=2), encoding="utf-8")
        out_path = tmp_dir / "manual_acquisition_queue.md"
        r = build_manual_queue(acq_path, out_path)
        assert r["status"] == "built", f"Test 15: Expected built, got {r['status']}"
        assert r["queued_count"] == 1, f"Test 15: Expected 1 queued, got {r['queued_count']}"
        content = out_path.read_text(encoding="utf-8")
        assert "Important Prior Work" in content, "Test 15: Expected paper title in queue"
        assert "Available Paper" not in content, "Test 15: Should not include available paper"
        print("  [PASS] 15. build-manual-queue for manual_required paper")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] 15. build-manual-queue: {e}")
        failed += 1
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    # Test 16: summarize-run detects search_plan_valid, search_jobs_valid, search_job_count
    try:
        tmp_dir = Path(tempfile.mkdtemp())
        run_dir = tmp_dir / "summary_run"
        init_run_skeleton(run_dir, "test", "novelty_check")

        # Add a raw result
        raw_rec = {
            "source": "arxiv", "title": "Paper A", "year": 2024,
            "url": "https://arxiv.org/abs/1234", "evidence_origin": "api_export",
            "authors": ["Author A"], "abstract": "Test abstract",
            "arxiv_id": "1234.5678"
        }
        with open(run_dir / "raw_results.jsonl", "w", encoding="utf-8") as f:
            f.write(json.dumps(raw_rec) + "\n")

        # Update acquisition status with papers
        acq = {
            "papers": [
                {"paper_id": "p1", "title": "A", "full_text_status": "available"},
                {"paper_id": "p2", "title": "B", "full_text_status": "manual_required", "evidence_gap": "need"},
                {"paper_id": "p3", "title": "C", "full_text_status": "metadata_only", "evidence_gap": "gap"},
            ]
        }
        (run_dir / "acquisition_status.json").write_text(json.dumps(acq, indent=2), encoding="utf-8")

        r = summarize_run(run_dir, json_output=False)
        assert r["search_plan_present"] is True, "Test 16: plan should be present"
        assert r["search_plan_valid"] is True, f"Test 16: plan should be valid"
        assert r["search_jobs_present"] is True, "Test 16: jobs should be present"
        assert r["search_jobs_valid"] is True, f"Test 16: jobs should be valid"
        assert r["search_job_count"] > 0, f"Test 16: job_count > 0, got {r['search_job_count']}"
        assert r["planned_job_count"] > 0, f"Test 16: planned_job_count > 0"
        assert r["raw_result_count"] == 1, f"Test 16: Expected 1 raw, got {r['raw_result_count']}"
        assert r["manual_required_count"] == 1, f"Test 16: Expected 1 manual_required, got {r['manual_required_count']}"
        assert r["status"] == "WARN", f"Test 16: Expected WARN (no candidates), got {r['status']}"
        print("  [PASS] 16. summarize-run detects search_plan_valid, search_jobs_valid, search_job_count")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] 16. summarize-run: {e}")
        failed += 1
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print(f"\nSelf-test results: {passed} passed, {failed} failed")
    return failed == 0


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

    sp = sub.add_parser("validate-search-plan", help="Validate search plan JSON")
    sp.add_argument("--file", required=True, help="Path to search_plan.yaml (JSON)")
    sp.add_argument("--json", action="store_true", help="Output JSON")

    bsp = sub.add_parser("build-search-plan", help="Build a search plan with query variants (no network)")
    bsp.add_argument("--topic", required=True, help="Research topic")
    bsp.add_argument("--intent", required=True, help="Search intent")
    bsp.add_argument("--must-include", action="append", required=True, help="Must-include term (repeatable)")
    bsp.add_argument("--source", action="append", required=True, help="Source to search (repeatable)")
    bsp.add_argument("--start-year", type=int, required=True, help="Start year")
    bsp.add_argument("--end-year", type=int, required=True, help="End year")
    bsp.add_argument("--max-results-per-source", type=int, required=True, help="Max results per source")
    bsp.add_argument("--output", required=True, help="Output path for search_plan.yaml")
    bsp.add_argument("--exclude", default="", help="Exclusion terms")
    bsp.add_argument("--json", action="store_true", help="Output JSON")

    bsj = sub.add_parser("build-search-jobs", help="Expand search plan into explicit search jobs (no network)")
    bsj.add_argument("--plan", required=True, help="Path to search_plan.yaml")
    bsj.add_argument("--output", required=True, help="Output path for search_jobs.json")
    bsj.add_argument("--json", action="store_true", help="Output JSON")

    vsj = sub.add_parser("validate-search-jobs", help="Validate search_jobs.json schema")
    vsj.add_argument("--file", required=True, help="Path to search_jobs.json")
    vsj.add_argument("--json", action="store_true", help="Output JSON")

    ir = sub.add_parser("init-run-skeleton", help="Create empty run skeleton")
    ir.add_argument("--run-dir", required=True, help="Target run directory")
    ir.add_argument("--topic", required=True, help="Research topic")
    ir.add_argument("--intent", required=True, help="Search intent")

    va = sub.add_parser("validate-acquisition-status", help="Validate acquisition_status.json")
    va.add_argument("--file", required=True, help="Path to acquisition_status.json")
    va.add_argument("--json", action="store_true", help="Output JSON")

    mq = sub.add_parser("build-manual-queue", help="Build manual acquisition queue")
    mq.add_argument("--acquisition-status", required=True, help="Path to acquisition_status.json")
    mq.add_argument("--output", required=True, help="Output path for manual_acquisition_queue.md")

    sr = sub.add_parser("summarize-run", help="Summarize a literature search run")
    sr.add_argument("--run-dir", required=True, help="Run directory to summarize")
    sr.add_argument("--json", action="store_true", help="Output JSON")

    parser.add_argument("--self-test", action="store_true", help="Run self-tests")

    args = parser.parse_args()

    if args.self_test:
        ok = _self_test()
        sys.exit(0 if ok else 1)

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
    elif args.command == "validate-search-plan":
        r = validate_search_plan(Path(args.file), args.json)
        if r["status"] == "FAIL":
            sys.exit(1)
    elif args.command == "build-search-plan":
        r = build_search_plan(
            topic=args.topic,
            intent=args.intent,
            must_include=args.must_include,
            sources=args.source,
            start_year=args.start_year,
            end_year=args.end_year,
            max_results_per_source=args.max_results_per_source,
            output_path=Path(args.output),
            exclude=args.exclude,
            json_output=args.json,
        )
        if r["status"] != "PASS":
            sys.exit(1)
    elif args.command == "build-search-jobs":
        r = build_search_jobs(Path(args.plan), Path(args.output), json_output=args.json)
        if r["status"] != "PASS":
            sys.exit(1)
    elif args.command == "validate-search-jobs":
        r = validate_search_jobs(Path(args.file), args.json)
        if r["status"] == "FAIL":
            sys.exit(1)
    elif args.command == "init-run-skeleton":
        r = init_run_skeleton(Path(args.run_dir), args.topic, args.intent)
        print(json.dumps(r, indent=2))
    elif args.command == "validate-acquisition-status":
        r = validate_acquisition_status(Path(args.file), args.json)
        if r["status"] == "FAIL":
            sys.exit(1)
    elif args.command == "build-manual-queue":
        r = build_manual_queue(Path(args.acquisition_status), Path(args.output))
        print(json.dumps(r, indent=2))
    elif args.command == "summarize-run":
        summarize_run(Path(args.run_dir), args.json)


if __name__ == "__main__":
    main()
