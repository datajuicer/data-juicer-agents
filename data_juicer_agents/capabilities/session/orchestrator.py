# -*- coding: utf-8 -*-
"""Session agent orchestration for unified `dj-agents` entry."""

from __future__ import annotations

import asyncio
import concurrent.futures
import contextlib
import io
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional, Tuple
from uuid import uuid4

import yaml

from data_juicer_agents.commands.apply_cmd import run_apply
from data_juicer_agents.commands.plan_cmd import execute_plan
from data_juicer_agents.capabilities.plan.service import (
    PlanUseCase,
    PlanningMode,
    default_workflows_dir,
)
from data_juicer_agents.capabilities.plan.validation import PlanValidator
from data_juicer_agents.capabilities.dev.service import DevUseCase
from data_juicer_agents.capabilities.plan.schema import PlanModel
from data_juicer_agents.capabilities.trace.repository import TraceStore
from data_juicer_agents.tools.dataset_probe import inspect_dataset_schema
from data_juicer_agents.tools.op_manager.retrieval_service import (
    extract_candidate_names,
    retrieve_operator_candidates,
)


_SESSION_MODEL = "qwen3-max-2026-01-23"
_RUN_ID_RE = re.compile(r"Run ID:\s*([A-Za-z0-9._:-]+)")
_LEADING_THINK_BLOCK_RE = re.compile(
    r"^\s*<think>\s*(.*?)\s*</think>\s*",
    re.DOTALL | re.IGNORECASE,
)
_LEADING_THINK_CLOSE_RE = re.compile(r"^\s*(?:</think>\s*)+", re.IGNORECASE)
_THINK_BLOCK_RE = re.compile(r"<think>\s*(.*?)\s*</think>", re.DOTALL | re.IGNORECASE)
_REFLECTIVE_TAIL_MARKERS = (
    re.compile(r"(?im)^\s*[·•\-\*]?\s*the user (requested|asked)\b"),
    re.compile(r"(?im)^\s*[·•\-\*]?\s*the task has been (successfully )?(completed|finished)\b"),
    re.compile(r"(?im)^\s*[·•\-\*]?\s*i (have )?(successfully )?(completed|finished)\b"),
    re.compile(r"(?im)^\s*[·•\-\*]?\s*task (is )?(completed|finished)\b"),
    re.compile(r"(?im)^\s*[·•\-\*]?\s*here (is|are) (what )?i (did|have done)\b"),
    re.compile(r"(?im)^\s*[·•\-\*]?\s*here'?s (a )?summary\b"),
    re.compile(r"(?m)^\s*[·•\-\*]?\s*用户(要求|请求|希望)"),
    re.compile(r"(?m)^\s*[·•\-\*]?\s*下面是.*(步骤|总结)"),
)
_REFLECTIVE_LINE_MARKERS = (
    re.compile(r"(?i)^\s*[·•\-\*]?\s*the user (requested|asked)\b"),
    re.compile(r"(?i)^\s*[·•\-\*]?\s*the task has been (successfully )?(completed|finished)\b"),
    re.compile(r"(?i)^\s*[·•\-\*]?\s*i (have )?successfully\b"),
    re.compile(r"(?i)^\s*[·•\-\*]?\s*here (is|are) (what )?i (did|have done)\b"),
    re.compile(r"(?i)^\s*[·•\-\*]?\s*here'?s (a )?summary\b"),
    re.compile(r"^\s*[·•\-\*]?\s*用户(要求|请求|希望)"),
)

_HELP_TEXT = (
    "I can help you orchestrate Data-Juicer workflows conversationally.\n"
    "Describe your request in natural language, for example:\n"
    "- I want a RAG cleaning workflow with input data/demo-dataset.jsonl\n"
    "- Show me the trace from the most recent run\n"
    "- Existing operators do not satisfy this requirement. Help me generate a new operator\n"
    "Available atomic capabilities: retrieve / plan(chain) / apply / trace / dev.\n"
    "Control commands: help / exit / cancel."
)


@dataclass
class SessionState:
    dataset_path: Optional[str] = None
    export_path: Optional[str] = None
    working_dir: str = "./.djx"
    plan_path: Optional[str] = None
    run_id: Optional[str] = None
    custom_operator_paths: List[str] = field(default_factory=list)
    draft_plan: Optional[Dict[str, Any]] = None
    draft_plan_path_hint: Optional[str] = None
    last_retrieval: Dict[str, Any] = field(default_factory=dict)
    last_inspected_dataset: Optional[str] = None
    last_dataset_profile: Dict[str, Any] = field(default_factory=dict)
    history: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class SessionReply:
    text: str
    thinking: str = ""
    stop: bool = False
    interrupted: bool = False


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _to_bool(value: Any, default: bool = False) -> bool:
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


def _to_string_list(value: Any) -> List[str]:
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


def _coerce_block_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("thinking", "text", "reasoning", "content", "output"):
            content = _coerce_block_text(value.get(key))
            if content:
                return content
        return ""
    if isinstance(value, list):
        parts: List[str] = []
        for item in value:
            part = _coerce_block_text(item)
            if part:
                parts.append(part)
        return "\n".join(parts).strip()
    return str(value).strip()


def _parse_line_ranges(ranges: Any) -> tuple[list[int] | None, str | None]:
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


def _normalize_line_idx(idx: int, total: int) -> int:
    if idx < 0:
        return total + idx + 1
    return idx


def _truncate_text(text: str, limit: int = 12000) -> str:
    if len(text) <= limit:
        return text
    keep = max(limit - 80, 0)
    return text[:keep] + f"\n... [truncated {len(text) - keep} chars]"


def _short_log(text: str, max_lines: int = 30, max_chars: int = 6000) -> str:
    if not text:
        return ""
    lines = text.splitlines()
    tail = lines[-max_lines:]
    merged = "\n".join(tail)
    if len(merged) > max_chars:
        return merged[-max_chars:]
    return merged


def _to_event_result_preview(value: Any, max_chars: int = 6000) -> str:
    if value is None:
        return ""
    try:
        rendered = json.dumps(value, ensure_ascii=False, indent=2, default=str)
    except Exception:
        rendered = str(value)
    return _truncate_text(rendered, limit=max_chars).strip()


def _strip_reflective_tail(text: str) -> tuple[str, str]:
    """Strip reflective/meta tail accidentally emitted in final answer text.

    Some model/provider paths occasionally append a self-referential recap
    (for example, "The user requested ...") after a complete final answer.
    Keep the user-facing answer in `text`, and return stripped tail separately.
    """
    body = str(text or "").strip()
    if not body:
        return "", ""

    # Phase 1: drop reflective lead-in lines when there is additional content.
    # This handles model outputs like:
    # "The user requested ... I successfully: ...",
    # while preserving the actual task/result lines.
    lines = body.splitlines()
    kept_lines: List[str] = []
    removed_lines: List[str] = []
    leading_done = False
    for line in lines:
        stripped = line.strip()
        if not leading_done:
            if not stripped:
                kept_lines.append(line)
                continue
            if any(pattern.match(stripped) for pattern in _REFLECTIVE_LINE_MARKERS):
                removed_lines.append(line)
                continue
            leading_done = True
        kept_lines.append(line)
    if removed_lines and any(str(row).strip() for row in kept_lines):
        cleaned = "\n".join(kept_lines).strip()
        removed = "\n".join(removed_lines).strip()
        if cleaned:
            return cleaned, removed

    for pattern in _REFLECTIVE_TAIL_MARKERS:
        matched = pattern.search(body)
        if not matched:
            continue
        idx = int(matched.start())
        if idx <= 0:
            continue
        # Guardrail: only trim when we already have at least one prior line.
        if "\n" not in body[:idx]:
            continue
        head = body[:idx].rstrip()
        tail = body[idx:].strip()
        if not head or len(tail) < 40:
            continue
        return head, tail
    return body, ""


def _sanitize_thinking_text(text: str) -> str:
    """Clean reasoning text shown in TUI/frontend.

    If reasoning starts with reflective recap markers, drop the whole block.
    This avoids duplicated "task completed / summary" text rendered as thinking.
    """
    body = str(text or "").strip()
    if not body:
        return ""

    first_nonempty = ""
    for line in body.splitlines():
        stripped = line.strip()
        if stripped:
            first_nonempty = stripped
            break
    if first_nonempty and any(pattern.match(first_nonempty) for pattern in _REFLECTIVE_LINE_MARKERS):
        return ""

    cleaned, _ = _strip_reflective_tail(body)
    return cleaned.strip()


def _to_text_response(payload: Dict[str, Any]):
    from agentscope.message import TextBlock
    from agentscope.tool import ToolResponse

    return ToolResponse(
        metadata={"ok": True},
        content=[TextBlock(type="text", text=json.dumps(payload, ensure_ascii=False))],
    )


class DJSessionAgent:
    """Session agent that orchestrates djx atomic commands via ReAct tools."""

    def __init__(
        self,
        use_llm_router: bool = True,
        dataset_path: Optional[str] = None,
        export_path: Optional[str] = None,
        working_dir: Optional[str] = None,
        verbose: bool = False,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        planner_model: Optional[str] = None,
        thinking: Optional[bool] = None,
        event_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        self.use_llm_router = use_llm_router
        self.verbose = bool(verbose)
        self.state = SessionState(
            dataset_path=dataset_path,
            export_path=export_path,
            working_dir=(str(working_dir).strip() if working_dir else "./.djx"),
        )
        self._react_agent = None
        self._api_key = str(api_key).strip() if api_key else None
        self._base_url = str(base_url).strip() if base_url else None
        self._model_name = str(model_name).strip() if model_name else None
        self._planner_model = str(planner_model).strip() if planner_model else None
        self._thinking = thinking if isinstance(thinking, bool) else None
        self._default_llm_review_enabled = _to_bool(
            os.environ.get("DJA_ENABLE_LLM_REVIEW"),
            False,
        )
        self._event_callback = event_callback
        self._last_reply_thinking = ""
        self._reasoning_step = 0
        self._interrupt_lock = threading.RLock()
        self._active_react_loop: asyncio.AbstractEventLoop | None = None
        self._active_react_inflight = False

        if self.use_llm_router:
            try:
                self._react_agent = self._build_react_agent()
            except Exception as exc:
                raise RuntimeError(
                    f"Failed to initialize dj-agents ReAct session: {exc}"
                ) from exc

    def _debug(self, message: str) -> None:
        if not self.verbose:
            return
        print(f"[dj-agents][debug] {message}")

    def _set_active_react_context(self, loop: asyncio.AbstractEventLoop) -> None:
        with self._interrupt_lock:
            self._active_react_loop = loop
            self._active_react_inflight = True

    def _clear_active_react_context(self, loop: asyncio.AbstractEventLoop) -> None:
        with self._interrupt_lock:
            if self._active_react_loop is loop:
                self._active_react_loop = None
            self._active_react_inflight = False

    def request_interrupt(self) -> bool:
        if self._react_agent is None:
            return False
        with self._interrupt_lock:
            loop = self._active_react_loop
            inflight = self._active_react_inflight
        if not inflight or loop is None or loop.is_closed():
            return False
        try:
            fut = asyncio.run_coroutine_threadsafe(self._react_agent.interrupt(), loop)
            try:
                fut.result(timeout=0.2)
            except concurrent.futures.TimeoutError:
                # Scheduled successfully; cancellation can finish asynchronously.
                pass
        except Exception as exc:
            self._debug(f"request_interrupt failed: {exc}")
            return False
        return True

    def _emit_event(self, event_type: str, **payload: Any) -> None:
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
            # Event callbacks are observational and must not break agent flow.
            return

    def _session_sys_prompt(self) -> str:
        working_dir = self.state.working_dir or "./.djx"
        return (
            "You are a Data-Juicer session orchestrator for data engineers.\n"
            "Default interaction is natural language, not command syntax.\n"
            "Available tools are djx atomic capabilities. Use tools for actionable requests.\n"
            f"You must only read, write, create, or execute files/commands inside the current working directory: {working_dir}.\n"
            "If the user explicitly specifies a different working directory, treat that directory as the new working directory for this session first, "
            "then keep all later file and command operations inside it.\n"
            "If a requested path is outside the current working directory, do not operate on it until the user explicitly changes the working directory.\n"
            "For planning requests, prefer this chain: "
            "inspect_dataset -> retrieve_operators -> plan_retrieve_candidates (optional) -> plan_generate -> plan_validate (draft) -> plan_save.\n"
            "Before calling plan_generate, synthesize a grounded_intent that merges: "
            "(a) user goal, (b) inspect_dataset findings (modality, candidate keys, sample stats), "
            "(c) retrieve_operators/plan_retrieve_candidates outputs (canonical operator names).\n"
            "Pass grounded_intent as plan_generate.intent instead of the raw user utterance.\n"
            "In grounded_intent, explicitly state target field(s), threshold/unit constraints, and preferred canonical operators.\n"
            "Never ignore inspect/retrieve results when forming plan_generate intent.\n"
            "For concrete dataset transformation requests (for example filtering/cleaning/dedup), "
            "you must execute tools instead of only providing reasoning.\n"
            "Do not end the turn with only planned tool calls; execute the planned tools and then summarize results.\n"
            "If plan_generate fails, inspect the returned errors/warnings and retry plan_generate with corrected constraints "
            "(for example canonical operator names, workflow intent, or field hints) before asking user follow-up questions.\n"
            "You should usually retry plan_generate at least once when failure is recoverable.\n"
            "Use view_text_file/write_text_file/insert_text_file for file operations when needed.\n"
            "Use execute_shell_command/execute_python_code for diagnostic or programmatic tasks when needed.\n"
            "When required fields are missing, ask concise follow-up questions.\n"
            "Before running apply_recipe, ask user for explicit confirmation.\n"
            "Call trace_run only when user explicitly asks for trace/log/run history, "
            "or when a run_id already exists and trace is needed to answer the user.\n"
            "After completing any meaningful stage of work, always send a final user-facing reply for that turn.\n"
            "In that reply, briefly summarize what you already executed, not just what you planned.\n"
            "If any new files were saved or written, explain what each file is for and include its path.\n"
            "Infer the user's likely next intent and end with a proactive suggestion in this style: "
            "'If you want ..., tell me ..., and I will ...'.\n"
            "If user says help, summarize capabilities and examples.\n"
            "If user says exit/quit, respond with a short goodbye.\n"
            "Always reflect tool results, including failures and next steps.\n"
            "Do not append meta narration like 'The user requested ...' after final answer.\n"
            "Respond in the same language as the user."
        )

    def _invoke_tool_with_event(
        self,
        tool_name: str,
        args: Dict[str, Any],
        fn: Callable[[], Dict[str, Any]],
    ) -> Dict[str, Any]:
        call_id = f"tool_{uuid4().hex[:10]}"
        self._emit_event(
            "tool_start",
            tool=tool_name,
            call_id=call_id,
            args=args,
        )
        try:
            payload = fn()
        except Exception as exc:
            self._emit_event(
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
        result_preview = _to_event_result_preview(payload)
        if isinstance(payload, dict):
            ok = bool(payload.get("ok", True))
            error_type = str(payload.get("error_type", "")).strip() or None
            summary = str(payload.get("message", "")).strip()
            if not summary and not ok:
                summary = str(payload.get("stderr", "")).strip() or str(payload.get("stdout", "")).strip()
                summary = summary[:240]

        self._emit_event(
            "tool_end",
            tool=tool_name,
            call_id=call_id,
            ok=ok,
            error_type=error_type,
            summary=summary,
            result_preview=result_preview,
        )
        return payload

    def _context_payload(self) -> Dict[str, Any]:
        draft = self.state.draft_plan if isinstance(self.state.draft_plan, dict) else None
        retrieval = self.state.last_retrieval if isinstance(self.state.last_retrieval, dict) else {}
        retrieval_candidates = retrieval.get("candidate_names", [])
        if not isinstance(retrieval_candidates, list):
            retrieval_candidates = []
        return {
            "dataset_path": self.state.dataset_path,
            "export_path": self.state.export_path,
            "plan_path": self.state.plan_path,
            "run_id": self.state.run_id,
            "custom_operator_paths": list(self.state.custom_operator_paths),
            "draft_plan_id": str((draft or {}).get("plan_id", "")).strip() or None,
            "draft_workflow": str((draft or {}).get("workflow", "")).strip() or None,
            "draft_operator_count": len((draft or {}).get("operators", [])) if isinstance((draft or {}).get("operators"), list) else 0,
            "draft_plan_path_hint": self.state.draft_plan_path_hint,
            "last_retrieval_intent": str(retrieval.get("intent", "")).strip() or None,
            "last_retrieval_candidate_count": len(retrieval_candidates),
            "last_inspected_dataset": self.state.last_inspected_dataset,
            "has_dataset_profile": bool(self.state.last_dataset_profile),
        }

    def _run_command(self, fn, args: Any) -> Tuple[int, str, str]:
        out = io.StringIO()
        err = io.StringIO()
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = fn(args)
            return int(code), out.getvalue(), err.getvalue()
        except Exception as exc:
            return 2, out.getvalue(), f"{err.getvalue()}\n{exc}".strip()

    def _next_session_plan_path(self) -> str:
        session_dir = Path(".djx") / "session_plans"
        session_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        return str(session_dir / f"session_plan_{ts}.yaml")

    def _load_plan_dict(self, plan_path: str) -> Optional[Dict[str, Any]]:
        try:
            data = yaml.safe_load(Path(plan_path).read_text(encoding="utf-8"))
        except Exception:
            return None
        return data if isinstance(data, dict) else None

    def _load_plan_id(self, plan_path: str) -> Optional[str]:
        data = self._load_plan_dict(plan_path)
        if not data:
            return None
        plan_id = str(data.get("plan_id", "")).strip()
        return plan_id or None

    def _load_plan_model(self, plan_path: str) -> Optional[PlanModel]:
        data = self._load_plan_dict(plan_path)
        if not isinstance(data, dict):
            return None
        try:
            return PlanModel.from_dict(data)
        except Exception:
            return None

    @staticmethod
    def _looks_like_plan_id(value: str) -> bool:
        token = str(value or "").strip()
        if not token:
            return False
        if "/" in token or "\\" in token:
            return False
        return token.startswith("plan_")

    def _find_saved_plan_path_by_plan_id(self, plan_id: str) -> Optional[str]:
        token = str(plan_id or "").strip()
        if not token:
            return None

        candidates: List[Path] = []
        if self.state.plan_path:
            candidates.append(Path(self.state.plan_path))
        for base_dir in (Path(".djx") / "session_plans", Path(".djx") / "recipes"):
            if base_dir.exists():
                candidates.extend(sorted(base_dir.glob("*.yaml")))

        seen: set[str] = set()
        for path in candidates:
            path_str = str(path)
            if path_str in seen:
                continue
            seen.add(path_str)
            model = self._load_plan_model(path_str)
            if model is None:
                continue
            if str(model.plan_id).strip() == token:
                return path_str
        return None

    def _current_draft_plan_model(self) -> Optional[PlanModel]:
        payload = self.state.draft_plan
        if not isinstance(payload, dict):
            return None
        try:
            return PlanModel.from_dict(payload)
        except Exception:
            return None

    def _new_planner_usecase(self, planning_mode: PlanningMode) -> PlanUseCase:
        return PlanUseCase(
            default_workflows_dir(),
            planning_mode=planning_mode,
            planner_model_name=self._planner_model,
            llm_api_key=self._api_key,
            llm_base_url=self._base_url,
            llm_thinking=self._thinking,
        )

    def _cached_retrieval_candidates(self, intent: str, dataset_path: str) -> Optional[List[Any]]:
        retrieval = self.state.last_retrieval
        if not isinstance(retrieval, dict):
            return None
        cached_intent = str(retrieval.get("intent", "")).strip()
        cached_dataset = str(retrieval.get("dataset_path", "")).strip()
        if cached_intent != str(intent).strip():
            return None
        if cached_dataset != str(dataset_path).strip():
            return None
        payload = retrieval.get("payload")
        if isinstance(payload, dict):
            candidates = payload.get("candidates")
            if isinstance(candidates, list):
                return list(candidates)
        names = retrieval.get("candidate_names")
        if not isinstance(names, list):
            return None
        return [str(item).strip() for item in names if str(item).strip()]

    def _extract_run_id(self, text: str) -> Optional[str]:
        match = _RUN_ID_RE.search(text or "")
        if not match:
            return None
        run_id = match.group(1).strip()
        return run_id or None

    def _build_toolkit(self):
        from agentscope.tool import Toolkit

        toolkit = Toolkit()

        def get_session_context() -> Any:
            return _to_text_response(
                self._invoke_tool_with_event(
                    "get_session_context",
                    {},
                    lambda: self.tool_get_context(),
                )
            )

        def set_session_context(
            dataset_path: str = "",
            export_path: str = "",
            plan_path: str = "",
            run_id: str = "",
            custom_operator_paths: str = "",
        ) -> Any:
            return _to_text_response(
                self._invoke_tool_with_event(
                    "set_session_context",
                    {
                        "dataset_path": dataset_path,
                        "export_path": export_path,
                        "plan_path": plan_path,
                        "run_id": run_id,
                    },
                    lambda: self.tool_set_context(
                        dataset_path=dataset_path,
                        export_path=export_path,
                        plan_path=plan_path,
                        run_id=run_id,
                        custom_operator_paths=custom_operator_paths,
                    ),
                )
            )

        def inspect_dataset(
            dataset_path: str = "",
            sample_size: int = 20,
        ) -> Any:
            return _to_text_response(
                self._invoke_tool_with_event(
                    "inspect_dataset",
                    {
                        "dataset_path": dataset_path,
                        "sample_size": sample_size,
                    },
                    lambda: self.tool_inspect_dataset(
                        dataset_path=dataset_path,
                        sample_size=sample_size,
                    ),
                )
            )

        def retrieve_operators(
            intent: str,
            top_k: int = 10,
            mode: str = "auto",
            dataset_path: str = "",
        ) -> Any:
            return _to_text_response(
                self._invoke_tool_with_event(
                    "retrieve_operators",
                    {
                        "intent": intent,
                        "top_k": top_k,
                        "mode": mode,
                        "dataset_path": dataset_path,
                    },
                    lambda: self.tool_retrieve(
                        intent=intent,
                        top_k=top_k,
                        mode=mode,
                        dataset_path=dataset_path,
                    ),
                )
            )

        def plan_retrieve_candidates(
            intent: str,
            top_k: int = 12,
            mode: str = "auto",
            dataset_path: str = "",
            remember: bool = True,
        ) -> Any:
            return _to_text_response(
                self._invoke_tool_with_event(
                    "plan_retrieve_candidates",
                    {
                        "intent": intent,
                        "top_k": top_k,
                        "mode": mode,
                        "dataset_path": dataset_path,
                        "remember": remember,
                    },
                    lambda: self.tool_plan_retrieve_candidates(
                        intent=intent,
                        top_k=top_k,
                        mode=mode,
                        dataset_path=dataset_path,
                        remember=remember,
                    ),
                )
            )

        def plan_generate(
            intent: str,
            dataset_path: str = "",
            export_path: str = "",
            output_path: str = "",
            base_plan: str = "",
            from_run_id: str = "",
            custom_operator_paths: str = "",
            from_template: str = "",
            template_retrieve: bool = False,
            use_cached_retrieval: bool = True,
            planning_mode: str = "auto",
            include_llm_review: bool | None = None,
        ) -> Any:
            return _to_text_response(
                self._invoke_tool_with_event(
                    "plan_generate",
                    {
                        "intent": intent,
                        "dataset_path": dataset_path,
                        "export_path": export_path,
                        "output_path": output_path,
                        "base_plan": base_plan,
                        "from_run_id": from_run_id,
                        "from_template": from_template,
                        "template_retrieve": template_retrieve,
                        "use_cached_retrieval": use_cached_retrieval,
                        "planning_mode": planning_mode,
                        "include_llm_review": include_llm_review,
                    },
                    lambda: self.tool_plan_generate(
                        intent=intent,
                        dataset_path=dataset_path,
                        export_path=export_path,
                        output_path=output_path,
                        base_plan=base_plan,
                        from_run_id=from_run_id,
                        custom_operator_paths=custom_operator_paths,
                        from_template=from_template,
                        template_retrieve=template_retrieve,
                        use_cached_retrieval=use_cached_retrieval,
                        planning_mode=planning_mode,
                        include_llm_review=include_llm_review,
                    ),
                )
            )

        def plan_validate(
            plan_path: str = "",
            include_llm_review: bool | None = None,
            use_draft: bool = True,
        ) -> Any:
            return _to_text_response(
                self._invoke_tool_with_event(
                    "plan_validate",
                    {
                        "plan_path": plan_path,
                        "include_llm_review": include_llm_review,
                        "use_draft": use_draft,
                    },
                    lambda: self.tool_plan_validate(
                        plan_path=plan_path,
                        include_llm_review=include_llm_review,
                        use_draft=use_draft,
                    ),
                )
            )

        def plan_save(
            output_path: str = "",
            overwrite: bool = False,
            source_plan_path: str = "",
        ) -> Any:
            return _to_text_response(
                self._invoke_tool_with_event(
                    "plan_save",
                    {
                        "output_path": output_path,
                        "overwrite": overwrite,
                        "source_plan_path": source_plan_path,
                    },
                    lambda: self.tool_plan_save(
                        output_path=output_path,
                        overwrite=overwrite,
                        source_plan_path=source_plan_path,
                    ),
                )
            )

        def apply_recipe(
            plan_path: str = "",
            dry_run: bool = False,
            timeout: int = 300,
            confirm: bool = False,
        ) -> Any:
            return _to_text_response(
                self._invoke_tool_with_event(
                    "apply_recipe",
                    {
                        "plan_path": plan_path,
                        "dry_run": dry_run,
                        "timeout": timeout,
                        "confirm": confirm,
                    },
                    lambda: self.tool_apply(
                        plan_path=plan_path,
                        dry_run=dry_run,
                        timeout=timeout,
                        confirm=confirm,
                    ),
                )
            )

        def trace_run(
            run_id: str = "",
            plan_id: str = "",
            limit: int = 20,
            stats: bool = False,
        ) -> Any:
            return _to_text_response(
                self._invoke_tool_with_event(
                    "trace_run",
                    {
                        "run_id": run_id,
                        "plan_id": plan_id,
                        "limit": limit,
                        "stats": stats,
                    },
                    lambda: self.tool_trace(
                        run_id=run_id,
                        plan_id=plan_id,
                        limit=limit,
                        stats=stats,
                    ),
                )
            )

        def develop_operator(
            intent: str,
            operator_name: str = "",
            output_dir: str = "",
            operator_type: str = "",
            from_retrieve: str = "",
            smoke_check: bool = False,
        ) -> Any:
            return _to_text_response(
                self._invoke_tool_with_event(
                    "develop_operator",
                    {
                        "intent": intent,
                        "operator_name": operator_name,
                        "output_dir": output_dir,
                        "operator_type": operator_type,
                        "from_retrieve": from_retrieve,
                        "smoke_check": smoke_check,
                    },
                    lambda: self.tool_dev(
                        intent=intent,
                        operator_name=operator_name,
                        output_dir=output_dir,
                        operator_type=operator_type,
                        from_retrieve=from_retrieve,
                        smoke_check=smoke_check,
                    ),
                )
            )

        def view_text_file(
            file_path: str,
            ranges: Any = None,
        ) -> Any:
            return _to_text_response(
                self._invoke_tool_with_event(
                    "view_text_file",
                    {
                        "file_path": file_path,
                        "ranges": ranges,
                    },
                    lambda: self.tool_view_text_file(
                        file_path=file_path,
                        ranges=ranges,
                    ),
                )
            )

        def write_text_file(
            file_path: str,
            content: str,
            ranges: Any = None,
        ) -> Any:
            return _to_text_response(
                self._invoke_tool_with_event(
                    "write_text_file",
                    {
                        "file_path": file_path,
                        "ranges": ranges,
                    },
                    lambda: self.tool_write_text_file(
                        file_path=file_path,
                        content=content,
                        ranges=ranges,
                    ),
                )
            )

        def insert_text_file(
            file_path: str,
            content: str,
            line_number: int,
        ) -> Any:
            return _to_text_response(
                self._invoke_tool_with_event(
                    "insert_text_file",
                    {
                        "file_path": file_path,
                        "line_number": line_number,
                    },
                    lambda: self.tool_insert_text_file(
                        file_path=file_path,
                        content=content,
                        line_number=line_number,
                    ),
                )
            )

        def execute_shell_command(
            command: str,
            timeout: int = 120,
        ) -> Any:
            command_text = str(command or "")
            return _to_text_response(
                self._invoke_tool_with_event(
                    "execute_shell_command",
                    {
                        "command": _truncate_text(command_text, limit=500),
                        "timeout": timeout,
                    },
                    lambda: self.tool_execute_shell_command(
                        command=command_text,
                        timeout=timeout,
                    ),
                )
            )

        def execute_python_code(
            code: str,
            timeout: int = 120,
        ) -> Any:
            code_text = str(code or "")
            return _to_text_response(
                self._invoke_tool_with_event(
                    "execute_python_code",
                    {
                        "code": _truncate_text(code_text, limit=800),
                        "timeout": timeout,
                    },
                    lambda: self.tool_execute_python_code(
                        code=code_text,
                        timeout=timeout,
                    ),
                )
            )

        toolkit.register_tool_function(get_session_context)
        toolkit.register_tool_function(set_session_context)
        toolkit.register_tool_function(inspect_dataset)
        toolkit.register_tool_function(retrieve_operators)
        toolkit.register_tool_function(plan_retrieve_candidates)
        toolkit.register_tool_function(plan_generate)
        toolkit.register_tool_function(plan_validate)
        toolkit.register_tool_function(plan_save)
        toolkit.register_tool_function(apply_recipe)
        toolkit.register_tool_function(trace_run)
        toolkit.register_tool_function(develop_operator)
        toolkit.register_tool_function(view_text_file)
        toolkit.register_tool_function(write_text_file)
        toolkit.register_tool_function(insert_text_file)
        toolkit.register_tool_function(execute_shell_command)
        toolkit.register_tool_function(execute_python_code)
        return toolkit

    def _build_react_agent(self):
        from agentscope.agent import ReActAgent
        from agentscope.formatter import OpenAIChatFormatter
        from agentscope.model import OpenAIChatModel

        api_key = self._api_key or os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("MODELSCOPE_API_TOKEN")
        if not api_key:
            raise RuntimeError("Missing API key: set DASHSCOPE_API_KEY or MODELSCOPE_API_TOKEN")

        base_url = self._base_url or os.environ.get(
            "DJA_OPENAI_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        if self._thinking is None:
            thinking_flag = os.environ.get("DJA_LLM_THINKING", "true").lower() in {
                "1",
                "true",
                "yes",
                "on",
            }
        else:
            thinking_flag = bool(self._thinking)
        model_name = self._model_name or os.environ.get("DJA_SESSION_MODEL", _SESSION_MODEL)

        model = OpenAIChatModel(
            model_name=model_name,
            api_key=api_key,
            stream=False,
            client_kwargs={"base_url": base_url},
            generate_kwargs={
                "temperature": 0,
                "extra_body": {"enable_thinking": thinking_flag},
            },
        )
        formatter = OpenAIChatFormatter()
        toolkit = self._build_toolkit()
        agent = ReActAgent(
            name="DJSessionReActAgent",
            sys_prompt=self._session_sys_prompt(),
            model=model,
            formatter=formatter,
            toolkit=toolkit,
            max_iters=10,
            parallel_tool_calls=False,
        )
        self._register_react_hooks(agent)
        agent.set_console_output_enabled(enabled=self.verbose)
        return agent

    def _register_react_hooks(self, react_agent: Any) -> None:
        def _post_reasoning_hook(_agent: Any, kwargs: Dict[str, Any], output: Any) -> Any:
            self._reasoning_step += 1
            payload = self._build_reasoning_event_payload(
                output=output,
                step=self._reasoning_step,
                tool_choice=kwargs.get("tool_choice"),
            )
            if payload:
                self._emit_event("reasoning_step", **payload)
            return None

        react_agent.register_instance_hook(
            "post_reasoning",
            "djx_reasoning_step",
            _post_reasoning_hook,
        )

    @staticmethod
    def _build_reasoning_event_payload(
        output: Any,
        step: int,
        tool_choice: Any = None,
    ) -> Optional[Dict[str, Any]]:
        if output is None or not hasattr(output, "get_content_blocks"):
            return None

        thinking_parts: List[str] = []
        text_parts: List[str] = []
        planned_tools: List[Dict[str, Any]] = []

        try:
            blocks = list(output.get_content_blocks())
        except Exception:
            blocks = []

        for block in blocks:
            if not isinstance(block, dict):
                continue
            block_type = str(block.get("type", "")).strip().lower()
            if block_type in {"thinking", "reasoning"}:
                value = ""
                for key in ("thinking", "text", "reasoning", "content"):
                    value = _coerce_block_text(block.get(key))
                    if value:
                        break
                if value:
                    thinking_parts.append(value)
                continue
            if block_type == "text":
                value = _coerce_block_text(block.get("text"))
                if value:
                    text_parts.append(value)
                continue
            if block_type == "tool_use":
                planned_tools.append(
                    {
                        "id": str(block.get("id", "")).strip(),
                        "name": str(block.get("name", "")).strip(),
                        "input": block.get("input", {}),
                    }
                )

        thinking = "\n\n".join(part for part in thinking_parts if part).strip()
        text_preview = "\n\n".join(part for part in text_parts if part).strip()
        # Some providers leak reflective recap text into intermediate blocks.
        # Keep reasoning/events concise and avoid duplicating final-answer tails.
        thinking = _sanitize_thinking_text(thinking)
        text_preview = _sanitize_thinking_text(text_preview)
        if not thinking and not text_preview and not planned_tools:
            return None

        return {
            "step": int(step),
            "tool_choice": str(tool_choice or "").strip() or None,
            "thinking": thinking,
            "text_preview": text_preview,
            "planned_tools": planned_tools,
            "has_tool_calls": bool(planned_tools),
        }

    @staticmethod
    def _reply_marked_interrupted(reply_msg: Any) -> bool:
        metadata = getattr(reply_msg, "metadata", None)
        if isinstance(metadata, dict) and metadata.get("_is_interrupted"):
            return True
        return False

    async def _react_reply_async(self, message: str) -> tuple[str, bool]:
        from agentscope.message import Msg

        assert self._react_agent is not None
        loop = asyncio.get_running_loop()
        self._set_active_react_context(loop)
        self._reasoning_step = 0
        context = json.dumps(self._context_payload(), ensure_ascii=False)
        prompt = (
            f"user_message: {message}\n"
            f"session_context: {context}\n"
        )
        try:
            # NOTE:
            # Do not redirect stdout/stderr here. redirect_stdout/redirect_stderr
            # mutates process-wide sys.stdout/sys.stderr, which suppresses TUI
            # rendering from the main thread while this worker turn is running.
            reply = await self._react_agent(Msg(name="user", role="user", content=prompt))
            text, thinking = self._extract_reply_text_and_thinking(reply)
            self._last_reply_thinking = thinking
            return text.strip(), self._reply_marked_interrupted(reply)
        finally:
            self._clear_active_react_context(loop)

    @staticmethod
    def _extract_reply_text_and_thinking(reply_msg: Any) -> tuple[str, str]:
        text = ""
        try:
            text = str(reply_msg.get_text_content() or "")
        except Exception:
            text = ""

        thinking_parts: List[str] = []
        try:
            for block in reply_msg.get_content_blocks():
                block_type = str(block.get("type", "")).strip().lower()
                if block_type not in {"thinking", "reasoning"}:
                    continue
                value = ""
                for key in ("thinking", "text", "reasoning", "content"):
                    value = _coerce_block_text(block.get(key))
                    if value:
                        break
                if not value:
                    continue
                thinking_parts.append(value)
        except Exception:
            pass

        thinking = "\n\n".join(part for part in thinking_parts if part).strip()

        # Case 1: explicit <think>...</think> blocks embedded in text payload.
        if "<think>" in text.lower() and "</think>" in text.lower():
            in_text_thinks = [m.group(1).strip() for m in _THINK_BLOCK_RE.finditer(text) if m.group(1).strip()]
            if in_text_thinks and not thinking:
                thinking = "\n\n".join(in_text_thinks).strip()
            text = _THINK_BLOCK_RE.sub("", text)
        else:
            # Case 2: leaked hidden reasoning as "<reasoning...></think><final answer>".
            close_idx = text.lower().rfind("</think>")
            if close_idx >= 0:
                leaked = text[:close_idx].strip()
                if leaked and not thinking:
                    thinking = leaked
                text = text[close_idx + len("</think>") :]

        matched = _LEADING_THINK_BLOCK_RE.match(text)
        if matched:
            think_in_text = matched.group(1).strip()
            if think_in_text and not thinking:
                thinking = think_in_text
            text = text[matched.end() :]

        text = _LEADING_THINK_CLOSE_RE.sub("", text, count=1).strip()
        thinking = _sanitize_thinking_text(thinking)
        text, _reflective_tail = _strip_reflective_tail(text)
        # Drop reflective tail from user-facing output entirely.
        # Do not move it into `thinking`, otherwise TUI still prints it.
        return text, thinking

    def _react_reply(self, message: str) -> tuple[str, bool]:
        try:
            return asyncio.run(self._react_reply_async(message))
        except RuntimeError as exc:
            if "asyncio.run() cannot be called from a running event loop" not in str(exc):
                raise
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(self._react_reply_async(message))
            finally:
                loop.close()

    # ---- Tool implementations exposed to ReAct ----

    def tool_get_context(self) -> Dict[str, Any]:
        self._debug("tool:get_session_context")
        payload = self._context_payload()
        payload["ok"] = True
        return payload

    def tool_set_context(
        self,
        dataset_path: str = "",
        export_path: str = "",
        plan_path: str = "",
        run_id: str = "",
        custom_operator_paths: Any = None,
    ) -> Dict[str, Any]:
        self._debug("tool:set_session_context")
        if str(dataset_path).strip():
            self.state.dataset_path = str(dataset_path).strip()
        if str(export_path).strip():
            self.state.export_path = str(export_path).strip()
        if str(plan_path).strip():
            self.state.plan_path = str(plan_path).strip()
            model = self._load_plan_model(self.state.plan_path)
            if model is not None:
                self.state.draft_plan = model.to_dict()
                self.state.draft_plan_path_hint = self.state.plan_path
        if str(run_id).strip():
            self.state.run_id = str(run_id).strip()

        paths = _to_string_list(custom_operator_paths)
        if paths:
            self.state.custom_operator_paths = paths

        return {
            "ok": True,
            "message": "session context updated",
            "context": self._context_payload(),
        }

    def tool_inspect_dataset(
        self,
        dataset_path: str = "",
        sample_size: int = 20,
    ) -> Dict[str, Any]:
        self._debug(
            f"tool:inspect_dataset dataset_path={dataset_path or self.state.dataset_path} sample_size={sample_size}"
        )
        resolved_dataset = str(dataset_path).strip() or (self.state.dataset_path or "")
        if not resolved_dataset:
            return {
                "ok": False,
                "error_type": "missing_required",
                "requires": ["dataset_path"],
                "message": "dataset_path is required for inspect_dataset",
            }

        payload = inspect_dataset_schema(
            dataset_path=resolved_dataset,
            sample_size=max(_to_int(sample_size, 20), 1),
        )
        self._debug(
            "tool:inspect_dataset result="
            f"ok={payload.get('ok')} modality={payload.get('modality')}"
        )
        if payload.get("ok"):
            self.state.dataset_path = resolved_dataset
            self.state.last_inspected_dataset = resolved_dataset
            self.state.last_dataset_profile = payload
        return payload

    def tool_retrieve(
        self,
        intent: str,
        top_k: int = 10,
        mode: str = "auto",
        dataset_path: str = "",
    ) -> Dict[str, Any]:
        self._debug(
            f"tool:retrieve_operators intent={intent!r} top_k={top_k} mode={mode} dataset_path={dataset_path or self.state.dataset_path}"
        )
        if not str(intent).strip():
            return {
                "ok": False,
                "error_type": "missing_required",
                "requires": ["intent"],
                "message": "intent is required for retrieve_operators",
            }

        resolved_dataset = str(dataset_path).strip() or (self.state.dataset_path or None)
        try:
            payload = retrieve_operator_candidates(
                intent=str(intent).strip(),
                top_k=max(_to_int(top_k, 10), 1),
                mode=str(mode or "auto").strip() or "auto",
                dataset_path=resolved_dataset,
            )
        except Exception as exc:
            self._debug(f"tool:retrieve_operators failed error={exc}")
            return {
                "ok": False,
                "error_type": "retrieve_failed",
                "message": f"retrieve failed: {exc}",
            }
        payload["ok"] = True
        candidate_names = extract_candidate_names(payload)
        self.state.last_retrieval = {
            "intent": str(intent).strip(),
            "dataset_path": str(resolved_dataset or ""),
            "candidate_names": candidate_names,
            "payload": payload,
        }
        self._debug(
            "tool:retrieve_operators result="
            f"candidate_count={payload.get('candidate_count')} source={payload.get('retrieval_source')}"
        )
        return payload

    def tool_plan_retrieve_candidates(
        self,
        intent: str,
        top_k: int = 12,
        mode: str = "auto",
        dataset_path: str = "",
        remember: bool = True,
    ) -> Dict[str, Any]:
        self._debug(
            "tool:plan_retrieve_candidates "
            f"intent={intent!r} top_k={top_k} mode={mode} dataset_path={dataset_path or self.state.dataset_path}"
        )
        if not str(intent).strip():
            return {
                "ok": False,
                "error_type": "missing_required",
                "requires": ["intent"],
                "message": "intent is required for plan_retrieve_candidates",
            }

        resolved_dataset = str(dataset_path).strip() or (self.state.dataset_path or "")
        try:
            payload = retrieve_operator_candidates(
                intent=str(intent).strip(),
                top_k=max(_to_int(top_k, 12), 1),
                mode=str(mode or "auto").strip() or "auto",
                dataset_path=(resolved_dataset or None),
            )
        except Exception as exc:
            self._debug(f"tool:plan_retrieve_candidates failed error={exc}")
            return {
                "ok": False,
                "error_type": "retrieve_failed",
                "message": f"retrieve failed: {exc}",
            }

        candidate_names = extract_candidate_names(payload)
        if resolved_dataset:
            self.state.dataset_path = resolved_dataset
        if _to_bool(remember, True):
            self.state.last_retrieval = {
                "intent": str(intent).strip(),
                "dataset_path": resolved_dataset,
                "candidate_names": list(candidate_names),
                "payload": payload,
            }

        result = {
            "ok": True,
            "action": "plan_retrieve_candidates",
            "intent": str(intent).strip(),
            "dataset_path": resolved_dataset,
            "candidate_count": len(candidate_names),
            "candidate_names": candidate_names,
            "payload": payload,
            "message": "retrieved planning candidates",
        }
        self._debug(
            "tool:plan_retrieve_candidates result "
            f"candidate_count={result.get('candidate_count')}"
        )
        return result

    def tool_plan_generate(
        self,
        intent: str,
        dataset_path: str = "",
        export_path: str = "",
        output_path: str = "",
        base_plan: str = "",
        from_run_id: str = "",
        custom_operator_paths: Any = None,
        from_template: str = "",
        template_retrieve: bool = False,
        use_cached_retrieval: bool = True,
        planning_mode: str = "auto",
        include_llm_review: bool | None = None,
    ) -> Dict[str, Any]:
        self._debug(
            "tool:plan_generate "
            f"intent={intent!r} dataset_path={dataset_path or self.state.dataset_path} "
            f"export_path={export_path or self.state.export_path} base_plan={base_plan or ''} "
            f"from_template={from_template or ''} template_retrieve={template_retrieve} "
            f"planning_mode={planning_mode} include_llm_review={include_llm_review}"
        )
        if not str(intent).strip():
            return {
                "ok": False,
                "error_type": "missing_required",
                "requires": ["intent"],
                "message": "intent is required for plan_generate",
            }

        resolved_base = str(base_plan).strip() or None
        resolved_from_run = str(from_run_id).strip() or None
        resolved_from_template = str(from_template).strip() or None
        resolved_template_retrieve = _to_bool(template_retrieve, False)
        ignored_template_retrieve = bool(resolved_from_template and resolved_template_retrieve)
        if ignored_template_retrieve:
            resolved_template_retrieve = False

        base_plan_model = None
        if resolved_base:
            base_path = Path(resolved_base)
            if not base_path.exists():
                return {
                    "ok": False,
                    "error_type": "base_plan_not_found",
                    "message": f"base plan file not found: {base_path}",
                }
            base_plan_model = self._load_plan_model(str(base_path))
            if base_plan_model is None:
                return {
                    "ok": False,
                    "error_type": "base_plan_invalid",
                    "message": f"failed to parse base plan: {base_path}",
                }

        if base_plan_model is not None and resolved_from_template:
            return {
                "ok": False,
                "error_type": "conflict_args",
                "message": "base_plan cannot be used with from_template",
            }
        if base_plan_model is not None and resolved_template_retrieve:
            return {
                "ok": False,
                "error_type": "conflict_args",
                "message": "base_plan cannot be used with template_retrieve",
            }
        if resolved_from_run and base_plan_model is None:
            return {
                "ok": False,
                "error_type": "missing_required",
                "requires": ["base_plan"],
                "message": "from_run_id requires base_plan",
            }

        resolved_dataset = str(dataset_path).strip() or (self.state.dataset_path or "")
        resolved_export = str(export_path).strip() or (self.state.export_path or "")
        resolved_output = str(output_path).strip()
        resolved_custom_paths = _to_string_list(custom_operator_paths) or list(self.state.custom_operator_paths)

        if base_plan_model is not None:
            if not resolved_dataset:
                resolved_dataset = base_plan_model.dataset_path
            if not resolved_export:
                resolved_export = base_plan_model.export_path
            if not resolved_custom_paths:
                resolved_custom_paths = list(base_plan_model.custom_operator_paths)

        if not resolved_dataset or not resolved_export:
            return {
                "ok": False,
                "error_type": "missing_required",
                "requires": ["dataset_path", "export_path"],
                "message": "dataset_path/export_path are required when base_plan is not provided",
            }

        run_context = None
        if resolved_from_run:
            run_context = TraceStore().get(resolved_from_run)
            if run_context is None:
                return {
                    "ok": False,
                    "error_type": "run_not_found",
                    "message": f"run not found: {resolved_from_run}",
                }

        raw_mode = str(planning_mode or "auto").strip().lower()
        if raw_mode in {"", "auto"}:
            if base_plan_model is not None or resolved_from_template or resolved_template_retrieve:
                selected_mode = PlanningMode.TEMPLATE_LLM
            else:
                selected_mode = PlanningMode.FULL_LLM
        elif raw_mode in {"full", "full_llm", "full-llm", "llm_full", "llm-full"}:
            selected_mode = PlanningMode.FULL_LLM
        elif raw_mode in {"template", "template_llm", "template-llm"}:
            selected_mode = PlanningMode.TEMPLATE_LLM
        else:
            return {
                "ok": False,
                "error_type": "invalid_args",
                "message": f"unsupported planning_mode: {planning_mode}",
            }

        provided_candidates = None
        if _to_bool(use_cached_retrieval, True):
            provided_candidates = self._cached_retrieval_candidates(
                intent=str(intent).strip(),
                dataset_path=resolved_dataset,
            )

        planner = self._new_planner_usecase(selected_mode)
        try:
            plan = planner.build_plan(
                user_intent=str(intent).strip(),
                dataset_path=resolved_dataset,
                export_path=resolved_export,
                custom_operator_paths=resolved_custom_paths,
                base_plan=base_plan_model,
                run_context=run_context,
                from_template=resolved_from_template,
                template_retrieve=resolved_template_retrieve,
                track_lineage=False,
                retrieved_candidates=provided_candidates,
            )
        except Exception as exc:
            return {
                "ok": False,
                "error_type": "plan_failed",
                "message": f"plan generation failed: {exc}",
                "plan_error": {
                    "stage": "plan_generate",
                    "code": "plan_generation_failed",
                    "recoverable": True,
                    "next_actions": [
                        "run plan_retrieve_candidates then retry plan_generate",
                        "adjust intent/constraints and retry plan_generate",
                    ],
                },
            }

        review_enabled = (
            self._default_llm_review_enabled
            if include_llm_review is None
            else _to_bool(include_llm_review, self._default_llm_review_enabled)
        )
        if review_enabled:
            review = PlanValidator.llm_review(plan)
        else:
            review = {"errors": [], "warnings": []}
        validation_errors = PlanValidator.validate(plan)
        review_errors = list(review.get("errors", []))
        review_warnings = list(review.get("warnings", []))
        errors = validation_errors + review_errors

        if errors:
            return {
                "ok": False,
                "error_type": "plan_validation_failed",
                "message": "generated plan failed validation",
                "plan_id": plan.plan_id,
                "workflow": plan.workflow,
                "operator_names": [item.name for item in plan.operators],
                "validation_errors": validation_errors,
                "review_errors": review_errors,
                "review_warnings": review_warnings,
                "planning_meta": dict(planner.last_plan_meta),
                "plan_error": {
                    "stage": "plan_validate",
                    "code": "plan_validation_failed",
                    "recoverable": True,
                    "next_actions": [
                        "adjust intent/constraints",
                        "re-run plan_generate",
                        "if still failing, ask user for clearer constraints and retry plan_generate",
                    ],
                },
            }

        plan_data = plan.to_dict()
        self.state.dataset_path = resolved_dataset
        self.state.export_path = resolved_export
        # New draft is not persisted yet; avoid accidentally reusing stale saved path.
        self.state.plan_path = None
        self.state.draft_plan = plan_data
        self.state.draft_plan_path_hint = resolved_output or None
        if resolved_custom_paths:
            self.state.custom_operator_paths = list(resolved_custom_paths)

        return {
            "ok": True,
            "action": "plan_generate",
            "message": "plan draft generated",
            "plan_id": plan.plan_id,
            "workflow": plan.workflow,
            "operator_names": [item.name for item in plan.operators],
            "plan": plan_data,
            "planning_meta": dict(planner.last_plan_meta),
            "validation_errors": validation_errors,
            "review_errors": review_errors,
            "review_warnings": review_warnings,
            "llm_review_enabled": bool(review_enabled),
            "used_cached_retrieval": provided_candidates is not None,
            "output_path_hint": resolved_output or None,
            "ignored_template_retrieve": ignored_template_retrieve,
            "requires_save": True,
            "context": self._context_payload(),
        }

    def tool_plan_validate(
        self,
        plan_path: str = "",
        include_llm_review: bool | None = None,
        use_draft: bool = True,
    ) -> Dict[str, Any]:
        self._debug(
            f"tool:plan_validate plan_path={plan_path or ''} include_llm_review={include_llm_review} use_draft={use_draft}"
        )
        resolved_path = str(plan_path).strip()
        plan = None
        plan_source = "draft"
        warnings: List[str] = []

        if resolved_path:
            plan = self._load_plan_model(resolved_path)
            if plan is not None:
                plan_source = "path"
                self.state.draft_plan = plan.to_dict()
                self.state.draft_plan_path_hint = resolved_path
            elif self._looks_like_plan_id(resolved_path):
                draft = self._current_draft_plan_model()
                if draft is not None and str(draft.plan_id).strip() == resolved_path:
                    plan = draft
                    plan_source = "draft_by_plan_id"
                    warnings.append(
                        f"plan_path={resolved_path} is a plan_id token; using current draft plan"
                    )
                else:
                    resolved_by_id = self._find_saved_plan_path_by_plan_id(resolved_path)
                    if resolved_by_id:
                        plan = self._load_plan_model(resolved_by_id)
                        if plan is not None:
                            plan_source = "resolved_path_by_plan_id"
                            self.state.draft_plan = plan.to_dict()
                            self.state.draft_plan_path_hint = resolved_by_id
                            warnings.append(
                                f"plan_path={resolved_path} treated as plan_id; resolved to {resolved_by_id}"
                            )
            if plan is None:
                if _to_bool(use_draft, True):
                    warnings.append(
                        f"failed to load plan file: {resolved_path}; fallback to draft plan"
                    )
                    plan = self._current_draft_plan_model()
                    if plan is not None:
                        plan_source = "draft_fallback"
                    elif self.state.plan_path:
                        plan = self._load_plan_model(self.state.plan_path)
                        if plan is not None:
                            plan_source = "saved_plan_fallback"
                            self.state.draft_plan = plan.to_dict()
                            self.state.draft_plan_path_hint = self.state.plan_path
                else:
                    return {
                        "ok": False,
                        "error_type": "plan_not_found",
                        "message": f"failed to load plan file: {resolved_path}",
                    }
        elif _to_bool(use_draft, True):
            plan = self._current_draft_plan_model()
            if plan is None and self.state.plan_path:
                plan = self._load_plan_model(self.state.plan_path)
                plan_source = "saved_plan"
                if plan is not None:
                    self.state.draft_plan = plan.to_dict()
                    self.state.draft_plan_path_hint = self.state.plan_path

        if plan is None:
            if resolved_path:
                return {
                    "ok": False,
                    "error_type": "plan_not_found",
                    "message": (
                        f"failed to load plan file: {resolved_path}; "
                        "no draft plan available for fallback"
                    ),
                }
            return {
                "ok": False,
                "error_type": "missing_required",
                "requires": ["plan_path_or_draft"],
                "message": "no plan available to validate; run plan_generate first or provide plan_path",
            }

        resolved_include_llm_review = (
            self._default_llm_review_enabled
            if include_llm_review is None
            else _to_bool(include_llm_review, self._default_llm_review_enabled)
        )
        validation_errors = PlanValidator.validate(plan)
        if resolved_include_llm_review:
            review = PlanValidator.llm_review(plan)
        else:
            review = {"errors": [], "warnings": []}

        review_errors = list(review.get("errors", []))
        review_warnings = list(review.get("warnings", []))
        all_errors = validation_errors + review_errors

        return {
            "ok": len(all_errors) == 0,
            "action": "plan_validate",
            "plan_source": plan_source,
            "plan_id": plan.plan_id,
            "workflow": plan.workflow,
            "operator_names": [item.name for item in plan.operators],
            "validation_errors": validation_errors,
            "review_errors": review_errors,
            "review_warnings": review_warnings,
            "llm_review_enabled": bool(resolved_include_llm_review),
            "warnings": warnings,
            "error_count": len(all_errors),
            "message": "plan is valid" if len(all_errors) == 0 else "plan validation failed",
            "context": self._context_payload(),
        }

    def tool_plan_save(
        self,
        output_path: str = "",
        overwrite: bool = False,
        source_plan_path: str = "",
    ) -> Dict[str, Any]:
        self._debug(
            "tool:plan_save "
            f"output_path={output_path or self.state.draft_plan_path_hint or self.state.plan_path} "
            f"overwrite={overwrite} source_plan_path={source_plan_path or ''}"
        )
        source_path = str(source_plan_path).strip()
        plan = None
        warnings: List[str] = []
        if source_path:
            plan = self._load_plan_model(source_path)
            if plan is None and self._looks_like_plan_id(source_path):
                draft = self._current_draft_plan_model()
                if draft is not None and str(draft.plan_id).strip() == source_path:
                    plan = draft
                    warnings.append(
                        f"source_plan_path={source_path} is a plan_id token; using current draft plan"
                    )
                else:
                    resolved_by_id = self._find_saved_plan_path_by_plan_id(source_path)
                    if resolved_by_id:
                        plan = self._load_plan_model(resolved_by_id)
                        if plan is not None:
                            self.state.draft_plan = plan.to_dict()
                            self.state.draft_plan_path_hint = resolved_by_id
                            warnings.append(
                                f"source_plan_path={source_path} treated as plan_id; resolved to {resolved_by_id}"
                            )
            if plan is None:
                return {
                    "ok": False,
                    "error_type": "plan_not_found",
                    "message": f"failed to load plan file: {source_path}",
                }
            self.state.draft_plan = plan.to_dict()
            self.state.draft_plan_path_hint = source_path
        else:
            plan = self._current_draft_plan_model()
            if plan is None and self.state.plan_path:
                plan = self._load_plan_model(self.state.plan_path)

        if plan is None:
            return {
                "ok": False,
                "error_type": "missing_required",
                "requires": ["draft_plan_or_source_plan_path"],
                "message": "no plan draft available to save",
            }

        resolved_output = (
            str(output_path).strip()
            or self.state.draft_plan_path_hint
            or self.state.plan_path
            or self._next_session_plan_path()
        )
        out_path = Path(resolved_output).expanduser()
        if out_path.exists() and not _to_bool(overwrite, False):
            return {
                "ok": False,
                "error_type": "file_exists",
                "message": f"output path exists: {out_path}; set overwrite=true to replace",
            }
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as handle:
            yaml.safe_dump(plan.to_dict(), handle, allow_unicode=False, sort_keys=False)

        self.state.plan_path = str(out_path)
        self.state.draft_plan = plan.to_dict()
        self.state.draft_plan_path_hint = str(out_path)
        self.state.dataset_path = plan.dataset_path
        self.state.export_path = plan.export_path
        self.state.custom_operator_paths = list(plan.custom_operator_paths)

        return {
            "ok": True,
            "action": "plan_save",
            "plan_path": str(out_path),
            "plan_id": plan.plan_id,
            "workflow": plan.workflow,
            "operator_names": [item.name for item in plan.operators],
            "message": f"plan saved: {out_path}",
            "warnings": warnings,
            "context": self._context_payload(),
        }

    def tool_plan(
        self,
        intent: str,
        dataset_path: str = "",
        export_path: str = "",
        output_path: str = "",
        base_plan: str = "",
        from_run_id: str = "",
        custom_operator_paths: Any = None,
        from_template: str = "",
        template_retrieve: bool = False,
        include_llm_review: bool | None = None,
    ) -> Dict[str, Any]:
        self._debug(
            "tool:plan_recipe "
            f"intent={intent!r} dataset_path={dataset_path or self.state.dataset_path} "
            f"export_path={export_path or self.state.export_path} base_plan={base_plan or ''} "
            f"from_template={from_template or ''} template_retrieve={template_retrieve} "
            f"include_llm_review={include_llm_review}"
        )
        if not str(intent).strip():
            return {
                "ok": False,
                "error_type": "missing_required",
                "requires": ["intent"],
                "message": "intent is required for plan_recipe",
            }

        resolved_dataset = str(dataset_path).strip() or (self.state.dataset_path or "")
        resolved_export = str(export_path).strip() or (self.state.export_path or "")
        resolved_output = str(output_path).strip() or self._next_session_plan_path()
        resolved_base = str(base_plan).strip() or None
        resolved_from_run = str(from_run_id).strip() or None
        resolved_from_template = str(from_template).strip() or None
        resolved_template_retrieve = _to_bool(template_retrieve, False)

        resolved_custom_paths = _to_string_list(custom_operator_paths)
        if not resolved_custom_paths:
            resolved_custom_paths = list(self.state.custom_operator_paths)

        if resolved_base:
            missing: List[str] = []
        else:
            missing = [
                field
                for field, value in {
                    "dataset_path": resolved_dataset,
                    "export_path": resolved_export,
                }.items()
                if not value
            ]
        if missing:
            return {
                "ok": False,
                "error_type": "missing_required",
                "requires": missing,
                "message": "dataset_path/export_path are required when base_plan is not provided",
            }

        args = SimpleNamespace(
            intent=str(intent).strip(),
            dataset=resolved_dataset,
            export=resolved_export,
            output=resolved_output,
            base_plan=resolved_base,
            from_run_id=resolved_from_run,
            custom_operator_paths=resolved_custom_paths,
            from_template=resolved_from_template,
            template_retrieve=resolved_template_retrieve,
            planner_model=self._planner_model,
            llm_api_key=self._api_key,
            llm_base_url=self._base_url,
            llm_thinking=self._thinking,
            llm_review=(
                self._default_llm_review_enabled
                if include_llm_review is None
                else _to_bool(include_llm_review, self._default_llm_review_enabled)
            ),
        )
        payload = execute_plan(args)
        self._debug(
            "tool:plan_recipe execute_plan_done "
            f"ok={payload.get('ok')} exit_code={payload.get('exit_code')} "
            f"stage={payload.get('stage')}"
        )

        result: Dict[str, Any] = {
            "ok": bool(payload.get("ok")),
            "action": "plan",
            "exit_code": int(payload.get("exit_code", 2)),
            "intent": args.intent,
            "plan_path": str(payload.get("plan_path") or resolved_output),
        }
        if not payload.get("ok"):
            result["error_type"] = str(payload.get("error_type", "plan_failed"))
            result["message"] = str(payload.get("message", "plan generation failed"))
            result["plan_error"] = {
                "stage": payload.get("stage"),
                "code": payload.get("error_code"),
                "recoverable": bool(payload.get("recoverable", True)),
                "attempts": list(payload.get("attempts", [])),
                "next_actions": list(payload.get("next_actions", [])),
            }
            return result

        plan_data = payload.get("plan") if isinstance(payload.get("plan"), dict) else {}
        operators = plan_data.get("operators", [])
        operator_names = [
            str(item.get("name", "")).strip()
            for item in operators
            if isinstance(item, dict) and str(item.get("name", "")).strip()
        ]

        self.state.dataset_path = args.dataset or self.state.dataset_path
        self.state.export_path = args.export or self.state.export_path
        self.state.plan_path = resolved_output
        self.state.draft_plan = plan_data if isinstance(plan_data, dict) else None
        self.state.draft_plan_path_hint = resolved_output
        if resolved_custom_paths:
            self.state.custom_operator_paths = list(resolved_custom_paths)

        result.update(
            {
                "plan_id": str(plan_data.get("plan_id", "")).strip(),
                "workflow": str(plan_data.get("workflow", "")).strip(),
                "operator_names": operator_names,
                "message": "plan generated",
                "context": self._context_payload(),
                "planning_meta": payload.get("planning_meta", {}),
                "attempts": list(payload.get("attempts", [])),
                "fallback_messages": list(payload.get("fallback_messages", [])),
            }
        )
        self._debug(
            f"tool:plan_recipe result plan_id={result.get('plan_id')} workflow={result.get('workflow')}"
        )
        return result

    def tool_apply(
        self,
        plan_path: str = "",
        dry_run: bool = False,
        timeout: int = 300,
        confirm: bool = False,
    ) -> Dict[str, Any]:
        self._debug(
            "tool:apply_recipe "
            f"plan_path={plan_path or self.state.plan_path} dry_run={dry_run} timeout={timeout} confirm={confirm}"
        )
        if not _to_bool(confirm, False):
            return {
                "ok": False,
                "error_type": "confirmation_required",
                "requires": ["confirm"],
                "message": (
                    "apply may execute dj-process and write export output. "
                    "Ask user to confirm, then call apply_recipe with confirm=true."
                ),
            }

        resolved_plan = str(plan_path).strip() or (self.state.plan_path or "")
        if not resolved_plan:
            return {
                "ok": False,
                "error_type": "missing_required",
                "requires": ["plan_path"],
                "message": "plan_path is required for apply_recipe",
            }

        args = SimpleNamespace(
            plan=resolved_plan,
            yes=True,
            dry_run=_to_bool(dry_run, False),
            timeout=max(_to_int(timeout, 300), 1),
        )
        code, stdout, stderr = self._run_command(run_apply, args)
        self._debug(
            "tool:apply_recipe command_done "
            f"exit_code={code} stdout_lines={len((stdout or '').splitlines())} "
            f"stderr_lines={len((stderr or '').splitlines())}"
        )

        result: Dict[str, Any] = {
            "ok": code == 0,
            "action": "apply",
            "exit_code": code,
            "plan_path": resolved_plan,
            "stdout": _short_log(stdout),
            "stderr": _short_log(stderr),
        }
        if code != 0:
            if code == 130:
                result["error_type"] = "interrupted"
                result["message"] = "apply interrupted by user"
            else:
                result["error_type"] = "apply_failed"
            return result

        run_id = self._extract_run_id(stdout)
        plan_id = self._load_plan_id(resolved_plan)
        if not run_id and plan_id:
            rows = TraceStore().list_by_plan(plan_id, limit=1)
            if rows:
                run_id = rows[-1].get("run_id")

        if run_id:
            self.state.run_id = str(run_id)
        self.state.plan_path = resolved_plan

        result.update(
            {
                "run_id": self.state.run_id,
                "trace_command": f"djx trace {self.state.run_id}" if self.state.run_id else "",
                "message": "apply succeeded" if self.state.run_id else "apply succeeded (run_id unavailable)",
                "context": self._context_payload(),
            }
        )
        self._debug(
            f"tool:apply_recipe result run_id={result.get('run_id')} trace_command={result.get('trace_command')!r}"
        )
        return result

    def tool_trace(
        self,
        run_id: str = "",
        plan_id: str = "",
        limit: int = 20,
        stats: bool = False,
    ) -> Dict[str, Any]:
        self._debug(
            f"tool:trace_run run_id={run_id or self.state.run_id} plan_id={plan_id} limit={limit} stats={stats}"
        )
        store = TraceStore()
        use_stats = _to_bool(stats, False)
        resolved_plan_id = str(plan_id).strip()
        resolved_run_id = str(run_id).strip() or (self.state.run_id or "")

        if use_stats:
            return {
                "ok": True,
                "action": "trace",
                "stats": store.stats(plan_id=resolved_plan_id or None),
            }

        if resolved_run_id:
            row = store.get(resolved_run_id)
            if row is None:
                return {
                    "ok": False,
                    "error_type": "run_not_found",
                    "message": f"Run not found: {resolved_run_id}",
                }
            self.state.run_id = resolved_run_id
            return {
                "ok": True,
                "action": "trace",
                "run": row,
            }

        if resolved_plan_id:
            rows = store.list_by_plan(
                resolved_plan_id,
                limit=max(_to_int(limit, 20), 1),
            )
            if not rows:
                return {
                    "ok": False,
                    "error_type": "plan_not_found",
                    "message": f"No runs found for plan_id: {resolved_plan_id}",
                }
            self.state.run_id = rows[-1].get("run_id")
            return {
                "ok": True,
                "action": "trace",
                "plan_id": resolved_plan_id,
                "runs": rows,
                "latest_run_id": self.state.run_id,
            }

        return {
            "ok": False,
            "error_type": "missing_required",
            "requires": ["run_id_or_plan_id"],
            "message": "provide run_id, plan_id, or enable stats",
        }

    def tool_dev(
        self,
        intent: str,
        operator_name: str = "",
        output_dir: str = "",
        operator_type: str = "",
        from_retrieve: str = "",
        smoke_check: bool = False,
    ) -> Dict[str, Any]:
        self._debug(
            "tool:develop_operator "
            f"intent={intent!r} operator_name={operator_name!r} output_dir={output_dir!r} "
            f"operator_type={operator_type!r} smoke_check={smoke_check}"
        )
        result = DevUseCase.execute(
            intent=str(intent).strip(),
            operator_name=str(operator_name).strip(),
            output_dir=str(output_dir).strip(),
            operator_type=(str(operator_type).strip() or None),
            from_retrieve=(str(from_retrieve).strip() or None),
            smoke_check=_to_bool(smoke_check, False),
        )
        if not result.get("ok"):
            self._debug(f"tool:develop_operator failed error={result.get('message')}")
            return {
                "ok": False,
                "error_type": str(result.get("error_type", "dev_failed")),
                "requires": list(result.get("requires", [])),
                "message": str(result.get("message", "dev scaffold generation failed")),
            }

        path_str = str(result.get("output_dir", "")).strip()
        if path_str not in self.state.custom_operator_paths:
            self.state.custom_operator_paths.append(path_str)

        payload: Dict[str, Any] = {
            "ok": bool(result.get("ok")),
            "action": "dev",
            "operator_name": str(result.get("operator_name", "")),
            "operator_type": str(result.get("operator_type", "")),
            "class_name": str(result.get("class_name", "")),
            "output_dir": path_str,
            "generated_files": list(result.get("generated_files", [])),
            "summary_path": str(result.get("summary_path", "")),
            "notes": list(result.get("notes", [])),
            "context": self._context_payload(),
        }
        if result.get("smoke_check") is not None:
            payload["smoke_check"] = result.get("smoke_check")
        self._debug(
            f"tool:develop_operator result operator_name={payload.get('operator_name')} output_dir={payload.get('output_dir')}"
        )
        return payload

    def tool_view_text_file(
        self,
        file_path: str,
        ranges: Any = None,
    ) -> Dict[str, Any]:
        path = str(file_path).strip()
        if not path:
            return {
                "ok": False,
                "error_type": "missing_required",
                "requires": ["file_path"],
                "message": "file_path is required for view_text_file",
            }
        target = Path(path).expanduser()
        if not target.exists():
            return {
                "ok": False,
                "error_type": "file_not_found",
                "message": f"file does not exist: {target}",
            }
        if not target.is_file():
            return {
                "ok": False,
                "error_type": "invalid_file_type",
                "message": f"path is not a file: {target}",
            }

        parsed_ranges, err = _parse_line_ranges(ranges)
        if err:
            return {
                "ok": False,
                "error_type": "invalid_ranges",
                "message": err,
            }

        try:
            lines = target.read_text(encoding="utf-8").splitlines()
        except Exception as exc:
            return {
                "ok": False,
                "error_type": "read_failed",
                "message": f"failed to read file: {exc}",
            }

        if parsed_ranges is None:
            start = 1
            end = len(lines)
        else:
            start_raw, end_raw = parsed_ranges
            start = _normalize_line_idx(start_raw, len(lines))
            end = _normalize_line_idx(end_raw, len(lines))
            if start < 1:
                start = 1
            if end > len(lines):
                end = len(lines)
            if len(lines) == 0:
                start, end = 1, 0
            if start > end and len(lines) > 0:
                return {
                    "ok": False,
                    "error_type": "invalid_ranges",
                    "message": f"invalid line range after normalization: [{start}, {end}]",
                }

        if len(lines) == 0:
            content = ""
        elif end <= 0:
            content = ""
        else:
            selected = lines[start - 1 : end]
            content = "\n".join(
                f"{idx + start}: {line}"
                for idx, line in enumerate(selected)
            )

        content = _truncate_text(content)
        return {
            "ok": True,
            "action": "view_text_file",
            "file_path": str(target),
            "line_range": [start, end] if parsed_ranges is not None else None,
            "line_count": len(lines),
            "content": content,
            "message": f"loaded {target}",
        }

    def tool_write_text_file(
        self,
        file_path: str,
        content: str,
        ranges: Any = None,
    ) -> Dict[str, Any]:
        path = str(file_path).strip()
        if not path:
            return {
                "ok": False,
                "error_type": "missing_required",
                "requires": ["file_path"],
                "message": "file_path is required for write_text_file",
            }
        target = Path(path).expanduser()
        payload = str(content or "")
        parsed_ranges, err = _parse_line_ranges(ranges)
        if err:
            return {
                "ok": False,
                "error_type": "invalid_ranges",
                "message": err,
            }

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            return {
                "ok": False,
                "error_type": "mkdir_failed",
                "message": f"failed to create parent dir: {exc}",
            }

        if parsed_ranges is None or not target.exists():
            try:
                target.write_text(payload, encoding="utf-8")
            except Exception as exc:
                return {
                    "ok": False,
                    "error_type": "write_failed",
                    "message": f"failed to write file: {exc}",
                }
            return {
                "ok": True,
                "action": "write_text_file",
                "file_path": str(target),
                "line_range": parsed_ranges,
                "message": f"wrote file {target}",
            }

        if not target.is_file():
            return {
                "ok": False,
                "error_type": "invalid_file_type",
                "message": f"path is not a file: {target}",
            }

        start_raw, end_raw = parsed_ranges
        try:
            lines = target.read_text(encoding="utf-8").splitlines(keepends=True)
        except Exception as exc:
            return {
                "ok": False,
                "error_type": "read_failed",
                "message": f"failed to read existing file: {exc}",
            }

        start = _normalize_line_idx(start_raw, len(lines))
        end = _normalize_line_idx(end_raw, len(lines))
        if start < 1:
            start = 1
        if end > len(lines):
            end = len(lines)
        if len(lines) > 0 and (start > end or start > len(lines)):
            return {
                "ok": False,
                "error_type": "invalid_ranges",
                "message": f"invalid line range after normalization: [{start}, {end}]",
            }

        replacement = payload
        if replacement and not replacement.endswith("\n"):
            replacement = replacement + "\n"
        new_lines = lines[: max(start - 1, 0)] + [replacement] + lines[end:]

        try:
            target.write_text("".join(new_lines), encoding="utf-8")
        except Exception as exc:
            return {
                "ok": False,
                "error_type": "write_failed",
                "message": f"failed to write file: {exc}",
            }

        return {
            "ok": True,
            "action": "write_text_file",
            "file_path": str(target),
            "line_range": [start, end],
            "message": f"updated lines [{start}, {end}] in {target}",
        }

    def tool_insert_text_file(
        self,
        file_path: str,
        content: str,
        line_number: int,
    ) -> Dict[str, Any]:
        path = str(file_path).strip()
        if not path:
            return {
                "ok": False,
                "error_type": "missing_required",
                "requires": ["file_path"],
                "message": "file_path is required for insert_text_file",
            }
        target = Path(path).expanduser()
        if not target.exists():
            return {
                "ok": False,
                "error_type": "file_not_found",
                "message": f"file does not exist: {target}",
            }
        if not target.is_file():
            return {
                "ok": False,
                "error_type": "invalid_file_type",
                "message": f"path is not a file: {target}",
            }
        insert_at = _to_int(line_number, 0)
        if insert_at <= 0:
            return {
                "ok": False,
                "error_type": "invalid_line_number",
                "message": "line_number must be >= 1",
            }

        try:
            lines = target.read_text(encoding="utf-8").splitlines(keepends=True)
        except Exception as exc:
            return {
                "ok": False,
                "error_type": "read_failed",
                "message": f"failed to read file: {exc}",
            }
        if insert_at > len(lines) + 1:
            return {
                "ok": False,
                "error_type": "invalid_line_number",
                "message": f"line_number {insert_at} out of range [1, {len(lines) + 1}]",
            }

        insert_text = str(content or "")
        if insert_text and not insert_text.endswith("\n"):
            insert_text = insert_text + "\n"
        new_lines = lines[: insert_at - 1] + [insert_text] + lines[insert_at - 1 :]
        try:
            target.write_text("".join(new_lines), encoding="utf-8")
        except Exception as exc:
            return {
                "ok": False,
                "error_type": "write_failed",
                "message": f"failed to write file: {exc}",
            }

        return {
            "ok": True,
            "action": "insert_text_file",
            "file_path": str(target),
            "line_number": insert_at,
            "message": f"inserted content at line {insert_at} in {target}",
        }

    def _run_interruptible_subprocess(
        self,
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
                        "stdout": _truncate_text(out or "", 8000),
                        "stderr": _truncate_text(err or "", 8000),
                        "message": f"process finished with returncode={int(rc)}",
                    }

                if time.monotonic() >= deadline:
                    with contextlib.suppress(Exception):
                        os.killpg(proc.pid, signal.SIGTERM)
                    with contextlib.suppress(Exception):
                        proc.wait(timeout=2)
                    if proc.poll() is None:
                        with contextlib.suppress(Exception):
                            os.killpg(proc.pid, signal.SIGKILL)
                        with contextlib.suppress(Exception):
                            proc.kill()
                    out, err = proc.communicate(timeout=2)
                    return {
                        "ok": False,
                        "error_type": "timeout",
                        "returncode": -1,
                        "stdout": _truncate_text(out or "", 8000),
                        "stderr": _truncate_text((err or "").strip(), 8000),
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

    def tool_execute_shell_command(
        self,
        command: str,
        timeout: int = 120,
    ) -> Dict[str, Any]:
        cmd = str(command or "").strip()
        if not cmd:
            return {
                "ok": False,
                "error_type": "missing_required",
                "requires": ["command"],
                "message": "command is required for execute_shell_command",
            }
        timeout_sec = max(_to_int(timeout, 120), 1)
        try:
            payload = self._run_interruptible_subprocess(
                cmd,
                timeout_sec=timeout_sec,
                shell=True,
            )
            payload["action"] = "execute_shell_command"
            return payload
        except Exception as exc:
            return {
                "ok": False,
                "error_type": "execution_failed",
                "message": f"shell command failed: {exc}",
            }

    def tool_execute_python_code(
        self,
        code: str,
        timeout: int = 120,
    ) -> Dict[str, Any]:
        snippet = str(code or "")
        if not snippet.strip():
            return {
                "ok": False,
                "error_type": "missing_required",
                "requires": ["code"],
                "message": "code is required for execute_python_code",
            }
        timeout_sec = max(_to_int(timeout, 120), 1)
        try:
            payload = self._run_interruptible_subprocess(
                [sys.executable, "-c", snippet],
                timeout_sec=timeout_sec,
                shell=False,
            )
            payload["action"] = "execute_python_code"
            return payload
        except Exception as exc:
            return {
                "ok": False,
                "error_type": "execution_failed",
                "message": f"python execution failed: {exc}",
            }

    def handle_message(
        self,
        message: str,
    ) -> SessionReply:
        message = message.strip()
        if not message:
            return SessionReply(text="Please enter a non-empty message.")

        self._debug(f"user_message={message!r}")
        self.state.history.append({"role": "user", "content": message})

        lowered = message.lower()
        if lowered in {"exit", "quit", "bye", "q", "退出"}:
            reply = SessionReply(text="Session ended.", stop=True)
            self.state.history.append({"role": "assistant", "content": reply.text})
            return reply
        if lowered in {"help", "h", "?", "帮助", "说明"}:
            reply = SessionReply(text=_HELP_TEXT)
            self.state.history.append({"role": "assistant", "content": reply.text})
            return reply
        if lowered in {"cancel", "取消"}:
            reply = SessionReply(text="No pending action. Continue with natural language requests.")
            self.state.history.append({"role": "assistant", "content": reply.text})
            return reply

        if self._react_agent is None:
            reply = SessionReply(
                text=(
                    "Session misconfigured: ReAct agent is unavailable. "
                    "Please restart `dj-agents` with valid LLM settings."
                ),
                stop=True,
            )
            self.state.history.append({"role": "assistant", "content": reply.text})
            return reply

        try:
            self._last_reply_thinking = ""
            text, interrupted = self._react_reply(message)
            if interrupted:
                self._debug("react_reply_interrupted")
                reply = SessionReply(
                    text="The current task was interrupted. You can continue with your next request.",
                    stop=False,
                    interrupted=True,
                    thinking=self._last_reply_thinking,
                )
            else:
                if not text:
                    text = "The request was processed, but no displayable text was returned."
                self._debug("react_reply_received")
                reply = SessionReply(text=text, thinking=self._last_reply_thinking)
        except asyncio.CancelledError:
            self._debug("react_reply_interrupted")
            reply = SessionReply(
                text="The current task was interrupted. You can continue with your next request.",
                stop=False,
                interrupted=True,
            )
        except Exception as exc:
            self._debug(f"react_reply_failed error={exc}")
            reply = SessionReply(
                text=(
                    "LLM session call failed, exiting session.\n"
                    f"error: {exc}"
                ),
                stop=True,
            )
        self.state.history.append({"role": "assistant", "content": reply.text})
        return reply
