"""arXiv API adapter — extracted from literature_evidence_landing.py."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ARXIV_API_BASE = "https://export.arxiv.org/api/query"
ARXIV_REQUEST_TIMEOUT = 15
ARXIV_SOURCE_URL = "https://arxiv.org/e-print/{arxiv_id}"
ARXIV_PDF_URL = "https://arxiv.org/pdf/{arxiv_id}.pdf"


def _parse_arxiv_date(date_str: str) -> str:
    """Extract year from arXiv date string like '2024-03-15' or '2024'."""
    if not date_str:
        return ""
    m = re.match(r"(\d{4})", date_str)
    return m.group(1) if m else ""


def _map_arxiv_entry_to_raw_record(entry: dict, job_id: str, query: str, retrieved_at: str) -> dict | None:
    """Map a parsed arXiv entry dict to the standard raw record schema."""
    title = entry.get("title", "").strip()
    if not title:
        return None
    authors = entry.get("authors", [])
    if isinstance(authors, str):
        authors = [a.strip() for a in authors.split(",") if a.strip()]
    year = _parse_arxiv_date(entry.get("published", ""))
    url = entry.get("url", "")
    arxiv_id = entry.get("arxiv_id", "")
    doi = entry.get("doi", "")
    if url.endswith(".pdf"):
        url = url.rsplit("/", 1)[0] if "/" in url else url
    return {
        "source": "arxiv",
        "title": title,
        "authors": authors,
        "year": year,
        "url": url,
        "doi": doi,
        "arxiv_id": arxiv_id,
        "openalex_id": "",
        "semantic_scholar_id": "",
        "abstract": entry.get("abstract", ""),
        "venue": "arXiv",
        "full_text_available": False,
        "pdf_url": "",
        "source_record_id": arxiv_id if arxiv_id else url,
        "evidence_origin": "api_export",
        "retrieved_at": retrieved_at,
        "query": query,
        "job_id": job_id,
    }


def _append_jsonl(path: Path, records: list[dict]) -> None:
    """Append records to a JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _execute_arxiv_job(job: dict, per_page: int = 10) -> dict:
    """Execute a single arXiv search job. Returns a source_job_result_v1 dict."""
    job_id = job.get("job_id", "")
    source = job.get("source", "")
    query = job.get("query", "")
    retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if source != "arxiv":
        return {
            "schema_version": "source_job_result_v1",
            "job_id": job_id, "source": source, "query": query,
            "status": "failed", "retrieved_at": retrieved_at,
            "raw_record_count": 0, "records": [],
            "error": f"source is '{source}', not 'arxiv'",
            "notes": "run-arxiv-job only accepts arxiv jobs",
        }
    search_query = f"all:{query}"
    params = {
        "search_query": search_query,
        "start": "0",
        "max_results": str(min(per_page, 50)),
        "sortBy": "relevance",
        "sortOrder": "descending",
    }
    url = ARXIV_API_BASE + "?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "literature-evidence-landing/1.0"})
        with urllib.request.urlopen(req, timeout=ARXIV_REQUEST_TIMEOUT) as resp:
            http_status = resp.status
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        http_status = e.code
        body = ""
        error_msg = f"HTTP {e.code}: {e.reason}"
        if e.code in (401, 403):
            status = "auth_failed"
        elif e.code == 429:
            status = "rate_limited"
        else:
            status = "failed"
        return {
            "schema_version": "source_job_result_v1",
            "job_id": job_id, "source": "arxiv", "query": query,
            "status": status, "http_status": http_status, "retrieved_at": retrieved_at,
            "raw_record_count": 0, "records": [], "error": error_msg, "notes": "",
        }
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        return {
            "schema_version": "source_job_result_v1",
            "job_id": job_id, "source": "arxiv", "query": query,
            "status": "failed", "http_status": 0, "retrieved_at": retrieved_at,
            "raw_record_count": 0, "records": [], "error": str(e), "notes": "",
        }
    try:
        root = ET.fromstring(body)
    except ET.ParseError as e:
        return {
            "schema_version": "source_job_result_v1",
            "job_id": job_id, "source": "arxiv", "query": query,
            "status": "failed", "http_status": http_status, "retrieved_at": retrieved_at,
            "raw_record_count": 0, "records": [],
            "error": f"XML parse error: {e}", "notes": "",
        }
    ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
    entries = root.findall("atom:entry", ns)
    if not entries:
        return {
            "schema_version": "source_job_result_v1",
            "job_id": job_id, "source": "arxiv", "query": query,
            "status": "empty", "http_status": http_status, "retrieved_at": retrieved_at,
            "raw_record_count": 0, "records": [], "error": "",
            "notes": "no entries in arXiv response",
        }
    raw_records = []
    for entry in entries:
        title_el = entry.find("atom:title", ns)
        title_text = title_el.text.strip().replace("\n", " ") if title_el is not None and title_el.text else ""
        authors = []
        for author_el in entry.findall("atom:author", ns):
            name_el = author_el.find("atom:name", ns)
            if name_el is not None and name_el.text:
                authors.append(name_el.text.strip())
        published_el = entry.find("atom:published", ns)
        published = published_el.text.strip() if published_el is not None and published_el.text else ""
        summary_el = entry.find("atom:summary", ns)
        abstract = summary_el.text.strip().replace("\n", " ") if summary_el is not None and summary_el.text else ""
        link_el = entry.find("atom:id", ns)
        url = link_el.text.strip() if link_el is not None and link_el.text else ""
        arxiv_id = ""
        if url:
            m = re.search(r"/abs/(.+?)(?:v\d+)?$", url)
            if m:
                arxiv_id = m.group(1)
        doi = ""
        doi_el = entry.find("arxiv:doi", ns)
        if doi_el is not None and doi_el.text:
            doi = doi_el.text.strip()
        rec = _map_arxiv_entry_to_raw_record(
            {"title": title_text, "authors": authors, "published": published,
             "url": url, "arxiv_id": arxiv_id, "doi": doi, "abstract": abstract},
            job_id=job_id, query=query, retrieved_at=retrieved_at,
        )
        if rec:
            raw_records.append(rec)
    if not raw_records:
        return {
            "schema_version": "source_job_result_v1",
            "job_id": job_id, "source": "arxiv", "query": query,
            "status": "empty", "http_status": http_status, "retrieved_at": retrieved_at,
            "raw_record_count": 0, "records": [], "error": "",
            "notes": "all entries failed to map",
        }
    return {
        "schema_version": "source_job_result_v1",
        "job_id": job_id, "source": "arxiv", "query": query,
        "status": "success", "http_status": http_status, "retrieved_at": retrieved_at,
        "raw_record_count": len(raw_records), "records": raw_records,
        "error": "", "notes": "",
    }


def run_arxiv_job(search_jobs_path: Path, job_id: str, output_path: Path,
                   per_page: int = 10, json_output: bool = False) -> dict:
    """Execute one arXiv job from search_jobs.json and append to job_results.jsonl."""
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
    if target_job.get("source") != "arxiv":
        result = {"status": "FAIL", "errors": [f"job source is '{target_job.get('source')}', not 'arxiv'"]}
        if json_output:
            print(json.dumps(result, indent=2))
        return result
    from tools.literature_evidence_landing import validate_job_results_dict
    job_result = _execute_arxiv_job(target_job, per_page=per_page)
    vr = validate_job_results_dict([job_result])
    if vr["status"] != "PASS":
        result = {"status": "FAIL", "errors": vr["errors"]}
        if json_output:
            print(json.dumps(result, indent=2))
        return result
    _append_jsonl(output_path, [job_result])
    result = {
        "status": "PASS", "job_id": job_id,
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


def run_arxiv_jobs(search_jobs_path: Path, output_path: Path,
                    max_jobs: int = 3, per_page: int = 10,
                    overwrite: bool = False, json_output: bool = False) -> dict:
    """Execute arXiv jobs from search_jobs.json, append to job_results.jsonl."""
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
    jobs_list = jobs_data.get("jobs", [])
    arxiv_jobs = [j for j in jobs_list if j.get("source") == "arxiv"]
    if not arxiv_jobs:
        result = {"status": "FAIL", "errors": ["no arxiv jobs found in search_jobs.json"]}
        if json_output:
            print(json.dumps(result, indent=2))
        return result
    if overwrite and output_path.exists():
        output_path.unlink()
    from tools.literature_evidence_landing import validate_job_results_dict
    executed = 0
    results = []
    for job in arxiv_jobs[:max_jobs]:
        job_result = _execute_arxiv_job(job, per_page=per_page)
        vr = validate_job_results_dict([job_result])
        if vr["status"] != "PASS":
            continue
        _append_jsonl(output_path, [job_result])
        executed += 1
        results.append({
            "job_id": job_result["job_id"],
            "status": job_result["status"],
            "raw_record_count": job_result["raw_record_count"],
        })
    result = {
        "status": "PASS", "jobs_executed": executed,
        "results": results, "output": str(output_path),
    }
    if json_output:
        print(json.dumps(result, indent=2))
    else:
        print(f"Executed {executed} arXiv job(s)")
        for r in results:
            print(f"  {r['job_id']}: status={r['status']}, records={r['raw_record_count']}")
    return result
