# -*- coding: utf-8 -*-
"""Bridge to Data-Juicer's native configuration system.

This module provides a dynamic bridge to Data-Juicer's configuration,
eliminating the need to manually sync schema definitions.

Public API:
    get_dj_config_bridge()  → singleton DJConfigBridge instance
    coerce_fields()         → type-coerce dict values via DJ parser hints

Field classification lists:
    dataset_fields          → dataset I/O and binding fields
    system_fields           → runtime/executor system fields
    agent_managed_fields    → fields auto-set by the agent (not by LLM)
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Field classification
# ---------------------------------------------------------------------------

# Fields automatically managed by the agent layer (not exposed to LLM).
# These are set programmatically during apply (e.g. project_name ← plan_id).
agent_managed_fields = [
    "project_name",
    "job_id",
    "auto",  # This is for auto-analyze mode, temporarily added here to avoid LLM exposure until we decide how to handle it.
    "config",  # This is for passing the full config dict to the agent for internal use, not for LLM configuration.
]

# Dataset-related field names
dataset_fields = [
    "dataset_path",
    "dataset",
    "generated_dataset_config",
    "validators",
    "load_dataset_kwargs",
    "export_path",
    "export_type",
    "export_shard_size",
    "export_in_parallel",
    "export_extra_args",
    "export_aws_credentials",
    "text_keys",
    "image_key",
    "image_bytes_key",
    "image_special_token",
    "audio_key",
    "audio_special_token",
    "video_key",
    "video_special_token",
    "eoc_special_token",
    "suffixes",
    "keep_stats_in_res_ds",
    "keep_hashes_in_res_ds",
]

# System/runtime-related field names (executor, parallelism, caching, etc.)
system_fields = [
    "adaptive_batch_size",
    "auto_num",
    "auto_op_parallelism",
    "backup_count",
    "cache_compress",
    "checkpoint.enabled",
    "checkpoint.n_ops",
    "checkpoint.op_names",
    "checkpoint.strategy",
    "checkpoint_dir",
    "conflict_resolve_strategy",
    "custom_operator_paths",
    "data_probe_algo",
    "data_probe_ratio",
    "debug",
    "ds_cache_dir",
    "event_log_dir",
    "event_logging.enabled",
    "executor_type",
    "export_original_dataset",
    "fusion_strategy",
    "hpo_config",
    "intermediate_storage.cleanup_on_success",
    "intermediate_storage.cleanup_temp_files",
    "intermediate_storage.compression",
    "intermediate_storage.format",
    "intermediate_storage.max_retention_days",
    "intermediate_storage.preserve_intermediate_data",
    "intermediate_storage.retention_policy",
    "intermediate_storage.write_partitions",
    "max_log_size_mb",
    "max_partition_size_mb",
    "min_common_dep_num_to_combine",
    "np",
    "op_fusion",
    "op_list_to_mine",
    "op_list_to_trace",
    "open_insight_mining",
    "open_monitor",
    "open_tracer",
    "partition.mode",
    "partition.num_of_partitions",
    "partition.target_size_mb",
    "partition_dir",
    "partition_size",
    "percentiles",
    "preserve_intermediate_data",
    "ray_address",
    "resource_optimization.auto_configure",
    "save_stats_in_one_file",
    "skip_op_error",
    "temp_dir",
    "trace_keys",
    "trace_num",
    "turbo",
    "use_cache",
    "use_checkpoint",
    "work_dir",
]

# ---------------------------------------------------------------------------
# Bridge class
# ---------------------------------------------------------------------------


class DJConfigBridge:
    """Bridge to Data-Juicer's native configuration and validation.

    All DJ-dependent logic is centralised here.  Callers should obtain
    the singleton via ``get_dj_config_bridge()`` and call methods on it.
    """

    def __init__(self):
        self._parser = None
        self._default_config = None

    # -- parser helpers -----------------------------------------------------

    @property
    def parser(self):
        """Lazy load Data-Juicer base parser (no OPs registered)."""
        if self._parser is None:
            from data_juicer.config.config import build_base_parser

            self._parser = build_base_parser()
        return self._parser

    def _build_parser_with_ops(self, used_ops: Optional[set] = None):
        """Build a fresh parser with OP arguments registered."""
        from data_juicer.config.config import (
            build_base_parser,
            sort_op_by_types_and_names,
            _collect_config_info_from_class_docs,
        )
        from data_juicer.ops.base_op import OPERATORS

        parser = build_base_parser()
        if used_ops:
            ops_sorted = sort_op_by_types_and_names(OPERATORS.modules.items())
            _collect_config_info_from_class_docs(
                [(name, cls) for name, cls in ops_sorted if name in used_ops],
                parser,
            )
        return parser

    # -- config extraction --------------------------------------------------

    def get_default_config(self) -> Dict[str, Any]:
        """Return all parser fields with their default values (cached)."""
        if self._default_config is not None:
            return self._default_config

        defaults = {}
        for action in self.parser._actions:
            if not hasattr(action, "dest") or action.dest == "help":
                continue
            defaults[action.dest] = getattr(action, "default", None)

        self._default_config = defaults
        return defaults

    def extract_system_config(
        self, config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Extract system-related fields based on the explicit ``system_fields`` list."""
        config_dict = config if config is not None else self.get_default_config()
        return {f: config_dict[f] for f in system_fields if f in config_dict}

    def extract_dataset_config(
        self, config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Extract dataset-related fields."""
        config_dict = config if config is not None else self.get_default_config()
        return {f: config_dict[f] for f in dataset_fields if f in config_dict}

    def extract_agent_managed_config(
        self, config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Extract agent-managed fields (auto-set by agent, not by LLM).

        These fields (e.g. ``project_name``) are programmatically set
        during the apply phase and should not be exposed to the LLM for
        configuration.
        """
        config_dict = config if config is not None else self.get_default_config()
        return {f: config_dict[f] for f in agent_managed_fields if f in config_dict}

    def extract_process_config(
        self, config: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Extract process operator list."""
        config_dict = config if config is not None else self.get_default_config()
        return config_dict.get("process", [])

    def get_param_descriptions(self) -> Dict[str, str]:
        """Get help text for all parameters from parser."""
        return {
            action.dest: getattr(action, "help", "")
            for action in self.parser._actions
            if hasattr(action, "dest") and action.dest != "help"
        }

    # -- validation ---------------------------------------------------------

    def validate(self, config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate a config dict using DJ base parser.

        Checks system/dataset field types and rejects unknown keys.
        Does NOT validate process list contents or operator params
        (that is handled by get_op_valid_params in the agents layer).

        Args:
            config: Config dict to validate.

        Returns:
            ``(is_valid, error_messages)``
        """
        try:
            from jsonargparse import Namespace

            ns = Namespace(**config)
            self.parser.validate(ns)
            return True, []
        except Exception as e:
            return False, [str(e)]

    # -- operator introspection ---------------------------------------------

    def get_op_valid_params(self, op_names: set) -> Tuple[Dict[str, set], set]:
        """Get valid parameter names for each operator.

        Registers the requested operators into a fresh parser, then
        extracts valid parameter names from the resulting flat actions
        (e.g. ``text_length_filter.min_len`` -> ``min_len``).

        Args:
            op_names: Set of operator names to look up.

        Returns:
            ``(op_param_map, known_op_names)`` where
            *op_param_map* is ``{op_name: {param, ...}}`` and
            *known_op_names* is the full set of registered DJ operators.
        """
        try:
            from data_juicer.ops.base_op import OPERATORS

            known_op_names: set = set(OPERATORS.modules.keys())
        except Exception:
            known_op_names = set()

        if not op_names:
            return {}, known_op_names

        valid_requested = op_names & known_op_names
        if not valid_requested:
            return {}, known_op_names

        try:
            parser = self._build_parser_with_ops(valid_requested)
        except Exception:
            return {}, known_op_names

        op_param_map: Dict[str, set] = {op: set() for op in valid_requested}
        for action in parser._actions:
            if not hasattr(action, "dest"):
                continue
            dest = action.dest
            if "." not in dest:
                continue
            op_name, param_name = dest.split(".", 1)
            if op_name in op_param_map:
                op_param_map[op_name].add(param_name)

        return op_param_map, known_op_names


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_bridge = None


def get_dj_config_bridge() -> DJConfigBridge:
    """Get singleton DJConfigBridge instance."""
    global _bridge
    if _bridge is None:
        _bridge = DJConfigBridge()
    return _bridge


# ---------------------------------------------------------------------------
# Standalone utility (used by normalize layer, not a bridge wrapper)
# ---------------------------------------------------------------------------


def coerce_fields(fields: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """Coerce field values to their correct basic Python types via DJ parser.

    Performs safe conversions for basic types (``bool``, ``int``, ``float``)
    by inspecting the DJ parser's registered default-value types.  Fields
    with non-basic target types or fields not registered in the parser are
    passed through unchanged.

    This is used during normalization to ensure values serialise correctly
    in recipe YAML (e.g. ``"true"`` -> ``True``, ``"4"`` -> ``4``).

    Args:
        fields: Dict of config fields to coerce.

    Returns:
        ``(coerced_fields, errors)`` where *errors* lists human-readable
        messages for any field that failed type coercion.
    """
    if not fields:
        return {}, []

    bridge = get_dj_config_bridge()

    # Build dest -> expected type mapping from parser default values.
    action_type_map: Dict[str, Any] = {}
    known_parser_dests: set = set()
    for action in bridge.parser._actions:
        if hasattr(action, "dest") and action.dest != "help":
            known_parser_dests.add(action.dest)
            default = getattr(action, "default", None)
            action_type_map[action.dest] = (
                type(default) if default is not None else None
            )

    known_fields = {k: v for k, v in fields.items() if k in known_parser_dests}
    unknown_fields = {k: v for k, v in fields.items() if k not in known_parser_dests}

    if not known_fields:
        return dict(fields), []

    errors: List[str] = []
    coerced_known: Dict[str, Any] = {}

    _BOOL_TRUE = {"true", "1", "yes"}
    _BOOL_FALSE = {"false", "0", "no"}

    for key, value in known_fields.items():
        expected_type = action_type_map.get(key)

        if expected_type is bool and isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in _BOOL_TRUE:
                coerced_known[key] = True
            elif lowered in _BOOL_FALSE:
                coerced_known[key] = False
            else:
                coerced_known[key] = value
                errors.append(f"Cannot coerce {key}={value!r} to bool; kept as-is.")
        elif expected_type is int and isinstance(value, str):
            try:
                coerced_known[key] = int(value)
            except (ValueError, TypeError):
                coerced_known[key] = value
                errors.append(f"Cannot coerce {key}={value!r} to int; kept as-is.")
        elif expected_type is float and isinstance(value, str):
            try:
                coerced_known[key] = float(value)
            except (ValueError, TypeError):
                coerced_known[key] = value
                errors.append(f"Cannot coerce {key}={value!r} to float; kept as-is.")
        else:
            coerced_known[key] = value

    return {**coerced_known, **unknown_fields}, errors
