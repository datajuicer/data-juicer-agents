# -*- coding: utf-8 -*-
"""Pure logic for write_text_file."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from data_juicer_agents.utils.runtime_helpers import normalize_line_idx, parse_line_ranges


def write_text_file(*, file_path: str, content: str = "", ranges: Any = None) -> Dict[str, Any]:
    path = str(file_path or "").strip()
    if not path:
        return {
            "ok": False,
            "error_type": "missing_required",
            "requires": ["file_path"],
            "message": "file_path is required for write_text_file",
        }

    target = Path(path).expanduser()
    payload = str(content or "")
    parsed_ranges, err = parse_line_ranges(ranges)
    if err:
        return {"ok": False, "error_type": "invalid_ranges", "message": err}

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        return {"ok": False, "error_type": "mkdir_failed", "message": f"failed to create parent dir: {exc}"}

    if parsed_ranges is None or not target.exists():
        try:
            target.write_text(payload, encoding="utf-8")
        except Exception as exc:
            return {"ok": False, "error_type": "write_failed", "message": f"failed to write file: {exc}"}
        return {
            "ok": True,
            "action": "write_text_file",
            "file_path": str(target),
            "line_range": parsed_ranges,
            "message": f"wrote file {target}",
        }

    if not target.is_file():
        return {"ok": False, "error_type": "invalid_file_type", "message": f"path is not a file: {target}"}

    start_raw, end_raw = parsed_ranges
    try:
        lines = target.read_text(encoding="utf-8").splitlines(keepends=True)
    except Exception as exc:
        return {"ok": False, "error_type": "read_failed", "message": f"failed to read existing file: {exc}"}

    start = max(normalize_line_idx(start_raw, len(lines)), 1)
    end = min(normalize_line_idx(end_raw, len(lines)), len(lines))
    if len(lines) > 0 and (start > end or start > len(lines)):
        return {
            "ok": False,
            "error_type": "invalid_ranges",
            "message": f"invalid line range after normalization: [{start}, {end}]",
        }

    replacement = payload
    if replacement and not replacement.endswith("\n"):
        replacement = replacement + "\n"
    new_lines = lines[: max(start - 1, 0)] + [replacement] + lines[end:]

    try:
        target.write_text("".join(new_lines), encoding="utf-8")
    except Exception as exc:
        return {"ok": False, "error_type": "write_failed", "message": f"failed to write file: {exc}"}

    return {
        "ok": True,
        "action": "write_text_file",
        "file_path": str(target),
        "line_range": [start, end],
        "message": f"updated lines [{start}, {end}] in {target}",
    }
