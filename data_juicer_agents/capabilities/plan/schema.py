# -*- coding: utf-8 -*-
"""Plan-domain models and validation rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class OperatorStep:
    """One operator invocation in a plan."""

    name: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlanModel:
    """Execution plan representation."""

    plan_id: str
    user_intent: str
    workflow: str
    dataset_path: str
    export_path: str
    modality: str = "unknown"
    text_keys: List[str] = field(default_factory=list)
    image_key: Optional[str] = None
    operators: List[OperatorStep] = field(default_factory=list)
    risk_notes: List[str] = field(default_factory=list)
    estimation: Dict[str, Any] = field(default_factory=dict)
    custom_operator_paths: List[str] = field(default_factory=list)
    template_source_plan_id: Optional[str] = None
    parent_plan_id: Optional[str] = None
    revision: int = 1
    change_summary: List[str] = field(default_factory=list)
    approval_required: bool = True
    created_at: str = field(default_factory=_utc_now_iso)

    @staticmethod
    def new_id() -> str:
        return f"plan_{uuid4().hex[:12]}"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlanModel":
        operators = [
            OperatorStep(name=item["name"], params=item.get("params", {}))
            for item in data.get("operators", [])
        ]
        revision_raw = data.get("revision", 1)
        try:
            revision = int(revision_raw)
        except (TypeError, ValueError):
            revision = 1
        return cls(
            plan_id=data["plan_id"],
            user_intent=data["user_intent"],
            workflow=data["workflow"],
            dataset_path=data["dataset_path"],
            export_path=data["export_path"],
            modality=data.get("modality", "unknown"),
            text_keys=list(data.get("text_keys", [])),
            image_key=data.get("image_key"),
            operators=operators,
            risk_notes=list(data.get("risk_notes", [])),
            estimation=dict(data.get("estimation", {})),
            custom_operator_paths=list(data.get("custom_operator_paths", [])),
            template_source_plan_id=data.get("template_source_plan_id"),
            parent_plan_id=data.get("parent_plan_id"),
            revision=revision,
            change_summary=list(data.get("change_summary", [])),
            approval_required=bool(data.get("approval_required", True)),
            created_at=data.get("created_at", _utc_now_iso()),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "user_intent": self.user_intent,
            "workflow": self.workflow,
            "dataset_path": self.dataset_path,
            "export_path": self.export_path,
            "modality": self.modality,
            "text_keys": self.text_keys,
            "image_key": self.image_key,
            "operators": [
                {"name": op.name, "params": op.params} for op in self.operators
            ],
            "risk_notes": self.risk_notes,
            "estimation": self.estimation,
            "custom_operator_paths": self.custom_operator_paths,
            "template_source_plan_id": self.template_source_plan_id,
            "parent_plan_id": self.parent_plan_id,
            "revision": self.revision,
            "change_summary": self.change_summary,
            "approval_required": self.approval_required,
            "created_at": self.created_at,
        }


def validate_plan(plan: PlanModel) -> List[str]:
    """Return validation errors. Empty list means valid."""

    errors: List[str] = []
    if not plan.plan_id:
        errors.append("plan_id is required")
    if not plan.user_intent:
        errors.append("user_intent is required")
    if plan.workflow not in {"rag_cleaning", "multimodal_dedup", "custom"}:
        errors.append("workflow must be one of rag_cleaning/multimodal_dedup/custom")
    if not plan.dataset_path:
        errors.append("dataset_path is required")
    if not plan.export_path:
        errors.append("export_path is required")
    if plan.modality not in {"text", "image", "multimodal", "unknown"}:
        errors.append("modality must be one of text/image/multimodal/unknown")
    if plan.revision < 1:
        errors.append("revision must be >= 1")
    if not isinstance(plan.custom_operator_paths, list):
        errors.append("custom_operator_paths must be an array")
    if not plan.operators:
        errors.append("operators must not be empty")
    for idx, op in enumerate(plan.operators):
        if not op.name:
            errors.append(f"operators[{idx}].name is required")
        if not isinstance(op.params, dict):
            errors.append(f"operators[{idx}].params must be an object")
    return errors


__all__ = ["OperatorStep", "PlanModel", "validate_plan"]
