#!/usr/bin/env python3
"""
ARIS Env Loader — Unified .env reader with masked output and role-based routing.

Reads <project_root>/.env using git rev-parse or CWD as fallback.
Supports KEY=value, KEY="value", KEY='value', export KEY=value, simple ${VAR} expansion.
Provides mask_secret() for safe display.

New ROLE_/MODEL_ routing system:
  - MODEL_<ALIAS>=provider:model  (e.g. MODEL_DS_PRO=deepseek:deepseek-v4-pro)
  - MODEL_<ALIAS>_THINKING=enabled|disabled
  - MODEL_<ALIAS>_EFFORT=low|medium|high|max
  - ROLE_<ROLE>=<ALIAS>          (e.g. ROLE_IDEA_REVIEWER=CODEX)
  - CODEX_ENABLED=true|false
  - CODEX_MCP_SERVER=codex
  - CODEX_DEFAULT_MODEL=auto|gpt-5.5|...

provider=codex  → backend_type=mcp, requires_api_key=false, mcp_server=CODEX_MCP_SERVER
provider=deepseek|kimi|minimax|openai → backend_type=openai_compatible_api,
                  requires_api_key=true, api_key_env=<PROVIDER>_API_KEY,
                  base_url=<PROVIDER>_BASE_URL
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional


def find_project_root() -> Path:
    """Locate project root: git root first, then CWD."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5,
            cwd=os.getcwd()
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
    except Exception:
        pass
    return Path(os.getcwd()).resolve()


def parse_env_line(line: str) -> Optional[tuple[str, str]]:
    """Parse a single .env line. Returns (key, value) or None."""
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    if line.startswith("export "):
        line = line[7:].strip()
    match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(.*)$', line)
    if not match:
        return None
    key = match.group(1)
    value = match.group(2).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        value = value[1:-1]
    return key, value


def resolve_variable(value: str, variables: Dict[str, str]) -> str:
    """Resolve ${VAR} references in value."""
    def replacer(m: re.Match) -> str:
        var_name = m.group(1) or m.group(2)
        return variables.get(var_name, m.group(0))
    return re.sub(r'\$\{([^}]+)\}|\$([a-zA-Z_][a-zA-Z0-9_]*)', replacer, value)


def load_env(env_path: Optional[str] = None) -> dict:
    """Load .env file and return structured result."""
    root = find_project_root() if env_path is None else Path(env_path).parent
    if env_path:
        env_file = Path(env_path)
    else:
        env_file = root / ".env"

    result: Dict[str, str] = {}
    if not env_file.exists():
        return {
            "env_path": str(env_file),
            "exists": False,
            "vars": {},
            "masked": {}
        }

    raw_lines = env_file.read_text(encoding="utf-8", errors="ignore").splitlines()
    variables: Dict[str, str] = {}
    for line in raw_lines:
        parsed = parse_env_line(line)
        if parsed:
            key, value = parsed
            variables[key] = value

    for key, value in variables.items():
        result[key] = resolve_variable(value, variables)

    return {
        "env_path": str(env_file),
        "exists": True,
        "vars": result,
        "masked": {k: mask_secret(k, v) for k, v in result.items()}
    }


def mask_secret(key: str, value: str) -> str:
    """Mask sensitive values for display."""
    if not value:
        return "missing"
    if len(value) <= 6:
        return "****"
    sensitive_keys = {"api_key", "secret", "token", "password", "key"}
    key_lower = key.lower()
    if any(sk in key_lower for sk in sensitive_keys):
        if len(value) <= 10:
            return value[:2] + "****" + value[-2:]
        return value[:4] + "****" + value[-4:]
    return value


# ---------------------------------------------------------------------------
# New ROLE_/MODEL_ routing system
# ---------------------------------------------------------------------------

def normalize_env(vars: Dict[str, str]) -> Dict[str, str]:
    """Normalize env vars: resolve ${VAR} references within the dict itself.

    This ensures MODEL_DS_FLASH=deepseek:${MODEL_NAME} resolves correctly
    when MODEL_NAME is also in vars.
    """
    result: Dict[str, str] = {}
    resolved: Dict[str, str] = {}

    # First pass: collect all raw values
    for key, value in vars.items():
        result[key] = value

    # Second pass: resolve variable references
    for key, value in vars.items():
        resolved[key] = resolve_variable(value, vars)

    result.update(resolved)
    return result


def _parse_model_alias(alias_value: str, vars: Dict[str, str]) -> Dict[str, Any]:
    """Parse a MODEL_<ALIAS> value into provider and model.

    Example: "deepseek:deepseek-v4-pro" -> provider=deepseek, model=deepseek-v4-pro
             "codex:auto"               -> provider=codex, model=auto
    """
    if ":" in alias_value:
        provider, model = alias_value.split(":", 1)
        provider = provider.strip().lower()
        model = model.strip()
    else:
        # Bare model name — treat as deepseek
        provider = "deepseek"
        model = alias_value.strip()

    # Resolve any remaining ${VAR} references
    model = resolve_variable(model, vars)

    return {"provider": provider, "model": model}


def resolve_model_alias(alias: str, vars: Dict[str, str]) -> Dict[str, Any]:
    """Resolve a model alias to full backend configuration.

    Returns:
        {
            "alias": str,
            "provider": str,         # deepseek | kimi | minimax | openai | codex
            "model": str,            # resolved model string
            "backend_type": str,     # openai_compatible_api | mcp
            "requires_api_key": bool,
            "api_key_env": str,      # e.g. "DEEPSEEK_API_KEY"
            "base_url": str,         # e.g. "https://api.deepseek.com"
            "mcp_server": str,      # e.g. "codex" (only for mcp backend)
            "thinking": str,         # enabled | disabled | ""
            "reasoning_effort": str,# low | medium | high | max | xhigh | ""
            "config_error": str,     # "" if ok, else error message
        }
    """
    alias_upper = alias.upper()
    key = f"MODEL_{alias_upper}"
    alias_value = vars.get(key, "")

    if not alias_value:
        return {
            "alias": alias,
            "provider": "",
            "model": "",
            "backend_type": "",
            "requires_api_key": False,
            "api_key_env": "",
            "base_url": "",
            "mcp_server": "",
            "thinking": "",
            "reasoning_effort": "",
            "config_error": f"MODEL_{alias_upper} not defined",
        }

    # Split on FIRST colon only — provider:model:extra is valid (e.g. openai:gpt-4:freeze)
    parts = alias_value.split(":", 1)
    if len(parts) == 2:
        provider, model = parts[0].strip().lower(), parts[1].strip()
    else:
        provider = "deepseek"
        model = alias_value.strip()

    # Resolve any ${VAR} references in model
    model = resolve_variable(model, vars)

    # Validate resolved model is not still a bare ${VAR} reference
    if model.startswith("${") and model.endswith("}"):
        return {
            "alias": alias,
            "provider": provider,
            "model": model,
            "backend_type": "",
            "requires_api_key": False,
            "api_key_env": "",
            "base_url": "",
            "mcp_server": "",
            "thinking": "",
            "reasoning_effort": "",
            "config_error": f"MODEL_{alias_upper}={alias_value} references undefined variable {model}",
        }

    # Provider-specific config
    if provider == "codex":
        base_url = ""
        api_key_env = ""
        requires_api_key = False
        backend_type = "mcp"
        mcp_server = vars.get("CODEX_MCP_SERVER", "codex")
    elif provider in ("deepseek", "kimi", "minimax", "openai"):
        base_url_key = f"{provider.upper()}_BASE_URL"
        api_key_env = f"{provider.upper()}_API_KEY"
        base_url = vars.get(base_url_key, "")
        requires_api_key = True
        backend_type = "openai_compatible_api"
        mcp_server = ""
    else:
        return {
            "alias": alias,
            "provider": provider,
            "model": model,
            "backend_type": "",
            "requires_api_key": False,
            "api_key_env": "",
            "base_url": "",
            "mcp_server": "",
            "thinking": "",
            "reasoning_effort": "",
            "config_error": f"Unknown provider: {provider}",
        }

    # Model params
    thinking = vars.get(f"MODEL_{alias_upper}_THINKING", "")
    reasoning_effort = vars.get(f"MODEL_{alias_upper}_EFFORT", "")

    return {
        "alias": alias,
        "provider": provider,
        "model": model,
        "backend_type": backend_type,
        "requires_api_key": requires_api_key,
        "api_key_env": api_key_env,
        "base_url": base_url,
        "mcp_server": mcp_server,
        "thinking": thinking,
        "reasoning_effort": reasoning_effort,
        "config_error": "",
    }


def resolve_role_config(role: str, vars: Dict[str, str]) -> Dict[str, Any]:
    """Resolve a role to its full model configuration.

    Uses new ROLE_<ROLE>=<ALIAS> system, falls back to old LLM_* vars.

    Returns:
        {
            "role": str,
            "model_alias": str,
            "provider": str,
            "backend_type": str,
            "model": str,
            "thinking": str,
            "reasoning_effort": str,
            "requires_api_key": bool,
            "api_key_env": str,
            "base_url": str,
            "mcp_server": str,
            "fallback_used": bool,
            "fallback_reason": str,
            "config_error": str,
        }
    """
    role_upper = role.upper()
    role_key = f"ROLE_{role_upper}"
    alias = vars.get(role_key, "")

    fallback_used = False
    fallback_reason = ""

    if alias:
        alias_config = resolve_model_alias(alias, vars)
        if alias_config.get("config_error"):
            # Alias defined but has error — try fallback
            fallback_used = True
            fallback_reason = alias_config["config_error"]
        else:
            return {
                "role": role,
                "model_alias": alias,
                **alias_config,
                "fallback_used": False,
                "fallback_reason": "",
            }

    # Fallback to old LLM_* vars
    legacy = _resolve_legacy_role(role, vars)
    if legacy:
        legacy["fallback_used"] = True
        legacy["fallback_reason"] = fallback_reason or "new ROLE_/MODEL_ system not fully configured; using legacy LLM_* vars"
        return legacy

    # Total failure
    return {
        "role": role,
        "model_alias": alias or "",
        "provider": "",
        "backend_type": "",
        "model": "",
        "thinking": "",
        "reasoning_effort": "",
        "requires_api_key": False,
        "api_key_env": "",
        "base_url": "",
        "mcp_server": "",
        "fallback_used": True,
        "fallback_reason": fallback_reason or f"ROLE_{role_upper} not configured and no legacy LLM_* vars found",
        "config_error": f"ROLE_{role_upper} not configured",
    }


def _resolve_legacy_role(role: str, vars: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """Try to resolve a role using old LLM_* variable names.

    Maps old LLM_IDEA_REVIEWER_PRIMARY=codex -> backend_type=mcp
    Maps old LLM_IDEA_REVIEWER_MODEL=deepseek-v4-pro -> backend_type=openai_compatible_api
    """
    prefix_map = {
        "literature_scout": "LLM_LITERATURE_SCOUT",
        "paper_summarizer": "LLM_PAPER_SUMMARIZER",
        "gap_extractor": "LLM_GAP_EXTRACTOR",
        "idea_generator": "LLM_IDEA_GENERATOR",
        "idea_deduplicator": "LLM_IDEA_DEDUPLICATOR",
        "idea_reviewer": "LLM_IDEA_REVIEWER",
        "novelty_checker": "LLM_NOVELTY_CHECKER",
        "adversarial_reviewer": "LLM_ADVERSARIAL_REVIEWER",
        "final_selector": "LLM_FINAL_SELECTOR",
        "contract_reviewer": "LLM_CONTRACT_REVIEWER",
        "experiment_implementer": "LLM_EXPERIMENT_IMPLEMENTER",
        "experiment_code_reviewer": "LLM_EXPERIMENT_CODE_REVIEWER",
        "experiment_auditor": "LLM_EXPERIMENT_AUDITOR",
        "result_judge": "LLM_RESULT_JUDGE",
        "paper_writer": "LLM_PAPER_WRITER",
        "claims_drafter": "LLM_CLAIMS_DRAFTER",
        "final_auditor": "LLM_FINAL_AUDITOR",
        "log_summarizer": "LLM_LOG_SUMMARIZER",
        "baseline_reviewer": "LLM_BASELINE_REVIEWER",
        "evidence_integrity_auditor": "LLM_EVIDENCE_AUDITOR",
        "idea_shortlist_auditor": "LLM_IDEA_SHORTLIST_AUDITOR",
        "paper_claim_auditor": "LLM_PAPER_CLAIM_AUDITOR",
    }

    prefix = prefix_map.get(role)
    if not prefix:
        return None

    primary = vars.get(f"{prefix}_PRIMARY", "").strip().lower()
    model = vars.get(f"{prefix}_MODEL", "").strip()
    thinking = vars.get(f"{prefix}_THINKING", vars.get("LLM_THINKING", "")).strip()
    effort = vars.get(f"{prefix}_REASONING_EFFORT", vars.get("LLM_REASONING_EFFORT", "")).strip()

    if primary == "codex":
        return {
            "role": role,
            "model_alias": "CODEX",
            "provider": "codex",
            "backend_type": "mcp",
            "model": vars.get("CODEX_DEFAULT_MODEL", "auto"),
            "thinking": vars.get("MODEL_CODEX_EFFORT", ""),
            "reasoning_effort": vars.get("MODEL_CODEX_EFFORT", ""),
            "requires_api_key": False,
            "api_key_env": "",
            "base_url": "",
            "mcp_server": vars.get("CODEX_MCP_SERVER", "codex"),
            "config_error": "",
        }

    if model or vars.get("LLM_MODEL"):
        actual_model = model or vars.get("LLM_MODEL", "")
        return {
            "role": role,
            "model_alias": "",
            "provider": "deepseek",  # default legacy provider
            "backend_type": "openai_compatible_api",
            "model": actual_model,
            "thinking": thinking,
            "reasoning_effort": effort,
            "requires_api_key": bool(vars.get("LLM_API_KEY", "")),
            "api_key_env": "LLM_API_KEY",
            "base_url": vars.get("LLM_BASE_URL", "https://api.deepseek.com"),
            "mcp_server": "",
            "config_error": "",
        }

    return None


def list_role_configs(vars: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
    """Return configs for all known roles."""
    roles = [
        "literature_scout", "paper_summarizer", "gap_extractor",
        "idea_generator", "idea_deduplicator",
        "idea_reviewer", "novelty_checker", "adversarial_reviewer",
        "final_selector", "contract_reviewer",
        "experiment_implementer", "experiment_code_reviewer", "experiment_auditor",
        "result_judge",
        "paper_writer", "claims_drafter", "final_auditor",
        "log_summarizer", "baseline_reviewer",
    ]
    return {role: resolve_role_config(role, vars) for role in roles}


def main():
    """CLI entry point."""
    args = sys.argv[1:]
    if args and args[0] == "mask":
        key = args[1] if len(args) > 1 else "key"
        val = args[2] if len(args) > 2 else ""
        print(mask_secret(key, val))
        return

    if args and args[0] == "path":
        print(str(find_project_root()))
        return

    result = load_env()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)
    main()