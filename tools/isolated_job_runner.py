#!/usr/bin/env python3
"""
ARIS Isolated Job Runner — API-first task execution engine for Agentic Idea Discovery.

Backends:
  api              — OpenAI-compatible chat completions via env_loader.
  claude_headless  — Subprocess call to `claude [--bare]` for tool-requiring tasks.
  codex_optional   — Protocol/documentation only in V1; falls back to api.

Commands:
  run              Execute a job from a JSON job file.
  status           Show status of a specific job (by job_id or run_id).
  list             List recent job runs.
  dry-run          Validate a job file without executing.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

TOOLS_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(TOOLS_DIR))

from env_loader import find_project_root, load_env, mask_secret


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_job_file(path: str) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        print(f"Error: job file not found: {path}", file=sys.stderr)
        sys.exit(1)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON in job file: {e}", file=sys.stderr)
        sys.exit(1)


def _write_handoff(handoff_path: str, content: str):
    p = Path(handoff_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def _get_llm_endpoint(base_url: str) -> str:
    """Normalize the completions endpoint URL.

    If base_url already ends with /v1, append /chat/completions.
    Otherwise append /v1/chat/completions (DeepSeek V4 API style).
    """
    url = base_url.rstrip("/")
    if url.endswith("/v1"):
        return f"{url}/chat/completions"
    return f"{url}/v1/chat/completions"


def _get_model_from_env(env_key: str, env_vars: Dict[str, str]) -> str:
    """Get model name from env, with fallback to LLM_FALLBACK_MODEL."""
    model = env_vars.get(env_key, "")
    if model:
        return model
    fallback_keys = [k for k in env_vars if "FALLBACK_MODEL" in k and env_vars[k]]
    if fallback_keys:
        return env_vars[fallback_keys[0]]
    return env_vars.get("LLM_MODEL", "deepseek-v4-pro")


def _get_env_value(keys: List[str], env_vars: Dict[str, str], default: str = "") -> str:
    """Get first non-empty env value from a list of keys."""
    for k in keys:
        v = env_vars.get(k, "")
        if v:
            return v
    return default


def _get_role_prefix(model_env: str) -> str:
    """Derive the env prefix from a model_env variable name.

    Example: LLM_GAP_EXTRACTOR_MODEL -> LLM_GAP_EXTRACTOR_
    If no recognized pattern, returns an empty string.
    """
    if model_env.endswith("_MODEL"):
        return model_env[:-5] + "_"
    if model_env.endswith("_FALLBACK_MODEL"):
        return model_env[:-12] + "_FALLBACK_"
    return ""


def _get_role_thinking_effort(model_env: str, env_vars: Dict[str, str]) -> tuple[str, str, int]:
    """Read role-specific THINKING, REASONING_EFFORT, MAX_TOKENS from env.

    Falls back to global LLM_THINKING / LLM_REASONING_EFFORT / LLM_MAX_TOKENS.
    """
    prefix = _get_role_prefix(model_env)
    thinking = env_vars.get(f"{prefix}THINKING", "") or env_vars.get("LLM_THINKING", "")
    effort = env_vars.get(f"{prefix}REASONING_EFFORT", "") or env_vars.get("LLM_REASONING_EFFORT", "")
    max_tokens_str = env_vars.get(f"{prefix}MAX_TOKENS", "") or env_vars.get("LLM_MAX_TOKENS", "4096")
    try:
        max_tokens = int(max_tokens_str)
    except (ValueError, TypeError):
        max_tokens = 4096
    return thinking, effort, max_tokens


# ---------------------------------------------------------------------------
# Output validation
# ---------------------------------------------------------------------------

def is_canonical_candidate_file(path: str) -> bool:
    """Check if a path points to a canonical candidate file.

    Must be under CANONICAL_IDEAS/ and match CAND_<digits>.md.
    REVIEWS/CAND_001_review.md and NOVELTY/CAND_001_novelty.md are NOT candidates.
    """
    norm = path.replace("\\", "/")
    if "CANONICAL_IDEAS/" not in norm:
        return False
    basename = norm.rsplit("/", 1)[-1] if "/" in norm else norm
    return bool(re.match(r"^CAND_\d+\.md$", basename))


def _extract_candidate_id(path: str) -> str:
    """Extract CAND_XXX from a canonical candidate path."""
    norm = path.replace("\\", "/")
    basename = norm.rsplit("/", 1)[-1] if "/" in norm else norm
    m = re.match(r"(CAND_\d+)", basename)
    return m.group(1) if m else ""


def validate_isolated_inputs(job: Dict[str, Any]) -> List[str]:
    """Validate that input files respect role isolation rules.

    Reviewer must only see one CAND_*.md at a time.
    Novelty checker must not see other candidates or old novelty.
    Adversarial reviewer must only see one candidate + its review + its novelty.

    Returns a list of violations (empty list = all clear).
    """
    violations: List[str] = []
    role = job.get("role", "")
    input_files = [Path(f) for f in job.get("input_files", [])]
    input_strs = [str(f) for f in input_files]

    if role == "idea_reviewer":
        # Must contain exactly one canonical candidate
        cand_files = [f for f in input_strs if is_canonical_candidate_file(f)]
        if len(cand_files) == 0:
            violations.append("idea_reviewer must have exactly one CANONICAL_IDEAS/CAND_*.md input")
        elif len(cand_files) > 1:
            violations.append(f"idea_reviewer has {len(cand_files)} CAND inputs (must be exactly 1): {cand_files}")

        # Forbidden paths
        forbidden_patterns = [
            "IDEA_CARDS", "RUNS/", "IDEA_BANK.md", "IDEA_BANK.json",
            "REVIEWS/", "NOVELTY/", "ADVERSARIAL/", "FINAL_SELECTION/",
            ".meta/", "generator_trace", "old_score", "user_preference", "praise"
        ]
        for f in input_strs:
            norm = f.replace("\\", "/")
            for pat in forbidden_patterns:
                if pat.lower() in norm.lower():
                    violations.append(f"idea_reviewer input contains forbidden path/pattern '{pat}': {f}")

    elif role == "novelty_checker":
        # Must contain exactly one canonical candidate
        cand_files = [f for f in input_strs if is_canonical_candidate_file(f)]
        if len(cand_files) == 0:
            violations.append("novelty_checker must have exactly one CAND_*.md input")
        elif len(cand_files) > 1:
            violations.append(f"novelty_checker has {len(cand_files)} CAND inputs (must be exactly 1): {cand_files}")

        # May contain LITERATURE_INDEX.md and literature-md/<paper_id>/
        # Must NOT contain other CAND, IDEA_CARDS, REVIEWS, old NOVELTY
        forbidden_patterns = [
            "IDEA_CARDS", "REVIEWS/", "NOVELTY/", "ADVERSARIAL/",
            "FINAL_SELECTION/", ".meta/"
        ]
        for f in input_strs:
            norm = f.replace("\\", "/")
            for pat in forbidden_patterns:
                if pat.lower() in norm.lower():
                    violations.append(f"novelty_checker input contains forbidden path/pattern '{pat}': {f}")

    elif role == "adversarial_reviewer":
        # Must contain exactly one canonical candidate
        cand_files = [f for f in input_strs if is_canonical_candidate_file(f)]
        if len(cand_files) == 0:
            violations.append("adversarial_reviewer must have exactly one CAND_*.md input")
        elif len(cand_files) > 1:
            violations.append(f"adversarial_reviewer has {len(cand_files)} CAND inputs (must be exactly 1): {cand_files}")

        # Extract candidate_id from the canonical candidate file
        cand_id = ""
        for f in input_strs:
            if is_canonical_candidate_file(f):
                cand_id = _extract_candidate_id(f)
                break

        # Must contain review matching this candidate_id
        if cand_id:
            has_matching_review = any(
                "REVIEWS" in (norm := f.replace("\\", "/")) and cand_id in norm
                for f in input_strs
            )
            if not has_matching_review:
                violations.append(f"adversarial_reviewer must include review for {cand_id} in REVIEWS/")
        else:
            violations.append("adversarial_reviewer: could not determine candidate_id from canonical file")

        # Must contain novelty matching this candidate_id
        if cand_id:
            has_matching_novelty = any(
                "NOVELTY" in (norm := f.replace("\\", "/")) and cand_id in norm
                for f in input_strs
            )
            if not has_matching_novelty:
                violations.append(f"adversarial_reviewer must include novelty report for {cand_id} in NOVELTY/")
        else:
            violations.append("adversarial_reviewer: could not determine candidate_id from canonical file")

        # Must NOT contain other candidates or generator trace
        forbidden_patterns = ["IDEA_CARDS", ".meta/"]
        for f in input_strs:
            norm = f.replace("\\", "/")
            for pat in forbidden_patterns:
                if pat.lower() in norm.lower():
                    violations.append(f"adversarial_reviewer input contains forbidden path/pattern '{pat}': {f}")

    elif role == "final_selector":
        # Must NOT read raw run artifacts
        forbidden_patterns = ["RUNS/", "IDEA_CARDS", ".meta/"]
        for f in input_strs:
            norm = f.replace("\\", "/")
            for pat in forbidden_patterns:
                if pat.lower() in norm.lower():
                    violations.append(f"final_selector input contains forbidden path/pattern '{pat}': {f}")

    return violations

def validate_output(role: str, output_files: List[str]) -> List[str]:
    """Validate that output files contain expected content for the given role.

    Returns a list of validation issues (empty list = all clear).
    """
    issues: List[str] = []

    if not output_files:
        issues.append("No output files specified")
        return issues

    # Check that at least one output file exists with content
    existing = [f for f in output_files if Path(f).exists() and Path(f).stat().st_size > 0]
    if not existing:
        issues.append("No output files exist with non-zero content")
        return issues

    # Role-specific content checks
    if role == "gap_extractor":
        any_content = ""
        for f in existing:
            any_content += Path(f).read_text(encoding="utf-8", errors="ignore")
        if "GAP_" not in any_content and "Gap statement" not in any_content:
            issues.append("gap_extractor output missing 'GAP_' or 'Gap statement'")
        if "Confidence:" not in any_content and "confidence:" not in any_content.lower():
            issues.append("gap_extractor output missing confidence levels")

    elif role == "idea_generator":
        # Must have at least 3 idea-like sections or 'idea_00' filenames
        idea_count = 0
        for f in existing:
            content = Path(f).read_text(encoding="utf-8", errors="ignore")
            if "# Idea Card" in content or "# Idea:" in content or "## Core Idea" in content:
                idea_count += 1
            elif "Title:" in content and "One-sentence hypothesis" in content:
                idea_count += 1
        # Also count output files that look like idea cards
        idea_files = [f for f in output_files if "idea_" in Path(f).name]
        idea_count = max(idea_count, len(idea_files))
        if idea_count < 1:
            issues.append("idea_generator produced no identifiable idea cards")
        elif idea_count < 3:
            issues.append(f"idea_generator only produced {idea_count} ideas (expected >= 3)")

        # Check output file splitting: if only 1 output file has all content, flag it
        files_with_content = 0
        for f in output_files:
            if Path(f).exists() and Path(f).stat().st_size > 50:
                files_with_content += 1
        if files_with_content <= 1 and len(output_files) > 2:
            # Multiple output files defined but content not split across them
            issues.append("Idea cards not split across output files; all content in single file")

    elif role == "idea_reviewer":
        any_content = ""
        for f in existing:
            any_content += Path(f).read_text(encoding="utf-8", errors="ignore")
        verdict_lower = any_content.lower()
        has_verdict = any(v in verdict_lower for v in ("verdict:", "## verdict"))
        if not has_verdict:
            issues.append("idea_reviewer output missing 'verdict' field")
        has_go_revise_kill = any(v in verdict_lower for v in ("go", "revise", "kill"))
        if not has_go_revise_kill:
            issues.append("idea_reviewer verdict must be one of: go, revise, kill")

    elif role == "novelty_checker":
        any_content = ""
        for f in existing:
            any_content += Path(f).read_text(encoding="utf-8", errors="ignore")
        valid_verdicts = ["confirmed_novel", "likely_incremental", "already_done", "insufficient_evidence"]
        if not any(v in any_content for v in valid_verdicts):
            issues.append("novelty_checker output missing required verdict")

    elif role == "adversarial_reviewer":
        any_content = ""
        for f in existing:
            any_content += Path(f).read_text(encoding="utf-8", errors="ignore")
        weakness_keywords = ["weakness", "fatal flaw", "reviewer objection", "vulnerability", "limitation"]
        if not any(k in any_content.lower() for k in weakness_keywords):
            issues.append("adversarial_reviewer output missing weakness/fatal flaw analysis")

    # role = literature_scout or idea_deduplicator: basic content check only
    return issues


# ---------------------------------------------------------------------------
# Handoff generation
# ---------------------------------------------------------------------------

def _generate_handoff_template(
    job: Dict[str, Any],
    status: str = "draft",
    decision: str = "",
    evidence: str = "",
    failure_modes: str = "",
    next_action: str = "",
) -> str:
    lines = [
        f"# Handoff: {job.get('job_id', 'unknown')}",
        "",
        "## Metadata",
        f"- job_id: {job.get('job_id', '')}",
        f"- run_id: {job.get('run_id', '')}",
        f"- role: {job.get('role', '')}",
        f"- backend: {job.get('backend', '')}",
        f"- created_at: {datetime.now(timezone.utc).isoformat()}",
        f"- status: {status}",
        "",
        "## Input Files",
    ]
    for f in job.get("input_files", []):
        lines.append(f"- {f}")
    if not job.get("input_files"):
        lines.append("- (none)")
    lines.extend(["", "## Output Files"])
    for f in job.get("output_files", []):
        lines.append(f"- {f}")
    if not job.get("output_files"):
        lines.append("- (none)")
    lines.extend([
        "",
        "## Decision",
        decision or "TODO: Fill decision.",
        "",
        "## Evidence",
        evidence or "TODO: Add evidence.",
        "",
        "## Failure Modes",
        failure_modes or "TODO: Add failure modes.",
        "",
        "## Unresolved Questions",
        "TODO: Add unresolved questions.",
        "",
        "## Next Action",
        next_action or "TODO: Add next action.",
        "",
        "## Do Not Assume",
        "- Do not assume this handoff is complete until evidence is filled.",
        "- Do not infer claims not supported by listed evidence.",
    ])
    return "\n".join(lines)


def _make_fallback_handoff(
    job: Dict[str, Any],
    error: str,
) -> str:
    return _generate_handoff_template(
        job, status="failed",
        decision=f"Job failed: {error}",
        evidence="Job did not complete successfully.",
        failure_modes=f"- {error}",
        next_action="Check error, fix inputs, and retry.",
    )


# ---------------------------------------------------------------------------
# API backend
# ---------------------------------------------------------------------------

def _generate_fallback_audit_header(ledger_overrides: Dict[str, Any]) -> str:
    """Generate an HTML-comment audit header documenting fallback provenance.

    Preprended to output artifacts when a fallback occurred (e.g. Codex
    unavailable → API).  The header is invisible in rendered Markdown but
    searchable in the artifact file.
    """
    lines = ["<!-- ARIS-AUDIT-BEGIN -->"]
    for key in ["primary_backend", "primary_model", "actual_backend",
                "actual_model", "fallback_used", "fallback_reason"]:
        val = ledger_overrides.get(key, "")
        lines.append(f"{key}: {val}")
    if ledger_overrides.get("fallback_used"):
        lines.append("REVIEWER_DOWNGRADED_FROM_CODEX_TO_LLM_FALLBACK: true")
    lines.append("<!-- ARIS-AUDIT-END -->")
    return "\n".join(lines)


def _backend_api(
    job: Dict[str, Any],
    env_vars: Dict[str, str],
    ledger_overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Execute a job via OpenAI-compatible chat completions API.

    ledger_overrides: optional dict merged into the llm_calls.jsonl entry
                      (used by codex_optional to record fallback provenance).
    """
    import httpx

    result: Dict[str, Any] = {
        "success": False,
        "error": None,
        "outputs_written": [],
        "handoff_written": None,
        "model_used": None,
        "fallback_used": False,
        "duration_sec": 0,
        "validation_issues": [],
    }
    start = time.time()

    api_key = env_vars.get("LLM_API_KEY", "")
    if not api_key:
        result["error"] = "LLM_API_KEY not set in .env"
        return result

    base_url = env_vars.get("LLM_BASE_URL", "https://api.deepseek.com")
    endpoint = _get_llm_endpoint(base_url)

    # Determine model and role-specific params
    model_env_key = job.get("model_env", "")
    model = _get_model_from_env(model_env_key, env_vars)
    result["model_used"] = model

    # Reject model="codex" — codex is not an API-callable model
    if model == "codex":
        result["error"] = (
            f"model='codex' is not valid for api backend. "
            f"Use codex_optional backend if Codex fallback is intended. "
            f"(model_env={model_env_key}, resolved={model})"
        )
        return result

    thinking, reasoning_effort, max_tokens = _get_role_thinking_effort(
        model_env_key, env_vars
    )
    # Allow job-level overrides
    thinking = job.get("thinking", "") or thinking
    reasoning_effort = job.get("reasoning_effort", "") or reasoning_effort
    max_tokens = job.get("max_tokens", 0) or max_tokens

    # Read prompt file or construct from job description
    prompt_file = job.get("prompt_file", "")
    if prompt_file and Path(prompt_file).exists():
        system_prompt = Path(prompt_file).read_text(encoding="utf-8")
    else:
        system_prompt = f"You are an ARIS {job.get('role', 'researcher')}.\n"
        system_prompt += f"Job: {job.get('description', '')}\n"
        system_prompt += "Read only the specified input files. Output only the required artifacts. Do not generate ideas beyond your role."

    # Read input files
    input_content = ""
    for f in job.get("input_files", []):
        fp = Path(f)
        if fp.exists():
            try:
                input_content += f"\n\n=== {f} ===\n{fp.read_text(encoding='utf-8', errors='ignore')[:50000]}"
            except Exception as e:
                input_content += f"\n\n=== {f} ===\n[Error reading: {e}]"

    user_prompt = job.get("description", "")
    if input_content:
        user_prompt = f"Input files:\n{input_content}\n\nTask: {job.get('description', '')}"

    # Construct payload
    payload: Dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": max_tokens,
    }
    if thinking and thinking != "disabled":
        payload["thinking"] = {"type": thinking}
    if reasoning_effort:
        payload["reasoning_effort"] = reasoning_effort

    # Record call in ledger
    root = find_project_root()
    calls_dir = root / ".aris" / "calls"
    calls_dir.mkdir(parents=True, exist_ok=True)

    call_id = f"job_{uuid.uuid4().hex[:8]}"
    call_entry = {
        "call_id": call_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "skill": "idea-discovery-agentic",
        "role": job.get("role", ""),
        "primary_backend": "api",
        "primary_model": model,
        "actual_backend": "api",
        "actual_model": model,
        "status": "started",
        "fallback_used": False,
        "fallback_reason": None,
        "duration_sec": 0,
        "input_files": job.get("input_files", []),
        "output_files": job.get("output_files", []),
        "env_source": ".env",
        "thinking": thinking,
        "reasoning_effort": reasoning_effort,
        "error": None,
    }

    # Apply ledger overrides (e.g. from codex_optional fallback) before writing
    if ledger_overrides:
        call_entry.update(ledger_overrides)

    (calls_dir / "current_call.json").write_text(
        json.dumps(call_entry, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    try:
        with httpx.Client(timeout=300.0) as client:
            resp = client.post(endpoint, headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }, json=payload)

        if resp.status_code != 200:
            result["error"] = f"API error {resp.status_code}: {resp.text[:500]}"
            call_entry["status"] = "failed"
            call_entry["error"] = result["error"]
        else:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            result["success"] = True

            # Prepend fallback audit header (invisible HTML comment in Markdown)
            if ledger_overrides and ledger_overrides.get("fallback_used"):
                content = _generate_fallback_audit_header(ledger_overrides) + "\n\n" + content
                result["REVIEWER_DOWNGRADED_FROM_CODEX_TO_LLM_FALLBACK"] = True

            # Write output files — first file gets full output
            output_files = job.get("output_files", [])
            if output_files:
                first_out = Path(output_files[0])
                first_out.parent.mkdir(parents=True, exist_ok=True)
                first_out.write_text(content, encoding="utf-8")
                result["outputs_written"].append(str(first_out))

                # Try to split into multiple files by === markers or # headings
                for extra_f in output_files[1:]:
                    fname = Path(extra_f).name
                    # Try === marker first
                    marker = f"=== {fname} ==="
                    if marker in content:
                        section = content.split(marker, 1)[1]
                        if "\n===" in section:
                            section = section.split("\n===")[0]
                        Path(extra_f).parent.mkdir(parents=True, exist_ok=True)
                        Path(extra_f).write_text(section.strip(), encoding="utf-8")
                        result["outputs_written"].append(str(extra_f))
                    else:
                        # Try section heading: # idea_002 or ## idea_002
                        heading_variants = [
                            f"# {Path(extra_f).stem}",
                            f"## {Path(extra_f).stem}",
                            f"### {Path(extra_f).stem}",
                        ]
                        found_heading = False
                        for hv in heading_variants:
                            if hv in content:
                                section = content.split(hv, 1)[1]
                                # Find next heading of same or higher level
                                section_lines = section.split("\n")
                                extracted = []
                                for sl in section_lines:
                                    if sl.startswith("# ") or sl.startswith("## ") or sl.startswith("### "):
                                        break
                                    extracted.append(sl)
                                Path(extra_f).parent.mkdir(parents=True, exist_ok=True)
                                Path(extra_f).write_text(
                                    hv + "\n" + "\n".join(extracted).strip(),
                                    encoding="utf-8",
                                )
                                result["outputs_written"].append(str(extra_f))
                                found_heading = True
                                break

            # Validate output
            validation_issues = validate_output(job.get("role", ""), job.get("output_files", []))
            result["validation_issues"] = validation_issues

            if call_entry.get("fallback_used"):
                call_entry["status"] = "completed_with_fallback"
            elif validation_issues:
                call_entry["status"] = "completed_with_issues"
            else:
                call_entry["status"] = "completed"

        # Write handoff
        handoff_file = job.get("handoff_file", "")
        if handoff_file:
            if result["success"] and not result["validation_issues"]:
                handoff = _generate_handoff_template(
                    job, status="done",
                    decision="Job executed successfully via API.",
                    evidence=f"Output files: {', '.join(result['outputs_written'])}",
                    failure_modes="None.",
                    next_action="Proceed to next phase.",
                )
            elif result["success"] and result["validation_issues"]:
                handoff = _generate_handoff_template(
                    job, status="needs_review",
                    decision="API call succeeded but output validation found issues.",
                    evidence=f"Output files: {', '.join(result['outputs_written'])}\nValidation issues: {'; '.join(result['validation_issues'])}",
                    failure_modes="Output did not meet expected format/quality criteria.",
                    next_action="Review output and re-run if needed.",
                )
            else:
                handoff = _make_fallback_handoff(job, result["error"])

            _write_handoff(handoff_file, handoff)
            result["handoff_written"] = handoff_file

    except Exception as e:
        result["error"] = str(e)
        result["success"] = False
        call_entry["status"] = "failed"
        call_entry["error"] = str(e)

        handoff_file = job.get("handoff_file", "")
        if handoff_file:
            handoff = _make_fallback_handoff(job, str(e))
            _write_handoff(handoff_file, handoff)
            result["handoff_written"] = handoff_file

    duration = time.time() - start
    result["duration_sec"] = int(duration)
    call_entry["duration_sec"] = int(duration)
    call_entry["completed_at"] = datetime.now(timezone.utc).isoformat()

    # Append to JSONL
    jsonl_file = calls_dir / "llm_calls.jsonl"
    with open(jsonl_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(call_entry, ensure_ascii=False) + "\n")

    (calls_dir / "current_call.json").write_text("{}", encoding="utf-8")

    return result


# ---------------------------------------------------------------------------
# codex_optional backend
# ---------------------------------------------------------------------------

def _backend_codex_optional(job: Dict[str, Any], env_vars: Dict[str, str]) -> Dict[str, Any]:
    """Execute job with Codex as primary, falling back to API.

    If the model_env resolves to "codex", Codex is preferred but unavailable
    in V1 — fallback to API with REVIEWER_DOWNGRADED_FROM_CODEX_TO_LLM_FALLBACK.
    If model_env resolves to a real model, call API directly (no fallback flag).

    Non-silent: always emits a clear fallback notification to stderr.
    """
    model_env_key = job.get("model_env", "")
    model = _get_model_from_env(model_env_key, env_vars)

    if model != "codex":
        # Not configured for Codex — call API directly
        result = _backend_api(job, env_vars)
        result["fallback_used"] = False
        return result

    # Derive role-specific fallback env key, e.g.:
    #   LLM_IDEA_REVIEWER_PRIMARY -> LLM_IDEA_REVIEWER_FALLBACK_MODEL
    #   LLM_NOVELTY_CHECKER_PRIMARY -> LLM_NOVELTY_CHECKER_FALLBACK_MODEL
    role_fallback_key = model_env_key.replace("_PRIMARY", "_FALLBACK_MODEL")
    fallback_model = env_vars.get(
        role_fallback_key,
        env_vars.get("LLM_FALLBACK_MODEL", env_vars.get("LLM_MODEL", "deepseek-v4-pro")),
    )

    # Non-silent fallback notification
    role_name = job.get("role", "unknown")
    print(
        f"[codex_optional] {role_name}: Codex unavailable (model_env={model_env_key}), "
        f"falling back to model={fallback_model}",
        file=sys.stderr,
    )

    # Override env so _backend_api resolves the fallback model instead of "codex"
    modified_env = dict(env_vars)
    modified_env[model_env_key] = fallback_model

    ledger_overrides = {
        "primary_backend": "codex_optional",
        "primary_model": "codex",
        "actual_backend": "api",
        "actual_model": fallback_model,
        "fallback_used": True,
        "fallback_reason": "Codex unavailable; fell back to role-specific LLM model",
        "status": "started",
    }
    result = _backend_api(job, modified_env, ledger_overrides=ledger_overrides)
    result["fallback_used"] = True
    result["REVIEWER_DOWNGRADED_FROM_CODEX_TO_LLM_FALLBACK"] = True
    return result


# ---------------------------------------------------------------------------
# Claude headless backend
# ---------------------------------------------------------------------------

def _check_claude_available() -> bool:
    """Check if `claude` command is available."""
    try:
        r = subprocess.run(
            ["claude", "--version"],
            capture_output=True, text=True, timeout=10,
        )
        return r.returncode == 0
    except Exception:
        return False


def _try_claude_bare(cmd_base: List[str], timeout_sec: int) -> subprocess.CompletedProcess | None:
    """Try running claude with --bare. If it fails with unknown option, retry without --bare."""
    # Try with --bare first
    cmd = cmd_base + ["--bare"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec)
        if r.returncode == 0:
            return r
        # Check if --bare was rejected
        stderr_lower = (r.stderr or "").lower()
        if "unknown option" in stderr_lower or "unrecognized" in stderr_lower or "bare" in stderr_lower:
            # Retry without --bare
            cmd_no_bare = cmd_base[:]
            r2 = subprocess.run(cmd_no_bare, capture_output=True, text=True, timeout=timeout_sec)
            return r2
        return r
    except Exception:
        return None


def _backend_claude_headless(job: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
    """Execute a job via subprocess call to `claude [--bare]`.

    In V1, this is a documented interface. Actual execution depends on local
    `claude` CLI availability.
    """
    result: Dict[str, Any] = {
        "success": False,
        "error": None,
        "outputs_written": [],
        "handoff_written": None,
        "model_used": "claude_headless",
        "fallback_used": False,
        "duration_sec": 0,
        "validation_issues": [],
    }

    if not _check_claude_available():
        result["error"] = "claude CLI not found. Install it or use api backend."
        return result

    root = find_project_root()
    timeout_sec = job.get("timeout_sec", 900)
    max_turns = job.get("max_turns", 8)
    description = job.get("description", "")
    input_files = job.get("input_files", [])
    output_files = job.get("output_files", [])
    handoff_file = job.get("handoff_file", "")

    # Build prompt
    prompt = f"Role: {job.get('role', 'researcher')}\n"
    prompt += f"Job ID: {job.get('job_id', 'unknown')}\n"
    prompt += f"Run ID: {job.get('run_id', 'unknown')}\n\n"
    prompt += f"Task: {description}\n\n"
    prompt += "Rules:\n"
    prompt += "- Read only the specified input_files.\n"
    prompt += f"  Input files: {', '.join(input_files) if input_files else '(none)'}\n"
    prompt += "- Write output to the specified output_files.\n"
    prompt += f"  Output files: {', '.join(output_files) if output_files else '(none)'}\n"
    if handoff_file:
        prompt += f"- After completing the task, write a handoff file to: {handoff_file}\n"
        prompt += "  The handoff must include: Decision, Evidence, Failure Modes, Next Action.\n"
    prompt += "- Do NOT modify project code.\n"
    prompt += "- Do NOT read other run files.\n"
    prompt += "- If evidence is insufficient, write 'insufficient_evidence'.\n"
    prompt += "- When done, output a JSON summary of what was accomplished.\n"

    if dry_run:
        result["success"] = True
        result["error"] = "dry-run — claude not actually called"
        result["outputs_written"] = output_files
        return result

    # Build claude command base (without --bare, added by _try_claude_bare)
    cmd = ["claude"]
    cmd.extend(["-p", prompt])
    cmd.extend(["--output-format", "json"])
    cmd.extend(["--max-turns", str(max_turns)])
    if root:
        cmd.extend(["--cwd", str(root)])
    allowed_tools = ["Read", "Grep", "Glob", "Write", "WebSearch", "WebFetch", "Bash"]
    for t in allowed_tools:
        cmd.extend(["--allowedTools", t])

    start = time.time()

    try:
        r = _try_claude_bare(cmd, timeout_sec)

        duration = time.time() - start
        result["duration_sec"] = int(duration)

        if r is None:
            result["error"] = "claude subprocess failed to start"
            return result

        if r.returncode != 0:
            result["error"] = f"claude exited with code {r.returncode}: {r.stderr[:500]}"
            return result

        # claude output
        stdout = r.stdout or ""

        # Write output files — DO NOT overwrite existing files
        for f in output_files:
            fp = Path(f)
            if fp.exists():
                # Already written by claude sub-agent — preserve it
                result["outputs_written"].append(str(fp))
            else:
                # Fallback: write stdout as content
                fp.parent.mkdir(parents=True, exist_ok=True)
                fp.write_text(stdout, encoding="utf-8")
                result["outputs_written"].append(str(fp))

        result["success"] = True

        # Validate output
        validation_issues = validate_output(job.get("role", ""), output_files)
        result["validation_issues"] = validation_issues

        # Write handoff if claude didn't
        if handoff_file and not Path(handoff_file).exists():
            if validation_issues:
                handoff = _generate_handoff_template(
                    job, status="needs_review",
                    decision="Claude headless agent completed but output validation found issues.",
                    evidence=f"Output files: {', '.join(result['outputs_written'])}\nValidation issues: {'; '.join(validation_issues)}",
                    failure_modes="Output did not meet expected format/quality criteria.",
                    next_action="Review output and re-run if needed.",
                )
            else:
                handoff = _generate_handoff_template(
                    job, status="done",
                    decision="Claude headless agent completed successfully.",
                    evidence=f"Output files: {', '.join(result['outputs_written'])}",
                    failure_modes="None.",
                    next_action="Proceed to next phase.",
                )
            _write_handoff(handoff_file, handoff)
            result["handoff_written"] = handoff_file

    except subprocess.TimeoutExpired:
        result["error"] = f"claude timed out after {timeout_sec}s"
    except FileNotFoundError:
        result["error"] = "claude CLI binary not found"
    except Exception as e:
        result["error"] = str(e)

    return result


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

def _validate_job(job: Dict[str, Any], strict: bool = False) -> List[str]:
    errors = []
    if not job.get("job_id"):
        errors.append("Missing required field: job_id")
    if not job.get("run_id"):
        errors.append("Missing required field: run_id")
    if not job.get("role"):
        errors.append("Missing required field: role")
    backend = job.get("backend", "")
    if backend not in ("api", "claude_headless", "codex_optional"):
        errors.append(f"Invalid backend: {backend}. Must be api, claude_headless, or codex_optional.")
    if strict:
        for f in job.get("input_files", []):
            if not Path(f).exists():
                errors.append(f"Input file not found: {f}")
    return errors


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_run(args: List[str]):
    """Execute a job file."""
    if not args:
        print("Usage: isolated_job_runner.py run --job-file <job.json> [--strict]", file=sys.stderr)
        sys.exit(1)

    job_file = None
    strict = False
    for i, a in enumerate(args):
        if a == "--job-file" and i + 1 < len(args):
            job_file = args[i + 1]
        if a == "--strict":
            strict = True

    if not job_file:
        print("Error: --job-file <path> required", file=sys.stderr)
        sys.exit(1)

    job = _read_job_file(job_file)
    errors = _validate_job(job, strict=strict)
    if errors:
        print("Job validation errors:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)

    # Input isolation check — fail fast before any model call
    isolation_errors = validate_isolated_inputs(job)
    if isolation_errors:
        print("Input isolation violations (refusing to execute):", file=sys.stderr)
        for e in isolation_errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)

    env_info = load_env()
    env_vars = env_info.get("vars", {})
    backend = job.get("backend", "api")

    print(json.dumps({
        "job_id": job["job_id"],
        "run_id": job["run_id"],
        "role": job["role"],
        "backend": backend,
        "status": "running",
    }, ensure_ascii=False, indent=2))

    if backend == "api":
        result = _backend_api(job, env_vars)
    elif backend == "claude_headless":
        result = _backend_claude_headless(job)
    elif backend == "codex_optional":
        result = _backend_codex_optional(job, env_vars)
    else:
        print(f"Unknown backend: {backend}", file=sys.stderr)
        sys.exit(1)

    result["job_id"] = job["job_id"]
    result["backend"] = backend
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_status(args: List[str]):
    """Show status of jobs. Accepts job_id or run_id."""
    if not args:
        # Show recent jobs from ledger
        root = find_project_root()
        jsonl_file = root / ".aris" / "calls" / "llm_calls.jsonl"
        jobs = []
        if jsonl_file.exists():
            with open(jsonl_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entry = json.loads(line)
                            if entry.get("skill") == "idea-discovery-agentic":
                                jobs.append({
                                    "call_id": entry.get("call_id", ""),
                                    "role": entry.get("role", ""),
                                    "status": entry.get("status", ""),
                                    "timestamp": entry.get("timestamp", ""),
                                    "error": entry.get("error"),
                                })
                        except json.JSONDecodeError:
                            continue
        print(json.dumps(jobs[:20] if jobs else [], ensure_ascii=False, indent=2))
        return

    query = args[0]
    root = find_project_root()
    jsonl_file = root / ".aris" / "calls" / "llm_calls.jsonl"
    if jsonl_file.exists():
        with open(jsonl_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and query in line:
                    try:
                        entry = json.loads(line)
                        print(json.dumps(entry, ensure_ascii=False, indent=2))
                        return
                    except json.JSONDecodeError:
                        continue
    print(json.dumps({"status": "not_found", "query": query}, ensure_ascii=False, indent=2))


def cmd_list(args: List[str]):
    """List recent runs from RUNS_INDEX.json."""
    root = find_project_root()
    runs_index = root / "idea-stage" / "AGENTIC" / "RUNS_INDEX.json"
    if runs_index.exists():
        try:
            data = json.loads(runs_index.read_text(encoding="utf-8"))
            print(json.dumps(data, ensure_ascii=False, indent=2))
            return
        except Exception:
            pass
    print(json.dumps({"runs": [], "message": "No runs yet."}, ensure_ascii=False, indent=2))


def cmd_dry_run(args: List[str]):
    """Validate a job file without executing.

    By default, missing input files produce warnings, not errors.
    Use --strict to require all input files to exist.
    """
    if not args:
        print("Usage: isolated_job_runner.py dry-run --job-file <job.json> [--strict]", file=sys.stderr)
        sys.exit(1)

    job_file = None
    strict = False
    for i, a in enumerate(args):
        if a == "--job-file" and i + 1 < len(args):
            job_file = args[i + 1]
        if a == "--strict":
            strict = True

    if not job_file:
        print("Error: --job-file <path> required", file=sys.stderr)
        sys.exit(1)

    job = _read_job_file(job_file)
    errors = _validate_job(job, strict=strict)
    backend = job.get("backend", "api")

    # Non-strict: check missing input files as warnings only
    warnings: List[str] = []
    if not strict:
        for f in job.get("input_files", []):
            if not Path(f).exists():
                warnings.append(f"Input file will be missing: {f}")

    report = {
        "job_id": job.get("job_id", "unknown"),
        "run_id": job.get("run_id", "unknown"),
        "role": job.get("role", "unknown"),
        "backend": backend,
        "errors": errors,
        "warnings": warnings,
        "valid": len(errors) == 0,
        "dry_run": True,
    }

    # Input isolation check
    iso_errors = validate_isolated_inputs(job)
    if iso_errors:
        errors.extend(f"Input isolation violation: {e}" for e in iso_errors)
        report["isolation_violations"] = iso_errors
        report["valid"] = False

    if backend == "claude_headless":
        claude_ok = _check_claude_available()
        report["claude_available"] = claude_ok
        if not claude_ok:
            report["warnings"].append("claude CLI not available locally")

    if not errors:
        report["would_execute"] = True
        report["input_files"] = job.get("input_files", [])
        report["output_files"] = job.get("output_files", [])
        report["model_env"] = job.get("model_env", "default")

    print(json.dumps(report, ensure_ascii=False, indent=2))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1]
    args = sys.argv[2:]

    if cmd in ("-h", "--help"):
        print(__doc__)
    elif cmd == "run":
        cmd_run(args)
    elif cmd == "status":
        cmd_status(args)
    elif cmd == "list":
        cmd_list(args)
    elif cmd == "dry-run":
        cmd_dry_run(args)
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        print("Usage: isolated_job_runner.py <run|status|list|dry-run> [args...]", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
