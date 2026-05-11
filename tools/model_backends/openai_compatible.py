#!/usr/bin/env python3
"""OpenAI-compatible backend adapter for trusted_role_runner.py."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from env_loader import load_env
from model_backends.base import BackendResult, make_backend_result


def _build_endpoint(base_url: str) -> str:
    url = base_url.rstrip("/")
    if not url:
        return ""
    if url.endswith("/chat/completions"):
        return url
    if url.endswith("/v1"):
        return f"{url}/chat/completions"
    return f"{url}/v1/chat/completions"


def resolve_api_key(api_key_env: str, env_vars: Optional[Dict[str, Any]] = None) -> str:
    key_name = str(api_key_env or "").strip()
    if not key_name:
        return ""
    vars_dict = env_vars
    if vars_dict is None:
        env_info = load_env()
        vars_dict = env_info.get("vars", {}) if isinstance(env_info, dict) else {}
    api_key = str(vars_dict.get(key_name, "") or "").strip()
    if api_key:
        return api_key
    return os.environ.get(key_name, "").strip()


def call_openai_compatible(
    route_config: Dict[str, Any],
    prompt: str,
    *,
    test_mode: bool = False,
    mock_response: str = "",
    mock_metadata: Optional[Dict[str, Any]] = None,
) -> BackendResult:
    provider = str(route_config.get("provider", "") or "").strip()
    model = str(route_config.get("model", "") or "").strip()
    base_url = str(route_config.get("base_url", "") or "").strip()
    api_key_env = str(route_config.get("api_key_env", "") or "").strip()
    thinking = str(route_config.get("thinking", "") or "").strip()
    reasoning_effort = str(route_config.get("reasoning_effort", "") or "").strip()

    if test_mode:
        return make_backend_result(
            ok=True,
            actual_backend=provider or "mock_api",
            actual_model=model or "mock-model",
            output_text=mock_response or "[mock openai-compatible response]",
            raw_metadata={
                "mock_mode": True,
                **(mock_metadata or {}),
            },
        )

    env_info = load_env()
    env_vars = env_info.get("vars", {}) if isinstance(env_info, dict) else {}
    api_key = resolve_api_key(api_key_env, env_vars=env_vars)
    if not provider or not model or not base_url or not api_key_env or not api_key:
        return make_backend_result(
            ok=False,
            actual_backend=provider,
            actual_model=model,
            error="config_missing",
            raw_metadata={
                "provider": provider,
                "model": model,
                "base_url_present": bool(base_url),
                "api_key_env": api_key_env,
                "api_key_present": bool(api_key),
            },
        )

    payload: Dict[str, Any] = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are the internal ARIS trusted role backend. "
                    "Follow the provided role task exactly."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 4096,
    }
    if thinking and thinking != "disabled":
        payload["thinking"] = {"type": thinking}
    if reasoning_effort:
        payload["reasoning_effort"] = reasoning_effort

    endpoint = _build_endpoint(base_url)
    try:
        with httpx.Client(timeout=300.0) as client:
            response = client.post(
                endpoint,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                json=payload,
            )
        if response.status_code != 200:
            return make_backend_result(
                ok=False,
                actual_backend=provider,
                actual_model=model,
                error="api_call_failed",
                raw_metadata={
                    "status_code": response.status_code,
                    "response_excerpt": response.text[:500],
                },
            )
        data = response.json()
        output_text = str(
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        return make_backend_result(
            ok=True,
            actual_backend=provider,
            actual_model=model,
            output_text=output_text,
            raw_metadata=data if isinstance(data, dict) else {"response_type": type(data).__name__},
        )
    except Exception as exc:
        return make_backend_result(
            ok=False,
            actual_backend=provider,
            actual_model=model,
            error="api_call_failed",
            raw_metadata={"exception": str(exc)},
        )


def cmd_self_test() -> bool:
    env_info = load_env()
    env_vars = env_info.get("vars", {}) if isinstance(env_info, dict) else {}

    results = []

    llm_visible = bool(resolve_api_key("LLM_API_KEY", env_vars=env_vars))
    results.append({
        "case": "LLM_API_KEY via env_loader vars",
        "api_key_present": llm_visible,
    })

    minimax_visible = bool(resolve_api_key("MINIMAX_API_KEY", env_vars=env_vars))
    results.append({
        "case": "MINIMAX_API_KEY via env_loader vars",
        "api_key_present": minimax_visible,
    })

    missing_result = call_openai_compatible(
        {
            "provider": "deepseek",
            "model": "deepseek-v4-flash",
            "base_url": "https://api.deepseek.com",
            "api_key_env": "",
        },
        "self-test",
    )
    results.append({
        "case": "missing api_key_env",
        "error": missing_result.error,
        "api_key_present": bool(missing_result.raw_metadata.get("api_key_present", False)),
    })

    assert results[0]["api_key_present"] is True, "Expected LLM_API_KEY to be visible via env_loader vars"
    assert missing_result.error == "config_missing", "Expected missing api_key_env to return config_missing"

    print(json.dumps(results, ensure_ascii=False, indent=2))
    print("All self-tests passed!")
    return True


def main() -> None:
    args = sys.argv[1:]
    if "--self-test" in args:
        sys.exit(0 if cmd_self_test() else 1)
    print(__doc__)


if __name__ == "__main__":
    main()
