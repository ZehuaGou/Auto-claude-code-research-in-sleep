"""Full-text store validation and summary helpers — extracted from literature_evidence_landing.py."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

# ---- Constants ----

VALID_ACQUISITION_STATUSES = frozenset([
    "acquired", "manual_required", "failed", "skipped"
])
VALID_ACQUISITION_METHODS = frozenset([
    "arxiv_source", "arxiv_pdf", "open_html", "open_pdf",
    "manual_required", "none", "manual_local"
])
VALID_EXTRACTION_STATUSES = frozenset([
    "extracted_markdown", "extracted_text", "tool_missing", "failed", "not_attempted"
])
VALID_EXTRACTION_METHODS = frozenset([
    "latex_to_markdown_mvp", "pdf_text", "html_text", "none", "manual_text_copy"
])
VALID_STORE_FULL_TEXT_STATUSES = frozenset([
    "source_acquired_unreviewed", "likely_full_text", "metadata_page_only",
    "landing_page_only", "manual_required", "extracted_markdown",
    "extracted_text", "tool_missing", "failed",
])
OPENALEX_HOST_PATTERNS = ("openalex.org", "openalex.org/")
DOI_HOST_PATTERNS = ("doi.org", "dx.doi.org")
VALID_PRIORITIES = frozenset(["critical", "high", "medium"])


def recompute_fulltext_store_summary(manifest: dict) -> dict:
    """Recompute manifest summary counts from current full-text store items."""
    items = manifest.get("items", [])
    summary = dict(manifest.get("summary", {}))
    summary["total_items"] = len(items)

    count_keys = [
        "source_acquired_unreviewed",
        "likely_full_text",
        "metadata_page_only",
        "landing_page_only",
        "manual_required",
        "extracted_markdown",
        "extracted_text",
        "tool_missing",
        "failed",
    ]
    for key in count_keys:
        summary[key] = 0

    for item in items:
        fts = item.get("full_text_status", "")
        if fts in summary:
            summary[fts] += 1
        ext = item.get("extraction_status", "")
        if ext in summary:
            summary[ext] += 1

    manifest["summary"] = summary
    return summary


def validate_fulltext_store(store_path: Path, json_output: bool = False) -> dict:
    """Validate full-text store manifest."""
    manifest_path = store_path / "manifest.json"
    errors: list[str] = []
    warnings: list[str] = []

    if not manifest_path.exists():
        errors.append("manifest.json not found")
        return {"status": "FAIL", "errors": errors, "warnings": warnings}

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:
        errors.append(f"cannot parse manifest.json: {e}")
        return {"status": "FAIL", "errors": errors, "warnings": warnings}

    # schema
    if manifest.get("schema_version") != "full_text_store_v1":
        errors.append(f"schema_version mismatch: {manifest.get('schema_version')}")

    # safety flags
    if manifest.get("paywall_bypass_used") is True:
        errors.append("paywall_bypass_used is true")
    if manifest.get("model_used") is True:
        errors.append("model_used is true")
    if manifest.get("pdfs_committed") is True:
        errors.append("pdfs_committed is true")
    if manifest.get("full_text_committed") is True:
        errors.append("full_text_committed is true")

    items = manifest.get("items", [])
    if not items:
        errors.append("items list is empty")

    # check queue_id uniqueness
    seen_ids: set[str] = set()
    for item in items:
        qid = item.get("queue_id", "")
        if qid in seen_ids:
            errors.append(f"duplicate queue_id: {qid}")
        seen_ids.add(qid)

        status = item.get("acquisition_status", "")
        if status not in VALID_ACQUISITION_STATUSES:
            errors.append(f"invalid acquisition_status '{status}' for {qid}")

        method = item.get("acquisition_method", "")
        if method not in VALID_ACQUISITION_METHODS:
            errors.append(f"invalid acquisition_method '{method}' for {qid}")

        ext_status = item.get("extraction_status", "")
        if ext_status not in VALID_EXTRACTION_STATUSES:
            errors.append(f"invalid extraction_status '{ext_status}' for {qid}")

        priority = item.get("priority", "")
        if priority not in VALID_PRIORITIES:
            errors.append(f"invalid priority '{priority}' for {qid}")

        # full_text_status validation
        fts = item.get("full_text_status", "")
        if fts and fts not in VALID_STORE_FULL_TEXT_STATUSES:
            errors.append(f"invalid full_text_status '{fts}' for {qid}")

        # Check: open_html from openalex.org must not be likely_full_text
        url = item.get("url", "").lower()
        if method == "open_html" and fts == "likely_full_text":
            if any(p in url for p in OPENALEX_HOST_PATTERNS):
                errors.append(
                    f"open_html from openalex.org cannot be likely_full_text for {qid}; "
                    f"should be metadata_page_only"
                )
            elif any(p in url for p in DOI_HOST_PATTERNS):
                warnings.append(
                    f"open_html from DOI landing page may not be full text for {qid}; "
                    f"consider landing_page_only"
                )

        if status == "acquired":
            has_path = (item.get("local_source_path") or item.get("local_pdf_path")
                        or item.get("local_html_path"))
            if not has_path:
                warnings.append(f"acquired item {qid} has no local source/pdf/html path")

        if ext_status == "extracted_markdown":
            if not item.get("local_markdown_path"):
                warnings.append(f"extracted_markdown item {qid} has no local_markdown_path")

        # Provenance and safety flag checks
        provenance = item.get("provenance", "")
        if method == "manual_local" and not provenance:
            warnings.append(f"manual_local item {qid} has no provenance field")
        usage_scope = item.get("usage_scope", "")
        if method == "manual_local" and usage_scope not in ("trusted_review_candidate", ""):
            errors.append(f"manual_local item {qid} has unexpected usage_scope: {usage_scope}")
        if item.get("should_commit_raw") is True:
            errors.append(f"should_commit_raw is true for {qid} — raw artifacts must not be committed")
        if item.get("should_commit_extracted_full_text") is True:
            errors.append(f"should_commit_extracted_full_text is true for {qid} — extracted text must not be committed")
        if method == "manual_local" and provenance == "user_supplied_local_file":
            if item.get("provenance_verified") is not False:
                warnings.append(f"manual_local item {qid} should have provenance_verified=false until human review")

    # Check manifest/queue consistency
    queue_path = store_path / "full_text_queue.json"
    if queue_path.exists():
        try:
            queue = json.loads(queue_path.read_text(encoding="utf-8"))
            queue_items = {qi["queue_id"]: qi for qi in queue.get("items", [])}
            for item in items:
                qid = item.get("queue_id", "")
                if qid in queue_items:
                    qi = queue_items[qid]
                    if item.get("acquisition_status") != qi.get("acquisition_status"):
                        errors.append(
                            f"manifest/queue disagree on acquisition_status for {qid}: "
                            f"manifest={item.get('acquisition_status')} queue={qi.get('acquisition_status')}"
                        )
                    if item.get("full_text_status") != qi.get("full_text_status"):
                        errors.append(
                            f"manifest/queue disagree on full_text_status for {qid}: "
                            f"manifest={item.get('full_text_status')} queue={qi.get('full_text_status')}"
                        )
        except Exception:
            warnings.append("cannot parse full_text_queue.json for consistency check")

    # Check summary consistency with items
    summary = manifest.get("summary", {})
    if items and summary:
        counts = {
            "source_acquired_unreviewed": 0,
            "likely_full_text": 0,
            "metadata_page_only": 0,
            "landing_page_only": 0,
            "manual_required": 0,
            "extracted_markdown": 0,
            "extracted_text": 0,
            "tool_missing": 0,
            "failed": 0,
        }
        for item in items:
            fts = item.get("full_text_status", "")
            if fts in counts:
                counts[fts] += 1
            ext = item.get("extraction_status", "")
            if ext in counts:
                counts[ext] += 1

        for key, expected in counts.items():
            actual = summary.get(key, -1)
            if actual != expected:
                errors.append(
                    f"summary.{key}={actual} but items count={expected}"
                )

    # check for tracked full-text files
    try:
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch"] +
            [str(f) for f in (store_path / "raw_pdfs").glob("*")
             if f.is_file() and f.name != ".gitkeep"] +
            [str(f) for f in (store_path / "raw_sources").glob("*")
             if f.is_file() and f.name != ".gitkeep"] +
            [str(f) for f in (store_path / "raw_html").glob("*")
             if f.is_file() and f.name != ".gitkeep"] +
            [str(f) for f in (store_path / "extracted_text").glob("*")
             if f.is_file() and f.name != ".gitkeep"] +
            [str(f) for f in (store_path / "extracted_markdown").glob("*")
             if f.is_file() and f.name != ".gitkeep"],
            capture_output=True, text=True, cwd=str(store_path),
        )
        if result.returncode == 0 and result.stdout.strip():
            for tracked in result.stdout.strip().split("\n"):
                if tracked.strip():
                    errors.append(f"full-text artifact tracked by git: {tracked}")
    except Exception:
        pass

    # check README
    readme_path = store_path / "README.md"
    if readme_path.exists():
        readme_text = readme_path.read_text(encoding="utf-8")
        if "paywall" in readme_text.lower() and "bypass" in readme_text.lower():
            if "no" not in readme_text.lower().split("paywall")[0][-20:]:
                warnings.append("README may contain paywall bypass instruction")
    else:
        warnings.append("README.md not found")

    status = "PASS" if not errors else "FAIL"
    return {"status": status, "errors": errors, "warnings": warnings}


def summarize_fulltext_store(store_path: Path, json_output: bool = False) -> dict:
    """Summarize full-text store status."""
    manifest_path = store_path / "manifest.json"
    if not manifest_path.exists():
        return {"status": "FAIL", "error": "manifest.json not found"}

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:
        return {"status": "FAIL", "error": f"cannot parse manifest: {e}"}

    items = manifest.get("items", [])
    summary = manifest.get("summary", {})

    result = {
        "status": "PASS",
        "schema_version": manifest.get("schema_version"),
        "total_items": summary.get("total_items", len(items)),
        "source_or_pdf_acquired": summary.get("source_or_pdf_acquired", 0),
        "likely_full_text": summary.get("likely_full_text", 0),
        "source_acquired_unreviewed": summary.get("source_acquired_unreviewed", 0),
        "landing_or_metadata_only": summary.get("landing_or_metadata_only", 0),
        "metadata_page_only": summary.get("metadata_page_only", 0),
        "landing_page_only": summary.get("landing_page_only", 0),
        "manual_required": summary.get("manual_required", 0),
        "extracted_markdown": summary.get("extracted_markdown", 0),
        "extracted_text": summary.get("extracted_text", 0),
        "tool_missing": summary.get("tool_missing", 0),
        "failed": summary.get("failed", 0),
        "paywall_bypass_used": manifest.get("paywall_bypass_used", False),
        "model_used": manifest.get("model_used", False),
        "items": [],
    }

    for item in items:
        result["items"].append({
            "queue_id": item.get("queue_id"),
            "title": item.get("title", "")[:80],
            "priority": item.get("priority"),
            "acquisition_status": item.get("acquisition_status"),
            "acquisition_method": item.get("acquisition_method"),
            "extraction_status": item.get("extraction_status"),
            "full_text_status": item.get("full_text_status", "unknown"),
        })

    return result
