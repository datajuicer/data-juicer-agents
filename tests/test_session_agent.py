# -*- coding: utf-8 -*-

import json
from pathlib import Path

import pytest
import yaml

from data_juicer_agents.capabilities.session.orchestrator import DJSessionAgent
from data_juicer_agents.tools.session import SessionState, SessionToolRuntime
from data_juicer_agents.tools.session.planner_tools import plan_build, plan_save, plan_validate


def test_session_agent_toolkit_uses_plan_build_not_plan_generate():
    pytest.importorskip("agentscope")
    agent = DJSessionAgent(use_llm_router=False)
    toolkit = agent._build_toolkit()  # pylint: disable=protected-access
    names = set(toolkit.tools.keys())
    assert "plan_build" in names
    assert "plan_generate" not in names
    assert "trace_run" not in names


def test_session_agent_plan_build_validate_save(tmp_path: Path):
    dataset = tmp_path / "data.jsonl"
    dataset.write_text('{"text": "hello world"}\n', encoding="utf-8")
    export_path = tmp_path / "out" / "result.jsonl"
    export_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path = tmp_path / "saved_plan.yaml"

    runtime = SessionToolRuntime(
        state=SessionState(
            dataset_path=str(dataset),
            export_path=str(export_path),
        )
    )

    built = plan_build(
        runtime,
        intent="filter short rows",
        draft_spec_json=json.dumps(
            {
                "modality": "text",
                "text_keys": ["text"],
                "operators": [
                    {"name": "words_num_filter", "params": {"min_words": 10}},
                ],
            }
        ),
    )
    assert built["ok"] is True
    assert built["action"] == "plan_build"
    assert "workflow" not in built["plan"]

    validated = plan_validate(runtime, use_draft=True)
    assert validated["ok"] is True
    assert validated["modality"] == "text"

    saved = plan_save(runtime, output_path=str(plan_path), overwrite=True)
    assert saved["ok"] is True
    payload = yaml.safe_load(plan_path.read_text(encoding="utf-8"))
    assert payload["plan_id"] == built["plan_id"]
    assert "workflow" not in payload
