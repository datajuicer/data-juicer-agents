# -*- coding: utf-8 -*-
"""AgentScope Studio session runner for dj-agents."""

from __future__ import annotations

import argparse
import asyncio
import os
from datetime import datetime

from data_juicer_agents.capabilities.session.orchestrator import DJSessionAgent

from .bridge_agent import DJStudioBridgeAgent


def _resolve_studio_url(args: argparse.Namespace) -> str:
    value = str(getattr(args, "studio_url", "") or os.environ.get("DJA_STUDIO_URL") or "").strip()
    return value or "http://localhost:3000"


async def _run_loop(args: argparse.Namespace) -> int:
    import agentscope
    from agentscope.agent import UserAgent

    studio_url = _resolve_studio_url(args)
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
    user = UserAgent("user")
    assistant = DJStudioBridgeAgent(session_agent=session_agent, name="dj-agents")
    session_agent.set_stream_callback(assistant.forward_stream_chunk)

    while True:
        user_msg = await user()
        assistant_msg = await assistant(user_msg)
        metadata = getattr(assistant_msg, "metadata", None) or {}
        if metadata.get("dj_stop"):
            return 0


def run_as_studio_session(args: argparse.Namespace) -> int:
    try:
        return asyncio.run(_run_loop(args))
    except Exception as exc:
        print(f"Failed to initialize AgentScope Studio session: {exc}")
        return 2
