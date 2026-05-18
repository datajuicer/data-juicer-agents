# -*- coding: utf-8 -*-
r"""Command-type detection and structured result parsing.

Detects the command flavour (grep, find, tail, head, cat, wc, ls, etc.)
from the raw shell command line and parses stdout/stderr into structured
result dicts that an LLM can consume efficiently.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Command flavour detection
# ---------------------------------------------------------------------------

# Matches the *first executable name* in a command line, stripping sudo/...
_COMMAND_RE = re.compile(
    r"^(?:(?:sudo|env|nice|nohup|time|ionice|taskset|chroot)\s+)?"
    r"(?P<cmd>[a-zA-Z0-9_][a-zA-Z0-9_.-]*)",
)


def detect_flavour(command: str) -> str:
    """Return a canonical flavour name for *command* (e.g. ``grep``)."""
    m = _COMMAND_RE.search(str(command or "").strip())
    if not m:
        return "unknown"
    cmd = m.group("cmd") or m.group(0)
    return cmd.strip().lower()


# ---------------------------------------------------------------------------
# Structured result
# ---------------------------------------------------------------------------


@dataclass
class ParsedResult:
    flavour: str
    ok: bool
    returncode: int
    stdout: str
    stderr: str
    # Structured summary
    summary: str = ""
    items: List[str] = field(default_factory=list)
    count: int = 0
    truncated: bool = False
    truncated_at: int = 0
    error_diagnosis: str = ""
    fix_suggestion: str = ""


# ---------------------------------------------------------------------------
# Output truncation
# ---------------------------------------------------------------------------

_MAX_LINES = 50
_MAX_CHARS = 8000


def _truncate(text: str, max_lines: int = _MAX_LINES) -> tuple[str, bool, int]:
    lines = text.splitlines()
    total = len(lines)
    if total <= max_lines:
        return text, False, total
    kept = "\n".join(lines[:max_lines])
    return kept, True, total


def _count_lines(text: str) -> int:
    if not text.strip():
        return 0
    return len(text.splitlines())


# ---------------------------------------------------------------------------
# Per-flavour parsers
# ---------------------------------------------------------------------------


def _parse_grep(stdout: str, stderr: str, _command: str) -> ParsedResult:
    lines = [l for l in stdout.splitlines() if l.strip()]
    count = _count_lines(stdout)
    truncated_out, is_trunc, total = _truncate(stdout)
    return ParsedResult(
        flavour="grep",
        ok=len(lines) > 0,
        returncode=0 if lines else 1,
        stdout=truncated_out,
        stderr=stderr,
        summary=f"grep matched {total} line(s)" if total else "grep: no matches",
        items=lines[:30],
        count=total,
        truncated=is_trunc,
        truncated_at=_MAX_LINES,
    )


def _parse_find(stdout: str, stderr: str, _command: str) -> ParsedResult:
    lines = [l for l in stdout.splitlines() if l.strip()]
    count = len(lines)
    truncated_out, is_trunc, total = _truncate(stdout)
    return ParsedResult(
        flavour="find",
        ok=True,
        returncode=0,
        stdout=truncated_out,
        stderr=stderr,
        summary=f"find returned {total} file(s)" if total else "find: no files matched",
        items=lines[:30],
        count=total,
        truncated=is_trunc,
        truncated_at=_MAX_LINES,
    )


def _parse_tail(stdout: str, stderr: str, _command: str) -> ParsedResult:
    count = _count_lines(stdout)
    return ParsedResult(
        flavour="tail",
        ok=True,
        returncode=0,
        stdout=stdout if len(stdout) <= _MAX_CHARS else stdout[:_MAX_CHARS],
        stderr=stderr,
        summary=f"tail returned {count} line(s)",
        items=stdout.splitlines()[-30:],
        count=count,
        truncated=len(stdout) > _MAX_CHARS,
        truncated_at=_MAX_CHARS,
    )


def _parse_head(stdout: str, stderr: str, _command: str) -> ParsedResult:
    count = _count_lines(stdout)
    return ParsedResult(
        flavour="head",
        ok=True,
        returncode=0,
        stdout=stdout if len(stdout) <= _MAX_CHARS else stdout[:_MAX_CHARS],
        stderr=stderr,
        summary=f"head returned {count} line(s)",
        items=stdout.splitlines()[:30],
        count=count,
        truncated=len(stdout) > _MAX_CHARS,
        truncated_at=_MAX_CHARS,
    )


def _parse_cat(stdout: str, stderr: str, _command: str) -> ParsedResult:
    count = _count_lines(stdout)
    truncated_out, is_trunc, _ = _truncate(stdout, max_lines=200)
    return ParsedResult(
        flavour="cat",
        ok=True,
        returncode=0,
        stdout=truncated_out if len(truncated_out) <= _MAX_CHARS else truncated_out[:_MAX_CHARS],
        stderr=stderr,
        summary=f"cat returned {count} line(s)" + (" [truncated]" if is_trunc else ""),
        items=stdout.splitlines()[:200],
        count=count,
        truncated=is_trunc or len(stdout) > _MAX_CHARS,
        truncated_at=max(_MAX_LINES, 200),
    )


def _parse_wc(stdout: str, stderr: str, _command: str) -> ParsedResult:
    return ParsedResult(
        flavour="wc",
        ok=True,
        returncode=0,
        stdout=stdout.strip(),
        stderr=stderr,
        summary=f"wc: {stdout.strip()}",
        count=0,
    )


def _parse_ls(stdout: str, stderr: str, _command: str) -> ParsedResult:
    lines = [l for l in stdout.splitlines() if l.strip()]
    count = len(lines)
    truncated_out, is_trunc, _ = _truncate(stdout)
    return ParsedResult(
        flavour="ls",
        ok=True,
        returncode=0,
        stdout=truncated_out,
        stderr=stderr,
        summary=f"ls listed {count} entries" + (" [truncated]" if is_trunc else ""),
        items=lines[:50],
        count=count,
        truncated=is_trunc,
        truncated_at=_MAX_LINES,
    )


def _parse_generic(stdout: str, stderr: str, returncode: int, command: str) -> ParsedResult:
    truncated_out, is_trunc, _ = _truncate(stdout)
    return ParsedResult(
        flavour=detect_flavour(command),
        ok=returncode == 0,
        returncode=returncode,
        stdout=truncated_out if len(truncated_out) <= _MAX_CHARS else truncated_out[:_MAX_CHARS],
        stderr=stderr if len(stderr) <= _MAX_CHARS else stderr[:_MAX_CHARS],
        summary=f"command exited with code {returncode}",
        truncated=is_trunc or len(stdout) > _MAX_CHARS,
        truncated_at=_MAX_LINES,
    )


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_PARSERS: Dict[str, Any] = {
    "grep": _parse_grep,
    "egrep": _parse_grep,
    "rg": _parse_grep,  # ripgrep
    "find": _parse_find,
    "fd": _parse_find,  # fd-find
    "tail": _parse_tail,
    "head": _parse_head,
    "cat": _parse_cat,
    "wc": _parse_wc,
    "ls": _parse_ls,
}


def parse_output(*, command: str, returncode: int, stdout: str, stderr: str) -> ParsedResult:
    flavour = detect_flavour(command)
    parser = _PARSERS.get(flavour)
    if parser:
        return parser(stdout, stderr, command)
    return _parse_generic(stdout, stderr, returncode, command)
