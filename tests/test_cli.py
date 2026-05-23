"""Unified CLI command delegation tests."""

from __future__ import annotations

from sys import modules as sys_modules
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
    assert "chat" in result.output


def test_api_subcommand_delegates_with_options() -> None:
    modules, run_api = _stub_module("perplexity_webui_scraper.api.launcher", "main")

    with patch.dict(sys_modules, modules):
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

    with patch.dict(sys_modules, modules):
        result = runner.invoke(cli, ["mcp"])

    assert result.exit_code == 0
    run_mcp.assert_called_once_with()


def test_token_subcommand_delegates_with_email() -> None:
    modules, run_token = _stub_module("perplexity_webui_scraper.cli.commands.get_session_token", "run")

    with patch.dict(sys_modules, modules):
        result = runner.invoke(cli, ["token", "user@example.com"])

    assert result.exit_code == 0
    run_token.assert_called_once_with("user@example.com")


def test_chat_subcommand_delegates_with_defaults() -> None:
    modules, run_chat = _stub_module("perplexity_webui_scraper.cli.commands.chat", "run")

    with patch.dict(sys_modules, modules):
        result = runner.invoke(cli, ["chat", "What is Python?"])

    assert result.exit_code == 0
    run_chat.assert_called_once_with(
        query="What is Python?",
        model=None,
        search_focus="web",
        source_focus="web",
        time_range="all",
        citation_mode="clean",
        language="en-US",
        files=None,
        timezone=None,
        latitude=None,
        longitude=None,
        space_uuid=None,
        save=False,
        copy=False,
        raw=False,
        token=None,
    )


def test_chat_subcommand_delegates_with_all_options() -> None:
    modules, run_chat = _stub_module("perplexity_webui_scraper.cli.commands.chat", "run")

    with patch.dict(sys_modules, modules):
        result = runner.invoke(
            cli,
            [
                "chat",
                "Explain AI",
                "perplexity/sonar-2",
                "-sf",
                "writing",
                "-SF",
                "academic",
                "-tr",
                "week",
                "-cm",
                "markdown",
                "-l",
                "pt-BR",
                "--copy",
                "--raw",
                "-t",
                "my-token",
            ],
        )

    assert result.exit_code == 0
    run_chat.assert_called_once_with(
        query="Explain AI",
        model="perplexity/sonar-2",
        search_focus="writing",
        source_focus="academic",
        time_range="week",
        citation_mode="markdown",
        language="pt-BR",
        files=None,
        timezone=None,
        latitude=None,
        longitude=None,
        space_uuid=None,
        save=False,
        copy=True,
        raw=True,
        token="my-token",
    )


def test_ask_setup_subcommand_delegates() -> None:
    modules, run_setup = _stub_module("perplexity_webui_scraper.cli.commands.chat", "setup")

    with patch.dict(sys_modules, modules):
        result = runner.invoke(cli, ["chat", "setup"])

    assert result.exit_code == 0
    run_setup.assert_called_once_with()
