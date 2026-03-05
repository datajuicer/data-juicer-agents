# -*- coding: utf-8 -*-

import json
from pathlib import Path

from data_juicer_agents.cli import main


def _write_runs(trace_file: Path) -> None:
    rows = [
        {
            "run_id": "run_a1",
            "plan_id": "plan_a",
            "selected_workflow": "rag_cleaning",
            "status": "success",
            "duration_seconds": 1.0,
            "error_type": "none",
        },
        {
            "run_id": "run_a2",
            "plan_id": "plan_a",
            "selected_workflow": "rag_cleaning",
            "status": "failed",
            "duration_seconds": 2.0,
            "error_type": "command_failed",
        },
        {
            "run_id": "run_b1",
            "plan_id": "plan_b",
            "selected_workflow": "custom",
            "status": "success",
            "duration_seconds": 3.0,
            "error_type": "none",
        },
    ]
    trace_file.parent.mkdir(parents=True, exist_ok=True)
    trace_file.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in rows) + "\n",
        encoding="utf-8",
    )


def test_trace_stats_can_filter_by_plan_id(tmp_path: Path, monkeypatch, capsys):
    _write_runs(tmp_path / ".djx" / "runs.jsonl")
    monkeypatch.chdir(tmp_path)

    code = main(["trace", "--stats", "--plan-id", "plan_a"])
    assert code == 0

    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["plan_id"] == "plan_a"
    assert payload["total_runs"] == 2
    assert payload["success_runs"] == 1
    assert payload["failed_runs"] == 1


def test_trace_list_runs_by_plan_id(tmp_path: Path, monkeypatch, capsys):
    _write_runs(tmp_path / ".djx" / "runs.jsonl")
    monkeypatch.chdir(tmp_path)

    code = main(["trace", "--plan-id", "plan_a", "--limit", "1"])
    assert code == 0

    text = capsys.readouterr().out
    assert "Plan ID: plan_a (latest 1 run(s))" in text
    assert "run_a2" in text
    assert "run_a1" not in text
