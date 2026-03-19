# -*- coding: utf-8 -*-

from pathlib import Path
from types import SimpleNamespace

import yaml

from data_juicer_agents.commands.plan_cmd import execute_plan, run_plan
from data_juicer_agents.capabilities.plan import generator as generator_mod
from data_juicer_agents.capabilities.plan import service as service_mod


def _args(tmp_path: Path) -> SimpleNamespace:
    dataset = tmp_path / "data.jsonl"
    dataset.write_text('{"text": "hello world"}\n', encoding="utf-8")
    output = tmp_path / "plan.yaml"
    export = tmp_path / "out" / "result.jsonl"
    export.parent.mkdir(parents=True, exist_ok=True)
    return SimpleNamespace(
        intent="filter short rows",
        dataset=str(dataset),
        export=str(export),
        output=str(output),
        custom_operator_paths=None,
        planner_model=None,
        llm_api_key=None,
        llm_base_url=None,
        llm_thinking=None,
        output_level="debug",
    )


def test_execute_plan_uses_retrieval_and_writes_new_schema(monkeypatch, tmp_path):
    args = _args(tmp_path)
    monkeypatch.setattr(
        service_mod,
        "retrieve_operator_candidates",
        lambda **_kwargs: {
            "ok": True,
            "retrieval_source": "lexical",
            "candidates": [
                {
                    "operator_name": "words_num_filter",
                    "description": "filter by word count",
                    "operator_type": "filter",
                    "arguments_preview": ["min_num: int"],
                }
            ],
        },
    )
    monkeypatch.setattr(
        generator_mod,
        "call_model_json",
        lambda *_args, **_kwargs: {
            "operators": [{"name": "words_num_filter", "params": {"min_num": 10}}],
        },
    )

    result = execute_plan(args)

    assert result["ok"] is True
    payload = yaml.safe_load(Path(result["plan_path"]).read_text(encoding="utf-8"))
    # modality is a plan-level field
    assert payload["modality"] == "text"
    # operators live inside recipe.process as DJ-native format
    assert payload["recipe"]["process"][0] == {"words_num_filter": {"min_num": 10}}
    assert "workflow" not in payload
    assert result["dataset_spec"]["binding"]["text_keys"] == ["text"]
    assert result["process_spec"]["operators"][0]["params"]["min_num"] == 10


def test_run_plan_prints_modality_not_workflow(monkeypatch, tmp_path, capsys):
    args = _args(tmp_path)
    monkeypatch.setattr(
        service_mod,
        "retrieve_operator_candidates",
        lambda **_kwargs: {
            "ok": True,
            "retrieval_source": "lexical",
            "candidates": [{"operator_name": "words_num_filter"}],
        },
    )
    monkeypatch.setattr(
        generator_mod,
        "call_model_json",
        lambda *_args, **_kwargs: {
            "operators": [{"name": "words_num_filter", "params": {"min_num": 10}}],
        },
    )

    code = run_plan(args)
    output = capsys.readouterr().out

    assert code == 0
    assert "Modality: text" in output
    assert "Workflow:" not in output
