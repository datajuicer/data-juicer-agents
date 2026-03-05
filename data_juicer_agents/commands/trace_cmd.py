# -*- coding: utf-8 -*-
"""Implementation for `djx trace`."""

from __future__ import annotations

import json

from data_juicer_agents.capabilities.trace.repository import TraceStore


def run_trace(args) -> int:
    store = TraceStore()
    if args.limit <= 0:
        print("limit must be > 0")
        return 2

    if args.stats:
        stats = store.stats(plan_id=args.plan_id)
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        return 0

    if args.run_id:
        item = store.get(args.run_id)
        if item is None:
            print(f"Run not found: {args.run_id}")
            return 2

        print(f"Run ID: {item['run_id']}")
        print(f"Plan ID: {item['plan_id']}")
        print(f"Workflow: {item['selected_workflow']}")
        print(f"Status: {item['status']}")
        print(f"Duration(s): {item.get('duration_seconds', 0.0):.3f}")
        print(f"Recipe: {item['generated_recipe_path']}")
        print(f"Command: {item['command']}")
        print(f"Error Type: {item.get('error_type', 'none')}")
        print(f"Retry Level: {item.get('retry_level', 'none')}")
        if item.get("error_message"):
            print(f"Error: {item['error_message']}")
        if item.get("next_actions"):
            print("Next Actions:")
            for action in item["next_actions"]:
                print(f"- {action}")
        return 0

    if args.plan_id:
        rows = store.list_by_plan(args.plan_id, limit=args.limit)
        if not rows:
            print(f"No runs found for plan_id: {args.plan_id}")
            return 2
        print(f"Plan ID: {args.plan_id} (latest {len(rows)} run(s))")
        for row in rows:
            print(
                f"- {row.get('run_id')} | status={row.get('status')} | "
                f"workflow={row.get('selected_workflow')} | "
                f"duration={float(row.get('duration_seconds', 0.0)):.3f}s | "
                f"error={row.get('error_type', 'none')}"
            )
        print("Use `djx trace <run_id>` for full details.")
        return 0

    print("Please provide run_id, or use --plan-id, or use --stats")
    return 2
