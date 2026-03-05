# -*- coding: utf-8 -*-
"""Shared output-level controls for djx commands."""

from __future__ import annotations

import json
from typing import Any

OUTPUT_LEVELS = ("quiet", "verbose", "debug")
_RANK = {"quiet": 0, "verbose": 1, "debug": 2}


def output_level(args: Any) -> str:
    level = str(getattr(args, "output_level", "quiet") or "quiet").strip().lower()
    if level not in _RANK:
        return "quiet"
    return level


def enabled(args: Any, level: str) -> bool:
    current = output_level(args)
    target = str(level or "quiet").strip().lower()
    if target not in _RANK:
        target = "quiet"
    return _RANK[current] >= _RANK[target]


def emit(args: Any, message: str, *, level: str = "quiet") -> None:
    if enabled(args, level):
        print(message)


def emit_json(
    args: Any,
    payload: Any,
    *,
    level: str = "debug",
    ensure_ascii: bool = False,
    indent: int = 2,
) -> None:
    if enabled(args, level):
        print(json.dumps(payload, ensure_ascii=ensure_ascii, indent=indent))

