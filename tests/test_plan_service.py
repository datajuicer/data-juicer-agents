# -*- coding: utf-8 -*-

from data_juicer_agents.capabilities.plan import service as service_mod


def test_resolve_retrieval_forwards_dataset_config(monkeypatch):
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

    dataset = {"configs": [{"type": "local", "path": "/tmp/data.jsonl"}]}
    payload = orchestrator._resolve_retrieval(
        user_intent="deduplicate text",
        dataset_path="",
        dataset=dataset,
        top_k=7,
        mode="auto",
        retrieved_candidates=None,
    )

    assert payload["ok"] is True
    assert captured["intent"] == "deduplicate text"
    assert captured["top_k"] == 7
    assert captured["mode"] == "auto"
    assert captured["dataset_path"] is None
    assert captured["dataset"] == dataset

