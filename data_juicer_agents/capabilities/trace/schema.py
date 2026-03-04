# -*- coding: utf-8 -*-
"""Run-trace domain model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List
from uuid import uuid4


@dataclass
class RunTraceModel:
    """Persistent run trace for plan apply executions."""

    run_id: str
    plan_id: str
    start_time: str
    end_time: str
    duration_seconds: float
    model_info: Dict[str, str]
    retrieval_mode: str
    selected_workflow: str
    generated_recipe_path: str
    command: str
    status: str
    artifacts: Dict[str, Any]
    error_type: str
    error_message: str
    retry_level: str
    next_actions: List[str]

    @staticmethod
    def new_id() -> str:
        return f"run_{uuid4().hex[:12]}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "plan_id": self.plan_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_seconds": self.duration_seconds,
            "model_info": self.model_info,
            "retrieval_mode": self.retrieval_mode,
            "selected_workflow": self.selected_workflow,
            "generated_recipe_path": self.generated_recipe_path,
            "command": self.command,
            "status": self.status,
            "artifacts": self.artifacts,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "retry_level": self.retry_level,
            "next_actions": self.next_actions,
        }


__all__ = ["RunTraceModel"]
