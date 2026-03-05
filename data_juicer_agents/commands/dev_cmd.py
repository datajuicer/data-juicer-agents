# -*- coding: utf-8 -*-
"""Implementation for `djx dev`."""

from __future__ import annotations

from data_juicer_agents.capabilities.dev.service import DevUseCase


def run_dev(args) -> int:
    if not args.intent.strip():
        print("intent is required")
        return 2
    if not args.operator_name.strip():
        print("--operator-name is required")
        return 2
    if not args.output_dir.strip():
        print("--output-dir is required")
        return 2

    result = DevUseCase.execute(
        intent=args.intent,
        operator_name=args.operator_name,
        output_dir=args.output_dir,
        operator_type=args.type,
        from_retrieve=args.from_retrieve,
        smoke_check=args.smoke_check,
    )
    if not result.get("ok"):
        print(str(result.get("message", "dev scaffold generation failed")))
        return 2

    print("Custom operator scaffold generated:")
    print(f"- operator: {result.get('operator_name')}")
    print(f"- type: {result.get('operator_type')}")
    print(f"- class: {result.get('class_name')}")
    print(f"- output_dir: {result.get('output_dir')}")
    print("- generated files:")
    for path in result.get("generated_files", []):
        print(f"  - {path}")
    print(f"- summary: {result.get('summary_path')}")
    for note in result.get("notes", []):
        print(f"Note: {note}")

    if args.smoke_check:
        smoke = result.get("smoke_check", {})
        print(str(smoke.get("message", "")))
        return 0 if bool(smoke.get("ok")) else 1

    return 0
