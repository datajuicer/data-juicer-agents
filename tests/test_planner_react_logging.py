# -*- coding: utf-8 -*-

import logging

from data_juicer_agents.capabilities.plan.service import (
    PlanUseCase,
    PlanningMode,
    default_workflows_dir,
)
from data_juicer_agents.utils.agentscope_logging import IgnoreThinkingBlockWarningFilter


def test_ignore_thinking_warning_filter_blocks_only_target_message():
    filt = IgnoreThinkingBlockWarningFilter()

    blocked = logging.LogRecord(
        name="as",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="Unsupported block type thinking in the message, skipped.",
        args=(),
        exc_info=None,
    )
    kept = logging.LogRecord(
        name="as",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="Some other warning should remain visible.",
        args=(),
        exc_info=None,
    )

    assert filt.filter(blocked) is False
    assert filt.filter(kept) is True


def test_plan_usecase_full_llm_is_single_shot(monkeypatch, tmp_path):
    from data_juicer_agents.capabilities.plan import service as planner_mod

    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"text":"hello"}\n', encoding="utf-8")
    export = tmp_path / "out.jsonl"

    call_count = {"n": 0}

    monkeypatch.setattr(
        planner_mod,
        "retrieve_operator_candidates",
        lambda **_kwargs: {
            "candidates": [
                {
                    "operator_name": "text_length_filter",
                    "description": "Filter records by text length.",
                    "arguments_preview": ["text_key: text", "min_len: 1"],
                }
            ]
        },
    )

    def fake_llm(_model: str, prompt: str, **_kwargs):
        call_count["n"] += 1
        assert "retrieved_candidates" in prompt
        assert "Filter records by text length." in prompt
        assert "min_len: 1" in prompt
        return {
            "workflow": "custom",
            "modality": "text",
            "text_keys": ["text"],
            "operators": [{"name": "text_length_filter", "params": {"min_len": 1}}],
            "risk_notes": [],
            "estimation": {},
        }

    monkeypatch.setattr(planner_mod, "call_model_json", fake_llm)

    planner = PlanUseCase(
        workflows_dir=default_workflows_dir(),
        planning_mode=PlanningMode.FULL_LLM,
    )
    plan = planner.build_plan(
        user_intent="filter long text",
        dataset_path=str(dataset),
        export_path=str(export),
    )

    assert call_count["n"] == 1
    assert plan.workflow == "custom"
