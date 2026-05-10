#!/usr/bin/env python3
"""
ARIS Model Route Resolver — Resolve codex/deepseek routing for a given role.

Reads ARIS_CODEX_GATE_MODE from .env / environment, plus per-role overrides,
and outputs a JSON routing decision for the requested role.

Usage:
    python tools/model_route.py final_selector
    python tools/model_route.py novelty_checker
    python tools/model_route.py idea_reviewer
    python tools/model_route.py --help

Exit code: 0 on success, 1 on unknown role or missing env.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

# Critical judgment gate roles (Codex-priority by default)
CRITICAL_ROLES = frozenset({
    "evidence_integrity_auditor",
    "idea_shortlist_auditor",
    "idea_reviewer",
    "novelty_checker",
    "adversarial_reviewer",
    "final_selector",
    "experiment_auditor",
    "result_judge",
    "final_paper_auditor",
    "contract_reviewer",
    "baseline_reviewer",
    "experiment_code_reviewer",
})

# Non-critical generation roles (always use LLM, never Codex)
GENERATION_ROLES = frozenset({
    "literature_scout",
    "paper_summarizer",
    "idea_generator",
    "gap_extractor",
    "idea_deduplicator",
    "log_summarizer",
})

# Role to env var name mapping
ROLE_TO_ENV_PREFIX = {
    "evidence_integrity_auditor": "LLM_EVIDENCE_AUDITOR",
    "idea_shortlist_auditor": "LLM_IDEA_SHORTLIST_AUDITOR",
    "idea_reviewer": "LLM_IDEA_REVIEWER",
    "novelty_checker": "LLM_NOVELTY_CHECKER",
    "adversarial_reviewer": "LLM_ADVERSARIAL_REVIEWER",
    "final_selector": "LLM_FINAL_SELECTOR",
    "experiment_auditor": "LLM_EXPERIMENT_AUDITOR",
    "result_judge": "LLM_RESULT_JUDGE",
    "final_paper_auditor": "LLM_FINAL_AUDITOR",
    "contract_reviewer": "LLM_CONTRACT_REVIEWER",
    "baseline_reviewer": "LLM_BASELINE_REVIEWER",
    "experiment_code_reviewer": "LLM_EXPERIMENT_CODE_REVIEWER",
    "literature_scout": "LLM_LITERATURE_SCOUT",
    "paper_summarizer": "LLM_PAPER_SUMMARIZER",
    "idea_generator": "LLM_IDEA_GENERATOR",
    "gap_extractor": "LLM_GAP_EXTRACTOR",
    "idea_deduplicator": "LLM_IDEA_DEDUPLICATOR",
    "log_summarizer": "LLM_LOG_SUMMARIZER",
}


def get_env(key: str, default: str = "") -> str:
    """Get env value; tries process env first, then .env file."""
    val = os.environ.get(key)
    if val:
        return val
    # Try loading .env manually
    try:
        root = Path(__file__).resolve().parent.parent
        env_file = root / ".env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[7:].strip()
                if "=" in line:
                    k, _, v = line.partition("=")
                    k = k.strip()
                    v = v.strip().strip("\"'")
                    if k == key:
                        return v
    except Exception:
        pass
    return default


def resolve_role(role: str) -> Dict[str, Any]:
    """Resolve routing for a given role."""
    prefix = ROLE_TO_ENV_PREFIX.get(role)
    if prefix is None:
        return {"error": f"Unknown role: {role}", "valid_roles": sorted(CRITICAL_ROLES | GENERATION_ROLES)}

    # Generation roles are never Codex
    if role in GENERATION_ROLES:
        model = get_env(f"{prefix}_MODEL", "deepseek-v4-pro")
        return {
            "role": role,
            "global_mode": "deepseek_only",
            "primary_backend": "llm-chat",
            "actual_model": model,
            "codex_used_expected": False,
            "codex_required": False,
            "fallback_allowed": False,
            "note": "generation role — always uses LLM",
        }

    # Critical gate role — check per-role override first
    role_primary = get_env(f"{prefix}_PRIMARY", "").strip().lower()
    global_mode = get_env("ARIS_CODEX_GATE_MODE", "codex_preferred").strip().lower()

    # Per-role override: if set to "codex", treat as codex_required
    if role_primary == "codex":
        effective_mode = "codex_required"
    elif role_primary in ("deepseek", "llm-chat", "api"):
        effective_mode = "deepseek_only"
    elif role_primary:
        # Custom model name — treat as deepseek_only with that model
        effective_mode = "deepseek_only"
    else:
        effective_mode = global_mode

    fallback_model = get_env("ARIS_CODEX_FALLBACK_MODEL", "deepseek-v4-pro")
    fallback_thinking = get_env("ARIS_CODEX_FALLBACK_THINKING", "enabled")
    fallback_reasoning = get_env("ARIS_CODEX_FALLBACK_REASONING_EFFORT", "max")
    fallback_model_env = get_env(f"{prefix}_FALLBACK_MODEL", "")
    if fallback_model_env:
        fallback_model = fallback_model_env

    if effective_mode == "codex_required":
        return {
            "role": role,
            "global_mode": global_mode,
            "effective_mode": "codex_required",
            "primary_backend": "codex",
            "fallback_allowed": False,
            "codex_required": True,
            "codex_used_expected": True,
            "if_codex_unavailable": "fail",
        }

    if effective_mode == "codex_preferred":
        return {
            "role": role,
            "global_mode": global_mode,
            "effective_mode": "codex_preferred",
            "primary_backend": "codex",
            "fallback_backend": "llm-chat",
            "fallback_model": fallback_model,
            "fallback_thinking": fallback_thinking,
            "fallback_reasoning": fallback_reasoning,
            "fallback_allowed": True,
            "codex_required": False,
            "codex_used_expected": True,
            "if_codex_unavailable": "fallback_with_warning",
        }

    if effective_mode == "deepseek_only":
        actual_model = role_primary if role_primary and role_primary not in ("deepseek", "llm-chat", "api") else fallback_model
        return {
            "role": role,
            "global_mode": global_mode,
            "effective_mode": "deepseek_only",
            "primary_backend": "llm-chat",
            "actual_backend": "llm-chat",
            "actual_model": actual_model,
            "codex_used_expected": False,
            "codex_required": False,
            "fallback_allowed": False,
            "selection_mode": "llm_fallback_gate",
            "warning": f"Codex disabled by ARIS_CODEX_GATE_MODE={global_mode}",
        }

    # Fallback
    return {
        "role": role,
        "global_mode": global_mode,
        "effective_mode": "codex_preferred",
        "primary_backend": "codex",
        "fallback_allowed": True,
        "codex_required": False,
        "codex_used_expected": True,
    }


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    role = sys.argv[1].strip().lower()
    result = resolve_role(role)

    if "error" in result:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
