# -*- coding: utf-8 -*-

from importlib import import_module as real_import_module
import json

from data_juicer_agents.cli import main

def test_retrieve_command_json_output(capsys):
    """Real retrieve command with JSON output."""
    code = main(["retrieve", "deduplicate document", "--json"])
    assert code == 0

    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["ok"] is True
    assert data["candidate_count"] >= 1
    assert any(
        c["operator_name"] == "document_deduplicator"
        for c in data["candidates"]
    )

def test_retrieve_command_top_k_validation():
    code = main(["retrieve", "dedup", "--top-k", "0"])
    assert code == 2

def test_retrieve_command_accepts_bm25_mode(capsys):
    """Real retrieve command with explicit bm25 mode."""
    code = main(["retrieve", "dedup text", "--mode", "bm25", "--json"])
    assert code == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["ok"] is True
    assert data["retrieval_source"] == "bm25"
    assert data["candidate_count"] >= 1

def test_retrieve_command_missing_core_dependency_reports_install_hint(monkeypatch, capsys):
    def _fake_import_module(name, package=None):
        if name == "data_juicer_agents.commands.retrieve_cmd":
            raise ModuleNotFoundError(name="langchain_community")
        return real_import_module(name, package)

    monkeypatch.setattr("data_juicer_agents.cli.import_module", _fake_import_module)

    code = main(["retrieve", "dedup", "--json"])
    assert code == 2

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "djx retrieve requires optional dependencies" in captured.err
    assert "data-juicer-agents[core]" in captured.err
