# -*- coding: utf-8 -*-
"""Planner schemas."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class OperatorStep:
    """One executable operator invocation."""

    name: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlanDraftOperator:
    """One operator draft emitted by LLM or provided by agent."""

    name: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlanDraftSpec:
    """Draft spec that is reconciled into a validated plan."""

    modality: str = "unknown"
    text_keys: List[str] = field(default_factory=list)
    image_key: Optional[str] = None
    operators: List[PlanDraftOperator] = field(default_factory=list)
    risk_notes: List[str] = field(default_factory=list)
    estimation: Dict[str, Any] = field(default_factory=dict)
    approval_required: bool = True

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlanDraftSpec":
        operators = []
        for item in data.get("operators", []):
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            params = item.get("params", {})
            if not isinstance(params, dict):
                params = {}
            if name:
                operators.append(PlanDraftOperator(name=name, params=params))
        return cls(
            modality=str(data.get("modality", "unknown") or "unknown").strip() or "unknown",
            text_keys=[
                str(item).strip()
                for item in data.get("text_keys", [])
                if str(item).strip()
            ]
            if isinstance(data.get("text_keys", []), list)
            else [],
            image_key=(str(data.get("image_key", "")).strip() or None),
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
            approval_required=bool(data.get("approval_required", True)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "modality": self.modality,
            "text_keys": list(self.text_keys),
            "image_key": self.image_key,
            "operators": [
                {"name": item.name, "params": item.params}
                for item in self.operators
            ],
            "risk_notes": list(self.risk_notes),
            "estimation": dict(self.estimation),
            "approval_required": self.approval_required,
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
    """Execution plan representation."""

    plan_id: str
    user_intent: str
    dataset_path: str
    export_path: str
    modality: str = "unknown"
    text_keys: List[str] = field(default_factory=list)
    image_key: Optional[str] = None
    operators: List[OperatorStep] = field(default_factory=list)
    risk_notes: List[str] = field(default_factory=list)
    estimation: Dict[str, Any] = field(default_factory=dict)
    custom_operator_paths: List[str] = field(default_factory=list)
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
        return cls(
            plan_id=str(data.get("plan_id", "")).strip(),
            user_intent=str(data.get("user_intent", "")).strip(),
            dataset_path=str(data.get("dataset_path", "")).strip(),
            export_path=str(data.get("export_path", "")).strip(),
            modality=str(data.get("modality", "unknown") or "unknown").strip() or "unknown",
            text_keys=[
                str(item).strip()
                for item in data.get("text_keys", [])
                if str(item).strip()
            ]
            if isinstance(data.get("text_keys", []), list)
            else [],
            image_key=(str(data.get("image_key", "")).strip() or None),
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
            custom_operator_paths=[
                str(item).strip()
                for item in data.get("custom_operator_paths", [])
                if str(item).strip()
            ]
            if isinstance(data.get("custom_operator_paths", []), list)
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
            "modality": self.modality,
            "text_keys": list(self.text_keys),
            "image_key": self.image_key,
            "operators": [
                {"name": item.name, "params": item.params}
                for item in self.operators
            ],
            "risk_notes": list(self.risk_notes),
            "estimation": dict(self.estimation),
            "custom_operator_paths": list(self.custom_operator_paths),
            "approval_required": self.approval_required,
            "created_at": self.created_at,
        }
