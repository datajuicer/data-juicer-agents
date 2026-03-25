# -*- coding: utf-8 -*-

from importlib.metadata import version as distribution_version

import pytest

import data_juicer_agents
from data_juicer_agents.cli import main


def test_package_exports_distribution_version():
    assert data_juicer_agents.__version__ == distribution_version("data-juicer-agents")


def test_djx_version_reports_installed_package_version(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])

    assert exc_info.value.code == 0
    assert (
        capsys.readouterr().out.strip()
        == f"djx {distribution_version('data-juicer-agents')}"
    )
