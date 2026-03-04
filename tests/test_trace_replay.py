# -*- coding: utf-8 -*-

from pathlib import Path

from data_juicer_agents.capabilities.trace.schema import RunTraceModel
from data_juicer_agents.capabilities.trace.repository import TraceStore


def test_trace_store_save_and_get(tmp_path: Path):
    store = TraceStore(base_dir=tmp_path / ".djx")
    trace = RunTraceModel(
        run_id="run_123",
        plan_id="plan_123",
        start_time="2026-02-10T00:00:00+00:00",
        end_time="2026-02-10T00:00:01+00:00",
        duration_seconds=1.0,
        model_info={"planner": "qwen3-max-thinking"},
        retrieval_mode="workflow-first",
        selected_workflow="rag_cleaning",
        generated_recipe_path="/tmp/p.yaml",
        command="dj-process --config /tmp/p.yaml",
        status="success",
        artifacts={"export_path": "/tmp/out.jsonl"},
        error_type="none",
        error_message="",
        retry_level="none",
        next_actions=[],
    )
    store.save(trace)

    loaded = store.get("run_123")
    assert loaded is not None
    assert loaded["plan_id"] == "plan_123"


def test_trace_store_stats(tmp_path: Path):
    store = TraceStore(base_dir=tmp_path / ".djx")

    success = RunTraceModel(
        run_id="run_ok",
        plan_id="plan_ok",
        start_time="2026-02-10T00:00:00+00:00",
        end_time="2026-02-10T00:00:01+00:00",
        duration_seconds=1.0,
        model_info={"planner": "qwen3-max-thinking"},
        retrieval_mode="workflow-first",
        selected_workflow="rag_cleaning",
        generated_recipe_path="/tmp/a.yaml",
        command="dj-process --config /tmp/a.yaml",
        status="success",
        artifacts={"export_path": "/tmp/a.jsonl"},
        error_type="none",
        error_message="",
        retry_level="none",
        next_actions=[],
    )
    failed = RunTraceModel(
        run_id="run_fail",
        plan_id="plan_fail",
        start_time="2026-02-10T00:00:00+00:00",
        end_time="2026-02-10T00:00:02+00:00",
        duration_seconds=2.0,
        model_info={"planner": "qwen3-max-thinking"},
        retrieval_mode="workflow-first",
        selected_workflow="multimodal_dedup",
        generated_recipe_path="/tmp/b.yaml",
        command="dj-process --config /tmp/b.yaml",
        status="failed",
        artifacts={"export_path": "/tmp/b.jsonl"},
        error_type="missing_command",
        error_message="command not found",
        retry_level="high",
        next_actions=["Install dj-process"],
    )

    store.save(success)
    store.save(failed)

    stats = store.stats()
    assert stats["total_runs"] == 2
    assert stats["success_runs"] == 1
    assert stats["failed_runs"] == 1
    assert stats["execution_success_rate"] == 0.5
    assert stats["plan_id"] is None

    filtered = store.stats(plan_id="plan_ok")
    assert filtered["total_runs"] == 1
    assert filtered["success_runs"] == 1
    assert filtered["failed_runs"] == 0

    rows = store.list_by_plan("plan_ok")
    assert len(rows) == 1
    assert rows[0]["run_id"] == "run_ok"
