# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from data_juicer_agents.capabilities.trace.repository import TraceStore
from studio.api.main import app


def _sample_plan_dict(dataset_path: str, export_path: str) -> dict:
    return {
        "plan_id": "plan_test_001",
        "user_intent": "clean and dedup",
        "workflow": "custom",
        "dataset_path": dataset_path,
        "export_path": export_path,
        "modality": "text",
        "text_keys": ["text"],
        "image_key": None,
        "operators": [
            {"name": "text_length_filter", "params": {"min_len": 1}},
        ],
        "risk_notes": [],
        "estimation": {},
        "custom_operator_paths": [],
        "revision": 1,
        "approval_required": True,
    }


def test_web_plan_load_and_save(tmp_path: Path):
    dataset = tmp_path / "dataset.jsonl"
    export = tmp_path / "out.jsonl"
    dataset.write_text('{"text":"hello"}\n', encoding="utf-8")

    plan_path = tmp_path / "plan.yaml"
    plan_payload = _sample_plan_dict(str(dataset), str(export))
    import yaml

    plan_path.write_text(yaml.safe_dump(plan_payload, sort_keys=False), encoding="utf-8")

    with TestClient(app) as client:
        load_resp = client.get("/api/plan", params={"path": str(plan_path)})
        assert load_resp.status_code == 200
        loaded = load_resp.json()
        assert loaded["ok"] is True
        assert loaded["plan"]["plan_id"] == "plan_test_001"

        edited = loaded["plan"]
        edited["operators"].append({"name": "document_deduplicator", "params": {}})
        save_resp = client.post(
            "/api/plan",
            json={
                "path": str(plan_path),
                "plan": edited,
            },
        )
        assert save_resp.status_code == 200
        saved = save_resp.json()
        assert saved["ok"] is True
        assert len(saved["plan"]["operators"]) == 2


def test_web_data_preview(tmp_path: Path):
    path = tmp_path / "dataset.jsonl"
    path.write_text(
        '{"text":"a"}\n'
        '{"text":"b"}\n'
        '{"text":"c"}\n',
        encoding="utf-8",
    )

    with TestClient(app) as client:
        resp = client.get(
            "/api/data/preview",
            params={
                "path": str(path),
                "limit": 2,
                "offset": 0,
            },
        )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["ok"] is True
    assert payload["sample"]["exists"] is True
    assert payload["sample"]["sample_count"] == 2
    assert payload["sample"]["truncated"] is True
    assert "text" in payload["sample"]["keys"]


def test_web_data_compare_by_run(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    djx_dir = tmp_path / ".djx"
    recipes_dir = djx_dir / "recipes"
    recipes_dir.mkdir(parents=True, exist_ok=True)

    dataset = tmp_path / "dataset.jsonl"
    export = tmp_path / "out.jsonl"
    dataset.write_text('{"text":"before"}\n', encoding="utf-8")
    export.write_text('{"text":"after"}\n', encoding="utf-8")

    recipe_path = recipes_dir / "plan_test_001.yaml"
    recipe_path.write_text(
        "project_name: plan_test_001\n"
        f"dataset_path: {dataset}\n"
        f"export_path: {export}\n"
        "process: []\n",
        encoding="utf-8",
    )

    trace_row = {
        "run_id": "run_test_001",
        "plan_id": "plan_test_001",
        "start_time": "2026-02-25T00:00:00Z",
        "end_time": "2026-02-25T00:00:01Z",
        "duration_seconds": 1.0,
        "model_info": {},
        "retrieval_mode": "workflow-first",
        "selected_workflow": "custom",
        "generated_recipe_path": str(recipe_path),
        "command": "dj-process --config plan_test_001.yaml",
        "status": "success",
        "artifacts": {"export_path": str(export)},
        "error_type": "none",
        "error_message": "",
        "retry_level": "none",
        "next_actions": [],
    }
    TraceStore().save_raw(trace_row)

    with TestClient(app) as client:
        resp = client.get(
            "/api/data/compare-by-run",
            params={
                "run_id": "run_test_001",
                "limit": 5,
            },
        )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["ok"] is True
    assert payload["run_id"] == "run_test_001"
    assert payload["input"] is not None
    assert payload["output"] is not None
    assert payload["input"]["records"][0]["text"] == "before"
    assert payload["output"]["records"][0]["text"] == "after"
