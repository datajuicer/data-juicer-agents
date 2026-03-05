# -*- coding: utf-8 -*-

from data_juicer_agents.tools import llm_gateway as llm_utils


def test_call_model_json_fallback_succeeds(monkeypatch):
    def fake_call(model_name: str, _prompt: str, **_kwargs):
        if model_name == "qwen-max":
            return {"ok": True}
        raise RuntimeError("Model not exist")

    monkeypatch.setenv("DJA_MODEL_FALLBACKS", "qwen-max")
    monkeypatch.setattr(llm_utils, "_call_model_json_once", fake_call)

    result = llm_utils.call_model_json("qwen3-max-2026-01-23", "ping")
    assert result == {"ok": True}


def test_call_model_json_fallback_all_fail(monkeypatch):
    def fake_call(_model_name: str, _prompt: str, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setenv("DJA_MODEL_FALLBACKS", "qwen-max")
    monkeypatch.setattr(llm_utils, "_call_model_json_once", fake_call)

    try:
        llm_utils.call_model_json("qwen3-max-2026-01-23", "ping")
        assert False, "expected failure"
    except RuntimeError as exc:
        msg = str(exc)
        assert "qwen3-max-2026-01-23" in msg
        assert "qwen-max" in msg
