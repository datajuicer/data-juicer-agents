# -*- coding: utf-8 -*-
"""Session file editing tools."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from .runtime import normalize_line_idx, parse_line_ranges, to_int, truncate_text


def view_text_file(*, file_path: str, ranges: Any = None) -> Dict[str, Any]:
    path = str(file_path).strip()
    if not path:
        return {
            "ok": False,
            "error_type": "missing_required",
            "requires": ["file_path"],
            "message": "file_path is required for view_text_file",
        }
    target = Path(path).expanduser()
    if not target.exists():
        return {
            "ok": False,
            "error_type": "file_not_found",
            "message": f"file does not exist: {target}",
        }
    if not target.is_file():
        return {
            "ok": False,
            "error_type": "invalid_file_type",
            "message": f"path is not a file: {target}",
        }

    parsed_ranges, err = parse_line_ranges(ranges)
    if err:
        return {
            "ok": False,
            "error_type": "invalid_ranges",
            "message": err,
        }

    try:
        lines = target.read_text(encoding="utf-8").splitlines()
    except Exception as exc:
        return {
            "ok": False,
            "error_type": "read_failed",
            "message": f"failed to read file: {exc}",
        }

    if parsed_ranges is None:
        start = 1
        end = len(lines)
    else:
        start_raw, end_raw = parsed_ranges
        start = normalize_line_idx(start_raw, len(lines))
        end = normalize_line_idx(end_raw, len(lines))
        if start < 1:
            start = 1
        if end > len(lines):
            end = len(lines)
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
        content = "\n".join(
            f"{idx + start}: {line}"
            for idx, line in enumerate(selected)
        )

    return {
        "ok": True,
        "action": "view_text_file",
        "file_path": str(target),
        "line_range": [start, end] if parsed_ranges is not None else None,
        "line_count": len(lines),
        "content": truncate_text(content),
        "message": f"loaded {target}",
    }


def write_text_file(*, file_path: str, content: str, ranges: Any = None) -> Dict[str, Any]:
    path = str(file_path).strip()
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
        return {
            "ok": False,
            "error_type": "invalid_ranges",
            "message": err,
        }

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        return {
            "ok": False,
            "error_type": "mkdir_failed",
            "message": f"failed to create parent dir: {exc}",
        }

    if parsed_ranges is None or not target.exists():
        try:
            target.write_text(payload, encoding="utf-8")
        except Exception as exc:
            return {
                "ok": False,
                "error_type": "write_failed",
                "message": f"failed to write file: {exc}",
            }
        return {
            "ok": True,
            "action": "write_text_file",
            "file_path": str(target),
            "line_range": parsed_ranges,
            "message": f"wrote file {target}",
        }

    if not target.is_file():
        return {
            "ok": False,
            "error_type": "invalid_file_type",
            "message": f"path is not a file: {target}",
        }

    start_raw, end_raw = parsed_ranges
    try:
        lines = target.read_text(encoding="utf-8").splitlines(keepends=True)
    except Exception as exc:
        return {
            "ok": False,
            "error_type": "read_failed",
            "message": f"failed to read existing file: {exc}",
        }

    start = normalize_line_idx(start_raw, len(lines))
    end = normalize_line_idx(end_raw, len(lines))
    if start < 1:
        start = 1
    if end > len(lines):
        end = len(lines)
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
        return {
            "ok": False,
            "error_type": "write_failed",
            "message": f"failed to write file: {exc}",
        }

    return {
        "ok": True,
        "action": "write_text_file",
        "file_path": str(target),
        "line_range": [start, end],
        "message": f"updated lines [{start}, {end}] in {target}",
    }


def insert_text_file(*, file_path: str, content: str, line_number: int) -> Dict[str, Any]:
    path = str(file_path).strip()
    if not path:
        return {
            "ok": False,
            "error_type": "missing_required",
            "requires": ["file_path"],
            "message": "file_path is required for insert_text_file",
        }
    target = Path(path).expanduser()
    if not target.exists():
        return {
            "ok": False,
            "error_type": "file_not_found",
            "message": f"file does not exist: {target}",
        }
    if not target.is_file():
        return {
            "ok": False,
            "error_type": "invalid_file_type",
            "message": f"path is not a file: {target}",
        }
    insert_at = to_int(line_number, 0)
    if insert_at <= 0:
        return {
            "ok": False,
            "error_type": "invalid_line_number",
            "message": "line_number must be >= 1",
        }

    try:
        lines = target.read_text(encoding="utf-8").splitlines(keepends=True)
    except Exception as exc:
        return {
            "ok": False,
            "error_type": "read_failed",
            "message": f"failed to read file: {exc}",
        }
    if insert_at > len(lines) + 1:
        return {
            "ok": False,
            "error_type": "invalid_line_number",
            "message": f"line_number {insert_at} out of range [1, {len(lines) + 1}]",
        }

    insert_text = str(content or "")
    if insert_text and not insert_text.endswith("\n"):
        insert_text = insert_text + "\n"
    new_lines = lines[: insert_at - 1] + [insert_text] + lines[insert_at - 1 :]
    try:
        target.write_text("".join(new_lines), encoding="utf-8")
    except Exception as exc:
        return {
            "ok": False,
            "error_type": "write_failed",
            "message": f"failed to write file: {exc}",
        }

    return {
        "ok": True,
        "action": "insert_text_file",
        "file_path": str(target),
        "line_number": insert_at,
        "message": f"inserted content at line {insert_at} in {target}",
    }


__all__ = ["insert_text_file", "view_text_file", "write_text_file"]
