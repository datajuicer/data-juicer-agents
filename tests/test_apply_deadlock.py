# -*- coding: utf-8 -*-

import os
import sys
import tempfile
import time
from pathlib import Path

import pytest
import yaml

from data_juicer_agents.capabilities.apply.service import ApplyUseCase
from data_juicer_agents.capabilities.plan.schema import OperatorStep, PlanModel


def test_apply_execute_large_output_no_deadlock(tmp_path: Path):
    """Verify that ApplyUseCase.execute does not deadlock on large output.

    This test creates a python script that prints a large amount of data to stdout
    and then calls ApplyUseCase.execute to run it. If the tempfile buffering logic
    is correct, this should finish quickly. If it relies on PIPE buffer, it might
    hang or fail.
    """
    # 1. Prepare a mock plan
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"text":"hello"}\n', encoding="utf-8")
    export = tmp_path / "output.jsonl"
    plan = PlanModel(
        plan_id="plan_large_output",
        user_intent="test large output",
        workflow="custom",
        dataset_path=str(dataset),
        export_path=str(export),
        text_keys=["text"],
        operators=[OperatorStep(name="text_length_filter", params={"min_len": 1})],
    )

    # 2. Create a script that generates massive output (>> 64KB pipe buffer)
    # 10000 lines * ~80 chars/line = ~800KB
    flooder_script = tmp_path / "flooder.py"
    flooder_script.write_text(
        "import sys\n"
        "import time\n"
        "print('start flooding')\n"
        "for i in range(10000):\n"
        "    print(f'Line {i}: ' + 'x' * 60)\n"
        "print('done flooding')\n",
        encoding="utf-8",
    )

    # 3. Use ApplyUseCase with command override
    use_case = ApplyUseCase()
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()

    command = f"{sys.executable} {flooder_script}"

    start_time = time.time()
    # Should finish within a few seconds if not deadlocked
    trace, returncode, stdout, stderr = use_case.execute(
        plan=plan,
        runtime_dir=runtime_dir,
        dry_run=False,
        timeout_seconds=10,
        command_override=command,
    )
    duration = time.time() - start_time

    # 4. Assertions
    assert returncode == 0, f"Process failed with {stderr}"
    assert "start flooding" in stdout
    assert "done flooding" in stdout
    # Ensure we captured all output (rough check of length)
    assert len(stdout) > 500000, "Stdout seems truncated or too short"
    assert duration < 10, "Execution took too long, possible partial blocking"
    assert trace.status == "success"
