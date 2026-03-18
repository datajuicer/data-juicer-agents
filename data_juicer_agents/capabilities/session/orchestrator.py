# -*- coding: utf-8 -*-
"""Session agent orchestration for unified `dj-agents` entry."""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import os
import threading
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional

from data_juicer_agents.capabilities.session.runtime import SessionState, SessionToolRuntime
from data_juicer_agents.capabilities.session.toolkit import build_session_toolkit

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


@dataclass
class _SessionMsgReply:
    msg: Any
    thinking: str = ""
    stop: bool = False
    interrupted: bool = False


@dataclass
class _StudioTurnResult:
    msg: Any
    stop: bool = False
    should_emit_final: bool = True


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


def _coerce_inbound_message_text(msg: Any) -> str:
    if msg is None:
        return ""
    content = getattr(msg, "content", msg)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = str(item.get("text", "")).strip()
                if text:
                    parts.append(text)
        return "\n".join(parts).strip()
    return str(content).strip()

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
        enable_streaming: bool = False,
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
        self._enable_streaming = bool(enable_streaming)
        self._stream_callback: Optional[Callable[[Any, bool], Awaitable[None] | None]] = None
        self._tool_runtime = SessionToolRuntime(
            state=self.state,
            verbose=self.verbose,
            event_callback=event_callback,
        )
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
            "inspect_dataset -> retrieve_operators -> build_dataset_spec -> build_process_spec -> build_system_spec -> assemble_plan -> plan_validate -> plan_save.\n"
            "All plan tools require explicit arguments. Do not rely on any hidden session defaults, current draft state, or current context fallback.\n"
            "Use inspect_dataset first, then pass its full dataset_profile output into build_dataset_spec together with explicit intent, dataset_path, and export_path.\n"
            "retrieve_operators does not inspect the dataset for you and does not return dataset_profile. If dataset structure matters, call inspect_dataset explicitly first.\n"
            "Use retrieve_operators before build_process_spec, then pass an explicit operators array with canonical operator names and filled params. build_process_spec will not canonicalize or repair operator names for you. Do not pass only operator names when a concrete threshold, mode, or option is already known.\n"
            "Use build_system_spec to produce the deterministic minimal runtime profile, then pass the full dataset_spec, process_spec, and system_spec objects into assemble_plan.\n"
            "After assemble_plan, pass the full returned plan object into plan_validate and plan_save. When calling plan_save, also provide an explicit output_path.\n"
            "When calling apply_recipe, always pass an explicit plan_path. apply_recipe executes the plan and does not validate it for you; call plan_validate explicitly beforehand when validation is needed.\n"
            "Never ignore inspect/retrieve results when forming build_dataset_spec or build_process_spec inputs.\n"
            "For concrete dataset transformation requests (for example filtering/cleaning/dedup), "
            "you must execute tools instead of only providing reasoning.\n"
            "Do not end the turn with only planned tool calls; execute the planned tools and then summarize results.\n"
            "If build_dataset_spec, build_process_spec, build_system_spec, or assemble_plan fails, inspect the returned errors and retry the failed stage with corrected inputs before asking user follow-up questions.\n"
            "You should usually retry a recoverable staged planning tool at least once.\n"
            "Warnings from build_system_spec and validate_process_spec are expected in this iteration; do not treat those warnings alone as fatal.\n"
            "Use view_text_file/write_text_file/insert_text_file for file operations when needed.\n"
            "Use execute_shell_command/execute_python_code for diagnostic or programmatic tasks when needed.\n"
            "After apply_recipe succeeds, do not call any more tools in this turn. "
            "Do not run inspect_dataset, execute_shell_command, execute_python_code, view_text_file, or any other "
            "post-apply verification step unless the user explicitly asked for verification. "
            "Immediately write the final natural-language summary based on the apply result and current context. "
            "If deeper post-apply inspection may be useful, mention that you can help inspect the output in a "
            "follow-up turn.\n"
            "When required fields are missing, ask concise follow-up questions.\n"
            "Before running apply_recipe, ask user for explicit confirmation.\n"
            "If you receive a system hint telling you that you failed to generate a response within the maximum iterations, "
            "or asking you to summarize the current situation directly, do not call any tools. "
            "In that case, produce only a plain natural-language summary of the current state, completed actions, failures, saved files, and next step.\n"
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

    async def _forward_stream_chunk(self, msg: Any, last: bool) -> None:
        callback = self._stream_callback
        if callback is None:
            return
        try:
            forwarded = callback(deepcopy(msg), last)
            if asyncio.iscoroutine(forwarded):
                await forwarded
        except Exception as exc:  # pragma: no cover - defensive callback guard
            self._debug(f"stream_callback_failed error={exc}")

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
            stream=self._enable_streaming,
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
            max_iters=15,
            parallel_tool_calls=False,
        )
        self._register_react_hooks(agent)
        original_print = agent.print

        async def _wrapped_print(msg: Any, last: bool = True, speech: Any = None) -> None:
            role = str(getattr(msg, "role", "") or "").strip().lower()
            if role == "assistant":
                await self._forward_stream_chunk(msg, last)
            await original_print(msg, last=last, speech=speech)

        agent.print = _wrapped_print
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

    async def _react_reply_msg_async(self, message: str) -> tuple[Any, str, str, bool]:
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
            return reply, text.strip(), thinking.strip(), self._reply_marked_interrupted(reply)
        finally:
            self._clear_active_react_context(loop)

    @staticmethod
    def _extract_reply_text_and_thinking(reply_msg: Any) -> tuple[str, str]:
        text = ""
        try:
            text = str(reply_msg.get_text_content() or "")
        except Exception:
            text = ""
        if not text:
            try:
                content = getattr(reply_msg, "content", None)
                text = _coerce_block_text(content)
            except Exception:
                text = ""
        if not text:
            try:
                blocks = reply_msg.get_content_blocks()
            except Exception:
                blocks = []
            text_parts: List[str] = []
            for block in blocks:
                block_type = str(block.get("type", "")).strip().lower()
                if block_type in {"thinking", "reasoning", "tool_use"}:
                    continue
                value = ""
                for key in ("text", "content"):
                    value = _coerce_block_text(block.get(key))
                    if value:
                        break
                if value:
                    text_parts.append(value)
            if text_parts:
                text = "\n\n".join(part for part in text_parts if part).strip()

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

    @staticmethod
    def _build_simple_reply_msg(text: str, *, stop: bool = False, interrupted: bool = False):
        from agentscope.message import Msg

        metadata: Dict[str, Any] = {}
        if stop:
            metadata["dj_stop"] = True
        if interrupted:
            metadata["dj_interrupted"] = True
        return Msg(
            name="dj-agents",
            role="assistant",
            content=text,
            metadata=metadata or None,
        )

    async def _handle_message_as_msg_async_impl(self, message: str) -> _SessionMsgReply:
        message = message.strip()
        if not message:
            return _SessionMsgReply(msg=self._build_simple_reply_msg("Please enter a non-empty message."))

        self._debug(f"user_message={message!r}")
        self.state.history.append({"role": "user", "content": message})

        lowered = message.lower()
        if lowered in {"exit", "quit", "bye", "q", "退出"}:
            reply = _SessionMsgReply(
                msg=self._build_simple_reply_msg("Session ended.", stop=True),
                stop=True,
            )
            self.state.history.append({"role": "assistant", "content": "Session ended."})
            return reply
        if lowered in {"help", "h", "?", "帮助", "说明"}:
            reply = _SessionMsgReply(msg=self._build_simple_reply_msg(_HELP_TEXT))
            self.state.history.append({"role": "assistant", "content": _HELP_TEXT})
            return reply
        if lowered in {"cancel", "取消"}:
            text = "No pending action. Continue with natural language requests."
            reply = _SessionMsgReply(msg=self._build_simple_reply_msg(text))
            self.state.history.append({"role": "assistant", "content": text})
            return reply

        if self._react_agent is None:
            text = (
                "Session misconfigured: ReAct agent is unavailable. "
                "Please restart `dj-agents` with valid LLM settings."
            )
            reply = _SessionMsgReply(
                msg=self._build_simple_reply_msg(text, stop=True),
                stop=True,
            )
            self.state.history.append({"role": "assistant", "content": text})
            return reply

        try:
            reply_msg, text, thinking, interrupted = await self._react_reply_msg_async(message)
            if interrupted:
                text = "The current task was interrupted. You can continue with your next request."
                reply = _SessionMsgReply(
                    msg=self._build_simple_reply_msg(text, interrupted=True),
                    interrupted=True,
                    thinking=thinking,
                )
            else:
                reply = _SessionMsgReply(
                    msg=reply_msg,
                    interrupted=False,
                    thinking=thinking,
                )
                if not text:
                    text = "The request was processed, but no displayable text was returned."
            self._debug("react_reply_received" if not interrupted else "react_reply_interrupted")
        except asyncio.CancelledError:
            self._debug("react_reply_interrupted")
            text = "The current task was interrupted. You can continue with your next request."
            reply = _SessionMsgReply(
                msg=self._build_simple_reply_msg(text, interrupted=True),
                interrupted=True,
            )
        except Exception as exc:
            self._debug(f"react_reply_failed error={exc}")
            text = (
                "LLM session call failed, exiting session.\n"
                f"error: {exc}"
            )
            reply = _SessionMsgReply(
                msg=self._build_simple_reply_msg(text, stop=True),
                stop=True,
            )

        self.state.history.append({"role": "assistant", "content": text})
        return reply

    async def _handle_message_async_impl(self, message: str) -> SessionReply:
        msg_reply = await self._handle_message_as_msg_async_impl(message)
        text, thinking = self._extract_reply_text_and_thinking(msg_reply.msg)
        if not text:
            text = "The request was processed, but no displayable text was returned."
        thinking = msg_reply.thinking or thinking
        return SessionReply(
            text=text,
            thinking=thinking,
            stop=msg_reply.stop,
            interrupted=msg_reply.interrupted,
        )

    async def handle_message_async(
        self,
        message: str,
    ) -> SessionReply:
        return await self._handle_message_async_impl(message)

    async def handle_as_studio_turn_async(
        self,
        inbound_msg: Any,
        emit_chunk: Callable[[Any, bool], Awaitable[None] | None],
    ) -> _StudioTurnResult:
        text = _coerce_inbound_message_text(inbound_msg)
        stream_emitted = False
        stream_last = False
        previous_callback = self._stream_callback

        async def _emit_studio_chunk(msg: Any, last: bool) -> None:
            nonlocal stream_emitted, stream_last
            metadata = dict(getattr(msg, "metadata", None) or {})
            metadata["dj_stream"] = True
            msg.metadata = metadata or None
            forwarded = emit_chunk(msg, last)
            if asyncio.iscoroutine(forwarded):
                await forwarded
            stream_emitted = True
            stream_last = bool(last)

        self._stream_callback = _emit_studio_chunk
        try:
            msg_reply = await self._handle_message_as_msg_async_impl(text)
        finally:
            self._stream_callback = previous_callback

        metadata = dict(getattr(msg_reply.msg, "metadata", None) or {})
        if msg_reply.stop:
            metadata["dj_stop"] = True
        if msg_reply.interrupted:
            metadata["dj_interrupted"] = True
        if msg_reply.thinking:
            metadata["dj_thinking"] = msg_reply.thinking

        out = msg_reply.msg
        out.metadata = metadata or None
        return _StudioTurnResult(
            msg=out,
            stop=msg_reply.stop,
            should_emit_final=not (stream_emitted and stream_last),
        )

    def handle_message(
        self,
        message: str,
    ) -> SessionReply:
        return asyncio.run(self._handle_message_async_impl(message))
