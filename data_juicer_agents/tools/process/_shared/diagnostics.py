# -*- coding: utf-8 -*-
"""Error diagnosis for shell command failures.

Maps exit codes / stderr patterns / empty-stdout heuristics to a
``(diagnosis, suggestion)`` pair that the agent can use to self-correct.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

# stderr → (diagnosis, suggestion). Checked first as the most specific signal.
_STDERR_PATTERNS = [
    (re.compile(r"Permission denied", re.I),
     "permission denied", "try a different directory or add sudo"),
    (re.compile(r"No such file or directory", re.I),
     "file or directory not found", "verify the path; try ls <dir>"),
    (re.compile(r"command not found", re.I),
     "command not found in PATH", "install the tool or use an alternative"),
    (re.compile(r"cannot (?:open|access|stat)", re.I),
     "cannot access file", "verify the file exists and is readable"),
    (re.compile(r"Is a directory", re.I),
     "target is a directory but expected a file", "use -r flag (grep) or specify a file"),
    (re.compile(r"not a directory", re.I),
     "target is a file but expected a directory", "remove the trailing filename from the path"),
    (re.compile(r"Argument list too long", re.I),
     "too many arguments (glob expanded)", "use find ... -exec or xargs"),
    (re.compile(r"Disk quota exceeded", re.I),
     "disk full", "free up space or write to a different volume"),
    (re.compile(r"Read-only file system", re.I),
     "read-only filesystem", "write to a different location"),
    (re.compile(r"invalid option.*--", re.I),
     "unsupported command flag", "check flag spelling with command --help"),
]

# Flavour-specific hints when stdout is empty and rc∈{0,1}.
_EMPTY_STDOUT_HINTS = {
    "grep": ("grep found no matches", "broaden the pattern, remove flags like -w, or search elsewhere"),
    "find": ("find returned no files", "widen the search directory, remove -name filter, or check the path"),
    "tail": ("tail returned no lines (empty file?)", "check the file is not empty; try cat <file>"),
    "head": ("head returned no lines (empty file?)", "check the file is not empty; try wc -l <file>"),
    "cat": ("cat returned no output (empty file?)", "verify the file exists and is not empty; try ls -la <file>"),
    "ls": ("ls returned nothing (empty directory?)", "the directory may be empty; check with ls -la"),
}


def _diagnose_by_exit_code(flavour: str, returncode: int, stderr: str) -> Tuple[str, str]:
    rc = int(returncode or 0)
    err = str(stderr or "")
    if rc == 0:
        return ("command succeeded but no output", "check whether the command is correct")
    if rc == 1:
        # Only emit the grep-specific hint when the command actually is grep;
        # other commands also use rc=1 for generic errors and would be misdiagnosed.
        if flavour == "grep" or "grep" in err.lower():
            return (
                "grep returned no matches (exit 1)",
                "broaden pattern, remove -w flag, or search a different path",
            )
        return ("command exited with code 1", "check the command arguments and target path")
    if rc == 2:
        if "No such file" in err:
            return ("file not found", "verify the file path exists; try ls <dir> first")
        if "Permission denied" in err:
            return ("permission denied", "try a different directory or add sudo")
        if "invalid option" in err.lower():
            return ("invalid command option", "check the flag spelling; run command --help")
        return ("command or file error (exit 2)", "verify the path and command syntax")
    if rc == 124:
        return ("command timed out", "reduce scope (narrow path, add -maxdepth, use head/tail limits)")
    if rc == 127:
        return (
            "command not found",
            "the tool is not installed; try an alternative like fd instead of find, rg instead of grep",
        )
    if rc == 130:
        return ("command was interrupted (SIGINT)", "command may have hung; try with a shorter scope")
    if rc == 137:
        return (
            "command killed (SIGKILL, likely OOM)",
            "reduce memory usage: use head, limit file sizes, or add -m flag to grep",
        )
    if rc > 128:
        return (f"command terminated by signal {rc - 128}", "retry with a timeout or smaller scope")
    return (f"command exited with code {rc}", "check stderr for details")


def _diagnose_by_stderr(stderr: str) -> Optional[Tuple[str, str]]:
    if not stderr:
        return None
    for pattern, diagnosis, suggestion in _STDERR_PATTERNS:
        if pattern.search(stderr):
            return (diagnosis, suggestion)
    return None


def diagnose(*, flavour: str, returncode: int, stdout: str, stderr: str) -> Tuple[str, str]:
    """Return ``(diagnosis, suggestion)``. Order: stderr → exit code → empty-stdout hint."""
    stderr_diag = _diagnose_by_stderr(stderr)
    if stderr_diag:
        return stderr_diag

    diag, sugg = _diagnose_by_exit_code(flavour, returncode, stderr)

    # For benign exit codes (0/1) without stdout, try a more specific flavour hint.
    if returncode in (0, 1) and not (stdout or "").strip():
        empty_diag = _EMPTY_STDOUT_HINTS.get(flavour)
        if empty_diag:
            return empty_diag

    return diag, sugg
