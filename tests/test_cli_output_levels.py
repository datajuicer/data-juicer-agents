# -*- coding: utf-8 -*-

from pathlib import Path

import yaml

from data_juicer_agents.cli import build_parser, main
from data_juicer_agents.capabilities.plan.schema import OperatorStep, PlanModel
from data_juicer_agents.capabilities.trace.schema import RunTraceModel


def _write_plan_file(tmp_path: Path) -> Path:
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"text":"hello"}\n', encoding="utf-8")
    output = tmp_path / "output.jsonl"
    plan = PlanModel(
        plan_id="plan_output_levels",
        user_intent="clean",
        workflow="rag_cleaning",
        dataset_path=str(dataset),
        export_path=str(output),
        text_keys=["text"],
        operators=[OperatorStep(name="text_length_filter", params={"min_len": 1})],
    )
    path = tmp_path / "plan.yaml"
    path.write_text(yaml.safe_dump(plan.to_dict(), sort_keys=False), encoding="utf-8")
    return path


def _fake_trace(plan_id: str) -> RunTraceModel:
    return RunTraceModel(
        run_id="run_output_levels",
        plan_id=plan_id,
        start_time="2026-03-03T00:00:00Z",
        end_time="2026-03-03T00:00:01Z",
        duration_seconds=1.0,
        model_info={},
        retrieval_mode="none",
        selected_workflow="rag_cleaning",
        generated_recipe_path=".djx/recipes/plan_output_levels.yaml",
        command="dj-process --config .djx/recipes/plan_output_levels.yaml",
        status="success",
        artifacts={},
        error_type="none",
        error_message="",
        retry_level="none",
        next_actions=[],
    )


def test_cli_output_level_parsing():
    parser = build_parser()

    args = parser.parse_args(["plan", "intent", "--dataset", "a.jsonl", "--export", "b.jsonl"])
    assert args.output_level == "quiet"

    args = parser.parse_args(["plan", "intent", "--dataset", "a.jsonl", "--export", "b.jsonl", "--verbose"])
    assert args.output_level == "verbose"

    args = parser.parse_args(["--debug", "plan", "intent", "--dataset", "a.jsonl", "--export", "b.jsonl"])
    assert args.output_level == "debug"


def test_apply_quiet_suppresses_tool_output(tmp_path: Path, monkeypatch, capsys):
    from data_juicer_agents.commands import apply_cmd as apply_mod

    plan_path = _write_plan_file(tmp_path)

    monkeypatch.setattr(
        apply_mod.ApplyUseCase,
        "execute",
        lambda self, **_kwargs: (_fake_trace("plan_output_levels"), 0, "tool stdout", "tool stderr"),
    )
    monkeypatch.chdir(tmp_path)

    code = main(["apply", "--plan", str(plan_path), "--yes"])
    assert code == 0
    output = capsys.readouterr().out
    assert "STDOUT:" not in output
    assert "STDERR:" not in output
    assert "tool stdout" not in output
    assert "tool stderr" not in output
    assert "Run Summary:" in output


def test_apply_verbose_shows_tool_output(tmp_path: Path, monkeypatch, capsys):
    from data_juicer_agents.commands import apply_cmd as apply_mod

    plan_path = _write_plan_file(tmp_path)

    monkeypatch.setattr(
        apply_mod.ApplyUseCase,
        "execute",
        lambda self, **_kwargs: (_fake_trace("plan_output_levels"), 0, "tool stdout", "tool stderr"),
    )
    monkeypatch.chdir(tmp_path)

    code = main(["apply", "--plan", str(plan_path), "--yes", "--verbose"])
    assert code == 0
    output = capsys.readouterr().out
    assert "STDOUT:" in output
    assert "STDERR:" in output
    assert "tool stdout" in output
    assert "tool stderr" in output


def test_apply_debug_shows_trace_payload(tmp_path: Path, monkeypatch, capsys):
    from data_juicer_agents.commands import apply_cmd as apply_mod

    plan_path = _write_plan_file(tmp_path)

    monkeypatch.setattr(
        apply_mod.ApplyUseCase,
        "execute",
        lambda self, **_kwargs: (_fake_trace("plan_output_levels"), 0, "tool stdout", "tool stderr"),
    )
    monkeypatch.chdir(tmp_path)

    code = main(["apply", "--plan", str(plan_path), "--yes", "--debug"])
    assert code == 0
    output = capsys.readouterr().out
    assert "Debug trace payload:" in output
    assert '"run_id": "run_output_levels"' in output
