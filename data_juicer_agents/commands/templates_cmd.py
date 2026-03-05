# -*- coding: utf-8 -*-
"""Implementation for `djx templates`."""

from __future__ import annotations

from pathlib import Path

import yaml


WORKFLOWS_DIR = Path(__file__).resolve().parent.parent / "workflows"


def run_templates(args) -> int:
    templates = sorted(path.stem for path in WORKFLOWS_DIR.glob("*.yaml"))
    if args.name:
        file_path = WORKFLOWS_DIR / f"{args.name}.yaml"
        if not file_path.exists():
            print(f"Template not found: {args.name}")
            return 2
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        print(yaml.safe_dump(data, allow_unicode=False, sort_keys=False))
        return 0

    print("Available templates:")
    for name in templates:
        print(f"- {name}")
    return 0
