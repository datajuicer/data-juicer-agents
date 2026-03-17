# -*- coding: utf-8 -*-
"""Pure logic for insert_text_file."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

from data_juicer_agents.utils.runtime_helpers import to_int


def insert_text_file(*, file_path: str, content: str = "", line_number: int = 1) -> Dict[str, object]:
    path = str(file_path or "").strip()
    if not path:
        return {
            "ok": False,
            "error_type": "missing_required",
            "requires": ["file_path"],
            "message": "file_path is required for insert_text_file",
        }

    target = Path(path).expanduser()
    if not target.exists():
        return {"ok": False, "error_type": "file_not_found", "message": f"file does not exist: {target}"}
    if not target.is_file():
        return {"ok": False, "error_type": "invalid_file_type", "message": f"path is not a file: {target}"}
    insert_at = to_int(line_number, 0)
    if insert_at <= 0:
        return {"ok": False, "error_type": "invalid_line_number", "message": "line_number must be >= 1"}

    try:
        lines = target.read_text(encoding="utf-8").splitlines(keepends=True)
    except Exception as exc:
        return {"ok": False, "error_type": "read_failed", "message": f"failed to read file: {exc}"}
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
        return {"ok": False, "error_type": "write_failed", "message": f"failed to write file: {exc}"}

    return {
        "ok": True,
        "action": "insert_text_file",
        "file_path": str(target),
        "line_number": insert_at,
        "message": f"inserted content at line {insert_at} in {target}",
    }
