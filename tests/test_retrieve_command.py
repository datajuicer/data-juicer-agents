# -*- coding: utf-8 -*-

from importlib import import_module as real_import_module
import json

from data_juicer_agents.cli import main


def test_retrieve_command_json_output(monkeypatch, capsys):
    from data_juicer_agents.commands import retrieve_cmd as retrieve_mod

    payload = {
        "ok": True,
        "intent": "deduplicate text",
        "top_k": 3,
        "mode": "auto",
        "retrieval_source": "lexical",
        "candidate_count": 1,
        "gap_detected": False,
        "candidates": [
            {
                "rank": 1,
                "operator_name": "document_deduplicator",
                "operator_type": "deduplicator",
                "description": "dedup",
                "relevance_score": 88.0,
                "arguments_preview": [],
            }
        ],
        "notes": [],
    }

    monkeypatch.setattr(
        retrieve_mod,
        "retrieve_operator_candidates",
        lambda **_kwargs: payload,
    )

    code = main(["retrieve", "deduplicate text", "--json"])
    assert code == 0

    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["candidate_count"] == 1
    assert data["candidates"][0]["operator_name"] == "document_deduplicator"


def test_retrieve_command_top_k_validation():
    code = main(["retrieve", "dedup", "--top-k", "0"])
    assert code == 2


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
