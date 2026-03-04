# -*- coding: utf-8 -*-

from studio.api.cli import build_parser


def test_web_api_cli_parser():
    parser = build_parser()
    args = parser.parse_args(["--host", "0.0.0.0", "--port", "8899", "--reload"])

    assert args.host == "0.0.0.0"
    assert args.port == 8899
    assert args.reload is True
