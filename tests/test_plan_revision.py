# -*- coding: utf-8 -*-

import json
from pathlib import Path

import yaml

from data_juicer_agents.cli import main
from data_juicer_agents.capabilities.plan.schema import OperatorStep, PlanModel


def test_plan_revision_uses_base_plan_defaults(tmp_path: Path, monkeypatch):
    from data_juicer_agents.capabilities.plan import service as planner_mod
    from data_juicer_agents.capabilities.plan import validation as validator_mod

    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"text":"hello world"}\n', encoding="utf-8")
    export_file = tmp_path / "out.jsonl"

    base_plan = PlanModel(
        plan_id="plan_base_001",
        user_intent="clean corpus",
        workflow="rag_cleaning",
        dataset_path=str(dataset),
        export_path=str(export_file),
        modality="text",
        text_keys=["text"],
        operators=[OperatorStep(name="text_length_filter", params={"min_len": 3})],
    )
    base_file = tmp_path / "base_plan.yaml"
    base_file.write_text(yaml.safe_dump(base_plan.to_dict(), sort_keys=False), encoding="utf-8")

    monkeypatch.setattr(
        planner_mod,
        "call_model_json",
        lambda _model, _prompt, **_kwargs: {},
    )
    monkeypatch.setattr(
        validator_mod.PlanValidator,
        "llm_review",
        staticmethod(lambda _plan: {"errors": [], "warnings": []}),
    )

    revised_file = tmp_path / "revised_plan.yaml"
    monkeypatch.chdir(tmp_path)
    code = main(
        [
            "plan",
            "tighten cleaning constraints",
            "--base-plan",
            str(base_file),
            "--output",
            str(revised_file),
        ]
    )

    assert code == 0
    data = yaml.safe_load(revised_file.read_text(encoding="utf-8"))
    assert data["parent_plan_id"] is None
    assert data["revision"] == 1
    assert data["template_source_plan_id"] == "plan_base_001"
    assert data["dataset_path"] == str(dataset)
    assert data["export_path"] == str(export_file)
    assert data["user_intent"] == "tighten cleaning constraints"
    assert data["change_summary"]


def test_plan_revision_with_from_run_id_context(tmp_path: Path, monkeypatch):
    from data_juicer_agents.capabilities.plan import service as planner_mod
    from data_juicer_agents.capabilities.plan import validation as validator_mod

    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"text":"hello world"}\n', encoding="utf-8")
    export_file = tmp_path / "out.jsonl"

    base_plan = PlanModel(
        plan_id="plan_base_ctx",
        user_intent="dedup corpus",
        workflow="custom",
        dataset_path=str(dataset),
        export_path=str(export_file),
        modality="text",
        text_keys=["text"],
        operators=[OperatorStep(name="document_deduplicator", params={"lowercase": False})],
    )
    base_file = tmp_path / "base_ctx.yaml"
    base_file.write_text(yaml.safe_dump(base_plan.to_dict(), sort_keys=False), encoding="utf-8")

    trace_dir = tmp_path / ".djx"
    trace_dir.mkdir(parents=True, exist_ok=True)
    run_payload = {
        "run_id": "run_fail_ctx",
        "plan_id": "plan_base_ctx",
        "status": "failed",
        "selected_workflow": "custom",
        "duration_seconds": 10.0,
        "error_type": "unsupported_operator",
        "error_message": "unsupported operator",
    }
    (trace_dir / "runs.jsonl").write_text(
        json.dumps(run_payload, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    def fake_call_model_json(_model: str, prompt: str, **_kwargs):
        assert "run_fail_ctx" in prompt
        return {
            "operators": [
                {"name": "document_minhash_deduplicator", "params": {"tokenization": "word"}},
            ],
            "change_summary": ["switch dedup strategy after unsupported operator failure"],
        }

    monkeypatch.setattr(planner_mod, "call_model_json", fake_call_model_json)
    monkeypatch.setattr(
        validator_mod.PlanValidator,
        "llm_review",
        staticmethod(lambda _plan: {"errors": [], "warnings": []}),
    )

    revised_file = tmp_path / "revised_ctx.yaml"
    monkeypatch.chdir(tmp_path)
    code = main(
        [
            "plan",
            "fix previous failure",
            "--base-plan",
            str(base_file),
            "--from-run-id",
            "run_fail_ctx",
            "--output",
            str(revised_file),
        ]
    )
    assert code == 0

    data = yaml.safe_load(revised_file.read_text(encoding="utf-8"))
    assert data["parent_plan_id"] is None
    assert data["revision"] == 1
    assert data["template_source_plan_id"] == "plan_base_ctx"
    assert data["operators"][0]["name"] == "document_minhash_deduplicator"
    assert data["change_summary"] == [
        "switch dedup strategy after unsupported operator failure"
    ]
