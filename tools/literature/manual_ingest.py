"""Manual local file ingestion — extracted from literature_evidence_landing.py."""

from __future__ import annotations

import json
import shutil
from pathlib import Path


def ingest_manual_fulltext(
    store_path: Path,
    queue_id: str,
    local_file: Path,
    json_output: bool = False,
) -> dict:
    """Ingest a local file (PDF, text, or markdown) into the full-text store.

    For .txt/.md files: copies directly to extracted_text/{queue_id}.txt
    For .pdf files: extracts text via pypdf/pymupdf and saves to extracted_text/{queue_id}.txt
    Updates manifest.json, full_text_queue.json, and review_notes.md.
    """
    manifest_path = store_path / "manifest.json"
    queue_path = store_path / "full_text_queue.json"
    review_notes_path = store_path / "review_notes.md"

    if not manifest_path.exists():
        return {"status": "FAIL", "error": f"manifest.json not found in {store_path}"}
    if not queue_path.exists():
        return {"status": "FAIL", "error": f"full_text_queue.json not found in {store_path}"}
    if not local_file.exists():
        return {"status": "FAIL", "error": f"Local file not found: {local_file}"}

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    queue = json.loads(queue_path.read_text(encoding="utf-8"))

    # Find the target item in manifest
    target_item = None
    for item in manifest.get("items", []):
        if item.get("queue_id") == queue_id:
            target_item = item
            break
    if target_item is None:
        return {"status": "FAIL", "error": f"queue_id '{queue_id}' not found in manifest"}

    extracted_dir = store_path / "extracted_text"
    extracted_dir.mkdir(exist_ok=True)

    suffix = local_file.suffix.lower()
    extracted_path = extracted_dir / f"{queue_id}.txt"

    if suffix in (".txt", ".md"):
        shutil.copy2(str(local_file), str(extracted_path))
        extraction_method = "manual_text_copy"
    elif suffix == ".pdf":
        extracted_text = None
        try:
            import pypdf
            reader = pypdf.PdfReader(str(local_file))
            pages = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
            extracted_text = "\n\n".join(pages)
            extraction_method = "pypdf"
        except ImportError:
            pass
        except Exception:
            pass

        if extracted_text is None:
            try:
                import pymupdf
                doc = pymupdf.open(str(local_file))
                pages = []
                for page in doc:
                    text = page.get_text()
                    if text:
                        pages.append(text)
                extracted_text = "\n\n".join(pages)
                extraction_method = "pymupdf"
            except ImportError:
                pass
            except Exception:
                pass

        if extracted_text is None:
            return {
                "status": "FAIL",
                "error": "No PDF extraction library available. Install pypdf or pymupdf.",
            }

        extracted_path.write_text(extracted_text, encoding="utf-8")
    else:
        return {"status": "FAIL", "error": f"Unsupported file type: {suffix}. Use .txt, .md, or .pdf"}

    # Update manifest item with provenance fields
    rel_path = str(extracted_path.relative_to(store_path)).replace("\\", "/")
    target_item["full_text_status"] = "likely_full_text"
    target_item["extraction_status"] = "extracted_text"
    target_item["extraction_method"] = extraction_method
    target_item["local_text_path"] = rel_path
    target_item["acquisition_method"] = "manual_local"
    target_item["provenance"] = "user_supplied_local_file"
    target_item["provenance_verified"] = False
    target_item["usage_scope"] = "trusted_review_candidate"
    target_item["should_commit_raw"] = False
    target_item["should_commit_extracted_full_text"] = False
    target_item["notes"] = "user supplied local full text; pending trusted review"

    # Update manifest summary
    m_summary = manifest.get("summary", {})
    status_counts: dict[str, int] = {}
    extract_counts: dict[str, int] = {}
    for item in manifest.get("items", []):
        fts = item.get("full_text_status", "unknown")
        ets = item.get("extraction_status", "unknown")
        status_counts[fts] = status_counts.get(fts, 0) + 1
        extract_counts[ets] = extract_counts.get(ets, 0) + 1
    m_summary.update(status_counts)
    m_summary.update(extract_counts)
    m_summary["total_items"] = len(manifest.get("items", []))
    manifest["summary"] = m_summary

    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    # Update queue
    for qi in queue.get("items", []):
        if qi.get("queue_id") == queue_id:
            qi["full_text_status"] = "likely_full_text"
            qi["extraction_status"] = "extracted_text"
            qi["extraction_method"] = extraction_method
            qi["local_text_path"] = rel_path
            qi["acquisition_method"] = "manual_local"
            qi["provenance"] = "user_supplied_local_file"
            qi["provenance_verified"] = False
            qi["usage_scope"] = "trusted_review_candidate"
            qi["should_commit_raw"] = False
            qi["should_commit_extracted_full_text"] = False
            qi["notes"] = "user supplied local full text; pending trusted review"
            break

    # Update queue summary
    q_summary = queue.get("summary", {})
    status_counts_q: dict[str, int] = {}
    extract_counts_q: dict[str, int] = {}
    for qi in queue.get("items", []):
        fts = qi.get("full_text_status", "unknown")
        ets = qi.get("extraction_status", "unknown")
        status_counts_q[fts] = status_counts_q.get(fts, 0) + 1
        extract_counts_q[ets] = extract_counts_q.get(ets, 0) + 1
    q_summary.update(status_counts_q)
    q_summary.update(extract_counts_q)
    q_summary["total_items"] = len(queue.get("items", []))
    queue["summary"] = q_summary

    queue_path.write_text(json.dumps(queue, indent=2, ensure_ascii=False), encoding="utf-8")

    # Update review_notes.md (append, do not write original content)
    review_entry = (
        f"\n---\n\n## Paper: {queue_id} — manual_local ingest\n\n"
        f"- **Source file:** {local_file.name}\n"
        f"- **Extraction method:** {extraction_method}\n"
        f"- **Provenance:** user_supplied_local_file\n"
        f"- **Provenance verified:** no (pending human verification)\n"
        f"- **Usage scope:** trusted_review_candidate\n"
        f"- **Should commit raw:** no\n"
        f"- **Should commit extracted text:** no\n"
        f"- **Date:** manual_local ingest\n\n"
        f"**Pending trusted review.** Do not treat as verified evidence.\n"
    )
    if review_notes_path.exists():
        existing = review_notes_path.read_text(encoding="utf-8")
        # Avoid duplicate entries
        if f"{queue_id} — manual_local ingest" not in existing:
            review_notes_path.write_text(existing + review_entry, encoding="utf-8")
    else:
        review_notes_path.write_text(f"# Full-text Review Notes\n{review_entry}", encoding="utf-8")

    return {
        "status": "PASS",
        "queue_id": queue_id,
        "local_file": str(local_file),
        "extraction_method": extraction_method,
        "extracted_path": rel_path,
        "full_text_status": "likely_full_text",
        "provenance": "user_supplied_local_file",
    }
