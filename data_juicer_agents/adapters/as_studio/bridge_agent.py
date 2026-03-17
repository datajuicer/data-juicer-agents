# -*- coding: utf-8 -*-
"""Bridge AgentScope Studio messages into the existing DJ session entrypoint."""

from __future__ import annotations

import asyncio
from typing import Any

from data_juicer_agents.capabilities.session.orchestrator import DJSessionAgent


def _coerce_message_text(msg: Any) -> str:
    if msg is None:
        return ""
    content = getattr(msg, "content", msg)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = str(item.get("text", "")).strip()
                if text:
                    parts.append(text)
        return "\n".join(parts).strip()
    return str(content).strip()


class DJStudioBridgeAgent:
    """Thin async wrapper that forwards Studio messages into DJSessionAgent."""

    def __init__(self, session_agent: DJSessionAgent, name: str = "assistant") -> None:
        from agentscope.agent import AgentBase

        class _BridgeAgent(AgentBase):
            def __init__(self, owner: "DJStudioBridgeAgent", bridge_name: str) -> None:
                super().__init__()
                self._owner = owner
                self.name = bridge_name

            async def reply(self, msg=None, *args, **kwargs):  # noqa: ANN001
                from agentscope.message import Msg

                text = _coerce_message_text(msg)
                self._owner._begin_turn_stream()
                try:
                    session_reply = await self._owner.session_agent.handle_message_as_msg_async(text)
                except Exception as exc:  # pragma: no cover - defensive runtime guard
                    self._owner._end_turn_stream()
                    out = Msg(
                        name=self.name,
                        role="assistant",
                        content=(
                            "AgentScope Studio bridge failed while handling the request.\n"
                            f"error: {exc}"
                        ),
                        metadata={"dj_error": True},
                    )
                    await self.print(out)
                    return out

                metadata = dict(getattr(session_reply.msg, "metadata", None) or {})
                if session_reply.stop:
                    metadata["dj_stop"] = True
                if session_reply.interrupted:
                    metadata["dj_interrupted"] = True
                if session_reply.thinking:
                    metadata["dj_thinking"] = session_reply.thinking

                out = session_reply.msg
                out.metadata = metadata or None
                if not self._owner._turn_stream_completed():
                    await self.print(out)
                self._owner._end_turn_stream()
                return out

        self.session_agent = session_agent
        self._agent = _BridgeAgent(self, name)
        self._stream_lock = asyncio.Lock()
        self._stream_emitted = False
        self._stream_last = False

    def _begin_turn_stream(self) -> None:
        self._stream_emitted = False
        self._stream_last = False

    def _end_turn_stream(self) -> None:
        self._stream_emitted = False
        self._stream_last = False

    def _turn_stream_completed(self) -> bool:
        return self._stream_emitted and self._stream_last

    async def forward_stream_chunk(self, msg: Any, last: bool) -> None:
        async with self._stream_lock:
            metadata = dict(getattr(msg, "metadata", None) or {})
            metadata["dj_stream"] = True
            msg.metadata = metadata
            self._stream_emitted = True
            self._stream_last = bool(last)
            await self._agent.print(msg, last=last)

    async def __call__(self, *args, **kwargs):
        return await self._agent(*args, **kwargs)

    async def reply(self, *args, **kwargs):
        return await self._agent.reply(*args, **kwargs)
