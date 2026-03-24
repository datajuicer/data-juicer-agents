# -*- coding: utf-8 -*-
"""Shared system-spec helpers for plan tools."""
from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List, Tuple

from .normalize import normalize_string_list
from .schema import SystemSpec


def normalize_system_spec(
    system_spec: SystemSpec | Dict[str, Any] | None,
    *,
    custom_operator_paths: Iterable[Any] | None = None,
) -> SystemSpec:
    """Normalize system spec, preserving all dynamic fields from Data-Juicer.

    Performs type coercion on all fields (core + extra) via
    ``coerce_fields`` so that values serialise correctly in recipe YAML.
    """
    if isinstance(system_spec, SystemSpec):
        spec = system_spec
    elif isinstance(system_spec, dict):
        spec = SystemSpec.from_dict(system_spec)
    elif system_spec is None:
        spec = SystemSpec()
    else:
        raise ValueError("system_spec must be a dict object")

    # Override custom_operator_paths if provided externally
    if custom_operator_paths is not None:
        spec.custom_operator_paths = normalize_string_list(custom_operator_paths)

    # Coerce all fields to correct types for YAML serialization
    try:
        from data_juicer_agents.utils.dj_config_bridge import coerce_fields

        # Coerce extra fields
        coerced_extra, extra_errors = coerce_fields(spec._extra_fields)
        spec._extra_fields = coerced_extra

        # Coerce core fields (np might be string from LLM)
        core_dict = {"np": spec.np, "executor_type": spec.executor_type}
        coerced_core, core_errors = coerce_fields(core_dict)
        spec.np = coerced_core.get("np", spec.np)
        spec.executor_type = coerced_core.get("executor_type", spec.executor_type)

        coerce_errors = extra_errors + core_errors
        if coerce_errors:
            spec.warnings.extend(f"[type coercion] {err}" for err in coerce_errors)
    except Exception:
        pass  # bridge unavailable — skip coercion

    # --- Auto-corrections (mirrors DJ init_setup_from_cfg) ----------------

    # np cap: ensure np does not exceed available CPU cores
    cpu_count = os.cpu_count() or 1
    if spec.np > cpu_count:
        spec.warnings.append(
            f"[auto-corrected] np={spec.np} exceeds CPU count "
            f"({cpu_count}); capped to {cpu_count}"
        )
        spec.np = cpu_count

    # cache / checkpoint mutual exclusion:
    # disabling cache or enabling checkpoint makes cache_compress meaningless
    use_cache = spec.get("use_cache", True)
    use_checkpoint = spec.get("use_checkpoint", False)
    cache_compress = spec.get("cache_compress", None)
    if (not use_cache or use_checkpoint) and cache_compress:
        spec.warnings.append(
            "[auto-corrected] cache_compress disabled because "
            "cache is off or checkpoint is on"
        )
        spec.set("cache_compress", None)

    # op_fusion / checkpoint mutual exclusion:
    # op fusion is not compatible with checkpoint mode
    op_fusion = spec.get("op_fusion", False)
    if op_fusion and spec.get("use_checkpoint", False):
        spec.warnings.append(
            "[auto-corrected] use_checkpoint disabled because " "op_fusion is enabled"
        )
        spec.set("use_checkpoint", False)

    return spec


def validate_system_spec_payload(
    system_spec: SystemSpec | Dict[str, Any],
) -> Tuple[List[str], List[str]]:
    """Validate system spec using Data-Juicer's native validation when possible."""
    if isinstance(system_spec, dict):
        system_spec = SystemSpec.from_dict(system_spec)

    errors: List[str] = []
    warnings: List[str] = []

    # Basic validation for core fields
    if not system_spec.executor_type:
        errors.append("executor_type is required")
    if int(system_spec.np or 0) <= 0:
        errors.append("np must be >= 1")

    # DJ parser validation
    try:
        from data_juicer_agents.utils.dj_config_bridge import get_dj_config_bridge

        bridge = get_dj_config_bridge()
        system_dict = system_spec.to_dict()
        # Remove non-DJ fields before validation
        dj_dict = {k: v for k, v in system_dict.items() if k != "warnings"}
        is_valid, dj_errors = bridge.validate(dj_dict)

        if not is_valid:
            errors.extend(dj_errors)
    except Exception:
        pass

    # --- Semantic validation (mirrors DJ init_setup_from_cfg) -------------

    # fusion_strategy must be in FUSION_STRATEGIES when op_fusion is on
    op_fusion = system_spec.get("op_fusion", False)
    if op_fusion:
        fusion_strategy = (
            str(system_spec.get("fusion_strategy", "") or "").strip().lower()
        )
        if fusion_strategy:
            try:
                from data_juicer.ops.op_fusion import FUSION_STRATEGIES

                if fusion_strategy not in FUSION_STRATEGIES:
                    errors.append(
                        f"fusion_strategy '{fusion_strategy}' is not supported; "
                        f"must be one of {sorted(FUSION_STRATEGIES)}"
                    )
            except Exception:
                pass  # DJ unavailable — skip check

    # work_dir: {job_id} placeholder must be the last path component
    work_dir = str(system_spec.get("work_dir", "") or "").strip()
    if work_dir and "{job_id}" in work_dir:
        if not work_dir.rstrip("/").endswith("{job_id}"):
            errors.append(
                "work_dir: '{job_id}' placeholder must be the last "
                "component of the path"
            )

    warnings.extend(
        [item for item in system_spec.warnings if item and item not in warnings]
    )

    return errors, warnings


__all__ = [
    "normalize_system_spec",
    "validate_system_spec_payload",
]
