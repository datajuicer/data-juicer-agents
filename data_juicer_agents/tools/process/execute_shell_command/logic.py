# -*- coding: utf-8 -*-
"""Pure logic for execute_shell_command."""

from __future__ import annotations

from typing import Any, Dict

from data_juicer_agents.utils.runtime_helpers import run_interruptible_subprocess, to_int


def execute_shell_command(*, command: str, timeout: int = 120) -> Dict[str, Any]:
    cmd = str(command or "").strip()
    if not cmd:
        return {
            "ok": False,
            "error_type": "missing_required",
            "requires": ["command"],
            "message": "command is required for execute_shell_command",
        }
    timeout_sec = max(to_int(timeout, 120), 1)
    payload = run_interruptible_subprocess(cmd, timeout_sec=timeout_sec, shell=True)
    payload["action"] = "execute_shell_command"
    return payload
