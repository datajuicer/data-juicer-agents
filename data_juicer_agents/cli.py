# -*- coding: utf-8 -*-
"""CLI entrypoint for Data-Juicer-Agents v0.1."""

from __future__ import annotations

import argparse
import sys

from data_juicer_agents.commands.apply_cmd import run_apply
from data_juicer_agents.commands.dev_cmd import run_dev
from data_juicer_agents.commands.plan_cmd import run_plan
from data_juicer_agents.commands.retrieve_cmd import run_retrieve


def _add_output_level_args(
    parser: argparse.ArgumentParser,
    *,
    set_default: bool,
) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--quiet",
        dest="output_level",
        action="store_const",
        const="quiet",
        default=argparse.SUPPRESS,
        help="Summary output (default)",
    )
    group.add_argument(
        "--verbose",
        dest="output_level",
        action="store_const",
        const="verbose",
        default=argparse.SUPPRESS,
        help="Expand tool execution output",
    )
    group.add_argument(
        "--debug",
        dest="output_level",
        action="store_const",
        const="debug",
        default=argparse.SUPPRESS,
        help="Include raw call details for debugging",
    )
    if set_default:
        parser.set_defaults(output_level="quiet")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="djx",
        description="Agentic CLI for Data-Juicer workflows (v0.1)",
    )
    _add_output_level_args(parser, set_default=True)
    output_parent = argparse.ArgumentParser(add_help=False)
    _add_output_level_args(output_parent, set_default=False)
    sub = parser.add_subparsers(dest="command", required=True)

    plan = sub.add_parser(
        "plan",
        help="Generate a structured execution plan",
        parents=[output_parent],
    )
    plan.add_argument("intent", type=str, help="Natural language task intent")
    plan.add_argument("--dataset", default=None, help="Input dataset path")
    plan.add_argument("--export", default=None, help="Output jsonl path")
    plan.add_argument("--output", default=None, help="Output plan yaml path")
    plan.add_argument(
        "--custom-operator-paths",
        nargs="+",
        default=None,
        help="Optional custom operator directories/files for validation/execution",
    )
    plan.set_defaults(handler=run_plan)

    apply_cmd = sub.add_parser(
        "apply",
        help="Apply a generated plan",
        parents=[output_parent],
    )
    apply_cmd.add_argument("--plan", required=True, help="Plan yaml path")
    apply_cmd.add_argument("--yes", action="store_true", help="Skip confirmation")
    apply_cmd.add_argument("--dry-run", action="store_true", help="Do not execute dj-process")
    apply_cmd.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Execution timeout in seconds",
    )
    apply_cmd.set_defaults(handler=run_apply)

    retrieve = sub.add_parser(
        "retrieve",
        help="Retrieve relevant Data-Juicer operators from natural language intent",
        parents=[output_parent],
    )
    retrieve.add_argument("intent", type=str, help="Natural language operator need")
    retrieve.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="Maximum candidate operators to return",
    )
    retrieve.add_argument(
        "--mode",
        choices=["auto", "llm", "vector"],
        default="auto",
        help="Retrieval backend mode",
    )
    retrieve.add_argument(
        "--dataset",
        default=None,
        help="Optional dataset path for schema/modality probing",
    )
    retrieve.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON payload",
    )
    retrieve.set_defaults(handler=run_retrieve)

    dev = sub.add_parser(
        "dev",
        help="Generate a non-invasive custom Data-Juicer operator scaffold",
        parents=[output_parent],
    )
    dev.add_argument("intent", type=str, help="Natural language operator requirement")
    dev.add_argument(
        "--operator-name",
        required=True,
        help="Target operator name (snake_case; suffix inferred if omitted)",
    )
    dev.add_argument(
        "--output-dir",
        required=True,
        help="Directory to write generated operator scaffold files",
    )
    dev.add_argument(
        "--type",
        choices=["mapper", "filter"],
        default=None,
        help="Optional operator type (mapper/filter)",
    )
    dev.add_argument(
        "--from-retrieve",
        default=None,
        help="Optional path to djx retrieve JSON output for design context",
    )
    dev.add_argument(
        "--smoke-check",
        action="store_true",
        help="Run an optional local dj-process smoke check using custom_operator_paths",
    )
    dev.set_defaults(handler=run_dev)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    sys.exit(main())
