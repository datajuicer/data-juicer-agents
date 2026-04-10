# -*- coding: utf-8 -*-
"""Scan custom operator paths and extract operator metadata via AST.

Used by PlanOrchestrator to inject custom operators into the retrieval
candidate list so the LLM planner can select them.
"""

from __future__ import annotations

import ast
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List

logger = logging.getLogger(__name__)


def _extract_register_name(decorator: ast.expr) -> str | None:
    """Extract the operator name from @OPERATORS.register_module("name")."""
    if not isinstance(decorator, ast.Call):
        return None
    func = decorator.func
    if not isinstance(func, ast.Attribute):
        return None
    if func.attr != "register_module":
        return None
    if decorator.args and isinstance(decorator.args[0], ast.Constant):
        return str(decorator.args[0].value)
    return None


def _extract_docstring(node: ast.ClassDef) -> str:
    """Extract the docstring from a class definition."""
    return ast.get_docstring(node) or ""


def _extract_init_params(node: ast.ClassDef) -> List[str]:
    """Extract __init__ parameter names (excluding self, *args, **kwargs)."""
    for item in node.body:
        if isinstance(item, ast.FunctionDef) and item.name == "__init__":
            params = []
            for arg in item.args.args:
                if arg.arg not in ("self",):
                    params.append(arg.arg)
            return params
    return []


def _scan_file(filepath: Path) -> List[Dict[str, Any]]:
    """Parse a single .py file and return metadata for registered operators."""
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, UnicodeDecodeError, OSError) as exc:
        logger.debug("Skipping %s: %s", filepath, exc)
        return []

    results = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for decorator in node.decorator_list:
            op_name = _extract_register_name(decorator)
            if op_name:
                docstring = _extract_docstring(node)
                init_params = _extract_init_params(node)
                results.append({
                    "operator_name": op_name,
                    "class_name": node.name,
                    "description": docstring,
                    "arguments_preview": init_params[:6],
                    "source_file": str(filepath),
                })
    return results


def scan_custom_operators(
    custom_operator_paths: Iterable[Any] | None,
) -> List[Dict[str, Any]]:
    """Scan custom operator paths and return candidate-format metadata.

    Args:
        custom_operator_paths: Directories or .py files containing custom
            operators registered via @OPERATORS.register_module.

    Returns:
        List of candidate dicts compatible with the retrieval payload format.
    """
    if not custom_operator_paths:
        return []

    raw_entries: List[Dict[str, Any]] = []
    seen_names: set = set()

    for raw_path in custom_operator_paths:
        path = Path(str(raw_path).strip()).expanduser().resolve()
        if not path.exists():
            logger.debug("Custom operator path does not exist: %s", path)
            continue

        py_files: List[Path] = []
        if path.is_file() and path.suffix == ".py":
            py_files.append(path)
        elif path.is_dir():
            py_files.extend(sorted(path.glob("**/*.py")))

        for py_file in py_files:
            for entry in _scan_file(py_file):
                name = entry["operator_name"]
                if name not in seen_names:
                    seen_names.add(name)
                    raw_entries.append(entry)

    candidates = []
    for rank, entry in enumerate(raw_entries, start=1):
        candidates.append({
            "rank": rank,
            "operator_name": entry["operator_name"],
            "operator_type": _infer_type_from_name(entry["operator_name"]),
            "description": entry["description"],
            "relevance_score": 1.0,
            "score_source": "custom_operator",
            "key_match": [],
            "arguments_preview": entry["arguments_preview"],
            "is_custom": True,
            "source_file": entry["source_file"],
        })

    return candidates


def _infer_type_from_name(name: str) -> str:
    """Infer operator type from naming convention."""
    if name.endswith("_mapper"):
        return "mapper"
    if name.endswith("_filter"):
        return "filter"
    if "dedup" in name:
        return "deduplicator"
    return "mapper"


__all__ = ["scan_custom_operators"]
