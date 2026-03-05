# -*- coding: utf-8 -*-

from pathlib import Path

from data_juicer_agents.capabilities.apply.service import ApplyUseCase
from data_juicer_agents.capabilities.plan.schema import OperatorStep, PlanModel


def test_executor_timeout_classification(tmp_path: Path):
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"text":"hello"}\n', encoding="utf-8")

    output = tmp_path / "out.jsonl"
    plan = PlanModel(
        plan_id="plan_timeout",
        user_intent="test timeout",
        workflow="rag_cleaning",
        dataset_path=str(dataset),
        export_path=str(output),
        text_keys=["text"],
        operators=[OperatorStep(name="text_length_filter", params={"min_len": 1})],
    )

    executor = ApplyUseCase()
    trace, returncode, _stdout, stderr = executor.execute(
        plan=plan,
        runtime_dir=tmp_path / ".djx" / "recipes",
        dry_run=False,
        timeout_seconds=1,
        command_override="python -c 'import time; time.sleep(2)'",
    )

    assert returncode != 0
    assert trace.error_type == "timeout"
    assert trace.retry_level == "medium"
    assert "Timeout" in stderr
