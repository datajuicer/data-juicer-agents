# -*- coding: utf-8 -*-
"""Interactive session entrypoint for `dj-agents`."""

from __future__ import annotations

import argparse
import contextlib
import os
import select
import sys
import threading
import time

try:
    import termios
    import tty
except Exception:  # pragma: no cover - non-posix runtime
    termios = None
    tty = None

from data_juicer_agents.capabilities.session.orchestrator import DJSessionAgent
from data_juicer_agents.agentscope_logging import install_thinking_warning_filter


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


@contextlib.contextmanager
def _cbreak_stdin():
    if os.name != "posix" or termios is None or tty is None or not sys.stdin.isatty():
        yield False
        return
    fd = sys.stdin.fileno()
    attrs = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        yield True
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, attrs)


def _poll_esc(timeout_sec: float = 0.1) -> bool:
    if os.name != "posix" or termios is None or tty is None or not sys.stdin.isatty():
        time.sleep(timeout_sec)
        return False
    ready, _, _ = select.select([sys.stdin], [], [], timeout_sec)
    if not ready:
        return False
    try:
        key = sys.stdin.read(1)
    except Exception:
        return False
    return key == "\x1b"


def _run_turn_with_interrupt(agent: DJSessionAgent, message: str):
    if os.name != "posix" or termios is None or tty is None or not sys.stdin.isatty():
        return agent.handle_message(message)

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

    with _cbreak_stdin():
        while not done.wait(0.05):
            if _poll_esc(timeout_sec=0.05):
                if not interrupt_sent and agent.request_interrupt():
                    interrupt_sent = True
                    print("\n[dj-agents] Interrupt requested (ESC).")

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
    print("DJ session started. Describe your task in natural language. Type `help` or `exit`.")
    print("Press ESC to interrupt the current turn without stopping the session.")

    while True:
        try:
            message = input("you> ")
        except (EOFError, KeyboardInterrupt):
            print("\nSession ended.")
            return 0

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
