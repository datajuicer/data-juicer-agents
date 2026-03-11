# -*- coding: utf-8 -*-

from pathlib import Path
from types import SimpleNamespace

import yaml

from data_juicer_agents.commands.apply_cmd import run_apply
from data_juicer_agents.tools.apply_tool_api import ApplyUseCase
from data_juicer_agents.tools.planner import OperatorStep, PlanModel


def test_apply_dry_run_prints_execution_summary_without_trace(tmp_path: Path, capsys):
    dataset = tmp_path / "data.jsonl"
    dataset.write_text('{"text": "hello world"}\n', encoding="utf-8")
    export_path = tmp_path / "out" / "result.jsonl"
    export_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path = tmp_path / "plan.yaml"

    plan = PlanModel(
        plan_id="plan_apply_001",
        user_intent="filter short rows",
        dataset_path=str(dataset),
        export_path=str(export_path),
        modality="text",
        text_keys=["text"],
        operators=[OperatorStep(name="words_num_filter", params={"min_words": 10})],
    )
    with open(plan_path, "w", encoding="utf-8") as handle:
        yaml.safe_dump(plan.to_dict(), handle, allow_unicode=False, sort_keys=False)

    args = SimpleNamespace(
        plan=str(plan_path),
        yes=True,
        dry_run=True,
        timeout=30,
        output_level="debug",
    )

    code = run_apply(args)
    output = capsys.readouterr().out

    assert code == 0
    assert "Execution ID:" in output
    assert "Trace command:" not in output
    assert "Status: success" in output
    recipe_path = Path(".djx") / "recipes" / "plan_apply_001.yaml"
    assert recipe_path.exists()


def test_apply_exec_uses_shell_free_command_with_spaced_recipe_path(tmp_path: Path, monkeypatch):
    dataset = tmp_path / "data.jsonl"
    dataset.write_text('{"text": "hello world"}\n', encoding="utf-8")
    export_path = tmp_path / "out file" / "result.jsonl"
    export_path.parent.mkdir(parents=True, exist_ok=True)

    plan = PlanModel(
        plan_id="plan_apply_002",
        user_intent="filter short rows",
        dataset_path=str(dataset),
        export_path=str(export_path),
        modality="text",
        text_keys=["text"],
        operators=[OperatorStep(name="words_num_filter", params={"min_words": 10})],
    )

    captured: dict = {}

    class DummyProc:
        def __init__(self):
            self.returncode = 0
            self.pid = 12345
            self._polled = False

        def poll(self):
            if not self._polled:
                self._polled = True
                return 0
            return 0

        def wait(self, timeout=None):
            return 0

        def terminate(self):
            return None

        def kill(self):
            return None

    def fake_popen(command, shell, stdout, stderr, text, start_new_session):
        captured["command"] = command
        captured["shell"] = shell
        captured["text"] = text
        captured["start_new_session"] = start_new_session
        return DummyProc()

    monkeypatch.setattr("data_juicer_agents.tools.apply_tool_api.subprocess.Popen", fake_popen)

    result, code, stdout, stderr = ApplyUseCase().execute(
        plan=plan,
        runtime_dir=tmp_path / "runtime dir",
        dry_run=False,
        timeout_seconds=5,
    )

    assert code == 0
    assert stdout == ""
    assert stderr == ""
    assert result.status == "success"
    assert captured["shell"] is False
    assert isinstance(captured["command"], list)
    assert captured["command"][:2] == ["dj-process", "--config"]
    assert "runtime dir" in captured["command"][2]
