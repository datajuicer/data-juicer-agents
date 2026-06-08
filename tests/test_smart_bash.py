# -*- coding: utf-8 -*-
"""Tests for SmartBash harness — parser, diagnostics, and execute_bash tool."""

from __future__ import annotations

from unittest.mock import patch


# ============================================================================
# Parser tests
# ============================================================================


class TestDetectFlavour:
    def test_recognised_commands(self):
        from data_juicer_agents.tools.process._shared.parser import detect_flavour
        assert detect_flavour("grep -r 'pat' .") == "grep"
        assert detect_flavour("egrep -i foo bar") == "egrep"
        assert detect_flavour("rg --type py TODO") == "rg"
        assert detect_flavour("find . -name '*.py'") == "find"
        assert detect_flavour("fd pattern") == "fd"
        assert detect_flavour("tail -n 50 log.txt") == "tail"
        assert detect_flavour("head -20 data.csv") == "head"
        assert detect_flavour("cat README.md") == "cat"
        assert detect_flavour("wc -l *.py") == "wc"
        assert detect_flavour("ls -la /tmp") == "ls"

    def test_sudo_prefix_stripped(self):
        from data_juicer_agents.tools.process._shared.parser import detect_flavour
        assert detect_flavour("sudo grep pattern /var/log/syslog") == "grep"
        assert detect_flavour("sudo find / -name foo") == "find"

    def test_pipe_uses_last_command(self):
        from data_juicer_agents.tools.process._shared.parser import detect_flavour
        assert detect_flavour("grep foo | wc -l") == "wc"
        assert detect_flavour("cat log.txt | grep ERROR | head -20") == "head"
        assert detect_flavour("find . -name '*.py' | xargs grep TODO") == "grep"

    def test_unknown_and_empty(self):
        from data_juicer_agents.tools.process._shared.parser import detect_flavour
        assert detect_flavour("mycustomtool --flag") == "mycustomtool"
        assert detect_flavour("") == "unknown"
        assert detect_flavour("   ") == "unknown"


class TestParseOutput:
    def test_grep_with_matches(self):
        from data_juicer_agents.tools.process._shared.parser import parse_output
        r = parse_output(
            command="grep def *.py",
            returncode=0,
            stdout="foo.py:def bar():\nbaz.py:def qux():",
            stderr="",
        )
        assert r.flavour == "grep"
        assert r.ok is True
        assert r.count == 2
        assert "matched" in r.summary
        assert "foo.py:def bar():" in r.items[0]

    def test_grep_no_matches(self):
        from data_juicer_agents.tools.process._shared.parser import parse_output
        r = parse_output(command="grep nonexistent *.py", returncode=1, stdout="", stderr="")
        assert r.flavour == "grep"
        assert r.ok is False
        assert r.count == 0
        assert "no matches" in r.summary

    def test_grep_error_returncode_preserved(self):
        from data_juicer_agents.tools.process._shared.parser import parse_output
        r = parse_output(
            command="grep '[invalid' *.py",
            returncode=2,
            stdout="",
            stderr="grep: Invalid regular expression",
        )
        assert r.flavour == "grep"
        assert r.ok is False
        assert r.returncode == 2

    def test_grep_truncation(self):
        from data_juicer_agents.tools.process._shared.parser import parse_output
        lines = [f"file_{i}.py:line {i}" for i in range(100)]
        r = parse_output(command="grep x *", returncode=0, stdout="\n".join(lines), stderr="")
        assert r.truncated is True
        assert r.count == 100
        assert len(r.items) == 30  # _MAX_ITEMS

    def test_find_results_and_empty(self):
        from data_juicer_agents.tools.process._shared.parser import parse_output
        r = parse_output(
            command="find . -name '*.py'", returncode=0,
            stdout="./a.py\n./b.py\n./sub/c.py", stderr="",
        )
        assert r.flavour == "find"
        assert r.ok is True
        assert r.count == 3
        assert len(r.items) == 3

        empty = parse_output(command="find . -name '*.zzz'", returncode=0, stdout="", stderr="")
        assert empty.flavour == "find"
        assert empty.ok is True
        assert empty.count == 0

    def test_listing_flavours(self):
        from data_juicer_agents.tools.process._shared.parser import parse_output
        for cmd, flavour, stdout, expected_count in [
            ("tail -n 5 log.txt", "tail", "l1\nl2\nl3\nl4\nl5", 5),
            ("head -3 data.csv", "head", "h1,h2\n1,2\n3,4", 3),
            ("cat README.md", "cat", "line1\nline2", 2),
            ("ls -la", "ls", "a.py\nb.py\nc.py", 3),
        ]:
            r = parse_output(command=cmd, returncode=0, stdout=stdout, stderr="")
            assert r.flavour == flavour
            assert r.ok is True
            assert r.count == expected_count

    def test_ls_truncated(self):
        from data_juicer_agents.tools.process._shared.parser import parse_output
        r = parse_output(
            command="ls", returncode=0,
            stdout="\n".join(f"file_{i}" for i in range(100)), stderr="",
        )
        assert r.truncated is True
        assert r.count == 100

    def test_wc_summary(self):
        from data_juicer_agents.tools.process._shared.parser import parse_output
        r = parse_output(command="wc -l *.py", returncode=0, stdout="  42 total", stderr="")
        assert r.flavour == "wc"
        assert "42" in r.summary

    def test_generic_success_and_failure(self):
        from data_juicer_agents.tools.process._shared.parser import parse_output
        ok = parse_output(command="mycli status", returncode=0, stdout="OK", stderr="")
        assert ok.flavour == "mycli"
        assert ok.ok is True
        assert "exited with code 0" in ok.summary

        fail = parse_output(command="mycli fail", returncode=1, stdout="", stderr="boom")
        assert fail.flavour == "mycli"
        assert fail.ok is False
        assert "exited with code 1" in fail.summary

    def test_char_truncation(self):
        from data_juicer_agents.tools.process._shared.parser import parse_output
        r = parse_output(command="somecmd", returncode=0, stdout="x" * 10000, stderr="")
        assert r.truncated is True
        assert len(r.stdout) <= 8000


# ============================================================================
# Diagnostics tests
# ============================================================================


class TestDiagnose:
    def test_stderr_patterns(self):
        from data_juicer_agents.tools.process._shared.diagnostics import diagnose

        diag, sugg = diagnose(flavour="grep", returncode=2, stdout="",
                              stderr="grep: /var/log/auth.log: Permission denied")
        assert "permission" in diag.lower()
        assert "sudo" in sugg.lower() or "different" in sugg.lower()

        diag, _ = diagnose(flavour="cat", returncode=1, stdout="",
                           stderr="Read-only file system")
        assert "read-only" in diag.lower()

    def test_exit_codes(self):
        from data_juicer_agents.tools.process._shared.diagnostics import diagnose

        diag, _ = diagnose(flavour="find", returncode=1, stdout="",
                           stderr="No such file or directory")
        assert "not found" in diag.lower()

        diag, sugg = diagnose(flavour="grep", returncode=127, stdout="",
                              stderr="bash: rg: command not found")
        assert "not found" in diag.lower()
        assert "install" in sugg.lower() or "alternative" in sugg.lower()

        diag, sugg = diagnose(flavour="find", returncode=124, stdout="", stderr="")
        assert "timed out" in diag.lower()
        assert "scope" in sugg.lower() or "reduce" in sugg.lower()

        diag, _ = diagnose(flavour="grep", returncode=137, stdout="", stderr="")
        assert "kill" in diag.lower() or "oom" in diag.lower()

        diag, _ = diagnose(flavour="tail", returncode=130, stdout="", stderr="")
        assert "interrupt" in diag.lower()

    def test_empty_stdout_hints(self):
        from data_juicer_agents.tools.process._shared.diagnostics import diagnose

        diag, sugg = diagnose(flavour="grep", returncode=1, stdout="", stderr="")
        assert "no matches" in diag.lower()
        assert "broaden" in sugg.lower() or "pattern" in sugg.lower()

        diag, _ = diagnose(flavour="grep", returncode=0, stdout="", stderr="")
        assert "no matches" in diag.lower() or "no output" in diag.lower()


# ============================================================================
# execute_bash logic + tool spec
# ============================================================================


def _patch_subprocess(monkeypatch, payload):
    monkeypatch.setattr(
        "data_juicer_agents.tools.process.execute_bash.logic.run_interruptible_subprocess",
        lambda cmd, timeout_sec, shell: payload,
    )


class TestExecuteBashLogic:
    def test_missing_command(self):
        from data_juicer_agents.tools.process.execute_bash.logic import execute_bash
        r = execute_bash(command="", timeout=120)
        assert r["ok"] is False
        assert r["error_type"] == "missing_required"

    def test_grep_success(self, monkeypatch):
        from data_juicer_agents.tools.process.execute_bash.logic import execute_bash
        _patch_subprocess(monkeypatch, {
            "ok": True, "returncode": 0,
            "stdout": "a.py:def foo():\nb.py:def bar():", "stderr": "",
        })
        r = execute_bash(command="grep def *.py")
        assert r["ok"] is True
        assert r["flavour"] == "grep"
        assert r["count"] == 2
        assert len(r["items"]) == 2

    def test_grep_no_matches_diagnosis(self, monkeypatch):
        from data_juicer_agents.tools.process.execute_bash.logic import execute_bash
        _patch_subprocess(monkeypatch, {
            "ok": False, "returncode": 1, "stdout": "", "stderr": "",
        })
        r = execute_bash(command="grep nonexistent *")
        assert r["ok"] is False
        assert "no matches" in r["diagnosis"].lower()
        assert r["suggestion"]

    def test_permission_denied_diagnosis(self, monkeypatch):
        from data_juicer_agents.tools.process.execute_bash.logic import execute_bash
        _patch_subprocess(monkeypatch, {
            "ok": False, "returncode": 2, "stdout": "",
            "stderr": "grep: /etc/shadow: Permission denied",
        })
        r = execute_bash(command="grep root /etc/shadow")
        assert r["ok"] is False
        assert "permission" in r["diagnosis"].lower()
        assert r["suggestion"]

    def test_command_not_found(self, monkeypatch):
        from data_juicer_agents.tools.process.execute_bash.logic import execute_bash
        _patch_subprocess(monkeypatch, {
            "ok": False, "returncode": 127, "stdout": "",
            "stderr": "bash: unknowncmd: command not found",
        })
        r = execute_bash(command="unknowncmd --flag")
        assert r["ok"] is False
        assert "not found" in r["diagnosis"].lower()


class TestToolSpec:
    def test_tool_registered_with_expected_metadata(self):
        from data_juicer_agents.core.tool.catalog import load_tool_specs_for_group
        specs = load_tool_specs_for_group("process")
        names = [s.name for s in specs]
        assert "execute_bash" in names
        spec = next(s for s in specs if s.name == "execute_bash")
        assert "process" in spec.tags
        assert "execute" in spec.tags
        assert spec.effects == "execute"
        assert spec.confirmation == "recommended"

    def test_tool_executor_success(self):
        from data_juicer_agents.core.tool import ToolContext
        from data_juicer_agents.tools.process.execute_bash.input import ExecuteBashInput
        from data_juicer_agents.tools.process.execute_bash.tool import _execute_bash

        with patch(
            "data_juicer_agents.tools.process.execute_bash.logic.run_interruptible_subprocess",
            return_value={
                "ok": True, "returncode": 0,
                "stdout": "a.py:foo\nb.py:bar", "stderr": "",
            },
        ):
            result = _execute_bash(ToolContext(), ExecuteBashInput(command="grep foo *.py"))
        assert result.ok is True
        assert "matched" in result.summary
        assert result.data["flavour"] == "grep"

    def test_tool_executor_failure_with_next_actions(self):
        from data_juicer_agents.core.tool import ToolContext
        from data_juicer_agents.tools.process.execute_bash.input import ExecuteBashInput
        from data_juicer_agents.tools.process.execute_bash.tool import _execute_bash

        with patch(
            "data_juicer_agents.tools.process.execute_bash.logic.run_interruptible_subprocess",
            return_value={
                "ok": False, "returncode": 127, "stdout": "",
                "stderr": "command not found",
            },
        ):
            result = _execute_bash(ToolContext(), ExecuteBashInput(command="nope"))
        assert result.ok is False
        assert result.next_actions
        assert any("install" in a.lower() or "alternative" in a.lower() for a in result.next_actions)

    def test_tool_executor_missing_command(self):
        from data_juicer_agents.core.tool import ToolContext
        from data_juicer_agents.tools.process.execute_bash.input import ExecuteBashInput
        from data_juicer_agents.tools.process.execute_bash.tool import _execute_bash

        result = _execute_bash(ToolContext(), ExecuteBashInput(command=""))
        assert result.ok is False
        assert result.error_type == "missing_required"
