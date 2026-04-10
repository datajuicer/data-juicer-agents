# -*- coding: utf-8 -*-
"""Planner schemas."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4


_ALLOWED_MODALITIES = {"text", "image", "audio", "video", "multimodal", "unknown"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _coerce_optional_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "none":
        return None
    return text


@dataclass
class SystemSpec:
    """Runtime/executor-level settings shared by the whole recipe.

    Note: ``custom_operator_paths`` is owned by ``ProcessSpec``, not here.
    It is semantically tied to the operator list and is written to the
    recipe by ``assemble_plan`` from the process spec.
    """

    # Core fields that are always present
    executor_type: str = "default"
    np: int = 1
    warnings: List[str] = field(default_factory=list)

    # Extra fields storage for any additional DJ system config fields
    # Note: system fields are statically maintained in dj_config_bridge.system_fields
    _extra_fields: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SystemSpec":
        """Create SystemSpec from dict."""
        # Extract core fields
        core_fields = {
            "executor_type": str(
                data.get("executor_type", "default") or "default"
            ).strip()
            or "default",
            "np": int(data.get("np", 1) or 1),
            "warnings": (
                [
                    str(item).strip()
                    for item in data.get("warnings", [])
                    if str(item).strip()
                ]
                if isinstance(data.get("warnings", []), list)
                else []
            ),
        }

        # Store all other fields in _extra_fields as-is.
        # custom_operator_paths is now owned by ProcessSpec; if present in
        # input data (e.g. legacy payloads), it is silently dropped here.
        # Type coercion is handled later by normalize_system_spec().
        core_field_names = {"executor_type", "np", "custom_operator_paths", "warnings"}
        raw_extra_fields = {k: v for k, v in data.items() if k not in core_field_names}

        return cls(**core_fields, _extra_fields=raw_extra_fields)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict, including all extra fields."""
        result = {
            "executor_type": self.executor_type,
            "np": self.np,
            "warnings": list(self.warnings),
        }

        # Add all extra fields
        result.update(self._extra_fields)

        return result

    def get(self, key: str, default: Any = None) -> Any:
        """Get a field value, checking both core and extra fields."""
        if key == "executor_type":
            return self.executor_type
        elif key == "np":
            return self.np
        elif key == "warnings":
            return self.warnings
        else:
            return self._extra_fields.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a field value, updating core or extra fields as appropriate."""
        if key == "executor_type":
            self.executor_type = value
        elif key == "np":
            self.np = value
        elif key == "warnings":
            self.warnings = value
        else:
            self._extra_fields[key] = value

    @classmethod
    def from_dj_config(cls, dj_system_config: Dict[str, Any]) -> "SystemSpec":
        """Create SystemSpec directly from Data-Juicer system config.

        Args:
            dj_system_config: System config dict from DJConfigBridge

        Returns:
            SystemSpec instance with all DJ system fields
        """
        return cls.from_dict(dj_system_config)


@dataclass
class DatasetSourceConfig:
    """Single dataset source entry (one item in dataset.configs)."""

    type: str = field(
        default="local",
        metadata={"description": "Required str. Strategy type (e.g. 'local'). Must match one of the 'type' values returned by list_dataset_load_strategies."},
    )
    path: Optional[str] = field(
        default=None,
        metadata={"description": "Optional str. Path to the dataset file or directory (for file-based sources)."},
    )
    source: Optional[str] = field(
        default=None,
        metadata={"description": "Optional str. Sub-source specifier (e.g. 'file', 's3'). Must match 'source' in the chosen strategy entry."},
    )
    weight: Optional[float] = field(
        default=None,
        metadata={"description": "Optional float. Sampling weight for this source when mixing multiple sources (default: 1.0)."},
    )
    split: Optional[str] = field(
        default=None,
        metadata={"description": "Optional str. Dataset split to load (e.g. 'train', 'test', 'validation')."},
    )
    _extra_kwargs: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DatasetSourceConfig":
        core_keys = {"type", "path", "source", "weight", "split"}
        weight_raw = data.get("weight")
        return cls(
            type=str(data.get("type", "local") or "local").strip(),
            path=_coerce_optional_text(data.get("path")),
            source=_coerce_optional_text(data.get("source")),
            weight=float(weight_raw) if weight_raw is not None else None,
            split=_coerce_optional_text(data.get("split")),
            _extra_kwargs={k: v for k, v in data.items() if k not in core_keys},
        )

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"type": self.type}
        if self.path is not None:
            result["path"] = self.path
        if self.source is not None:
            result["source"] = self.source
        if self.weight is not None:
            result["weight"] = self.weight
        if self.split is not None:
            result["split"] = self.split
        result.update(self._extra_kwargs)
        return result


@dataclass
class DatasetObjectConfig:
    """YAML-style dataset config block (the ``dataset:`` key in a DJ recipe)."""

    configs: List["DatasetSourceConfig"] = field(
        default_factory=list,
        metadata={"description": "Required list. One or more source config dicts, each using the DatasetSourceConfig fields."},
    )
    max_sample_num: Optional[int] = field(
        default=None,
        metadata={"description": "Optional int. Cap the total number of samples loaded across all sources."},
    )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DatasetObjectConfig":
        configs_raw = data.get("configs", [])
        configs = [
            DatasetSourceConfig.from_dict(c)
            for c in configs_raw
            if isinstance(c, dict)
        ]
        max_sample_num_raw = data.get("max_sample_num")
        return cls(
            configs=configs,
            max_sample_num=int(max_sample_num_raw) if max_sample_num_raw is not None else None,
        )

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"configs": [c.to_dict() for c in self.configs]}
        if self.max_sample_num is not None:
            result["max_sample_num"] = self.max_sample_num
        return result


@dataclass
class GeneratedDatasetConfig:
    """Config for dynamically generated datasets via Data-Juicer FORMATTERS."""

    type: str = ""
    _extra_kwargs: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GeneratedDatasetConfig":
        return cls(
            type=str(data.get("type", "") or "").strip(),
            _extra_kwargs={k: v for k, v in data.items() if k != "type"},
        )

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"type": self.type}
        result.update(self._extra_kwargs)
        return result


@dataclass
class DatasetIOSpec:
    """Dataset input/output shape used by the recipe."""

    dataset_path: str = ""
    dataset: Optional[DatasetObjectConfig] = None
    generated_dataset_config: Optional[GeneratedDatasetConfig] = None
    export_path: str = ""
    # Extra dataset fields storage for advanced options (export_type, export_shard_size,
    # load_dataset_kwargs, suffixes, image_special_token, etc.).
    # These are passed via build_dataset_spec kwargs and transparently forwarded to the recipe.
    _extra_fields: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DatasetIOSpec":
        dataset_raw = data.get("dataset")
        generated_raw = data.get("generated_dataset_config")
        core_keys = {"dataset_path", "dataset", "generated_dataset_config", "export_path"}
        return cls(
            dataset_path=str(data.get("dataset_path", "")).strip(),
            dataset=DatasetObjectConfig.from_dict(dataset_raw) if isinstance(dataset_raw, dict) else None,
            generated_dataset_config=(
                GeneratedDatasetConfig.from_dict(generated_raw) if isinstance(generated_raw, dict) else None
            ),
            export_path=str(data.get("export_path", "")).strip(),
            _extra_fields={k: v for k, v in data.items() if k not in core_keys},
        )

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "dataset_path": self.dataset_path,
            "dataset": self.dataset.to_dict() if self.dataset is not None else None,
            "generated_dataset_config": (
                self.generated_dataset_config.to_dict()
                if self.generated_dataset_config is not None
                else None
            ),
            "export_path": self.export_path,
        }
        # Merge extra fields (advanced dataset options) into the output
        result.update(self._extra_fields)
        return result


@dataclass
class DatasetBindingSpec:
    """Shared/default field binding layer for the recipe."""

    modality: str = "unknown"
    text_keys: List[str] = field(default_factory=list)
    image_key: Optional[str] = None
    audio_key: Optional[str] = None
    video_key: Optional[str] = None
    image_bytes_key: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DatasetBindingSpec":
        return cls(
            modality=str(data.get("modality", "unknown") or "unknown").strip()
            or "unknown",
            text_keys=(
                [
                    str(item).strip()
                    for item in data.get("text_keys", [])
                    if str(item).strip()
                ]
                if isinstance(data.get("text_keys", []), list)
                else []
            ),
            image_key=_coerce_optional_text(data.get("image_key")),
            audio_key=_coerce_optional_text(data.get("audio_key")),
            video_key=_coerce_optional_text(data.get("video_key")),
            image_bytes_key=_coerce_optional_text(data.get("image_bytes_key")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "modality": self.modality,
            "text_keys": list(self.text_keys),
            "image_key": self.image_key,
            "audio_key": self.audio_key,
            "video_key": self.video_key,
            "image_bytes_key": self.image_bytes_key,
        }


@dataclass
class DatasetSpec:
    """Dataset IO and binding spec."""

    io: DatasetIOSpec = field(default_factory=DatasetIOSpec)
    binding: DatasetBindingSpec = field(default_factory=DatasetBindingSpec)
    warnings: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DatasetSpec":
        io_payload = data.get("io", {})
        binding_payload = data.get("binding", {})
        return cls(
            io=DatasetIOSpec.from_dict(
                io_payload if isinstance(io_payload, dict) else {}
            ),
            binding=DatasetBindingSpec.from_dict(
                binding_payload if isinstance(binding_payload, dict) else {}
            ),
            warnings=(
                [
                    str(item).strip()
                    for item in data.get("warnings", [])
                    if str(item).strip()
                ]
                if isinstance(data.get("warnings", []), list)
                else []
            ),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "io": self.io.to_dict(),
            "binding": self.binding.to_dict(),
            "warnings": list(self.warnings),
        }


@dataclass
class ProcessOperator:
    """One operator inside the process spec."""

    name: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProcessSpec:
    """Ordered process/operator specification.

    ``custom_operator_paths`` is bound here (not in ``SystemSpec``)
    because it is semantically tied to the operator list: the paths
    determine which custom operators are available for validation and
    execution.  This mirrors how ``DatasetBindingSpec`` binds
    ``image_key`` to the dataset spec.
    """

    operators: List[ProcessOperator] = field(default_factory=list)
    custom_operator_paths: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProcessSpec":
        operators: List[ProcessOperator] = []
        for item in data.get("operators", []):
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            params = item.get("params", {})
            if not isinstance(params, dict):
                params = {}
            if name:
                operators.append(ProcessOperator(name=name, params=params))
        raw_paths = data.get("custom_operator_paths", [])
        custom_operator_paths = (
            [str(p).strip() for p in raw_paths if str(p).strip()]
            if isinstance(raw_paths, list)
            else []
        )
        return cls(operators=operators, custom_operator_paths=custom_operator_paths)

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "operators": [
                {"name": item.name, "params": item.params} for item in self.operators
            ],
        }
        if self.custom_operator_paths:
            result["custom_operator_paths"] = list(self.custom_operator_paths)
        return result


@dataclass
class PlanContext:
    """Deterministic inputs required to build a plan."""

    user_intent: str
    dataset_path: str
    export_path: str


@dataclass
class PlanModel:
    """Execution plan: plan metadata + embedded DJ-native recipe.

    The ``recipe`` field is a plain dict that maps 1-to-1 with a
    Data-Juicer YAML config file.  All dataset, system, and process
    settings live inside ``recipe``; ``PlanModel`` itself only owns
    plan-level metadata.

    Downstream code should access recipe fields via ``plan.recipe[key]``
    or ``plan.recipe.get(key)`` to keep the boundary between plan
    metadata and DJ config clear.
    """

    # Plan-level metadata (strong-typed)
    plan_id: str
    user_intent: str
    modality: str = "unknown"
    operator_names: List[str] = field(default_factory=list)
    recipe: Dict[str, Any] = field(default_factory=dict)
    risk_notes: List[str] = field(default_factory=list)
    estimation: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    approval_required: bool = True
    created_at: str = field(default_factory=_utc_now_iso)

    @staticmethod
    def new_id() -> str:
        return f"plan_{uuid4().hex[:12]}"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlanModel":
        recipe = data.get("recipe")
        if not isinstance(recipe, dict):
            raise ValueError("plan must contain a 'recipe' dict")

        if "process" in recipe and isinstance(recipe["process"], list):
            operator_names = [
                list(step.keys())[0]
                for step in recipe["process"]
                if isinstance(step, dict) and step
            ]
        else:
            operator_names = []

        warnings = (
            [
                str(item).strip()
                for item in data.get("warnings", [])
                if str(item).strip()
            ]
            if isinstance(data.get("warnings", []), list)
            else []
        )

        risk_notes_raw = data.get("risk_notes", [])
        risk_notes = (
            [str(item).strip() for item in risk_notes_raw if str(item).strip()]
            if isinstance(risk_notes_raw, list)
            else []
        )
        estimation_raw = data.get("estimation", {})
        estimation = dict(estimation_raw) if isinstance(estimation_raw, dict) else {}

        return cls(
            plan_id=str(data.get("plan_id", "")).strip(),
            user_intent=str(data.get("user_intent", "")).strip(),
            modality=str(data.get("modality", "unknown") or "unknown").strip()
            or "unknown",
            operator_names=operator_names,
            recipe=dict(recipe),
            risk_notes=risk_notes,
            estimation=estimation,
            warnings=warnings,
            approval_required=bool(data.get("approval_required", True)),
            created_at=str(data.get("created_at", _utc_now_iso())).strip()
            or _utc_now_iso(),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "user_intent": self.user_intent,
            "modality": self.modality,
            "operator_names": list(self.operator_names),
            "recipe": dict(self.recipe),
            "risk_notes": list(self.risk_notes),
            "estimation": dict(self.estimation),
            "warnings": list(self.warnings),
            "approval_required": self.approval_required,
            "created_at": self.created_at,
        }


__all__ = [
    "DatasetBindingSpec",
    "DatasetIOSpec",
    "DatasetObjectConfig",
    "DatasetSourceConfig",
    "DatasetSpec",
    "GeneratedDatasetConfig",
    "PlanContext",
    "PlanModel",
    "ProcessOperator",
    "ProcessSpec",
    "SystemSpec",
    "_ALLOWED_MODALITIES",
]
