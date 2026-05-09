#!/usr/bin/env python3
"""
ARIS Agentic Idea Discovery — Orchestrator for isolated job workflow.

Commands:
  init-run <topic>              Create run directory structure and manifest.
  create-jobs <run_id>          Generate job JSON files for each phase.
  dry-run <run_id>              Validate all job files and paths without executing.
  status <run_id>               Show run status from RUN_MANIFEST and handoffs.
"""
from __future__ import annotations

import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

TOOLS_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(TOOLS_DIR))

from env_loader import find_project_root


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slugify(text: str) -> str:
    """Create a filesystem-safe slug from topic text."""
    s = text.lower().strip()
    s = re.sub(r'[^a-z0-9]+', '_', s)
    return s[:40].strip('_')


def _generate_run_id(topic: str) -> str:
    now = datetime.now()
    slug = _slugify(topic)
    return now.strftime(f"%Y%m%d_%H%M%S_{slug}")


def _path(path: str) -> Path:
    return Path(path)


def _ensure_dir(d: Path):
    d.mkdir(parents=True, exist_ok=True)


def _extract_gap_excerpt(gap_map_path: Path, cand_path: Path, output_path: Path):
    """Extract the gap section referenced by a candidate from GAP_MAP.md.

    Reads the candidate's Linked gap field, finds the matching section
    in GAP_MAP.md, and writes a focused excerpt to output_path.
    """
    if not gap_map_path.exists():
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            f"# Gap Excerpt for {cand_path.stem}\n\n(GAP_MAP.md not found)\n",
            encoding="utf-8",
        )
        return

    cand_content = cand_path.read_text(encoding="utf-8", errors="ignore")
    gap_map_content = gap_map_path.read_text(encoding="utf-8", errors="ignore")

    # Find linked gap ID from candidate (e.g. "- Linked gap: GAP_003")
    linked_gap = ""
    for line in cand_content.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("- linked gap"):
            parts = stripped.split(":", 1)
            if len(parts) == 2:
                linked_gap = parts[1].strip()
            break

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not linked_gap:
        output_path.write_text(
            f"# Gap Excerpt for {cand_path.stem}\n\n"
            f"(No linked gap ID found in candidate file)\n",
            encoding="utf-8",
        )
        return

    # Find and extract the matching section from GAP_MAP.md
    lines = gap_map_content.splitlines()
    excerpt_lines = [
        f"# Gap Excerpt: {linked_gap}",
        f"Extracted from {gap_map_path.name} for {cand_path.stem}",
        "",
    ]

    in_section = False
    section_heading_level = 0
    for line in lines:
        heading_match = line.startswith("#")
        if not in_section and heading_match and linked_gap in line:
            in_section = True
            section_heading_level = len(line) - len(line.lstrip("#"))
            excerpt_lines.append(line)
        elif in_section:
            if heading_match:
                current_level = len(line) - len(line.lstrip("#"))
                if current_level <= section_heading_level:
                    break
            excerpt_lines.append(line)

    if not in_section:
        excerpt_lines.append(f"(Section '{linked_gap}' not found in {gap_map_path.name})")

    output_path.write_text("\n".join(excerpt_lines), encoding="utf-8")


def _read_json(path: Path) -> Any:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_json(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Directory / file layout
# ---------------------------------------------------------------------------

AGENTIC_DIR = Path("idea-stage") / "AGENTIC"
RUNS_DIR = AGENTIC_DIR / "RUNS"
JOBS_DIR_NAME = "JOBS"
HANDOFFS_DIR_NAME = "HANDOFFS"
IDEA_CARDS_DIR_NAME = "IDEA_CARDS"


def _get_run_dir(run_id: str) -> Path:
    return RUNS_DIR / run_id


def _get_jobs_dir(run_id: str) -> Path:
    return _get_run_dir(run_id) / JOBS_DIR_NAME


def _get_handoffs_dir(run_id: str) -> Path:
    return _get_run_dir(run_id) / HANDOFFS_DIR_NAME


def _get_idea_cards_dir(run_id: str) -> Path:
    return _get_run_dir(run_id) / IDEA_CARDS_DIR_NAME


# ---------------------------------------------------------------------------
# Job config templates
# ---------------------------------------------------------------------------

def _make_literature_scout_job(run_id: str, run_dir: Path) -> Dict[str, Any]:
    return {
        "job_id": f"job_{run_id}_literature_scout",
        "run_id": run_id,
        "role": "literature_scout",
        "backend": "claude_headless",
        "model_env": "LLM_LITERATURE_SCOUT_MODEL",
        "description": "Search and compile literature index for the research topic",
        "input_files": [
            str(run_dir / "INPUTS.md"),
        ],
        "output_files": [
            str(run_dir / "LITERATURE_INDEX.md"),
        ],
        "handoff_file": str(_get_handoffs_dir(run_id) / "literature_scout.md"),
        "prompt_file": "",
        "max_tokens": 8192,
        "timeout_sec": 900,
        "use_bare": True,
        "status": "pending",
    }


def _make_gap_extractor_job(run_id: str, run_dir: Path) -> Dict[str, Any]:
    return {
        "job_id": f"job_{run_id}_gap_extractor",
        "run_id": run_id,
        "role": "gap_extractor",
        "backend": "api",
        "model_env": "LLM_GAP_EXTRACTOR_MODEL",
        "description": "Extract research gaps from literature index",
        "input_files": [
            str(run_dir / "LITERATURE_INDEX.md"),
        ],
        "output_files": [
            str(run_dir / "GAP_MAP.md"),
        ],
        "handoff_file": str(_get_handoffs_dir(run_id) / "gap_extractor.md"),
        "prompt_file": "",
        "max_tokens": 8192,
        "timeout_sec": 600,
        "status": "pending",
    }


def _make_idea_generator_job(run_id: str, run_dir: Path) -> Dict[str, Any]:
    return {
        "job_id": f"job_{run_id}_idea_generator",
        "run_id": run_id,
        "role": "idea_generator",
        "backend": "api",
        "model_env": "LLM_IDEA_GENERATOR_MODEL",
        "description": "Generate 8-12 idea cards from gap map and literature",
        "input_files": [
            str(run_dir / "GAP_MAP.md"),
            str(run_dir / "LITERATURE_INDEX.md"),
        ],
        "output_files": [
            str(_get_idea_cards_dir(run_id) / "idea_001.md"),
            str(_get_idea_cards_dir(run_id) / "idea_002.md"),
            str(_get_idea_cards_dir(run_id) / "idea_003.md"),
            str(_get_idea_cards_dir(run_id) / "idea_004.md"),
            str(_get_idea_cards_dir(run_id) / "idea_005.md"),
            str(_get_idea_cards_dir(run_id) / "idea_006.md"),
            str(_get_idea_cards_dir(run_id) / "idea_007.md"),
            str(_get_idea_cards_dir(run_id) / "idea_008.md"),
        ],
        "handoff_file": str(_get_handoffs_dir(run_id) / "idea_generator.md"),
        "prompt_file": "",
        "max_tokens": 8192,
        "timeout_sec": 600,
        "status": "pending",
    }


def _make_idea_deduplicator_job(run_id: str, run_dir: Path) -> Dict[str, Any]:
    return {
        "job_id": f"job_{run_id}_idea_deduplicator",
        "run_id": run_id,
        "role": "idea_deduplicator",
        "backend": "api",
        "model_env": "LLM_IDEA_DEDUPLICATOR_MODEL",
        "description": "Deduplicate ideas against existing IDEA_BANK and create canonical candidates",
        "input_files": [
            str(_get_idea_cards_dir(run_id)),
            str(AGENTIC_DIR / "IDEA_BANK.md"),
            str(AGENTIC_DIR / "CANONICAL_IDEAS"),
        ],
        "output_files": [
            str(AGENTIC_DIR / "IDEA_BANK.md"),
            str(AGENTIC_DIR / "IDEA_BANK.json"),
        ],
        "handoff_file": str(_get_handoffs_dir(run_id) / "idea_deduplicator.md"),
        "prompt_file": "",
        "max_tokens": 8192,
        "timeout_sec": 600,
        "status": "pending",
    }


# ---------------------------------------------------------------------------
# Downstream job templates (per-candidate)
# ---------------------------------------------------------------------------

def _make_idea_reviewer_job(run_id: str, cand_path: Path, gap_excerpt: Path) -> Dict[str, Any]:
    cand_id = cand_path.stem  # e.g. CAND_001
    return {
        "job_id": f"job_{run_id}_review_{cand_id}",
        "run_id": run_id,
        "role": "idea_reviewer",
        "backend": "codex_optional",
        "model_env": "LLM_IDEA_REVIEWER_PRIMARY",
        "description": f"Independent review of {cand_id}",
        "input_files": [
            str(cand_path),
            str(gap_excerpt),
        ],
        "output_files": [
            str(AGENTIC_DIR / "REVIEWS" / f"{cand_id}_review.md"),
            str(AGENTIC_DIR / "REVIEWS" / f"{cand_id}_review.json"),
        ],
        "handoff_file": str(AGENTIC_DIR / "REVIEWS" / f"{cand_id}_handoff.md"),
        "prompt_file": "",
        "max_tokens": 4096,
        "timeout_sec": 600,
        "status": "pending",
    }


def _make_novelty_checker_job(run_id: str, cand_path: Path, lit_index: Path) -> Dict[str, Any]:
    cand_id = cand_path.stem
    return {
        "job_id": f"job_{run_id}_novelty_{cand_id}",
        "run_id": run_id,
        "role": "novelty_checker",
        "backend": "codex_optional",
        "model_env": "LLM_NOVELTY_CHECKER_PRIMARY",
        "description": f"Novelty check for {cand_id}",
        "input_files": [
            str(cand_path),
            str(lit_index) if lit_index.exists() else "",
        ],
        "output_files": [
            str(AGENTIC_DIR / "NOVELTY" / f"{cand_id}_novelty.md"),
            str(AGENTIC_DIR / "NOVELTY" / f"{cand_id}_novelty.json"),
        ],
        "handoff_file": str(AGENTIC_DIR / "NOVELTY" / f"{cand_id}_handoff.md"),
        "prompt_file": "",
        "max_tokens": 4096,
        "timeout_sec": 600,
        "status": "pending",
    }


def _make_adversarial_reviewer_job(run_id: str, cand_path: Path, review_path: Path, novelty_path: Path) -> Dict[str, Any]:
    cand_id = cand_path.stem
    return {
        "job_id": f"job_{run_id}_adversarial_{cand_id}",
        "run_id": run_id,
        "role": "adversarial_reviewer",
        "backend": "api",
        "model_env": "LLM_ADVERSARIAL_REVIEWER_FALLBACK_MODEL",
        "description": f"Adversarial review of {cand_id}",
        "input_files": [
            str(cand_path),
            str(review_path),
            str(novelty_path),
        ],
        "output_files": [
            str(AGENTIC_DIR / "ADVERSARIAL" / f"{cand_id}_adversarial.md"),
        ],
        "handoff_file": str(AGENTIC_DIR / "ADVERSARIAL" / f"{cand_id}_handoff.md"),
        "prompt_file": "",
        "max_tokens": 4096,
        "timeout_sec": 600,
        "status": "pending",
    }


def _make_final_selector_job(run_id: str) -> Dict[str, Any]:
    """Final selection reads only already-reviewed artifacts, never raw run data."""
    return {
        "job_id": f"job_{run_id}_final_selector",
        "run_id": run_id,
        "role": "final_selector",
        "backend": "api",
        "model_env": "LLM_MODEL",
        "description": "Final idea selection from reviewed/novelty-checked/adversarial-reviewed candidates",
        "input_files": [
            str(AGENTIC_DIR / "IDEA_BANK.md"),
            str(AGENTIC_DIR / "IDEA_BANK.json"),
            str(AGENTIC_DIR / "CANONICAL_IDEAS"),
            str(AGENTIC_DIR / "REVIEWS"),
            str(AGENTIC_DIR / "NOVELTY"),
            str(AGENTIC_DIR / "ADVERSARIAL"),
        ],
        "output_files": [
            str(AGENTIC_DIR / "FINAL_SELECTION" / "IDEA_SELECTION_REPORT.md"),
        ],
        "handoff_file": str(AGENTIC_DIR / "FINAL_SELECTION" / "handoff.md"),
        "prompt_file": "",
        "max_tokens": 8192,
        "timeout_sec": 600,
        "status": "pending",
        "notes": "final_selector MUST NOT read RUNS/<run_id>/IDEA_CARDS, IDEA_CARDS anywhere, or .meta/",
    }


# ---------------------------------------------------------------------------
# init-run
# ---------------------------------------------------------------------------

def cmd_init_run(args: List[str]):
    """Create run directory structure and manifest."""
    if not args:
        print("Usage: agentic_idea_discovery.py init-run <topic>", file=sys.stderr)
        sys.exit(1)

    topic = " ".join(args)
    run_id = _generate_run_id(topic)
    run_dir = _get_run_dir(run_id)

    # Create directories
    _ensure_dir(run_dir)
    _ensure_dir(_get_jobs_dir(run_id))
    _ensure_dir(_get_handoffs_dir(run_id))
    _ensure_dir(_get_idea_cards_dir(run_id))

    # Write RUN_MANIFEST.md
    now = datetime.now(timezone.utc).isoformat()
    manifest_lines = [
        f"# Run Manifest: {run_id}",
        "",
        "## Metadata",
        f"- run_id: {run_id}",
        f"- topic: {topic}",
        f"- created_at: {now}",
        f"- status: initialized",
        "",
        "## Phases",
        "",
        "| Phase | Role | Backend | Status | Handoff |",
        "|-------|------|---------|--------|---------|",
        "| 1 | literature_scout | claude_headless | pending | - |",
        "| 2 | gap_extractor | api | pending | - |",
        "| 3 | idea_generator | api | pending | - |",
        "| 4 | idea_deduplicator | api | pending | - |",
        "",
        "## Notes",
        "- Run `agentic_idea_discovery.py create-jobs {run_id}` to generate job files.",
        "- Run `isolated_job_runner.py dry-run --job-file <job.json>` to validate.",
        "- Run `isolated_job_runner.py run --job-file <job.json>` to execute each job.",
    ]
    (run_dir / "RUN_MANIFEST.md").write_text("\n".join(manifest_lines), encoding="utf-8")

    # Write INPUTS.md
    inputs_lines = [
        f"# Inputs: {run_id}",
        "",
        "## Research Direction",
        topic,
        "",
        "## Constraints",
        "- (add constraints here if any)",
        "",
        "## Files Read",
        "- (input files will be listed here)",
    ]
    (run_dir / "INPUTS.md").write_text("\n".join(inputs_lines), encoding="utf-8")

    # Update RUNS_INDEX.json
    runs_index = AGENTIC_DIR / "RUNS_INDEX.json"
    index = _read_json(runs_index)
    if "runs" not in index:
        index["runs"] = []
    index["runs"].append({
        "run_id": run_id,
        "topic": topic,
        "created_at": now,
        "status": "initialized",
    })
    _write_json(runs_index, index)

    result = {
        "run_id": run_id,
        "topic": topic,
        "run_dir": str(run_dir),
        "status": "initialized",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# create-jobs
# ---------------------------------------------------------------------------

def cmd_create_jobs(args: List[str]):
    """Generate job JSON files for each phase."""
    if not args:
        print("Usage: agentic_idea_discovery.py create-jobs <run_id>", file=sys.stderr)
        sys.exit(1)

    run_id = args[0]
    run_dir = _get_run_dir(run_id)
    if not run_dir.exists():
        print(f"Error: run {run_id} not found at {run_dir}", file=sys.stderr)
        sys.exit(1)

    jobs = [
        _make_literature_scout_job(run_id, run_dir),
        _make_gap_extractor_job(run_id, run_dir),
        _make_idea_generator_job(run_id, run_dir),
        _make_idea_deduplicator_job(run_id, run_dir),
    ]

    jobs_dir = _get_jobs_dir(run_id)
    created = []
    for job in jobs:
        role = job["role"]
        job_path = jobs_dir / f"{role}.json"
        _write_json(job_path, job)
        created.append(str(job_path))

    # Check existing input files availability
    warnings = []
    for job in jobs:
        for f in job.get("input_files", []):
            fp = Path(f)
            if not fp.exists():
                warnings.append(f"Input file not yet available: {f} (will be created by prior phases)")

    result = {
        "run_id": run_id,
        "jobs_created": len(created),
        "job_files": created,
        "warnings": warnings,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# dry-run
# ---------------------------------------------------------------------------

def cmd_dry_run(args: List[str]):
    """Validate all job files and paths without executing."""
    if not args:
        print("Usage: agentic_idea_discovery.py dry-run <run_id>", file=sys.stderr)
        sys.exit(1)

    run_id = args[0]
    strict = "--strict" in args
    run_dir = _get_run_dir(run_id)

    if not run_dir.exists():
        print(json.dumps({"error": f"Run {run_id} not found", "run_dir": str(run_dir)}, ensure_ascii=False, indent=2))
        sys.exit(1)

    jobs_dir = _get_jobs_dir(run_id)
    job_files = sorted(jobs_dir.glob("*.json")) if jobs_dir.exists() else []

    reports = []
    all_valid = True
    for jf in job_files:
        job_data = _read_json(jf)
        role = job_data.get("role", "unknown")
        backend = job_data.get("backend", "unknown")
        errors = []
        warnings = []

        # Check required fields
        for field in ("job_id", "run_id", "role", "backend"):
            if not job_data.get(field):
                errors.append(f"Missing field: {field}")

        # Check backend
        if backend not in ("api", "claude_headless", "codex_optional"):
            errors.append(f"Unknown backend: {backend}")

        # Check input files (only if --strict)
        if strict:
            for f in job_data.get("input_files", []):
                if not Path(f).exists():
                    errors.append(f"Input file not found: {f}")
        else:
            for f in job_data.get("input_files", []):
                if not Path(f).exists():
                    warnings.append(f"Input file missing (non-strict): {f}")

        # Check output file parent dirs exist
        for f in job_data.get("output_files", []):
            parent = Path(f).parent
            if not parent.exists():
                warnings.append(f"Output parent dir missing (will be created): {parent}")

        # Check handoff parent dir
        hf = job_data.get("handoff_file", "")
        if hf:
            hparent = Path(hf).parent
            if not hparent.exists():
                warnings.append(f"Handoff parent dir missing (will be created): {hparent}")

        valid = len(errors) == 0
        if not valid:
            all_valid = False

        reports.append({
            "job_file": str(jf),
            "role": role,
            "backend": backend,
            "valid": valid,
            "errors": errors,
            "warnings": warnings,
        })

    # Check RUN_MANIFEST
    manifest = run_dir / "RUN_MANIFEST.md"
    manifest_ok = manifest.exists()

    result = {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "manifest_exists": manifest_ok,
        "total_jobs": len(job_files),
        "valid": all_valid and manifest_ok,
        "jobs": reports,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

def cmd_status(args: List[str]):
    """Show run status from RUN_MANIFEST and handoffs."""
    if not args:
        # List all runs
        runs_index = AGENTIC_DIR / "RUNS_INDEX.json"
        idx = _read_json(runs_index)
        if not idx.get("runs"):
            print(json.dumps({"runs": [], "message": "No runs found."}, ensure_ascii=False, indent=2))
            return
        print(json.dumps(idx, ensure_ascii=False, indent=2))
        return

    run_id = args[0]
    run_dir = _get_run_dir(run_id)
    if not run_dir.exists():
        print(json.dumps({"error": f"Run {run_id} not found"}, ensure_ascii=False, indent=2))
        sys.exit(1)

    handoffs_dir = _get_handoffs_dir(run_id)
    handoff_files = sorted(handoffs_dir.glob("*.md")) if handoffs_dir.exists() else []

    handoff_status = {}
    for hf in handoff_files:
        content = hf.read_text(encoding="utf-8", errors="ignore")
        status = "unknown"
        for line in content.splitlines():
            if line.startswith("- status:"):
                status = line.split(":", 1)[1].strip()
                break
        handoff_status[hf.stem] = status

    # Read manifest
    manifest = run_dir / "RUN_MANIFEST.md"
    manifest_lines = manifest.read_text(encoding="utf-8", errors="ignore").splitlines() if manifest.exists() else []

    # Determine overall status
    if not manifest.exists():
        overall = "incomplete"
    elif any(s in ("failed",) for s in handoff_status.values()):
        overall = "failed"
    elif any(s == "needs_review" for s in handoff_status.values()):
        overall = "needs_review"
    elif all(s == "done" for s in handoff_status.values()) and handoff_status:
        overall = "completed"
    elif not handoff_status:
        overall = "initialized"
    else:
        overall = "in_progress"

    # Check output files
    output_files = {
        "LITERATURE_INDEX.md": (run_dir / "LITERATURE_INDEX.md").exists(),
        "GAP_MAP.md": (run_dir / "GAP_MAP.md").exists(),
        "IDEA_CARDS": _get_idea_cards_dir(run_id).exists() and any(_get_idea_cards_dir(run_id).iterdir()),
    }

    result = {
        "run_id": run_id,
        "status": overall,
        "handoffs": handoff_status,
        "output_files_exist": output_files,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# create-review-jobs
# ---------------------------------------------------------------------------

def cmd_create_review_jobs(args: List[str]):
    """Generate per-candidate idea_reviewer jobs from CANONICAL_IDEAS status.

    Usage: agentic_idea_discovery.py create-review-jobs <run_id>
    """
    if not args:
        print("Usage: agentic_idea_discovery.py create-review-jobs <run_id>", file=sys.stderr)
        sys.exit(1)

    run_id = args[0]
    run_dir = _get_run_dir(run_id)
    if not run_dir.exists():
        print(f"Error: run {run_id} not found", file=sys.stderr)
        sys.exit(1)

    gap_map = run_dir / "GAP_MAP.md"
    gap_excerpts_dir = AGENTIC_DIR / "GAP_EXCERPTS"
    _ensure_dir(gap_excerpts_dir)
    canonical_dir = AGENTIC_DIR / "CANONICAL_IDEAS"
    if not canonical_dir.exists():
        print("Error: CANONICAL_IDEAS/ not found — run idea_deduplicator first", file=sys.stderr)
        sys.exit(1)

    # Read IDEA_BANK.json for candidate status
    bank = _read_json(AGENTIC_DIR / "IDEA_BANK.json")
    candidates = bank.get("candidates", [])

    cand_files = sorted(canonical_dir.glob("CAND_*.md"))
    if not cand_files:
        print("No CAND_*.md files found in CANONICAL_IDEAS/", file=sys.stderr)
        sys.exit(1)

    jobs_dir = _get_jobs_dir(run_id) / "review"
    _ensure_dir(jobs_dir)

    created = []
    skipped = []
    for cand_path in cand_files:
        cand_id = cand_path.stem
        # Skip killed candidates
        status = "active"
        for c in candidates:
            if c.get("candidate_id") == cand_id:
                status = c.get("status", "active")
                break
        if status == "killed":
            skipped.append(cand_id)
            continue

        # Generate per-candidate gap excerpt (avoids passing RUNS/ paths)
        gap_excerpt = gap_excerpts_dir / f"{cand_id}_gap.md"
        _extract_gap_excerpt(gap_map, cand_path, gap_excerpt)

        job = _make_idea_reviewer_job(run_id, cand_path, gap_excerpt)
        job_path = jobs_dir / f"{cand_id}.json"
        _write_json(job_path, job)
        created.append(str(job_path))

    result = {
        "run_id": run_id,
        "jobs_created": len(created),
        "job_files": created,
        "skipped_killed": skipped,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# create-novelty-jobs
# ---------------------------------------------------------------------------

def cmd_create_novelty_jobs(args: List[str]):
    """Generate per-candidate novelty_checker jobs from CANONICAL_IDEAS.

    Only creates jobs for candidates that have a go/revise review verdict.
    Usage: agentic_idea_discovery.py create-novelty-jobs <run_id>
    """
    if not args:
        print("Usage: agentic_idea_discovery.py create-novelty-jobs <run_id>", file=sys.stderr)
        sys.exit(1)

    run_id = args[0]
    run_dir = _get_run_dir(run_id)
    if not run_dir.exists():
        print(f"Error: run {run_id} not found", file=sys.stderr)
        sys.exit(1)

    lit_index = run_dir / "LITERATURE_INDEX.md"
    canonical_dir = AGENTIC_DIR / "CANONICAL_IDEAS"
    reviews_dir = AGENTIC_DIR / "REVIEWS"

    cand_files = sorted(canonical_dir.glob("CAND_*.md"))
    if not cand_files:
        print("No CAND_*.md files found", file=sys.stderr)
        sys.exit(1)

    jobs_dir = _get_jobs_dir(run_id) / "novelty"
    _ensure_dir(jobs_dir)

    created = []
    skipped = []
    for cand_path in cand_files:
        cand_id = cand_path.stem
        # Only create novelty job if review verdict is go or revise
        review_file = reviews_dir / f"{cand_id}_review.md"
        if review_file.exists():
            content = review_file.read_text(encoding="utf-8", errors="ignore")
            if "kill" in content.lower() and "verdict: kill" in content.lower():
                skipped.append(f"{cand_id} (review verdict: kill)")
                continue
        # else: no review file yet, create anyway

        job = _make_novelty_checker_job(run_id, cand_path, lit_index)
        job_path = jobs_dir / f"{cand_id}.json"
        _write_json(job_path, job)
        created.append(str(job_path))

    result = {
        "run_id": run_id,
        "jobs_created": len(created),
        "job_files": created,
        "skipped": skipped,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# create-adversarial-jobs
# ---------------------------------------------------------------------------

def cmd_create_adversarial_jobs(args: List[str]):
    """Generate per-candidate adversarial_reviewer jobs.

    Only creates jobs for candidates that have both review and novelty reports.
    Usage: agentic_idea_discovery.py create-adversarial-jobs <run_id>
    """
    if not args:
        print("Usage: agentic_idea_discovery.py create-adversarial-jobs <run_id>", file=sys.stderr)
        sys.exit(1)

    run_id = args[0]
    canonical_dir = AGENTIC_DIR / "CANONICAL_IDEAS"
    reviews_dir = AGENTIC_DIR / "REVIEWS"
    novelty_dir = AGENTIC_DIR / "NOVELTY"

    cand_files = sorted(canonical_dir.glob("CAND_*.md"))
    if not cand_files:
        print("No CAND_*.md files found", file=sys.stderr)
        sys.exit(1)

    jobs_dir = _get_jobs_dir(run_id) / "adversarial"
    _ensure_dir(jobs_dir)

    created = []
    skipped = []
    for cand_path in cand_files:
        cand_id = cand_path.stem
        review_path = reviews_dir / f"{cand_id}_review.md"
        novelty_path = novelty_dir / f"{cand_id}_novelty.md"

        if not review_path.exists():
            skipped.append(f"{cand_id} (no review)")
            continue
        if not novelty_path.exists():
            skipped.append(f"{cand_id} (no novelty report)")
            continue

        job = _make_adversarial_reviewer_job(run_id, cand_path, review_path, novelty_path)
        job_path = jobs_dir / f"{cand_id}.json"
        _write_json(job_path, job)
        created.append(str(job_path))

    result = {
        "run_id": run_id,
        "jobs_created": len(created),
        "job_files": created,
        "skipped": skipped,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# create-final-selection-job
# ---------------------------------------------------------------------------

def cmd_create_final_selection_job(args: List[str]):
    """Generate the final_selector job.

    The final_selector reads only reviewed/novelty-checked artifacts,
    never raw run data or generator traces.
    Usage: agentic_idea_discovery.py create-final-selection-job <run_id>
    """
    if not args:
        print("Usage: agentic_idea_discovery.py create-final-selection-job <run_id>", file=sys.stderr)
        sys.exit(1)

    run_id = args[0]

    # Ensure source directories exist
    _ensure_dir(AGENTIC_DIR / "REVIEWS")
    _ensure_dir(AGENTIC_DIR / "NOVELTY")
    _ensure_dir(AGENTIC_DIR / "ADVERSARIAL")
    _ensure_dir(AGENTIC_DIR / "FINAL_SELECTION")

    job = _make_final_selector_job(run_id)
    jobs_dir = _get_jobs_dir(run_id) / "final_selection"
    _ensure_dir(jobs_dir)
    job_path = jobs_dir / "final_selector.json"
    _write_json(job_path, job)

    result = {
        "run_id": run_id,
        "job_file": str(job_path),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1]
    args = sys.argv[2:]

    if cmd in ("-h", "--help"):
        print(__doc__)
    elif cmd == "init-run":
        cmd_init_run(args)
    elif cmd == "create-jobs":
        cmd_create_jobs(args)
    elif cmd == "dry-run":
        cmd_dry_run(args)
    elif cmd == "status":
        cmd_status(args)
    elif cmd == "create-review-jobs":
        cmd_create_review_jobs(args)
    elif cmd == "create-novelty-jobs":
        cmd_create_novelty_jobs(args)
    elif cmd == "create-adversarial-jobs":
        cmd_create_adversarial_jobs(args)
    elif cmd == "create-final-selection-job":
        cmd_create_final_selection_job(args)
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
