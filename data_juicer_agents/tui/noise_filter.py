# -*- coding: utf-8 -*-
"""TUI-specific stderr/warning noise suppression."""

from __future__ import annotations

import contextlib
import io
import re
import sys
import warnings
from typing import Iterable


_NOISE_PATTERNS = (
    re.compile(r"Importing operator modules took .* seconds"),
    re.compile(
        r"^<unknown>:\d+:\s+DeprecationWarning:\s+invalid escape sequence",
        re.IGNORECASE,
    ),
)
_REFLECTIVE_REASONING_LINE_MARKERS = (
    re.compile(r"(?i)^\s*[·•\-\*]?\s*the user (requested|asked)\b"),
    re.compile(r"(?i)^\s*[·•\-\*]?\s*the task has been (successfully )?(completed|finished)\b"),
    re.compile(r"(?i)^\s*[·•\-\*]?\s*i (have )?(successfully )?(completed|finished)\b"),
    re.compile(r"(?i)^\s*[·•\-\*]?\s*here'?s (a )?summary\b"),
    re.compile(r"^\s*[·•\-\*]?\s*用户(要求|请求|希望)"),
    re.compile(r"^\s*[·•\-\*]?\s*任务(已)?完成"),
)
_SUMMARY_HINTS = (
    re.compile(r"(?i)\bsummary\b"),
    re.compile(r"(?i)\bsuccessfully completed\b"),
    re.compile(r"(?m)^\s*\d+\.\s+"),
    re.compile(r"已完成操作"),
    re.compile(r"任务成功完成"),
)


def install_tui_warning_filters() -> None:
    """Install warning filters for known non-actionable runtime noise."""
    warnings.filterwarnings(
        "ignore",
        message=r"invalid escape sequence.*",
        category=DeprecationWarning,
    )


def sanitize_reasoning_text(text: str) -> str:
    """Drop reflective/meta reasoning recaps from TUI timeline."""
    body = str(text or "").strip()
    if not body:
        return ""

    lines = body.splitlines()
    first_nonempty = ""
    for line in lines:
        stripped = line.strip()
        if stripped:
            first_nonempty = stripped
            break

    starts_reflective = bool(
        first_nonempty
        and any(pattern.match(first_nonempty) for pattern in _REFLECTIVE_REASONING_LINE_MARKERS)
    )
    has_summary_hint = any(pattern.search(body) for pattern in _SUMMARY_HINTS)
    if starts_reflective and has_summary_hint:
        return ""

    kept_lines = []
    leading = True
    for line in lines:
        stripped = line.strip()
        if leading and stripped and any(pattern.match(stripped) for pattern in _REFLECTIVE_REASONING_LINE_MARKERS):
            continue
        if stripped:
            leading = False
        kept_lines.append(line)
    return "\n".join(kept_lines).strip()


class FilteredStderr(io.TextIOBase):
    """Stream wrapper that drops known noise lines and forwards others."""

    def __init__(
        self,
        target,
        patterns: Iterable[re.Pattern[str]] | None = None,
    ) -> None:
        self._target = target
        self._patterns = tuple(patterns or _NOISE_PATTERNS)
        self._buffer = ""
        self.suppressed_lines = 0

    @staticmethod
    def _normalize_line(line: str) -> str:
        return str(line or "").strip()

    def _is_noise(self, line: str) -> bool:
        text = self._normalize_line(line)
        if not text:
            return False
        for pattern in self._patterns:
            if pattern.search(text):
                return True
        return False

    def _emit_line(self, line: str) -> None:
        if self._is_noise(line):
            self.suppressed_lines += 1
            return
        self._target.write(line)

    def write(self, data: str) -> int:  # type: ignore[override]
        text = str(data or "")
        if not text:
            return 0
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            self._emit_line(line + "\n")
        return len(text)

    def flush(self) -> None:  # type: ignore[override]
        if self._buffer:
            self._emit_line(self._buffer)
            self._buffer = ""
        if hasattr(self._target, "flush"):
            self._target.flush()

    def isatty(self) -> bool:  # pragma: no cover - passthrough
        if hasattr(self._target, "isatty"):
            return bool(self._target.isatty())
        return False

    def fileno(self) -> int:  # pragma: no cover - passthrough
        if hasattr(self._target, "fileno"):
            return int(self._target.fileno())
        raise OSError("fileno unavailable")

    @property
    def encoding(self) -> str:  # pragma: no cover - passthrough
        return getattr(self._target, "encoding", "utf-8")


@contextlib.contextmanager
def suppress_tui_noise_stderr():
    """Context manager to suppress known third-party stderr noise in TUI."""
    filtered = FilteredStderr(sys.stderr)
    with contextlib.redirect_stderr(filtered):
        try:
            yield filtered
        finally:
            filtered.flush()
