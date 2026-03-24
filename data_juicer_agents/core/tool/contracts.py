# -*- coding: utf-8 -*-
"""Runtime-agnostic tool contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Literal, Optional, Tuple, Type

from pydantic import BaseModel, ValidationError


ToolEffect = Literal["read", "write", "execute", "external"]
ToolConfirmation = Literal["none", "recommended", "required"]


@dataclass(frozen=True)
class ToolContext:
    """Execution context shared by all tool runtimes."""

    working_dir: str = "./.djx"
    env: Dict[str, str] = field(default_factory=dict)
    artifacts_dir: Optional[str] = None
    runtime_values: Dict[str, Any] = field(default_factory=dict)

    def resolve_artifacts_dir(self) -> Path:
        raw = str(self.artifacts_dir or self.working_dir or "./.djx").strip() or "./.djx"
        return Path(raw).expanduser()


@dataclass(frozen=True)
class ToolArtifact:
    """Named artifact produced by a tool."""

    path: str
    description: str = ""
    kind: str = "file"
    label: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "description": self.description,
            "kind": self.kind,
            "label": self.label,
        }


@dataclass
class ToolResult:
    """Normalized tool execution result."""

    ok: bool
    summary: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    artifacts: List[ToolArtifact] = field(default_factory=list)
    error_type: str = ""
    error_message: str = ""
    next_actions: List[str] = field(default_factory=list)

    @classmethod
    def success(
        cls,
        *,
        summary: str = "",
        data: Optional[Dict[str, Any]] = None,
        artifacts: Optional[Iterable[ToolArtifact]] = None,
    ) -> "ToolResult":
        return cls(
            ok=True,
            summary=summary,
            data=dict(data or {}),
            artifacts=list(artifacts or []),
        )

    @classmethod
    def failure(
        cls,
        *,
        summary: str,
        error_type: str,
        error_message: str = "",
        data: Optional[Dict[str, Any]] = None,
        next_actions: Optional[Iterable[str]] = None,
    ) -> "ToolResult":
        return cls(
            ok=False,
            summary=summary,
            data=dict(data or {}),
            error_type=str(error_type or "tool_failed"),
            error_message=str(error_message or "").strip(),
            next_actions=list(next_actions or []),
        )

    def to_payload(self, *, action: str | None = None) -> Dict[str, Any]:
        payload = dict(self.data)
        payload.setdefault("ok", bool(self.ok))
        if action and "action" not in payload:
            payload["action"] = action
        if self.summary and "message" not in payload:
            payload["message"] = self.summary
        if self.error_type and "error_type" not in payload:
            payload["error_type"] = self.error_type
        if self.error_message and "error_message" not in payload:
            payload["error_message"] = self.error_message
        if self.next_actions and "next_actions" not in payload:
            payload["next_actions"] = list(self.next_actions)
        if self.artifacts and "artifacts" not in payload:
            payload["artifacts"] = [item.to_dict() for item in self.artifacts]
        return payload


ToolExecutor = Callable[[ToolContext, BaseModel], ToolResult]


@dataclass(frozen=True)
class ToolSpec:
    """Definition of one atomic tool."""

    name: str
    description: str
    input_model: Type[BaseModel]
    output_model: Type[BaseModel] | None
    executor: ToolExecutor
    tags: Tuple[str, ...] = ()
    effects: ToolEffect = "read"
    confirmation: ToolConfirmation = "none"

    def execute(self, ctx: ToolContext, raw_input: BaseModel | Dict[str, Any]) -> ToolResult:
        try:
            if isinstance(raw_input, self.input_model):
                parsed = raw_input
            else:
                parsed = self.input_model.model_validate(raw_input)
            return self.executor(ctx, parsed)
        except ValidationError:
            raise
        except Exception as exc:
            return ToolResult.failure(
                summary=f"tool '{self.name}' raised an unexpected exception: {exc}",
                error_type="tool_exception",
                error_message=str(exc),
            )


__all__ = [
    "ToolArtifact",
    "ToolConfirmation",
    "ToolContext",
    "ToolEffect",
    "ToolExecutor",
    "ToolResult",
    "ToolSpec",
]
