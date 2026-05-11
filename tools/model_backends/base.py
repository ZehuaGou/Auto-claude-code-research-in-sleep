#!/usr/bin/env python3
"""Shared backend result types for trusted model execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class BackendResult:
    ok: bool
    actual_backend: str
    actual_model: str
    output_text: str
    codex_thread_id: Optional[str] = None
    error: Optional[str] = None
    raw_metadata: Dict[str, Any] = field(default_factory=dict)


def make_backend_result(
    *,
    ok: bool,
    actual_backend: str,
    actual_model: str,
    output_text: str = "",
    codex_thread_id: Optional[str] = None,
    error: Optional[str] = None,
    raw_metadata: Optional[Dict[str, Any]] = None,
) -> BackendResult:
    return BackendResult(
        ok=ok,
        actual_backend=actual_backend,
        actual_model=actual_model,
        output_text=output_text,
        codex_thread_id=codex_thread_id,
        error=error,
        raw_metadata=raw_metadata or {},
    )
