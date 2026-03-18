# -*- coding: utf-8 -*-
"""Interactive session entrypoint for `dj-agents`."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import threading
from datetime import datetime

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
        choices=["plain", "tui", "as_studio"],
        default="tui",
        help="Session UI mode (default: tui)",
    )
    parser.add_argument(
        "--studio-url",
        default=os.environ.get("DJA_STUDIO_URL", "http://localhost:3000"),
        help="AgentScope Studio URL for --ui as_studio (default: http://localhost:3000)",
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


async def _run_as_studio_session_async(args: argparse.Namespace) -> int:
    import agentscope
    from agentscope.agent import AgentBase, UserAgent
    from agentscope.message import Msg

    studio_url = str(args.studio_url).strip()
    run_id = f"dj_agents_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    agentscope.init(
        project="data-juicer-agents",
        name="dj-agents",
        run_id=run_id,
        studio_url=studio_url,
    )

    session_agent = DJSessionAgent(
        use_llm_router=True,
        dataset_path=args.dataset,
        export_path=args.export,
        verbose=args.verbose,
        enable_streaming=True,
    )

    class _StudioShell(AgentBase):
        def __init__(self, agent: DJSessionAgent, name: str = "dj-agents") -> None:
            super().__init__()
            self._session_agent = agent
            self.name = name

        async def _emit_chunk(self, chunk: Msg, last: bool) -> None:
            await self.print(chunk, last=last)

        async def reply(self, msg=None, *args, **kwargs):  # noqa: ANN001
            try:
                turn = await self._session_agent.handle_as_studio_turn_async(msg, self._emit_chunk)
            except Exception as exc:  # pragma: no cover - defensive runtime guard
                out = Msg(
                    name=self.name,
                    role="assistant",
                    content=(
                        "AgentScope Studio runtime failed while handling the request.\n"
                        f"error: {exc}"
                    ),
                    metadata={"dj_error": True},
                )
                await self.print(out)
                return out

            if turn.should_emit_final:
                await self.print(turn.msg)
            return turn.msg

    user = UserAgent("user")
    assistant = _StudioShell(session_agent)

    while True:
        user_msg = await user()
        assistant_msg = await assistant(user_msg)
        metadata = getattr(assistant_msg, "metadata", None) or {}
        if metadata.get("dj_stop"):
            return 0


def _run_as_studio_session(args: argparse.Namespace) -> int:
    try:
        return asyncio.run(_run_as_studio_session_async(args))
    except Exception as exc:
        print(f"Failed to initialize AgentScope Studio session: {exc}")
        return 2


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.ui == "plain":
        install_thinking_warning_filter()
        return _run_plain_session(args)
    if args.ui == "as_studio":
        install_thinking_warning_filter()
        return _run_as_studio_session(args)

    from data_juicer_agents.tui import run_tui_session

    return run_tui_session(args)


if __name__ == "__main__":
    sys.exit(main())
