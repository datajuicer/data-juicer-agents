# -*- coding: utf-8 -*-
"""Bridge to Data-Juicer's native configuration system.

This module provides a dynamic bridge to Data-Juicer's configuration,
eliminating the need to manually sync schema definitions.
"""

from typing import Any, Dict, List, Optional, Tuple

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
        """Lazy load Data-Juicer parser."""
        if self._parser is None:
            from data_juicer.config.config import build_base_parser

            self._parser = build_base_parser()
        return self._parser

    def get_default_config_dict(self) -> Dict[str, Any]:
        """Get default configuration from Data-Juicer parser.

        This is more efficient than init_configs as it directly extracts
        defaults from the parser without creating temp files or triggering
        full initialization.

        Returns:
            Dict with all default configuration values
        """
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

    def config_to_dict(self, config: Any) -> Dict[str, Any]:
        """Convert Data-Juicer Namespace config to dict.

        Args:
            config: Namespace object from Data-Juicer

        Returns:
            Dict representation of the config
        """
        from jsonargparse import namespace_to_dict

        return namespace_to_dict(config)

    def dict_to_config(self, config_dict: Dict[str, Any]) -> Any:
        """Convert dict to Data-Juicer Namespace config.

        Args:
            config_dict: Dict with config values

        Returns:
            Namespace object
        """
        from jsonargparse import dict_to_namespace

        return dict_to_namespace(config_dict)

    def validate_config(self, config_dict: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate configuration using Data-Juicer's native validation.

        Args:
            config_dict: Configuration dict to validate

        Returns:
            Tuple of (is_valid, error_messages)
        """
        try:
            # Convert dict to Namespace
            cfg = self.dict_to_config(config_dict)

            # Use Data-Juicer's validation
            self.parser.check_config(cfg)

            return True, []
        except Exception as e:
            return False, [str(e)]

    def extract_system_config(
        self, config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Extract system-related configuration from full config.

        Args:
            config: Config dict. If None, uses defaults from parser.

        Returns:
            Dict with system-related config fields
        """
        if config is None:
            config_dict = self.get_default_config_dict()
        elif isinstance(config, dict):
            config_dict = config
        else:
            config_dict = self.config_to_dict(config)

        # System-related field names (excluding process and dataset)
        system_fields = config_dict.keys() - set(dataset_fields) - {"process"}

        system_config = {}
        for field in system_fields:
            if field in config_dict:
                system_config[field] = config_dict[field]

        return system_config

    def extract_dataset_config(
        self, config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Extract dataset-related configuration from full config.

        Args:
            config: Config dict. If None, uses defaults from parser.

        Returns:
            Dict with dataset-related config fields
        """
        if config is None:
            config_dict = self.get_default_config_dict()
        elif isinstance(config, dict):
            config_dict = config
        else:
            config_dict = self.config_to_dict(config)

        dataset_config = {}
        for field in dataset_fields:
            if field in config_dict:
                dataset_config[field] = config_dict[field]

        return dataset_config

    def extract_process_config(
        self, config: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Extract process operators from config.

        Args:
            config: Config dict. If None, uses defaults from parser.

        Returns:
            List of operator dicts
        """
        if config is None:
            config_dict = self.get_default_config_dict()
        elif isinstance(config, dict):
            config_dict = config
        else:
            config_dict = self.config_to_dict(config)

        return config_dict.get("process", [])

    def merge_config(
        self, base_config: Optional[Dict[str, Any]] = None, **overrides
    ) -> Dict[str, Any]:
        """Merge user overrides with base config.

        Args:
            base_config: Base config dict. If None, uses DJ defaults from parser.
            **overrides: Config fields to override

        Returns:
            Merged config dict
        """
        if base_config is None:
            base_config = self.get_default_config_dict()

        merged = dict(base_config)
        merged.update(overrides)

        return merged

    def create_minimal_config(
        self,
        dataset_path: str,
        export_path: str,
        process: Optional[List[Dict[str, Any]]] = None,
        **system_overrides,
    ) -> Dict[str, Any]:
        """Create a minimal valid config for Data-Juicer.

        Args:
            dataset_path: Path to input dataset
            export_path: Path to export output
            process: List of operator configs
            **system_overrides: System config overrides (np, executor_type, etc.)

        Returns:
            Complete config dict ready for Data-Juicer
        """
        # Get defaults from parser
        config_dict = self.get_default_config_dict().copy()

        # Override required fields
        config_dict["dataset_path"] = dataset_path
        config_dict["export_path"] = export_path

        if process is not None:
            config_dict["process"] = process

        # Override system fields
        for key, value in system_overrides.items():
            config_dict[key] = value

        return config_dict


# Singleton instance
_bridge = None


def get_dj_config_bridge() -> DJConfigBridge:
    """Get singleton DJConfigBridge instance."""
    global _bridge
    if _bridge is None:
        _bridge = DJConfigBridge()
    return _bridge


def validate_system_config(system_config: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate system configuration using DJ's native validation.

    Args:
        system_config: System config dict to validate

    Returns:
        Tuple of (is_valid, error_messages)
    """
    bridge = get_dj_config_bridge()

    # Create minimal config with system overrides
    full_config = bridge.create_minimal_config(
        dataset_path="dummy.jsonl", export_path="dummy_output.jsonl", **system_config
    )

    return bridge.validate_config(full_config)

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