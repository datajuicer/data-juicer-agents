# -*- coding: utf-8 -*-

from data_juicer_agents.capabilities.plan import service as service_mod


def test_resolve_retrieval_does_not_forward_dataset_source(monkeypatch):
    captured: dict = {}

    def _fake_retrieve(**kwargs):
        captured.update(kwargs)
        return {
            "ok": True,
            "retrieval_source": "lexical",
            "candidates": [],
        }

    monkeypatch.setattr(service_mod, "retrieve_operator_candidates", _fake_retrieve)
    orchestrator = service_mod.PlanOrchestrator(planner_model_name="unit-test")

    payload = orchestrator._resolve_retrieval(
        user_intent="deduplicate text",
        top_k=7,
        mode="auto",
        retrieved_candidates=None,
    )

    assert payload["ok"] is True
    assert captured["intent"] == "deduplicate text"
    assert captured["top_k"] == 7
    assert captured["mode"] == "auto"
    assert "dataset_source" not in captured
