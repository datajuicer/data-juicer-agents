# -*- coding: utf-8 -*-

from types import SimpleNamespace


def test_run_tui_session_uses_prompt_session_reader(monkeypatch):
    from data_juicer_agents.tui import app as tui_app

    class _FakeController:
        def __init__(self, **_kwargs):
            self.started = False

        def start(self):
            self.started = True

        def is_turn_running(self):
            return False

        def drain_events(self):
            return []

        def consume_turn_result(self):
            raise AssertionError("consume_turn_result should not be called")

        def submit_turn(self, _message):
            raise AssertionError("submit_turn should not be called")

    prompts = []

    class _FakeReader:
        def read_line(self, _prompt):
            prompts.append(_prompt)
            raise EOFError()

    monkeypatch.setattr(tui_app, "SessionController", _FakeController)
    monkeypatch.setattr(tui_app, "_new_line_reader", lambda: _FakeReader())

    code = tui_app.run_tui_session(
        SimpleNamespace(dataset=None, export=None, verbose=False),
    )

    assert code == 0
    assert prompts == ["\n> "]


def test_run_tui_session_does_not_echo_user_message_as_you_block(monkeypatch):
    from data_juicer_agents.tui import app as tui_app

    class _FakeController:
        def __init__(self, **_kwargs):
            self._submitted = False

        def start(self):
            return None

        def is_turn_running(self):
            return False

        def drain_events(self):
            return []

        def consume_turn_result(self):
            from data_juicer_agents.capabilities.session.orchestrator import SessionReply

            return SessionReply(text="done")

        def submit_turn(self, message):
            assert message == "hello"
            self._submitted = True

    class _FakeReader:
        def __init__(self):
            self._answers = iter(["hello", EOFError()])

        def read_line(self, _prompt):
            value = next(self._answers)
            if isinstance(value, BaseException):
                raise value
            return value

    recorded = []

    def _fake_flush(console, state, cursor):
        recorded.append([(item.kind, item.title, item.text) for item in state.timeline])
        return len(state.timeline)

    monkeypatch.setattr(tui_app, "SessionController", _FakeController)
    monkeypatch.setattr(tui_app, "_new_line_reader", lambda: _FakeReader())
    monkeypatch.setattr(tui_app, "_flush_timeline", _fake_flush)

    code = tui_app.run_tui_session(
        SimpleNamespace(dataset=None, export=None, verbose=False),
    )

    assert code == 0
    all_items = [item for snapshot in recorded for item in snapshot]
    assert not any(kind == "user" and title == "you" for kind, title, _text in all_items)
    assert any(kind == "assistant" and text == "done" for kind, _title, text in all_items)
