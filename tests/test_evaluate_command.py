# -*- coding: utf-8 -*-

import json
from pathlib import Path

from data_juicer_agents.cli import main


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


def test_evaluate_command_generates_report(tmp_path: Path, monkeypatch):
    cases = _write_case(tmp_path)
    report = tmp_path / "report.json"
    errors = tmp_path / "errors.json"

    _mock_planner_calls(monkeypatch)
    monkeypatch.chdir(tmp_path)
    code = main(
        [
            "evaluate",
            "--cases",
            str(cases),
            "--output",
            str(report),
            "--errors-output",
            str(errors),
        ],
    )

    assert code == 0
    assert report.exists()
    assert errors.exists()

    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["summary"]["total"] == 1
    assert data["summary"]["task_success_rate"] == 1.0
    assert data["summary"]["execution_mode"] == "none"
    assert data["summary"]["error_case_count"] == 0


def test_evaluate_command_dry_run_execution(tmp_path: Path, monkeypatch):
    cases = _write_case(tmp_path)
    report = tmp_path / "report_dry.json"

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
            "dry-run",
        ],
    )

    assert code == 0
    assert (tmp_path / ".djx" / "runs.jsonl").exists()

    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["summary"]["execution_mode"] == "dry-run"
    assert data["summary"]["execution_success_rate"] == 1.0
