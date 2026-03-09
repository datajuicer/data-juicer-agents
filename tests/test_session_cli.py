# -*- coding: utf-8 -*-

import time

import pytest

from data_juicer_agents.session_cli import _run_plain_session
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
