#!/usr/bin/env python3
"""Trusted backend adapters for ARIS role execution."""

from model_backends.base import BackendResult, make_backend_result
from model_backends.codex_mcp import call_codex_mcp
from model_backends.openai_compatible import call_openai_compatible

__all__ = [
    "BackendResult",
    "make_backend_result",
    "call_codex_mcp",
    "call_openai_compatible",
]
