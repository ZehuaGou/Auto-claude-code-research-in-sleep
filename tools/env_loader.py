#!/usr/bin/env python3
"""
ARIS Env Loader — Unified .env reader with masked output.

Reads <project_root>/.env using git rev-parse or CWD as fallback.
Supports KEY=value, KEY="value", KEY='value', export KEY=value, simple ${VAR} expansion.
Provides mask_secret() for safe display.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional


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
    # Remove export prefix
    if line.startswith("export "):
        line = line[7:].strip()
    match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(.*)$', line)
    if not match:
        return None
    key = match.group(1)
    value = match.group(2).strip()
    # Remove quotes
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

    # Second pass: resolve variables
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
