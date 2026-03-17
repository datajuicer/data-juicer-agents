#!/usr/bin/env python3
"""
Evaluation Metrics Scorer for Skills Ablation Experiment.

This script reads the output JSONL files from eval_cases/run_eval.py and computes
comparison metrics for the skills ablation experiment (with_skills vs without_skills).

Usage:
    python eval_cases/score_eval.py --results-dir eval_cases/results/
    python eval_cases/score_eval.py --with-skills X.jsonl --without-skills Y.jsonl
    python eval_cases/score_eval.py --results-dir eval_cases/results/ --output report.md
"""

import sys as _sys
from pathlib import Path as _Path
_project_root = _Path(__file__).resolve().parent.parent
if str(_project_root) not in _sys.path:
    _sys.path.insert(0, str(_project_root))
del _sys, _Path, _project_root  # clean up namespace

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean, stdev
from typing import Any, Dict, List, Optional, Tuple


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Score evaluation results from skills ablation experiment.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Auto-detect most recent result pair
  python eval_cases/score_eval.py --results-dir eval_cases/results/

  # Explicit file paths
  python eval_cases/score_eval.py --with-skills with_skills_XXX.jsonl --without-skills without_skills_XXX.jsonl

  # Single condition only
  python eval_cases/score_eval.py --with-skills with_skills_XXX.jsonl

  # Save report to file
  python eval_cases/score_eval.py --results-dir eval_cases/results/ --output report.md
        """,
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        help="Directory containing result JSONL files. Auto-detects most recent pair.",
    )
    parser.add_argument(
        "--with-skills",
        type=Path,
        help="Path to with_skills result JSONL file.",
    )
    parser.add_argument(
        "--without-skills",
        type=Path,
        help="Path to without_skills result JSONL file.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Output file path for the report (Markdown format).",
    )
    parser.add_argument(
        "--detail",
        action="store_true",
        help="Include per-case detail comparison table.",
    )
    parser.add_argument(
        "--eval-tier",
        choices=["smoke", "baseline", "hard"],
        help="Manually specify the evaluation tier for labeling.",
    )
    return parser.parse_args()


def extract_timestamp(filename: str) -> Optional[datetime]:
    """Extract timestamp from filename like with_skills_20260317_120000.jsonl."""
    match = re.search(r"(\d{8}_\d{6})\.jsonl$", filename)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y%m%d_%H%M%S")
        except ValueError:
            return None
    return None


def find_latest_pair(
    results_dir: Path,
) -> Tuple[Optional[Path], Optional[Path]]:
    """
    Find the most recent pair of with_skills and without_skills result files.

    Returns:
        Tuple of (with_skills_path, without_skills_path), either may be None.
    """
    with_skills_files: List[Tuple[datetime, Path]] = []
    without_skills_files: List[Tuple[datetime, Path]] = []

    for f in results_dir.glob("*.jsonl"):
        ts = extract_timestamp(f.name)
        if ts is None:
            continue
        if f.name.startswith("with_skills_"):
            with_skills_files.append((ts, f))
        elif f.name.startswith("without_skills_"):
            without_skills_files.append((ts, f))

    with_skills_files.sort(reverse=True, key=lambda x: x[0])
    without_skills_files.sort(reverse=True, key=lambda x: x[0])

    with_skills_path = with_skills_files[0][1] if with_skills_files else None
    without_skills_path = without_skills_files[0][1] if without_skills_files else None

    return with_skills_path, without_skills_path


def load_results(filepath: Path) -> List[Dict[str, Any]]:
    """Load results from a JSONL file."""
    results = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                results.append(json.loads(line))
    return results


def compute_metrics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compute aggregate metrics from a list of result records.

    Returns:
        Dictionary containing all computed metrics.
    """
    if not results:
        return {
            "count": 0,
            "workflow_accuracy": 0.0,
            "plan_validity": 0.0,
            "execution_success": 0.0,
            "avg_tokens": 0.0,
            "avg_prompt_tokens": 0.0,
            "avg_completion_tokens": 0.0,
            "avg_tool_calls": 0.0,
            "avg_reasoning_steps": 0.0,
            "avg_wall_clock": 0.0,
            "error_rate": 0.0,
            "std_tokens": 0.0,
            "std_tool_calls": 0.0,
            "std_wall_clock": 0.0,
        }

    count = len(results)

    # Boolean metrics
    workflow_matches = sum(1 for r in results if r.get("workflow_match", False))
    plan_valids = sum(1 for r in results if r.get("plan_valid", False))
    execution_successes = sum(1 for r in results if r.get("execution_success", False))
    error_cases = sum(1 for r in results if r.get("error_messages"))

    # Numeric metrics
    total_tokens = [
        r.get("token_usage", {}).get("total_tokens", 0) for r in results
    ]
    prompt_tokens = [
        r.get("token_usage", {}).get("prompt_tokens", 0) for r in results
    ]
    completion_tokens = [
        r.get("token_usage", {}).get("completion_tokens", 0) for r in results
    ]
    tool_calls = [r.get("tool_call_count", 0) for r in results]
    reasoning_steps = [r.get("reasoning_step_count", 0) for r in results]
    wall_clocks = [r.get("wall_clock_seconds", 0.0) for r in results]

    return {
        "count": count,
        "workflow_accuracy": (workflow_matches / count) * 100,
        "plan_validity": (plan_valids / count) * 100,
        "execution_success": (execution_successes / count) * 100,
        "avg_tokens": mean(total_tokens),
        "avg_prompt_tokens": mean(prompt_tokens),
        "avg_completion_tokens": mean(completion_tokens),
        "avg_tool_calls": mean(tool_calls),
        "avg_reasoning_steps": mean(reasoning_steps),
        "avg_wall_clock": mean(wall_clocks),
        "error_rate": (error_cases / count) * 100,
        "std_tokens": stdev(total_tokens) if count > 1 else 0.0,
        "std_tool_calls": stdev(tool_calls) if count > 1 else 0.0,
        "std_wall_clock": stdev(wall_clocks) if count > 1 else 0.0,
    }


def format_rate_delta(with_val: float, without_val: float) -> str:
    """Format delta for rate metrics (percentage points)."""
    delta = with_val - without_val
    sign = "+" if delta >= 0 else ""
    return f"{sign}{delta:.1f}pp"


def format_avg_delta(with_val: float, without_val: float) -> str:
    """Format delta for average metrics (percentage change)."""
    if without_val == 0:
        return "N/A"
    delta_pct = ((with_val - without_val) / without_val) * 100
    sign = "+" if delta_pct >= 0 else ""
    return f"{sign}{delta_pct:.1f}%"


def format_number(val: float, decimals: int = 1) -> str:
    """Format number with thousands separator."""
    if val >= 1000:
        return f"{val:,.{decimals}f}"
    return f"{val:.{decimals}f}"


def infer_tier(case_count: int) -> str:
    """Infer evaluation tier from case count."""
    if case_count == 2:
        return "smoke"
    elif case_count == 20:
        return "baseline"
    elif case_count == 10:
        return "hard"
    else:
        return "unknown"


def generate_header(
    with_skills_path: Optional[Path],
    without_skills_path: Optional[Path],
    with_metrics: Optional[Dict[str, Any]],
    without_metrics: Optional[Dict[str, Any]],
    eval_tier: Optional[str],
) -> str:
    """Generate report header with experiment metadata."""
    lines = ["# Skills Ablation Evaluation Report", ""]
    lines.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    if with_skills_path:
        ts = extract_timestamp(with_skills_path.name)
        ts_str = ts.strftime("%Y-%m-%d %H:%M:%S") if ts else "unknown"
        lines.append(f"**With Skills File**: `{with_skills_path.name}` (run: {ts_str})")
    if without_skills_path:
        ts = extract_timestamp(without_skills_path.name)
        ts_str = ts.strftime("%Y-%m-%d %H:%M:%S") if ts else "unknown"
        lines.append(f"**Without Skills File**: `{without_skills_path.name}` (run: {ts_str})")

    lines.append("")

    if with_metrics:
        lines.append(f"**With Skills Cases**: {with_metrics['count']}")
    if without_metrics:
        lines.append(f"**Without Skills Cases**: {without_metrics['count']}")

    # Determine tier
    case_count = (with_metrics or without_metrics or {}).get("count", 0)
    tier = eval_tier or infer_tier(case_count)
    lines.append(f"**Evaluation Tier**: {tier}")

    lines.append("")
    return "\n".join(lines)


def generate_single_condition_table(
    condition: str, metrics: Dict[str, Any]
) -> str:
    """Generate metrics table for a single condition."""
    lines = [f"## {condition} Metrics", ""]
    lines.append("| Metric                     | Value          |")
    lines.append("|----------------------------|----------------|")
    lines.append(f"| Cases Evaluated            | {metrics['count']}              |")
    lines.append(f"| Workflow Accuracy          | {metrics['workflow_accuracy']:.1f}%          |")
    lines.append(f"| Plan Validity              | {metrics['plan_validity']:.1f}%          |")
    lines.append(f"| Execution Success          | {metrics['execution_success']:.1f}%          |")
    lines.append(f"| Avg Tokens/Case            | {format_number(metrics['avg_tokens'])}        |")
    lines.append(f"|   - Prompt Tokens          | {format_number(metrics['avg_prompt_tokens'])}        |")
    lines.append(f"|   - Completion Tokens      | {format_number(metrics['avg_completion_tokens'])}        |")
    lines.append(f"| Avg Tool Calls             | {metrics['avg_tool_calls']:.1f}            |")
    lines.append(f"| Avg Reasoning Steps        | {metrics['avg_reasoning_steps']:.1f}            |")
    lines.append(f"| Avg Time (s)               | {metrics['avg_wall_clock']:.2f}           |")
    lines.append(f"| Error Rate                 | {metrics['error_rate']:.1f}%          |")
    lines.append("")
    return "\n".join(lines)


def generate_comparison_table(
    with_metrics: Dict[str, Any], without_metrics: Dict[str, Any]
) -> str:
    """Generate the main comparison table."""
    lines = ["## Overall Comparison", ""]
    lines.append("| Metric                | With Skills | Without Skills | Delta    |")
    lines.append("|-----------------------|-------------|----------------|----------|")

    # Workflow Accuracy
    lines.append(
        f"| Workflow Accuracy     | {with_metrics['workflow_accuracy']:.1f}%       "
        f"| {without_metrics['workflow_accuracy']:.1f}%          "
        f"| {format_rate_delta(with_metrics['workflow_accuracy'], without_metrics['workflow_accuracy'])}  |"
    )

    # Plan Validity
    lines.append(
        f"| Plan Validity         | {with_metrics['plan_validity']:.1f}%       "
        f"| {without_metrics['plan_validity']:.1f}%          "
        f"| {format_rate_delta(with_metrics['plan_validity'], without_metrics['plan_validity'])}  |"
    )

    # Execution Success
    lines.append(
        f"| Execution Success     | {with_metrics['execution_success']:.1f}%       "
        f"| {without_metrics['execution_success']:.1f}%          "
        f"| {format_rate_delta(with_metrics['execution_success'], without_metrics['execution_success'])}  |"
    )

    # Avg Tokens
    lines.append(
        f"| Avg Tokens/Case       | {format_number(with_metrics['avg_tokens'])}       "
        f"| {format_number(without_metrics['avg_tokens'])}          "
        f"| {format_avg_delta(with_metrics['avg_tokens'], without_metrics['avg_tokens'])}   |"
    )

    # Avg Tool Calls
    lines.append(
        f"| Avg Tool Calls        | {with_metrics['avg_tool_calls']:.1f}         "
        f"| {without_metrics['avg_tool_calls']:.1f}            "
        f"| {format_avg_delta(with_metrics['avg_tool_calls'], without_metrics['avg_tool_calls'])}   |"
    )

    # Avg Reasoning Steps
    lines.append(
        f"| Avg Reasoning Steps   | {with_metrics['avg_reasoning_steps']:.1f}         "
        f"| {without_metrics['avg_reasoning_steps']:.1f}            "
        f"| {format_avg_delta(with_metrics['avg_reasoning_steps'], without_metrics['avg_reasoning_steps'])}   |"
    )

    # Avg Time
    lines.append(
        f"| Avg Time (s)          | {with_metrics['avg_wall_clock']:.1f}        "
        f"| {without_metrics['avg_wall_clock']:.1f}           "
        f"| {format_avg_delta(with_metrics['avg_wall_clock'], without_metrics['avg_wall_clock'])}   |"
    )

    # Error Rate
    lines.append(
        f"| Error Rate            | {with_metrics['error_rate']:.1f}%       "
        f"| {without_metrics['error_rate']:.1f}%          "
        f"| {format_rate_delta(with_metrics['error_rate'], without_metrics['error_rate'])}  |"
    )

    lines.append("")
    lines.append("*Note: For rates, delta shows percentage points (pp). "
                 "For averages, delta shows percentage change.*")
    lines.append("")
    return "\n".join(lines)


def generate_workflow_breakdown(
    with_results: List[Dict[str, Any]],
    without_results: List[Dict[str, Any]],
) -> str:
    """Generate breakdown table by workflow type."""
    lines = ["## Breakdown by Workflow Type", ""]

    # Group results by workflow type
    def group_by_workflow(results: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for r in results:
            workflow = r.get("expected_workflow", "unknown")
            groups[workflow].append(r)
        return dict(groups)

    with_groups = group_by_workflow(with_results) if with_results else {}
    without_groups = group_by_workflow(without_results) if without_results else {}

    all_workflows = set(with_groups.keys()) | set(without_groups.keys())

    if not all_workflows:
        lines.append("*No workflow data available.*")
        lines.append("")
        return "\n".join(lines)

    lines.append("| Workflow        | Condition      | Cases | Accuracy | Plan Valid | Avg Tools | Avg Time |")
    lines.append("|-----------------|----------------|-------|----------|------------|-----------|----------|")

    for workflow in sorted(all_workflows):
        # With skills
        if workflow in with_groups:
            m = compute_metrics(with_groups[workflow])
            lines.append(
                f"| {workflow:<15} | With Skills    | {m['count']:<5} | {m['workflow_accuracy']:.1f}%    "
                f"| {m['plan_validity']:.1f}%      | {m['avg_tool_calls']:.1f}       | {m['avg_wall_clock']:.1f}s     |"
            )

        # Without skills
        if workflow in without_groups:
            m = compute_metrics(without_groups[workflow])
            lines.append(
                f"| {workflow:<15} | Without Skills | {m['count']:<5} | {m['workflow_accuracy']:.1f}%    "
                f"| {m['plan_validity']:.1f}%      | {m['avg_tool_calls']:.1f}       | {m['avg_wall_clock']:.1f}s     |"
            )

    lines.append("")
    return "\n".join(lines)


def generate_detail_table(
    with_results: List[Dict[str, Any]],
    without_results: List[Dict[str, Any]],
) -> str:
    """Generate per-case detail comparison table."""
    lines = ["## Per-Case Detail Comparison", ""]

    # Index results by case_id
    with_by_case = {r.get("case_id"): r for r in with_results} if with_results else {}
    without_by_case = {r.get("case_id"): r for r in without_results} if without_results else {}

    all_cases = sorted(set(with_by_case.keys()) | set(without_by_case.keys()))

    if not all_cases:
        lines.append("*No case data available.*")
        lines.append("")
        return "\n".join(lines)

    lines.append("| Case ID  | Expected       | With Skills    | Without Skills | Match W | Match WO |")
    lines.append("|----------|----------------|----------------|----------------|---------|----------|")

    for case_id in all_cases:
        with_r = with_by_case.get(case_id, {})
        without_r = without_by_case.get(case_id, {})

        expected = with_r.get("expected_workflow") or without_r.get("expected_workflow", "-")
        with_gen = with_r.get("generated_workflow", "-") or "-"
        without_gen = without_r.get("generated_workflow", "-") or "-"

        with_match = "PASS" if with_r.get("workflow_match") else "FAIL" if with_r else "-"
        without_match = "PASS" if without_r.get("workflow_match") else "FAIL" if without_r else "-"

        lines.append(
            f"| {case_id:<8} | {expected:<14} | {with_gen:<14} | {without_gen:<14} "
            f"| {with_match:<7} | {without_match:<8} |"
        )

    lines.append("")
    return "\n".join(lines)


def generate_token_breakdown(
    with_metrics: Dict[str, Any], without_metrics: Dict[str, Any]
) -> str:
    """Generate detailed token usage breakdown."""
    lines = ["## Token Usage Breakdown", ""]
    lines.append("| Token Type        | With Skills | Without Skills | Delta    |")
    lines.append("|-------------------|-------------|----------------|----------|")

    lines.append(
        f"| Prompt Tokens     | {format_number(with_metrics['avg_prompt_tokens'])}       "
        f"| {format_number(without_metrics['avg_prompt_tokens'])}          "
        f"| {format_avg_delta(with_metrics['avg_prompt_tokens'], without_metrics['avg_prompt_tokens'])}   |"
    )

    lines.append(
        f"| Completion Tokens | {format_number(with_metrics['avg_completion_tokens'])}       "
        f"| {format_number(without_metrics['avg_completion_tokens'])}          "
        f"| {format_avg_delta(with_metrics['avg_completion_tokens'], without_metrics['avg_completion_tokens'])}   |"
    )

    lines.append(
        f"| Total Tokens      | {format_number(with_metrics['avg_tokens'])}       "
        f"| {format_number(without_metrics['avg_tokens'])}          "
        f"| {format_avg_delta(with_metrics['avg_tokens'], without_metrics['avg_tokens'])}   |"
    )

    lines.append("")
    return "\n".join(lines)


def generate_error_summary(
    with_results: List[Dict[str, Any]],
    without_results: List[Dict[str, Any]],
) -> str:
    """Generate error summary section."""
    lines = ["## Error Summary", ""]

    def collect_errors(results: List[Dict[str, Any]]) -> Dict[str, int]:
        error_counts: Dict[str, int] = defaultdict(int)
        for r in results:
            errors = r.get("error_messages", [])
            for err in errors:
                # Extract tool name from error format "tool_name: description"
                if ":" in err:
                    tool = err.split(":")[0].strip()
                else:
                    tool = "unknown"
                error_counts[tool] += 1
        return dict(error_counts)

    with_errors = collect_errors(with_results) if with_results else {}
    without_errors = collect_errors(without_results) if without_results else {}

    all_tools = sorted(set(with_errors.keys()) | set(without_errors.keys()))

    if not all_tools:
        lines.append("*No errors recorded.*")
        lines.append("")
        return "\n".join(lines)

    lines.append("| Tool/Source       | With Skills | Without Skills |")
    lines.append("|-------------------|-------------|----------------|")

    for tool in all_tools:
        w_count = with_errors.get(tool, 0)
        wo_count = without_errors.get(tool, 0)
        lines.append(f"| {tool:<17} | {w_count:<11} | {wo_count:<14} |")

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    """Main entry point."""
    args = parse_args()

    with_skills_path: Optional[Path] = args.with_skills
    without_skills_path: Optional[Path] = args.without_skills

    # Auto-detection mode
    if args.results_dir and not (with_skills_path and without_skills_path):
        if not args.results_dir.exists():
            print(f"Error: Results directory not found: {args.results_dir}", file=sys.stderr)
            return 1

        detected_with, detected_without = find_latest_pair(args.results_dir)

        if with_skills_path is None and detected_with:
            with_skills_path = detected_with
            print(f"Auto-detected with_skills file: {with_skills_path.name}")

        if without_skills_path is None and detected_without:
            without_skills_path = detected_without
            print(f"Auto-detected without_skills file: {without_skills_path.name}")

        if with_skills_path is None and without_skills_path is None:
            print("Error: No result files found in results directory.", file=sys.stderr)
            return 1

        print()

    # Validate we have at least one file
    if with_skills_path is None and without_skills_path is None:
        print(
            "Error: Must specify --results-dir or at least one of "
            "--with-skills / --without-skills",
            file=sys.stderr,
        )
        return 1

    # Load results
    with_results: List[Dict[str, Any]] = []
    without_results: List[Dict[str, Any]] = []

    if with_skills_path:
        if not with_skills_path.exists():
            print(f"Error: File not found: {with_skills_path}", file=sys.stderr)
            return 1
        with_results = load_results(with_skills_path)
        print(f"Loaded {len(with_results)} cases from with_skills file")

    if without_skills_path:
        if not without_skills_path.exists():
            print(f"Error: File not found: {without_skills_path}", file=sys.stderr)
            return 1
        without_results = load_results(without_skills_path)
        print(f"Loaded {len(without_results)} cases from without_skills file")

    print()

    # Compute metrics
    with_metrics = compute_metrics(with_results) if with_results else None
    without_metrics = compute_metrics(without_results) if without_results else None

    # Build report
    report_parts: List[str] = []

    # Header
    report_parts.append(
        generate_header(
            with_skills_path,
            without_skills_path,
            with_metrics,
            without_metrics,
            args.eval_tier,
        )
    )

    # Main comparison or single condition
    if with_metrics and without_metrics:
        # Full comparison mode
        report_parts.append(generate_comparison_table(with_metrics, without_metrics))
        report_parts.append(generate_token_breakdown(with_metrics, without_metrics))
        report_parts.append(generate_workflow_breakdown(with_results, without_results))
        report_parts.append(generate_error_summary(with_results, without_results))

        if args.detail:
            report_parts.append(generate_detail_table(with_results, without_results))
    elif with_metrics:
        # Single condition: with_skills only
        report_parts.append(generate_single_condition_table("With Skills", with_metrics))
        report_parts.append(
            generate_workflow_breakdown(with_results, [])
        )
    elif without_metrics:
        # Single condition: without_skills only
        report_parts.append(generate_single_condition_table("Without Skills", without_metrics))
        report_parts.append(
            generate_workflow_breakdown([], without_results)
        )

    # Combine and output
    full_report = "\n".join(report_parts)

    # Print to stdout
    print(full_report)

    # Save to file if requested
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(full_report)
        print(f"\nReport saved to: {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
