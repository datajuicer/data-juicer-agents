# -*- coding: utf-8 -*-

import io
import sys
import warnings

from data_juicer_agents.tui.noise_filter import FilteredStderr
from data_juicer_agents.tui.noise_filter import install_tui_warning_filters
from data_juicer_agents.tui.noise_filter import sanitize_reasoning_text
from data_juicer_agents.tui.noise_filter import suppress_tui_noise_stderr


def test_filtered_stderr_suppresses_known_noise_lines():
    sink = io.StringIO()
    filtered = FilteredStderr(sink)

    filtered.write(
        "2026-03-04 15:47:47.280 | INFO | data_juicer.ops:timing_context:12 - "
        "Importing operator modules took 1.45 seconds\n"
    )
    filtered.write("<unknown>:43: DeprecationWarning: invalid escape sequence '\\s'\n")
    filtered.write(
        "<frozen importlib._bootstrap>:241: DeprecationWarning: "
        "builtin type SwigPyPacked has no __module__ attribute\n"
    )
    filtered.write("real stderr line\n")
    filtered.flush()

    output = sink.getvalue()
    assert "Importing operator modules took" not in output
    assert "invalid escape sequence" not in output
    assert "SwigPyPacked" not in output
    assert "real stderr line" in output
    assert filtered.suppressed_lines == 3


def test_filtered_stderr_keeps_non_newline_tail():
    sink = io.StringIO()
    filtered = FilteredStderr(sink)

    filtered.write("partial")
    filtered.write(" line")
    filtered.flush()

    assert sink.getvalue() == "partial line"


def test_suppress_tui_noise_stderr_context_filters_only_noise(monkeypatch):
    sink = io.StringIO()
    monkeypatch.setattr(sys, "stderr", sink)

    with suppress_tui_noise_stderr() as filtered:
        sys.stderr.write("Importing operator modules took 1.45 seconds\n")
        sys.stderr.write("important stderr\n")

    output = sink.getvalue()
    assert "Importing operator modules took" not in output
    assert "important stderr" in output
    assert filtered.suppressed_lines == 1


def test_install_tui_warning_filters_suppresses_deprecation_warnings():
    with warnings.catch_warnings(record=True) as records:
        warnings.simplefilter("always")
        install_tui_warning_filters()
        warnings.warn("invalid escape sequence '\\s'", DeprecationWarning)
        warnings.warn(
            "builtin type SwigPyPacked has no __module__ attribute",
            DeprecationWarning,
        )
        warnings.warn("other deprecation", DeprecationWarning)

    messages = [str(item.message) for item in records]
    assert "invalid escape sequence '\\s'" not in messages
    assert "builtin type SwigPyPacked has no __module__ attribute" not in messages
    assert "other deprecation" not in messages


def test_sanitize_reasoning_text_keeps_reflective_summary_block():
    raw = (
        "The task has been successfully completed. Here's a summary:\n"
        "✅ **已完成操作**：\n"
        "1. inspected dataset\n"
        "2. retrieved operators\n"
        "3. applied recipe\n"
    )
    assert sanitize_reasoning_text(raw) == raw.strip()


def test_sanitize_reasoning_text_keeps_normal_reasoning():
    raw = "先查看样本字段，再决定是否调用 inspect_dataset。"
    assert sanitize_reasoning_text(raw) == raw
