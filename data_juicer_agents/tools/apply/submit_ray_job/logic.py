# -*- coding: utf-8 -*-
"""Pure logic for submit_ray_job — runtime-agnostic."""

from __future__ import annotations

import logging
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
from uuid import uuid4

import yaml

_logger = logging.getLogger(__name__)

_JOB_ID_PATTERN = re.compile(r"Job '(raysubmit_\w+)' submitted successfully")


def _load_plan(plan_path: str) -> Dict[str, Any] | None:
    """Load and validate a plan YAML file."""
    path = Path(plan_path).expanduser().resolve()
    if not path.exists():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


# Fields known to be compatible with the older dj-process on Ray Worker.
_RECIPE_ALLOWED_KEYS = {
    "dataset_path",
    "export_path",
    "work_dir",
    "process",
    "executor_type",
    "np",
    "text_keys",
    "image_key",
    "audio_key",
    "video_key",
    "project_name",
    "open_tracer",
    "op_fusion",
    "custom_operator_paths",
}

# When executor_type=ray, single-machine deduplicators are incompatible with
# Ray's streaming DAG (they raise TypeError). Map them to their ray-native
# equivalents. Only 1:1 equivalents whose params migrate safely are listed;
# the minhash family is intentionally excluded (param signatures differ).
_RAY_DEDUP_REWRITE = {
    "image_deduplicator": "ray_image_deduplicator",
    "document_deduplicator": "ray_document_deduplicator",
    "video_deduplicator": "ray_video_deduplicator",
}

# Params accepted by the single-machine op but NOT by the ray-native variant;
# they must be dropped on rewrite to avoid a constructor TypeError.
_RAY_DEDUP_DROP_PARAMS = {
    "ray_image_deduplicator": {"consider_text"},
    "ray_video_deduplicator": {"consider_text"},
}


def _to_dj_process(raw_process: list) -> list:
    """Normalise a process list to DJ-native form ``[{op_name: params}, ...]``.

    The plan may carry ``process`` in either representation:
    - agent-internal ``[{"name": op, "params": {...}}, ...]``
    - DJ-native ``[{op_name: {...}}, ...]`` (what assemble_plan emits)
    Both are accepted and DJ-native form is returned, so downstream rewriting
    is form-independent and can never be silently skipped.
    """
    dj = []
    for step in raw_process:
        if not isinstance(step, dict):
            continue
        if "name" in step:
            name = str(step.get("name", "")).strip()
            if name:
                dj.append({name: step.get("params", {}) or {}})
        elif len(step) == 1:
            dj.append(step)
    return dj


def _rewrite_dedup_ops_for_ray(process: list) -> list:
    """Rewrite single-machine dedup ops to ray-native versions (executor=ray).

    ``process`` must be DJ-native form ``[{op_name: params}, ...]`` (run it
    through _to_dj_process first).
    - Only ops whose name is in _RAY_DEDUP_REWRITE are changed; everything else
      (mappers, filters, already-ray_ ops) is passed through untouched.
    - Params unsupported by the ray-native variant are dropped (with a warning)
      to avoid a constructor TypeError.
    - Idempotent: ops already using a ray_ prefix are not in the map, so they
      are left as-is.
    """
    rewritten = []
    for step in process:
        if not isinstance(step, dict) or len(step) != 1:
            rewritten.append(step)
            continue
        name, params = next(iter(step.items()))
        new_name = _RAY_DEDUP_REWRITE.get(str(name).strip())
        if not new_name:
            rewritten.append(step)
            continue
        params = dict(params or {})
        dropped = _RAY_DEDUP_DROP_PARAMS.get(new_name, set()) & params.keys()
        for key in dropped:
            params.pop(key, None)
        if dropped:
            _logger.warning(
                "Ray dedup rewrite: %s -> %s, dropped incompatible params %s",
                name,
                new_name,
                sorted(dropped),
            )
        else:
            _logger.info("Ray dedup rewrite: %s -> %s", name, new_name)
        rewritten.append({new_name: params})
    return rewritten


def _write_recipe(
    plan_payload: Dict[str, Any], output_dir: Path, exec_id: str
) -> Path:
    """Write a minimal DJ recipe YAML from plan payload.

    Key decisions:
    - executor_type is set to 'ray' so the job runs distributed on the
      cluster AND Ray is guaranteed to be initialized: RayExecutor.__init__
      calls initialize_ray(force=True), which lets both plain CPU ops
      (parallelized via Ray Data) and ray-native ops (e.g.
      ray_image_deduplicator, which needs ray.init()) run correctly.
      Inside a `ray job submit` job, ray.init(address="auto") attaches to
      the existing cluster; it does NOT use the blocked Ray Client port
      10001. Note: in ray mode the exporter treats export_path as a
      directory of shard files rather than a single file.
    - work_dir is forced to a Worker-local path (/tmp/...) keyed by the
      per-submission exec_id, so concurrent or repeated runs of the same
      plan never share logs/checkpoints. Otherwise
      data-juicer defaults it to os.path.dirname(export_path); when
      export_path is on an OSS FUSE mount, loguru's gz log compression
      calls os.remove() on the mount at shutdown, which the mount rejects
      (PermissionError -> job exits 1). Keeping logs/checkpoints/tmp on
      local disk avoids this; results still land at export_path.
    - Only emit fields known to be compatible with the Worker's older
      dj-process version; unsupported fields are dropped with a warning
      to avoid 'Option not accepted' errors.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    plan_id = str(plan_payload.get("plan_id", "")).strip() or "ray_job"
    recipe_path = output_dir / f"{plan_id}.yaml"

    recipe = plan_payload.get("recipe")
    if not isinstance(recipe, dict):
        raise ValueError("plan must contain a 'recipe' dict")

    recipe = dict(recipe)

    # Use ray executor: runs distributed on the cluster and guarantees Ray
    # initialization for ray-native ops (see docstring above).
    recipe["executor_type"] = "ray"
    recipe.setdefault("project_name", plan_id)

    # Force work_dir onto Worker-local disk so loguru's gz log compression
    # never runs os.remove() on an OSS FUSE mount (see docstring above).
    # Keyed by exec_id (unique per submission) rather than plan_id, so
    # overlapping runs of the same plan cannot stomp each other's state.
    recipe["work_dir"] = f"/tmp/dj_work_{plan_id}_{exec_id}"

    # Normalise process to DJ-native form [{op_name: params}] and rewrite
    # single-machine dedup ops to ray-native equivalents. The plan may store
    # process either as [{name, params}] (agent-internal) or as DJ-native
    # [{op_name: params}] (what assemble_plan emits); handle both so the
    # rewrite is never silently skipped. executor_type is forced to ray above
    # and Ray's streaming DAG cannot run single-machine deduplicators.
    raw_process = recipe.get("process", [])
    if isinstance(raw_process, list) and raw_process:
        recipe["process"] = _rewrite_dedup_ops_for_ray(_to_dj_process(raw_process))

    # Strip fields not supported by the Worker's older dj-process version.
    # Surface what gets dropped: a silently vanishing option (e.g.
    # eoc_special_token) is very hard to debug from the Ray side.
    dropped_keys = sorted(k for k in recipe if k not in _RECIPE_ALLOWED_KEYS)
    if dropped_keys:
        _logger.warning(
            "Recipe keys unsupported by the Worker's dj-process were dropped: %s",
            dropped_keys,
        )
    minimal_recipe = {
        k: v for k, v in recipe.items() if k in _RECIPE_ALLOWED_KEYS
    }

    with open(recipe_path, "w", encoding="utf-8") as handle:
        yaml.safe_dump(minimal_recipe, handle, allow_unicode=False, sort_keys=False)
    return recipe_path


def _classify_ray_error(returncode: int, stderr: str) -> tuple[str, str]:
    """Classify Ray job submission error."""
    msg = (stderr or "").lower()
    if returncode == 0:
        return "none", ""
    if "connectionerror" in msg or "failed to connect" in msg or "connection refused" in msg:
        return "connection_failed", "Cannot connect to Ray cluster. Verify RAY_ADDRESS and cluster status."
    if "no such file" in msg or "not found" in msg:
        return "command_not_found", "ray CLI not found. Ensure ray is installed in PATH."
    if "runtime_env" in msg or "package" in msg:
        return "packaging_failed", "Failed to package working directory for Ray cluster."
    if "timeout" in msg:
        return "timeout", "Job execution timed out."
    return "submission_failed", f"Ray job submission failed (exit code {returncode})."


def _uniquify_export_path(export_path: str, token: str) -> str:
    """Insert a per-run ``token`` before the file extension of ``export_path``.

    In ray executor mode RayExporter runs ``os.makedirs(export_path)`` and
    writes shard files inside that directory. Reusing the same path across runs
    is unsafe on an OSS FUSE mount: a pre-existing file there triggers
    ``FileExistsError`` and the mount usually forbids deleting it, while a
    pre-existing directory would accumulate stale shards from earlier runs.
    Giving every submission a fresh, unique path sidesteps both problems and
    needs no deletion. Example:
    ``.../car_cleaned.jsonl`` -> ``.../car_cleaned_ray_a1b2c3d4.jsonl``.
    """
    if not export_path or not token:
        return export_path
    path = Path(export_path)
    return str(path.with_name(f"{path.stem}_{token}{path.suffix}"))


def submit_ray_job(
    *,
    plan_path: str,
    ray_address: str | None = None,
    timeout_seconds: int = 600,
    no_wait: bool = False,
) -> Dict[str, Any]:
    """Submit a dj-process job to a Ray cluster via the Ray Job API.

    The plan's recipe is written with executor_type=ray and submitted via
    ``ray job submit -- dj-process --config <recipe>.yaml``. Returns a summary
    dict with job_id, status, and output.
    """
    # 1. Resolve Ray address
    address = (ray_address or "").strip() or os.environ.get("RAY_ADDRESS", "").strip()
    if not address:
        return {
            "ok": False,
            "error_type": "missing_ray_address",
            "message": (
                "No Ray address provided. Set RAY_ADDRESS environment variable "
                "or pass ray_address parameter explicitly."
            ),
        }

    # 2. Load plan
    plan_payload = _load_plan(plan_path)
    if plan_payload is None:
        return {
            "ok": False,
            "error_type": "plan_not_found",
            "message": f"Failed to load plan file: {plan_path}",
        }

    # 3. Prepare working directory and recipe
    exec_id = f"ray_{uuid4().hex[:8]}"
    # Staging dir for `ray job submit --working-dir` (holds the recipe YAML that
    # gets packaged and uploaded to the cluster). Keep it on Worker-local /tmp
    # rather than next to the plan: the plan often lives on an OSS FUSE mount
    # that forbids deletion, which would both litter the mount and break cleanup.
    working_dir = Path(tempfile.gettempdir()) / f".ray_submit_{exec_id}"
    dj_export_path = ""

    # Submit as a dj-process job with executor_type=ray. Uniquify export_path
    # per submission: in ray mode RayExporter runs os.makedirs(export_path);
    # reusing a path collides with a prior run's file/dir on the OSS mount
    # (which forbids deletion). A fresh path per run avoids FileExistsError
    # and stale-shard accumulation entirely. Work on a copy of the recipe so
    # the caller's plan payload is never mutated in place.
    _recipe = plan_payload.get("recipe")
    if isinstance(_recipe, dict):
        _recipe = dict(_recipe)
        if str(_recipe.get("export_path", "")).strip():
            _recipe["export_path"] = _uniquify_export_path(
                str(_recipe["export_path"]).strip(), exec_id
            )
        plan_payload = {**plan_payload, "recipe": _recipe}
    try:
        recipe_path = _write_recipe(plan_payload, working_dir, exec_id)
    except ValueError as exc:
        shutil.rmtree(working_dir, ignore_errors=True)
        return {
            "ok": False,
            "error_type": "invalid_plan",
            "message": str(exc),
        }

    recipe_filename = recipe_path.name
    dj_export_path = str((plan_payload.get("recipe") or {}).get("export_path", "")).strip()

    cmd = [
        "ray", "job", "submit",
        "--address", address,
        "--working-dir", str(working_dir),
    ]
    if no_wait:
        cmd.append("--no-wait")
    cmd.extend(["--", "dj-process", "--config", recipe_filename])

    command_display = shlex.join(cmd)
    _logger.info("Submitting Ray job: %s", command_display)

    # 5. Execute
    start_dt = datetime.now(timezone.utc)
    try:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            returncode = result.returncode
            stdout = result.stdout
            stderr = result.stderr
        except subprocess.TimeoutExpired:
            end_dt = datetime.now(timezone.utc)
            return {
                "ok": False,
                "error_type": "timeout",
                "message": f"Ray job submission timed out after {timeout_seconds}s",
                "command": command_display,
                "duration_seconds": (end_dt - start_dt).total_seconds(),
            }
        except FileNotFoundError:
            return {
                "ok": False,
                "error_type": "command_not_found",
                "message": "ray CLI not found. Ensure ray package is installed.",
                "command": command_display,
            }
        except Exception as exc:
            return {
                "ok": False,
                "error_type": "unexpected_error",
                "message": f"Unexpected error during submission: {exc}",
                "command": command_display,
            }
    finally:
        # working_dir has already been packaged/uploaded to the cluster by the
        # time `ray job submit` returns, so it is safe to remove. ignore_errors
        # ensures cleanup never breaks an otherwise successful submission.
        shutil.rmtree(working_dir, ignore_errors=True)

    end_dt = datetime.now(timezone.utc)
    duration = (end_dt - start_dt).total_seconds()

    # 6. Parse job_id
    job_id = ""
    match = _JOB_ID_PATTERN.search(stdout)
    if match:
        job_id = match.group(1)

    # 7. Classify result
    if returncode != 0:
        error_type, error_msg = _classify_ray_error(returncode, stderr)
        return {
            "ok": False,
            "error_type": error_type,
            "message": error_msg,
            "job_id": job_id,
            "command": command_display,
            "stdout": stdout[-2000:] if len(stdout) > 2000 else stdout,
            "stderr": stderr[-2000:] if len(stderr) > 2000 else stderr,
            "duration_seconds": duration,
        }

    # Determine job status from output. Match Ray's specific final-status line
    # (which embeds job_id) to avoid false positives from "succeeded"/"failed"
    # appearing in the job's own logs that `ray job submit` tails into stdout.
    if job_id:
        succeeded = bool(re.search(rf"Job '{re.escape(job_id)}' succeeded", stdout, re.IGNORECASE))
        failed = bool(re.search(rf"Job '{re.escape(job_id)}' failed", stdout, re.IGNORECASE))
    else:
        succeeded = "succeeded" in stdout.lower()
        failed = "failed" in stdout.lower() and not succeeded

    status = "succeeded" if succeeded else ("failed" if failed else "submitted")

    return {
        "ok": not failed,
        "job_id": job_id,
        "status": status,
        "ray_address": address,
        "command": command_display,
        "working_dir": str(working_dir),
        "export_path": dj_export_path,
        "stdout": stdout[-3000:] if len(stdout) > 3000 else stdout,
        "stderr": stderr[-1000:] if len(stderr) > 1000 else stderr,
        "duration_seconds": duration,
        "message": (
            f"Ray job {job_id} {status} (took {duration:.1f}s)"
            if job_id
            else f"Ray job {status} (took {duration:.1f}s)"
        ),
    }


__all__ = ["submit_ray_job"]
