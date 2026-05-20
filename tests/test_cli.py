"""Unified CLI command delegation tests."""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import Mock, patch

from typer.testing import CliRunner

from perplexity_webui_scraper.cli.__main__ import cli


runner = CliRunner()
TEST_HOST = "127.0.0.1"


def _stub_module(name: str, attr: str) -> tuple[dict[str, ModuleType], Mock]:
    mock = Mock()
    module = ModuleType(name)
    setattr(module, attr, mock)
    return {name: module}, mock


def test_root_help_lists_subcommands() -> None:
    result = runner.invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "api" in result.output
    assert "mcp" in result.output
    assert "token" in result.output


def test_api_subcommand_delegates_with_options() -> None:
    modules, run_api = _stub_module("perplexity_webui_scraper.api.launcher", "main")

    with patch.dict(sys.modules, modules):
        result = runner.invoke(
            cli,
            [
                "api",
                "--host",
                TEST_HOST,
                "--port",
                "8080",
                "--reload",
                "--log-level",
                "debug",
            ],
        )

    assert result.exit_code == 0
    run_api.assert_called_once_with(host=TEST_HOST, port=8080, reload=True, log_level="debug")


def test_mcp_subcommand_delegates() -> None:
    modules, run_mcp = _stub_module("perplexity_webui_scraper.mcp.server", "main")

    with patch.dict(sys.modules, modules):
        result = runner.invoke(cli, ["mcp"])

    assert result.exit_code == 0
    run_mcp.assert_called_once_with()


def test_token_subcommand_delegates_with_email() -> None:
    modules, run_token = _stub_module("perplexity_webui_scraper.cli.commands.get_session_token", "run")

    with patch.dict(sys.modules, modules):
        result = runner.invoke(cli, ["token", "user@example.com"])

    assert result.exit_code == 0
    run_token.assert_called_once_with("user@example.com")
