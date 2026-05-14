"""OpenAlex API adapter — extracted from literature_evidence_landing.py."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OPENALEX_API_BASE = "https://api.openalex.org/works"
OPENALEX_REQUEST_TIMEOUT = 15


def _openalex_work_id_from_url(openalex_id_url: str) -> str:
    """Extract W... ID from an OpenAlex URL like https://openalex.org/W12345."""
    if not openalex_id_url:
        return ""
    url = str(openalex_id_url).strip()
    if "/" in url:
        parts = url.rstrip("/").split("/")
        return parts[-1] if parts else ""
    return url


def _normalize_openalex_doi(doi_url: str) -> str:
    """Normalize DOI from https://doi.org/10.xxxx to bare 10.xxxx."""
    if not doi_url:
        return ""
    doi = str(doi_url).strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "http://dx.doi.org/"):
        if doi.lower().startswith(prefix.lower()):
            doi = doi[len(prefix):]
            break
    return doi


def _reconstruct_openalex_abstract(abstract_inverted_index) -> str:
    """Reconstruct abstract from OpenAlex abstract_inverted_index format."""
    if not abstract_inverted_index or not isinstance(abstract_inverted_index, dict):
        return ""
    position_word = []
    for word, positions in abstract_inverted_index.items():
        if isinstance(positions, list):
            for pos in positions:
                if isinstance(pos, int):
                    position_word.append((pos, word))
    position_word.sort(key=lambda x: x[0])
    return " ".join(pw[1] for pw in position_word)


def _map_openalex_work_to_raw_record(work: dict, job_id: str, query: str, retrieved_at: str) -> dict | None:
    """Map an OpenAlex work object to a raw_results record. Returns None if title missing."""
    if not isinstance(work, dict):
        return None
    title = work.get("display_name") or work.get("title") or ""
    if not title.strip():
        return None
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
    year = work.get("publication_year", "")
    openalex_id_raw = work.get("id", "")
    openalex_id = _openalex_work_id_from_url(openalex_id_raw)
    url = f"https://openalex.org/{openalex_id}" if openalex_id else ""
    doi_raw = work.get("doi", "") or ""
    ids = work.get("ids", {})
    if not doi_raw and isinstance(ids, dict):
        doi_raw = ids.get("doi", "") or ""
    doi = _normalize_openalex_doi(doi_raw)
    arxiv_id = ""
    if isinstance(ids, dict):
        arxiv_raw = ids.get("arxiv", "") or ""
        if arxiv_raw:
            arxiv_id = str(arxiv_raw).strip()
    venue = ""
    primary_location = work.get("primary_location", {})
    if isinstance(primary_location, dict):
        source_obj = primary_location.get("source", {})
        if isinstance(source_obj, dict):
            venue = source_obj.get("display_name", "") or ""
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


def _append_jsonl(path: Path, records: list[dict]) -> None:
    """Append records to a JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _execute_openalex_job(job: dict, per_page: int = 5, mailto: str = "") -> dict:
    """Execute a single OpenAlex search job. Returns a source_job_result_v1 dict."""
    job_id = job.get("job_id", "")
    source = job.get("source", "")
    query = job.get("query", "")
    time_range = job.get("time_range", {})
    retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if source != "openalex":
        return {
            "schema_version": "source_job_result_v1",
            "job_id": job_id, "source": source, "query": query,
            "status": "failed", "retrieved_at": retrieved_at,
            "raw_record_count": 0, "records": [],
            "error": f"source is '{source}', not 'openalex'",
            "notes": "run-openalex-job only accepts openalex jobs",
        }
    params = {
        "search": query,
        "per-page": str(min(per_page, 50)),
        "sort": "relevance_score:desc",
    }
    if isinstance(time_range, dict):
        sy = time_range.get("start_year")
        ey = time_range.get("end_year")
        if isinstance(sy, int) and isinstance(ey, int):
            params["filter"] = f"publication_year:{sy}-{ey}"
    if mailto:
        params["mailto"] = mailto
    url = OPENALEX_API_BASE + "?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "literature-evidence-landing/1.0"})
        with urllib.request.urlopen(req, timeout=OPENALEX_REQUEST_TIMEOUT) as resp:
            http_status = resp.status
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        http_status = e.code
        body = ""
        error_msg = f"HTTP {e.code}: {e.reason}"
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
            "job_id": job_id, "source": "openalex", "query": query,
            "status": status, "http_status": http_status, "retrieved_at": retrieved_at,
            "raw_record_count": 0, "records": [], "error": error_msg, "notes": "",
        }
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        return {
            "schema_version": "source_job_result_v1",
            "job_id": job_id, "source": "openalex", "query": query,
            "status": "failed", "retrieved_at": retrieved_at,
            "raw_record_count": 0, "records": [],
            "error": f"network error: {e}", "notes": "",
        }
    try:
        data = json.loads(body)
    except json.JSONDecodeError as e:
        return {
            "schema_version": "source_job_result_v1",
            "job_id": job_id, "source": "openalex", "query": query,
            "status": "failed", "http_status": http_status, "retrieved_at": retrieved_at,
            "raw_record_count": 0, "records": [],
            "error": f"JSON parse error: {e}", "notes": "",
        }
    results = data.get("results", [])
    if not isinstance(results, list):
        results = []
    raw_records = []
    for work in results:
        rec = _map_openalex_work_to_raw_record(work, job_id, query, retrieved_at)
        if rec is not None:
            raw_records.append(rec)
    status = "success" if raw_records else "empty"
    return {
        "schema_version": "source_job_result_v1",
        "job_id": job_id, "source": "openalex", "query": query,
        "status": status, "http_status": http_status, "retrieved_at": retrieved_at,
        "raw_record_count": len(raw_records), "records": raw_records,
        "error": "", "notes": "",
    }


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
    if target_job.get("source") != "openalex":
        result = {"status": "FAIL", "errors": [f"job source is '{target_job.get('source')}', not 'openalex'"]}
        if json_output:
            print(json.dumps(result, indent=2))
        return result
    # Import validator from main module to avoid circular imports
    from tools.literature_evidence_landing import validate_job_results_dict
    job_result = _execute_openalex_job(target_job, per_page=per_page, mailto=mailto)
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
    all_jobs = jobs_data.get("jobs", [])
    openalex_jobs = [j for j in all_jobs if j.get("source") == "openalex"]
    if not openalex_jobs:
        result = {"status": "FAIL", "errors": ["no openalex jobs found in search_jobs.json"]}
        if json_output:
            print(json.dumps(result, indent=2))
        return result
    jobs_to_run = openalex_jobs[:max_jobs]
    if overwrite and output_path.exists():
        output_path.unlink()
    from tools.literature_evidence_landing import validate_job_results_dict
    executed = []
    for job in jobs_to_run:
        job_result = _execute_openalex_job(job, per_page=per_page, mailto=mailto)
        vr = validate_job_results_dict([job_result])
        if vr["status"] != "PASS":
            job_result = {
                "schema_version": "source_job_result_v1",
                "job_id": job.get("job_id", ""),
                "source": "openalex", "query": job.get("query", ""),
                "status": "failed",
                "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "raw_record_count": 0, "records": [],
                "error": f"validation failed: {vr['errors']}", "notes": "",
            }
        _append_jsonl(output_path, [job_result])
        executed.append({
            "job_id": job_result["job_id"],
            "status": job_result["status"],
            "raw_record_count": job_result["raw_record_count"],
        })
    result = {
        "status": "PASS", "executed_count": len(executed),
        "executed": executed, "output": str(output_path),
    }
    if json_output:
        print(json.dumps(result, indent=2))
    else:
        print(f"Executed {len(executed)} openalex job(s) -> {output_path}")
        for e in executed:
            print(f"  {e['job_id']}: status={e['status']}, records={e['raw_record_count']}")
    return result
