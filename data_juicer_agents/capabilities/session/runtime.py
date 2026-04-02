# -*- coding: utf-8 -*-
"""Runtime primitives shared by session tools."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

import yaml

from data_juicer_agents.tools.plan import PlanModel
from data_juicer_agents.utils.runtime_helpers import (
    normalize_line_idx,
    parse_line_ranges,
    run_interruptible_subprocess,
    short_log,
    to_bool,
    to_event_result_preview,
    to_int,
    to_string_list,
    to_text_response,
    truncate_text,
)

_logger = logging.getLogger(__name__)


@dataclass
class SessionState:
    dataset_path: Optional[str] = None
    export_path: Optional[str] = None
    working_dir: str = "./.djx"
    plan_path: Optional[str] = None
    plan_intent: Optional[str] = None
    custom_operator_paths: List[str] = field(default_factory=list)
    dataset_spec: Optional[Dict[str, Any]] = None
    process_spec: Optional[Dict[str, Any]] = None
    system_spec: Optional[Dict[str, Any]] = None
    draft_plan: Optional[Dict[str, Any]] = None
    draft_plan_path_hint: Optional[str] = None
    last_retrieval: Dict[str, Any] = field(default_factory=dict)
    last_inspected_dataset: Optional[str] = None
    last_dataset_profile: Dict[str, Any] = field(default_factory=dict)
    history: List[Dict[str, str]] = field(default_factory=list)

class SessionToolRuntime:
    """Mutable runtime shared by all session tools."""

    def __init__(
        self,
        *,
        state: SessionState,
        verbose: bool = False,
        event_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        self.state = state
        self.verbose = bool(verbose)
        self._event_callback = event_callback

    def debug(self, message: str) -> None:
        if not self.verbose:
            return
        print(f"[dj-agents][debug] {message}")

    def emit_event(self, event_type: str, **payload: Any) -> None:
        if self._event_callback is None:
            return
        event: Dict[str, Any] = {
            "type": event_type,
            "timestamp": datetime.utcnow().isoformat(timespec="milliseconds") + "Z",
        }
        event.update(payload)
        try:
            self._event_callback(event)
        except Exception as exc:
            _logger.debug("event_callback failed: %s", exc)
            return

    def invoke_tool(
        self,
        tool_name: str,
        args: Dict[str, Any],
        fn: Callable[[], Dict[str, Any]],
    ) -> Dict[str, Any]:
        call_id = f"tool_{uuid4().hex[:10]}"
        self.emit_event(
            "tool_start",
            tool=tool_name,
            call_id=call_id,
            args=args,
        )
        try:
            payload = fn()
        except Exception as exc:
            self.emit_event(
                "tool_end",
                tool=tool_name,
                call_id=call_id,
                ok=False,
                error_type="exception",
                summary=str(exc),
            )
            raise

        ok = True
        error_type = None
        summary = ""
        result_preview = to_event_result_preview(payload)
        failure_preview = ""
        if isinstance(payload, dict):
            ok = bool(payload.get("ok", True))
            error_type = str(payload.get("error_type", "")).strip() or None
            summary = str(payload.get("message", "")).strip()
            failure_preview = self._build_failure_preview(payload, max_chars=320) if not ok else ""
            if not summary and not ok:
                summary = str(payload.get("stderr", "")).strip() or str(payload.get("stdout", "")).strip()
                summary = summary[:240]

        self.emit_event(
            "tool_end",
            tool=tool_name,
            call_id=call_id,
            ok=ok,
            error_type=error_type,
            summary=summary,
            failure_preview=failure_preview,
            result_preview=result_preview,
        )
        return payload

    @staticmethod
    def _build_failure_preview(payload: Dict[str, Any], *, max_chars: int = 320) -> str:
        direct = str(payload.get("failure_preview", "")).strip()
        if direct:
            return truncate_text(direct, limit=max_chars)

        validation_errors = payload.get("validation_errors")
        if isinstance(validation_errors, list):
            details = [str(item).strip() for item in validation_errors if str(item).strip()]
            if details:
                return truncate_text(
                    "validation_errors: " + "; ".join(details[:3]),
                    limit=max_chars,
                )

        error_message = str(payload.get("error_message", "")).strip()
        if error_message:
            return truncate_text(error_message, limit=max_chars)

        stderr = str(payload.get("stderr", "")).strip()
        if stderr:
            return truncate_text(f"stderr: {stderr}", limit=max_chars)

        stdout = str(payload.get("stdout", "")).strip()
        if stdout:
            return truncate_text(f"stdout: {stdout}", limit=max_chars)

        message = str(payload.get("message", "")).strip()
        if message:
            return truncate_text(message, limit=max_chars)

        error_type = str(payload.get("error_type", "")).strip()
        if error_type:
            return truncate_text(error_type, limit=max_chars)

        return ""

    def invoke_text_tool(
        self,
        tool_name: str,
        args: Dict[str, Any],
        fn: Callable[[], Dict[str, Any]],
    ):
        return to_text_response(self.invoke_tool(tool_name, args, fn))

    def context_payload(self) -> Dict[str, Any]:
        draft = self.state.draft_plan if isinstance(self.state.draft_plan, dict) else None
        retrieval = self.state.last_retrieval if isinstance(self.state.last_retrieval, dict) else {}
        retrieval_candidates = retrieval.get("candidate_names", [])
        if not isinstance(retrieval_candidates, list):
            retrieval_candidates = []
        dataset_spec = self.state.dataset_spec if isinstance(self.state.dataset_spec, dict) else {}
        process_spec = self.state.process_spec if isinstance(self.state.process_spec, dict) else {}
        system_spec = self.state.system_spec if isinstance(self.state.system_spec, dict) else {}
        return {
            "dataset_path": self.state.dataset_path,
            "export_path": self.state.export_path,
            "plan_path": self.state.plan_path,
            "plan_intent": self.state.plan_intent,
            "custom_operator_paths": list(self.state.custom_operator_paths),
            "has_dataset_spec": bool(dataset_spec),
            "dataset_spec_modality": str(((dataset_spec.get("binding") or {}).get("modality", ""))).strip() or None,
            "has_process_spec": bool(process_spec),
            "process_operator_count": len(process_spec.get("operators", [])) if isinstance(process_spec.get("operators", []), list) else 0,
            "has_system_spec": bool(system_spec),
            "draft_plan_id": str((draft or {}).get("plan_id", "")).strip() or None,
            "draft_modality": str((draft or {}).get("modality", "")).strip() or None,
            "draft_operator_count": len((draft or {}).get("operators", [])) if isinstance((draft or {}).get("operators"), list) else 0,
            "draft_plan_path_hint": self.state.draft_plan_path_hint,
            "last_retrieval_intent": str(retrieval.get("intent", "")).strip() or None,
            "last_retrieval_candidate_count": len(retrieval_candidates),
            "last_inspected_dataset": self.state.last_inspected_dataset,
            "has_dataset_profile": bool(self.state.last_dataset_profile),
        }

    def storage_root(self) -> Path:
        root = str(self.state.working_dir or "./.djx").strip() or "./.djx"
        return Path(root).expanduser()

    def next_session_plan_path(self) -> str:
        session_dir = self.storage_root() / "session_plans"
        session_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        return str(session_dir / f"session_plan_{ts}.yaml")

    def load_plan_dict(self, plan_path: str) -> Optional[Dict[str, Any]]:
        try:
            data = yaml.safe_load(Path(plan_path).expanduser().read_text(encoding="utf-8"))
        except Exception as exc:
            _logger.debug("load_plan_dict failed for %s: %s", plan_path, exc)
            return None
        return data if isinstance(data, dict) else None

    def load_plan_model(self, plan_path: str) -> Optional[PlanModel]:
        data = self.load_plan_dict(plan_path)
        if not isinstance(data, dict):
            return None
        try:
            return PlanModel.from_dict(data)
        except Exception as exc:
            _logger.debug("load_plan_model failed for %s: %s", plan_path, exc)
            return None

    @staticmethod
    def looks_like_plan_id(value: str) -> bool:
        token = str(value or "").strip()
        if not token:
            return False
        if "/" in token or "\\" in token:
            return False
        return token.startswith("plan_")

    def find_saved_plan_path_by_plan_id(self, plan_id: str) -> Optional[str]:
        token = str(plan_id or "").strip()
        if not token:
            return None

        root = self.storage_root()
        candidates: List[Path] = []
        if self.state.plan_path:
            candidates.append(Path(self.state.plan_path).expanduser())
        for base_dir in (root / "session_plans", root / "recipes"):
            if base_dir.exists():
                candidates.extend(sorted(base_dir.glob("*.yaml")))

        seen: set[str] = set()
        for path in candidates:
            path_str = str(path)
            if path_str in seen:
                continue
            seen.add(path_str)
            model = self.load_plan_model(path_str)
            if model is None:
                continue
            if str(model.plan_id).strip() == token:
                return path_str
        return None

    def current_draft_plan_model(self) -> Optional[PlanModel]:
        payload = self.state.draft_plan
        if not isinstance(payload, dict):
            return None
        try:
            return PlanModel.from_dict(payload)
        except Exception as exc:
            _logger.debug("current_draft_plan_model failed: %s", exc)
            return None


__all__ = [
    "SessionState",
    "SessionToolRuntime",
    "normalize_line_idx",
    "parse_line_ranges",
    "run_interruptible_subprocess",
    "short_log",
    "to_bool",
    "to_int",
    "to_string_list",
    "to_text_response",
    "truncate_text",
]
