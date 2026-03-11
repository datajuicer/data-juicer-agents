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
        r"DeprecationWarning:",
        re.IGNORECASE,
    ),
)


def install_tui_warning_filters() -> None:
    """Install warning filters for known non-actionable runtime noise."""
    warnings.filterwarnings(
        "ignore",
        category=DeprecationWarning,
    )


def sanitize_reasoning_text(text: str) -> str:
    """Pass through reasoning text without reflective-summary filtering."""
    return str(text or "").strip()


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
