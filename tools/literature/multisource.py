"""Multi-source pipeline orchestrator — extracted from literature_evidence_landing.py."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


def _append_jsonl(path: Path, records: list[dict]) -> None:
    """Append records to a JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _execute_jobs_by_source(search_jobs_path: Path, output_path: Path,
                             max_jobs: int, per_page: int,
                             sources: list[str], overwrite: bool) -> dict:
    """Execute jobs from search_jobs.json filtered by source list.
    Dispatches to the appropriate source adapter. Returns summary."""
    from tools.literature.adapters.openalex import _execute_openalex_job
    from tools.literature.adapters.arxiv import _execute_arxiv_job
    from tools.literature.adapters.crossref import _execute_crossref_job
    from tools.literature_evidence_landing import validate_job_results_dict

    if not search_jobs_path.exists():
        return {"status": "FAIL", "errors": ["search_jobs.json not found"]}

    try:
        jobs_data = json.loads(search_jobs_path.read_text(encoding="utf-8", errors="ignore"))
    except json.JSONDecodeError as e:
        return {"status": "FAIL", "errors": [f"invalid JSON: {e}"]}

    jobs_list = jobs_data.get("jobs", [])
    filtered_jobs = [j for j in jobs_list if j.get("source") in sources]

    if not filtered_jobs:
        return {"status": "FAIL", "errors": [f"no jobs found for sources: {sources}"]}

    if overwrite and output_path.exists():
        output_path.unlink()

    executed = 0
    results = []
    for job in filtered_jobs[:max_jobs]:
        source = job.get("source", "")
        if source == "openalex":
            jr = _execute_openalex_job(job, per_page=per_page)
        elif source == "arxiv":
            jr = _execute_arxiv_job(job, per_page=per_page)
        elif source == "crossref":
            jr = _execute_crossref_job(job, per_page=per_page)
        else:
            continue

        vr = validate_job_results_dict([jr])
        if vr["status"] != "PASS":
            continue
        _append_jsonl(output_path, [jr])
        executed += 1
        results.append({
            "job_id": jr["job_id"],
            "source": source,
            "status": jr["status"],
            "raw_record_count": jr["raw_record_count"],
        })

    return {
        "status": "PASS",
        "jobs_executed": executed,
        "results": results,
        "output": str(output_path),
    }


def run_multisource_pipeline(
    topic: str,
    intent: str,
    must_include: list[str],
    sources: list[str],
    run_dir: Path,
    start_year: int | None = None,
    end_year: int | None = None,
    max_results_per_source: int = 10,
    max_jobs: int = 9,
    per_page: int = 10,
    top_k: int = 10,
    overwrite: bool = False,
    exclude: str = "",
    dry_run: bool = False,
    json_output: bool = False,
) -> dict:
    """Run multi-source literature evidence pipeline.
    Supports openalex, arxiv, crossref. No Semantic Scholar in this phase.
    No model calls. No PDF downloads."""
    from tools.literature_evidence_landing import (
        _check_run_dir_safe,
        build_search_plan,
        build_search_jobs,
        validate_job_results,
        normalize_job_results,
        validate_raw,
        build_candidates,
        validate_candidates,
        build_top_k,
        summarize_run,
    )

    steps_executed = []

    safety_errors = _check_run_dir_safe(run_dir)
    if safety_errors:
        result = {"status": "FAIL", "failed_step": "prepare_run_dir", "errors": safety_errors, "steps_executed": steps_executed, "dry_run": dry_run}
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    if run_dir.exists():
        if not overwrite:
            result = {"status": "FAIL", "failed_step": "prepare_run_dir", "errors": [f"run_dir already exists; use --overwrite"], "steps_executed": steps_executed, "dry_run": dry_run}
            if json_output:
                print(json.dumps(result, indent=2))
            return result
        shutil.rmtree(run_dir)

    run_dir.mkdir(parents=True, exist_ok=True)

    if start_year is None:
        start_year = 2020
    if end_year is None:
        end_year = datetime.now(timezone.utc).year

    allowed_sources = {"openalex", "arxiv", "crossref"}
    sources = [s for s in sources if s in allowed_sources]
    if not sources:
        result = {"status": "FAIL", "failed_step": "validate_sources", "errors": ["no valid sources provided"], "steps_executed": steps_executed, "dry_run": dry_run}
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    plan_path = run_dir / "search_plan.yaml"
    jobs_path = run_dir / "search_jobs.json"
    job_results_path = run_dir / "job_results.jsonl"
    raw_results_path = run_dir / "raw_results.jsonl"
    candidates_path = run_dir / "candidates.jsonl"

    # Step 1: build_search_plan
    plan_result = build_search_plan(
        topic=topic, intent=intent, must_include=must_include,
        sources=sources, start_year=start_year, end_year=end_year,
        max_results_per_source=max_results_per_source,
        output_path=plan_path, exclude=exclude, json_output=False,
    )
    steps_executed.append({"step": "build_search_plan", "status": plan_result["status"]})
    if plan_result["status"] != "PASS":
        result = {"status": "FAIL", "failed_step": "build_search_plan", "errors": plan_result.get("errors", []), "steps_executed": steps_executed, "dry_run": dry_run}
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    # Step 2: build_search_jobs
    jobs_result = build_search_jobs(plan_path, jobs_path, json_output=False)
    steps_executed.append({"step": "build_search_jobs", "status": jobs_result["status"]})
    if jobs_result["status"] != "PASS":
        result = {"status": "FAIL", "failed_step": "build_search_jobs", "errors": jobs_result.get("errors", []), "steps_executed": steps_executed, "dry_run": dry_run}
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    if dry_run:
        result = {
            "status": "PASS", "dry_run": True, "run_dir": str(run_dir),
            "steps_executed": steps_executed,
            "files_created": [str(plan_path), str(jobs_path)],
        }
        if json_output:
            print(json.dumps(result, indent=2))
        else:
            print(f"Dry-run complete. Plan + jobs written to {run_dir}")
        return result

    # Step 3: execute jobs by source
    exec_result = _execute_jobs_by_source(
        search_jobs_path=jobs_path, output_path=job_results_path,
        max_jobs=max_jobs, per_page=per_page, sources=sources, overwrite=overwrite,
    )
    steps_executed.append({"step": "execute_jobs_by_source", "status": exec_result["status"]})
    if exec_result["status"] != "PASS":
        result = {"status": "FAIL", "failed_step": "execute_jobs_by_source", "errors": exec_result.get("errors", []), "steps_executed": steps_executed, "dry_run": False}
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    # Step 4: validate_job_results
    vjr_result = validate_job_results(job_results_path, json_output=False)
    steps_executed.append({"step": "validate_job_results", "status": vjr_result["status"]})
    if vjr_result["status"] != "PASS":
        result = {"status": "FAIL", "failed_step": "validate_job_results", "errors": vjr_result.get("errors", []), "steps_executed": steps_executed, "dry_run": False}
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    # Step 5: normalize_job_results
    norm_result = normalize_job_results(job_results_path, raw_results_path, json_output=False)
    steps_executed.append({"step": "normalize_job_results", "status": norm_result["status"]})
    if norm_result["status"] != "PASS":
        result = {"status": "FAIL", "failed_step": "normalize_job_results", "errors": norm_result.get("errors", []), "steps_executed": steps_executed, "dry_run": False}
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    # Step 6: validate_raw
    vr_result = validate_raw(raw_results_path, json_output=False)
    steps_executed.append({"step": "validate_raw", "status": vr_result["status"]})
    if vr_result["status"] not in ("PASS", "valid", "valid_with_warnings"):
        result = {"status": "FAIL", "failed_step": "validate_raw", "errors": vr_result.get("errors", []), "steps_executed": steps_executed, "dry_run": False}
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    # Step 7: build_candidates
    cand_result = build_candidates(run_dir, json_output=False)
    steps_executed.append({"step": "build_candidates", "status": cand_result["status"]})
    if cand_result["status"] not in ("PASS", "built"):
        result = {"status": "FAIL", "failed_step": "build_candidates", "errors": cand_result.get("errors", []), "steps_executed": steps_executed, "dry_run": False}
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    # Step 8: validate_candidates
    vc_result = validate_candidates(candidates_path, json_output=False)
    steps_executed.append({"step": "validate_candidates", "status": vc_result["status"]})
    if vc_result["status"] not in ("PASS", "valid", "valid_with_warnings"):
        result = {"status": "FAIL", "failed_step": "validate_candidates", "errors": vc_result.get("errors", []), "steps_executed": steps_executed, "dry_run": False}
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    # Step 9: build_top_k
    tk_result = build_top_k(run_dir, top_k, json_output=False)
    steps_executed.append({"step": "build_top_k", "status": tk_result["status"]})
    if tk_result["status"] not in ("PASS", "built"):
        result = {"status": "FAIL", "failed_step": "build_top_k", "errors": tk_result.get("errors", []), "steps_executed": steps_executed, "dry_run": False}
        if json_output:
            print(json.dumps(result, indent=2))
        return result

    # Step 10: summarize
    summary = summarize_run(run_dir, json_output=False)

    result = {
        "status": "PASS", "dry_run": False, "run_dir": str(run_dir),
        "steps_executed": steps_executed, "summary": summary,
    }
    if json_output:
        print(json.dumps(result, indent=2))
    else:
        print(f"Multi-source pipeline complete. Run directory: {run_dir}")
        for s in steps_executed:
            print(f"  {s['step']}: {s['status']}")
    return result
