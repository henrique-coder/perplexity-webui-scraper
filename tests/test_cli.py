"""Tests for the unified Typer CLI and optional features."""

from __future__ import annotations

from pathlib import Path
from subprocess import run
from tomllib import loads
from unittest.mock import Mock, patch

from pytest import raises
from typer.testing import CliRunner

from perplexity_webui_scraper.cli.__main__ import _COMMANDS, _load_command, api, cli, token


runner = CliRunner()


def test_root_help_lists_commands_without_importing_feature_modules() -> None:
    with patch("perplexity_webui_scraper.cli.__main__.import_module") as import_module:
        result = runner.invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert all(name in result.output for name in _COMMANDS)
    import_module.assert_not_called()


def test_help_aliases_work_for_root_and_all_subcommands() -> None:
    for command in ([], ["token"], ["api"], ["mcp"]):
        for option in ("-h", "--help"):
            result = runner.invoke(cli, [*command, option])

            assert result.exit_code == 0, (command, option, result.output)
            assert "Usage:" in result.output


def test_public_extra_order_matches_all_extra() -> None:
    project = loads(Path("pyproject.toml").read_text())
    extras = project["project"]["optional-dependencies"]
    assert list(extras) == ["all", "token", "api", "mcp"]
    assert extras["all"] == ["perplexity-webui-scraper[token,api,mcp]"]


def test_base_only_install_runs_root_help_without_feature_dependencies() -> None:
    help_result = run(_base_only_command("--help"), capture_output=True, check=False, text=True)
    assert help_result.returncode == 0, help_result.stderr
    assert "token" in help_result.stdout
    assert "api" in help_result.stdout
    assert "mcp" in help_result.stdout
    dependency_result = run(
        [
            "uv",
            "run",
            "--isolated",
            "--no-project",
            "--with",
            f"perplexity-webui-scraper @ file://{Path.cwd()}",
            "--",
            "python",
            "-c",
            (
                "from importlib.util import find_spec; "
                "print(find_spec('fastapi'), find_spec('pyperclip'), find_spec('fastmcp'))"
            ),
        ],
        capture_output=True,
        check=False,
        text=True,
    )
    assert dependency_result.returncode == 0, dependency_result.stderr
    assert "None None None" in dependency_result.stdout


def test_base_only_feature_command_explains_extra() -> None:
    result = run(_base_only_command("token"), capture_output=True, check=False, text=True)
    assert result.returncode == 1
    assert "perplexity-webui-scraper[token]" in result.stderr


def _base_only_command(*arguments: str) -> list[str]:
    return [
        "uv",
        "run",
        "--isolated",
        "--no-project",
        "--with",
        f"perplexity-webui-scraper @ file://{Path.cwd()}",
        "--",
        "perplexity-webui-scraper",
        *arguments,
    ]


def test_unavailable_extra_reports_install_command() -> None:
    with (
        patch(
            "perplexity_webui_scraper.cli.__main__.import_module",
            side_effect=ModuleNotFoundError("missing fastapi", name="fastapi"),
        ),
        raises(SystemExit, match=r"perplexity-webui-scraper\[api\]"),
    ):
        _load_command("api")


def test_missing_token_extra_is_reported_as_clean_cli_error() -> None:
    with patch(
        "perplexity_webui_scraper.cli.__main__.import_module",
        side_effect=ModuleNotFoundError("missing pyperclip", name="pyperclip"),
    ):
        result = runner.invoke(cli, ["token"])

    assert result.exit_code == 1
    assert "perplexity-webui-scraper[token]" in result.output


def test_token_dispatch_uses_token_extra_app() -> None:
    token_app = Mock()
    with (
        patch("perplexity_webui_scraper.cli.__main__._load_command", return_value=(token_app, "token")),
        patch("perplexity_webui_scraper.cli.__main__.echo"),
    ):
        token("user@example.com")

    token_app.assert_called_once_with("user@example.com")


def test_token_command_dispatches_email_to_authentication_function() -> None:
    token_run = Mock()
    token_module = Mock(run=token_run)
    with patch("perplexity_webui_scraper.cli.__main__.import_module", return_value=token_module):
        result = runner.invoke(cli, ["token", "--email", "user@example.com"])

    assert result.exit_code == 0
    token_run.assert_called_once_with("user@example.com")


def test_token_command_accepts_short_email_option() -> None:
    token_run = Mock()
    token_module = Mock(run=token_run)
    with patch("perplexity_webui_scraper.cli.__main__.import_module", return_value=token_module):
        result = runner.invoke(cli, ["token", "-e", "user@example.com"])

    assert result.exit_code == 0
    token_run.assert_called_once_with("user@example.com")


def test_api_dispatch_passes_cli_options_to_launcher() -> None:
    api_launcher = Mock()
    with patch("perplexity_webui_scraper.cli.__main__._load_command", return_value=(api_launcher, "api")):
        api("0.0.0.0", 8080, True, "debug", "token", "gateway")

    api_launcher.assert_called_once_with(
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="debug",
        default_session_token="token",
        gateway_api_key="gateway",
    )


def test_mcp_command_invokes_mcp_server() -> None:
    mcp_command = Mock()
    with patch("perplexity_webui_scraper.cli.__main__._load_command", return_value=(mcp_command, "mcp")):
        result = runner.invoke(cli, ["mcp"])

    assert result.exit_code == 0
    mcp_command.assert_called_once_with()
