# -*- coding: utf-8 -*-

import json
from pathlib import Path

from data_juicer_agents.cli import main
from data_juicer_agents.capabilities.trace.schema import RunTraceModel


def _write_case(tmp_path: Path) -> Path:
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"text":"hello"}\n', encoding="utf-8")
    out_dir = tmp_path / "out"
    out_dir.mkdir(exist_ok=True)

    cases = tmp_path / "cases.jsonl"
    row = {
        "intent": "clean rag corpus",
        "dataset_path": str(dataset),
        "export_path": str(out_dir / "result.jsonl"),
        "expected_workflow": "rag_cleaning",
    }
    cases.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    return cases


def _mock_planner_calls(monkeypatch):
    from data_juicer_agents.capabilities.plan import service as planner_mod

    monkeypatch.setattr(
        planner_mod,
        "retrieve_operator_candidates",
        lambda **_kwargs: {"candidates": []},
    )
    monkeypatch.setattr(
        planner_mod,
        "call_model_json",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("mock llm unavailable")),
    )


def test_evaluate_retries_and_history(tmp_path: Path, monkeypatch):
    from data_juicer_agents.capabilities.apply import service as executor_mod

    calls = {"n": 0}

    def fake_execute(self, plan, runtime_dir, dry_run=False, timeout_seconds=300, command_override=None):
        calls["n"] += 1
        if calls["n"] == 1:
            trace = RunTraceModel(
                run_id="run_fail",
                plan_id=plan.plan_id,
                start_time="2026-02-10T00:00:00+00:00",
                end_time="2026-02-10T00:00:01+00:00",
                duration_seconds=1.0,
                model_info={"executor": "fake"},
                retrieval_mode="workflow-first",
                selected_workflow=plan.workflow,
                generated_recipe_path=str(runtime_dir / "x.yaml"),
                command="fake",
                status="failed",
                artifacts={"export_path": plan.export_path},
                error_type="command_failed",
                error_message="boom",
                retry_level="low",
                next_actions=["retry"],
            )
            return trace, 1, "", "boom"

        trace = RunTraceModel(
            run_id="run_ok",
            plan_id=plan.plan_id,
            start_time="2026-02-10T00:00:00+00:00",
            end_time="2026-02-10T00:00:01+00:00",
            duration_seconds=1.0,
            model_info={"executor": "fake"},
            retrieval_mode="workflow-first",
            selected_workflow=plan.workflow,
            generated_recipe_path=str(runtime_dir / "x.yaml"),
            command="fake",
            status="success",
            artifacts={"export_path": plan.export_path},
            error_type="none",
            error_message="",
            retry_level="none",
            next_actions=[],
        )
        return trace, 0, "ok", ""

    monkeypatch.setattr(executor_mod.ApplyUseCase, "execute", fake_execute)

    cases = _write_case(tmp_path)
    report = tmp_path / "report.json"
    history = tmp_path / "history.jsonl"

    _mock_planner_calls(monkeypatch)
    monkeypatch.chdir(tmp_path)
    code = main(
        [
            "evaluate",
            "--cases",
            str(cases),
            "--output",
            str(report),
            "--execute",
            "run",
            "--retries",
            "1",
            "--jobs",
            "1",
            "--history-file",
            str(history),
        ],
    )

    assert code == 0
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["summary"]["retry_used_cases"] == 1
    assert data["summary"]["execution_success_rate"] == 1.0
    assert history.exists()
    lines = history.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1


def test_evaluate_jobs_must_be_positive(tmp_path: Path, monkeypatch):
    cases = _write_case(tmp_path)
    monkeypatch.chdir(tmp_path)

    code = main([
        "evaluate",
        "--cases",
        str(cases),
        "--jobs",
        "0",
    ])
    assert code == 2


def test_evaluate_failure_buckets_for_misroute(tmp_path: Path, monkeypatch):
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"text":"hello"}\n', encoding="utf-8")
    out_dir = tmp_path / "out"
    out_dir.mkdir(exist_ok=True)

    cases = tmp_path / "cases_misroute.jsonl"
    row = {
        "intent": "clean rag corpus",
        "dataset_path": str(dataset),
        "export_path": str(out_dir / "result.jsonl"),
        "expected_workflow": "multimodal_dedup",
    }
    cases.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")

    report = tmp_path / "report_misroute.json"
    _mock_planner_calls(monkeypatch)
    monkeypatch.chdir(tmp_path)
    code = main(
        [
            "evaluate",
            "--cases",
            str(cases),
            "--output",
            str(report),
            "--execute",
            "none",
            "--failure-top-k",
            "3",
            "--no-history",
        ],
    )
    assert code == 0

    data = json.loads(report.read_text(encoding="utf-8"))
    buckets = data["summary"]["failure_buckets_topk"]
    assert len(buckets) >= 1
    assert buckets[0]["bucket"] == "misroute"
