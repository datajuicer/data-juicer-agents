# -*- coding: utf-8 -*-
r"""Command-flavour detection and structured stdout parsing.

Detects which command was executed (grep, find, tail, head, cat, wc, ls, ...)
and converts raw stdout into a compact, LLM-friendly structured result.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Tuple

# ---------------------------------------------------------------------------
# Flavour detection
# ---------------------------------------------------------------------------

# Well-known prefix words that wrap the real command (sudo, env, ...).
_PREFIX_WORDS = frozenset({
    "sudo", "env", "nice", "nohup", "time", "ionice", "taskset", "chroot",
    "xargs",
})
# Match a leading executable token: first char letter/digit/underscore.
_CMD_RE = re.compile(r"^(?P<cmd>[a-zA-Z0-9_][a-zA-Z0-9_.-]*)")


def detect_flavour(command: str) -> str:
    """Return a canonical flavour name for ``command`` (e.g. ``"grep"``).

    Handles plain commands (``grep ...``), absolute paths (``/usr/bin/grep ...``),
    relative paths (``./tool ...``), and well-known prefix wrappers
    (``sudo grep ...``, ``env FOO=bar grep ...``).

    For pipelines (``grep ... | wc -l``), returns the flavour of the **last**
    command, since that determines stdout format.
    """
    cmd = str(command or "").strip()
    # For pipelines, use the last segment (it determines stdout format).
    if "|" in cmd:
        segments = cmd.split("|")
        cmd = segments[-1].strip()
    tokens = cmd.split()
    # Skip prefix words (sudo, env, ...) and any KEY=VAL assignments after env.
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        bare = os.path.basename(tok)
        if bare in _PREFIX_WORDS:
            i += 1
            # `env` may be followed by KEY=VAL pairs.
            if bare == "env":
                while i < len(tokens) and "=" in tokens[i] and not tokens[i].startswith("-"):
                    i += 1
            continue
        break
    if i >= len(tokens):
        return "unknown"
    base = os.path.basename(tokens[i])
    m = _CMD_RE.match(base)
    if not m:
        return "unknown"
    return (m.group("cmd") or "").strip().lower() or "unknown"


# ---------------------------------------------------------------------------
# Result + truncation
# ---------------------------------------------------------------------------

_MAX_LINES = 50
_MAX_ITEMS = 30
_MAX_CHARS = 8000


@dataclass
class ParsedResult:
    flavour: str
    ok: bool
    returncode: int
    stdout: str
    stderr: str
    summary: str = ""
    items: List[str] = field(default_factory=list)
    count: int = 0
    truncated: bool = False


def _truncate(text: str) -> Tuple[str, bool]:
    """Cap ``text`` at ``_MAX_CHARS`` characters AND ``_MAX_LINES`` lines."""
    if len(text) > _MAX_CHARS:
        return text[:_MAX_CHARS], True
    lines = text.splitlines()
    if len(lines) > _MAX_LINES:
        return "\n".join(lines[:_MAX_LINES]), True
    return text, False


def _nonempty_lines(text: str) -> List[str]:
    return [ln for ln in text.splitlines() if ln.strip()]


def _wrap(
    flavour: str,
    stdout: str,
    stderr: str,
    *,
    summary: str,
    items: List[str],
    returncode: int = 0,
    ok: bool = True,
) -> ParsedResult:
    truncated_out, truncated = _truncate(stdout)
    return ParsedResult(
        flavour=flavour,
        ok=ok,
        returncode=returncode,
        stdout=truncated_out,
        stderr=stderr,
        summary=summary,
        items=items[:_MAX_ITEMS],
        count=len(stdout.splitlines()) if stdout else 0,
        truncated=truncated,
    )


# ---------------------------------------------------------------------------
# Per-flavour parsers
# ---------------------------------------------------------------------------


def _parse_grep(stdout: str, stderr: str, _command: str, returncode: int = 0) -> ParsedResult:
    lines = _nonempty_lines(stdout)
    total = len(stdout.splitlines()) if stdout else 0
    has_match = bool(lines)
    # Respect the real returncode: rc>=2 means an actual error (syntax, permission, …),
    # not just "no matches" (rc=1).  Only synthesize ok from content when rc∈{0,1}.
    if returncode >= 2:
        ok = False
    else:
        ok = has_match
    return _wrap(
        "grep", stdout, stderr,
        ok=ok,
        returncode=returncode,
        summary=f"grep matched {total} line(s)" if total else "grep: no matches",
        items=lines,
    )


def _parse_find(stdout: str, stderr: str, _command: str, returncode: int = 0) -> ParsedResult:
    lines = _nonempty_lines(stdout)
    total = len(lines)
    return _wrap(
        "find", stdout, stderr,
        returncode=returncode,
        ok=(returncode == 0),
        summary=f"find returned {total} file(s)" if total else "find: no files matched",
        items=lines,
    )


def _parse_listing(flavour: str, stdout: str, stderr: str, _command: str, returncode: int = 0) -> ParsedResult:
    """Generic line-oriented parser shared by tail / head / cat / ls."""
    lines = stdout.splitlines()
    total = len(lines)
    if flavour == "tail":
        items = lines[-_MAX_ITEMS:]
    elif flavour == "ls":
        items = _nonempty_lines(stdout)
    else:  # head, cat
        items = lines
    if total:
        summary = f"{flavour} returned {total} line(s)"
    else:
        summary = f"{flavour}: empty output"
    return _wrap(flavour, stdout, stderr, returncode=returncode, ok=(returncode == 0),
                 summary=summary, items=items)


def _parse_wc(stdout: str, stderr: str, _command: str, returncode: int = 0) -> ParsedResult:
    text = stdout.strip()
    return _wrap("wc", text, stderr, returncode=returncode, ok=(returncode == 0),
                 summary=f"wc: {text}", items=[text] if text else [])


def _parse_generic(stdout: str, stderr: str, returncode: int, command: str) -> ParsedResult:
    return _wrap(
        detect_flavour(command), stdout, stderr,
        returncode=returncode,
        ok=(returncode == 0),
        summary=f"command exited with code {returncode}",
        items=_nonempty_lines(stdout),
    )


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_PARSERS: Dict[str, Callable[[str, str, str, int], ParsedResult]] = {
    "grep": _parse_grep,
    "egrep": _parse_grep,
    "rg": _parse_grep,
    "find": _parse_find,
    "fd": _parse_find,
    "tail": lambda o, e, c, rc: _parse_listing("tail", o, e, c, rc),
    "head": lambda o, e, c, rc: _parse_listing("head", o, e, c, rc),
    "cat": lambda o, e, c, rc: _parse_listing("cat", o, e, c, rc),
    "ls": lambda o, e, c, rc: _parse_listing("ls", o, e, c, rc),
    "wc": _parse_wc,
}


def parse_output(*, command: str, returncode: int, stdout: str, stderr: str) -> ParsedResult:
    parser = _PARSERS.get(detect_flavour(command))
    if parser is not None:
        return parser(stdout, stderr, command, returncode)
    return _parse_generic(stdout, stderr, returncode, command)
