# -*- coding: utf-8 -*-

from pathlib import Path

import yaml

from data_juicer_agents.cli import main
from data_juicer_agents.capabilities.plan.schema import OperatorStep, PlanModel


def test_plan_command_uses_full_llm_mode_by_default(tmp_path: Path, monkeypatch):
    from data_juicer_agents.capabilities.plan import service as planner_mod
    from data_juicer_agents.capabilities.plan import validation as validator_mod

    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"text":"hello world"}\n', encoding="utf-8")

    export_dir = tmp_path / "out"
    export_dir.mkdir()
    export_file = export_dir / "result.jsonl"
    plan_file = tmp_path / "plan.yaml"

    monkeypatch.setattr(
        planner_mod.PlanUseCase,
        "_request_full_plan",
        lambda self, **_kwargs: {
            "workflow": "custom",
            "modality": "text",
            "text_keys": ["text"],
            "operators": [
                {"name": "document_deduplicator", "params": {"lowercase": False}},
            ],
            "risk_notes": [],
            "estimation": {},
        },
    )
    monkeypatch.setattr(
        validator_mod.PlanValidator,
        "llm_review",
        staticmethod(lambda _plan: {"errors": [], "warnings": []}),
    )

    monkeypatch.chdir(tmp_path)
    exit_code = main(
        [
            "plan",
            "clean rag corpus",
            "--dataset",
            str(dataset),
            "--export",
            str(export_file),
            "--output",
            str(plan_file),
        ],
    )

    assert exit_code == 0
    assert plan_file.exists()


def test_plan_command_accepts_custom_operator_paths(tmp_path: Path, monkeypatch):
    from data_juicer_agents.capabilities.plan import service as planner_mod
    from data_juicer_agents.capabilities.plan import validation as validator_mod

    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"text":"hello world"}\n', encoding="utf-8")
    export_file = tmp_path / "result.jsonl"
    plan_file = tmp_path / "plan_custom_path.yaml"
    custom_pkg = tmp_path / "custom_ops_pkg"
    custom_pkg.mkdir(parents=True, exist_ok=True)
    (custom_pkg / "__init__.py").write_text("", encoding="utf-8")

    monkeypatch.setattr(
        planner_mod.PlanUseCase,
        "_request_full_plan",
        lambda self, **_kwargs: {
            "workflow": "custom",
            "modality": "text",
            "text_keys": ["text"],
            "operators": [
                {"name": "document_deduplicator", "params": {"lowercase": False}},
            ],
            "risk_notes": [],
            "estimation": {},
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
            "clean rag corpus",
            "--dataset",
            str(dataset),
            "--export",
            str(export_file),
            "--output",
            str(plan_file),
            "--custom-operator-paths",
            str(custom_pkg),
        ],
    )
    assert code == 0
    import yaml

    payload = yaml.safe_load(plan_file.read_text(encoding="utf-8"))
    assert payload["custom_operator_paths"] == [str(custom_pkg)]


def test_plan_rejects_base_plan_with_from_template(tmp_path: Path, monkeypatch):
    base_plan = PlanModel(
        plan_id="plan_base_conflict_1",
        user_intent="clean corpus",
        workflow="rag_cleaning",
        dataset_path=str(tmp_path / "dataset.jsonl"),
        export_path=str(tmp_path / "out.jsonl"),
        operators=[OperatorStep(name="text_length_filter", params={"min_len": 1})],
    )
    base_file = tmp_path / "base_conflict_1.yaml"
    base_file.write_text(yaml.safe_dump(base_plan.to_dict(), sort_keys=False), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    code = main(
        [
            "plan",
            "conflict check",
            "--base-plan",
            str(base_file),
            "--from-template",
            "rag_cleaning",
        ],
    )
    assert code == 2


def test_plan_rejects_base_plan_with_template_retrieve(tmp_path: Path, monkeypatch):
    base_plan = PlanModel(
        plan_id="plan_base_conflict_2",
        user_intent="clean corpus",
        workflow="rag_cleaning",
        dataset_path=str(tmp_path / "dataset.jsonl"),
        export_path=str(tmp_path / "out.jsonl"),
        operators=[OperatorStep(name="text_length_filter", params={"min_len": 1})],
    )
    base_file = tmp_path / "base_conflict_2.yaml"
    base_file.write_text(yaml.safe_dump(base_plan.to_dict(), sort_keys=False), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    code = main(
        [
            "plan",
            "conflict check",
            "--base-plan",
            str(base_file),
            "--template-retrieve",
        ],
    )
    assert code == 2


def test_plan_from_template_mode_success(tmp_path: Path, monkeypatch):
    from data_juicer_agents.capabilities.plan import service as planner_mod
    from data_juicer_agents.capabilities.plan import validation as validator_mod

    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"text":"hello world"}\n', encoding="utf-8")
    export_file = tmp_path / "out.jsonl"
    plan_file = tmp_path / "plan_from_template.yaml"

    monkeypatch.setattr(planner_mod, "call_model_json", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        planner_mod.PlanUseCase,
        "_request_full_plan",
        lambda self, **_kwargs: (_ for _ in ()).throw(RuntimeError("full-llm should not be called")),
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
            "clean rag data",
            "--dataset",
            str(dataset),
            "--export",
            str(export_file),
            "--from-template",
            "rag_cleaning",
            "--output",
            str(plan_file),
        ],
    )
    assert code == 0
    payload = yaml.safe_load(plan_file.read_text(encoding="utf-8"))
    assert payload["workflow"] == "rag_cleaning"


def test_plan_template_retrieve_fallback_to_full_llm_when_no_match(tmp_path: Path, monkeypatch, capsys):
    from data_juicer_agents.capabilities.plan import service as planner_mod
    from data_juicer_agents.capabilities.plan import validation as validator_mod

    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"text":"hello world"}\n', encoding="utf-8")
    export_file = tmp_path / "out.jsonl"
    plan_file = tmp_path / "plan_template_retrieve_fallback.yaml"

    monkeypatch.setattr(planner_mod, "retrieve_workflow", lambda _intent: None)
    monkeypatch.setattr(
        planner_mod.PlanUseCase,
        "_request_full_plan",
        lambda self, **_kwargs: {
            "workflow": "custom",
            "modality": "text",
            "text_keys": ["text"],
            "operators": [{"name": "document_deduplicator", "params": {}}],
            "risk_notes": [],
            "estimation": {},
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
            "just do something",
            "--dataset",
            str(dataset),
            "--export",
            str(export_file),
            "--template-retrieve",
            "--output",
            str(plan_file),
        ],
    )
    assert code == 0
    payload = yaml.safe_load(plan_file.read_text(encoding="utf-8"))
    assert payload["workflow"] == "custom"
    captured = capsys.readouterr()
    assert "fallback to full-llm" in captured.out


def test_plan_from_template_overrides_template_retrieve(tmp_path: Path, monkeypatch, capsys):
    from data_juicer_agents.capabilities.plan import service as planner_mod
    from data_juicer_agents.capabilities.plan import validation as validator_mod

    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"text":"hello world"}\n', encoding="utf-8")
    export_file = tmp_path / "out.jsonl"
    plan_file = tmp_path / "plan_template_override.yaml"

    monkeypatch.setattr(planner_mod, "call_model_json", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        planner_mod.PlanUseCase,
        "_request_full_plan",
        lambda self, **_kwargs: (_ for _ in ()).throw(RuntimeError("full-llm should not be called")),
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
            "clean rag data",
            "--dataset",
            str(dataset),
            "--export",
            str(export_file),
            "--from-template",
            "rag_cleaning",
            "--template-retrieve",
            "--output",
            str(plan_file),
        ],
    )

    assert code == 0
    captured = capsys.readouterr()
    assert "ignoring --template-retrieve" in captured.out


def test_plan_command_default_disables_llm_review(tmp_path: Path, monkeypatch):
    from data_juicer_agents.capabilities.plan import service as planner_mod
    from data_juicer_agents.capabilities.plan import validation as validator_mod

    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"text":"hello world"}\n', encoding="utf-8")
    export_file = tmp_path / "result.jsonl"
    plan_file = tmp_path / "plan_no_review.yaml"

    monkeypatch.setattr(
        planner_mod.PlanUseCase,
        "_request_full_plan",
        lambda self, **_kwargs: {
            "workflow": "custom",
            "modality": "text",
            "text_keys": ["text"],
            "operators": [
                {"name": "document_deduplicator", "params": {"lowercase": False}},
            ],
            "risk_notes": [],
            "estimation": {},
        },
    )
    monkeypatch.setattr(
        validator_mod.PlanValidator,
        "llm_review",
        staticmethod(lambda _plan: (_ for _ in ()).throw(AssertionError("llm_review should be disabled"))),
    )

    monkeypatch.chdir(tmp_path)
    code = main(
        [
            "plan",
            "clean rag corpus",
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


def test_plan_command_can_enable_llm_review_with_flag(tmp_path: Path, monkeypatch):
    from data_juicer_agents.capabilities.plan import service as planner_mod
    from data_juicer_agents.capabilities.plan import validation as validator_mod

    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"text":"hello world"}\n', encoding="utf-8")
    export_file = tmp_path / "result.jsonl"
    plan_file = tmp_path / "plan_with_review.yaml"
    called = {"review": 0}

    monkeypatch.setattr(
        planner_mod.PlanUseCase,
        "_request_full_plan",
        lambda self, **_kwargs: {
            "workflow": "custom",
            "modality": "text",
            "text_keys": ["text"],
            "operators": [
                {"name": "document_deduplicator", "params": {"lowercase": False}},
            ],
            "risk_notes": [],
            "estimation": {},
        },
    )

    def _review(_plan):
        called["review"] += 1
        return {"errors": [], "warnings": []}

    monkeypatch.setattr(
        validator_mod.PlanValidator,
        "llm_review",
        staticmethod(_review),
    )

    monkeypatch.chdir(tmp_path)
    code = main(
        [
            "plan",
            "clean rag corpus",
            "--dataset",
            str(dataset),
            "--export",
            str(export_file),
            "--output",
            str(plan_file),
            "--llm-review",
        ],
    )
    assert code == 0
    assert called["review"] == 1
