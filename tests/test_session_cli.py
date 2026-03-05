# -*- coding: utf-8 -*-

import pytest

from data_juicer_agents.session_cli import build_parser


def test_session_cli_parser_accepts_verbose_flag():
    parser = build_parser()
    args = parser.parse_args(
        ["--verbose", "--dataset", "a.jsonl", "--export", "b.jsonl", "--ui", "tui"]
    )
    assert args.verbose is True
    assert args.dataset == "a.jsonl"
    assert args.export == "b.jsonl"
    assert args.ui == "tui"


def test_session_cli_parser_rejects_unknown_flag():
    parser = build_parser()
    with pytest.raises(SystemExit):
        _ = parser.parse_args(["--deprecated-flag"])


def test_session_cli_parser_default_ui_is_tui():
    parser = build_parser()
    args = parser.parse_args([])
    assert args.ui == "tui"
