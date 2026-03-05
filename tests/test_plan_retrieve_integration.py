# -*- coding: utf-8 -*-

from pathlib import Path

from data_juicer_agents.capabilities.plan.service import (
    PlanUseCase,
    PlanningMode,
    default_workflows_dir,
)


def test_template_llm_patch_receives_retrieve_candidates(monkeypatch, tmp_path: Path):
    from data_juicer_agents.capabilities.plan import service as planner_mod

    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"text":"hello"}\n', encoding="utf-8")
    export = tmp_path / "out.jsonl"

    monkeypatch.setattr(
        planner_mod,
        "retrieve_operator_candidates",
        lambda **_kwargs: {
            "candidates": [
                {"operator_name": "document_deduplicator"},
                {"operator_name": "text_length_filter"},
            ]
        },
    )

    def fake_llm(_model: str, prompt: str, **_kwargs):
        assert "retrieved_candidates" in prompt
        assert "document_deduplicator" in prompt
        return {
            "operators": [
                {"name": "document_deduplicator", "params": {"lowercase": False}},
            ],
            "text_keys": ["text"],
        }

    monkeypatch.setattr(planner_mod, "call_model_json", fake_llm)

    planner = PlanUseCase(
        workflows_dir=default_workflows_dir(),
        planning_mode=PlanningMode.TEMPLATE_LLM,
    )
    plan = planner.build_plan(
        user_intent="deduplicate text corpus",
        dataset_path=str(dataset),
        export_path=str(export),
    )

    assert plan.operators[0].name == "document_deduplicator"
    assert planner.last_plan_meta.get("retrieve_candidates") == "2"


def test_llm_full_plan_passes_retrieve_candidates(monkeypatch, tmp_path: Path):
    from data_juicer_agents.capabilities.plan import service as planner_mod

    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"text":"hello"}\n', encoding="utf-8")
    export = tmp_path / "out.jsonl"
    captured = {}

    monkeypatch.setattr(
        planner_mod,
        "retrieve_operator_candidates",
        lambda **_kwargs: {
            "candidates": [
                {"operator_name": "document_deduplicator"},
                {"operator_name": "text_length_filter"},
            ]
        },
    )

    def fake_full_plan(self, **kwargs):
        captured.update(kwargs)
        captured["api_key"] = self.llm_api_key
        captured["base_url"] = self.llm_base_url
        captured["thinking"] = self.llm_thinking
        return {
            "workflow": "custom",
            "modality": "text",
            "text_keys": ["text"],
            "operators": [
                {"name": "document_deduplicator", "params": {}},
            ],
            "risk_notes": [],
            "estimation": {},
        }

    monkeypatch.setattr(
        planner_mod.PlanUseCase,
        "_request_full_plan",
        fake_full_plan,
    )

    planner = PlanUseCase(
        workflows_dir=default_workflows_dir(),
        planning_mode=PlanningMode.FULL_LLM,
        llm_api_key="sk-test",
        llm_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        llm_thinking=True,
    )
    plan = planner.build_plan(
        user_intent="deduplication",
        dataset_path=str(dataset),
        export_path=str(export),
    )
    assert plan.workflow == "custom"
    assert captured.get("retrieved_candidates") == [
        "document_deduplicator",
        "text_length_filter",
    ]
    assert captured.get("api_key") == "sk-test"
    assert captured.get("base_url") == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert captured.get("thinking") is True


def test_build_plan_uses_provided_candidates_without_internal_retrieve(monkeypatch, tmp_path: Path):
    from data_juicer_agents.capabilities.plan import service as planner_mod

    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"text":"hello"}\n', encoding="utf-8")
    export = tmp_path / "out.jsonl"

    def fail_retrieve(**_kwargs):
        raise AssertionError("internal retrieve should be skipped when candidates are provided")

    monkeypatch.setattr(planner_mod, "retrieve_operator_candidates", fail_retrieve)

    seen_prompt = {}

    def fake_llm(_model: str, prompt: str, **_kwargs):
        seen_prompt["prompt"] = prompt
        return {
            "workflow": "custom",
            "modality": "text",
            "text_keys": ["text"],
            "operators": [
                {"name": "document_deduplicator", "params": {}},
            ],
            "risk_notes": [],
            "estimation": {},
        }

    monkeypatch.setattr(planner_mod, "call_model_json", fake_llm)

    planner = PlanUseCase(
        workflows_dir=default_workflows_dir(),
        planning_mode=PlanningMode.FULL_LLM,
    )
    _ = planner.build_plan(
        user_intent="dedup text",
        dataset_path=str(dataset),
        export_path=str(export),
        retrieved_candidates=["text_length_filter", "document_deduplicator"],
    )

    assert "text_length_filter" in seen_prompt["prompt"]
    assert planner.last_plan_meta.get("retrieve_source") == "provided"


def test_plan_usecase_defaults_planner_thinking_to_false(monkeypatch, tmp_path: Path):
    from data_juicer_agents.capabilities.plan import service as planner_mod

    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"text":"hello"}\n', encoding="utf-8")
    export = tmp_path / "out.jsonl"
    captured = {}

    monkeypatch.delenv("DJA_PLANNER_THINKING", raising=False)

    def fake_llm(_model: str, _prompt: str, **kwargs):
        captured["thinking"] = kwargs.get("thinking")
        return {
            "workflow": "custom",
            "modality": "text",
            "text_keys": ["text"],
            "operators": [
                {"name": "document_deduplicator", "params": {}},
            ],
            "risk_notes": [],
            "estimation": {},
        }

    monkeypatch.setattr(planner_mod, "call_model_json", fake_llm)
    monkeypatch.setattr(
        planner_mod,
        "retrieve_operator_candidates",
        lambda **_kwargs: {"candidates": [{"operator_name": "document_deduplicator"}]},
    )

    planner = PlanUseCase(
        workflows_dir=default_workflows_dir(),
        planning_mode=PlanningMode.FULL_LLM,
    )
    _ = planner.build_plan(
        user_intent="dedup text",
        dataset_path=str(dataset),
        export_path=str(export),
    )

    assert captured.get("thinking") is False
