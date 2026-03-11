# -*- coding: utf-8 -*-

import pytest

from data_juicer_agents.tools.planner import PlannerBuildError, PlannerCore
from data_juicer_agents.tools.planner import core as core_mod


def test_planner_core_builds_plan_without_legacy_fields(monkeypatch, tmp_path):
    monkeypatch.setattr(
        core_mod,
        "get_available_operator_names",
        lambda: {"words_num_filter"},
    )
    dataset = tmp_path / "data.jsonl"
    dataset.write_text('{"text": "hello"}\n', encoding="utf-8")
    export_path = tmp_path / "out" / "result.jsonl"
    export_path.parent.mkdir(parents=True, exist_ok=True)

    plan = PlannerCore.build_plan(
        user_intent="filter short rows",
        dataset_path=str(dataset),
        export_path=str(export_path),
        draft_spec={
            "text_keys": ["text"],
            "operators": [
                {"name": "WordNumFilter", "params": {"min_words": 10}},
            ],
        },
    )

    payload = plan.to_dict()
    assert plan.operators[0].name == "words_num_filter"
    assert payload["modality"] == "text"
    assert "workflow" not in payload
    assert "revision" not in payload
    assert "parent_plan_id" not in payload


def test_planner_core_rejects_empty_operator_list(tmp_path):
    dataset = tmp_path / "data.jsonl"
    dataset.write_text('{"text": "hello"}\n', encoding="utf-8")
    export_path = tmp_path / "out" / "result.jsonl"
    export_path.parent.mkdir(parents=True, exist_ok=True)

    with pytest.raises(PlannerBuildError):
        PlannerCore.build_plan(
            user_intent="invalid",
            dataset_path=str(dataset),
            export_path=str(export_path),
            draft_spec={"text_keys": ["text"], "operators": []},
        )
