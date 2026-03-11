# -*- coding: utf-8 -*-
"""Tool-level APIs for deterministic Data-Juicer execution."""

from __future__ import annotations

import contextlib
import os
import shlex
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Tuple
from uuid import uuid4

import yaml

from data_juicer_agents.tools.planner import PlanModel


_DEFAULT_PLANNER_MODEL = os.environ.get("DJA_PLANNER_MODEL", "qwen3-max-2026-01-23")


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
    if "keyerror" in msg and ("operators.modules" in msg or "_mapper" in msg or "_deduplicator" in msg):
        return "unsupported_operator", "high", [
            "Check operator names against installed Data-Juicer version",
            "Regenerate plan with supported operators",
        ]
    if "timeout" in msg:
        return "timeout", "medium", [
            "Reduce dataset size and retry",
            "Increase execution timeout if needed",
        ]
    return "command_failed", "low", [
        "Inspect stderr details",
        "Adjust operator parameters and retry",
    ]


@dataclass
class ApplyResult:
    """Execution summary for one plan apply run."""

    execution_id: str
    plan_id: str
    start_time: str
    end_time: str
    duration_seconds: float
    model_info: Dict[str, str]
    generated_recipe_path: str
    command: str
    status: str
    artifacts: Dict[str, str]
    error_type: str
    error_message: str
    retry_level: str
    next_actions: List[str]

    @staticmethod
    def new_id() -> str:
        return f"exec_{uuid4().hex[:12]}"

    def to_dict(self) -> Dict[str, object]:
        return {
            "execution_id": self.execution_id,
            "plan_id": self.plan_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_seconds": self.duration_seconds,
            "model_info": dict(self.model_info),
            "generated_recipe_path": self.generated_recipe_path,
            "command": self.command,
            "status": self.status,
            "artifacts": dict(self.artifacts),
            "error_type": self.error_type,
            "error_message": self.error_message,
            "retry_level": self.retry_level,
            "next_actions": list(self.next_actions),
        }


class ApplyUseCase:
    """Execute validated plans and return execution summaries."""

    @staticmethod
    def _normalize_command(
        recipe_path: Path,
        command_override: str | Iterable[str] | None,
    ) -> tuple[list[str], str]:
        if command_override is None:
            command = ["dj-process", "--config", str(recipe_path)]
            return command, shlex.join(command)

        if isinstance(command_override, str):
            parts = shlex.split(command_override)
        else:
            parts = [str(item) for item in command_override if str(item).strip()]

        if not parts:
            raise ValueError("command_override must not be empty")

        return parts, shlex.join(parts)

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
        with open(recipe_path, "w", encoding="utf-8") as handle:
            yaml.safe_dump(recipe, handle, allow_unicode=False, sort_keys=False)
        return recipe_path

    def execute(
        self,
        plan: PlanModel,
        runtime_dir: Path,
        dry_run: bool = False,
        timeout_seconds: int = 300,
        command_override: str | Iterable[str] | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> Tuple[ApplyResult, int, str, str]:
        recipe_path = self._write_recipe(plan, runtime_dir)
        command_args, command_display = self._normalize_command(recipe_path, command_override)
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
                    command_args,
                    shell=False,
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
                    stderr = (stderr_f.read().rstrip("\n") + "\nInterrupted by user.").strip()
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
                    proc.wait()
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
        status = "success" if returncode == 0 else ("interrupted" if returncode == 130 else "failed")
        error_type, retry_level, next_actions = _classify_error(returncode, stderr)
        result = ApplyResult(
            execution_id=ApplyResult.new_id(),
            plan_id=plan.plan_id,
            start_time=start_dt.isoformat(),
            end_time=end_dt.isoformat(),
            duration_seconds=duration,
            model_info={
                "planner": _DEFAULT_PLANNER_MODEL,
                "executor": "deterministic-cli",
            },
            generated_recipe_path=str(recipe_path),
            command=command_display,
            status=status,
            artifacts={"export_path": plan.export_path},
            error_type=error_type,
            error_message="" if returncode == 0 else stderr.strip(),
            retry_level=retry_level,
            next_actions=next_actions,
        )
        return result, returncode, stdout, stderr


__all__ = ["ApplyResult", "ApplyUseCase"]
