# -*- coding: utf-8 -*-
"""Shared runtime helpers for session tools, adapters, and CLI surfaces."""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import time
from typing import Any, Dict, List


def to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def to_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def to_string_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        if raw.startswith("["):
            try:
                data = json.loads(raw)
                if isinstance(data, list):
                    return [str(item).strip() for item in data if str(item).strip()]
            except Exception:
                pass
        return [part.strip() for part in raw.split(",") if part.strip()]
    return []


def truncate_text(text: str, limit: int = 12000) -> str:
    if len(text) <= limit:
        return text
    keep = max(limit - 80, 0)
    return text[:keep] + f"\n... [truncated {len(text) - keep} chars]"


def short_log(text: str, max_lines: int = 30, max_chars: int = 6000) -> str:
    if not text:
        return ""
    lines = text.splitlines()
    tail = lines[-max_lines:]
    merged = "\n".join(tail)
    if len(merged) > max_chars:
        return merged[-max_chars:]
    return merged


def parse_line_ranges(ranges: Any) -> tuple[list[int] | None, str | None]:
    if ranges is None:
        return None, None
    if isinstance(ranges, list) and len(ranges) == 2 and all(isinstance(i, int) for i in ranges):
        return [int(ranges[0]), int(ranges[1])], None
    if isinstance(ranges, str):
        raw = ranges.strip()
        if not raw:
            return None, None
        range_match = re.match(r"^\s*(-?\d+)\s*[-,:]\s*(-?\d+)\s*$", raw)
        if range_match:
            return [int(range_match.group(1)), int(range_match.group(2))], None
        try:
            data = json.loads(raw)
        except Exception:
            return None, "ranges must be a JSON array like [start, end]"
        if isinstance(data, list) and len(data) == 2 and all(isinstance(i, int) for i in data):
            return [int(data[0]), int(data[1])], None
        return None, "ranges must be two integers [start, end]"
    return None, "ranges must be null, [start, end], or JSON string of that list"


def normalize_line_idx(idx: int, total: int) -> int:
    if idx < 0:
        return total + idx + 1
    return idx


def to_event_result_preview(value: Any, max_chars: int = 6000) -> str:
    if value is None:
        return ""
    try:
        rendered = json.dumps(value, ensure_ascii=False, indent=2, default=str)
    except Exception:
        rendered = str(value)
    return truncate_text(rendered, limit=max_chars).strip()


def to_text_response(payload: Dict[str, Any]):
    from agentscope.message import TextBlock
    from agentscope.tool import ToolResponse

    return ToolResponse(
        metadata={"ok": True},
        content=[TextBlock(type="text", text=json.dumps(payload, ensure_ascii=False))],
    )


def run_interruptible_subprocess(
    command: Any,
    *,
    timeout_sec: int,
    shell: bool,
) -> Dict[str, Any]:
    proc = subprocess.Popen(
        command,
        shell=shell,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    deadline = time.monotonic() + float(timeout_sec)
    try:
        while True:
            rc = proc.poll()
            if rc is not None:
                out, err = proc.communicate()
                return {
                    "ok": int(rc) == 0,
                    "returncode": int(rc),
                    "stdout": truncate_text(out or "", 8000),
                    "stderr": truncate_text(err or "", 8000),
                    "message": f"process finished with returncode={int(rc)}",
                }

            if time.monotonic() >= deadline:
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except Exception:
                    pass
                try:
                    proc.wait(timeout=2)
                except Exception:
                    pass
                if proc.poll() is None:
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except Exception:
                        pass
                    try:
                        proc.kill()
                    except Exception:
                        pass
                out, err = proc.communicate(timeout=2)
                return {
                    "ok": False,
                    "error_type": "timeout",
                    "returncode": -1,
                    "stdout": truncate_text(out or "", 8000),
                    "stderr": truncate_text((err or "").strip(), 8000),
                    "message": f"process timeout after {timeout_sec}s",
                }
            time.sleep(0.1)
    except Exception as exc:
        return {
            "ok": False,
            "error_type": "execution_failed",
            "returncode": -1,
            "stdout": "",
            "stderr": "",
            "message": f"process execution failed: {exc}",
        }


__all__ = [
    "normalize_line_idx",
    "parse_line_ranges",
    "run_interruptible_subprocess",
    "short_log",
    "to_bool",
    "to_event_result_preview",
    "to_int",
    "to_string_list",
    "to_text_response",
    "truncate_text",
]
