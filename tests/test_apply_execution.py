# -*- coding: utf-8 -*-

import json
from pathlib import Path

import yaml

from data_juicer_agents.cli import main
from data_juicer_agents.capabilities.plan.schema import OperatorStep, PlanModel
from data_juicer_agents.capabilities.trace.schema import RunTraceModel


def test_apply_dry_run_creates_trace_and_recipe(tmp_path: Path, monkeypatch):
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"text":"hello"}\n', encoding="utf-8")

    output = tmp_path / "output.jsonl"
    plan = PlanModel(
        plan_id="plan_test_apply",
        user_intent="clean",
        workflow="rag_cleaning",
        dataset_path=str(dataset),
        export_path=str(output),
        text_keys=["text"],
        operators=[OperatorStep(name="text_length_filter", params={"min_len": 1})],
    )

    plan_file = tmp_path / "plan.yaml"
    with open(plan_file, "w", encoding="utf-8") as f:
        yaml.safe_dump(plan.to_dict(), f, sort_keys=False)

    monkeypatch.chdir(tmp_path)
    exit_code = main(["apply", "--plan", str(plan_file), "--yes", "--dry-run"])
    assert exit_code == 0
    assert (tmp_path / ".djx" / "runs.jsonl").exists()
    assert (tmp_path / ".djx" / "recipes" / "plan_test_apply.yaml").exists()


def test_apply_prints_trace_command_at_end(tmp_path: Path, monkeypatch, capsys):
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"text":"hello"}\n', encoding="utf-8")

    output = tmp_path / "output.jsonl"
    plan = PlanModel(
        plan_id="plan_test_apply_trace_cmd",
        user_intent="clean",
        workflow="rag_cleaning",
        dataset_path=str(dataset),
        export_path=str(output),
        text_keys=["text"],
        operators=[OperatorStep(name="text_length_filter", params={"min_len": 1})],
    )

    plan_file = tmp_path / "plan.yaml"
    with open(plan_file, "w", encoding="utf-8") as f:
        yaml.safe_dump(plan.to_dict(), f, sort_keys=False)

    monkeypatch.chdir(tmp_path)
    exit_code = main(["apply", "--plan", str(plan_file), "--yes", "--dry-run"])
    assert exit_code == 0

    output_text = capsys.readouterr().out.strip()
    trace_file = tmp_path / ".djx" / "runs.jsonl"
    run_payload = trace_file.read_text(encoding="utf-8").strip().splitlines()[-1]
    run_id = json.loads(run_payload)["run_id"]
    assert "Run Summary:" in output_text
    assert "Trace command: djx trace " in output_text
    assert output_text.endswith(f"Trace command: djx trace {run_id}")


def test_apply_recipe_includes_custom_operator_paths(tmp_path: Path, monkeypatch):
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"text":"hello"}\n', encoding="utf-8")
    output = tmp_path / "output.jsonl"

    custom_pkg = tmp_path / "custom_ops_pkg"
    custom_pkg.mkdir(parents=True, exist_ok=True)
    (custom_pkg / "__init__.py").write_text("", encoding="utf-8")

    plan = PlanModel(
        plan_id="plan_test_custom_path",
        user_intent="custom op",
        workflow="custom",
        dataset_path=str(dataset),
        export_path=str(output),
        custom_operator_paths=[str(custom_pkg)],
        text_keys=["text"],
        operators=[OperatorStep(name="text_length_filter", params={"min_len": 1})],
    )
    plan_file = tmp_path / "plan.yaml"
    with open(plan_file, "w", encoding="utf-8") as f:
        yaml.safe_dump(plan.to_dict(), f, sort_keys=False)

    monkeypatch.chdir(tmp_path)
    exit_code = main(["apply", "--plan", str(plan_file), "--yes", "--dry-run"])
    assert exit_code == 0

    recipe_file = tmp_path / ".djx" / "recipes" / "plan_test_custom_path.yaml"
    recipe = yaml.safe_load(recipe_file.read_text(encoding="utf-8"))
    assert recipe["custom_operator_paths"] == [str(custom_pkg)]


def test_apply_interrupted_does_not_persist_trace(tmp_path: Path, monkeypatch):
    from data_juicer_agents.commands import apply_cmd as apply_mod

    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"text":"hello"}\n', encoding="utf-8")
    output = tmp_path / "output.jsonl"

    plan = PlanModel(
        plan_id="plan_test_interrupted",
        user_intent="custom op",
        workflow="custom",
        dataset_path=str(dataset),
        export_path=str(output),
        text_keys=["text"],
        operators=[OperatorStep(name="text_length_filter", params={"min_len": 1})],
    )
    plan_file = tmp_path / "plan.yaml"
    with open(plan_file, "w", encoding="utf-8") as f:
        yaml.safe_dump(plan.to_dict(), f, sort_keys=False)

    interrupted_trace = RunTraceModel(
        run_id="run_interrupted_x",
        plan_id=plan.plan_id,
        start_time="2026-03-03T00:00:00Z",
        end_time="2026-03-03T00:00:01Z",
        duration_seconds=1.0,
        model_info={},
        retrieval_mode="workflow-first",
        selected_workflow=plan.workflow,
        generated_recipe_path=str(tmp_path / ".djx" / "recipes" / f"{plan.plan_id}.yaml"),
        command="dj-process --config x.yaml",
        status="interrupted",
        artifacts={"export_path": str(output)},
        error_type="interrupted",
        error_message="Interrupted by user.",
        retry_level="none",
        next_actions=[],
    )

    monkeypatch.setattr(
        apply_mod.ApplyUseCase,
        "execute",
        lambda self, **_kwargs: (interrupted_trace, 130, "", "Interrupted by user."),
    )

    monkeypatch.chdir(tmp_path)
    exit_code = main(["apply", "--plan", str(plan_file), "--yes"])
    assert exit_code == 130
    assert not (tmp_path / ".djx" / "runs.jsonl").exists()
