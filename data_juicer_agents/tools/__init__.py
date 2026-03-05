# -*- coding: utf-8 -*-
"""Public exports for DJX tool services."""

from .dataset_probe import inspect_dataset_schema
from .llm_gateway import call_model_json
from .router_helpers import explain_routing, retrieve_workflow, select_workflow
from .op_manager import (
    extract_candidate_names,
    get_available_operator_names,
    resolve_operator_name,
    retrieve_operator_candidates,
)
from .op_manager import operator_registry, retrieval_service

__all__ = [
    "inspect_dataset_schema",
    "call_model_json",
    "select_workflow",
    "retrieve_workflow",
    "explain_routing",
    "get_available_operator_names",
    "resolve_operator_name",
    "retrieve_operator_candidates",
    "extract_candidate_names",
    # Backward-compatible module aliases.
    "operator_registry",
    "retrieval_service",
]
