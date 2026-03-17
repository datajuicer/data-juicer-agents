#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Skills ablation evaluation harness for DJSessionAgent.

Compares DJSessionAgent performance WITH vs WITHOUT skills documents
injected into the system prompt.

Usage:
    python eval_cases/run_eval.py --eval-file eval_cases/v0.1_run_smoke.jsonl --condition with_skills
    python eval_cases/run_eval.py --eval-file eval_cases/v0.1_run_smoke.jsonl --condition without_skills
"""

from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
_project_root = _Path(__file__).resolve().parent.parent
if str(_project_root) not in _sys.path:
    _sys.path.insert(0, str(_project_root))
del _sys, _Path, _project_root  # clean up namespace

import argparse
import json
import os
import time
import traceback
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

import yaml


# =============================================================================
# Skills Loading
# =============================================================================

# Skill definitions with when-conditions for on-demand loading
SKILL_REGISTRY = [
    {
        "file": "SKILL.md",
        "auto_load": True,  # Always loaded as the router
        "keywords": [],
    },
    {
        "file": "plan.md",
        "auto_load": False,
        "keywords": ["process", "clean", "filter", "deduplicate", "dedup", "plan",
                      "normalize", "rag", "corpus", "multimodal", "image",
                      "处理", "清洗", "过滤", "去重", "规范化", "语料", "多模态", "图"],
    },
    {
        "file": "apply.md",
        "auto_load": False,
        "keywords": ["execute", "run", "apply", "执行", "运行"],
    },
    {
        "file": "retrieve.md",
        "auto_load": False,
        "keywords": ["search operator", "what operator", "find operator", "retrieve",
                      "搜索算子", "有哪些算子", "查找"],
    },
    {
        "file": "dev.md",
        "auto_load": False,
        "keywords": ["custom", "new operator", "develop", "自定义", "新算子", "开发"],
    },
    {
        "file": "debug.md",
        "auto_load": False,
        "keywords": ["error", "failed", "not working", "出错", "失败", "排查", "问题"],
    },
    {
        "file": "session.md",
        "auto_load": False,
        "keywords": ["interactive", "conversational", "chat", "对话", "交互", "dj-agents"],
    },
]


def load_all_skills(skills_dir: Path) -> str:
    """Concatenate all skill markdown files into a single context string.
    
    This is the original load_skills function, kept as a fallback.
    """
    skill_files = [
        "SKILL.md",
        "plan.md",
        "apply.md",
        "retrieve.md",
        "dev.md",
        "debug.md",
        "session.md",
    ]
    
    contents: List[str] = []
    
    # Load main skill files
    for filename in skill_files:
        filepath = skills_dir / filename
        if filepath.exists():
            text = filepath.read_text(encoding="utf-8").strip()
            if text:
                contents.append(f"### {filename}\n\n{text}")
    
    # Load patch files
    patches_dir = skills_dir / "patches"
    if patches_dir.exists():
        for patch_file in sorted(patches_dir.glob("*.md")):
            text = patch_file.read_text(encoding="utf-8").strip()
            if text:
                contents.append(f"### patches/{patch_file.name}\n\n{text}")
    
    return "\n\n---\n\n".join(contents)


def load_skills_on_demand(skills_dir: Path, intent: str) -> tuple[str, list[str], int]:
    """Load only skills whose when-conditions match the intent.
    
    Args:
        skills_dir: Path to the skills directory
        intent: The user intent to match against skill keywords
    
    Returns:
        Tuple of (skills_context_string, list_of_loaded_files, total_bytes)
    """
    intent_lower = intent.lower()
    loaded_files: List[str] = []
    loaded_names: List[str] = []
    total_bytes = 0
    debug_loaded = False
    
    for skill in SKILL_REGISTRY:
        should_load = skill["auto_load"]
        if not should_load:
            # Check if any keyword matches the intent
            for kw in skill["keywords"]:
                if kw.lower() in intent_lower:
                    should_load = True
                    break
        
        if should_load:
            filepath = skills_dir / skill["file"]
            if filepath.exists():
                text = filepath.read_text(encoding="utf-8").strip()
                if text:
                    loaded_files.append(f"### {skill['file']}\n\n{text}")
                    loaded_names.append(skill["file"])
                    total_bytes += len(text.encode("utf-8"))
                    if skill["file"] == "debug.md":
                        debug_loaded = True
    
    # Also load relevant patches if debug.md is loaded
    if debug_loaded:
        patches_dir = skills_dir / "patches"
        if patches_dir.exists():
            for patch_file in sorted(patches_dir.glob("*.md")):
                text = patch_file.read_text(encoding="utf-8").strip()
                if text:
                    loaded_files.append(f"### patches/{patch_file.name}\n\n{text}")
                    loaded_names.append(f"patches/{patch_file.name}")
                    total_bytes += len(text.encode("utf-8"))
    
    skills_context = "\n\n---\n\n".join(loaded_files)
    return skills_context, loaded_names, total_bytes


# Backwards compatibility alias
load_skills = load_all_skills


# =============================================================================
# Token Usage Tracking (Monkey-patch OpenAI)
# =============================================================================

_token_log: List[Dict[str, int]] = []
_original_completions_create: Optional[Callable] = None


def patch_token_tracking() -> List[Dict[str, int]]:
    """Monkey-patch OpenAI client to capture token usage."""
    global _original_completions_create
    
    try:
        from openai.resources.chat.completions import Completions
    except ImportError:
        # OpenAI not installed; return empty log
        return _token_log
    
    if _original_completions_create is not None:
        # Already patched
        return _token_log
    
    _original_completions_create = Completions.create
    
    def _tracked_create(self, *args, **kwargs):
        response = _original_completions_create(self, *args, **kwargs)
        if hasattr(response, "usage") and response.usage:
            _token_log.append({
                "prompt_tokens": response.usage.prompt_tokens or 0,
                "completion_tokens": response.usage.completion_tokens or 0,
                "total_tokens": response.usage.total_tokens or 0,
            })
        return response
    
    Completions.create = _tracked_create
    return _token_log


def unpatch_token_tracking() -> None:
    """Restore original OpenAI completions create method."""
    global _original_completions_create
    
    if _original_completions_create is None:
        return
    
    try:
        from openai.resources.chat.completions import Completions
        Completions.create = _original_completions_create
        _original_completions_create = None
    except ImportError:
        pass


# =============================================================================
# Event Collector
# =============================================================================

class EventCollector:
    """Collects tool call and reasoning step events during agent execution."""
    
    def __init__(self):
        self.tool_traces: List[Dict[str, Any]] = []
        self.reasoning_steps: List[Dict[str, Any]] = []
        self._pending_tools: Dict[str, Dict[str, Any]] = {}
    
    def callback(self, event: Dict[str, Any]) -> None:
        """Event callback for DJSessionAgent."""
        event_type = event.get("type", "")
        
        if event_type == "tool_start":
            call_id = event.get("call_id", "")
            trace = {
                "call_id": call_id,
                "tool": event.get("tool", ""),
                "args": event.get("args", {}),
                "start_time": event.get("timestamp", ""),
                "end_time": None,
                "ok": None,
                "error_type": None,
                "summary": None,
            }
            self._pending_tools[call_id] = trace
            self.tool_traces.append(trace)
        
        elif event_type == "tool_end":
            call_id = event.get("call_id", "")
            if call_id in self._pending_tools:
                trace = self._pending_tools[call_id]
                trace["end_time"] = event.get("timestamp", "")
                trace["ok"] = event.get("ok", True)
                trace["error_type"] = event.get("error_type")
                trace["summary"] = event.get("summary", "")
        
        elif event_type == "reasoning_step":
            self.reasoning_steps.append({
                "step": event.get("step", 0),
                "thinking": event.get("thinking", "")[:500],  # Truncate
                "text_preview": event.get("text_preview", "")[:500],
                "has_tool_calls": event.get("has_tool_calls", False),
                "planned_tools": event.get("planned_tools", []),
                "timestamp": event.get("timestamp", ""),
            })
    
    def reset(self) -> None:
        """Reset collector state for a new case."""
        self.tool_traces = []
        self.reasoning_steps = []
        self._pending_tools = {}


# =============================================================================
# EvalDJSessionAgent with Skills Injection
# =============================================================================

class EvalDJSessionAgent:
    """DJSessionAgent wrapper with optional skills context injection.
    
    This subclasses the real DJSessionAgent to inject skills into the system prompt.
    """
    
    def __init__(self, skills_context: Optional[str] = None, **kwargs):
        self._skills_context = skills_context
        
        # Import here to avoid import errors if dependencies not available
        from data_juicer_agents.capabilities.session.orchestrator import DJSessionAgent
        
        # Store original class reference
        self._base_class = DJSessionAgent
        
        # Create instance with modified prompt method
        self._agent = self._create_agent_with_skills(**kwargs)
    
    def _create_agent_with_skills(self, **kwargs):
        """Create DJSessionAgent with skills-injected system prompt."""
        from data_juicer_agents.capabilities.session.orchestrator import DJSessionAgent
        
        skills_context = self._skills_context
        
        class SkillsInjectedAgent(DJSessionAgent):
            """DJSessionAgent with skills context in system prompt."""
            
            def __init__(self, _skills_ctx: Optional[str] = None, **kw):
                self._injected_skills = _skills_ctx
                super().__init__(**kw)
            
            def _session_sys_prompt(self) -> str:
                base = super()._session_sys_prompt()
                if self._injected_skills:
                    return base + "\n\n## Skills Reference\n\n" + self._injected_skills
                return base
        
        return SkillsInjectedAgent(_skills_ctx=skills_context, **kwargs)
    
    @property
    def state(self):
        """Access agent state."""
        return self._agent.state
    
    def handle_message(self, message: str):
        """Forward to underlying agent."""
        return self._agent.handle_message(message)


# =============================================================================
# Workflow Extraction
# =============================================================================

# rag_cleaning indicators
RAG_INDICATORS = [
    "text_length_filter",
    "document_deduplicator",
    "document_minhash_deduplicator",
    "document_simhash_deduplicator",
    "clean_email_mapper",
    "clean_links_mapper",
    "clean_html_mapper",
    "remove_",
    "language_id_score_filter",
    "perplexity_filter",
    "words_num_filter",
    "alphanumeric_filter",
    "whitespace_normalization_mapper",
    "punctuation_normalization_mapper",
]

# multimodal_dedup indicators
MULTIMODAL_INDICATORS = [
    "image_",
    "phash",
    "ray_image_deduplicator",
    "image_deduplicator",
    "image_text_matching",
    "image_aspect_ratio",
    "image_size_filter",
    "image_watermark",
]


def _classify_workflow_from_operators(operators: List[str]) -> Optional[str]:
    """Classify workflow type from operator names."""
    if not operators:
        return None

    operators_str = " ".join(op.lower() for op in operators)

    rag_score = sum(1 for ind in RAG_INDICATORS if ind in operators_str)
    multimodal_score = sum(1 for ind in MULTIMODAL_INDICATORS if ind in operators_str)

    if multimodal_score > rag_score:
        return "multimodal_dedup"
    elif rag_score > 0:
        return "rag_cleaning"
    return None


def _find_plan_save_info(tool_traces: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Find the successful plan_save tool call info."""
    for trace in reversed(tool_traces):  # Check most recent first
        if trace.get("tool") == "plan_save" and trace.get("ok") is True:
            return trace
    return None


def _extract_operators_from_yaml(plan_data: Dict[str, Any]) -> List[str]:
    """Extract operator names from plan YAML structure.
    
    Plan YAML uses 'process' key with format: [{op_name: params}, ...]
    """
    operators: List[str] = []
    process = plan_data.get("process", [])
    if isinstance(process, list):
        for item in process:
            if isinstance(item, dict):
                # Format: {operator_name: params}
                for name in item.keys():
                    operators.append(str(name))
            elif isinstance(item, str):
                operators.append(item)
    
    # Also check 'operators' key (alternate format)
    ops = plan_data.get("operators", [])
    if isinstance(ops, list):
        for op in ops:
            if isinstance(op, dict):
                name = op.get("name", "") or op.get("operator", "")
                if name:
                    operators.append(str(name))
            elif isinstance(op, str):
                operators.append(op)
    return operators


def _try_load_plan_yaml(working_dir: str, output_path: str) -> Optional[Dict[str, Any]]:
    """Try to load plan YAML file from various possible locations."""
    if not output_path:
        return None
    
    # Try different path resolutions
    candidates = [
        Path(working_dir) / output_path,  # Direct path in working dir
        Path(working_dir) / "recipes" / Path(output_path).name,  # In recipes subdir
        Path(working_dir) / "session_plans" / Path(output_path).name,  # In session_plans
        Path(output_path),  # Absolute or relative to cwd
    ]
    
    for candidate in candidates:
        try:
            if candidate.exists():
                with open(candidate, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f)
        except Exception:
            continue
    return None


def _extract_ops_from_tool_args(tool_traces: List[Dict[str, Any]]) -> List[str]:
    """Extract operators from assemble_plan or build_process_spec tool args."""
    operators: List[str] = []
    
    for trace in reversed(tool_traces):
        tool_name = trace.get("tool", "")
        args = trace.get("args", {})
        if not isinstance(args, dict):
            continue
        
        if tool_name == "assemble_plan" and trace.get("ok") is True:
            # process_spec might be a JSON string or dict
            ps = args.get("process_spec")
            if isinstance(ps, str):
                try:
                    ps = json.loads(ps)
                except Exception:
                    ps = None
            if isinstance(ps, dict):
                ops = ps.get("operators", [])
                if isinstance(ops, list):
                    for op in ops:
                        if isinstance(op, dict):
                            name = op.get("name", "")
                            if name:
                                operators.append(str(name))
                        elif isinstance(op, str):
                            operators.append(op)
        
        elif tool_name == "build_process_spec" and trace.get("ok") is True:
            # operators might be a JSON string or list
            ops = args.get("operators", [])
            if isinstance(ops, str):
                try:
                    ops = json.loads(ops)
                except Exception:
                    ops = []
            if isinstance(ops, list):
                for op in ops:
                    if isinstance(op, dict):
                        name = op.get("name", "")
                        if name:
                            operators.append(str(name))
                    elif isinstance(op, str):
                        operators.append(op)
        
        if operators:
            break  # Use first successful extraction
    
    return operators


def extract_workflow(
    tool_traces: List[Dict[str, Any]],
    agent_response: str,
    working_dir: str,
) -> Optional[str]:
    """Infer workflow type using multiple strategies.
    
    Strategy 1: Load plan from saved YAML file
    Strategy 2: Extract from tool trace args
    Strategy 3: Analyze agent response text
    
    Returns:
        "rag_cleaning", "multimodal_dedup", or None
    """
    operators: List[str] = []
    
    # Strategy 1: Load from saved YAML file
    plan_save_info = _find_plan_save_info(tool_traces)
    if plan_save_info:
        args = plan_save_info.get("args", {})
        output_path = args.get("output_path", "") if isinstance(args, dict) else ""
        
        # Also try to parse path from summary: "plan saved: <path>"
        if not output_path:
            summary = plan_save_info.get("summary", "")
            if "plan saved:" in str(summary):
                output_path = str(summary).split("plan saved:")[-1].strip()
        
        plan_data = _try_load_plan_yaml(working_dir, output_path)
        if plan_data:
            operators = _extract_operators_from_yaml(plan_data)
    
    # Strategy 2: Extract from tool args
    if not operators:
        operators = _extract_ops_from_tool_args(tool_traces)
    
    # Strategy 3: Analyze agent response text (last resort)
    if not operators and agent_response:
        response_lower = agent_response.lower()
        # Check for common operator mentions in response
        all_indicators = RAG_INDICATORS + MULTIMODAL_INDICATORS
        for ind in all_indicators:
            if ind.rstrip("_") in response_lower:
                operators.append(ind)
    
    return _classify_workflow_from_operators(operators)


def check_plan_valid(tool_traces: List[Dict[str, Any]], working_dir: str) -> bool:
    """Check if agent produced a valid plan by checking tool traces."""
    plan_save_info = _find_plan_save_info(tool_traces)
    if not plan_save_info:
        return False
    
    # Try to load and verify the plan has operators
    args = plan_save_info.get("args", {})
    output_path = args.get("output_path", "") if isinstance(args, dict) else ""
    if not output_path:
        summary = plan_save_info.get("summary", "")
        if "plan saved:" in str(summary):
            output_path = str(summary).split("plan saved:")[-1].strip()
    
    plan_data = _try_load_plan_yaml(working_dir, output_path)
    if plan_data:
        operators = _extract_operators_from_yaml(plan_data)
        return len(operators) > 0
    
    # Fallback: check assemble_plan succeeded
    for trace in reversed(tool_traces):
        if trace.get("tool") == "assemble_plan" and trace.get("ok") is True:
            return True
    return False


def has_plan(tool_traces: List[Dict[str, Any]]) -> bool:
    """Check if agent has a saved plan (plan_save succeeded)."""
    return _find_plan_save_info(tool_traces) is not None


def extract_errors(tool_traces: List[Dict[str, Any]]) -> List[str]:
    """Extract error messages from tool traces."""
    errors = []
    for trace in tool_traces:
        if trace.get("ok") is False:
            error_msg = trace.get("error_type") or trace.get("summary") or "Unknown error"
            errors.append(f"{trace.get('tool', 'unknown')}: {error_msg}")
    return errors


def serialize_plan(
    tool_traces: List[Dict[str, Any]],
    working_dir: str,
) -> Optional[Dict[str, Any]]:
    """Load and serialize plan from saved YAML file."""
    plan_save_info = _find_plan_save_info(tool_traces)
    if not plan_save_info:
        return None
    
    args = plan_save_info.get("args", {})
    output_path = args.get("output_path", "") if isinstance(args, dict) else ""
    if not output_path:
        summary = plan_save_info.get("summary", "")
        if "plan saved:" in str(summary):
            output_path = str(summary).split("plan saved:")[-1].strip()
    
    plan_data = _try_load_plan_yaml(working_dir, output_path)
    if plan_data:
        try:
            return json.loads(json.dumps(plan_data, default=str))
        except Exception:
            return {"error": "Failed to serialize plan", "path": output_path}
    
    return {"plan_save_path": output_path, "note": "YAML file not found"}


# =============================================================================
# Directory Hiding Context Manager
# =============================================================================

@contextmanager
def hide_directory(dir_path: Path):
    """Temporarily hide a directory by renaming it.
    
    Used during without_skills evaluation to prevent agent from accessing
    skills directory via file system tools.
    """
    hidden_path = dir_path.parent / f".{dir_path.name}.hidden"
    renamed = False
    try:
        if dir_path.exists():
            dir_path.rename(hidden_path)
            renamed = True
            print(f"Hidden: {dir_path} -> {hidden_path}")
        yield hidden_path
    finally:
        if renamed and hidden_path.exists():
            hidden_path.rename(dir_path)
            print(f"Restored: {hidden_path} -> {dir_path}")


# =============================================================================
# Single Case Execution
# =============================================================================

def run_single_case(
    case: Dict[str, Any],
    case_idx: int,
    skills_context_or_dir: Optional[Union[str, Path]],
    condition_name: str,
    config: Dict[str, Any],
    working_dir: str,
    collector: EventCollector,
    token_log: List[Dict[str, int]],
    token_log_start_idx: int,
    verbose: bool = False,
) -> Dict[str, Any]:
    """Run one eval case. Creates a FRESH agent per case for isolation.
    
    Args:
        skills_context_or_dir: Either a pre-loaded skills context string,
            or a Path to the skills directory for on-demand loading.
            If None, no skills are loaded.
    """
    collector.reset()
    
    case_id = f"case_{case_idx:03d}"
    
    # Prepare unique working directory for this case to avoid cross-contamination
    case_working_dir = Path(working_dir) / case_id
    case_working_dir.mkdir(parents=True, exist_ok=True)
    
    # Load skills on-demand based on intent, or use pre-loaded context
    skills_context: Optional[str] = None
    skills_loaded_info: Optional[str] = None
    
    if skills_context_or_dir is not None:
        if isinstance(skills_context_or_dir, Path):
            # On-demand: load skills based on this case's intent
            skills_context, loaded_names, total_bytes = load_skills_on_demand(
                skills_context_or_dir, case["intent"]
            )
            kb_size = total_bytes / 1024
            skills_loaded_info = f"{', '.join(loaded_names)} ({len(loaded_names)} files, {kb_size:.1f}KB)"
        else:
            # Pre-loaded context string
            skills_context = skills_context_or_dir
            skills_loaded_info = f"pre-loaded ({len(skills_context)} chars)"
    
    if skills_loaded_info:
        print(f"  Skills loaded: {skills_loaded_info}")
    
    try:
        agent = EvalDJSessionAgent(
            skills_context=skills_context,
            use_llm_router=True,
            dataset_path=case.get("dataset_path"),
            export_path=case.get("export_path"),
            working_dir=str(case_working_dir),
            model_name=config.get("experiment", {}).get("model", "qwen3-max-2026-01-23"),
            thinking=True,
            event_callback=collector.callback,
            verbose=verbose,
            api_key=os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("MODELSCOPE_API_TOKEN"),
        )
        
        start_time = time.time()
        reply = agent.handle_message(case["intent"])
        elapsed = time.time() - start_time
        
        # Capture tool traces and agent response for extraction
        tool_traces = collector.tool_traces
        agent_response = reply.text or ""
        case_dir = str(case_working_dir)
        
        # Extract workflow from tool traces and saved plan
        generated_workflow = extract_workflow(tool_traces, agent_response, case_dir)
        
        # Calculate token usage for this case
        case_tokens = token_log[token_log_start_idx:]
        prompt_tokens = sum(t.get("prompt_tokens", 0) for t in case_tokens)
        completion_tokens = sum(t.get("completion_tokens", 0) for t in case_tokens)
        total_tokens = sum(t.get("total_tokens", 0) for t in case_tokens)
        
        return {
            "case_id": case_id,
            "intent": case["intent"],
            "condition": condition_name,
            "expected_workflow": case.get("expected_workflow"),
            "generated_workflow": generated_workflow,
            "workflow_match": generated_workflow == case.get("expected_workflow"),
            "plan_valid": check_plan_valid(tool_traces, case_dir),
            "execution_success": not reply.stop and not reply.interrupted and has_plan(tool_traces),
            "token_usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            },
            "tool_call_count": len(tool_traces),
            "tool_calls": tool_traces,
            "reasoning_step_count": len(collector.reasoning_steps),
            "reasoning_steps": collector.reasoning_steps,
            "wall_clock_seconds": round(elapsed, 2),
            "agent_response": agent_response[:2000],
            "agent_thinking": reply.thinking[:1000] if reply.thinking else "",
            "error_messages": extract_errors(tool_traces),
            "plan_snapshot": serialize_plan(tool_traces, case_dir),
            "reply_stop": reply.stop,
            "reply_interrupted": reply.interrupted,
        }
    
    except Exception as exc:
        elapsed = time.time() - start_time if "start_time" in dir() else 0
        return {
            "case_id": case_id,
            "intent": case["intent"],
            "condition": condition_name,
            "expected_workflow": case.get("expected_workflow"),
            "generated_workflow": None,
            "workflow_match": False,
            "plan_valid": False,
            "execution_success": False,
            "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "tool_call_count": len(collector.tool_traces),
            "tool_calls": collector.tool_traces,
            "reasoning_step_count": len(collector.reasoning_steps),
            "reasoning_steps": collector.reasoning_steps,
            "wall_clock_seconds": round(elapsed, 2),
            "agent_response": "",
            "agent_thinking": "",
            "error_messages": [f"Exception: {exc}"],
            "plan_snapshot": None,
            "reply_stop": True,
            "reply_interrupted": False,
            "exception": str(exc),
            "traceback": traceback.format_exc(),
        }


# =============================================================================
# Main CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Skills ablation evaluation harness for DJSessionAgent"
    )
    parser.add_argument(
        "--eval-file",
        required=True,
        help="Path to eval JSONL file (e.g., eval_cases/v0.1_run_smoke.jsonl)",
    )
    parser.add_argument(
        "--condition",
        required=True,
        choices=["with_skills", "without_skills"],
        help="Experiment condition: with_skills or without_skills",
    )
    parser.add_argument(
        "--config",
        default="eval_cases/eval_config.yaml",
        help="Path to eval config YAML file",
    )
    parser.add_argument(
        "--skills-dir",
        default="skills/",
        help="Path to skills directory",
    )
    parser.add_argument(
        "--output-dir",
        default="eval_cases/results/",
        help="Directory for output results",
    )
    parser.add_argument(
        "--working-dir",
        default="./.eval_djx",
        help="Working directory for agent sessions",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--hide-skills",
        action="store_true",
        default=False,
        help="Hide skills directory during without_skills runs (prevents agent file access)",
    )
    parser.add_argument(
        "--load-all-skills",
        action="store_true",
        default=False,
        help="Load all skills at once instead of on-demand (legacy behavior)",
    )
    args = parser.parse_args()
    
    # Load config
    config_path = Path(args.config)
    if config_path.exists():
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    else:
        print(f"Warning: Config file not found at {args.config}, using defaults")
        config = {"experiment": {"model": "qwen3-max-2026-01-23"}}
    
    # Setup skills loading based on condition
    skills_dir = Path(args.skills_dir)
    skills_context_or_dir: Optional[Union[str, Path]] = None
    
    if args.condition == "with_skills":
        if skills_dir.exists():
            if args.load_all_skills:
                # Legacy behavior: load all skills upfront
                skills_context_or_dir = load_all_skills(skills_dir)
                print(f"Loaded all skills context: {len(skills_context_or_dir)} characters")
            else:
                # New behavior: pass skills_dir for on-demand loading per case
                skills_context_or_dir = skills_dir
                print(f"Skills directory: {skills_dir} (on-demand loading per case)")
        else:
            print(f"Warning: Skills directory not found at {args.skills_dir}")
    
    # Load eval cases
    eval_file_path = Path(args.eval_file)
    if not eval_file_path.exists():
        print(f"Error: Eval file not found: {args.eval_file}")
        return 1
    
    cases = []
    with open(eval_file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    
    if not cases:
        print("Error: No eval cases found in file")
        return 1
    
    print(f"Loaded {len(cases)} eval cases from {args.eval_file}")
    print(f"Condition: {args.condition}")
    print(f"Model: {config.get('experiment', {}).get('model', 'qwen3-max-2026-01-23')}")
    print("-" * 60)
    
    # Patch token tracking
    token_log = patch_token_tracking()
    
    # Prepare working directory
    working_dir = Path(args.working_dir)
    working_dir.mkdir(parents=True, exist_ok=True)
    
    # Run cases
    collector = EventCollector()
    results = []
    
    def run_all_cases():
        """Inner function to run all cases, can be called with or without directory hiding."""
        for i, case in enumerate(cases):
            intent_preview = case.get("intent", "")[:60]
            print(f"Running case {i + 1}/{len(cases)}: {intent_preview}...")
            
            token_start = len(token_log)
            result = run_single_case(
                case=case,
                case_idx=i,
                skills_context_or_dir=skills_context_or_dir,
                condition_name=args.condition,
                config=config,
                working_dir=str(working_dir),
                collector=collector,
                token_log=token_log,
                token_log_start_idx=token_start,
                verbose=args.verbose,
            )
            results.append(result)
            
            # Print brief status
            status = "PASS" if result["workflow_match"] else "FAIL"
            print(f"  -> {status} (expected={result['expected_workflow']}, got={result['generated_workflow']}, "
                  f"tools={result['tool_call_count']}, time={result['wall_clock_seconds']:.1f}s)")
    
    # Run cases with optional directory hiding for without_skills condition
    if args.condition == "without_skills" and args.hide_skills and skills_dir.exists():
        with hide_directory(skills_dir):
            run_all_cases()
    else:
        run_all_cases()
    
    # Restore OpenAI
    unpatch_token_tracking()
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{args.condition}_{timestamp}.jsonl"
    
    with open(output_path, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
    
    # Print summary
    print("\n" + "=" * 60)
    print(f"Results saved to: {output_path}")
    print("=" * 60)
    
    passed = sum(1 for r in results if r["workflow_match"])
    total = len(results)
    accuracy = 100 * passed / total if total > 0 else 0
    
    print(f"Workflow accuracy: {passed}/{total} ({accuracy:.1f}%)")
    
    avg_tools = sum(r["tool_call_count"] for r in results) / total if total > 0 else 0
    print(f"Avg tool calls: {avg_tools:.1f}")
    
    avg_time = sum(r["wall_clock_seconds"] for r in results) / total if total > 0 else 0
    print(f"Avg time: {avg_time:.1f}s")
    
    total_tokens = sum(r["token_usage"]["total_tokens"] for r in results)
    print(f"Total tokens: {total_tokens:,}")
    
    success_count = sum(1 for r in results if r["execution_success"])
    print(f"Execution success: {success_count}/{total}")
    
    return 0


if __name__ == "__main__":
    exit(main())
