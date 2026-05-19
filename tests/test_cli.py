"""Unified CLI command delegation tests."""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from perplexity_webui_scraper.cli.__main__ import cli


runner = CliRunner()


def test_root_help_lists_subcommands() -> None:
    result = runner.invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "api" in result.output
    assert "mcp" in result.output
    assert "token" in result.output


def test_api_subcommand_delegates_with_options() -> None:
    with patch("perplexity_webui_scraper.api.launcher.main") as run_api:
        result = runner.invoke(
            cli,
            [
                "api",
                "--host",
                "0.0.0.0",
                "--port",
                "8080",
                "--reload",
                "--log-level",
                "debug",
            ],
        )

    assert result.exit_code == 0
    run_api.assert_called_once_with(host="0.0.0.0", port=8080, reload=True, log_level="debug")


def test_mcp_subcommand_delegates() -> None:
    with patch("perplexity_webui_scraper.mcp.server.main") as run_mcp:
        result = runner.invoke(cli, ["mcp"])

    assert result.exit_code == 0
    run_mcp.assert_called_once_with()


def test_token_subcommand_delegates_with_email() -> None:
    with patch("perplexity_webui_scraper.cli.commands.get_session_token.run") as run_token:
        result = runner.invoke(cli, ["token", "user@example.com"])

    assert result.exit_code == 0
    run_token.assert_called_once_with("user@example.com")
