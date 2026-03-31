# -*- coding: utf-8 -*-

import json

from data_juicer_agents.cli import main

def test_retrieve_command_json_output(capsys):
    """Real retrieve command with JSON output."""
    code = main(["retrieve", "deduplicate text", "--json"])
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
