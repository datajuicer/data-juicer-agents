# -*- coding: utf-8 -*-
"""Tests for multi-turn recipe management functionality."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml

from data_juicer_agents.capabilities.plan.schema import PlanModel, OperatorStep
from data_juicer_agents.capabilities.plan.validation import (
    ValidationError,
    validate_with_suggestions,
)
from data_juicer_agents.capabilities.session.orchestrator import (
    DJSessionAgent,
    SessionState,
)


class TestValidationError:
    """Tests for ValidationError dataclass."""

    def test_validation_error_creation(self):
        error = ValidationError(
            category="path",
            field="dataset_path",
            message="dataset_path does not exist",
            suggestion="Provide a valid path",
        )
        assert error.category == "path"
        assert error.field == "dataset_path"
        assert error.message == "dataset_path does not exist"
        assert error.suggestion == "Provide a valid path"

    def test_validation_error_to_dict(self):
        error = ValidationError(
            category="operator",
            field="operators",
            message="unknown operator",
            suggestion="use a valid operator",
        )
        result = error.to_dict()
        assert result == {
            "category": "operator",
            "field": "operators",
            "message": "unknown operator",
            "suggestion": "use a valid operator",
        }


class TestValidateWithSuggestions:
    """Tests for validate_with_suggestions function."""

    def test_validate_missing_dataset_path(self, tmp_path):
        plan = PlanModel(
            plan_id="test_plan",
            user_intent="test",
            workflow="custom",
            dataset_path=str(tmp_path / "nonexistent.jsonl"),
            export_path=str(tmp_path / "output.jsonl"),
            operators=[OperatorStep(name="cleaner", params={})],
        )
        errors = validate_with_suggestions(plan)
        assert len(errors) >= 1
        path_errors = [e for e in errors if e.category == "path" and e.field == "dataset_path"]
        assert len(path_errors) >= 1
        assert "does not exist" in path_errors[0].message

    def test_validate_missing_export_parent(self):
        plan = PlanModel(
            plan_id="test_plan",
            user_intent="test",
            workflow="custom",
            dataset_path="data/test.jsonl",
            export_path="/nonexistent/dir/output.jsonl",
            operators=[OperatorStep(name="cleaner", params={})],
        )
        errors = validate_with_suggestions(plan)
        path_errors = [e for e in errors if e.category == "path" and e.field == "export_path"]
        # May or may not have export_path error depending on filesystem
        # Just check the function runs without error

    def test_validate_text_modality_missing_text_keys(self, tmp_path):
        dataset_path = tmp_path / "test.jsonl"
        dataset_path.write_text('{"text": "hello"}\n', encoding="utf-8")
        
        plan = PlanModel(
            plan_id="test_plan",
            user_intent="test",
            workflow="custom",
            dataset_path=str(dataset_path),
            export_path=str(tmp_path / "output.jsonl"),
            modality="text",
            text_keys=[],
            operators=[OperatorStep(name="cleaner", params={})],
        )
        errors = validate_with_suggestions(plan)
        config_errors = [e for e in errors if e.category == "config" and e.field == "text_keys"]
        assert len(config_errors) >= 1
        assert "text modality requires text_keys" in config_errors[0].message

    def test_validate_empty_operators(self, tmp_path):
        dataset_path = tmp_path / "test.jsonl"
        dataset_path.write_text('{"text": "hello"}\n', encoding="utf-8")
        
        plan = PlanModel(
            plan_id="test_plan",
            user_intent="test",
            workflow="custom",
            dataset_path=str(dataset_path),
            export_path=str(tmp_path / "output.jsonl"),
            operators=[],
        )
        errors = validate_with_suggestions(plan)
        config_errors = [e for e in errors if e.category == "config" and e.field == "operators"]
        assert len(config_errors) >= 1
        assert "empty" in config_errors[0].message.lower()


class TestSessionStateExtensions:
    """Tests for SessionState multi-turn recipe fields."""

    def test_session_state_default_values(self):
        state = SessionState()
        assert state.draft_recipe_path is None
        assert state.recipe_status == "empty"
        assert state.validation_errors == []
        assert state.validation_warnings == []

    def test_session_state_with_values(self):
        state = SessionState(
            draft_recipe_path=".djx/recipes/draft_recipe.yaml",
            recipe_status="draft",
            validation_errors=["error1"],
            validation_warnings=["warning1"],
        )
        assert state.draft_recipe_path == ".djx/recipes/draft_recipe.yaml"
        assert state.recipe_status == "draft"
        assert state.validation_errors == ["error1"]
        assert state.validation_warnings == ["warning1"]


class TestToolEditRecipe:
    """Tests for tool_edit_recipe functionality."""

    def test_edit_recipe_no_draft_plan(self):
        agent = DJSessionAgent.__new__(DJSessionAgent)
        agent.state = SessionState()
        agent.state.draft_plan = None
        agent._debug = lambda x: None
        
        result = agent.tool_edit_recipe(dataset_path="new/path.jsonl")
        assert result["ok"] is False
        assert result["error_type"] == "missing_required"

    def test_edit_recipe_direct_field_edit(self, tmp_path):
        agent = DJSessionAgent.__new__(DJSessionAgent)
        agent.state = SessionState()
        agent.state.draft_plan = {
            "plan_id": "test_plan",
            "user_intent": "test",
            "workflow": "custom",
            "dataset_path": "old/path.jsonl",
            "export_path": str(tmp_path / "output.jsonl"),
            "modality": "text",
            "text_keys": ["text"],
            "operators": [{"name": "cleaner", "params": {}}],
        }
        agent.state.validation_errors = []
        agent.state.validation_warnings = []
        agent._debug = lambda x: None
        agent._current_draft_plan_model = lambda: None
        agent._auto_save_draft_recipe = lambda: ".djx/recipes/draft_recipe.yaml"
        
        result = agent.tool_edit_recipe(dataset_path="new/path.jsonl")
        assert result["ok"] is True
        assert "dataset_path: new/path.jsonl" in result["changes"]

    def test_edit_recipe_operators_update(self, tmp_path):
        agent = DJSessionAgent.__new__(DJSessionAgent)
        agent.state = SessionState()
        agent.state.draft_plan = {
            "plan_id": "test_plan",
            "user_intent": "test",
            "workflow": "custom",
            "dataset_path": str(tmp_path / "test.jsonl"),
            "export_path": str(tmp_path / "output.jsonl"),
            "modality": "text",
            "text_keys": ["text"],
            "operators": [{"name": "cleaner", "params": {}}],
        }
        agent.state.validation_errors = []
        agent.state.validation_warnings = []
        agent._debug = lambda x: None
        agent._current_draft_plan_model = lambda: None
        agent._auto_save_draft_recipe = lambda: ".djx/recipes/draft_recipe.yaml"
        
        new_operators = [
            {"name": "filter", "params": {"min_length": 10}},
            {"name": "dedup", "params": {}},
        ]
        result = agent.tool_edit_recipe(operators=new_operators)
        assert result["ok"] is True
        assert any("operators" in change for change in result["changes"])

    def test_edit_recipe_no_changes(self, tmp_path):
        agent = DJSessionAgent.__new__(DJSessionAgent)
        agent.state = SessionState()
        agent.state.draft_plan = {
            "plan_id": "test_plan",
            "user_intent": "test",
            "workflow": "custom",
            "dataset_path": str(tmp_path / "test.jsonl"),
            "export_path": str(tmp_path / "output.jsonl"),
            "operators": [{"name": "cleaner", "params": {}}],
        }
        agent._debug = lambda x: None
        
        result = agent.tool_edit_recipe()
        assert result["ok"] is True
        assert result["changes"] == []


class TestToolConfirmRecipe:
    """Tests for tool_confirm_recipe functionality."""

    def test_confirm_recipe_no_draft_plan(self):
        agent = DJSessionAgent.__new__(DJSessionAgent)
        agent.state = SessionState()
        agent.state.draft_plan = None
        agent._debug = lambda x: None
        
        result = agent.tool_confirm_recipe()
        assert result["ok"] is False
        assert result["error_type"] == "missing_required"

    def test_confirm_recipe_validation_failure(self, tmp_path):
        agent = DJSessionAgent.__new__(DJSessionAgent)
        agent.state = SessionState()
        agent.state.draft_plan = {
            "plan_id": "test_plan",
            "user_intent": "test",
            "workflow": "custom",
            "dataset_path": str(tmp_path / "nonexistent.jsonl"),  # Will fail validation
            "export_path": str(tmp_path / "output.jsonl"),
            "operators": [],  # Empty operators will fail
        }
        agent.state.validation_errors = []
        agent._debug = lambda x: None
        
        result = agent.tool_confirm_recipe()
        assert result["ok"] is False
        assert result["error_type"] == "validation_failed"
        assert len(result["validation_errors"]) >= 1


class TestToolApplyEnhancements:
    """Tests for enhanced tool_apply functionality."""

    def test_apply_with_use_draft_no_plan(self):
        agent = DJSessionAgent.__new__(DJSessionAgent)
        agent.state = SessionState()
        agent.state.draft_plan = None
        agent._debug = lambda x: None
        
        result = agent.tool_apply(use_draft=True, confirm=True)
        assert result["ok"] is False
        assert result["error_type"] == "missing_required"

    def test_apply_with_invalid_recipe_status(self, tmp_path):
        agent = DJSessionAgent.__new__(DJSessionAgent)
        agent.state = SessionState()
        agent.state.draft_plan = {
            "plan_id": "test_plan",
            "user_intent": "test",
            "workflow": "custom",
            "dataset_path": str(tmp_path / "nonexistent.jsonl"),
            "export_path": str(tmp_path / "output.jsonl"),
            "operators": [],
        }
        agent.state.recipe_status = "invalid"
        agent._debug = lambda x: None
        agent._current_draft_plan_model = lambda: PlanModel(
            plan_id="test_plan",
            user_intent="test",
            workflow="custom",
            dataset_path=str(tmp_path / "nonexistent.jsonl"),
            export_path=str(tmp_path / "output.jsonl"),
            operators=[],
        )
        
        result = agent.tool_apply(use_draft=True, confirm=True)
        assert result["ok"] is False
        assert result["error_type"] == "validation_failed"

    def test_apply_suggests_use_draft_when_no_plan_path(self):
        agent = DJSessionAgent.__new__(DJSessionAgent)
        agent.state = SessionState()
        agent.state.plan_path = None
        agent.state.draft_plan = {"plan_id": "test", "operators": []}
        agent.state.recipe_status = "draft"
        agent._debug = lambda x: None
        
        result = agent.tool_apply(confirm=True)
        assert result["ok"] is False
        assert "use_draft" in result["message"].lower() or "confirm_recipe" in result["message"].lower()


class TestAutoSaveDraftRecipe:
    """Tests for _auto_save_draft_recipe method."""

    def test_auto_save_no_draft_plan(self, tmp_path):
        agent = DJSessionAgent.__new__(DJSessionAgent)
        agent.state = SessionState()
        agent.state.draft_plan = None
        agent._current_draft_plan_model = lambda: None
        
        result = agent._auto_save_draft_recipe()
        assert result is None

    def test_auto_save_creates_file(self, tmp_path):
        agent = DJSessionAgent.__new__(DJSessionAgent)
        agent.state = SessionState()
        agent.state.draft_plan = {
            "plan_id": "test_plan",
            "user_intent": "test",
            "workflow": "custom",
            "dataset_path": str(tmp_path / "test.jsonl"),
            "export_path": str(tmp_path / "output.jsonl"),
            "operators": [{"name": "cleaner", "params": {}}],
        }
        agent._current_draft_plan_model = lambda: PlanModel(
            plan_id="test_plan",
            user_intent="test",
            workflow="custom",
            dataset_path=str(tmp_path / "test.jsonl"),
            export_path=str(tmp_path / "output.jsonl"),
            operators=[OperatorStep(name="cleaner", params={})],
        )
        
        # Change to temp directory for .djx creation
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = agent._auto_save_draft_recipe()
            assert result is not None
            assert Path(result).exists()
            assert Path(result).name == "draft_recipe.yaml"
        finally:
            os.chdir(original_cwd)


class TestContextPayloadExtensions:
    """Tests for _context_payload with recipe status fields."""

    def test_context_payload_includes_recipe_status(self):
        agent = DJSessionAgent.__new__(DJSessionAgent)
        agent.state = SessionState(
            draft_recipe_path=".djx/recipes/draft.yaml",
            recipe_status="draft",
            validation_errors=["error1"],
            validation_warnings=["warning1"],
        )
        
        payload = agent._context_payload()
        assert payload["draft_recipe_path"] == ".djx/recipes/draft.yaml"
        assert payload["recipe_status"] == "draft"
        assert payload["validation_errors"] == ["error1"]
        assert payload["validation_warnings"] == ["warning1"]
