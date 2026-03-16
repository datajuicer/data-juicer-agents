# -*- coding: utf-8 -*-
"""Pure logic for execute_python_code."""

from __future__ import annotations

import sys
from typing import Any, Dict

from data_juicer_agents.utils.runtime_helpers import run_interruptible_subprocess, to_int


def execute_python_code(*, code: str, timeout: int = 120) -> Dict[str, Any]:
    snippet = str(code or "")
    if not snippet.strip():
        return {
            "ok": False,
            "error_type": "missing_required",
            "requires": ["code"],
            "message": "code is required for execute_python_code",
        }
    timeout_sec = max(to_int(timeout, 120), 1)
    payload = run_interruptible_subprocess([sys.executable, "-c", snippet], timeout_sec=timeout_sec, shell=False)
    payload["action"] = "execute_python_code"
    return payload
