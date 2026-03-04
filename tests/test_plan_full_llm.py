# -*- coding: utf-8 -*-

from pathlib import Path

import yaml

from data_juicer_agents.cli import main


def test_plan_command_llm_full_plan(tmp_path: Path, monkeypatch):
    from data_juicer_agents.capabilities.plan import service as planner_mod
    from data_juicer_agents.capabilities.plan import validation as validator_mod

    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"text":"hello world"}\n', encoding="utf-8")

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    export_file = out_dir / "result.jsonl"
    plan_file = tmp_path / "plan_full_llm.yaml"

    monkeypatch.setattr(
        planner_mod.PlanUseCase,
        "_request_full_plan",
        lambda self, **_kwargs: {
            "workflow": "custom",
            "text_keys": ["text"],
            "operators": [
                {"name": "document_deduplicator", "params": {"lowercase": False}},
            ],
            "risk_notes": ["from llm full plan"],
            "estimation": {"expected_minutes": 3},
        },
    )
    monkeypatch.setattr(
        validator_mod.PlanValidator,
        "llm_review",
        staticmethod(lambda _plan: {"errors": [], "warnings": []}),
    )

    monkeypatch.chdir(tmp_path)
    code = main(
        [
            "plan",
            "generate full plan with llm",
            "--dataset",
            str(dataset),
            "--export",
            str(export_file),
            "--output",
            str(plan_file),
        ],
    )

    assert code == 0
    assert plan_file.exists()

    plan_data = yaml.safe_load(plan_file.read_text(encoding="utf-8"))
    assert plan_data["workflow"] == "custom"
    assert plan_data["operators"][0]["name"] == "document_deduplicator"


def test_plan_command_llm_full_forces_custom_workflow(tmp_path: Path, monkeypatch):
    from data_juicer_agents.capabilities.plan import service as planner_mod

    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"text":"hello world"}\n', encoding="utf-8")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    export_file = out_dir / "result.jsonl"
    plan_file = tmp_path / "plan_full_llm_forced_custom.yaml"

    monkeypatch.setattr(
        planner_mod.PlanUseCase,
        "_request_full_plan",
        lambda self, **_kwargs: {
            "workflow": "rag_cleaning",
            "text_keys": ["text"],
            "operators": [
                {"name": "document_deduplicator", "params": {}},
            ],
            "risk_notes": [],
            "estimation": {},
        },
    )

    monkeypatch.chdir(tmp_path)
    code = main(
        [
            "plan",
            "deduplicate records",
            "--dataset",
            str(dataset),
            "--export",
            str(export_file),
            "--output",
            str(plan_file),
        ],
    )
    assert code == 0
    plan_data = yaml.safe_load(plan_file.read_text(encoding="utf-8"))
    assert plan_data["workflow"] == "custom"
    assert plan_data["modality"] == "text"


def test_plan_command_removed_llm_flags_rejected(tmp_path: Path, monkeypatch):
    import pytest

    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"text":"hello world"}\n', encoding="utf-8")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    export_file = out_dir / "result.jsonl"

    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as exc:
        main(
            [
                "plan",
                "flag removed check",
                "--dataset",
                str(dataset),
                "--export",
                str(export_file),
                "--llm-full-plan",
            ],
        )
    assert exc.value.code == 2


def test_plan_command_llm_full_plan_invalid_output(tmp_path: Path, monkeypatch):
    from data_juicer_agents.capabilities.plan import service as planner_mod

    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"text":"hello world"}\n', encoding="utf-8")

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    export_file = out_dir / "result.jsonl"
    plan_file = tmp_path / "plan_full_llm_invalid.yaml"

    # Missing operators -> should fail in llm-full-plan mode.
    monkeypatch.setattr(
        planner_mod.PlanUseCase,
        "_request_full_plan",
        lambda self, **_kwargs: {
            "workflow": "custom",
            "text_keys": ["text"],
            "risk_notes": [],
            "estimation": {},
        },
    )

    monkeypatch.chdir(tmp_path)
    code = main(
        [
            "plan",
            "invalid llm plan output",
            "--dataset",
            str(dataset),
            "--export",
            str(export_file),
            "--output",
            str(plan_file),
        ],
    )
    assert code == 2
    assert not plan_file.exists()


def test_plan_command_llm_full_plan_rejects_unknown_operator(tmp_path: Path, monkeypatch):
    from data_juicer_agents.capabilities.plan import service as planner_mod
    from data_juicer_agents.capabilities.plan import validation as validator_mod

    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"text":"hello world"}\n', encoding="utf-8")

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    export_file = out_dir / "result.jsonl"
    plan_file = tmp_path / "plan_full_llm_dedup.yaml"

    monkeypatch.setattr(
        planner_mod.PlanUseCase,
        "_request_full_plan",
        lambda self, **_kwargs: {
            "workflow": "custom",
            "text_keys": ["text"],
            "operators": [
                {"name": "non_existing_operator_for_test", "params": {}},
            ],
            "risk_notes": [],
            "estimation": {},
        },
    )
    monkeypatch.setattr(
        validator_mod,
        "get_available_operator_names",
        lambda: {"document_deduplicator", "text_length_filter"},
    )

    monkeypatch.chdir(tmp_path)
    code = main(
        [
            "plan",
            "deduplication",
            "--dataset",
            str(dataset),
            "--export",
            str(export_file),
            "--output",
            str(plan_file),
        ],
    )

    assert code == 2
    assert not plan_file.exists()


def test_plan_command_llm_full_normalizes_operator_name(tmp_path: Path, monkeypatch):
    from data_juicer_agents.capabilities.plan import service as planner_mod
    from data_juicer_agents.capabilities.plan import validation as validator_mod

    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"text":"hello world"}\n', encoding="utf-8")

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    export_file = out_dir / "result.jsonl"
    plan_file = tmp_path / "plan_full_llm_normalized.yaml"

    monkeypatch.setattr(
        planner_mod.PlanUseCase,
        "_request_full_plan",
        lambda self, **_kwargs: {
            "workflow": "custom",
            "text_keys": ["text"],
            "operators": [
                {"name": "DocumentMinHashDeduplicator", "params": {}},
            ],
            "risk_notes": [],
            "estimation": {},
        },
    )
    monkeypatch.setattr(
        planner_mod,
        "get_available_operator_names",
        lambda: {"document_minhash_deduplicator", "text_length_filter"},
    )
    monkeypatch.setattr(
        validator_mod,
        "get_available_operator_names",
        lambda: {"document_minhash_deduplicator", "text_length_filter"},
    )

    monkeypatch.chdir(tmp_path)
    code = main(
        [
            "plan",
            "deduplication",
            "--dataset",
            str(dataset),
            "--export",
            str(export_file),
            "--output",
            str(plan_file),
        ],
    )

    assert code == 0
    plan_data = yaml.safe_load(plan_file.read_text(encoding="utf-8"))
    assert plan_data["operators"][0]["name"] == "document_minhash_deduplicator"
