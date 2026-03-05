# -*- coding: utf-8 -*-

from pathlib import Path

import pytest

from data_juicer_agents.cli import main


def test_apply_timeout_must_be_positive(tmp_path: Path, monkeypatch):
    plan_file = tmp_path / "plan.yaml"
    plan_file.write_text("{}\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    code = main(["apply", "--plan", str(plan_file), "--timeout", "0"])
    assert code == 2


def test_evaluate_timeout_must_be_positive(tmp_path: Path, monkeypatch):
    cases = tmp_path / "cases.jsonl"
    cases.write_text("{}\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    code = main(["evaluate", "--cases", str(cases), "--timeout", "0"])
    assert code == 2


def test_evaluate_failure_top_k_must_be_positive(tmp_path: Path, monkeypatch):
    cases = tmp_path / "cases.jsonl"
    cases.write_text("{}\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    code = main(["evaluate", "--cases", str(cases), "--failure-top-k", "0"])
    assert code == 2


def test_evaluate_planning_mode_conflicts_with_llm_full_alias(tmp_path: Path, monkeypatch):
    cases = tmp_path / "cases.jsonl"
    cases.write_text("{}\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    code = main(
        [
            "evaluate",
            "--cases",
            str(cases),
            "--planning-mode",
            "template-llm",
            "--llm-full-plan",
        ]
    )
    assert code == 2


def test_plan_text_keys_and_image_key_args_removed(tmp_path: Path, monkeypatch):
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text("{}\n", encoding="utf-8")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    export_file = out_dir / "result.jsonl"
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as exc:
        main(
            [
                "plan",
                "intent",
                "--dataset",
                str(dataset),
                "--export",
                str(export_file),
                "--text-keys",
                "text",
            ]
        )
    assert exc.value.code == 2


def test_plan_requires_dataset_export_without_base(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    code = main(["plan", "intent"])
    assert code == 2


def test_plan_from_run_id_requires_base_plan(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    code = main(["plan", "intent", "--from-run-id", "run_x"])
    assert code == 2
