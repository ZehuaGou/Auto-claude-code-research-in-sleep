"""Crossref API adapter — extracted from literature_evidence_landing.py."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

CROSSREF_API_BASE = "https://api.crossref.org/works"
CROSSREF_REQUEST_TIMEOUT = 15


def _parse_crossref_date(date_parts) -> str:
    """Extract year from Crossref date parts like [[2024, 3, 15]]."""
    if not date_parts or not isinstance(date_parts, list):
        return ""
    if date_parts and isinstance(date_parts[0], list) and date_parts[0]:
        return str(date_parts[0][0])
    if date_parts and isinstance(date_parts[0], int):
        return str(date_parts[0])
    return ""


def _map_crossref_item_to_raw_record(item: dict, job_id: str, query: str, retrieved_at: str) -> dict | None:
    """Map a Crossref work item to the standard raw record schema."""
    title_list = item.get("title", [])
    title = title_list[0].strip() if title_list and isinstance(title_list[0], str) else ""
    if not title:
        return None
    authors = []
    for author in item.get("author", []):
        name_parts = []
        if author.get("given"):
            name_parts.append(author["given"])
        if author.get("family"):
            name_parts.append(author["family"])
        if name_parts:
            authors.append(" ".join(name_parts))
    year = ""
    for date_field in ("published-print", "published-online", "issued"):
        dp = item.get(date_field, {}).get("date-parts")
        year = _parse_crossref_date(dp)
        if year:
            break
    doi = item.get("DOI", "")
    url = item.get("URL", "")
    if doi and not url:
        url = f"https://doi.org/{doi}"
    container = item.get("container-title", [])
    venue = container[0] if container and isinstance(container[0], str) else ""
    abstract = item.get("abstract", "")
    if abstract:
        abstract = re.sub(r"<[^>]+>", "", abstract).strip()
    source_record_id = doi if doi else url
    return {
        "source": "crossref",
        "title": title,
        "authors": authors,
        "year": year,
        "url": url,
        "doi": doi,
        "arxiv_id": "",
        "openalex_id": "",
        "semantic_scholar_id": "",
        "abstract": abstract,
        "venue": venue,
        "full_text_available": False,
        "pdf_url": "",
        "source_record_id": source_record_id,
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


def _execute_crossref_job(job: dict, per_page: int = 10) -> dict:
    """Execute a single Crossref search job. Returns a source_job_result_v1 dict."""
    job_id = job.get("job_id", "")
    source = job.get("source", "")
    query = job.get("query", "")
    time_range = job.get("time_range", {})
    retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if source != "crossref":
        return {
            "schema_version": "source_job_result_v1",
            "job_id": job_id, "source": source, "query": query,
            "status": "failed", "retrieved_at": retrieved_at,
            "raw_record_count": 0, "records": [],
            "error": f"source is '{source}', not 'crossref'",
            "notes": "run-crossref-job only accepts crossref jobs",
        }
    params = {
        "query.bibliographic": query,
        "rows": str(min(per_page, 50)),
        "sort": "score",
        "order": "desc",
    }
    if isinstance(time_range, dict):
        sy = time_range.get("start_year")
        ey = time_range.get("end_year")
        if isinstance(sy, int) and isinstance(ey, int):
            params["filter"] = f"from-pub-date:{sy},until-pub-date:{ey}"
    url = CROSSREF_API_BASE + "?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "literature-evidence-landing/1.0 (mailto:research@example.com)",
        })
        with urllib.request.urlopen(req, timeout=CROSSREF_REQUEST_TIMEOUT) as resp:
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
            "job_id": job_id, "source": "crossref", "query": query,
            "status": status, "http_status": http_status, "retrieved_at": retrieved_at,
            "raw_record_count": 0, "records": [], "error": error_msg, "notes": "",
        }
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        return {
            "schema_version": "source_job_result_v1",
            "job_id": job_id, "source": "crossref", "query": query,
            "status": "failed", "http_status": 0, "retrieved_at": retrieved_at,
            "raw_record_count": 0, "records": [], "error": str(e), "notes": "",
        }
    try:
        data = json.loads(body)
    except json.JSONDecodeError as e:
        return {
            "schema_version": "source_job_result_v1",
            "job_id": job_id, "source": "crossref", "query": query,
            "status": "failed", "http_status": http_status, "retrieved_at": retrieved_at,
            "raw_record_count": 0, "records": [],
            "error": f"JSON parse error: {e}", "notes": "",
        }
    message = data.get("message", {})
    items = message.get("items", [])
    if not items:
        return {
            "schema_version": "source_job_result_v1",
            "job_id": job_id, "source": "crossref", "query": query,
            "status": "empty", "http_status": http_status, "retrieved_at": retrieved_at,
            "raw_record_count": 0, "records": [], "error": "",
            "notes": "no items in Crossref response",
        }
    raw_records = []
    for item in items:
        rec = _map_crossref_item_to_raw_record(item, job_id=job_id, query=query, retrieved_at=retrieved_at)
        if rec:
            raw_records.append(rec)
    if not raw_records:
        return {
            "schema_version": "source_job_result_v1",
            "job_id": job_id, "source": "crossref", "query": query,
            "status": "empty", "http_status": http_status, "retrieved_at": retrieved_at,
            "raw_record_count": 0, "records": [], "error": "",
            "notes": "all items failed to map",
        }
    return {
        "schema_version": "source_job_result_v1",
        "job_id": job_id, "source": "crossref", "query": query,
        "status": "success", "http_status": http_status, "retrieved_at": retrieved_at,
        "raw_record_count": len(raw_records), "records": raw_records,
        "error": "", "notes": "",
    }


def run_crossref_job(search_jobs_path: Path, job_id: str, output_path: Path,
                      per_page: int = 10, json_output: bool = False) -> dict:
    """Execute one Crossref job from search_jobs.json and append to job_results.jsonl."""
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
    if target_job.get("source") != "crossref":
        result = {"status": "FAIL", "errors": [f"job source is '{target_job.get('source')}', not 'crossref'"]}
        if json_output:
            print(json.dumps(result, indent=2))
        return result
    from tools.literature_evidence_landing import validate_job_results_dict
    job_result = _execute_crossref_job(target_job, per_page=per_page)
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


def run_crossref_jobs(search_jobs_path: Path, output_path: Path,
                       max_jobs: int = 3, per_page: int = 10,
                       overwrite: bool = False, json_output: bool = False) -> dict:
    """Execute Crossref jobs from search_jobs.json, append to job_results.jsonl."""
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
    crossref_jobs = [j for j in jobs_list if j.get("source") == "crossref"]
    if not crossref_jobs:
        result = {"status": "FAIL", "errors": ["no crossref jobs found in search_jobs.json"]}
        if json_output:
            print(json.dumps(result, indent=2))
        return result
    if overwrite and output_path.exists():
        output_path.unlink()
    from tools.literature_evidence_landing import validate_job_results_dict
    executed = 0
    results = []
    for job in crossref_jobs[:max_jobs]:
        job_result = _execute_crossref_job(job, per_page=per_page)
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
        print(f"Executed {executed} Crossref job(s)")
        for r in results:
            print(f"  {r['job_id']}: status={r['status']}, records={r['raw_record_count']}")
    return result
