# -*- coding: utf-8 -*-
"""Execution use case for deterministic Data-Juicer execution."""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Tuple

import yaml

from data_juicer_agents.capabilities.plan.schema import PlanModel
from data_juicer_agents.capabilities.trace.schema import RunTraceModel


_DEFAULT_PLANNER_MODEL = os.environ.get("DJA_PLANNER_MODEL", "qwen3-max-2026-01-23")
_DEFAULT_VALIDATOR_MODEL = os.environ.get("DJA_VALIDATOR_MODEL", "qwen3-max-2026-01-23")


def _classify_error(returncode: int, stderr: str) -> tuple[str, str, List[str]]:
    if returncode == 0:
        return "none", "none", []

    if returncode == 130:
        return "interrupted", "none", [
            "Execution interrupted by user.",
            "Adjust plan or timeout and retry when ready.",
        ]

    msg = (stderr or "").lower()

    if "command not found" in msg or "not recognized" in msg:
        return "missing_command", "high", [
            "Install Data-Juicer CLI and verify dj-process is in PATH",
            "Run `which dj-process` to verify environment",
        ]

    if "no such file or directory" in msg:
        return "missing_path", "medium", [
            "Check dataset_path and export_path in plan",
            "Ensure recipe file path exists and is readable",
        ]

    if "permission denied" in msg:
        return "permission_denied", "high", [
            "Fix file or directory permissions",
            "Retry with a writable export path",
        ]

    if "keyerror" in msg and "operators.modules" in msg:
        return "unsupported_operator", "high", [
            "Check workflow operator names against installed Data-Juicer version",
            "Regenerate plan with supported operators",
        ]

    if "keyerror:" in msg and ("_mapper" in msg or "_deduplicator" in msg):
        return "unsupported_operator", "high", [
            "Operator missing in current Data-Juicer installation",
            "Replace unsupported operator and retry",
        ]

    if "timeout" in msg:
        return "timeout", "medium", [
            "Reduce dataset size and retry",
            "Increase execution timeout in future versions",
        ]

    return "command_failed", "low", [
        "Inspect stderr details",
        "Adjust operator parameters and retry",
    ]


class ApplyUseCase:
    """Execute validated plans and generate run traces."""

    @staticmethod
    def _write_recipe(plan: PlanModel, runtime_dir: Path) -> Path:
        runtime_dir.mkdir(parents=True, exist_ok=True)
        recipe_path = runtime_dir / f"{plan.plan_id}.yaml"
        recipe = {
            "project_name": plan.plan_id,
            "dataset_path": plan.dataset_path,
            "export_path": plan.export_path,
            "text_keys": plan.text_keys,
            "image_key": plan.image_key,
            "np": 1,
            "skip_op_error": False,
            "process": [{step.name: step.params} for step in plan.operators],
        }
        if plan.custom_operator_paths:
            recipe["custom_operator_paths"] = list(plan.custom_operator_paths)
        with open(recipe_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(recipe, f, allow_unicode=False, sort_keys=False)
        return recipe_path

    def execute(
        self,
        plan: PlanModel,
        runtime_dir: Path,
        dry_run: bool = False,
        timeout_seconds: int = 300,
        command_override: str | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> Tuple[RunTraceModel, int, str, str]:
        recipe_path = self._write_recipe(plan, runtime_dir)
        command = command_override or f"dj-process --config {recipe_path}"

        start_dt = datetime.now(timezone.utc)

        if dry_run:
            if callable(cancel_check) and bool(cancel_check()):
                returncode = 130
                stdout = ""
                stderr = "Interrupted by user."
            else:
                returncode = 0
                stdout = "dry-run: command not executed"
                stderr = ""
        else:
            stdout_f = tempfile.TemporaryFile(mode="w+")
            stderr_f = tempfile.TemporaryFile(mode="w+")
            try:
                proc = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=stdout_f,
                    stderr=stderr_f,
                    text=True,
                    start_new_session=True,
                )
                deadline = time.monotonic() + float(timeout_seconds)
                interrupted = False
                timed_out = False
                while True:
                    if callable(cancel_check) and bool(cancel_check()):
                        interrupted = True
                        break
                    if time.monotonic() >= deadline:
                        timed_out = True
                        break
                    rc = proc.poll()
                    if rc is not None:
                        break
                    time.sleep(0.1)

                if interrupted:
                    try:
                        os.killpg(proc.pid, signal.SIGTERM)
                    except Exception:
                        with contextlib.suppress(Exception):
                            proc.terminate()
                    with contextlib.suppress(Exception):
                        proc.wait(timeout=2)
                    if proc.poll() is None:
                        with contextlib.suppress(Exception):
                            os.killpg(proc.pid, signal.SIGKILL)
                        with contextlib.suppress(Exception):
                            proc.kill()
                    returncode = 130
                    stdout_f.seek(0)
                    stderr_f.seek(0)
                    stdout = stdout_f.read()
                    stderr = stderr_f.read().rstrip("\n")
                    stderr = (stderr + "\nInterrupted by user.").strip()
                elif timed_out:
                    try:
                        os.killpg(proc.pid, signal.SIGTERM)
                    except Exception:
                        with contextlib.suppress(Exception):
                            proc.terminate()
                    with contextlib.suppress(Exception):
                        proc.wait(timeout=2)
                    if proc.poll() is None:
                        with contextlib.suppress(Exception):
                            os.killpg(proc.pid, signal.SIGKILL)
                        with contextlib.suppress(Exception):
                            proc.kill()
                    returncode = 124
                    stdout_f.seek(0)
                    stderr_f.seek(0)
                    stdout = stdout_f.read()
                    stderr = (stderr_f.read().rstrip("\n") + f"\nTimeout after {timeout_seconds}s").strip()
                else:
                    proc.wait()  # Ensure process is dead
                    returncode = int(proc.returncode or 0)
                    stdout_f.seek(0)
                    stderr_f.seek(0)
                    stdout = stdout_f.read()
                    stderr = stderr_f.read()
            except subprocess.TimeoutExpired as exc:
                returncode = 124
                stdout = str(exc.stdout or "")
                stderr = str(exc.stderr or "") + f"\nTimeout after {timeout_seconds}s"
            finally:
                stdout_f.close()
                stderr_f.close()

        end_dt = datetime.now(timezone.utc)
        duration = (end_dt - start_dt).total_seconds()
        if returncode == 0:
            status = "success"
        elif returncode == 130:
            status = "interrupted"
        else:
            status = "failed"
        error_type, retry_level, next_actions = _classify_error(returncode, stderr)

        trace = RunTraceModel(
            run_id=RunTraceModel.new_id(),
            plan_id=plan.plan_id,
            start_time=start_dt.isoformat(),
            end_time=end_dt.isoformat(),
            duration_seconds=duration,
            model_info={
                "planner": _DEFAULT_PLANNER_MODEL,
                "validator": _DEFAULT_VALIDATOR_MODEL,
                "executor": "deterministic-cli",
            },
            retrieval_mode="workflow-first",
            selected_workflow=plan.workflow,
            generated_recipe_path=str(recipe_path),
            command=command,
            status=status,
            artifacts={"export_path": plan.export_path},
            error_type=error_type,
            error_message="" if returncode == 0 else stderr.strip(),
            retry_level=retry_level,
            next_actions=next_actions,
        )

        return trace, returncode, stdout, stderr
