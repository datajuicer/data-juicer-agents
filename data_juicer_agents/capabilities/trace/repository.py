# -*- coding: utf-8 -*-
"""Trace persistence repository (JSONL-backed)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from data_juicer_agents.capabilities.trace.schema import RunTraceModel


class TraceStore:
    """Append-only JSONL trace store."""

    def __init__(self, base_dir: Path | None = None):
        if base_dir is None:
            base_dir = Path.cwd() / ".djx"
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.trace_file = self.base_dir / "runs.jsonl"

    def save(self, trace: RunTraceModel) -> None:
        self.save_raw(trace.to_dict())

    def save_raw(self, payload: Dict[str, Any]) -> None:
        with open(self.trace_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def get(self, run_id: str) -> Optional[Dict[str, Any]]:
        for item in self.list_all():
            if item.get("run_id") == run_id:
                return item
        return None

    def list_by_plan(self, plan_id: str, limit: int | None = None) -> List[Dict[str, Any]]:
        rows = [row for row in self.list_all() if row.get("plan_id") == plan_id]
        if limit is None or limit <= 0:
            return rows
        return rows[-limit:]

    def list_all(self, limit: int | None = None) -> List[Dict[str, Any]]:
        if not self.trace_file.exists():
            return []

        rows: List[Dict[str, Any]] = []
        with open(self.trace_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))

        if limit is None or limit <= 0:
            return rows
        return rows[-limit:]

    def stats(self, plan_id: str | None = None) -> Dict[str, Any]:
        rows = self.list_by_plan(plan_id, limit=None) if plan_id else self.list_all()
        total = len(rows)
        if total == 0:
            return {
                "total_runs": 0,
                "success_runs": 0,
                "failed_runs": 0,
                "execution_success_rate": 0.0,
                "avg_duration_seconds": 0.0,
                "plan_id": plan_id,
                "by_workflow": {},
                "by_error_type": {},
            }

        success_runs = sum(1 for row in rows if row.get("status") == "success")
        failed_runs = total - success_runs

        durations = [float(row.get("duration_seconds", 0.0)) for row in rows]
        avg_duration = sum(durations) / len(durations)

        by_workflow: Dict[str, Dict[str, Any]] = {}
        by_error_type: Dict[str, int] = {}

        for row in rows:
            workflow = row.get("selected_workflow", "unknown")
            wf_stat = by_workflow.setdefault(
                workflow,
                {"total": 0, "success": 0, "failed": 0},
            )
            wf_stat["total"] += 1
            if row.get("status") == "success":
                wf_stat["success"] += 1
            else:
                wf_stat["failed"] += 1

            error_type = row.get("error_type", "none")
            by_error_type[error_type] = by_error_type.get(error_type, 0) + 1

        for wf_stat in by_workflow.values():
            total_wf = wf_stat["total"]
            wf_stat["success_rate"] = (
                wf_stat["success"] / total_wf if total_wf else 0.0
            )

        return {
            "total_runs": total,
            "success_runs": success_runs,
            "failed_runs": failed_runs,
            "execution_success_rate": success_runs / total,
            "avg_duration_seconds": avg_duration,
            "plan_id": plan_id,
            "by_workflow": by_workflow,
            "by_error_type": by_error_type,
        }


__all__ = ["TraceStore"]
