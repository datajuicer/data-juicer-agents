# -*- coding: utf-8 -*-
"""Session command execution tools."""

from __future__ import annotations

import sys
from typing import Any, Dict

from .runtime import SessionToolRuntime, run_interruptible_subprocess, to_int


def execute_shell_command(
    runtime: SessionToolRuntime,
    *,
    command: str,
    timeout: int = 120,
) -> Dict[str, Any]:
    cmd = str(command or "").strip()
    if not cmd:
        return {
            "ok": False,
            "error_type": "missing_required",
            "requires": ["command"],
            "message": "command is required for execute_shell_command",
        }
    timeout_sec = max(to_int(timeout, 120), 1)
    payload = run_interruptible_subprocess(
        cmd,
        timeout_sec=timeout_sec,
        shell=True,
    )
    payload["action"] = "execute_shell_command"
    return payload


def execute_python_code(
    runtime: SessionToolRuntime,
    *,
    code: str,
    timeout: int = 120,
) -> Dict[str, Any]:
    snippet = str(code or "")
    if not snippet.strip():
        return {
            "ok": False,
            "error_type": "missing_required",
            "requires": ["code"],
            "message": "code is required for execute_python_code",
        }
    timeout_sec = max(to_int(timeout, 120), 1)
    payload = run_interruptible_subprocess(
        [sys.executable, "-c", snippet],
        timeout_sec=timeout_sec,
        shell=False,
    )
    payload["action"] = "execute_python_code"
    return payload


__all__ = ["execute_python_code", "execute_shell_command"]
