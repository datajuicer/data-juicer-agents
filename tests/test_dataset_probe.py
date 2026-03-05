# -*- coding: utf-8 -*-

import json
from pathlib import Path

from data_juicer_agents.tools.dataset_probe import inspect_dataset_schema


def test_inspect_dataset_schema_text(tmp_path: Path):
    dataset = tmp_path / "text.jsonl"
    dataset.write_text(
        "\n".join(
            [
                json.dumps({"text": "hello world", "id": 1}, ensure_ascii=False),
                json.dumps({"text": "second row", "id": 2}, ensure_ascii=False),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    out = inspect_dataset_schema(str(dataset), sample_size=10)
    assert out["ok"] is True
    assert out["modality"] == "text"
    assert "text" in out["candidate_text_keys"]
    assert out["sampled_records"] == 2


def test_inspect_dataset_schema_multimodal(tmp_path: Path):
    dataset = tmp_path / "mm.jsonl"
    dataset.write_text(
        "\n".join(
            [
                json.dumps(
                    {"text": "cat image", "image": "images/cat_1.jpg"},
                    ensure_ascii=False,
                ),
                json.dumps(
                    {"text": "dog image", "image": "images/dog_1.png"},
                    ensure_ascii=False,
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    out = inspect_dataset_schema(str(dataset), sample_size=10)
    assert out["ok"] is True
    assert out["modality"] == "multimodal"
    assert "text" in out["candidate_text_keys"]
    assert "image" in out["candidate_image_keys"]

