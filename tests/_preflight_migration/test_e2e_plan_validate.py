# -*- coding: utf-8 -*-
"""E2E tests pinning plan_validate behavior before preflight cleanup."""

from data_juicer_agents.tools.plan.plan_validate.logic import plan_validate


class TestPlanValidate:
    """Pin current behavior of plan_validate end-to-end."""

    def _valid_plan(self, **overrides):
        plan = {
            "plan_id": "plan_test123",
            "user_intent": "filter short texts",
            "modality": "text",
            "recipe": {
                "dataset_path": "/tmp",
                "export_path": "/tmp/out",
                "text_keys": ["text"],
                "process": [{"remove_long_words_mapper": {"min_len": 1}}],
            },
        }
        plan.update(overrides)
        return plan

    def test_valid_plan_passes(self):
        result = plan_validate(plan_payload=self._valid_plan())
        assert result["ok"] is True
        assert result["validation_errors"] == []
        assert "plan_test123" == result["plan_id"]

    def test_missing_plan_id_error(self):
        result = plan_validate(plan_payload=self._valid_plan(plan_id=""))
        assert result["ok"] is False
        assert any("plan_id is required" in e for e in result["validation_errors"])

    def test_missing_user_intent_error(self):
        result = plan_validate(plan_payload=self._valid_plan(user_intent=""))
        assert result["ok"] is False
        assert any("user_intent is required" in e for e in result["validation_errors"])

    def test_missing_recipe_error(self):
        plan = {"plan_id": "plan_x", "user_intent": "test", "modality": "text"}
        result = plan_validate(plan_payload=plan)
        assert result["ok"] is False
        assert "recipe" in result.get("message", "")

    def test_invalid_modality_error(self):
        result = plan_validate(plan_payload=self._valid_plan(modality="invalid_mod"))
        assert result["ok"] is False
        assert any("modality" in e for e in result["validation_errors"])

    def test_text_modality_requires_text_keys(self):
        plan = self._valid_plan()
        del plan["recipe"]["text_keys"]
        result = plan_validate(plan_payload=plan)
        assert result["ok"] is False
        assert any("text modality requires text_keys" in e for e in result["validation_errors"])

    def test_nonexistent_dataset_path_error(self):
        plan = self._valid_plan()
        plan["recipe"]["dataset_path"] = "/nonexistent/path.jsonl"
        result = plan_validate(plan_payload=plan)
        assert result["ok"] is False
        assert any("does not exist" in e for e in result["validation_errors"])

    def test_missing_export_path_error(self):
        plan = self._valid_plan()
        plan["recipe"]["export_path"] = ""
        result = plan_validate(plan_payload=plan)
        assert result["ok"] is False
        assert any("export_path is required" in e for e in result["validation_errors"])

    def test_multiple_dataset_sources_error(self):
        plan = self._valid_plan()
        plan["recipe"]["dataset"] = {"configs": [{"type": "local", "path": "/tmp/a.jsonl"}]}
        result = plan_validate(plan_payload=plan)
        assert result["ok"] is False
        assert any("multiple dataset sources" in e for e in result["validation_errors"])

    def test_operator_names_extracted(self):
        result = plan_validate(plan_payload=self._valid_plan())
        assert "remove_long_words_mapper" in result["operator_names"]

    def test_custom_operator_paths_nonexistent_error(self):
        plan = self._valid_plan()
        plan["recipe"]["custom_operator_paths"] = ["/nonexistent/custom_ops"]
        result = plan_validate(plan_payload=plan)
        assert result["ok"] is False
        assert any("custom_operator_path" in e and "does not exist" in e for e in result["validation_errors"])
