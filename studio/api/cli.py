# -*- coding: utf-8 -*-
"""CLI entrypoint for DJX UI local API server."""

from __future__ import annotations

import argparse

import uvicorn


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="djx-ui-api",
        description="Run local API server for DJX frontend",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    parser.add_argument("--port", type=int, default=8787, help="Port to bind")
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    run_kwargs = {
        "host": args.host,
        "port": args.port,
        "reload": bool(args.reload),
    }
    if args.reload:
        # Avoid reloading on runtime artifacts (.djx/data logs), which would
        # drop in-memory sessions and cause frontend polling 404s.
        run_kwargs.update(
            reload_dirs=["studio", "data_juicer_agents"],
            reload_excludes=[
                ".djx/*",
                "data/log/*",
                "data/*.jsonl",
            ],
        )
    uvicorn.run(
        "studio.api.main:app",
        **run_kwargs,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
