#!/usr/bin/env python3
"""
ARIS Config Check — Check .env MODEL_/ROLE_ configuration.

Reads: .env (via env_loader)
Outputs: config/status.json, config/CONFIG_CHECK.md

Checks:
  - All ROLE_* variables resolve correctly
  - API backends have corresponding API Key
  - Codex backend checks CODEX_ENABLED and Codex MCP status
  - Legacy LLM_* vars are NOT required (optional fallbacks)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

TOOLS_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(TOOLS_DIR))

from env_loader import find_project_root, load_env, mask_secret, resolve_role_config, list_role_configs


def is_real_value(value: str) -> bool:
    """Check if a value is a real config value, not a placeholder."""
    if not value:
        return False
    stripped = value.strip().lower()
    placeholders = ["your-", "your_", "example", "changeme", "todo", "xxx",
                    "placeholder", "replace-me", "replace_me"]
    return not any(p in stripped for p in placeholders)


def check_codex_status() -> Dict[str, Any]:
    """Check if Codex CLI and MCP are available."""
    result: Dict[str, Any] = {"cli_available": False, "mcp_status": "unknown",
                               "codex_enabled": False, "default_model": "auto"}

    env_info = load_env()
    vars_dict = env_info.get("vars", {})
    result["codex_enabled"] = vars_dict.get("CODEX_ENABLED", "").lower() == "true"
    result["default_model"] = vars_dict.get("CODEX_DEFAULT_MODEL", "auto")

    # Check CLI
    codex_path = shutil.which("codex")
    if codex_path:
        result["cli_available"] = True
    else:
        for p in [os.path.expanduser("~/.local/bin/codex"),
                  "/usr/local/bin/codex", "/opt/homebrew/bin/codex"]:
            if os.path.isfile(p):
                result["cli_available"] = True
                break

    # Check MCP in settings
    settings = Path(os.path.expanduser("~/.claude/settings.json"))
    for cfg in [settings, Path(os.path.expanduser("~/.claude/settings.local.json"))]:
        if cfg.exists():
            try:
                data = json.loads(cfg.read_text(encoding="utf-8", errors="ignore"))
                servers = data.get("mcpServers", {})
                if "codex" in servers or any("codex" in k for k in servers):
                    result["mcp_status"] = "available"
                    break
            except Exception:
                continue

    return result


def main():
    root = find_project_root()
    env_info = load_env()
    vars_dict = env_info.get("vars", {})

    warnings: List[str] = []
    errors: List[str] = []
    role_reports: List[Dict[str, Any]] = []

    # Resolve all roles
    all_configs = list_role_configs(vars_dict)

    for role, config in all_configs.items():
        alias = config.get("model_alias", "")
        provider = config.get("provider", "")
        backend_type = config.get("backend_type", "")
        model = config.get("model", "")
        thinking = config.get("thinking", "")
        effort = config.get("reasoning_effort", "")
        requires_key = config.get("requires_api_key", False)
        key_env = config.get("api_key_env", "")
        base_url = config.get("base_url", "")
        mcp_server = config.get("mcp_server", "")
        fallback_used = config.get("fallback_used", False)
        config_error = config.get("config_error", "")

        status = "ok"
        status_detail = ""
        missing_key = False

        if config_error and not model:
            status = "error"
            status_detail = config_error
        elif backend_type == "mcp":
            codex_check = check_codex_status()
            if not codex_check["codex_enabled"]:
                status = "warn"
                status_detail = "CODEX_ENABLED=false"
            elif not codex_check["mcp_status"] == "available":
                status = "warn"
                status_detail = "Codex MCP not detected in settings"
        elif backend_type == "openai_compatible_api" and requires_key:
            if key_env:
                key_val = vars_dict.get(key_env, "")
                if not is_real_value(key_val):
                    status = "error"
                    status_detail = f"{key_env} missing or placeholder"
                    missing_key = True
                    errors.append(f"ROLE_{role.upper()}=ROLE_{role.upper()} but {key_env} is not set")
            if not base_url:
                status = "warn"
                status_detail = f"{provider.upper()}_BASE_URL not set"

        role_reports.append({
            "role": role,
            "alias": alias,
            "provider": provider,
            "backend_type": backend_type,
            "model": model,
            "thinking": thinking,
            "effort": effort,
            "mcp_server": mcp_server,
            "base_url": base_url,
            "status": status,
            "detail": status_detail,
            "fallback_used": fallback_used,
        })

    # Codex overall status
    codex_check = check_codex_status()

    # Build status dict
    status_output = {
        "env_path": env_info["env_path"],
        "env_exists": env_info["exists"],
        "codex": codex_check,
        "role_configs": role_reports,
        "errors": errors,
        "warnings": warnings,
        "checked_at": datetime.now().isoformat(),
    }

    # Write status.json
    config_dir = root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "status.json").write_text(
        json.dumps(status_output, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    # Generate CONFIG_CHECK.md
    lines = ["# ARIS Configuration Check Report\n",
             f"检查时间: {status_output['checked_at']}\n"]

    # Codex section
    lines.append("## Codex MCP Status\n")
    lines.append(f"- CODEX_ENABLED: {'✅ true' if codex_check['codex_enabled'] else '❌ false (Codex roles will use API fallback)'}")
    lines.append(f"- CODEX_DEFAULT_MODEL: `{codex_check['default_model']}`")
    lines.append(f"- CLI 可用: {'✅' if codex_check['cli_available'] else '❌'}")
    lines.append(f"- MCP 状态: {'✅ available' if codex_check['mcp_status'] == 'available' else '❓ ' + codex_check['mcp_status']}")

    # Role table
    lines.append("\n## Role Configuration Status\n")
    lines.append("| Role | Alias | Provider | Backend | Model | Effort | Status |\n")
    lines.append("|------|-------|----------|---------|-------|--------|--------|\n")
    for r in role_reports:
        status_icon = {"ok": "✅", "warn": "⚠️", "error": "❌"}.get(r["status"], "?")
        effort_str = r["effort"] or r["thinking"] or "-"
        lines.append(f"| {r['role']} | {r['alias'] or '-'} | {r['provider'] or '-'} | "
                     f"{r['backend_type'] or '-'} | {r['model'] or '-'} | {effort_str} | "
                     f"{status_icon} {r['detail']} |\n")

    # Errors
    lines.append("\n## Errors\n")
    if errors:
        for e in errors:
            lines.append(f"- ❌ {e}\n")
    else:
        lines.append("- ✅ 无配置错误\n")

    lines.append("\n---\n")
    lines.append("**注意**: 本工具只检查配置，不会自动修改 `.env`。\n")

    report = "".join(lines)
    (config_dir / "CONFIG_CHECK.md").write_text(report, encoding="utf-8")

    print(json.dumps(status_output, ensure_ascii=False, indent=2))
    print(f"\nReport written to: {config_dir / 'CONFIG_CHECK.md'}", file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)
    main()