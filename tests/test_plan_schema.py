# -*- coding: utf-8 -*-

import pytest

from data_juicer_agents.tools.plan import PlannerBuildError, PlannerCore


def test_planner_core_builds_plan_from_specs_without_legacy_fields(tmp_path):
    dataset = tmp_path / "data.jsonl"
    dataset.write_text('{"text": "hello"}\n', encoding="utf-8")
    export_path = tmp_path / "out" / "result.jsonl"
    export_path.parent.mkdir(parents=True, exist_ok=True)

    plan = PlannerCore.build_plan_from_specs(
        user_intent="filter short rows",
        dataset_spec={
            "io": {
                "dataset_path": str(dataset),
                "export_path": str(export_path),
            },
            "binding": {
                "modality": "text",
                "text_keys": ["text"],
            },
        },
        process_spec={
            "operators": [
                {"name": "WordNumFilter", "params": {"min_words": 10}},
            ],
        },
        system_spec={"np": 1},
        approval_required=True,
    )

    payload = plan.to_dict()
    assert list(plan.recipe["process"][0].keys())[0] == "WordNumFilter"
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
        PlannerCore.build_plan_from_specs(
            user_intent="invalid",
            dataset_spec={
                "io": {
                    "dataset_path": str(dataset),
                    "export_path": str(export_path),
                },
                "binding": {"modality": "text", "text_keys": ["text"]},
            },
            process_spec={"operators": []},
            system_spec={"np": 1},
        )
