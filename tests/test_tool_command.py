# -*- coding: utf-8 -*-

import json
from pathlib import Path

from data_juicer_agents.cli import build_parser, main
from data_juicer_agents.tools.plan import PlanModel


def test_tool_parser_accepts_nested_commands():
    parser = build_parser()
    args = parser.parse_args(["tool", "run", "inspect_dataset", "--input-json", "{}"])
    assert args.command == "tool"
    assert args.tool_action == "run"
    assert args.tool_name == "inspect_dataset"


def test_tool_parser_accepts_global_output_flags_after_subcommand():
    parser = build_parser()
    args = parser.parse_args(["tool", "list", "--debug"])
    assert args.command == "tool"
    assert args.tool_action == "list"
    assert args.output_level == "debug"


def test_tool_list_accepts_global_output_flags_in_main_path(capsys):
    code = main(["tool", "list", "--debug"])
    assert code == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["action"] == "tool_list"


def test_tool_list_returns_json_payload(capsys):
    code = main(["tool", "list", "--tag", "plan"])
    assert code == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["action"] == "tool_list"
    assert payload["count"] > 0
    assert any(item["name"] == "plan_validate" for item in payload["tools"])
    assert all("plan" in item["tags"] for item in payload["tools"])


def test_tool_schema_returns_input_schema(capsys):
    code = main(["tool", "schema", "inspect_dataset"])
    assert code == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["tool"]["name"] == "inspect_dataset"
    assert payload["input_schema"]["properties"]["dataset_path"]["type"] == "string"


def test_tool_schema_unknown_tool_returns_exit_2(capsys):
    code = main(["tool", "schema", "missing_tool"])
    assert code == 2

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["error_type"] == "tool_not_found"


def test_tool_run_read_tool_success(tmp_path: Path, capsys):
    dataset = tmp_path / "data.jsonl"
    dataset.write_text('{"text": "hello world"}\n', encoding="utf-8")

    code = main(
        [
            "tool",
            "run",
            "inspect_dataset",
            "--input-json",
            json.dumps({"dataset_path": str(dataset), "sample_size": 1}),
        ]
    )
    assert code == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["action"] == "inspect_dataset"
    assert payload["dataset_path"] == str(dataset)


def test_tool_run_write_tool_requires_explicit_confirmation(tmp_path: Path, capsys):
    target = tmp_path / "notes.txt"

    code = main(
        [
            "tool",
            "run",
            "write_text_file",
            "--input-json",
            json.dumps({"file_path": str(target), "content": "hello"}),
        ]
    )
    assert code == 3
    assert not target.exists()

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["error_type"] == "confirmation_required"
    assert payload["tool_name"] == "write_text_file"


def test_tool_run_write_tool_succeeds_with_yes(tmp_path: Path, capsys):
    target = tmp_path / "notes.txt"

    code = main(
        [
            "tool",
            "run",
            "write_text_file",
            "--yes",
            "--input-json",
            json.dumps({"file_path": str(target), "content": "hello"}),
        ]
    )
    assert code == 0
    assert target.read_text(encoding="utf-8") == "hello"

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["file_path"] == str(target)


def test_tool_run_execute_tool_succeeds_with_yes(capsys):
    code = main(
        [
            "tool",
            "run",
            "execute_shell_command",
            "--yes",
            "--input-json",
            json.dumps({"command": "printf hello", "timeout": 5}),
        ]
    )
    assert code == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["stdout"] == "hello"


def test_tool_run_plan_validate_success(tmp_path: Path, capsys):
    dataset = tmp_path / "data.jsonl"
    dataset.write_text('{"text": "hello world"}\n', encoding="utf-8")
    export = tmp_path / "out" / "result.jsonl"
    export.parent.mkdir(parents=True, exist_ok=True)
    plan = PlanModel(
        plan_id="plan_tool_cli_001",
        user_intent="filter short rows",
        modality="text",
        recipe={
            "dataset_path": str(dataset),
            "export_path": str(export),
            "text_keys": ["text"],
            "np": 1,
            "executor_type": "default",
            "process": [{"words_num_filter": {"min_words": 10}}],
        },
    )

    code = main(
        [
            "tool",
            "run",
            "plan_validate",
            "--input-json",
            json.dumps({"plan_payload": plan.to_dict()}),
        ]
    )
    assert code == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["plan_id"] == "plan_tool_cli_001"
    assert payload["operator_names"] == ["words_num_filter"]


def test_tool_run_invalid_json_returns_exit_2(capsys):
    code = main(["tool", "run", "list_system_config", "--input-json", "{not-json}"])
    assert code == 2

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["error_type"] == "invalid_input"


def test_tool_run_validation_error_returns_exit_2(capsys):
    code = main(["tool", "run", "inspect_dataset", "--input-json", json.dumps({})])
    assert code == 2

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["error_type"] == "input_validation_failed"
    assert payload["validation_errors"]


def test_tool_run_tool_failure_returns_exit_4(tmp_path: Path, capsys):
    missing = tmp_path / "missing.txt"
    code = main(
        [
            "tool",
            "run",
            "view_text_file",
            "--input-json",
            json.dumps({"file_path": str(missing)}),
        ]
    )
    assert code == 4

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["error_type"] == "file_not_found"
