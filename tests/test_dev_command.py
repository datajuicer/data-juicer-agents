# -*- coding: utf-8 -*-

from pathlib import Path

from data_juicer_agents.cli import main
def test_dev_command_generates_non_invasive_scaffold(tmp_path: Path, monkeypatch):
    out_dir = tmp_path / "custom_ops"
    monkeypatch.chdir(tmp_path)

    code = main(
        [
            "dev",
            "normalize user text",
            "--operator-name",
            "normalize_user_text",
            "--output-dir",
            str(out_dir),
        ]
    )
    assert code == 0
    assert (out_dir / "normalize_user_text_mapper.py").exists()
    assert (out_dir / "test_normalize_user_text_mapper.py").exists()
    assert (out_dir / "__init__.py").exists()
    assert (out_dir / "normalize_user_text_mapper_SUMMARY.md").exists()


def test_dev_command_suffix_type_conflict(tmp_path: Path, monkeypatch):
    out_dir = tmp_path / "custom_ops"
    monkeypatch.chdir(tmp_path)

    code = main(
        [
            "dev",
            "conflict case",
            "--operator-name",
            "foo_filter",
            "--type",
            "mapper",
            "--output-dir",
            str(out_dir),
        ]
    )
    assert code == 2


def test_dev_command_smoke_check(monkeypatch, tmp_path: Path):
    from data_juicer_agents.commands import dev_cmd as dev_mod

    out_dir = tmp_path / "ops"
    out_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        dev_mod.DevUseCase,
        "execute",
        staticmethod(
            lambda **_kwargs: {
                "ok": True,
                "operator_name": "sample_mapper",
                "operator_type": "mapper",
                "class_name": "SampleMapper",
                "output_dir": str(out_dir),
                "generated_files": [str(out_dir / "sample_mapper.py")],
                "summary_path": str(out_dir / "sample_mapper_SUMMARY.md"),
                "notes": [],
                "smoke_check": {"ok": True, "message": "ok"},
            }
        ),
    )
    monkeypatch.chdir(tmp_path)

    code = main(
        [
            "dev",
            "sample",
            "--operator-name",
            "sample_mapper",
            "--output-dir",
            str(out_dir),
            "--smoke-check",
        ]
    )
    assert code == 0
