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
class OperatorStep:
    """One executable operator invocation."""

    name: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemSpec:
    """Runtime/executor-level settings shared by the whole recipe."""

    executor_type: str = "default"
    np: int = 1
    open_tracer: bool = False
    open_monitor: Optional[bool] = None
    use_cache: Optional[bool] = None
    skip_op_error: bool = False
    custom_operator_paths: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SystemSpec":
        return cls(
            executor_type=str(data.get("executor_type", "default") or "default").strip() or "default",
            np=int(data.get("np", 1) or 1),
            open_tracer=bool(data.get("open_tracer", False)),
            open_monitor=data.get("open_monitor") if isinstance(data.get("open_monitor"), bool) else None,
            use_cache=data.get("use_cache") if isinstance(data.get("use_cache"), bool) else None,
            skip_op_error=bool(data.get("skip_op_error", False)),
            custom_operator_paths=[
                str(item).strip()
                for item in data.get("custom_operator_paths", [])
                if str(item).strip()
            ]
            if isinstance(data.get("custom_operator_paths", []), list)
            else [],
            warnings=[
                str(item).strip()
                for item in data.get("warnings", [])
                if str(item).strip()
            ]
            if isinstance(data.get("warnings", []), list)
            else [],
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "executor_type": self.executor_type,
            "np": self.np,
            "open_tracer": self.open_tracer,
            "open_monitor": self.open_monitor,
            "use_cache": self.use_cache,
            "skip_op_error": self.skip_op_error,
            "custom_operator_paths": list(self.custom_operator_paths),
            "warnings": list(self.warnings),
        }


@dataclass
class DatasetIOSpec:
    """Dataset input/output shape used by the recipe."""

    dataset_path: str = ""
    dataset: Optional[Dict[str, Any]] = None
    generated_dataset_config: Optional[Dict[str, Any]] = None
    export_path: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DatasetIOSpec":
        dataset = data.get("dataset")
        generated = data.get("generated_dataset_config")
        return cls(
            dataset_path=str(data.get("dataset_path", "")).strip(),
            dataset=dict(dataset) if isinstance(dataset, dict) else None,
            generated_dataset_config=dict(generated) if isinstance(generated, dict) else None,
            export_path=str(data.get("export_path", "")).strip(),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset_path": self.dataset_path,
            "dataset": dict(self.dataset) if isinstance(self.dataset, dict) else None,
            "generated_dataset_config": (
                dict(self.generated_dataset_config)
                if isinstance(self.generated_dataset_config, dict)
                else None
            ),
            "export_path": self.export_path,
        }


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
            modality=str(data.get("modality", "unknown") or "unknown").strip() or "unknown",
            text_keys=[
                str(item).strip()
                for item in data.get("text_keys", [])
                if str(item).strip()
            ]
            if isinstance(data.get("text_keys", []), list)
            else [],
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
            io=DatasetIOSpec.from_dict(io_payload if isinstance(io_payload, dict) else {}),
            binding=DatasetBindingSpec.from_dict(
                binding_payload if isinstance(binding_payload, dict) else {}
            ),
            warnings=[
                str(item).strip()
                for item in data.get("warnings", [])
                if str(item).strip()
            ]
            if isinstance(data.get("warnings", []), list)
            else [],
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
    """Ordered process/operator specification."""

    operators: List[ProcessOperator] = field(default_factory=list)

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
        return cls(operators=operators)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operators": [
                {"name": item.name, "params": item.params}
                for item in self.operators
            ],
        }


@dataclass
class PlanContext:
    """Deterministic inputs required to build a plan."""

    user_intent: str
    dataset_path: str
    export_path: str
    custom_operator_paths: List[str] = field(default_factory=list)


@dataclass
class PlanModel:
    """Final flattened execution plan representation."""

    plan_id: str
    user_intent: str
    dataset_path: str
    export_path: str
    dataset: Optional[Dict[str, Any]] = None
    generated_dataset_config: Optional[Dict[str, Any]] = None
    modality: str = "unknown"
    text_keys: List[str] = field(default_factory=list)
    image_key: Optional[str] = None
    audio_key: Optional[str] = None
    video_key: Optional[str] = None
    image_bytes_key: Optional[str] = None
    operators: List[OperatorStep] = field(default_factory=list)
    risk_notes: List[str] = field(default_factory=list)
    estimation: Dict[str, Any] = field(default_factory=dict)
    executor_type: str = "default"
    np: int = 1
    open_tracer: bool = False
    open_monitor: Optional[bool] = None
    use_cache: Optional[bool] = None
    skip_op_error: bool = False
    custom_operator_paths: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    approval_required: bool = True
    created_at: str = field(default_factory=_utc_now_iso)

    @staticmethod
    def new_id() -> str:
        return f"plan_{uuid4().hex[:12]}"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlanModel":
        operators = []
        for item in data.get("operators", []):
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            params = item.get("params", {})
            if not isinstance(params, dict):
                params = {}
            if name:
                operators.append(OperatorStep(name=name, params=params))
        dataset = data.get("dataset")
        generated = data.get("generated_dataset_config")
        return cls(
            plan_id=str(data.get("plan_id", "")).strip(),
            user_intent=str(data.get("user_intent", "")).strip(),
            dataset_path=str(data.get("dataset_path", "")).strip(),
            export_path=str(data.get("export_path", "")).strip(),
            dataset=dict(dataset) if isinstance(dataset, dict) else None,
            generated_dataset_config=dict(generated) if isinstance(generated, dict) else None,
            modality=str(data.get("modality", "unknown") or "unknown").strip() or "unknown",
            text_keys=[
                str(item).strip()
                for item in data.get("text_keys", [])
                if str(item).strip()
            ]
            if isinstance(data.get("text_keys", []), list)
            else [],
            image_key=_coerce_optional_text(data.get("image_key")),
            audio_key=_coerce_optional_text(data.get("audio_key")),
            video_key=_coerce_optional_text(data.get("video_key")),
            image_bytes_key=_coerce_optional_text(data.get("image_bytes_key")),
            operators=operators,
            risk_notes=[
                str(item).strip()
                for item in data.get("risk_notes", [])
                if str(item).strip()
            ]
            if isinstance(data.get("risk_notes", []), list)
            else [],
            estimation=dict(data.get("estimation", {}))
            if isinstance(data.get("estimation", {}), dict)
            else {},
            executor_type=str(data.get("executor_type", "default") or "default").strip() or "default",
            np=int(data.get("np", 1) or 1),
            open_tracer=bool(data.get("open_tracer", False)),
            open_monitor=data.get("open_monitor") if isinstance(data.get("open_monitor"), bool) else None,
            use_cache=data.get("use_cache") if isinstance(data.get("use_cache"), bool) else None,
            skip_op_error=bool(data.get("skip_op_error", False)),
            custom_operator_paths=[
                str(item).strip()
                for item in data.get("custom_operator_paths", [])
                if str(item).strip()
            ]
            if isinstance(data.get("custom_operator_paths", []), list)
            else [],
            warnings=[
                str(item).strip()
                for item in data.get("warnings", [])
                if str(item).strip()
            ]
            if isinstance(data.get("warnings", []), list)
            else [],
            approval_required=bool(data.get("approval_required", True)),
            created_at=str(data.get("created_at", _utc_now_iso())).strip() or _utc_now_iso(),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "user_intent": self.user_intent,
            "dataset_path": self.dataset_path,
            "export_path": self.export_path,
            "dataset": dict(self.dataset) if isinstance(self.dataset, dict) else None,
            "generated_dataset_config": (
                dict(self.generated_dataset_config)
                if isinstance(self.generated_dataset_config, dict)
                else None
            ),
            "modality": self.modality,
            "text_keys": list(self.text_keys),
            "image_key": self.image_key,
            "audio_key": self.audio_key,
            "video_key": self.video_key,
            "image_bytes_key": self.image_bytes_key,
            "operators": [
                {"name": item.name, "params": item.params}
                for item in self.operators
            ],
            "risk_notes": list(self.risk_notes),
            "estimation": dict(self.estimation),
            "executor_type": self.executor_type,
            "np": self.np,
            "open_tracer": self.open_tracer,
            "open_monitor": self.open_monitor,
            "use_cache": self.use_cache,
            "skip_op_error": self.skip_op_error,
            "custom_operator_paths": list(self.custom_operator_paths),
            "warnings": list(self.warnings),
            "approval_required": self.approval_required,
            "created_at": self.created_at,
        }


__all__ = [
    "DatasetBindingSpec",
    "DatasetIOSpec",
    "DatasetSpec",
    "OperatorStep",
    "PlanContext",
    "PlanModel",
    "ProcessOperator",
    "ProcessSpec",
    "SystemSpec",
    "_ALLOWED_MODALITIES",
]
