# -*- coding: utf-8 -*-

import json
from pathlib import Path

from data_juicer_agents.cli import main


def test_evaluate_llm_full_plan_mode(tmp_path: Path, monkeypatch):
    from data_juicer_agents.capabilities.plan import service as planner_mod

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

    monkeypatch.setattr(
        planner_mod.PlanUseCase,
        "_request_full_plan",
        lambda self, **_kwargs: {
            "workflow": "rag_cleaning",
            "text_keys": ["text"],
            "operators": [
                {"name": "text_length_filter", "params": {"min_len": 1}},
            ],
            "risk_notes": [],
            "estimation": {},
        },
    )

    report = tmp_path / "report.json"
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
            "--planning-mode",
            "full-llm",
            "--no-history",
        ],
    )

    assert code == 0
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["summary"]["plan_valid_rate"] == 1.0
    assert data["summary"]["task_success_rate"] == 1.0
    assert data["summary"]["planning_mode"] == "full_llm"


def test_evaluate_llm_full_plan_alias_still_works(tmp_path: Path, monkeypatch):
    from data_juicer_agents.capabilities.plan import service as planner_mod

    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"text":"hello"}\n', encoding="utf-8")
    out_dir = tmp_path / "out"
    out_dir.mkdir(exist_ok=True)
    cases = tmp_path / "cases_alias.jsonl"
    row = {
        "intent": "clean rag corpus",
        "dataset_path": str(dataset),
        "export_path": str(out_dir / "result.jsonl"),
        "expected_workflow": "rag_cleaning",
    }
    cases.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")

    monkeypatch.setattr(
        planner_mod.PlanUseCase,
        "_request_full_plan",
        lambda self, **_kwargs: {
            "workflow": "rag_cleaning",
            "text_keys": ["text"],
            "operators": [
                {"name": "text_length_filter", "params": {"min_len": 1}},
            ],
            "risk_notes": [],
            "estimation": {},
        },
    )

    report = tmp_path / "report_alias.json"
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
            "--llm-full-plan",
            "--no-history",
        ],
    )
    assert code == 0
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["summary"]["planning_mode"] == "full_llm"
