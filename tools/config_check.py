#!/usr/bin/env python3
"""
ARIS Config Check — Check .env, LLM Chat, Codex, Feishu configuration.

Reads: .env (via env_loader), .env.example, mcp-servers/llm-chat/server.py
Outputs: config/status.json, config/CONFIG_CHECK.md
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Union

# Add tools dir to path
TOOLS_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(TOOLS_DIR))

from env_loader import find_project_root, load_env, mask_secret

REQUIRED_VARS = [
    "LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL", "LLM_FALLBACK_MODEL",
]

OPTIONAL_VARS = [
    "LLM_THINKING", "LLM_REASONING_EFFORT", "LLM_MAX_TOKENS",
]

ROLE_VARS = [
    "LLM_IDEA_REVIEWER_PRIMARY", "LLM_NOVELTY_CHECKER_PRIMARY",
    "LLM_CONTRACT_REVIEWER_PRIMARY", "LLM_RESULT_JUDGE_PRIMARY",
    "LLM_FINAL_AUDITOR_PRIMARY",
]

ROLE_FALLBACK_VARS = [
    "LLM_IDEA_REVIEWER_FALLBACK_MODEL", "LLM_NOVELTY_CHECKER_FALLBACK_MODEL",
    "LLM_CONTRACT_REVIEWER_FALLBACK_MODEL", "LLM_RESULT_JUDGE_FALLBACK_MODEL",
    "LLM_FINAL_AUDITOR_FALLBACK_MODEL",
]


def is_real_value(value: str) -> bool:
    """Check if a value is a real configuration value, not a placeholder.

    Returns False for empty strings and common placeholder patterns
    (your-, example, changeme, todo, xxx), True for actual values.
    """
    if not value:
        return False
    stripped = value.strip().lower()
    placeholder_patterns = [
        "your-", "your_",
        "example", "changeme", "todo", "xxx",
        "placeholder", "replace-me", "replace_me",
    ]
    for pattern in placeholder_patterns:
        if pattern in stripped:
            return False
    return True


def check_codex() -> Dict[str, Any]:
    """Check if Codex CLI and MCP are available."""
    result: Dict[str, Any] = {"cli_available": False, "mcp_status": "unknown"}

    # Check CLI
    codex_path = shutil.which("codex")
    if codex_path:
        result["cli_available"] = True
    else:
        # Also check common install paths
        for p in [
            os.path.expanduser("~/.local/bin/codex"),
            "/usr/local/bin/codex",
            "/opt/homebrew/bin/codex"
        ]:
            if os.path.isfile(p):
                result["cli_available"] = True
                break

    # Check MCP — we can detect from .mcp.json or settings.json
    root = find_project_root()
    mcp_json = root / ".mcp.json"
    settings = Path(os.path.expanduser("~/.claude/settings.json"))

    for cfg in [mcp_json, settings]:
        if cfg.exists():
            try:
                data = json.loads(cfg.read_text(encoding="utf-8", errors="ignore"))
                servers = data.get("mcpServers", {})
                if "codex" in servers or any("codex" in k for k in servers):
                    result["mcp_status"] = "available"
                    break
            except Exception:
                continue

    if result["mcp_status"] == "unknown":
        # Check .claude/settings.local.json too
        settings_local = Path(os.path.expanduser("~/.claude/settings.local.json"))
        if settings_local.exists():
            try:
                data = json.loads(settings_local.read_text(encoding="utf-8", errors="ignore"))
                servers = data.get("mcpServers", {})
                if "codex" in servers or any("codex" in k for k in servers):
                    result["mcp_status"] = "available"
            except Exception:
                pass

    return result


def check_feishu(env_vars: Dict[str, str]) -> Dict[str, Any]:
    """Check Feishu configuration (supports both Bridge and Webhook modes).

    Uses is_real_value() to distinguish placeholder values from real config.
    """
    feishu_app_id = env_vars.get("FEISHU_APP_ID", "")
    feishu_app_secret = env_vars.get("FEISHU_APP_SECRET", "")
    feishu_user_id = env_vars.get("FEISHU_USER_ID", "")
    feishu_webhook = env_vars.get("FEISHU_WEBHOOK", "")
    feishu_secret = env_vars.get("FEISHU_SECRET", "")

    bridge = {
        "app_id_present": is_real_value(feishu_app_id),
        "app_secret_present": is_real_value(feishu_app_secret),
        "user_id_present": is_real_value(feishu_user_id),
        "receive_id_type": env_vars.get("FEISHU_RECEIVE_ID_TYPE", "missing"),
        "configured": (
            is_real_value(feishu_app_id)
            and is_real_value(feishu_app_secret)
            and is_real_value(feishu_user_id)
        ),
    }
    webhook = {
        "webhook_present": is_real_value(feishu_webhook),
        "secret_present": is_real_value(feishu_secret),
        "configured": is_real_value(feishu_webhook),
    }
    return {"bridge": bridge, "webhook": webhook}


def check_server_py(root: Path) -> List[str]:
    """Check llm-chat server.py for compatibility."""
    warnings = []
    server_path = root / "mcp-servers" / "llm-chat" / "server.py"
    if not server_path.exists():
        warnings.append("mcp-servers/llm-chat/server.py not found")
        return warnings

    content = server_path.read_text(encoding="utf-8", errors="ignore")
    if "LLM_THINKING" not in content:
        warnings.append("server.py does not support LLM_THINKING env var (needs patch)")
    if "reasoning_effort" not in content:
        warnings.append("server.py does not support reasoning_effort (needs patch)")
    if "max_tokens" not in content:
        warnings.append("server.py does not support max_tokens override (needs patch)")
    return warnings


def check_required_role_vars(env_vars: Dict[str, str]) -> Dict[str, str]:
    """Check which role variables are present and their status."""
    result = {}
    for var in ROLE_VARS:
        val = env_vars.get(var, "")
        if val:
            if val == "codex":
                result[var] = "codex"
            else:
                result[var] = f"present ({val})"
        else:
            result[var] = "missing"
    return result


def main():
    root = find_project_root()
    env_info = load_env()
    env_vars = env_info.get("vars", {})

    warnings: List[str] = []
    missing: List[str] = []

    # Check required vars
    for var in REQUIRED_VARS:
        if not env_vars.get(var):
            missing.append(var)

    # Check optional vars
    for var in OPTIONAL_VARS:
        if not env_vars.get(var):
            warnings.append(f"Optional var {var} not set (will use defaults)")

    # Check role fallback vars
    for var in ROLE_FALLBACK_VARS:
        if not env_vars.get(var):
            warnings.append(f"Role fallback var {var} not set (will use LLM_FALLBACK_MODEL)")

    # Check server.py
    server_warnings = check_server_py(root)
    warnings.extend(server_warnings)

    # Check Codex
    codex_status = check_codex()

    # Check Feishu
    feishu_status = check_feishu(env_vars)

    # Check role vars
    role_vars_status = check_required_role_vars(env_vars)

    status = {
        "env": {
            "exists": env_info["exists"],
            "path": env_info["env_path"],
            "llm_api_key": mask_secret("LLM_API_KEY", env_vars.get("LLM_API_KEY", "")),
            "llm_base_url": env_vars.get("LLM_BASE_URL", "missing"),
            "llm_model": env_vars.get("LLM_MODEL", "missing"),
            "llm_fallback_model": env_vars.get("LLM_FALLBACK_MODEL", "missing"),
            "thinking": env_vars.get("LLM_THINKING", "not set"),
            "reasoning_effort": env_vars.get("LLM_REASONING_EFFORT", "not set"),
        },
        "codex": codex_status,
        "feishu": feishu_status,
        "role_vars": role_vars_status,
        "warnings": warnings,
        "missing": missing,
        "checked_at": datetime.now().isoformat(),
    }

    # Write config/status.json
    config_dir = root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "status.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    # Generate CONFIG_CHECK.md
    lines = []
    lines.append("# ARIS Configuration Check Report\n")
    lines.append(f"检查时间: {status['checked_at']}\n")

    lines.append("## DeepSeek LLM Chat Configuration\n")
    if env_info["exists"]:
        masked_key = mask_secret("LLM_API_KEY", env_vars.get("LLM_API_KEY", ""))
        lines.append(f"- `.env` 状态: 存在")
        lines.append(f"- LLM_API_KEY: {masked_key}")
        lines.append(f"- LLM_BASE_URL: {env_vars.get('LLM_BASE_URL', '❌ missing')}")
        lines.append(f"- LLM_MODEL: {env_vars.get('LLM_MODEL', '❌ missing')}")
        lines.append(f"- LLM_FALLBACK_MODEL: {env_vars.get('LLM_FALLBACK_MODEL', '❌ missing')}")
        lines.append(f"- LLM_THINKING: {env_vars.get('LLM_THINKING', 'not set')}")
        lines.append(f"- LLM_REASONING_EFFORT: {env_vars.get('LLM_REASONING_EFFORT', 'not set')}")
    else:
        lines.append("- ❌ `.env` 不存在。请复制 `.env.example` 为 `.env` 并填入 API Key。")

    lines.append("\n## Codex Status\n")
    lines.append(f"- CLI 可用: {'✅' if codex_status['cli_available'] else '❌'}")
    lines.append(f"- MCP 状态: {'✅' if codex_status['mcp_status'] == 'available' else '❓ ' + codex_status['mcp_status']}")
    if not codex_status['cli_available'] and codex_status['mcp_status'] != 'available':
        lines.append("- ⚠️ Codex 不可用。关键审查将 fallback 到 LLM。")

    feishu_bridge = feishu_status.get("bridge", {})
    feishu_webhook = feishu_status.get("webhook", {})
    lines.append("\n## Feishu Status\n")
    lines.append("### Bridge Mode\n")
    lines.append(f"- FEISHU_APP_ID: {'✅' if feishu_bridge.get('app_id_present') else '❌ not configured'}")
    lines.append(f"- FEISHU_APP_SECRET: {'✅' if feishu_bridge.get('app_secret_present') else '❌ not configured'}")
    lines.append(f"- FEISHU_USER_ID: {'✅' if feishu_bridge.get('user_id_present') else '❌ not configured'}")
    lines.append(f"- FEISHU_RECEIVE_ID_TYPE: {feishu_bridge.get('receive_id_type', 'missing')}")
    lines.append(f"- Bridge Configured: {'✅' if feishu_bridge.get('configured') else '❌ not configured'}")
    lines.append("")
    lines.append("### Webhook Mode\n")
    lines.append(f"- FEISHU_WEBHOOK: {'✅' if feishu_webhook.get('webhook_present') else '❌ not configured'}")
    lines.append(f"- FEISHU_SECRET: {'✅' if feishu_webhook.get('secret_present') else '❌ not configured'}")
    lines.append(f"- Webhook Configured: {'✅' if feishu_webhook.get('configured') else '❌ not configured'}")
    if not feishu_bridge.get('configured') and not feishu_webhook.get('configured'):
        lines.append("- ⚠️ Feishu 未配置。通知将无法发送。")

    lines.append("\n## Missing Variables\n")
    if missing:
        for var in missing:
            lines.append(f"- ❌ {var} 缺失，请手动添加到 `.env`")
    else:
        lines.append("- ✅ 所有必需变量已配置")

    lines.append("\n## Warnings\n")
    if warnings:
        for w in warnings:
            lines.append(f"- ⚠️ {w}")
    else:
        lines.append("- ✅ 无警告")
    lines.append("\n---\n")
    lines.append("**注意**: 本工具只检查配置，不会自动修改 `.env`。请手动添加缺失变量。\n")

    report = "\n".join(lines)
    (config_dir / "CONFIG_CHECK.md").write_text(report, encoding="utf-8")

    print(json.dumps(status, ensure_ascii=False, indent=2))
    print(f"\nReport written to: {config_dir / 'CONFIG_CHECK.md'}", file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)
    main()
