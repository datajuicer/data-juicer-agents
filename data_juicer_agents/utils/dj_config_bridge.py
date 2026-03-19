# -*- coding: utf-8 -*-
"""Bridge to Data-Juicer's native configuration system.

This module provides a dynamic bridge to Data-Juicer's configuration,
eliminating the need to manually sync schema definitions.
"""

from typing import Any, Dict, List, Optional, Tuple
import tempfile
import json
import os

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


class DJConfigBridge:
    """Bridge to Data-Juicer's native configuration and validation."""

    def __init__(self):
        self._parser = None
        self._default_config = None

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

    def get_default_config(self) -> Dict[str, Any]:
        if self._default_config is not None:
            return self._default_config

        defaults = {}

        # Extract defaults from parser actions
        for action in self.parser._actions:
            if not hasattr(action, "dest") or action.dest == "help":
                continue

            dest = action.dest
            default_value = getattr(action, "default", None)

            # Handle special cases
            if default_value is not None:
                defaults[dest] = default_value

        self._default_config = defaults
        return defaults

    def validate_config(self, config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate config dict using Data-Juicer's parser.

        Works for full config, partial config (system/dataset/process only).

        Args:
            config: Config dict to validate

        Returns:
            (is_valid, error_messages)
        """
        used_ops = {
            list(op.keys())[0]
            for op in config.get("process", [])
            if op
        }
        parser = self._build_parser_with_ops(used_ops or None)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config, f)
            temp_path = f.name

        try:
            parser.parse_args(["--config", temp_path])
            return True, []
        except Exception as e:
            return False, [str(e)]
        finally:
            os.unlink(temp_path)

    def extract_system_config(self, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Extract system-related fields (excluding dataset fields and process)."""
        config_dict = config if config is not None else self.get_default_config()
        system_fields = set(config_dict.keys()) - set(dataset_fields) - {"process"}
        return {f: config_dict[f] for f in system_fields if f in config_dict}

    def extract_dataset_config(self, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Extract dataset-related fields."""
        config_dict = config if config is not None else self.get_default_config()
        return {f: config_dict[f] for f in dataset_fields if f in config_dict}

    def extract_process_config(self, config: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
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

# Singleton instance
_bridge = None


def get_dj_config_bridge() -> DJConfigBridge:
    """Get singleton DJConfigBridge instance."""
    global _bridge
    if _bridge is None:
        _bridge = DJConfigBridge()
    return _bridge


def validate_system_config(system_config: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate system config fields only.
    
    Args:
        system_config: System config fields to validate
        
    Returns:
        (is_valid, error_messages)
    """
    bridge = get_dj_config_bridge()
    
    # Merge system config into defaults to get a complete valid config
    base = bridge.get_default_config().copy()
    base.update(system_config)
    
    # Remove process to skip OP validation
    base.pop("process", None)
    
    return bridge.validate_config(base)


def get_system_config_schema() -> Dict[str, Any]:
    """Get system configuration schema from Data-Juicer.
    
    Returns:
        Dict with system config fields and their default values
    """
    bridge = get_dj_config_bridge()
    return bridge.extract_system_config()


def get_system_param_descriptions() -> Dict[str, str]:
    """Get descriptions for all system parameters from Data-Juicer parser.
    
    Returns:
        Dict mapping parameter names to their descriptions
    """
    bridge = get_dj_config_bridge()
    descriptions = {}
    
    for action in bridge.parser._actions:
        if not hasattr(action, 'dest') or action.dest == 'help':
            continue
        
        dest = action.dest
        help_text = getattr(action, 'help', '')
        
        if help_text and dest:
            descriptions[dest] = help_text
    
    return descriptions


def coerce_extra_fields(extra_fields: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """Coerce extra system fields to their correct types using the DJ parser.

    Uses ``parser.parse_object()`` to enforce type hints (e.g. ``bool`` for
    ``open_tracer``) without writing any temporary files or requiring a full
    config.  Fields whose keys are not registered in the parser are passed
    through unchanged.

    Args:
        extra_fields: Dict of extra system config fields to coerce.

    Returns:
        A tuple ``(coerced_fields, errors)`` where ``errors`` is a list of
        human-readable messages for any field that failed type coercion.
    """
    if not extra_fields:
        return {}, []

    bridge = get_dj_config_bridge()

    known_parser_dests = {
        action.dest
        for action in bridge.parser._actions
        if hasattr(action, "dest") and action.dest != "help"
    }

    known_fields = {k: v for k, v in extra_fields.items() if k in known_parser_dests}
    unknown_fields = {k: v for k, v in extra_fields.items() if k not in known_parser_dests}

    if not known_fields:
        return dict(extra_fields), []

    errors: List[str] = []
    coerced_known: Dict[str, Any] = dict(known_fields)

    try:
        # parse_object accepts a plain dict and applies type coercion without
        # requiring a temporary file or a fully-populated config.
        namespace = bridge.parser.parse_object(known_fields)
        for key in known_fields:
            if hasattr(namespace, key):
                coerced_known[key] = getattr(namespace, key)
    except SystemExit:
        # jsonargparse calls sys.exit(2) on type errors; treat as a soft error
        errors.append(
            f"Type coercion failed for fields: {list(known_fields.keys())}. "
            "Values kept as-is."
        )
    except Exception as exc:
        errors.append(str(exc))

    return {**coerced_known, **unknown_fields}, errors


def get_op_valid_params(op_names: set) -> Tuple[Dict[str, set], set]:
    """Get valid parameter names for each operator, and all known operator names.

    Uses ``_build_parser_with_ops`` to register the requested operators into a
    fresh parser, then extracts the set of valid parameter names from the
    resulting flat actions (e.g. ``text_length_filter.min_len`` → ``min_len``).

    Args:
        op_names: Set of operator names to look up.

    Returns:
        A tuple ``(op_param_map, known_op_names)`` where:
        - ``op_param_map``: ``{op_name: {valid_param_name, ...}}``
        - ``known_op_names``: set of all registered operator names in DJ
    """
    bridge = get_dj_config_bridge()

    # All registered operator names from DJ's OPERATORS registry
    try:
        from data_juicer.ops.base_op import OPERATORS
        known_op_names: set = set(OPERATORS.modules.keys())
    except Exception:
        known_op_names = set()

    if not op_names:
        return {}, known_op_names

    # Only build parser for ops that actually exist in the registry
    valid_requested = op_names & known_op_names
    if not valid_requested:
        return {}, known_op_names

    try:
        parser = bridge._build_parser_with_ops(valid_requested)
    except Exception:
        return {}, known_op_names

    # Extract {op_name: {param_name, ...}} from flat actions like "op_name.param_name"
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