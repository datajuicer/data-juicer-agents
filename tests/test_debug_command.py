# -*- coding: utf-8 -*-

import json

from data_juicer_agents.cli import build_parser, main


def test_debug_parser_accepts_token_usage_command():
    parser = build_parser()
    args = parser.parse_args(
        [
            "debug",
            "token-usage",
            "execute_bash",
            "--input-json",
            '{"ok": true}',
            "--provider",
            "char",
        ]
    )
    assert args.command == "debug"
    assert args.debug_action == "token-usage"
    assert args.tool_name == "execute_bash"
    assert args.provider == "char"


def test_debug_token_usage_char_provider_reports_compaction_savings(capsys):
    payload = {
        "ok": True,
        "action": "execute_bash",
        "returncode": 0,
        "command": "python script.py --verbose",
        "stdout": "line output with diagnostic details " * 500,
        "stderr": "warning details " * 200,
        "message": "command finished",
    }

    code = main(
        [
            "debug",
            "token-usage",
            "execute_bash",
            "--input-json",
            json.dumps(payload),
            "--provider",
            "char",
        ]
    )

    assert code == 0
    result = json.loads(capsys.readouterr().out)
    assert result["ok"] is True
    assert result["action"] == "debug_token_usage"
    assert result["provider"] == "char"
    assert result["tool_name"] == "execute_bash"
    assert result["full_tokens"] > result["compact_tokens"]
    assert result["saved_tokens"] > 0
    assert result["saved_pct"] > 50


def test_debug_token_usage_qwen_missing_key_returns_json_error(monkeypatch, capsys):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("MODELSCOPE_API_TOKEN", raising=False)

    code = main(
        [
            "debug",
            "token-usage",
            "execute_bash",
            "--input-json",
            json.dumps({"ok": True, "action": "execute_bash", "stdout": "hello"}),
            "--provider",
            "qwen",
        ]
    )

    assert code == 4
    result = json.loads(capsys.readouterr().out)
    assert result["ok"] is False
    assert result["action"] == "debug_token_usage"
    assert result["error_type"] == "token_usage_failed"
    assert result["provider"] == "qwen"
    assert "API_KEY" in result["message"]
