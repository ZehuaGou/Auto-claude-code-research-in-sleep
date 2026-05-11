#!/usr/bin/env python3
"""
ARIS Model Route Resolver — Resolve backend/model for a given role.

Uses tools/env_loader.py for config. Supports both new ROLE_/MODEL_ system
and legacy LLM_* vars for backward compatibility.

Usage:
    python tools/model_route.py final_selector
    python tools/model_route.py novelty_checker
    python tools/model_route.py idea_reviewer
    python tools/model_route.py --help

Output JSON fields:
    role, model_alias, provider, backend_type, model,
    thinking, reasoning_effort, requires_api_key, api_key_env,
    base_url, mcp_server, fallback_used, fallback_reason, config_error

Exit code: 0 on success, 1 on unknown role or config error.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

TOOLS_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(TOOLS_DIR))

from env_loader import load_env, resolve_role_config, mask_secret

# All known roles
ALL_ROLES = frozenset({
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
    "literature_scout",
    "paper_summarizer",
    "idea_generator",
    "gap_extractor",
    "idea_deduplicator",
    "experiment_implementer",
    "paper_writer",
    "claims_drafter",
    "log_summarizer",
    "paper_claim_auditor",
})

# Codex-priority critical roles
CRITICAL_CODEX_ROLES = frozenset({
    "idea_reviewer",
    "novelty_checker",
    "adversarial_reviewer",
    "final_selector",
    "experiment_code_reviewer",
    "experiment_auditor",
    "result_judge",
    "final_paper_auditor",
    "contract_reviewer",
    "evidence_integrity_auditor",
    "idea_shortlist_auditor",
    "paper_claim_auditor",
})


def resolve_role(role: str) -> Dict[str, Any]:
    """Resolve routing for a given role using env_loader.

    ARIS_CODEX_GATE_MODE values (from .env):
      - codex_required: Require Codex; fail if unavailable (for critical judgment gates)
      - codex_preferred: Try Codex first; fallback to API with warning (default)
      - deepseek_only: Skip Codex entirely; use API directly (for generation tasks)
    """
    env_info = load_env()
    vars_dict = env_info.get("vars", {})

    config = resolve_role_config(role, vars_dict)

    # Enhance with Codex-specific logic
    provider = config.get("provider", "")
    backend_type = config.get("backend_type", "")

    # If Codex, annotate that runner must call MCP
    if backend_type == "mcp":
        config["codex_required_roles_note"] = (
            f"Role '{role}' resolves to Codex MCP. "
            "The outer Agent must call mcp__codex__codex directly. "
            "isolated_job_runner cannot invoke Codex MCP itself."
        )

    # Include mode strings for verify compatibility
    config["gate_modes"] = ["codex_required", "codex_preferred", "deepseek_only"]

    if config.get("config_error"):
        return config

    return config


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    role = sys.argv[1].strip().lower()
    result = resolve_role(role)

    if "config_error" in result and not result.get("model") and not result.get("provider"):
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()