# -*- coding: utf-8 -*-

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from data_juicer_agents.core.tool import DatasetSource
from data_juicer_agents.tools.context import inspect_dataset_schema


def test_inspect_dataset_schema_text(tmp_path: Path):
    dataset = tmp_path / "text.jsonl"
    rows = [{"text": f"row {i}", "id": i} for i in range(10)]
    dataset.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )

    out = inspect_dataset_schema(dataset_source=DatasetSource(path=str(dataset)), sample_size=5)
    assert out["ok"] is True
    assert out["modality"] == "text"
    assert "text" in out["candidate_text_keys"]
    assert out["sampled_records"] == 5


def test_inspect_dataset_schema_multimodal(tmp_path: Path):
    dataset = tmp_path / "mm.jsonl"
    rows = [
        {"text": f"image {i}", "image": f"images/img_{i}.jpg"}
        for i in range(10)
    ]
    dataset.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )

    out = inspect_dataset_schema(dataset_source=DatasetSource(path=str(dataset)), sample_size=5)
    assert out["ok"] is True
    assert out["modality"] == "multimodal"
    assert "text" in out["candidate_text_keys"]
    assert "image" in out["candidate_image_keys"]
    assert out["sampled_records"] == 5


# ---------------------------------------------------------------------------
# JSON / CSV / TSV / Parquet tests
# ---------------------------------------------------------------------------

def test_inspect_dataset_schema_json(tmp_path: Path):
    dataset = tmp_path / "data.json"
    rows = [{"text": f"row {i}", "id": i} for i in range(10)]
    dataset.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")

    out = inspect_dataset_schema(dataset_source=DatasetSource(path=str(dataset)), sample_size=5)
    assert out["ok"] is True
    assert out["modality"] == "text"
    assert "text" in out["candidate_text_keys"]
    assert out["sampled_records"] == 5


def test_inspect_dataset_schema_csv(tmp_path: Path):
    dataset = tmp_path / "data.csv"
    lines = ["text,id"] + [f"row {i},{i}" for i in range(10)]
    dataset.write_text("\n".join(lines) + "\n", encoding="utf-8")

    out = inspect_dataset_schema(dataset_source=DatasetSource(path=str(dataset)), sample_size=5)
    assert out["ok"] is True
    assert out["modality"] == "text"
    assert "text" in out["candidate_text_keys"]
    assert out["sampled_records"] == 5


def test_inspect_dataset_schema_tsv(tmp_path: Path):
    dataset = tmp_path / "data.tsv"
    lines = ["text\tid"] + [f"row {i}\t{i}" for i in range(10)]
    dataset.write_text("\n".join(lines) + "\n", encoding="utf-8")

    out = inspect_dataset_schema(dataset_source=DatasetSource(path=str(dataset)), sample_size=5)
    assert out["ok"] is True
    assert out["modality"] == "text"
    assert "text" in out["candidate_text_keys"]
    assert out["sampled_records"] == 5


pyarrow = pytest.importorskip("pyarrow", reason="pyarrow not installed")


def test_inspect_dataset_schema_parquet(tmp_path: Path):
    import pyarrow as pa
    import pyarrow.parquet as pq

    table = pa.table({
        "text": [f"row {i}" for i in range(10)],
        "id": list(range(10)),
    })
    dataset = tmp_path / "data.parquet"
    pq.write_table(table, str(dataset))

    out = inspect_dataset_schema(dataset_source=DatasetSource(path=str(dataset)), sample_size=5)
    assert out["ok"] is True
    assert out["modality"] == "text"
    assert "text" in out["candidate_text_keys"]
    assert out["sampled_records"] == 5