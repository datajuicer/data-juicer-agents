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

import inspect
import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Custom operator loading
# ---------------------------------------------------------------------------

# Snapshot of builtin operator names captured before any custom operators
# are loaded.  Populated lazily on first call to
# ``get_builtin_operator_names()`` so that all DJ-native operators are
# already registered by that point.
_builtin_operator_names: Optional[frozenset] = None

# Paths that have already been successfully loaded into the registry.
# Used to skip redundant calls to DJ's ``load_custom_operators`` which
# raises RuntimeError on repeated loads via ``sys.modules`` checks.
_loaded_custom_paths: set = set()

# Whether the OPRecord monkey-patch has been applied.
_op_record_patched: bool = False

# Lock protecting _loaded_custom_paths and _op_record_patched against
# concurrent access from multiple threads.
_custom_op_lock = threading.Lock()


def _patch_op_record() -> None:
    """Monkey-patch ``OPRecord.__init__`` to handle custom operators.

    Data-Juicer's ``OPRecord`` assumes all operators live inside the
    ``data_juicer`` package tree.  Custom operators loaded from standalone
    files break three assumptions:

    1. **Module path depth** — ``op_cls.__module__.split('.')[2]`` assumes
       at least 3 segments (e.g. ``data_juicer.ops.mapper``).  Custom ops
       have a flat module name like ``my_custom_mapper``, causing
       ``IndexError``.

    2. **Source path resolution** — ``get_source_path(op_cls)`` computes a
       path relative to DJ's ``PROJECT_ROOT``.  Custom ops live outside
       that tree, raising ``ValueError``.

    3. **Test path lookup** — ``find_test_by_searching_content`` searches
       DJ's test directory.  Custom ops have no tests there, but the
       fallback is harmless (returns ``None``).

    This patch wraps the original ``__init__`` to pre-resolve the operator
    type for flat-module operators and gracefully handle source/test path
    resolution failures.
    """
    global _op_record_patched
    with _custom_op_lock:
        if _op_record_patched:
            return

        try:
            from data_juicer.tools.op_search import OPRecord
        except ImportError:
            return

        original_init = OPRecord.__init__

        def _safe_init(self, name, op_cls, op_type=None):
            # --- Fix 1: resolve op_type for flat-module custom operators ---
            if op_type is None and op_cls is not None:
                module_parts = op_cls.__module__.split(".")
                if len(module_parts) < 3:
                    op_type = self._search_mro_for_type(op_cls)

            # --- Fix 2 & 3: catch source/test path errors for custom ops ---
            try:
                original_init(self, name, op_cls, op_type=op_type)
            except (ValueError, OSError):
                # Fallback: manually set fields that original_init would set,
                # but with safe defaults for custom operators.
                self.name = name
                self.type = op_type or "unknown"
                self.desc = op_cls.__doc__ or ""

                try:
                    from data_juicer.tools.op_search import analyze_tag_from_cls
                    self.tags = analyze_tag_from_cls(op_cls, name)
                except Exception:
                    self.tags = []

                try:
                    self.sig = inspect.signature(op_cls.__init__)
                except (ValueError, TypeError):
                    self.sig = None

                try:
                    from data_juicer.tools.op_search import extract_param_docstring
                    self.param_desc = extract_param_docstring(
                        op_cls.__init__.__doc__ or ""
                    )
                except Exception:
                    self.param_desc = ""

                self.param_desc_map = self._parse_param_desc()

                # Use the actual source file path (absolute) for custom ops
                try:
                    self.source_path = str(Path(inspect.getfile(op_cls)))
                except (TypeError, OSError):
                    self.source_path = ""

                self.test_path = None

        OPRecord.__init__ = _safe_init
        _op_record_patched = True
        logger.debug("Patched OPRecord.__init__ for custom operator compatibility")


def create_op_searcher(
    *,
    include_formatter: bool = False,
    specified_op_list: Optional[List[str]] = None,
):
    """Create an ``OPSearcher`` instance with custom-operator safety patches.

    All code in ``data_juicer_agents`` that needs an ``OPSearcher`` should
    call this factory instead of importing and instantiating ``OPSearcher``
    directly.  This ensures the ``OPRecord`` monkey-patch is applied
    exactly once before any searcher is created.

    Args:
        include_formatter: Whether to include formatter operators.
        specified_op_list: Optional explicit list of operator names to scan.

    Returns:
        A fully initialised ``OPSearcher`` instance.
    """
    _patch_op_record()

    from data_juicer.tools.op_search import OPSearcher

    if specified_op_list is not None:
        return OPSearcher(specified_op_list=specified_op_list)
    return OPSearcher(include_formatter=include_formatter)


def get_builtin_operator_names() -> frozenset:
    """Return the set of operator names that ship with Data-Juicer.

    The snapshot is captured once on first call and cached for the
    lifetime of the process.  This allows callers to distinguish
    custom operators from built-in ones regardless of how many times
    ``load_custom_operators_into_registry`` is invoked.

    If the DJ registry is empty at call time (e.g. DJ not yet fully
    initialised), the result is **not** cached so that a subsequent
    call can capture the real set.
    """
    global _builtin_operator_names
    if _builtin_operator_names is not None:
        return _builtin_operator_names
    try:
        from data_juicer.ops import OPERATORS
        names = frozenset(OPERATORS.modules.keys())
        if not names:
            logger.warning(
                "OPERATORS.modules is empty; builtin snapshot not cached "
                "— will retry on next call"
            )
            return frozenset()
        _builtin_operator_names = names
    except ImportError:
        _builtin_operator_names = frozenset()
    return _builtin_operator_names


def load_custom_operators_into_registry(paths: List[str]) -> List[str]:
    """Import custom operator modules into the DJ OPERATORS registry.

    Triggers ``@OPERATORS.register_module`` decorators in the given paths.
    Tracks which paths have been successfully loaded so that repeated
    calls with the same paths are silently skipped without hitting DJ's
    ``sys.modules`` conflict detection.

    On first call the builtin operator snapshot is captured automatically
    so that ``get_builtin_operator_names()`` can later distinguish custom
    operators from built-in ones.

    Args:
        paths: List of directory or .py file paths containing custom operators.

    Returns:
        List of warning/error messages encountered during loading.
        Empty list on success.  Callers are responsible for surfacing
        these messages through their own error handling.
    """
    if not paths:
        return ["No custom operator paths provided"]

    # Ensure builtin snapshot is captured before loading custom operators
    get_builtin_operator_names()

    # Patch OPRecord to handle custom operators with flat module paths
    _patch_op_record()

    # Normalize and filter out already-loaded paths
    with _custom_op_lock:
        new_paths = []
        for path in paths:
            normalized = os.path.abspath(path)
            if normalized not in _loaded_custom_paths:
                new_paths.append(path)

        if not new_paths:
            return []

        try:
            from data_juicer.config.config import load_custom_operators
            load_custom_operators(new_paths)
            # Mark all new paths as successfully loaded
            for path in new_paths:
                _loaded_custom_paths.add(os.path.abspath(path))
            return []
        except RuntimeError as exc:
            # DJ raises RuntimeError for genuine name conflicts (e.g. a custom
            # operator has the same module name as an already-loaded one but
            # different source).  Surface this so users know their operator
            # was NOT registered.
            return [f"Custom operator loading issue: {exc}"]
        except Exception as exc:
            return [f"Failed to load custom operators: {exc}"]

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
    "keep_stats_in_res_ds",
    "keep_hashes_in_res_ds",
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
    ) -> Dict[str, Any]:
        """Extract process-related fields (operator list and custom operator paths).

        Returns a dict with ``process`` (the operator list) and optionally
        ``custom_operator_paths`` when present.  This mirrors the ownership
        model where ``custom_operator_paths`` is bound to ``ProcessSpec``.
        """
        config_dict = config if config is not None else self.get_default_config()
        result: Dict[str, Any] = {
            "process": config_dict.get("process", []),
        }
        custom_paths = config_dict.get("custom_operator_paths")
        if custom_paths:
            result["custom_operator_paths"] = custom_paths
        return result

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

    def get_implemented_load_strategies(
        self, executor_type: str = "default"
    ) -> List[Dict[str, Any]]:
        """Dynamically probe DataLoadStrategyRegistry to find truly implemented
        load strategies by inspecting source code for NotImplementedError.

        This avoids hardcoding a whitelist: when the main library fixes a
        placeholder strategy, the agent automatically discovers it on the next
        startup with zero manual maintenance.

        Args:
            executor_type: Filter by executor type ('default', 'ray', or '*' for all).

        Returns:
            List of dicts with keys: executor_type, type, source,
            config_validation_rules (required_fields, optional_fields).
        """
        try:
            from data_juicer.core.data.load_strategy import DataLoadStrategyRegistry
        except ImportError:
            return []

        implemented: List[Dict[str, Any]] = []
        for key, strategy_cls in DataLoadStrategyRegistry._strategies.items():
            # Filter by executor type ('*' means wildcard / match all)
            if executor_type != "*" and key.executor_type not in (executor_type, "*"):
                continue

            try:
                source_code = inspect.getsource(strategy_cls.load_data)
                # If the method body raises NotImplementedError, it is a placeholder
                if "raise NotImplementedError" in source_code:
                    continue
            except (OSError, TypeError):
                # Cannot inspect source (e.g. built-in) → skip to be safe
                continue

            # Extract CONFIG_VALIDATION_RULES if the strategy declares them
            config_rules = getattr(strategy_cls, "CONFIG_VALIDATION_RULES", {})

            implemented.append(
                {
                    "executor_type": key.executor_type,
                    "type": key.data_type,
                    "source": key.data_source,
                    "config_validation_rules": config_rules,
                }
            )

        return implemented

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
