# -*- coding: utf-8 -*-
"""Implementation for `djx apply`."""

from __future__ import annotations

from pathlib import Path

import yaml

from data_juicer_agents.capabilities.apply.service import ApplyUseCase
from data_juicer_agents.commands.output_control import emit, emit_json, enabled


def _confirm(plan_data: dict) -> bool:
    print(f"About to execute plan: {str(plan_data.get('plan_id', '')).strip()}")
    print(f"Modality: {str(plan_data.get('modality', '')).strip()}")
    recipe = plan_data.get("recipe", {})    
    print(f"Dataset: {str(recipe.get('dataset_path', '')).strip()}")
    print(f"Export: {str(recipe.get('export_path', '')).strip()}")
    answer = input("Proceed? [y/N]: ").strip().lower()
    return answer in {"y", "yes"}


def run_apply(args) -> int:
    if args.timeout <= 0:
        print("timeout must be > 0")
        return 2

    plan_path = Path(args.plan)
    if not plan_path.exists():
        print(f"Plan file not found: {plan_path}")
        return 2

    with open(plan_path, "r", encoding="utf-8") as f:
        plan_data = yaml.safe_load(f)

    if not isinstance(plan_data, dict):
        print(f"Plan file is not a mapping: {plan_path}")
        return 2

    if not args.yes and not _confirm(plan_data):
        print("Execution canceled")
        return 1

    runtime_dir = Path(".djx") / "recipes"
    executor = ApplyUseCase()
    result, returncode, stdout, stderr = executor.execute(
        plan_payload=plan_data,
        runtime_dir=runtime_dir,
        dry_run=args.dry_run,
        timeout_seconds=args.timeout,
        cancel_check=getattr(args, "cancel_check", None),
    )

    interrupted = str(getattr(result, "error_type", "")).strip() == "interrupted"
    if interrupted:
        print("Execution interrupted by user.")

    if stdout and enabled(args, "verbose"):
        print("STDOUT:")
        print(stdout)
    if stderr and enabled(args, "verbose"):
        print("STDERR:")
        print(stderr)
    if enabled(args, "debug"):
        emit(args, "Debug apply payload:")
        emit_json(args, result.to_dict(), level="debug")
    print("Run Summary:")
    print(f"Execution ID: {result.execution_id}")
    print(f"Status: {result.status}")
    print(f"Recipe: {result.generated_recipe_path}")
    if result.error_type not in {"", "none"}:
        print(f"Error Type: {result.error_type}")
    if result.error_message:
        print(f"Error: {result.error_message}")

    return returncode
