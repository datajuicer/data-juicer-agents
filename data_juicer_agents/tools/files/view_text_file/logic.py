# -*- coding: utf-8 -*-
"""Pure logic for view_text_file."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from data_juicer_agents.utils.runtime_helpers import normalize_line_idx, parse_line_ranges, truncate_text


def view_text_file(*, file_path: str, ranges: Any = None) -> Dict[str, Any]:
    path = str(file_path or "").strip()
    if not path:
        return {
            "ok": False,
            "error_type": "missing_required",
            "requires": ["file_path"],
            "message": "file_path is required for view_text_file",
        }

    target = Path(path).expanduser()
    if not target.exists():
        return {"ok": False, "error_type": "file_not_found", "message": f"file does not exist: {target}"}
    if not target.is_file():
        return {"ok": False, "error_type": "invalid_file_type", "message": f"path is not a file: {target}"}

    parsed_ranges, err = parse_line_ranges(ranges)
    if err:
        return {"ok": False, "error_type": "invalid_ranges", "message": err}

    try:
        lines = target.read_text(encoding="utf-8").splitlines()
    except Exception as exc:
        return {"ok": False, "error_type": "read_failed", "message": f"failed to read file: {exc}"}

    if parsed_ranges is None:
        start = 1
        end = len(lines)
    else:
        start_raw, end_raw = parsed_ranges
        start = max(normalize_line_idx(start_raw, len(lines)), 1)
        end = min(normalize_line_idx(end_raw, len(lines)), len(lines))
        if len(lines) == 0:
            start, end = 1, 0
        if start > end and len(lines) > 0:
            return {
                "ok": False,
                "error_type": "invalid_ranges",
                "message": f"invalid line range after normalization: [{start}, {end}]",
            }

    if len(lines) == 0 or end <= 0:
        content = ""
    else:
        selected = lines[start - 1 : end]
        content = "\n".join(f"{idx + start}: {line}" for idx, line in enumerate(selected))

    return {
        "ok": True,
        "action": "view_text_file",
        "file_path": str(target),
        "line_range": [start, end] if parsed_ranges is not None else None,
        "line_count": len(lines),
        "content": truncate_text(content),
        "message": f"loaded {target}",
    }
