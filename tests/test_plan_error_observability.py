# -*- coding: utf-8 -*-

from types import SimpleNamespace


def test_execute_plan_failed_payload_contains_attempts(monkeypatch, tmp_path):
    from data_juicer_agents.commands import plan_cmd
    from data_juicer_agents.capabilities.plan import service as planner_mod

    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"text":"hello"}\n', encoding="utf-8")
    export = tmp_path / "out.jsonl"

    monkeypatch.setattr(planner_mod, "retrieve_workflow", lambda _intent: None)

    args = SimpleNamespace(
        intent="do something",
        dataset=str(dataset),
        export=str(export),
        output=str(tmp_path / "plan.yaml"),
        base_plan=None,
        from_run_id=None,
        custom_operator_paths=[],
        from_template=None,
        template_retrieve=True,
        planner_model=None,
        llm_api_key=None,
        llm_base_url=None,
        llm_thinking=None,
    )

    result = plan_cmd.execute_plan(args)

    assert result["ok"] is False
    assert result["error_type"] == "plan_failed"
    assert result["stage"] == "full-llm"
    assert len(result["attempts"]) == 2
    assert result["attempts"][0]["name"] == "template-retrieve"
    assert result["attempts"][0]["error_code"] == "template_retrieve_no_match"
    assert result["attempts"][1]["name"] == "full-llm"
    assert result["attempts"][1]["status"] == "failed"
    assert len(result["next_actions"]) > 0


def test_execute_plan_success_payload_contains_attempt_meta(monkeypatch, tmp_path):
    from data_juicer_agents.commands import plan_cmd
    from data_juicer_agents.capabilities.plan import service as planner_mod
    from data_juicer_agents.capabilities.plan import validation as validator_mod

    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"text":"hello"}\n', encoding="utf-8")
    export = tmp_path / "out.jsonl"

    monkeypatch.setattr(
        planner_mod.PlanUseCase,
        "_request_full_plan",
        lambda self, **_kwargs: {
            "workflow": "custom",
            "modality": "text",
            "text_keys": ["text"],
            "operators": [{"name": "text_length_filter", "params": {"min_len": 1}}],
            "risk_notes": [],
            "estimation": {},
        },
    )
    monkeypatch.setattr(
        validator_mod.PlanValidator,
        "llm_review",
        staticmethod(lambda _plan: {"errors": [], "warnings": []}),
    )

    args = SimpleNamespace(
        intent="filter text",
        dataset=str(dataset),
        export=str(export),
        output=str(tmp_path / "plan.yaml"),
        base_plan=None,
        from_run_id=None,
        custom_operator_paths=[],
        from_template=None,
        template_retrieve=False,
        planner_model=None,
        llm_api_key=None,
        llm_base_url=None,
        llm_thinking=None,
    )

    result = plan_cmd.execute_plan(args)

    assert result["ok"] is True
    assert result["plan"]["workflow"] == "custom"
    assert len(result["attempts"]) == 1
    assert result["attempts"][0]["name"] == "full-llm"
    assert result["attempts"][0]["status"] == "success"
    assert result["planning_meta"]["plan_mode"] == "llm_full"
