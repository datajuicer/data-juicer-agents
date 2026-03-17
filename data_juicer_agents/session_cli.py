# -*- coding: utf-8 -*-
"""Interactive session entrypoint for `dj-agents`."""

from __future__ import annotations

import argparse
import sys
import threading

from data_juicer_agents.capabilities.session.orchestrator import DJSessionAgent
from data_juicer_agents.utils.agentscope_logging import install_thinking_warning_filter
from data_juicer_agents.utils.terminal_input import TerminalLineReader


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dj-agents",
        description="ReAct conversational entry for DJX atomic capabilities (LLM required)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable detailed session logs (tool calls and ReAct console output)",
    )
    parser.add_argument(
        "--dataset",
        default=None,
        help="Optional initial dataset path for session memory",
    )
    parser.add_argument(
        "--export",
        default=None,
        help="Optional initial export path for session memory",
    )
    parser.add_argument(
        "--ui",
        choices=["plain", "tui"],
        default="tui",
        help="Session UI mode (default: tui)",
    )
    return parser


def _wait_for_turn(done: threading.Event, timeout_sec: float = 0.05) -> bool:
    return bool(done.wait(timeout_sec))


def _new_line_reader() -> TerminalLineReader:
    return TerminalLineReader()


def _run_turn_with_interrupt(agent: DJSessionAgent, message: str):
    result: dict = {}
    error: dict = {}
    done = threading.Event()

    def _worker():
        try:
            result["reply"] = agent.handle_message(message)
        except Exception as exc:
            error["error"] = exc
        finally:
            done.set()

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    interrupt_sent = False
    while True:
        try:
            if _wait_for_turn(done, 0.05):
                break
        except KeyboardInterrupt:
            if not interrupt_sent and agent.request_interrupt():
                interrupt_sent = True
                print("\n[dj-agents] Interrupt requested (Ctrl+C).")
            else:
                print("\n[dj-agents] Interrupt ignored.")

    thread.join()
    if "error" in error:
        raise error["error"]
    return result["reply"]


def _run_plain_session(args: argparse.Namespace) -> int:
    try:
        agent = DJSessionAgent(
            use_llm_router=True,
            dataset_path=args.dataset,
            export_path=args.export,
            verbose=args.verbose,
        )
    except Exception as exc:
        print(f"Failed to start dj-agents session: {exc}")
        return 2
    line_reader = _new_line_reader()
    print("DJ session started. Describe your task in natural language. Type `help` or `exit`.")
    print("Press Ctrl+C to interrupt the current turn. Press Ctrl+D to exit the session.")

    while True:
        try:
            message = line_reader.read_line("you> ")
        except EOFError:
            print("\nSession ended.")
            return 0
        except KeyboardInterrupt:
            print("\n[dj-agents] No running task to interrupt. Press Ctrl+D to exit.")
            continue

        reply = _run_turn_with_interrupt(agent, message)
        print(f"agent> {reply.text}")
        if reply.stop:
            return 0


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.ui == "plain":
        install_thinking_warning_filter()
        return _run_plain_session(args)

    from data_juicer_agents.tui import run_tui_session

    return run_tui_session(args)


if __name__ == "__main__":
    sys.exit(main())
