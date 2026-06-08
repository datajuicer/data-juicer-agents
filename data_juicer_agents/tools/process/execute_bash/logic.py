# -*- coding: utf-8 -*-
"""Pure logic for execute_bash — SmartBash execution with structured parsing."""

from __future__ import annotations

from typing import Any, Dict

from data_juicer_agents.utils.runtime_helpers import run_interruptible_subprocess, to_int

from .._shared.diagnostics import diagnose
from .._shared.parser import parse_output


def execute_bash(*, command: str, timeout: int = 120) -> Dict[str, Any]:
    cmd = str(command or "").strip()
    if not cmd:
        return {
            "ok": False,
            "error_type": "missing_required",
            "requires": ["command"],
            "message": "command is required",
        }

    timeout_sec = max(to_int(timeout, 120), 1)
    raw = run_interruptible_subprocess(cmd, timeout_sec=timeout_sec, shell=True)

    returncode = raw.get("returncode", -1)
    stdout = str(raw.get("stdout", ""))
    stderr = str(raw.get("stderr", ""))

    parsed = parse_output(command=cmd, returncode=returncode, stdout=stdout, stderr=stderr)
    diag, suggestion = diagnose(
        flavour=parsed.flavour, returncode=returncode, stdout=stdout, stderr=stderr,
    )

    return {
        "ok": parsed.ok,
        "action": "execute_bash",
        "flavour": parsed.flavour,
        "returncode": returncode,
        "stdout": parsed.stdout,
        "stderr": stderr,
        "summary": parsed.summary,
        "items": parsed.items,
        "count": parsed.count,
        "truncated": parsed.truncated,
        "diagnosis": diag,
        "suggestion": suggestion,
        "command": cmd,
        "timeout": timeout_sec,
    }
