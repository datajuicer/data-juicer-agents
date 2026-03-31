# -*- coding: utf-8 -*-
"""Helpers for optional dependency and install-profile messaging."""

from __future__ import annotations

from typing import Iterable, Tuple


def _normalize_extras(extras: Iterable[str]) -> Tuple[str, ...]:
    seen = set()
    ordered = []
    for item in extras:
        value = str(item or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return tuple(ordered)


def install_command_for_extras(*extras: str) -> str:
    normalized = _normalize_extras(extras)
    if not normalized:
        return "pip install data-juicer-agents"
    if len(normalized) == 1:
        return f"pip install 'data-juicer-agents[{normalized[0]}]'"
    joined = ",".join(normalized)
    return f"pip install 'data-juicer-agents[{joined}]'"


def missing_dependency_message(
    feature: str,
    *,
    extras: Iterable[str],
    missing_module: str | None = None,
) -> str:
    install_cmd = install_command_for_extras(*tuple(extras))
    message = f"{feature} requires optional dependencies that are not installed."
    if missing_module:
        message += f" Missing module: {missing_module}."
    message += f" Install them with: {install_cmd}"
    return message


__all__ = ["install_command_for_extras", "missing_dependency_message"]
