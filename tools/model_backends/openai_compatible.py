#!/usr/bin/env python3
"""OpenAI-compatible backend adapter for trusted_role_runner.py."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import httpx

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

    api_key = os.environ.get(api_key_env, "").strip() if api_key_env else ""
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
