# -*- coding: utf-8 -*-

import argparse
import asyncio

from data_juicer_agents.adapters.as_studio.app import run_as_studio_session
from data_juicer_agents.adapters.as_studio.bridge_agent import DJStudioBridgeAgent
from data_juicer_agents.capabilities.session.orchestrator import SessionMsgReply


def test_bridge_agent_forwards_message_and_sets_stop_metadata():
    from agentscope.message import Msg

    class _SessionAgent:
        def __init__(self):
            self.seen = []

        async def handle_message_as_msg_async(self, text):
            self.seen.append(text)
            return SessionMsgReply(
                msg=Msg(
                    name="dj-agents",
                    role="assistant",
                    content=[{"type": "text", "text": "done"}],
                    metadata={"source": "react"},
                ),
                stop=True,
                thinking="trace",
            )

    session_agent = _SessionAgent()
    bridge = DJStudioBridgeAgent(session_agent)

    class _Msg:
        content = "hello from studio"

    reply = asyncio.run(bridge.reply(_Msg()))
    assert session_agent.seen == ["hello from studio"]
    assert reply.content == [{"type": "text", "text": "done"}]
    assert reply.metadata["source"] == "react"
    assert reply.metadata["dj_stop"] is True
    assert reply.metadata["dj_thinking"] == "trace"


def test_bridge_agent_streams_chunks_without_duplicate_final_message(monkeypatch):
    from agentscope.message import Msg

    class _SessionAgent:
        def __init__(self):
            self.bridge = None

        async def handle_message_as_msg_async(self, text):  # noqa: ARG002
            await self.bridge.forward_stream_chunk(
                Msg(name="dj-agents", role="assistant", content=[{"type": "text", "text": "part"}]),
                last=False,
            )
            await self.bridge.forward_stream_chunk(
                Msg(name="dj-agents", role="assistant", content=[{"type": "text", "text": "done"}]),
                last=True,
            )
            return SessionMsgReply(
                msg=Msg(name="dj-agents", role="assistant", content=[{"type": "text", "text": "done"}]),
            )

    session_agent = _SessionAgent()
    bridge = DJStudioBridgeAgent(session_agent)
    session_agent.bridge = bridge

    printed = []

    async def _fake_print(msg, last=True, speech=None):  # noqa: ARG001
        printed.append((msg.content, last))

    monkeypatch.setattr(bridge._agent, 'print', _fake_print)  # pylint: disable=protected-access

    class _Msg:
        content = "hello from studio"

    reply = asyncio.run(bridge.reply(_Msg()))

    assert reply.content == [{"type": "text", "text": "done"}]
    assert printed == [
        ([{"type": "text", "text": "part"}], False),
        ([{"type": "text", "text": "done"}], True),
    ]


def test_bridge_agent_prints_final_message_when_no_stream_chunks(monkeypatch):
    from agentscope.message import Msg

    class _SessionAgent:
        async def handle_message_as_msg_async(self, text):  # noqa: ARG002
            return SessionMsgReply(
                msg=Msg(name="dj-agents", role="assistant", content=[{"type": "text", "text": "done"}]),
            )

    bridge = DJStudioBridgeAgent(_SessionAgent())
    printed = []

    async def _fake_print(msg, last=True, speech=None):  # noqa: ARG001
        printed.append((msg.content, last))

    monkeypatch.setattr(bridge._agent, 'print', _fake_print)  # pylint: disable=protected-access

    class _Msg:
        content = "hello from studio"

    reply = asyncio.run(bridge.reply(_Msg()))

    assert reply.content == [{"type": "text", "text": "done"}]
    assert printed == [([{"type": "text", "text": "done"}], True)]


def test_run_as_studio_session_calls_agentscope_init_and_stops(monkeypatch):
    seen = {}

    class _UserAgent:
        def __init__(self, _name):
            self.calls = 0

        async def __call__(self):
            self.calls += 1
            return type("Msg", (), {"content": "exit"})()

    class _Bridge:
        def __init__(self, session_agent, name):  # noqa: ARG002
            self.session_agent = session_agent
            seen["bridge_session_agent"] = session_agent

        async def __call__(self, _msg):
            return type("Msg", (), {"metadata": {"dj_stop": True}})()

        async def forward_stream_chunk(self, msg, last):  # noqa: ARG002
            seen.setdefault("stream_calls", []).append(last)

    class _SessionAgent:
        def __init__(self, **kwargs):
            seen["session_kwargs"] = kwargs
            self.stream_callback = None

        def set_stream_callback(self, callback):
            self.stream_callback = callback
            seen["stream_callback_set"] = callback is not None

    def _fake_init(**kwargs):
        seen["init_kwargs"] = kwargs

    monkeypatch.setattr("agentscope.init", _fake_init)
    monkeypatch.setattr("agentscope.agent.UserAgent", _UserAgent)
    monkeypatch.setattr("data_juicer_agents.adapters.as_studio.app.DJSessionAgent", _SessionAgent)
    monkeypatch.setattr("data_juicer_agents.adapters.as_studio.app.DJStudioBridgeAgent", _Bridge)

    args = argparse.Namespace(
        dataset="a.jsonl",
        export="b.jsonl",
        verbose=True,
        studio_url="http://localhost:4000",
    )
    code = run_as_studio_session(args)

    assert code == 0
    assert seen["init_kwargs"]["studio_url"] == "http://localhost:4000"
    assert seen["init_kwargs"]["project"] == "data-juicer-agents"
    assert seen["session_kwargs"]["dataset_path"] == "a.jsonl"
    assert seen["session_kwargs"]["export_path"] == "b.jsonl"
    assert seen["session_kwargs"]["verbose"] is True
    assert seen["session_kwargs"]["enable_streaming"] is True
    assert seen["stream_callback_set"] is True


def test_run_as_studio_session_returns_2_when_init_fails(monkeypatch, capsys):
    def _boom(**_kwargs):
        raise RuntimeError("cannot connect")

    monkeypatch.setattr("agentscope.init", _boom)

    args = argparse.Namespace(
        dataset=None,
        export=None,
        verbose=False,
        studio_url="http://localhost:4000",
    )
    code = run_as_studio_session(args)

    assert code == 2
    assert "Failed to initialize AgentScope Studio session" in capsys.readouterr().out
