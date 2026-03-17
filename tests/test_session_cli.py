# -*- coding: utf-8 -*-

import argparse
import time

import pytest

from data_juicer_agents.session_cli import _run_plain_session
from data_juicer_agents.session_cli import _run_as_studio_session
from data_juicer_agents.session_cli import _run_turn_with_interrupt
from data_juicer_agents.session_cli import build_parser


def test_session_cli_parser_accepts_verbose_flag():
    parser = build_parser()
    args = parser.parse_args(
        ["--verbose", "--dataset", "a.jsonl", "--export", "b.jsonl", "--ui", "tui"]
    )
    assert args.verbose is True
    assert args.dataset == "a.jsonl"
    assert args.export == "b.jsonl"
    assert args.ui == "tui"


def test_session_cli_parser_rejects_unknown_flag():
    parser = build_parser()
    with pytest.raises(SystemExit):
        _ = parser.parse_args(["--deprecated-flag"])


def test_session_cli_parser_default_ui_is_tui():
    parser = build_parser()
    args = parser.parse_args([])
    assert args.ui == "tui"


def test_session_cli_parser_accepts_as_studio_and_studio_url():
    parser = build_parser()
    args = parser.parse_args(["--ui", "as_studio", "--studio-url", "http://localhost:4000"])
    assert args.ui == "as_studio"
    assert args.studio_url == "http://localhost:4000"


def test_run_turn_with_interrupt_requests_ctrl_c_interrupt(monkeypatch, capsys):
    class _Agent:
        def __init__(self):
            self.interrupt_calls = 0

        def handle_message(self, _message):
            time.sleep(0.1)
            return "done"

        def request_interrupt(self):
            self.interrupt_calls += 1
            return True

    agent = _Agent()
    calls = {"count": 0}

    def _fake_wait(_done, _timeout):
        calls["count"] += 1
        if calls["count"] == 1:
            raise KeyboardInterrupt()
        time.sleep(0.12)
        return True

    monkeypatch.setattr("data_juicer_agents.session_cli._wait_for_turn", _fake_wait)
    reply = _run_turn_with_interrupt(agent, "hello")
    assert reply == "done"
    assert agent.interrupt_calls == 1
    assert "Interrupt requested (Ctrl+C)." in capsys.readouterr().out


def test_plain_session_ctrl_c_when_idle_does_not_exit(monkeypatch, capsys):
    class _Agent:
        def handle_message(self, _message):
            raise AssertionError("should not handle message")

    monkeypatch.setattr(
        "data_juicer_agents.session_cli.DJSessionAgent",
        lambda **_kwargs: _Agent(),
    )

    answers = iter([KeyboardInterrupt(), EOFError()])

    class _FakeReader:
        def read_line(self, _prompt):
            value = next(answers)
            if isinstance(value, BaseException):
                raise value
            return value

    monkeypatch.setattr("data_juicer_agents.session_cli._new_line_reader", lambda: _FakeReader())
    args = build_parser().parse_args(["--ui", "plain"])
    code = _run_plain_session(args)
    output = capsys.readouterr().out
    assert code == 0
    assert "No running task to interrupt" in output
    assert "Session ended." in output


def test_run_as_studio_session_calls_agentscope_init_and_stops(monkeypatch):
    seen = {}

    class _UserAgent:
        def __init__(self, _name):
            self.calls = 0

        async def __call__(self):
            self.calls += 1
            return type("Msg", (), {"content": "exit"})()

    class _SessionAgent:
        def __init__(self, **kwargs):
            seen["session_kwargs"] = kwargs

        async def handle_as_studio_turn_async(self, msg, emit_chunk):  # noqa: ARG002
            seen["seen_content"] = getattr(msg, "content", None)
            seen["emit_chunk"] = emit_chunk
            return type(
                "Turn",
                (),
                {
                    "msg": type("Msg", (), {"metadata": {"dj_stop": True}})(),
                    "stop": True,
                    "should_emit_final": False,
                },
            )()

    def _fake_init(**kwargs):
        seen["init_kwargs"] = kwargs

    monkeypatch.setattr("agentscope.init", _fake_init)
    monkeypatch.setattr("agentscope.agent.UserAgent", _UserAgent)
    monkeypatch.setattr("data_juicer_agents.session_cli.DJSessionAgent", _SessionAgent)

    args = argparse.Namespace(
        dataset="a.jsonl",
        export="b.jsonl",
        verbose=True,
        studio_url="http://localhost:4000",
    )
    code = _run_as_studio_session(args)

    assert code == 0
    assert seen["init_kwargs"]["studio_url"] == "http://localhost:4000"
    assert seen["init_kwargs"]["project"] == "data-juicer-agents"
    assert seen["session_kwargs"]["dataset_path"] == "a.jsonl"
    assert seen["session_kwargs"]["export_path"] == "b.jsonl"
    assert seen["session_kwargs"]["verbose"] is True
    assert seen["session_kwargs"]["enable_streaming"] is True
    assert seen["seen_content"] == "exit"
    assert callable(seen["emit_chunk"])


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
    code = _run_as_studio_session(args)

    assert code == 2
    assert "Failed to initialize AgentScope Studio session" in capsys.readouterr().out
