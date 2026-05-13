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
    python tools/literature_evidence_landing.py validate-job-results --file <path> [--json]
    python tools/literature_evidence_landing.py normalize-job-results --input <path> --output <path> [--json]
    python tools/literature_evidence_landing.py summarize-job-results --file <path> [--json]
    python tools/literature_evidence_landing.py run-openalex-job --job-id <id> --search-jobs <path> --output <path> [--per-page <n>] [--mailto <email>] [--json]
    python tools/literature_evidence_landing.py run-openalex-jobs --search-jobs <path> --output <path> [--max-jobs <n>] [--per-page <n>] [--mailto <email>] [--overwrite] [--json]
    python tools/literature_evidence_landing.py run-openalex-pipeline --topic <t> --intent <i> --must-include <m> --run-dir <dir> [--start-year <y>] [--end-year <y>] [--max-results-per-source <n>] [--max-jobs <n>] [--per-page <n>] [--top-k <n>] [--overwrite] [--exclude <e>] [--mailto <email>] [--dry-run] [--json]
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
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ALLOWED_SOURCES = frozenset([
    "arxiv", "semantic_scholar", "openalex", "crossref", "unpaywall",
    "openreview", "conference_site", "author_homepage", "github", "webfetch", "manual"
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

VALID_JOB_RESULT_STATUSES = frozenset([
    "success", "empty", "failed", "rate_limited", "auth_failed", "blocked"
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

    # Read must_include from search_plan.yaml if available
    must_include = []
    plan_path = run_dir / "search_plan.yaml"
    if plan_path.exists():
        try:
            plan_data = json.loads(plan_path.read_text(encoding="utf-8", errors="ignore"))
            must_include = plan_data.get("must_include", [])
        except Exception:
            pass

    # Compute normalized titles, canonical identities, and relevance for all
    enriched = []
    for idx, rec in enumerate(records):
        nt = _normalize_title(rec.get("title", ""))
        yr = str(rec.get("year", ""))
        identity = _canonical_identity(rec, nt, yr)
        stable_ids = _build_stable_ids(rec)

        # Compute relevance scoring
        relevance = _score_text_relevance(
            rec.get("title", ""),
            rec.get("abstract", ""),
            must_include,
        )

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
            "relevance": relevance,
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
        relevance = entry["relevance"]
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
            "relevance_score": relevance["relevance_score"],
            "relevance_label": relevance["relevance_label"],
            "relevance_reasons": relevance["relevance_reasons"],
            "relevance_flags": relevance["relevance_flags"],
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


# ---- Relevance scoring ----

_HALLUCINATION_GROUP = frozenset([
    "hallucination", "hallucinations", "confabulation", "factuality", "factual",
    "truthfulness", "untruthful", "misinformation", "faithfulness", "faithful",
    "hallucinate", "hallucinated", "fabrication", "inaccurate", "inaccuracy",
])

_LLM_GROUP = frozenset([
    "llm", "llms", "large language model", "language model", "foundation model",
    "generative ai", "generative model", "neural language model", "transformer",
    "chatgpt", "gpt", "bert", "llama", "mistral",
])

_INTERNAL_STATE_GROUP = frozenset([
    "hidden state", "hidden states", "internal state", "internal states",
    "activation", "activations", "representation", "representations",
    "layer", "layerwise", "trajectory", "embedding", "embeddings",
    "neural activation", "model state", "latent", "intermediate representation",
])

_TOKEN_GROUP = frozenset([
    "token", "tokens", "token-level", "per-token", "decoding step",
    "generation step", "logit", "logits", "token probability", "token uncertainty",
    "token-level detection", "word-level",
])

_DETECTION_GROUP = frozenset([
    "detect", "detection", "detector", "anomaly", "outlier", "uncertainty",
    "confidence", "estimation", "monitor", "monitoring", "identification",
    "classification", "recognition",
])

_NEGATIVE_GROUP = frozenset([
    "metaverse", "geriatric", "agriculture", "forecasting", "self-adaptive",
    "personal agents", "prompt engineering", "medical", "healthcare",
    "robotics decision-making", "autonomous systems", "sensor network",
    "smart city", "edge computing", "iot", "internet of things",
])


def _score_text_relevance(title: str, abstract: str, must_include: list[str]) -> dict:
    """Deterministic keyword/concept relevance scoring. No model, no semantic inference."""
    text = f"{title} {abstract}".lower()

    score = 0
    reasons = []
    flags = []

    # Positive scoring
    hallucination_hits = sum(1 for term in _HALLUCINATION_GROUP if term in text)
    if hallucination_hits > 0:
        score += 3
        reasons.append(f"hallucination_group matched ({hallucination_hits} terms)")

    llm_hits = sum(1 for term in _LLM_GROUP if term in text)
    if llm_hits > 0:
        score += 2
        reasons.append(f"llm_group matched ({llm_hits} terms)")

    internal_hits = sum(1 for term in _INTERNAL_STATE_GROUP if term in text)
    if internal_hits > 0:
        score += 3
        reasons.append(f"internal_state_group matched ({internal_hits} terms)")

    token_hits = sum(1 for term in _TOKEN_GROUP if term in text)
    if token_hits > 0:
        score += 2
        reasons.append(f"token_group matched ({token_hits} terms)")

    detection_hits = sum(1 for term in _DETECTION_GROUP if term in text)
    if detection_hits > 0:
        score += 2
        reasons.append(f"detection_group matched ({detection_hits} terms)")

    # must_include term matching
    must_hits = 0
    for term in must_include:
        if term.lower() in text:
            must_hits += 1
    if must_hits > 0:
        bonus = min(must_hits, 3)
        score += bonus
        reasons.append(f"must_include matched ({must_hits}/{len(must_include)})")

    # Negative scoring
    negative_hits = sum(1 for term in _NEGATIVE_GROUP if term in text)
    if negative_hits > 0:
        penalty = negative_hits * 2
        score -= penalty
        reasons.append(f"negative_terms penalized (-{penalty})")
        flags.append(f"negative_match_{negative_hits}")

    # Determine label
    has_core = hallucination_hits > 0 or internal_hits > 0
    has_support = llm_hits > 0 or detection_hits > 0

    if score >= 7 and has_core and has_support:
        label = "high"
    elif score >= 4:
        label = "medium"
    else:
        label = "low"

    return {
        "relevance_score": score,
        "relevance_label": label,
        "relevance_reasons": reasons,
        "relevance_flags": flags,
    }


def _compute_ranking_score(relevance: dict, metadata_score: int, year_int: int) -> tuple[int, int, int]:
    """Combine relevance + metadata + recency into a single ranking tuple (higher = better)."""
    label_bonus = {"high": 100, "medium": 50, "low": 0}
    rel_score = relevance["relevance_score"] + label_bonus.get(relevance["relevance_label"], 0)
    return (rel_score, metadata_score, year_int)


# ---- Top-K building ----

def _score_candidate(rec: dict) -> tuple[int, int, int, str]:
    """Score a canonical candidate. Returns (ranking_score, rel_score, year_int, title_lower)."""
    # Metadata completeness score (same as before)
    meta_score = 0
    stable_ids = rec.get("stable_ids", {})
    has_stable = any(stable_ids.get(k) for k in ("doi", "arxiv_id", "semantic_scholar_id", "openalex_id"))
    if has_stable:
        meta_score += 2
    else:
        meta_score -= 1

    if rec.get("abstract", "").strip():
        meta_score += 2
    else:
        meta_score -= 2

    if rec.get("retrieved_at"):
        meta_score += 1

    source = rec.get("source", "")
    if source in ("arxiv", "openreview", "openalex"):
        meta_score += 1

    if rec.get("authors"):
        meta_score += 1

    if rec.get("venue"):
        meta_score += 1

    if source == "manual" and not rec.get("url", "").strip():
        meta_score -= 1

    try:
        year_int = int(str(rec.get("year", "")).strip())
    except (ValueError, TypeError):
        year_int = 0

    # Relevance scoring from candidate fields
    relevance_label = rec.get("relevance_label", "low")
    relevance_score = rec.get("relevance_score", 0)

    ranking_score_tuple = _compute_ranking_score(
        {"relevance_score": relevance_score, "relevance_label": relevance_label},
        meta_score,
        year_int,
    )

    title_lower = rec.get("title", "").lower().strip()
    return (ranking_score_tuple[0], relevance_score, year_int, title_lower)


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

    # Score all canonical candidates
    scored = []
    for rec in canonical:
        ranking_score, rel_score, year_int, title_lower = _score_candidate(rec)
        scored.append((ranking_score, rel_score, year_int, title_lower, rec))

    # Sort by ranking score (relevance + metadata + recency)
    scored.sort(key=lambda x: (-x[0], -x[1], -x[2], x[3]))

    # Split into high/medium/low by relevance label
    high_rel = [(s, r, y, t, rec) for s, r, y, t, rec in scored if rec.get("relevance_label") == "high"]
    med_rel = [(s, r, y, t, rec) for s, r, y, t, rec in scored if rec.get("relevance_label") == "medium"]
    low_rel = [(s, r, y, t, rec) for s, r, y, t, rec in scored if rec.get("relevance_label") == "low"]

    # Fill top_k: high first, then medium, then low only if not enough
    top_k_records = []
    for bucket in (high_rel, med_rel, low_rel):
        for entry in bucket:
            if len(top_k_records) < k:
                top_k_records.append(entry)

    filtered_low = [rec for _, _, _, _, rec in low_rel if rec not in [e[4] for e in top_k_records]]

    dup_of_counter: dict[str, int] = {}
    for rec in duplicates:
        canonical_id = rec.get("duplicate_of", "")
        if canonical_id:
            dup_of_counter[canonical_id] = dup_of_counter.get(canonical_id, 0) + 1

    output_path = run_dir / "top_k.md"
    _write_top_k_md(output_path, top_k_records, filtered_low, duplicates, dup_of_counter, len(canonical), len(records), k)

    print(f"Built top_k={k} from {len(records)} total / {len(canonical)} canonical -> {output_path}")
    print(f"  High relevance: {len(high_rel)}, Medium: {len(med_rel)}, Low: {len(low_rel)}")
    print(f"  Selected: {len(top_k_records)}, Filtered low: {len(filtered_low)}")

    result = {
        "status": "built",
        "total": len(records),
        "canonical": len(canonical),
        "duplicates": len(duplicates),
        "top_k": len(top_k_records),
        "high_relevance": len(high_rel),
        "medium_relevance": len(med_rel),
        "low_relevance": len(low_rel),
        "filtered_low": len(filtered_low),
        "output": str(output_path),
    }
    if json_output:
        print(json.dumps(result, indent=2))
    return result


def _write_top_k_md(path: Path, top_k_records: list, filtered_low: list,
                    duplicates: list, dup_of_counter: dict[str, int],
                    canonical_count: int, total_count: int, k: int) -> None:
    lines = [
        "# Top-K Literature Evidence",
        "",
        "Status: populated_by_tool",
        "",
        "## Search Summary",
        f"- Source file: candidates.jsonl",
        f"- Generated by: tools/literature_evidence_landing.py build-top-k",
        "- Selection method: deterministic relevance scoring (keyword/concept matching) + metadata completeness + recency",
        "- Relevance scoring: keyword/concept based only, not semantic judgment",
        f"- Total candidates: {total_count}",
        f"- Canonical candidates: {canonical_count}",
        f"- Duplicate records: {len(duplicates)}",
        f"- Selected top_k: {len(top_k_records)}",
        f"- Filtered low-relevance: {len(filtered_low)}",
        "- Warning: This file is literature evidence summary, not a novelty verdict.",
        "",
        "## Candidate Papers",
    ]

    for rank, (ranking_score, rel_score, year_int, title_lower, rec) in enumerate(top_k_records, 1):
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

        relevance_label = rec.get("relevance_label", "unknown")
        relevance_score = rec.get("relevance_score", 0)
        relevance_reasons = rec.get("relevance_reasons", [])

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
            f"relevance_score: {relevance_score}",
            f"relevance_label: {relevance_label}",
            f"relevance_reasons: {', '.join(relevance_reasons) if relevance_reasons else 'none'}",
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

    # Filtered low-relevance candidates section
    if filtered_low:
        lines.extend([
            "",
            "## Filtered Low-Relevance Candidates",
            f"- Total filtered: {len(filtered_low)}",
            "- These papers were excluded from top-k due to low relevance score.",
            "- They remain in candidates.jsonl for completeness.",
        ])
        for rec in filtered_low:
            title = rec.get("title", "")
            label = rec.get("relevance_label", "unknown")
            score = rec.get("relevance_score", 0)
            reasons = rec.get("relevance_reasons", [])
            lines.append(f"  - [{label}, score={score}] {title}")
            if reasons:
                lines.append(f"    reasons: {', '.join(reasons)}")

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
    """Deterministic query variant generation from topic + must_include. No model, no network.
    Produces focused variants that combine core concept groups."""
    variants = []
    seen = set()

    def _add(q: str):
        q = q.strip()
        if q and q.lower() not in seen:
            seen.add(q.lower())
            variants.append(q)

    # Core concept groups for this research domain
    hallucination_terms = ["hallucination detection", "factuality detection", "truthfulness detection",
                           "hallucination uncertainty"]
    internal_terms = ["hidden states", "internal states", "activations", "representations",
                      "representation trajectory", "layerwise representations"]
    token_terms = ["token-level", "per-token", "token uncertainty", "generation step"]
    detection_terms = ["anomaly detection", "outlier detection", "confidence estimation",
                       "uncertainty estimation"]
    model_terms = ["LLM", "language model"]

    # 1. Topic itself
    _add(topic)

    # 2. must_include terms combined
    if must_include:
        _add(" ".join(must_include))

    # 3. Core combinations: hallucination × internal × model
    for h in hallucination_terms[:2]:
        for i in internal_terms[:2]:
            for m in model_terms[:1]:
                _add(f"{m} {h} {i}")

    # 4. Token-level hallucination combinations
    for t in token_terms[:2]:
        for h in hallucination_terms[:2]:
            _add(f"{t} {h} hidden states")

    # 5. Detection/anomaly with internal states
    for d in detection_terms[:2]:
        for i in internal_terms[:2]:
            _add(f"LLM hallucination {d} {i}")

    # 6. Pair combinations of must_include terms (limited)
    for i, a in enumerate(must_include):
        for b in must_include[i + 1:]:
            _add(f"{a} {b}")

    # 7. Shortened topic + key terms
    topic_words = topic.split()
    if len(topic_words) > 3 and must_include:
        _add(" ".join(topic_words[:3]) + " hidden states")

    # Limit to 12 variants
    return variants[:12]


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
    "verdict", "novelty_verdict", "confirmed_novel", "already_done",
    "likely_incremental", "potentially_novel", "no_prior_work"
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
    (run_dir / "job_results.jsonl").write_text("", encoding="utf-8")

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
        "search_plan.yaml", "search_jobs.json", "job_results.jsonl",
        "raw_results.jsonl", "candidates.jsonl",
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

    # Job results
    job_results_path = run_dir / "job_results.jsonl"
    job_results_present = job_results_path.exists()
    job_results_valid = False
    job_result_count = 0
    successful_job_result_count = 0
    failed_job_result_count = 0
    total_raw_records_from_job_results = 0
    if job_results_present:
        try:
            jr_records, jr_parse_errors = _parse_jsonl(job_results_path)
            if not jr_parse_errors:
                vr_jr = validate_job_results_dict(jr_records)
                job_results_valid = vr_jr["status"] == "PASS"
                job_result_count = len(jr_records)
                for rec in jr_records:
                    if rec.get("status") == "success":
                        successful_job_result_count += 1
                        total_raw_records_from_job_results += rec.get("raw_record_count", 0)
                    elif rec.get("status") in ("failed", "rate_limited", "auth_failed", "blocked"):
                        failed_job_result_count += 1
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
        "job_results_present": job_results_present,
        "job_results_valid": job_results_valid,
        "job_result_count": job_result_count,
        "successful_job_result_count": successful_job_result_count,
        "failed_job_result_count": failed_job_result_count,
        "total_raw_records_from_job_results": total_raw_records_from_job_results,
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


# ---- Source adapter job result validation ----

def _find_forbidden_verdict_fields(obj, path: str = "") -> list[str]:
    """Recursively find NOVELTY_VERDICT_FIELDS in any nested dict/list structure.
    Returns list of paths where forbidden fields are found."""
    found = []
    if isinstance(obj, dict):
        for key in obj:
            current_path = f"{path}.{key}" if path else key
            if key in NOVELTY_VERDICT_FIELDS:
                found.append(current_path)
            found.extend(_find_forbidden_verdict_fields(obj[key], current_path))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            current_path = f"{path}[{i}]"
            found.extend(_find_forbidden_verdict_fields(item, current_path))
    return found


def validate_job_results_dict(records: list[dict]) -> dict:
    """Validate a list of source_job_result_v1 records in memory. No file I/O, no network."""
    errors = []

    if not isinstance(records, list):
        return {"status": "FAIL", "errors": ["job_results must be a list"]}

    if len(records) == 0:
        return {"status": "PASS", "errors": [], "total_jobs": 0}

    for idx, rec in enumerate(records):
        prefix = f"job_results[{idx}]"

        if not isinstance(rec, dict):
            errors.append(f"{prefix}: must be a dict")
            continue

        # schema_version
        if rec.get("schema_version") != "source_job_result_v1":
            errors.append(f"{prefix}: schema_version must be 'source_job_result_v1', got '{rec.get('schema_version')}'")

        # job_id non-empty
        if not rec.get("job_id") or not str(rec["job_id"]).strip():
            errors.append(f"{prefix}: job_id is empty")

        # source in ALLOWED_SOURCES (which now covers VALID_PLAN_SOURCES + webfetch)
        source = rec.get("source", "")
        if not source:
            errors.append(f"{prefix}: source is empty")
        elif source not in ALLOWED_SOURCES:
            errors.append(f"{prefix}: source '{source}' not in allowed list: {sorted(ALLOWED_SOURCES)}")

        # query non-empty
        if not rec.get("query") or not str(rec["query"]).strip():
            errors.append(f"{prefix}: query is empty")

        # status validation
        status = rec.get("status", "")
        if not status:
            errors.append(f"{prefix}: status is empty")
        elif status not in VALID_JOB_RESULT_STATUSES:
            errors.append(f"{prefix}: status '{status}' not in {sorted(VALID_JOB_RESULT_STATUSES)}")

        # retrieved_at non-empty
        if not rec.get("retrieved_at") or not str(rec["retrieved_at"]).strip():
            errors.append(f"{prefix}: retrieved_at is empty")

        # raw_record_count must equal len(records)
        raw_record_count = rec.get("raw_record_count")
        record_list = rec.get("records", [])
        if not isinstance(record_list, list):
            errors.append(f"{prefix}: records must be a list")
            record_list = []
        if not isinstance(raw_record_count, int):
            errors.append(f"{prefix}: raw_record_count must be an integer")
        elif raw_record_count != len(record_list):
            errors.append(f"{prefix}: raw_record_count ({raw_record_count}) != len(records) ({len(record_list)})")

        # http_status: optional, but if present must be integer
        http_status = rec.get("http_status")
        if http_status is not None and not isinstance(http_status, int):
            errors.append(f"{prefix}: http_status must be an integer if present")

        # Status-specific rules
        if status == "success":
            if isinstance(raw_record_count, int) and raw_record_count == 0:
                errors.append(f"{prefix}: status=success but raw_record_count=0")
            err = rec.get("error", "")
            if err:
                errors.append(f"{prefix}: status=success but error is non-empty: '{err}'")
            # Validate each record has required fields
            for ri, record in enumerate(record_list):
                if not isinstance(record, dict):
                    errors.append(f"{prefix}: records[{ri}] must be a dict")
                    continue
                for field in ("source", "title", "year", "url", "evidence_origin"):
                    if not record.get(field):
                        errors.append(f"{prefix}: records[{ri}] missing required field: {field}")
        elif status == "empty":
            if isinstance(raw_record_count, int) and raw_record_count != 0:
                errors.append(f"{prefix}: status=empty but raw_record_count != 0")
            if record_list:
                errors.append(f"{prefix}: status=empty but records is non-empty")
        elif status in ("failed", "rate_limited", "auth_failed", "blocked"):
            if isinstance(raw_record_count, int) and raw_record_count != 0:
                errors.append(f"{prefix}: status={status} but raw_record_count != 0")
            if record_list:
                errors.append(f"{prefix}: status={status} but records is non-empty")
            err = rec.get("error", "")
            if not err or not str(err).strip():
                errors.append(f"{prefix}: status={status} but error is empty")

        # No novelty verdict fields allowed anywhere in the record (recursive)
        forbidden_paths = _find_forbidden_verdict_fields(rec, prefix)
        for fp in forbidden_paths:
            errors.append(f"{prefix}: novelty verdict field not allowed at: {fp}")

    status_out = "PASS" if not errors else "FAIL"
    return {"status": status_out, "errors": errors, "total_jobs": len(records)}


def validate_job_results(file_path: Path, json_output: bool) -> dict:
    """Validate a job_results.jsonl file. No network, no model."""
    if not file_path.exists():
        result = {"status": "FAIL", "errors": ["file not found"], "total_jobs": 0}
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    records, parse_errors = _parse_jsonl(file_path)
    if parse_errors:
        result = {"status": "FAIL", "errors": [e.get("message", str(e)) for e in parse_errors], "total_jobs": 0}
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    result = validate_job_results_dict(records)
    if json_output:
        print(json.dumps(result, indent=2))
    else:
        print(f"Status: {result['status']}")
        print(f"Total jobs: {result['total_jobs']}")
        if result["errors"]:
            print(f"Errors ({len(result['errors'])}):")
            for e in result["errors"][:10]:
                print(f"  - {e}")
    return result


def normalize_job_results(input_path: Path, output_path: Path, json_output: bool) -> dict:
    """Convert successful job results into raw_results.jsonl records.
    Fail-closed: validates job_results first, then validates converted records.
    No network, no model."""
    # Step 1: validate job_results
    if not input_path.exists():
        result = {"status": "FAIL", "errors": ["input file not found"]}
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    records, parse_errors = _parse_jsonl(input_path)
    if parse_errors:
        result = {"status": "FAIL", "errors": [e.get("message", str(e)) for e in parse_errors]}
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    vr = validate_job_results_dict(records)
    if vr["status"] != "PASS":
        result = {"status": "FAIL", "errors": vr["errors"]}
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    # Step 2: extract success records into raw format
    raw_records = []
    for rec in records:
        if rec.get("status") != "success":
            continue
        for paper in rec.get("records", []):
            raw = {
                "source": paper.get("source", ""),
                "title": paper.get("title", ""),
                "authors": paper.get("authors", []),
                "year": paper.get("year", ""),
                "url": paper.get("url", ""),
                "doi": paper.get("doi", ""),
                "arxiv_id": paper.get("arxiv_id", ""),
                "semantic_scholar_id": paper.get("semantic_scholar_id", ""),
                "openalex_id": paper.get("openalex_id", ""),
                "abstract": paper.get("abstract", ""),
                "venue": paper.get("venue", ""),
                "retrieved_at": paper.get("retrieved_at", ""),
                "evidence_origin": paper.get("evidence_origin", "api_export"),
                "notes": paper.get("notes", ""),
            }
            raw_records.append(raw)

    if not raw_records:
        result = {"status": "FAIL", "errors": ["no success records to normalize"]}
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    # Step 3: validate converted raw records
    raw_errors, raw_warnings, _ = _validate_records(raw_records)
    if raw_errors:
        result = {"status": "FAIL", "errors": [f"converted raw records invalid: {e}" for e in raw_errors[:5]]}
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    # Step 4: write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_jsonl(output_path, raw_records)

    result = {
        "status": "PASS",
        "output": str(output_path),
        "total_job_results": len(records),
        "success_job_results": sum(1 for r in records if r.get("status") == "success"),
        "normalized_records": len(raw_records),
        "warnings": len(raw_warnings),
    }
    if json_output:
        print(json.dumps(result, indent=2))
    else:
        print(f"Status: PASS")
        print(f"Normalized {len(raw_records)} record(s) from {result['success_job_results']} success job(s) -> {output_path}")
    return result


def summarize_job_results(file_path: Path, json_output: bool) -> dict:
    """Summarize job_results.jsonl. No network, no model, no novelty judgment."""
    if not file_path.exists():
        result = {
            "status": "FAIL",
            "total_jobs": 0, "success_count": 0, "empty_count": 0,
            "failed_count": 0, "rate_limited_count": 0, "auth_failed_count": 0,
            "blocked_count": 0, "total_raw_records": 0, "sources": {}, "errors": ["file not found"],
        }
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    records, parse_errors = _parse_jsonl(file_path)
    if parse_errors:
        result = {
            "status": "FAIL",
            "total_jobs": 0, "success_count": 0, "empty_count": 0,
            "failed_count": 0, "rate_limited_count": 0, "auth_failed_count": 0,
            "blocked_count": 0, "total_raw_records": 0, "sources": {},
            "errors": [e.get("message", str(e)) for e in parse_errors],
        }
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    # Validate schema
    vr = validate_job_results_dict(records)
    if vr["status"] != "PASS":
        result = {
            "status": "FAIL",
            "total_jobs": len(records), "success_count": 0, "empty_count": 0,
            "failed_count": 0, "rate_limited_count": 0, "auth_failed_count": 0,
            "blocked_count": 0, "total_raw_records": 0, "sources": {},
            "errors": vr["errors"],
        }
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    # Count statuses
    counts = {s: 0 for s in VALID_JOB_RESULT_STATUSES}
    total_raw = 0
    sources: dict[str, dict] = {}

    for rec in records:
        status = rec.get("status", "")
        if status in counts:
            counts[status] += 1
        total_raw += rec.get("raw_record_count", 0)

        src = rec.get("source", "unknown")
        if src not in sources:
            sources[src] = {"jobs": 0, "success": 0, "failed": 0, "raw_records": 0}
        sources[src]["jobs"] += 1
        if status == "success":
            sources[src]["success"] += 1
            sources[src]["raw_records"] += rec.get("raw_record_count", 0)
        elif status in ("failed", "rate_limited", "auth_failed", "blocked"):
            sources[src]["failed"] += 1

    # Status logic
    if counts["success"] > 0 or counts["empty"] > 0:
        status = "PASS"
    elif counts["failed"] > 0 or counts["rate_limited"] > 0 or counts["auth_failed"] > 0 or counts["blocked"] > 0:
        status = "WARN"
    else:
        status = "PASS"

    result = {
        "status": status,
        "total_jobs": len(records),
        "success_count": counts["success"],
        "empty_count": counts["empty"],
        "failed_count": counts["failed"],
        "rate_limited_count": counts["rate_limited"],
        "auth_failed_count": counts["auth_failed"],
        "blocked_count": counts["blocked"],
        "total_raw_records": total_raw,
        "sources": sources,
        "errors": [],
    }

    if json_output:
        print(json.dumps(result, indent=2))
    else:
        print(f"Status: {status}")
        print(f"Total jobs: {len(records)}")
        print(f"Success: {counts['success']}, Empty: {counts['empty']}, Failed: {counts['failed']}")
        print(f"Rate limited: {counts['rate_limited']}, Auth failed: {counts['auth_failed']}, Blocked: {counts['blocked']}")
        print(f"Total raw records: {total_raw}")
        for src, info in sorted(sources.items()):
            print(f"  {src}: {info['jobs']} jobs, {info['success']} success, {info['raw_records']} records")
    return result


# ---- OpenAlex adapter ----

OPENALEX_API_BASE = "https://api.openalex.org/works"
OPENALEX_REQUEST_TIMEOUT = 15


def _openalex_work_id_from_url(openalex_id_url: str) -> str:
    """Extract W... ID from an OpenAlex URL like https://openalex.org/W12345."""
    if not openalex_id_url:
        return ""
    url = str(openalex_id_url).strip()
    # Handle both full URL and bare ID
    if "/" in url:
        parts = url.rstrip("/").split("/")
        return parts[-1] if parts else ""
    return url


def _normalize_openalex_doi(doi_url: str) -> str:
    """Normalize DOI from https://doi.org/10.xxxx to bare 10.xxxx."""
    if not doi_url:
        return ""
    doi = str(doi_url).strip()
    # Strip common prefixes
    for prefix in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "http://dx.doi.org/"):
        if doi.lower().startswith(prefix.lower()):
            doi = doi[len(prefix):]
            break
    return doi


def _reconstruct_openalex_abstract(abstract_inverted_index) -> str:
    """Reconstruct abstract from OpenAlex abstract_inverted_index format.

    OpenAlex returns: {"word1": [pos1, pos2], "word2": [pos3], ...}
    We reconstruct by placing words at their positions.
    """
    if not abstract_inverted_index or not isinstance(abstract_inverted_index, dict):
        return ""

    # Build position -> word mapping
    position_word = []
    for word, positions in abstract_inverted_index.items():
        if isinstance(positions, list):
            for pos in positions:
                if isinstance(pos, int):
                    position_word.append((pos, word))

    # Sort by position and join
    position_word.sort(key=lambda x: x[0])
    return " ".join(pw[1] for pw in position_word)


def _map_openalex_work_to_raw_record(work: dict, job_id: str, query: str, retrieved_at: str) -> dict | None:
    """Map an OpenAlex work object to a raw_results record. Returns None if title missing."""
    if not isinstance(work, dict):
        return None

    title = work.get("display_name") or work.get("title") or ""
    if not title.strip():
        return None

    # Authors
    authorships = work.get("authorships", [])
    authors = []
    if isinstance(authorships, list):
        for a in authorships:
            if isinstance(a, dict):
                author_obj = a.get("author", {})
                if isinstance(author_obj, dict):
                    name = author_obj.get("display_name", "")
                    if name:
                        authors.append(name)

    # Year
    year = work.get("publication_year", "")

    # OpenAlex ID and URL
    openalex_id_raw = work.get("id", "")
    openalex_id = _openalex_work_id_from_url(openalex_id_raw)
    url = f"https://openalex.org/{openalex_id}" if openalex_id else ""

    # DOI
    doi_raw = work.get("doi", "") or ""
    ids = work.get("ids", {})
    if not doi_raw and isinstance(ids, dict):
        doi_raw = ids.get("doi", "") or ""
    doi = _normalize_openalex_doi(doi_raw)

    # arXiv ID - extract from ids if available
    arxiv_id = ""
    if isinstance(ids, dict):
        arxiv_raw = ids.get("arxiv", "") or ""
        if arxiv_raw:
            arxiv_id = str(arxiv_raw).strip()

    # Venue from primary_location
    venue = ""
    primary_location = work.get("primary_location", {})
    if isinstance(primary_location, dict):
        source_obj = primary_location.get("source", {})
        if isinstance(source_obj, dict):
            venue = source_obj.get("display_name", "") or ""

    # Abstract
    abstract = _reconstruct_openalex_abstract(work.get("abstract_inverted_index"))

    return {
        "source": "openalex",
        "title": title.strip(),
        "authors": authors,
        "year": year,
        "url": url,
        "doi": doi,
        "arxiv_id": arxiv_id,
        "semantic_scholar_id": "",
        "openalex_id": openalex_id,
        "abstract": abstract,
        "venue": venue,
        "retrieved_at": retrieved_at,
        "evidence_origin": "api_export",
        "notes": f"source_job_id={job_id}; query={query}",
    }


def _execute_openalex_job(job: dict, per_page: int = 5, mailto: str = "") -> dict:
    """Execute a single OpenAlex search job. Returns a source_job_result_v1 dict.
    No PDF download. No model. No .env."""
    job_id = job.get("job_id", "")
    source = job.get("source", "")
    query = job.get("query", "")
    time_range = job.get("time_range", {})
    retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Validate source
    if source != "openalex":
        return {
            "schema_version": "source_job_result_v1",
            "job_id": job_id,
            "source": source,
            "query": query,
            "status": "failed",
            "retrieved_at": retrieved_at,
            "raw_record_count": 0,
            "records": [],
            "error": f"source is '{source}', not 'openalex'",
            "notes": "run-openalex-job only accepts openalex jobs",
        }

    # Build URL
    params = {
        "search": query,
        "per-page": str(min(per_page, 50)),
        "sort": "relevance_score:desc",
    }
    # Add year filter if time_range present
    if isinstance(time_range, dict):
        sy = time_range.get("start_year")
        ey = time_range.get("end_year")
        if isinstance(sy, int) and isinstance(ey, int):
            params["filter"] = f"publication_year:{sy}-{ey}"
    if mailto:
        params["mailto"] = mailto

    url = OPENALEX_API_BASE + "?" + urllib.parse.urlencode(params)

    # Execute request
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "literature-evidence-landing/1.0"})
        with urllib.request.urlopen(req, timeout=OPENALEX_REQUEST_TIMEOUT) as resp:
            http_status = resp.status
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        http_status = e.code
        body = ""
        error_msg = f"HTTP {e.code}: {e.reason}"
        # Map HTTP errors
        if e.code in (401, 403):
            status = "auth_failed"
        elif e.code == 402:
            status = "blocked"
        elif e.code == 429:
            status = "rate_limited"
        else:
            status = "failed"
        return {
            "schema_version": "source_job_result_v1",
            "job_id": job_id,
            "source": "openalex",
            "query": query,
            "status": status,
            "http_status": http_status,
            "retrieved_at": retrieved_at,
            "raw_record_count": 0,
            "records": [],
            "error": error_msg,
            "notes": "",
        }
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        return {
            "schema_version": "source_job_result_v1",
            "job_id": job_id,
            "source": "openalex",
            "query": query,
            "status": "failed",
            "retrieved_at": retrieved_at,
            "raw_record_count": 0,
            "records": [],
            "error": f"network error: {e}",
            "notes": "",
        }

    # Parse response
    try:
        data = json.loads(body)
    except json.JSONDecodeError as e:
        return {
            "schema_version": "source_job_result_v1",
            "job_id": job_id,
            "source": "openalex",
            "query": query,
            "status": "failed",
            "http_status": http_status,
            "retrieved_at": retrieved_at,
            "raw_record_count": 0,
            "records": [],
            "error": f"JSON parse error: {e}",
            "notes": "",
        }

    # Extract works
    results = data.get("results", [])
    if not isinstance(results, list):
        results = []

    # Map works to raw records
    raw_records = []
    for work in results:
        rec = _map_openalex_work_to_raw_record(work, job_id, query, retrieved_at)
        if rec is not None:
            raw_records.append(rec)

    # Determine status
    if raw_records:
        status = "success"
    else:
        status = "empty"

    return {
        "schema_version": "source_job_result_v1",
        "job_id": job_id,
        "source": "openalex",
        "query": query,
        "status": status,
        "http_status": http_status,
        "retrieved_at": retrieved_at,
        "raw_record_count": len(raw_records),
        "records": raw_records,
        "error": "",
        "notes": "",
    }


def _append_jsonl(path: Path, records: list[dict]) -> None:
    """Append records to a JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def run_openalex_job(search_jobs_path: Path, job_id: str, output_path: Path,
                     per_page: int = 5, mailto: str = "", json_output: bool = False) -> dict:
    """Execute one OpenAlex job from search_jobs.json and append to job_results.jsonl."""
    if not search_jobs_path.exists():
        result = {"status": "FAIL", "errors": ["search_jobs.json not found"]}
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    try:
        jobs_data = json.loads(search_jobs_path.read_text(encoding="utf-8", errors="ignore"))
    except json.JSONDecodeError as e:
        result = {"status": "FAIL", "errors": [f"invalid JSON: {e}"]}
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    # Find job by ID
    jobs_list = jobs_data.get("jobs", [])
    target_job = None
    for j in jobs_list:
        if j.get("job_id") == job_id:
            target_job = j
            break

    if target_job is None:
        result = {"status": "FAIL", "errors": [f"job_id '{job_id}' not found in search_jobs.json"]}
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    # Reject non-openalex jobs before any execution
    if target_job.get("source") != "openalex":
        result = {"status": "FAIL", "errors": [f"job source is '{target_job.get('source')}', not 'openalex'"]}
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    # Execute
    job_result = _execute_openalex_job(target_job, per_page=per_page, mailto=mailto)

    # Validate before writing
    vr = validate_job_results_dict([job_result])
    if vr["status"] != "PASS":
        result = {"status": "FAIL", "errors": vr["errors"]}
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    # Append to output
    _append_jsonl(output_path, [job_result])

    result = {
        "status": "PASS",
        "job_id": job_id,
        "job_result_status": job_result["status"],
        "raw_record_count": job_result["raw_record_count"],
        "http_status": job_result.get("http_status"),
        "output": str(output_path),
    }
    if json_output:
        print(json.dumps(result, indent=2))
    else:
        print(f"Executed {job_id}: status={job_result['status']}, records={job_result['raw_record_count']}")
    return result


def run_openalex_jobs(search_jobs_path: Path, output_path: Path,
                      max_jobs: int = 3, per_page: int = 5, mailto: str = "",
                      overwrite: bool = False, json_output: bool = False) -> dict:
    """Execute OpenAlex jobs from search_jobs.json, append to job_results.jsonl."""
    if not search_jobs_path.exists():
        result = {"status": "FAIL", "errors": ["search_jobs.json not found"]}
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    try:
        jobs_data = json.loads(search_jobs_path.read_text(encoding="utf-8", errors="ignore"))
    except json.JSONDecodeError as e:
        result = {"status": "FAIL", "errors": [f"invalid JSON: {e}"]}
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    # Filter to openalex jobs only
    all_jobs = jobs_data.get("jobs", [])
    openalex_jobs = [j for j in all_jobs if j.get("source") == "openalex"]

    if not openalex_jobs:
        result = {"status": "FAIL", "errors": ["no openalex jobs found in search_jobs.json"]}
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    # Respect max_jobs
    jobs_to_run = openalex_jobs[:max_jobs]

    # Handle overwrite
    if overwrite and output_path.exists():
        output_path.unlink()

    # Execute each job
    executed = []
    for job in jobs_to_run:
        job_result = _execute_openalex_job(job, per_page=per_page, mailto=mailto)

        # Validate before writing
        vr = validate_job_results_dict([job_result])
        if vr["status"] != "PASS":
            # Write as failed instead
            job_result = {
                "schema_version": "source_job_result_v1",
                "job_id": job.get("job_id", ""),
                "source": "openalex",
                "query": job.get("query", ""),
                "status": "failed",
                "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "raw_record_count": 0,
                "records": [],
                "error": f"validation failed: {vr['errors']}",
                "notes": "",
            }

        _append_jsonl(output_path, [job_result])
        executed.append({
            "job_id": job_result["job_id"],
            "status": job_result["status"],
            "raw_record_count": job_result["raw_record_count"],
        })

    result = {
        "status": "PASS",
        "executed_count": len(executed),
        "executed": executed,
        "output": str(output_path),
    }
    if json_output:
        print(json.dumps(result, indent=2))
    else:
        print(f"Executed {len(executed)} openalex job(s) -> {output_path}")
        for e in executed:
            print(f"  {e['job_id']}: status={e['status']}, records={e['raw_record_count']}")
    return result


# ---- Pipeline run-dir safety ----

_DANGEROUS_DIR_NAMES = frozenset({".aris", "research", "literature", ".env"})


def _check_run_dir_safe(run_dir: Path) -> list[str]:
    """Return list of errors if run_dir is dangerous, empty if safe."""
    errors = []
    run_str = str(run_dir).strip()

    # Reject empty or "." paths
    if not run_str or run_str == ".":
        errors.append("run_dir must not be empty or '.'")
        return errors

    resolved = run_dir.resolve()
    cwd = Path.cwd().resolve()

    # Reject cwd itself
    if resolved == cwd:
        errors.append(f"run_dir must not be the current working directory: {resolved}")
    # Reject cwd parent
    if resolved == cwd.parent:
        errors.append(f"run_dir must not be the parent of cwd: {resolved}")
    # Reject any path containing dangerous directory names
    for part in resolved.parts:
        if part in _DANGEROUS_DIR_NAMES:
            errors.append(f"run_dir contains forbidden path segment: {part}")
            break
    # Reject home directory
    try:
        home = Path.home().resolve()
        if resolved == home:
            errors.append(f"run_dir must not be the home directory: {resolved}")
    except Exception:
        pass

    return errors


# ---- Pipeline smoke command ----

def run_openalex_pipeline(
    topic: str,
    intent: str,
    must_include: list[str],
    run_dir: Path,
    start_year: int | None = None,
    end_year: int | None = None,
    max_results_per_source: int = 10,
    max_jobs: int = 3,
    per_page: int = 5,
    top_k: int = 5,
    overwrite: bool = False,
    exclude: str = "",
    mailto: str = "",
    dry_run: bool = False,
    json_output: bool = False,
) -> dict:
    """Chain all literature layer MVP steps into one controlled pipeline.
    Fail-closed: stops on any step failure.
    No model calls. Network only for OpenAlex API (skipped in dry-run)."""

    import shutil

    steps_executed = []

    # Safety check: reject dangerous run_dir paths
    safety_errors = _check_run_dir_safe(run_dir)
    if safety_errors:
        result = {
            "status": "FAIL",
            "failed_step": "prepare_run_dir",
            "errors": safety_errors,
            "steps_executed": steps_executed,
            "dry_run": dry_run,
        }
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    # Handle existing directory
    if run_dir.exists():
        if not overwrite:
            result = {
                "status": "FAIL",
                "failed_step": "prepare_run_dir",
                "errors": [f"run_dir already exists; use --overwrite"],
                "steps_executed": steps_executed,
                "dry_run": dry_run,
            }
            if json_output:
                print(json.dumps(result, indent=2))
            return result
        # overwrite=True: delete existing run_dir then recreate
        shutil.rmtree(run_dir)

    run_dir.mkdir(parents=True, exist_ok=True)

    # Resolve year defaults
    if start_year is None:
        start_year = 2020
    if end_year is None:
        end_year = datetime.now(timezone.utc).year

    # Define output paths
    plan_path = run_dir / "search_plan.yaml"
    jobs_path = run_dir / "search_jobs.json"
    job_results_path = run_dir / "job_results.jsonl"
    raw_results_path = run_dir / "raw_results.jsonl"
    candidates_path = run_dir / "candidates.jsonl"

    # Step 1: build_search_plan
    plan_result = build_search_plan(
        topic=topic,
        intent=intent,
        must_include=must_include,
        sources=["openalex"],
        start_year=start_year,
        end_year=end_year,
        max_results_per_source=max_results_per_source,
        output_path=plan_path,
        exclude=exclude,
        json_output=False,
    )
    steps_executed.append({"step": "build_search_plan", "status": plan_result["status"]})
    if plan_result["status"] != "PASS":
        result = {
            "status": "FAIL",
            "failed_step": "build_search_plan",
            "errors": plan_result.get("errors", []),
            "steps_executed": steps_executed,
            "dry_run": dry_run,
        }
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    # Step 2: build_search_jobs
    jobs_result = build_search_jobs(plan_path, jobs_path, json_output=False)
    steps_executed.append({"step": "build_search_jobs", "status": jobs_result["status"]})
    if jobs_result["status"] != "PASS":
        result = {
            "status": "FAIL",
            "failed_step": "build_search_jobs",
            "errors": jobs_result.get("errors", []),
            "steps_executed": steps_executed,
            "dry_run": dry_run,
        }
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    # Step 3: dry-run stop
    if dry_run:
        result = {
            "status": "PASS",
            "dry_run": True,
            "run_dir": str(run_dir),
            "steps_executed": steps_executed,
            "files_created": [str(plan_path), str(jobs_path)],
        }
        if json_output:
            print(json.dumps(result, indent=2))
        else:
            print(f"Dry-run complete. Plan + jobs written to {run_dir}")
        return result

    # Step 4: run_openalex_jobs
    exec_result = run_openalex_jobs(
        search_jobs_path=jobs_path,
        output_path=job_results_path,
        max_jobs=max_jobs,
        per_page=per_page,
        mailto=mailto,
        overwrite=overwrite,
        json_output=False,
    )
    steps_executed.append({"step": "run_openalex_jobs", "status": exec_result["status"]})
    if exec_result["status"] != "PASS":
        result = {
            "status": "FAIL",
            "failed_step": "run_openalex_jobs",
            "errors": exec_result.get("errors", []),
            "steps_executed": steps_executed,
            "dry_run": False,
        }
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    # Step 5: validate_job_results
    vjr_result = validate_job_results(job_results_path, json_output=False)
    steps_executed.append({"step": "validate_job_results", "status": vjr_result["status"]})
    if vjr_result["status"] != "PASS":
        result = {
            "status": "FAIL",
            "failed_step": "validate_job_results",
            "errors": vjr_result.get("errors", []),
            "steps_executed": steps_executed,
            "dry_run": False,
        }
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    # Step 6: normalize_job_results
    norm_result = normalize_job_results(job_results_path, raw_results_path, json_output=False)
    steps_executed.append({"step": "normalize_job_results", "status": norm_result["status"]})
    if norm_result["status"] != "PASS":
        result = {
            "status": "FAIL",
            "failed_step": "normalize_job_results",
            "errors": norm_result.get("errors", []),
            "steps_executed": steps_executed,
            "dry_run": False,
        }
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    # Step 7: validate_raw
    vr_result = validate_raw(raw_results_path, json_output=False)
    steps_executed.append({"step": "validate_raw", "status": vr_result["status"]})
    # validate_raw returns "valid" or "valid_with_warnings" on success, not "PASS"
    if vr_result["status"] not in ("PASS", "valid", "valid_with_warnings"):
        result = {
            "status": "FAIL",
            "failed_step": "validate_raw",
            "errors": vr_result.get("errors", []),
            "steps_executed": steps_executed,
            "dry_run": False,
        }
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    # Step 8: build_candidates
    cand_result = build_candidates(run_dir, json_output=False)
    steps_executed.append({"step": "build_candidates", "status": cand_result["status"]})
    # build_candidates returns "built" on success, not "PASS"
    if cand_result["status"] not in ("PASS", "built"):
        result = {
            "status": "FAIL",
            "failed_step": "build_candidates",
            "errors": cand_result.get("errors", []),
            "steps_executed": steps_executed,
            "dry_run": False,
        }
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    # Step 9: validate_candidates
    vc_result = validate_candidates(candidates_path, json_output=False)
    steps_executed.append({"step": "validate_candidates", "status": vc_result["status"]})
    # validate_candidates returns "valid" or "valid_with_warnings" on success
    if vc_result["status"] not in ("PASS", "valid", "valid_with_warnings"):
        result = {
            "status": "FAIL",
            "failed_step": "validate_candidates",
            "errors": vc_result.get("errors", []),
            "steps_executed": steps_executed,
            "dry_run": False,
        }
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    # Step 10: build_top_k
    topk_result = build_top_k(run_dir, k=top_k, json_output=False)
    steps_executed.append({"step": "build_top_k", "status": topk_result["status"]})
    # build_top_k returns "built" on success, not "PASS"
    if topk_result["status"] not in ("PASS", "built"):
        result = {
            "status": "FAIL",
            "failed_step": "build_top_k",
            "errors": topk_result.get("errors", []),
            "steps_executed": steps_executed,
            "dry_run": False,
        }
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    # Step 11: summarize_run
    summary = summarize_run(run_dir, json_output=False)
    steps_executed.append({"step": "summarize_run", "status": summary.get("status", "PASS")})

    result = {
        "status": "PASS",
        "dry_run": False,
        "run_dir": str(run_dir),
        "steps_executed": steps_executed,
        "summary": summary,
    }
    if json_output:
        print(json.dumps(result, indent=2))
    else:
        print(f"Pipeline complete. Run directory: {run_dir}")
        for s in steps_executed:
            print(f"  {s['step']}: {s['status']}")
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

    # Test 17: validate-job-results valid success result → PASS
    try:
        tmp_dir = Path(tempfile.mkdtemp())
        jr_path = tmp_dir / "job_results.jsonl"
        rec = {
            "schema_version": "source_job_result_v1",
            "job_id": "job_openalex_abc12345",
            "source": "openalex",
            "query": "LLM hallucination detection",
            "status": "success",
            "http_status": 200,
            "retrieved_at": "2026-05-13",
            "raw_record_count": 1,
            "records": [{
                "source": "openalex", "title": "Test Paper", "authors": ["A"],
                "year": 2024, "url": "https://openalex.org/W123", "doi": "",
                "arxiv_id": "", "semantic_scholar_id": "", "openalex_id": "W123",
                "abstract": "Test abstract", "venue": "", "retrieved_at": "2026-05-13",
                "evidence_origin": "api_export", "notes": "",
            }],
            "error": "",
            "notes": "",
        }
        _write_jsonl(jr_path, [rec])
        r = validate_job_results(jr_path, json_output=False)
        assert r["status"] == "PASS", f"Test 17: Expected PASS, got {r['status']}: {r['errors']}"
        print("  [PASS] 17. validate-job-results valid success result → PASS")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] 17. validate-job-results success: {e}")
        failed += 1
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    # Test 18: validate-job-results success with raw_record_count mismatch → FAIL
    try:
        tmp_dir = Path(tempfile.mkdtemp())
        jr_path = tmp_dir / "job_results.jsonl"
        rec = {
            "schema_version": "source_job_result_v1",
            "job_id": "job_openalex_badcount",
            "source": "openalex",
            "query": "test",
            "status": "success",
            "http_status": 200,
            "retrieved_at": "2026-05-13",
            "raw_record_count": 5,
            "records": [{"source": "openalex", "title": "T", "year": 2024, "url": "x", "evidence_origin": "api_export"}],
            "error": "",
            "notes": "",
        }
        _write_jsonl(jr_path, [rec])
        r = validate_job_results(jr_path, json_output=False)
        assert r["status"] == "FAIL", f"Test 18: Expected FAIL, got {r['status']}"
        assert any("raw_record_count" in e for e in r["errors"]), f"Test 18: Expected count mismatch error, got {r['errors']}"
        print("  [PASS] 18. validate-job-results success with raw_record_count mismatch → FAIL")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] 18. raw_record_count mismatch: {e}")
        failed += 1
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    # Test 19: validate-job-results failed result with empty error → FAIL
    try:
        tmp_dir = Path(tempfile.mkdtemp())
        jr_path = tmp_dir / "job_results.jsonl"
        rec = {
            "schema_version": "source_job_result_v1",
            "job_id": "job_arxiv_failnoerr",
            "source": "arxiv",
            "query": "test",
            "status": "failed",
            "retrieved_at": "2026-05-13",
            "raw_record_count": 0,
            "records": [],
            "error": "",
            "notes": "",
        }
        _write_jsonl(jr_path, [rec])
        r = validate_job_results(jr_path, json_output=False)
        assert r["status"] == "FAIL", f"Test 19: Expected FAIL, got {r['status']}"
        assert any("error is empty" in e for e in r["errors"]), f"Test 19: Expected empty error msg, got {r['errors']}"
        print("  [PASS] 19. validate-job-results failed with empty error → FAIL")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] 19. failed empty error: {e}")
        failed += 1
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    # Test 20: validate-job-results rate_limited with error and zero records → PASS
    try:
        tmp_dir = Path(tempfile.mkdtemp())
        jr_path = tmp_dir / "job_results.jsonl"
        rec = {
            "schema_version": "source_job_result_v1",
            "job_id": "job_semantic_scholar_rl",
            "source": "semantic_scholar",
            "query": "test",
            "status": "rate_limited",
            "http_status": 429,
            "retrieved_at": "2026-05-13",
            "raw_record_count": 0,
            "records": [],
            "error": "rate limit exceeded",
            "notes": "",
        }
        _write_jsonl(jr_path, [rec])
        r = validate_job_results(jr_path, json_output=False)
        assert r["status"] == "PASS", f"Test 20: Expected PASS, got {r['status']}: {r['errors']}"
        print("  [PASS] 20. validate-job-results rate_limited with error and zero records → PASS")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] 20. rate_limited: {e}")
        failed += 1
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    # Test 21: normalize-job-results valid success → writes raw_results.jsonl
    try:
        tmp_dir = Path(tempfile.mkdtemp())
        jr_path = tmp_dir / "job_results.jsonl"
        raw_out = tmp_dir / "raw_results.jsonl"
        rec = {
            "schema_version": "source_job_result_v1",
            "job_id": "job_openalex_norm",
            "source": "openalex",
            "query": "test query",
            "status": "success",
            "http_status": 200,
            "retrieved_at": "2026-05-13",
            "raw_record_count": 2,
            "records": [
                {
                    "source": "openalex", "title": "Paper A", "authors": ["Author A"],
                    "year": 2024, "url": "https://openalex.org/W1", "doi": "10.1234/a",
                    "arxiv_id": "", "semantic_scholar_id": "", "openalex_id": "W1",
                    "abstract": "Abstract A", "venue": "Conf A", "retrieved_at": "2026-05-13",
                    "evidence_origin": "api_export", "notes": "",
                },
                {
                    "source": "openalex", "title": "Paper B", "authors": ["Author B"],
                    "year": 2023, "url": "https://openalex.org/W2", "doi": "",
                    "arxiv_id": "2301.00001", "semantic_scholar_id": "", "openalex_id": "W2",
                    "abstract": "Abstract B", "venue": "", "retrieved_at": "2026-05-13",
                    "evidence_origin": "api_export", "notes": "",
                },
            ],
            "error": "",
            "notes": "",
        }
        _write_jsonl(jr_path, [rec])
        r = normalize_job_results(jr_path, raw_out, json_output=False)
        assert r["status"] == "PASS", f"Test 21: Expected PASS, got {r['status']}: {r.get('errors', '')}"
        assert raw_out.exists(), "Test 21: output file should exist"
        assert r["normalized_records"] == 2, f"Test 21: Expected 2 normalized, got {r['normalized_records']}"
        # Verify output passes validate_raw
        vr = validate_raw(raw_out, json_output=False)
        assert vr["status"] in ("valid", "valid_with_warnings"), f"Test 21: raw should validate, got {vr['status']}"
        print("  [PASS] 21. normalize-job-results valid success → writes raw_results.jsonl")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] 21. normalize-job-results success: {e}")
        failed += 1
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    # Test 22: normalize-job-results invalid job_results → FAIL and no output file
    try:
        tmp_dir = Path(tempfile.mkdtemp())
        jr_path = tmp_dir / "job_results.jsonl"
        raw_out = tmp_dir / "raw_results.jsonl"
        rec = {
            "schema_version": "WRONG",
            "job_id": "job_bad",
            "source": "arxiv",
            "query": "test",
            "status": "success",
            "retrieved_at": "2026-05-13",
            "raw_record_count": 0,
            "records": [],
            "error": "",
            "notes": "",
        }
        _write_jsonl(jr_path, [rec])
        r = normalize_job_results(jr_path, raw_out, json_output=False)
        assert r["status"] == "FAIL", f"Test 22: Expected FAIL, got {r['status']}"
        assert not raw_out.exists(), f"Test 22: output file should NOT exist on FAIL"
        print("  [PASS] 22. normalize-job-results invalid → FAIL and no output file")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] 22. normalize-job-results invalid: {e}")
        failed += 1
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    # Test 23: summarize-job-results counts success/failed/rate_limited correctly
    try:
        tmp_dir = Path(tempfile.mkdtemp())
        jr_path = tmp_dir / "job_results.jsonl"
        recs = [
            {
                "schema_version": "source_job_result_v1",
                "job_id": "job_oa_ok", "source": "openalex", "query": "q1",
                "status": "success", "http_status": 200, "retrieved_at": "2026-05-13",
                "raw_record_count": 3, "records": [{"source":"openalex","title":"T","year":2024,"url":"u","evidence_origin":"api_export"}] * 3,
                "error": "", "notes": "",
            },
            {
                "schema_version": "source_job_result_v1",
                "job_id": "job_arxiv_fail", "source": "arxiv", "query": "q2",
                "status": "failed", "retrieved_at": "2026-05-13",
                "raw_record_count": 0, "records": [],
                "error": "connection timeout", "notes": "",
            },
            {
                "schema_version": "source_job_result_v1",
                "job_id": "job_ss_rl", "source": "semantic_scholar", "query": "q3",
                "status": "rate_limited", "http_status": 429, "retrieved_at": "2026-05-13",
                "raw_record_count": 0, "records": [],
                "error": "rate limited", "notes": "",
            },
        ]
        _write_jsonl(jr_path, recs)
        r = summarize_job_results(jr_path, json_output=False)
        assert r["status"] == "PASS", f"Test 23: Expected PASS, got {r['status']}"
        assert r["total_jobs"] == 3, f"Test 23: Expected 3 jobs, got {r['total_jobs']}"
        assert r["success_count"] == 1, f"Test 23: Expected 1 success, got {r['success_count']}"
        assert r["failed_count"] == 1, f"Test 23: Expected 1 failed, got {r['failed_count']}"
        assert r["rate_limited_count"] == 1, f"Test 23: Expected 1 rate_limited, got {r['rate_limited_count']}"
        assert r["total_raw_records"] == 3, f"Test 23: Expected 3 raw records, got {r['total_raw_records']}"
        assert "openalex" in r["sources"], "Test 23: openalex should be in sources"
        assert r["sources"]["openalex"]["success"] == 1, "Test 23: openalex success should be 1"
        print("  [PASS] 23. summarize-job-results counts success/failed/rate_limited correctly")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] 23. summarize-job-results: {e}")
        failed += 1
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    # Test 24: init-run-skeleton creates empty job_results.jsonl
    try:
        tmp_dir = Path(tempfile.mkdtemp())
        run_dir = tmp_dir / "skeleton_test"
        r = init_run_skeleton(run_dir, "test topic", "novelty_check")
        assert r["status"] == "created", f"Test 24: Expected created, got {r['status']}"
        assert "job_results.jsonl" in r["files"], f"Test 24: job_results.jsonl should be in files list"
        jr_path = run_dir / "job_results.jsonl"
        assert jr_path.exists(), "Test 24: job_results.jsonl should exist"
        content = jr_path.read_text(encoding="utf-8").strip()
        assert content == "", f"Test 24: job_results.jsonl should be empty, got '{content}'"
        print("  [PASS] 24. init-run-skeleton creates empty job_results.jsonl")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] 24. init-run-skeleton job_results: {e}")
        failed += 1
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    # Test 25: validate-job-results success with nested paper field confirmed_novel → FAIL
    try:
        tmp_dir = Path(tempfile.mkdtemp())
        jr_path = tmp_dir / "job_results.jsonl"
        rec = {
            "schema_version": "source_job_result_v1",
            "job_id": "job_openalex_nested1",
            "source": "openalex",
            "query": "test",
            "status": "success",
            "http_status": 200,
            "retrieved_at": "2026-05-13",
            "raw_record_count": 1,
            "records": [{
                "source": "openalex", "title": "Paper A", "authors": ["A"],
                "year": 2024, "url": "https://openalex.org/W1", "doi": "",
                "arxiv_id": "", "semantic_scholar_id": "", "openalex_id": "W1",
                "abstract": "Test", "venue": "", "retrieved_at": "2026-05-13",
                "evidence_origin": "api_export", "notes": "",
                "confirmed_novel": True,
            }],
            "error": "",
            "notes": "",
        }
        _write_jsonl(jr_path, [rec])
        r = validate_job_results(jr_path, json_output=False)
        assert r["status"] == "FAIL", f"Test 25: Expected FAIL, got {r['status']}"
        assert any("confirmed_novel" in e and "records[0]" in e for e in r["errors"]), \
            f"Test 25: Expected nested confirmed_novel error, got {r['errors']}"
        print("  [PASS] 25. validate-job-results nested paper confirmed_novel → FAIL")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] 25. nested confirmed_novel: {e}")
        failed += 1
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    # Test 26: validate-job-results with nested metadata no_prior_work → FAIL
    try:
        tmp_dir = Path(tempfile.mkdtemp())
        jr_path = tmp_dir / "job_results.jsonl"
        rec = {
            "schema_version": "source_job_result_v1",
            "job_id": "job_openalex_nested2",
            "source": "openalex",
            "query": "test",
            "status": "success",
            "http_status": 200,
            "retrieved_at": "2026-05-13",
            "raw_record_count": 1,
            "records": [{
                "source": "openalex", "title": "Paper B", "authors": ["B"],
                "year": 2024, "url": "https://openalex.org/W2", "doi": "",
                "arxiv_id": "", "semantic_scholar_id": "", "openalex_id": "W2",
                "abstract": "Test", "venue": "", "retrieved_at": "2026-05-13",
                "evidence_origin": "api_export", "notes": "",
                "metadata": {"no_prior_work": True, "confidence": 0.9},
            }],
            "error": "",
            "notes": "",
        }
        _write_jsonl(jr_path, [rec])
        r = validate_job_results(jr_path, json_output=False)
        assert r["status"] == "FAIL", f"Test 26: Expected FAIL, got {r['status']}"
        assert any("no_prior_work" in e and "metadata" in e for e in r["errors"]), \
            f"Test 26: Expected nested metadata no_prior_work error, got {r['errors']}"
        print("  [PASS] 26. validate-job-results nested metadata no_prior_work → FAIL")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] 26. nested metadata no_prior_work: {e}")
        failed += 1
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    # Test 27: normalize-job-results with nested forbidden verdict field → FAIL, no output
    try:
        tmp_dir = Path(tempfile.mkdtemp())
        jr_path = tmp_dir / "job_results.jsonl"
        raw_out = tmp_dir / "raw_results.jsonl"
        rec = {
            "schema_version": "source_job_result_v1",
            "job_id": "job_openalex_nested3",
            "source": "openalex",
            "query": "test",
            "status": "success",
            "http_status": 200,
            "retrieved_at": "2026-05-13",
            "raw_record_count": 1,
            "records": [{
                "source": "openalex", "title": "Paper C", "authors": ["C"],
                "year": 2024, "url": "https://openalex.org/W3", "doi": "10.1234/c",
                "arxiv_id": "", "semantic_scholar_id": "", "openalex_id": "W3",
                "abstract": "Test", "venue": "", "retrieved_at": "2026-05-13",
                "evidence_origin": "api_export", "notes": "",
                "potentially_novel": True,
            }],
            "error": "",
            "notes": "",
        }
        _write_jsonl(jr_path, [rec])
        r = normalize_job_results(jr_path, raw_out, json_output=False)
        assert r["status"] == "FAIL", f"Test 27: Expected FAIL, got {r['status']}"
        assert not raw_out.exists(), f"Test 27: output file should NOT exist on FAIL"
        print("  [PASS] 27. normalize-job-results nested forbidden verdict → FAIL, no output")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] 27. normalize nested forbidden: {e}")
        failed += 1
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    # Test 28: reconstruct abstract from abstract_inverted_index
    try:
        idx = {"The": [0], "quick": [1], "brown": [2], "fox": [3]}
        abstract = _reconstruct_openalex_abstract(idx)
        assert abstract == "The quick brown fox", f"Test 28: Expected 'The quick brown fox', got '{abstract}'"
        # Empty case
        assert _reconstruct_openalex_abstract(None) == ""
        assert _reconstruct_openalex_abstract({}) == ""
        print("  [PASS] 28. reconstruct abstract from abstract_inverted_index")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] 28. reconstruct abstract: {e}")
        failed += 1

    # Test 29: normalize DOI from https://doi.org/10.xxxx
    try:
        assert _normalize_openalex_doi("https://doi.org/10.1234/test") == "10.1234/test"
        assert _normalize_openalex_doi("http://doi.org/10.5678/foo") == "10.5678/foo"
        assert _normalize_openalex_doi("https://dx.doi.org/10.9999/bar") == "10.9999/bar"
        assert _normalize_openalex_doi("10.1234/already") == "10.1234/already"
        assert _normalize_openalex_doi("") == ""
        assert _normalize_openalex_doi(None) == ""
        print("  [PASS] 29. normalize DOI from https://doi.org prefix")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] 29. normalize DOI: {e}")
        failed += 1

    # Test 30: map OpenAlex work to raw record with correct openalex_id and url
    try:
        work = {
            "id": "https://openalex.org/W2741809807",
            "display_name": "Test Paper Title",
            "publication_year": 2024,
            "doi": "https://doi.org/10.1234/test",
            "authorships": [
                {"author": {"display_name": "Alice Smith"}},
                {"author": {"display_name": "Bob Jones"}},
            ],
            "primary_location": {
                "source": {"display_name": "Test Venue"}
            },
            "abstract_inverted_index": {"We": [0], "study": [1], "LLMs": [2]},
        }
        rec = _map_openalex_work_to_raw_record(work, "job_test_001", "LLM hallucination", "2026-05-13")
        assert rec is not None, "Test 30: record should not be None"
        assert rec["source"] == "openalex"
        assert rec["title"] == "Test Paper Title"
        assert rec["authors"] == ["Alice Smith", "Bob Jones"]
        assert rec["year"] == 2024
        assert rec["url"] == "https://openalex.org/W2741809807"
        assert rec["doi"] == "10.1234/test"
        assert rec["openalex_id"] == "W2741809807"
        assert rec["venue"] == "Test Venue"
        assert rec["abstract"] == "We study LLMs"
        assert rec["evidence_origin"] == "api_export"
        assert "job_test_001" in rec["notes"]
        print("  [PASS] 30. map OpenAlex work to raw record")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] 30. map OpenAlex work: {e}")
        failed += 1

    # Test 31: validate mapped record with _validate_records
    try:
        work = {
            "id": "https://openalex.org/W123",
            "display_name": "Valid Paper",
            "publication_year": 2023,
            "doi": "https://doi.org/10.1111/valid",
            "authorships": [{"author": {"display_name": "Author One"}}],
            "abstract_inverted_index": {"Abstract": [0], "text": [1]},
        }
        rec = _map_openalex_work_to_raw_record(work, "job_v", "test query", "2026-05-13")
        errors, warnings, _ = _validate_records([rec])
        assert not errors, f"Test 31: Expected no errors, got {errors}"
        print("  [PASS] 31. validate mapped record passes _validate_records")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] 31. validate mapped record: {e}")
        failed += 1

    # Test 32: execute fake OpenAlex response mapping to success job result
    try:
        # Create a mock job and test the mapping logic (not the HTTP call)
        job = {"job_id": "job_oa_mock", "source": "openalex", "query": "test",
               "time_range": {"start_year": 2020, "end_year": 2026}}
        # Simulate what _execute_openalex_job does after getting a 200 response
        mock_works = [
            {"id": "https://openalex.org/W999", "display_name": "Mock Paper",
             "publication_year": 2024, "doi": "", "authorships": [],
             "abstract_inverted_index": None},
        ]
        raw_records = []
        for w in mock_works:
            r = _map_openalex_work_to_raw_record(w, "job_oa_mock", "test", "2026-05-13")
            if r:
                raw_records.append(r)
        result = {
            "schema_version": "source_job_result_v1",
            "job_id": "job_oa_mock", "source": "openalex", "query": "test",
            "status": "success", "http_status": 200, "retrieved_at": "2026-05-13",
            "raw_record_count": len(raw_records), "records": raw_records,
            "error": "", "notes": "",
        }
        vr = validate_job_results_dict([result])
        assert vr["status"] == "PASS", f"Test 32: Expected PASS, got {vr['status']}: {vr['errors']}"
        print("  [PASS] 32. fake OpenAlex response → success job result validates PASS")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] 32. fake OpenAlex response: {e}")
        failed += 1

    # Test 33: non-openalex job passed to run helper should FAIL before network
    try:
        tmp_dir = Path(tempfile.mkdtemp())
        jobs_path = tmp_dir / "search_jobs.json"
        out_path = tmp_dir / "job_results.jsonl"
        jobs_data = {
            "schema_version": "search_jobs_v1", "source_plan": "test.yaml",
            "topic": "test", "search_intent": "novelty_check", "job_count": 1,
            "jobs": [{"job_id": "job_arxiv_1", "source": "arxiv", "query": "q",
                      "time_range": {"start_year": 2020, "end_year": 2026},
                      "max_results": 10, "status": "planned",
                      "network_required": True, "execution_result": "not_started",
                      "raw_output_file": "", "error": "", "notes": ""}],
        }
        jobs_path.write_text(json.dumps(jobs_data), encoding="utf-8")
        r = run_openalex_job(jobs_path, "job_arxiv_1", out_path, json_output=False)
        assert r["status"] == "FAIL", f"Test 33: Expected FAIL, got {r['status']}"
        assert not out_path.exists(), "Test 33: output should not exist"
        print("  [PASS] 33. non-openalex job → FAIL before network")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] 33. non-openalex job: {e}")
        failed += 1
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    # Test 34: HTTP 429 mapping produces rate_limited job result
    try:
        result = {
            "schema_version": "source_job_result_v1",
            "job_id": "job_oa_429", "source": "openalex", "query": "test",
            "status": "rate_limited", "http_status": 429, "retrieved_at": "2026-05-13",
            "raw_record_count": 0, "records": [],
            "error": "HTTP 429: Too Many Requests", "notes": "",
        }
        vr = validate_job_results_dict([result])
        assert vr["status"] == "PASS", f"Test 34: Expected PASS, got {vr['status']}: {vr['errors']}"
        print("  [PASS] 34. HTTP 429 → rate_limited job result validates PASS")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] 34. HTTP 429 mapping: {e}")
        failed += 1

    # Test 35: missing/invalid title work is skipped, not fabricated
    try:
        # Work with empty title
        work_no_title = {"id": "https://openalex.org/W000", "display_name": "", "publication_year": 2024}
        rec = _map_openalex_work_to_raw_record(work_no_title, "job_skip", "test", "2026-05-13")
        assert rec is None, f"Test 35: Expected None for empty title, got {rec}"
        # Work with no display_name or title
        work_no_field = {"id": "https://openalex.org/W001", "publication_year": 2024}
        rec2 = _map_openalex_work_to_raw_record(work_no_field, "job_skip", "test", "2026-05-13")
        assert rec2 is None, f"Test 35: Expected None for missing title, got {rec2}"
        print("  [PASS] 35. missing title work → skipped (None)")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] 35. missing title skip: {e}")
        failed += 1

    # Test 36: dry-run produces plan + jobs, no job_results
    try:
        tmpdir = Path(tempfile.mkdtemp())
        run_dir = tmpdir / "run36"
        r = run_openalex_pipeline(
            topic="test topic",
            intent="novelty_check",
            must_include=["test"],
            run_dir=run_dir,
            dry_run=True,
            json_output=False,
        )
        assert r["status"] == "PASS", f"Test 36: expected PASS, got {r['status']}"
        assert r["dry_run"] is True, f"Test 36: expected dry_run=True"
        assert (run_dir / "search_plan.yaml").exists(), "Test 36: search_plan.yaml missing"
        assert (run_dir / "search_jobs.json").exists(), "Test 36: search_jobs.json missing"
        assert not (run_dir / "job_results.jsonl").exists(), "Test 36: job_results.jsonl should not exist"
        assert not (run_dir / "raw_results.jsonl").exists(), "Test 36: raw_results.jsonl should not exist"
        print("  [PASS] 36. dry-run produces plan + jobs, no network files")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] 36. dry-run: {e}")
        failed += 1
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    # Test 37: dry-run with overwrite flag succeeds
    try:
        tmpdir = Path(tempfile.mkdtemp())
        run_dir = tmpdir / "run37"
        r1 = run_openalex_pipeline(
            topic="test topic",
            intent="novelty_check",
            must_include=["test"],
            run_dir=run_dir,
            dry_run=True,
            overwrite=True,
            json_output=False,
        )
        assert r1["status"] == "PASS", f"Test 37: first run expected PASS"
        r2 = run_openalex_pipeline(
            topic="test topic",
            intent="novelty_check",
            must_include=["test"],
            run_dir=run_dir,
            dry_run=True,
            overwrite=True,
            json_output=False,
        )
        assert r2["status"] == "PASS", f"Test 37: second run with overwrite expected PASS"
        print("  [PASS] 37. dry-run with overwrite succeeds")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] 37. dry-run overwrite: {e}")
        failed += 1
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    # Test 38: invalid start_year > end_year fails at plan step
    try:
        tmpdir = Path(tempfile.mkdtemp())
        run_dir = tmpdir / "run38"
        r = run_openalex_pipeline(
            topic="test",
            intent="novelty_check",
            must_include=["test"],
            run_dir=run_dir,
            start_year=2025,
            end_year=2020,
            dry_run=True,
            json_output=False,
        )
        assert r["status"] == "FAIL", f"Test 38: expected FAIL, got {r['status']}"
        assert r.get("failed_step") == "build_search_plan", f"Test 38: expected failed_step=build_search_plan, got {r.get('failed_step')}"
        print("  [PASS] 38. invalid year range fails at plan step")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] 38. invalid year: {e}")
        failed += 1
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    # Test 39: invalid intent fails at plan step
    try:
        tmpdir = Path(tempfile.mkdtemp())
        run_dir = tmpdir / "run39"
        r = run_openalex_pipeline(
            topic="test",
            intent="invalid_intent",
            must_include=["test"],
            run_dir=run_dir,
            dry_run=True,
            json_output=False,
        )
        assert r["status"] == "FAIL", f"Test 39: expected FAIL, got {r['status']}"
        assert r.get("failed_step") == "build_search_plan", f"Test 39: expected failed_step=build_search_plan"
        print("  [PASS] 39. invalid intent fails at plan step")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] 39. invalid intent: {e}")
        failed += 1
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    # Test 40: pipeline result has no fabricated results field
    try:
        tmpdir = Path(tempfile.mkdtemp())
        run_dir = tmpdir / "run40"
        r = run_openalex_pipeline(
            topic="test topic",
            intent="novelty_check",
            must_include=["test"],
            run_dir=run_dir,
            dry_run=True,
            json_output=True,
        )
        assert "results" not in r, f"Test 40: pipeline result should not have 'results' field"
        assert "steps_executed" in r, "Test 40: should have steps_executed"
        print("  [PASS] 40. no fabricated results in pipeline output")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] 40. no fabricated results: {e}")
        failed += 1
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    # Test 41: summary includes dry_run flag
    try:
        tmpdir = Path(tempfile.mkdtemp())
        run_dir = tmpdir / "run41"
        r = run_openalex_pipeline(
            topic="test",
            intent="novelty_check",
            must_include=["test"],
            run_dir=run_dir,
            dry_run=True,
            json_output=False,
        )
        assert r.get("dry_run") is True, f"Test 41: expected dry_run=True in result"
        print("  [PASS] 41. summary includes dry_run flag")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] 41. dry_run flag: {e}")
        failed += 1
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    # Test 42: pipeline stops on invalid plan (empty must_include)
    try:
        tmpdir = Path(tempfile.mkdtemp())
        run_dir = tmpdir / "run42"
        r = run_openalex_pipeline(
            topic="test",
            intent="novelty_check",
            must_include=[],
            run_dir=run_dir,
            dry_run=True,
            json_output=False,
        )
        # Empty must_include should cause plan build to fail or produce empty variants
        # Either way, pipeline should not proceed to network steps
        assert r.get("dry_run") is True or r.get("status") == "FAIL", \
            f"Test 42: expected dry_run or FAIL, got status={r.get('status')}"
        print("  [PASS] 42. pipeline handles edge case (empty must_include)")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] 42. edge case: {e}")
        failed += 1
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    # Test A: existing run_dir without --overwrite → FAIL, old files preserved
    try:
        tmpdir = Path(tempfile.mkdtemp())
        existing = tmpdir / "existing_run"
        existing.mkdir()
        marker = existing / "old_marker.txt"
        marker.write_text("old content", encoding="utf-8")
        r = run_openalex_pipeline(
            topic="test",
            intent="novelty_check",
            must_include=["test"],
            run_dir=existing,
            dry_run=True,
            overwrite=False,
            json_output=False,
        )
        assert r["status"] == "FAIL", f"Test A: expected FAIL, got {r['status']}"
        assert r.get("failed_step") == "prepare_run_dir", f"Test A: expected failed_step=prepare_run_dir"
        assert marker.exists(), "Test A: old_marker.txt should still exist"
        assert not (existing / "search_plan.yaml").exists(), "Test A: search_plan.yaml should not exist"
        print("  [PASS] A. existing run_dir without --overwrite → FAIL, old files preserved")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] A. existing run_dir no overwrite: {e}")
        failed += 1
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    # Test B: existing run_dir with --overwrite → PASS, old files deleted
    try:
        tmpdir = Path(tempfile.mkdtemp())
        existing = tmpdir / "existing_run"
        existing.mkdir()
        marker = existing / "old_marker.txt"
        marker.write_text("old content", encoding="utf-8")
        r = run_openalex_pipeline(
            topic="test",
            intent="novelty_check",
            must_include=["test"],
            run_dir=existing,
            dry_run=True,
            overwrite=True,
            json_output=False,
        )
        assert r["status"] == "PASS", f"Test B: expected PASS, got {r['status']}"
        assert not marker.exists(), "Test B: old_marker.txt should be deleted"
        assert (existing / "search_plan.yaml").exists(), "Test B: search_plan.yaml should exist"
        assert (existing / "search_jobs.json").exists(), "Test B: search_jobs.json should exist"
        print("  [PASS] B. existing run_dir with --overwrite → PASS, old files deleted")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] B. existing run_dir overwrite: {e}")
        failed += 1
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    # Test C: run_dir=Path(".") → FAIL
    try:
        r = run_openalex_pipeline(
            topic="test",
            intent="novelty_check",
            must_include=["test"],
            run_dir=Path("."),
            dry_run=True,
            json_output=False,
        )
        assert r["status"] == "FAIL", f"Test C: expected FAIL, got {r['status']}"
        assert r.get("failed_step") == "prepare_run_dir", f"Test C: expected failed_step=prepare_run_dir"
        print("  [PASS] C. run_dir='.' → FAIL")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] C. run_dir='.': {e}")
        failed += 1

    # Test D: run_dir contains 'research' segment → FAIL
    try:
        tmpdir = Path(tempfile.mkdtemp())
        bad_path = tmpdir / "research" / "bad"
        r = run_openalex_pipeline(
            topic="test",
            intent="novelty_check",
            must_include=["test"],
            run_dir=bad_path,
            dry_run=True,
            json_output=False,
        )
        assert r["status"] == "FAIL", f"Test D: expected FAIL, got {r['status']}"
        assert r.get("failed_step") == "prepare_run_dir", f"Test D: expected failed_step=prepare_run_dir"
        print("  [PASS] D. run_dir contains 'research' → FAIL")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] D. run_dir 'research': {e}")
        failed += 1
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    # Test E: relevance scoring high (hallucination + LLM + hidden states)
    try:
        r = _score_text_relevance(
            "LLM hallucination detection via hidden states",
            "We propose a method for detecting hallucinations in large language models using hidden state representations",
            ["hallucination detection", "hidden states"],
        )
        assert r["relevance_label"] == "high", f"Test E: expected high, got {r['relevance_label']}"
        assert r["relevance_score"] >= 7, f"Test E: expected score >= 7, got {r['relevance_score']}"
        assert len(r["relevance_reasons"]) >= 2, f"Test E: expected multiple reasons"
        print("  [PASS] E. relevance scoring high for hallucination + LLM + hidden states")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] E. relevance high: {e}")
        failed += 1

    # Test F: relevance scoring low (metaverse/geriatric)
    try:
        r = _score_text_relevance(
            "Metaverse applications for geriatric medicine",
            "This paper explores virtual reality in elderly care",
            ["hallucination detection", "hidden states"],
        )
        assert r["relevance_label"] == "low", f"Test F: expected low, got {r['relevance_label']}"
        assert r["relevance_score"] < 4, f"Test F: expected score < 4, got {r['relevance_score']}"
        assert len(r["relevance_flags"]) > 0, f"Test F: expected negative flags"
        print("  [PASS] F. relevance scoring low for metaverse/geriatric")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] F. relevance low: {e}")
        failed += 1

    # Test G: build-candidates includes relevance fields
    try:
        tmpdir = Path(tempfile.mkdtemp())
        run_dir = tmpdir / "test_g"
        run_dir.mkdir()
        raw = [{"title": "Test paper", "source": "openalex", "url": "https://test.com",
                "evidence_origin": "api_export", "year": 2024}]
        _write_jsonl(run_dir / "raw_results.jsonl", raw)
        plan = {"must_include": ["hallucination detection"]}
        (run_dir / "search_plan.yaml").write_text(json.dumps(plan))
        r = build_candidates(run_dir, json_output=False)
        assert r["status"] == "built", f"Test G: expected built"
        cands, _ = _parse_jsonl(run_dir / "candidates.jsonl")
        assert len(cands) == 1, f"Test G: expected 1 candidate"
        c = cands[0]
        assert "relevance_score" in c, f"Test G: missing relevance_score"
        assert "relevance_label" in c, f"Test G: missing relevance_label"
        assert "relevance_reasons" in c, f"Test G: missing relevance_reasons"
        assert "relevance_flags" in c, f"Test G: missing relevance_flags"
        print("  [PASS] G. build-candidates includes relevance fields")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] G. build-candidates relevance: {e}")
        failed += 1
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    # Test H: build-top-k ranks high-relevance above metadata-rich irrelevant
    try:
        tmpdir = Path(tempfile.mkdtemp())
        run_dir = tmpdir / "test_h"
        run_dir.mkdir()
        # High relevance paper (hallucination + hidden states)
        high = {
            "title": "LLM hallucination detection hidden states",
            "source": "openalex", "url": "https://high.com", "year": 2024,
            "evidence_origin": "api_export", "abstract": "detecting hallucinations using hidden states in LLMs",
            "authors": ["Alice"], "venue": "TestVenue",
            "stable_ids": {"openalex_id": "W123"},
            "relevance_score": 10, "relevance_label": "high",
            "relevance_reasons": ["hallucination_group matched", "llm_group matched", "internal_state_group matched"],
            "relevance_flags": [],
        }
        # Metadata-rich but irrelevant paper
        low = {
            "title": "Metaverse for personal agents in smart cities",
            "source": "openalex", "url": "https://low.com", "year": 2025,
            "evidence_origin": "api_export", "abstract": "A comprehensive survey on metaverse applications",
            "authors": ["Bob", "Carol", "Dave", "Eve"], "venue": "BigVenue",
            "stable_ids": {"openalex_id": "W456"},
            "relevance_score": 0, "relevance_label": "low",
            "relevance_reasons": [],
            "relevance_flags": ["negative_match_1"],
        }
        _write_jsonl(run_dir / "candidates.jsonl", [high, low])
        r = build_top_k(run_dir, k=5, json_output=False)
        assert r["status"] == "built", f"Test H: expected built"
        topk_path = run_dir / "top_k.md"
        content = topk_path.read_text()
        # High relevance paper should appear before low relevance
        high_pos = content.find("LLM hallucination detection hidden states")
        low_pos = content.find("Metaverse for personal agents in smart cities")
        assert high_pos > 0, f"Test H: high relevance paper not found in top_k"
        assert high_pos < low_pos, f"Test H: high relevance paper should appear before low relevance"
        print("  [PASS] H. build-top-k ranks high-relevance above irrelevant")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] H. build-top-k ranking: {e}")
        failed += 1
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    # Test I: low-relevance appears in Filtered section
    try:
        tmpdir = Path(tempfile.mkdtemp())
        run_dir = tmpdir / "test_i"
        run_dir.mkdir()
        high = {
            "title": "Hallucination detection in LLMs via hidden states",
            "source": "openalex", "url": "https://high.com", "year": 2025,
            "evidence_origin": "api_export", "abstract": "detecting hallucinations using internal representations",
            "stable_ids": {"openalex_id": "W111"},
            "relevance_score": 10, "relevance_label": "high",
            "relevance_reasons": ["hallucination", "hidden states"], "relevance_flags": [],
        }
        low = {
            "title": "Agricultural forecasting with IoT sensors",
            "source": "openalex", "url": "https://low.com", "year": 2024,
            "evidence_origin": "api_export", "abstract": "smart farming using edge computing",
            "stable_ids": {"openalex_id": "W789"},
            "relevance_score": 0, "relevance_label": "low",
            "relevance_reasons": [], "relevance_flags": [],
        }
        _write_jsonl(run_dir / "candidates.jsonl", [high, low])
        r = build_top_k(run_dir, k=1, json_output=False)
        content = (run_dir / "top_k.md").read_text()
        assert "Filtered Low-Relevance Candidates" in content, f"Test I: missing Filtered section"
        assert "Agricultural forecasting" in content, f"Test I: low-rel paper not in Filtered section"
        print("  [PASS] I. low-relevance candidate in Filtered section")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] I. filtered section: {e}")
        failed += 1
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    # Test J: top_k.md contains "not a novelty verdict"
    try:
        tmpdir = Path(tempfile.mkdtemp())
        run_dir = tmpdir / "test_j"
        run_dir.mkdir()
        rec = {
            "title": "Test paper", "source": "openalex", "url": "https://test.com",
            "evidence_origin": "api_export", "year": 2024,
            "stable_ids": {},
            "relevance_score": 5, "relevance_label": "medium",
            "relevance_reasons": [], "relevance_flags": [],
        }
        _write_jsonl(run_dir / "candidates.jsonl", [rec])
        build_top_k(run_dir, k=5, json_output=False)
        content = (run_dir / "top_k.md").read_text()
        assert "not a novelty verdict" in content, f"Test J: missing novelty verdict warning"
        print("  [PASS] J. top_k.md contains 'not a novelty verdict'")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] J. novelty verdict warning: {e}")
        failed += 1
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    # Test K: top_k.md no forbidden novelty conclusions
    try:
        tmpdir = Path(tempfile.mkdtemp())
        run_dir = tmpdir / "test_k"
        run_dir.mkdir()
        rec = {
            "title": "Test paper", "source": "openalex", "url": "https://test.com",
            "evidence_origin": "api_export", "year": 2024,
            "stable_ids": {},
            "relevance_score": 5, "relevance_label": "medium",
            "relevance_reasons": [], "relevance_flags": [],
        }
        _write_jsonl(run_dir / "candidates.jsonl", [rec])
        build_top_k(run_dir, k=5, json_output=False)
        content = (run_dir / "top_k.md").read_text()
        forbidden = ["confirmed novel", "no prior work", "direct overlap none", "potentially novel"]
        for term in forbidden:
            # Allow in warning/forbidden context lines
            for line in content.split("\n"):
                if term in line.lower() and "not" in line.lower():
                    continue
                if term in line.lower():
                    assert False, f"Test K: forbidden term '{term}' found outside warning: {line}"
        print("  [PASS] K. top_k.md no forbidden novelty conclusions")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] K. forbidden terms: {e}")
        failed += 1
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    # Test L: validate-candidates passes with relevance fields
    try:
        tmpdir = Path(tempfile.mkdtemp())
        run_dir = tmpdir / "test_l"
        run_dir.mkdir()
        raw = [{"title": "Test", "source": "openalex", "url": "https://t.com",
                "evidence_origin": "api_export", "year": 2024}]
        _write_jsonl(run_dir / "raw_results.jsonl", raw)
        (run_dir / "search_plan.yaml").write_text(json.dumps({"must_include": ["test"]}))
        build_candidates(run_dir, json_output=False)
        r = validate_candidates(run_dir / "candidates.jsonl", json_output=False)
        assert r["status"] in ("valid", "valid_with_warnings"), f"Test L: expected valid, got {r['status']}"
        print("  [PASS] L. validate-candidates passes with relevance fields")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] L. validate-candidates: {e}")
        failed += 1
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

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

    vjr = sub.add_parser("validate-job-results", help="Validate job_results.jsonl schema")
    vjr.add_argument("--file", required=True, help="Path to job_results.jsonl")
    vjr.add_argument("--json", action="store_true", help="Output JSON")

    njr = sub.add_parser("normalize-job-results", help="Normalize successful job results into raw_results.jsonl")
    njr.add_argument("--input", required=True, help="Path to job_results.jsonl")
    njr.add_argument("--output", required=True, help="Output path for raw_results.jsonl")
    njr.add_argument("--json", action="store_true", help="Output JSON")

    sjr = sub.add_parser("summarize-job-results", help="Summarize job_results.jsonl")
    sjr.add_argument("--file", required=True, help="Path to job_results.jsonl")
    sjr.add_argument("--json", action="store_true", help="Output JSON")

    roj = sub.add_parser("run-openalex-job", help="Execute one OpenAlex search job")
    roj.add_argument("--job-id", required=True, help="Job ID to execute")
    roj.add_argument("--search-jobs", required=True, help="Path to search_jobs.json")
    roj.add_argument("--output", required=True, help="Output path for job_results.jsonl")
    roj.add_argument("--per-page", type=int, default=5, help="Results per page (default: 5)")
    roj.add_argument("--mailto", default="", help="Optional email for polite API pool")
    roj.add_argument("--json", action="store_true", help="Output JSON")

    rojs = sub.add_parser("run-openalex-jobs", help="Execute multiple OpenAlex search jobs")
    rojs.add_argument("--search-jobs", required=True, help="Path to search_jobs.json")
    rojs.add_argument("--output", required=True, help="Output path for job_results.jsonl")
    rojs.add_argument("--max-jobs", type=int, default=3, help="Max jobs to execute (default: 3)")
    rojs.add_argument("--per-page", type=int, default=5, help="Results per page (default: 5)")
    rojs.add_argument("--mailto", default="", help="Optional email for polite API pool")
    rojs.add_argument("--overwrite", action="store_true", help="Overwrite output instead of append")
    rojs.add_argument("--json", action="store_true", help="Output JSON")

    rop = sub.add_parser("run-openalex-pipeline", help="Run full OpenAlex pipeline (plan → jobs → execute → validate → candidates → top-k)")
    rop.add_argument("--topic", required=True, help="Research topic")
    rop.add_argument("--intent", default="novelty_check", help="Search intent (default: novelty_check)")
    rop.add_argument("--must-include", action="append", required=True, help="Must-include term (repeatable)")
    rop.add_argument("--run-dir", required=True, help="Run directory for all outputs")
    rop.add_argument("--start-year", type=int, default=None, help="Start year (default: 2020)")
    rop.add_argument("--end-year", type=int, default=None, help="End year (default: current year)")
    rop.add_argument("--max-results-per-source", type=int, default=10, help="Max results per source (default: 10)")
    rop.add_argument("--max-jobs", type=int, default=3, help="Max OpenAlex jobs to execute (default: 3)")
    rop.add_argument("--per-page", type=int, default=5, help="Results per page (default: 5)")
    rop.add_argument("--top-k", type=int, default=5, help="Top-K candidates to select (default: 5)")
    rop.add_argument("--overwrite", action="store_true", help="Overwrite job results instead of append")
    rop.add_argument("--exclude", default="", help="Exclusion terms")
    rop.add_argument("--mailto", default="", help="Optional email for polite API pool")
    rop.add_argument("--dry-run", action="store_true", help="Stop after plan + jobs (no network)")
    rop.add_argument("--json", action="store_true", help="Output JSON")

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
    elif args.command == "validate-job-results":
        r = validate_job_results(Path(args.file), args.json)
        if r["status"] == "FAIL":
            sys.exit(1)
    elif args.command == "normalize-job-results":
        r = normalize_job_results(Path(args.input), Path(args.output), args.json)
        if r["status"] != "PASS":
            sys.exit(1)
    elif args.command == "summarize-job-results":
        summarize_job_results(Path(args.file), args.json)
    elif args.command == "run-openalex-job":
        r = run_openalex_job(
            search_jobs_path=Path(args.search_jobs),
            job_id=args.job_id,
            output_path=Path(args.output),
            per_page=args.per_page,
            mailto=args.mailto,
            json_output=args.json,
        )
        if r["status"] != "PASS":
            sys.exit(1)
    elif args.command == "run-openalex-jobs":
        r = run_openalex_jobs(
            search_jobs_path=Path(args.search_jobs),
            output_path=Path(args.output),
            max_jobs=args.max_jobs,
            per_page=args.per_page,
            mailto=args.mailto,
            overwrite=args.overwrite,
            json_output=args.json,
        )
        if r["status"] != "PASS":
            sys.exit(1)
    elif args.command == "run-openalex-pipeline":
        r = run_openalex_pipeline(
            topic=args.topic,
            intent=args.intent,
            must_include=args.must_include,
            run_dir=Path(args.run_dir),
            start_year=args.start_year,
            end_year=args.end_year,
            max_results_per_source=args.max_results_per_source,
            max_jobs=args.max_jobs,
            per_page=args.per_page,
            top_k=args.top_k,
            overwrite=args.overwrite,
            exclude=args.exclude,
            mailto=args.mailto,
            dry_run=args.dry_run,
            json_output=args.json,
        )
        if r["status"] != "PASS":
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
