# -*- coding: utf-8 -*-
"""CLI entrypoint for the ``djx`` command."""

from __future__ import annotations

import argparse
from importlib import import_module
import sys

from data_juicer_agents import __version__
from data_juicer_agents.utils.optional_deps import missing_dependency_message


_COMMAND_HANDLER_SPECS = {
    "plan": {
        "module": "data_juicer_agents.commands.plan_cmd",
        "handler": "run_plan",
        "feature": "djx plan",
        "extras": ("harness", "core"),
    },
    "apply": {
        "module": "data_juicer_agents.commands.apply_cmd",
        "handler": "run_apply",
        "feature": "djx apply",
        "extras": ("harness", "core"),
    },
    "retrieve": {
        "module": "data_juicer_agents.commands.retrieve_cmd",
        "handler": "run_retrieve",
        "feature": "djx retrieve",
        "extras": ("core",),
    },
    "dev": {
        "module": "data_juicer_agents.commands.dev_cmd",
        "handler": "run_dev",
        "feature": "djx dev",
        "extras": ("harness", "core"),
    },
    "tool": {
        "module": "data_juicer_agents.commands.tool_cmd",
        "handler": "run_tool",
        "feature": "djx tool",
        "extras": ("harness", "core"),
    },
}


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
        description="Agentic CLI for Data-Juicer workflows",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
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
    plan.set_defaults(handler_name="plan")

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
    apply_cmd.set_defaults(handler_name="apply")

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
        choices=["auto", "llm", "vector", "bm25", "regex"],
        default="auto",
        help="Retrieval backend mode",
    )
    retrieve.add_argument(
        "--dataset",
        default=None,
        help="Optional dataset path for schema/modality probing",
    )
    retrieve.add_argument(
        "--type",
        dest="op_type",
        default=None,
        help="Filter by operator type (e.g. filter, mapper, deduplicator)",
    )
    retrieve.add_argument(
        "--tags",
        nargs="*",
        default=None,
        help="Filter by operator tags (e.g. text image multimodal)",
    )
    retrieve.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON payload",
    )
    retrieve.set_defaults(handler_name="retrieve")

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
    dev.set_defaults(handler_name="dev")

    tool = sub.add_parser(
        "tool",
        help="Inspect or execute atomic built-in tools",
        parents=[output_parent],
    )
    tool_sub = tool.add_subparsers(dest="tool_action", required=True)

    tool_list = tool_sub.add_parser(
        "list",
        help="List all registered tools",
        parents=[output_parent],
    )
    tool_list.add_argument(
        "--tag",
        action="append",
        default=[],
        help="Optional tag filter; may be repeated",
    )
    tool_list.set_defaults(handler_name="tool")

    tool_schema = tool_sub.add_parser(
        "schema",
        help="Show tool metadata and input schema",
        parents=[output_parent],
    )
    tool_schema.add_argument("tool_name", type=str, help="Registered tool name")
    tool_schema.set_defaults(handler_name="tool")

    tool_run = tool_sub.add_parser(
        "run",
        help="Execute a tool with JSON input",
        parents=[output_parent],
    )
    tool_run.add_argument("tool_name", type=str, help="Registered tool name")
    input_group = tool_run.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--input-json",
        default=None,
        help="Inline JSON object input for the tool",
    )
    input_group.add_argument(
        "--input-file",
        default=None,
        help="Path to a JSON file containing the tool input object",
    )
    tool_run.add_argument(
        "--working-dir",
        default=None,
        help="Working directory used to build ToolContext",
    )
    tool_run.add_argument(
        "--yes",
        action="store_true",
        help="Explicitly confirm running write/execute tools",
    )
    tool_run.set_defaults(handler_name="tool")

    return parser


def _load_handler(handler_name: str):
    spec = _COMMAND_HANDLER_SPECS.get(str(handler_name or "").strip())
    if spec is None:
        raise KeyError(f"unknown command handler: {handler_name}")

    try:
        module = import_module(str(spec["module"]))
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            missing_dependency_message(
                str(spec["feature"]),
                extras=tuple(spec["extras"]),
                missing_module=getattr(exc, "name", None),
            )
        ) from exc
    return getattr(module, str(spec["handler"]))


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        handler = _load_handler(str(getattr(args, "handler_name", "") or ""))
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return int(handler(args))


if __name__ == "__main__":
    sys.exit(main())
