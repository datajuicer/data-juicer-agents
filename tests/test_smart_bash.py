# -*- coding: utf-8 -*-
"""Tests for SmartBash harness — parser, diagnostics, and execute_bash tool."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

# Mock data_juicer before imports
_fake = MagicMock()
sys.modules["data_juicer"] = MagicMock()
sys.modules["data_juicer.tools"] = MagicMock()
sys.modules["data_juicer.tools.op_search"] = _fake
_fake.OPSearcher = MagicMock


# ============================================================================
# Parser tests
# ============================================================================


class TestDetectFlavour:
    def test_grep(self):
        from data_juicer_agents.tools.bash._shared.parser import detect_flavour
        assert detect_flavour("grep -r 'pattern' .") == "grep"
        assert detect_flavour("egrep -i foo bar") == "egrep"
        assert detect_flavour("rg --type py TODO") == "rg"

    def test_find(self):
        from data_juicer_agents.tools.bash._shared.parser import detect_flavour
        assert detect_flavour("find . -name '*.py'") == "find"
        assert detect_flavour("fd pattern") == "fd"

    def test_tail_head_cat(self):
        from data_juicer_agents.tools.bash._shared.parser import detect_flavour
        assert detect_flavour("tail -n 50 log.txt") == "tail"
        assert detect_flavour("head -20 data.csv") == "head"
        assert detect_flavour("cat README.md") == "cat"

    def test_wc_ls(self):
        from data_juicer_agents.tools.bash._shared.parser import detect_flavour
        assert detect_flavour("wc -l *.py") == "wc"
        assert detect_flavour("ls -la /tmp") == "ls"

    def test_sudo_ignored(self):
        from data_juicer_agents.tools.bash._shared.parser import detect_flavour
        assert detect_flavour("sudo grep pattern /var/log/syslog") == "grep"
        assert detect_flavour("sudo find / -name foo") == "find"

    def test_unknown_still_returns_cmd(self):
        from data_juicer_agents.tools.bash._shared.parser import detect_flavour
        assert detect_flavour("mycustomtool --flag") == "mycustomtool"

    def test_empty_returns_unknown(self):
        from data_juicer_agents.tools.bash._shared.parser import detect_flavour
        assert detect_flavour("") == "unknown"
        assert detect_flavour("   ") == "unknown"


class TestParseGrep:
    def test_with_matches(self):
        from data_juicer_agents.tools.bash._shared.parser import parse_output
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
        assert len(r.items) == 2

    def test_no_matches(self):
        from data_juicer_agents.tools.bash._shared.parser import parse_output
        r = parse_output(
            command="grep nonexistent *.py",
            returncode=1,
            stdout="",
            stderr="",
        )
        assert r.flavour == "grep"
        assert r.ok is False
        assert r.count == 0
        assert "no matches" in r.summary

    def test_truncated(self):
        from data_juicer_agents.tools.bash._shared.parser import parse_output
        lines = [f"file_{i}.py:line {i}" for i in range(100)]
        r = parse_output(
            command="grep something *",
            returncode=0,
            stdout="\n".join(lines),
            stderr="",
        )
        assert r.truncated is True
        assert r.count == 100
        assert len(r.items) == 30


class TestParseFind:
    def test_with_results(self):
        from data_juicer_agents.tools.bash._shared.parser import parse_output
        r = parse_output(
            command="find . -name '*.py'",
            returncode=0,
            stdout="./a.py\n./b.py\n./sub/c.py",
            stderr="",
        )
        assert r.flavour == "find"
        assert r.ok is True
        assert r.count == 3
        assert len(r.items) == 3

    def test_empty(self):
        from data_juicer_agents.tools.bash._shared.parser import parse_output
        r = parse_output(
            command="find . -name '*.zzz'",
            returncode=0,
            stdout="",
            stderr="",
        )
        assert r.flavour == "find"
        assert r.ok is True
        assert r.count == 0


class TestParseTail:
    def test_basic(self):
        from data_juicer_agents.tools.bash._shared.parser import parse_output
        r = parse_output(
            command="tail -n 5 log.txt",
            returncode=0,
            stdout="line6\nline7\nline8\nline9\nline10",
            stderr="",
        )
        assert r.flavour == "tail"
        assert r.ok is True
        assert r.count == 5


class TestParseHead:
    def test_basic(self):
        from data_juicer_agents.tools.bash._shared.parser import parse_output
        r = parse_output(
            command="head -3 data.csv",
            returncode=0,
            stdout="h1,h2\n1,2\n3,4",
            stderr="",
        )
        assert r.flavour == "head"
        assert r.ok is True
        assert r.count == 3


class TestParseCat:
    def test_basic(self):
        from data_juicer_agents.tools.bash._shared.parser import parse_output
        r = parse_output(
            command="cat README.md",
            returncode=0,
            stdout="line1\nline2",
            stderr="",
        )
        assert r.flavour == "cat"
        assert r.ok is True
        assert r.count == 2

    def test_empty_file(self):
        from data_juicer_agents.tools.bash._shared.parser import parse_output
        r = parse_output(
            command="cat empty.txt",
            returncode=0,
            stdout="",
            stderr="",
        )
        assert r.flavour == "cat"
        assert r.ok is True
        assert r.count == 0


class TestParseWC:
    def test_line_count(self):
        from data_juicer_agents.tools.bash._shared.parser import parse_output
        r = parse_output(
            command="wc -l *.py",
            returncode=0,
            stdout="  42 total",
            stderr="",
        )
        assert r.flavour == "wc"
        assert r.ok is True
        assert "42" in r.summary


class TestParseLS:
    def test_basic(self):
        from data_juicer_agents.tools.bash._shared.parser import parse_output
        r = parse_output(
            command="ls -la",
            returncode=0,
            stdout="a.py\nb.py\nc.py",
            stderr="",
        )
        assert r.flavour == "ls"
        assert r.ok is True
        assert r.count == 3
        assert len(r.items) == 3

    def test_empty_dir(self):
        from data_juicer_agents.tools.bash._shared.parser import parse_output
        r = parse_output(
            command="ls emptydir",
            returncode=0,
            stdout="",
            stderr="",
        )
        assert r.flavour == "ls"
        assert r.ok is True
        assert r.count == 0

    def test_truncated_ls(self):
        from data_juicer_agents.tools.bash._shared.parser import parse_output
        r = parse_output(
            command="ls",
            returncode=0,
            stdout="\n".join([f"file_{i}" for i in range(100)]),
            stderr="",
        )
        assert r.truncated is True
        assert r.count == 100


class TestParseGeneric:
    def test_unknown_command_success(self):
        from data_juicer_agents.tools.bash._shared.parser import parse_output
        r = parse_output(
            command="mycli status",
            returncode=0,
            stdout="OK",
            stderr="",
        )
        assert r.flavour == "mycli"
        assert r.ok is True
        assert "exited with code 0" in r.summary

    def test_unknown_command_failure(self):
        from data_juicer_agents.tools.bash._shared.parser import parse_output
        r = parse_output(
            command="mycli fail",
            returncode=1,
            stdout="",
            stderr="something went wrong",
        )
        assert r.flavour == "mycli"
        assert r.ok is False
        assert "exited with code 1" in r.summary

    def test_output_truncation(self):
        from data_juicer_agents.tools.bash._shared.parser import parse_output
        big = "x" * 10000
        r = parse_output(
            command="somecmd",
            returncode=0,
            stdout=big,
            stderr="",
        )
        assert r.truncated is True
        assert len(r.stdout) <= 8000


# ============================================================================
# Diagnostics tests
# ============================================================================


class TestDiagnose:
    def test_permission_denied(self):
        from data_juicer_agents.tools.bash._shared.diagnostics import diagnose
        diag, sugg = diagnose(
            flavour="grep",
            returncode=2,
            stdout="",
            stderr="grep: /var/log/auth.log: Permission denied",
        )
        assert "permission" in diag.lower()
        assert "sudo" in sugg.lower() or "different" in sugg.lower()

    def test_file_not_found(self):
        from data_juicer_agents.tools.bash._shared.diagnostics import diagnose
        diag, sugg = diagnose(
            flavour="find",
            returncode=1,
            stdout="",
            stderr="No such file or directory",
        )
        assert "not found" in diag.lower()

    def test_command_not_found(self):
        from data_juicer_agents.tools.bash._shared.diagnostics import diagnose
        diag, sugg = diagnose(
            flavour="grep",
            returncode=127,
            stdout="",
            stderr="bash: rg: command not found",
        )
        assert "not found" in diag.lower()
        assert "install" in sugg.lower() or "alternative" in sugg.lower()

    def test_timeout(self):
        from data_juicer_agents.tools.bash._shared.diagnostics import diagnose
        diag, sugg = diagnose(
            flavour="find",
            returncode=124,
            stdout="",
            stderr="",
        )
        assert "timed out" in diag.lower()
        assert "scope" in sugg.lower() or "reduce" in sugg.lower()

    def test_grep_no_matches_empty_stdout(self):
        from data_juicer_agents.tools.bash._shared.diagnostics import diagnose
        diag, sugg = diagnose(
            flavour="grep",
            returncode=1,
            stdout="",
            stderr="",
        )
        assert "no matches" in diag.lower()
        assert "broaden" in sugg.lower() or "pattern" in sugg.lower()

    def test_success_but_empty(self):
        from data_juicer_agents.tools.bash._shared.diagnostics import diagnose
        diag, sugg = diagnose(
            flavour="grep",
            returncode=0,
            stdout="",
            stderr="",
        )
        assert "no matches" in diag.lower() or "no output" in diag.lower()

    def test_killed_oom(self):
        from data_juicer_agents.tools.bash._shared.diagnostics import diagnose
        diag, sugg = diagnose(
            flavour="grep",
            returncode=137,
            stdout="",
            stderr="",
        )
        assert "kill" in diag.lower() or "oom" in diag.lower()

    def test_interrupted(self):
        from data_juicer_agents.tools.bash._shared.diagnostics import diagnose
        diag, sugg = diagnose(
            flavour="tail",
            returncode=130,
            stdout="",
            stderr="",
        )
        assert "interrupt" in diag.lower()

    def test_read_only_fs(self):
        from data_juicer_agents.tools.bash._shared.diagnostics import diagnose
        diag, sugg = diagnose(
            flavour="cat",
            returncode=1,
            stdout="",
            stderr="Read-only file system",
        )
        assert "read-only" in diag.lower()


# ============================================================================
# execute_bash logic tests (mock subprocess)
# ============================================================================


class TestExecuteBashLogic:
    def test_missing_command(self):
        from data_juicer_agents.tools.bash.execute_bash.logic import execute_bash
        r = execute_bash(command="", timeout=120)
        assert r["ok"] is False
        assert r["error_type"] == "missing_required"

    def test_grep_success(self, monkeypatch):
        from data_juicer_agents.tools.bash.execute_bash.logic import execute_bash

        def fake_subprocess(cmd, timeout_sec, shell):
            return {
                "ok": True,
                "returncode": 0,
                "stdout": "a.py:def foo():\nb.py:def bar():",
                "stderr": "",
                "message": "done",
            }

        monkeypatch.setattr(
            "data_juicer_agents.tools.bash.execute_bash.logic.run_interruptible_subprocess",
            fake_subprocess,
        )
        r = execute_bash(command="grep def *.py")
        assert r["ok"] is True
        assert r["flavour"] == "grep"
        assert r["count"] == 2
        assert len(r["items"]) == 2
        assert "matched" in r["summary"]

    def test_grep_no_matches(self, monkeypatch):
        from data_juicer_agents.tools.bash.execute_bash.logic import execute_bash

        def fake_subprocess(cmd, timeout_sec, shell):
            return {
                "ok": False,
                "returncode": 1,
                "stdout": "",
                "stderr": "",
                "message": "exit 1",
            }

        monkeypatch.setattr(
            "data_juicer_agents.tools.bash.execute_bash.logic.run_interruptible_subprocess",
            fake_subprocess,
        )
        r = execute_bash(command="grep nonexistent *")
        assert r["ok"] is False
        assert r["flavour"] == "grep"
        assert "no matches" in r["diagnosis"].lower()
        assert r["suggestion"]

    def test_find_with_results(self, monkeypatch):
        from data_juicer_agents.tools.bash.execute_bash.logic import execute_bash

        def fake_subprocess(cmd, timeout_sec, shell):
            return {
                "ok": True,
                "returncode": 0,
                "stdout": "./src/a.py\n./src/b.py\n./tests/test_a.py",
                "stderr": "",
                "message": "done",
            }

        monkeypatch.setattr(
            "data_juicer_agents.tools.bash.execute_bash.logic.run_interruptible_subprocess",
            fake_subprocess,
        )
        r = execute_bash(command="find . -name '*.py'")
        assert r["ok"] is True
        assert r["flavour"] == "find"
        assert r["count"] == 3
        assert len(r["items"]) == 3

    def test_permission_denied_diagnosis(self, monkeypatch):
        from data_juicer_agents.tools.bash.execute_bash.logic import execute_bash

        def fake_subprocess(cmd, timeout_sec, shell):
            return {
                "ok": False,
                "returncode": 2,
                "stdout": "",
                "stderr": "grep: /etc/shadow: Permission denied",
                "message": "exit 2",
            }

        monkeypatch.setattr(
            "data_juicer_agents.tools.bash.execute_bash.logic.run_interruptible_subprocess",
            fake_subprocess,
        )
        r = execute_bash(command="grep root /etc/shadow")
        assert r["ok"] is False
        assert "permission" in r["diagnosis"].lower()
        assert r["suggestion"]

    def test_ls_empty_dir(self, monkeypatch):
        from data_juicer_agents.tools.bash.execute_bash.logic import execute_bash

        def fake_subprocess(cmd, timeout_sec, shell):
            return {
                "ok": True,
                "returncode": 0,
                "stdout": "",
                "stderr": "",
                "message": "done",
            }

        monkeypatch.setattr(
            "data_juicer_agents.tools.bash.execute_bash.logic.run_interruptible_subprocess",
            fake_subprocess,
        )
        r = execute_bash(command="ls /empty")
        assert r["ok"] is True
        assert r["flavour"] == "ls"
        assert r["count"] == 0
        assert "empty" in r["diagnosis"].lower() or "listed" in r.get("diagnosis", "").lower()

    def test_command_not_found(self, monkeypatch):
        from data_juicer_agents.tools.bash.execute_bash.logic import execute_bash

        def fake_subprocess(cmd, timeout_sec, shell):
            return {
                "ok": False,
                "returncode": 127,
                "stdout": "",
                "stderr": "bash: unknowncmd: command not found",
                "message": "exit 127",
            }

        monkeypatch.setattr(
            "data_juicer_agents.tools.bash.execute_bash.logic.run_interruptible_subprocess",
            fake_subprocess,
        )
        r = execute_bash(command="unknowncmd --flag")
        assert r["ok"] is False
        assert "not found" in r["diagnosis"].lower()


# ============================================================================
# Tool spec integration tests
# ============================================================================


class TestToolSpec:
    def test_tool_registered_in_catalog(self):
        from data_juicer_agents.core.tool.catalog import load_tool_specs_for_group
        specs = load_tool_specs_for_group("bash")
        names = [s.name for s in specs]
        assert "execute_bash" in names

    def test_tool_has_expected_tags(self):
        from data_juicer_agents.core.tool.catalog import load_tool_specs_for_group
        specs = load_tool_specs_for_group("bash")
        spec = specs[0]
        assert "bash" in spec.tags
        assert "execute" in spec.tags
        assert spec.effects == "execute"
        assert spec.confirmation == "recommended"

    def test_tool_execute_success(self):
        from data_juicer_agents.core.tool import ToolContext
        from data_juicer_agents.tools.bash.execute_bash.tool import EXECUTE_BASH, _execute_bash
        from data_juicer_agents.tools.bash.execute_bash.input import ExecuteBashInput

        with patch(
            "data_juicer_agents.tools.bash.execute_bash.logic.run_interruptible_subprocess",
            return_value={
                "ok": True,
                "returncode": 0,
                "stdout": "a.py:foo\nb.py:bar",
                "stderr": "",
                "message": "done",
            },
        ):
            ctx = ToolContext()
            args = ExecuteBashInput(command="grep foo *.py")
            result = _execute_bash(ctx, args)
            assert result.ok is True
            assert "matched" in result.summary
            assert result.data["flavour"] == "grep"

    def test_tool_execute_failure_with_next_actions(self):
        from data_juicer_agents.core.tool import ToolContext
        from data_juicer_agents.tools.bash.execute_bash.tool import EXECUTE_BASH, _execute_bash
        from data_juicer_agents.tools.bash.execute_bash.input import ExecuteBashInput

        with patch(
            "data_juicer_agents.tools.bash.execute_bash.logic.run_interruptible_subprocess",
            return_value={
                "ok": False,
                "returncode": 127,
                "stdout": "",
                "stderr": "command not found",
                "message": "exit 127",
            },
        ):
            ctx = ToolContext()
            args = ExecuteBashInput(command="nonexistent")
            result = _execute_bash(ctx, args)
            assert result.ok is False
            assert result.next_actions  # should have a suggestion
            assert any("install" in a.lower() or "alternative" in a.lower() for a in result.next_actions)

    def test_tool_execute_missing_command(self):
        from data_juicer_agents.core.tool import ToolContext
        from data_juicer_agents.tools.bash.execute_bash.tool import EXECUTE_BASH, _execute_bash
        from data_juicer_agents.tools.bash.execute_bash.input import ExecuteBashInput

        ctx = ToolContext()
        args = ExecuteBashInput(command="")
        result = _execute_bash(ctx, args)
        assert result.ok is False
        assert result.error_type == "missing_required"
