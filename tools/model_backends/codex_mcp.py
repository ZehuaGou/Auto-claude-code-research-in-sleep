#!/usr/bin/env python3
"""Codex MCP backend adapter for trusted_role_runner.py."""

from __future__ import annotations

import importlib
import os
from typing import Any, Dict, Optional

from model_backends.base import BackendResult, make_backend_result


def _extract_thread_id_from_metadata(metadata: Dict[str, Any]) -> Optional[str]:
    if not isinstance(metadata, dict):
        return None

    direct_keys = ("codex_thread_id", "threadId", "thread_id")
    for key in direct_keys:
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    nested_keys = ("metadata", "result", "response", "session", "thread")
    for key in nested_keys:
        nested = metadata.get(key)
        if isinstance(nested, dict):
            thread_id = _extract_thread_id_from_metadata(nested)
            if thread_id:
                return thread_id
    return None


def _load_runtime_adapter():
    adapter_spec = os.environ.get("ARIS_CODEX_MCP_PYTHON_ADAPTER", "").strip()
    if not adapter_spec:
        return None, "No explicit Python Codex MCP adapter configured"

    if ":" not in adapter_spec:
        return None, "ARIS_CODEX_MCP_PYTHON_ADAPTER must use module:function format"

    module_name, func_name = adapter_spec.split(":", 1)
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:
        return None, f"Cannot import adapter module {module_name}: {exc}"

    func = getattr(module, func_name, None)
    if not callable(func):
        return None, f"Adapter callable {func_name} is missing from {module_name}"
    return func, ""


def call_codex_mcp(
    route_config: Dict[str, Any],
    prompt: str,
    *,
    test_mode: bool = False,
    mock_response: str = "",
    mock_metadata: Optional[Dict[str, Any]] = None,
) -> BackendResult:
    model = str(route_config.get("model", "") or "").strip() or "auto"

    if test_mode:
        metadata = dict(mock_metadata or {})
        thread_id = _extract_thread_id_from_metadata(metadata)
        if not thread_id:
            return make_backend_result(
                ok=False,
                actual_backend="codex",
                actual_model=model,
                error="codex_missing_thread_id",
                raw_metadata={"mock_mode": True, **metadata},
            )
        return make_backend_result(
            ok=True,
            actual_backend="codex",
            actual_model=model,
            output_text=mock_response or "[mock codex response]",
            codex_thread_id=thread_id,
            raw_metadata={"mock_mode": True, **metadata},
        )

    adapter, reason = _load_runtime_adapter()
    if adapter is None:
        return make_backend_result(
            ok=False,
            actual_backend="codex",
            actual_model=model,
            error="unsupported_runtime_backend",
            raw_metadata={
                "reason": reason,
                "note": (
                    "trusted_role_runner.py cannot call assistant-only Codex MCP tools "
                    "from a plain Python runtime without an explicit adapter."
                ),
            },
        )

    try:
        adapter_result = adapter(prompt=prompt, route_config=route_config)
    except Exception as exc:
        return make_backend_result(
            ok=False,
            actual_backend="codex",
            actual_model=model,
            error="call_failed",
            raw_metadata={"exception": str(exc)},
        )

    if not isinstance(adapter_result, dict):
        return make_backend_result(
            ok=False,
            actual_backend="codex",
            actual_model=model,
            error="unsupported_runtime_backend",
            raw_metadata={
                "reason": "adapter_returned_non_dict",
                "returned_type": type(adapter_result).__name__,
            },
        )

    metadata = dict(adapter_result.get("raw_metadata") or adapter_result.get("metadata") or {})
    thread_id = _extract_thread_id_from_metadata(metadata)
    if not thread_id:
        return make_backend_result(
            ok=False,
            actual_backend="codex",
            actual_model=str(adapter_result.get("actual_model") or model),
            error="codex_missing_thread_id",
            raw_metadata=metadata,
        )

    return make_backend_result(
        ok=True,
        actual_backend="codex",
        actual_model=str(adapter_result.get("actual_model") or model),
        output_text=str(adapter_result.get("output_text") or ""),
        codex_thread_id=thread_id,
        raw_metadata=metadata,
    )
