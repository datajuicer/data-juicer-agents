# -*- coding: utf-8 -*-
"""Runtime primitives shared by session tools."""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

import yaml

from data_juicer_agents.tools.planner import PlanModel


@dataclass
class SessionState:
    dataset_path: Optional[str] = None
    export_path: Optional[str] = None
    working_dir: str = "./.djx"
    plan_path: Optional[str] = None
    custom_operator_paths: List[str] = field(default_factory=list)
    draft_plan: Optional[Dict[str, Any]] = None
    draft_plan_path_hint: Optional[str] = None
    last_retrieval: Dict[str, Any] = field(default_factory=dict)
    last_inspected_dataset: Optional[str] = None
    last_dataset_profile: Dict[str, Any] = field(default_factory=dict)
    history: List[Dict[str, str]] = field(default_factory=list)


def to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def to_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def to_string_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        if raw.startswith("["):
            try:
                data = json.loads(raw)
                if isinstance(data, list):
                    return [str(item).strip() for item in data if str(item).strip()]
            except Exception:
                pass
        return [part.strip() for part in raw.split(",") if part.strip()]
    return []


def truncate_text(text: str, limit: int = 12000) -> str:
    if len(text) <= limit:
        return text
    keep = max(limit - 80, 0)
    return text[:keep] + f"\n... [truncated {len(text) - keep} chars]"


def short_log(text: str, max_lines: int = 30, max_chars: int = 6000) -> str:
    if not text:
        return ""
    lines = text.splitlines()
    tail = lines[-max_lines:]
    merged = "\n".join(tail)
    if len(merged) > max_chars:
        return merged[-max_chars:]
    return merged


def parse_line_ranges(ranges: Any) -> tuple[list[int] | None, str | None]:
    if ranges is None:
        return None, None
    if isinstance(ranges, list) and len(ranges) == 2 and all(isinstance(i, int) for i in ranges):
        return [int(ranges[0]), int(ranges[1])], None
    if isinstance(ranges, str):
        raw = ranges.strip()
        if not raw:
            return None, None
        range_match = re.match(r"^\s*(-?\d+)\s*[-,:]\s*(-?\d+)\s*$", raw)
        if range_match:
            return [int(range_match.group(1)), int(range_match.group(2))], None
        try:
            data = json.loads(raw)
        except Exception:
            return None, "ranges must be a JSON array like [start, end]"
        if isinstance(data, list) and len(data) == 2 and all(isinstance(i, int) for i in data):
            return [int(data[0]), int(data[1])], None
        return None, "ranges must be two integers [start, end]"
    return None, "ranges must be null, [start, end], or JSON string of that list"


def normalize_line_idx(idx: int, total: int) -> int:
    if idx < 0:
        return total + idx + 1
    return idx


def to_event_result_preview(value: Any, max_chars: int = 6000) -> str:
    if value is None:
        return ""
    try:
        rendered = json.dumps(value, ensure_ascii=False, indent=2, default=str)
    except Exception:
        rendered = str(value)
    return truncate_text(rendered, limit=max_chars).strip()


def to_text_response(payload: Dict[str, Any]):
    from agentscope.message import TextBlock
    from agentscope.tool import ToolResponse

    return ToolResponse(
        metadata={"ok": True},
        content=[TextBlock(type="text", text=json.dumps(payload, ensure_ascii=False))],
    )


def run_interruptible_subprocess(
    command: Any,
    *,
    timeout_sec: int,
    shell: bool,
) -> Dict[str, Any]:
    proc = subprocess.Popen(
        command,
        shell=shell,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    deadline = time.monotonic() + float(timeout_sec)
    try:
        while True:
            rc = proc.poll()
            if rc is not None:
                out, err = proc.communicate()
                return {
                    "ok": int(rc) == 0,
                    "returncode": int(rc),
                    "stdout": truncate_text(out or "", 8000),
                    "stderr": truncate_text(err or "", 8000),
                    "message": f"process finished with returncode={int(rc)}",
                }

            if time.monotonic() >= deadline:
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except Exception:
                    pass
                try:
                    proc.wait(timeout=2)
                except Exception:
                    pass
                if proc.poll() is None:
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except Exception:
                        pass
                    try:
                        proc.kill()
                    except Exception:
                        pass
                out, err = proc.communicate(timeout=2)
                return {
                    "ok": False,
                    "error_type": "timeout",
                    "returncode": -1,
                    "stdout": truncate_text(out or "", 8000),
                    "stderr": truncate_text((err or "").strip(), 8000),
                    "message": f"process timeout after {timeout_sec}s",
                }
            time.sleep(0.1)
    except Exception as exc:
        return {
            "ok": False,
            "error_type": "execution_failed",
            "returncode": -1,
            "stdout": "",
            "stderr": "",
            "message": f"process execution failed: {exc}",
        }


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
        except Exception:
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
        if isinstance(payload, dict):
            ok = bool(payload.get("ok", True))
            error_type = str(payload.get("error_type", "")).strip() or None
            summary = str(payload.get("message", "")).strip()
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
            result_preview=result_preview,
        )
        return payload

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
        return {
            "dataset_path": self.state.dataset_path,
            "export_path": self.state.export_path,
            "plan_path": self.state.plan_path,
            "custom_operator_paths": list(self.state.custom_operator_paths),
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
        except Exception:
            return None
        return data if isinstance(data, dict) else None

    def load_plan_model(self, plan_path: str) -> Optional[PlanModel]:
        data = self.load_plan_dict(plan_path)
        if not isinstance(data, dict):
            return None
        try:
            return PlanModel.from_dict(data)
        except Exception:
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
        except Exception:
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
