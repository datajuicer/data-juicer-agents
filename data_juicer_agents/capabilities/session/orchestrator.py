# -*- coding: utf-8 -*-
"""Session agent orchestration for unified `dj-agents` entry."""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import os
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from data_juicer_agents.tools.session import (
    SessionState,
    SessionToolRuntime,
    build_session_toolkit,
)

_SESSION_MODEL = "qwen3-max-2026-01-23"

_HELP_TEXT = (
    "I can help you orchestrate Data-Juicer workflows conversationally.\n"
    "Describe your request in natural language, for example:\n"
    "- I want a cleaning plan for data/demo-dataset.jsonl\n"
    "- Retrieve candidate operators for deduplication and filtering\n"
    "- Existing operators do not satisfy this requirement. Help me generate a new operator\n"
    "Available atomic capabilities: retrieve / plan(core tools) / apply / dev.\n"
    "Control commands: help / exit / cancel."
)

@dataclass
class SessionReply:
    text: str
    thinking: str = ""
    stop: bool = False
    interrupted: bool = False


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
        self._thinking = thinking if isinstance(thinking, bool) else None
        self._event_callback = event_callback
        self._tool_runtime = SessionToolRuntime(
            state=self.state,
            verbose=self.verbose,
            event_callback=event_callback,
        )
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
            f"You must only write, create, or execute files/commands inside the current working directory: {working_dir}.\n"
            "If the user explicitly specifies a different working directory, treat that directory as the new working directory for this session first, "
            "then keep all later file and command operations inside it.\n"
            "If a requested path is outside the current working directory, do not operate on it until the user explicitly changes the working directory.\n"
            "For planning requests, prefer this chain: "
            "inspect_dataset -> retrieve_operators -> plan_build -> plan_validate (draft) -> plan_save.\n"
            "Before calling plan_build, synthesize a grounded spec that merges: "
            "(a) user goal, (b) inspect_dataset findings (modality, candidate keys, sample stats), "
            "(c) retrieve_operators outputs (canonical operator names).\n"
            "Build draft_spec_json with explicit target fields, threshold/unit constraints, and canonical operator names.\n"
            "Never ignore inspect/retrieve results when forming plan_build inputs.\n"
            "For concrete dataset transformation requests (for example filtering/cleaning/dedup), "
            "you must execute tools instead of only providing reasoning.\n"
            "Do not end the turn with only planned tool calls; execute the planned tools and then summarize results.\n"
            "If plan_build fails, inspect the returned errors and retry plan_build with corrected spec fields before asking user follow-up questions.\n"
            "You should usually retry plan_build at least once when failure is recoverable.\n"
            "Use view_text_file/write_text_file/insert_text_file for file operations when needed.\n"
            "Use execute_shell_command/execute_python_code for diagnostic or programmatic tasks when needed.\n"
            "When required fields are missing, ask concise follow-up questions.\n"
            "Before running apply_recipe, ask user for explicit confirmation.\n"
            "Turn completion protocol:\n"
            "- Every turn must end with a final user-facing natural language reply.\n"
            "- Do not end a turn with only tool calls, tool results, or empty text.\n"
            "- Never assume tool output itself is the final answer shown to the user.\n"
            "- If you called tools in this turn, your final reply must summarize what you executed, what succeeded or failed, and the most relevant next step.\n"
            "- If any new files were saved or written, explain what each file is for and include its path.\n"
            "- If a tool failed and you stop without retrying, explicitly explain the failure in the final reply.\n"
            "- After the last tool call, write the final reply before ending the turn.\n"
            "Infer the user's likely next intent and end with a proactive suggestion in this style: "
            "'If you want ..., tell me ..., and I will ...'.\n"
            "If user says help, summarize capabilities and examples.\n"
            "If user says exit/quit, respond with a short goodbye.\n"
            "Always reflect tool results, including failures and next steps.\n"
            "Do not append meta narration like 'The user requested ...' after final answer.\n"
            "Respond in the same language as the user."
        )

    def _context_payload(self) -> Dict[str, Any]:
        return self._tool_runtime.context_payload()

    def _build_toolkit(self):
        return build_session_toolkit(self._tool_runtime)

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

        return text.strip(), thinking.strip()

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
