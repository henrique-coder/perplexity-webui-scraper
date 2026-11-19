"""Tests for the unified Typer CLI and optional features."""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from subprocess import run
from typing import Any
from unittest.mock import Mock, patch

from pytest import raises
from rich.console import Console
from typer.testing import CliRunner

from perplexity_webui_scraper._internal.constants import SESSION_COOKIE_PREFIX, SESSION_TOKEN_JWE_HEADER
from perplexity_webui_scraper.auth.session_token import pack_session_token
from perplexity_webui_scraper.cli.__main__ import _COMMANDS, _load_command, api, cli
from perplexity_webui_scraper.cli.commands.token import _prompt_otp, _prompt_totp
from perplexity_webui_scraper.cli.commands.token import run_command as run_token_command


runner = CliRunner()
_TOKEN_UUID = "123e4567-e89b-42d3-a456-426614174000"
_TOKEN_JWE = f"{SESSION_TOKEN_JWE_HEADER}..EBESExQVFhcYGRob.AQIDBAUGBw.MDEyMzQ1Njc4OTo7PD0-Pw"
_RAW_TOKEN = f"{SESSION_COOKIE_PREFIX}{_TOKEN_UUID}={_TOKEN_JWE}"
_COMPACT_TOKEN = pack_session_token(_RAW_TOKEN)


def test_root_help_lists_commands_without_importing_feature_modules() -> None:
    with patch("perplexity_webui_scraper.cli.__main__.import_module") as import_module:
        result = runner.invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert all(name in result.output for name in _COMMANDS)
    import_module.assert_not_called()


def test_help_aliases_work_for_root_and_all_subcommands() -> None:
    for command in ([], ["token"], ["token", "convert"], ["token", "deconvert"], ["api"], ["mcp"]):
        for option in ("-h", "--help"):
            result = runner.invoke(cli, [*command, option])

            assert result.exit_code == 0, (command, option, result.output)
            assert "Usage:" in result.output


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


def test_token_email_options_dispatch_to_authentication_command() -> None:
    for option in ("-e", "--email"):
        run_token = Mock()
        with patch("perplexity_webui_scraper.cli.__main__.import_module", return_value=Mock(run_command=run_token)):
            result = runner.invoke(cli, ["token", option, "user@example.test"])

        assert result.exit_code == 0
        run_token.assert_called_once_with("user@example.test")


def test_token_convert_and_deconvert_use_masked_input_without_authentication(monkeypatch: Any) -> None:
    monkeypatch.setattr("perplexity_webui_scraper.cli.commands.token.authenticate", Mock(side_effect=AssertionError))
    prompt = Mock(side_effect=[_RAW_TOKEN, _COMPACT_TOKEN, _COMPACT_TOKEN])
    confirm = Mock(return_value=False)
    copy_credential = Mock()
    monkeypatch.setattr("perplexity_webui_scraper.cli.commands.token.Prompt.ask", prompt)
    monkeypatch.setattr("perplexity_webui_scraper.cli.commands.token.Confirm.ask", confirm)
    monkeypatch.setattr("perplexity_webui_scraper.cli.commands.token.copy", copy_credential)

    raw_conversion = runner.invoke(cli, ["token", "convert"])
    compact_validation = runner.invoke(cli, ["token", "convert"])
    raw_restoration = runner.invoke(cli, ["token", "deconvert"])

    assert raw_conversion.exit_code == 0, raw_conversion.output
    assert _COMPACT_TOKEN in raw_conversion.output
    assert compact_validation.exit_code == 0, compact_validation.output
    assert _COMPACT_TOKEN in compact_validation.output
    assert raw_restoration.exit_code == 0, raw_restoration.output
    assert _RAW_TOKEN in raw_restoration.output
    assert prompt.call_count == 3
    assert all(prompt_call.kwargs["password"] is True for prompt_call in prompt.call_args_list)
    assert confirm.call_count == 3
    copy_credential.assert_not_called()


def test_token_conversion_copies_only_after_user_confirmation(monkeypatch: Any) -> None:
    credential = _RAW_TOKEN
    copy_credential = Mock()
    monkeypatch.setattr("perplexity_webui_scraper.cli.commands.token.Prompt.ask", Mock(return_value=credential))
    monkeypatch.setattr("perplexity_webui_scraper.cli.commands.token.Confirm.ask", Mock(return_value=True))
    monkeypatch.setattr("perplexity_webui_scraper.cli.commands.token.copy", copy_credential)
    monkeypatch.setattr("perplexity_webui_scraper.cli.commands.token.sys_stdin_is_tty", lambda: False)

    result = runner.invoke(cli, ["token", "convert"])

    assert result.exit_code == 0, result.output
    copy_credential.assert_called_once()


def test_token_transform_rejects_positional_credentials_without_echoing_them() -> None:
    for operation, credential in (
        ("convert", _RAW_TOKEN),
        ("convert", _COMPACT_TOKEN),
        ("deconvert", _COMPACT_TOKEN),
    ):
        result = runner.invoke(cli, ["token", operation, credential], input="n\n")

        assert result.exit_code == 2
        assert _RAW_TOKEN not in result.output
        assert _COMPACT_TOKEN not in result.output


def test_bare_token_command_invokes_interactive_auth(monkeypatch: Any) -> None:
    output = StringIO()
    console = Console(file=output, color_system="standard", force_terminal=False, soft_wrap=True)
    prompt_email = Mock(return_value="person@example.test")
    authenticate_mock = Mock(return_value=_COMPACT_TOKEN)
    monkeypatch.setattr("perplexity_webui_scraper.cli.commands.token.console", console)
    monkeypatch.setattr("perplexity_webui_scraper.cli.commands.token.sys_stdin_is_tty", lambda: False)
    monkeypatch.setattr("perplexity_webui_scraper.cli.commands.token._prompt_email", prompt_email)
    monkeypatch.setattr("perplexity_webui_scraper.cli.commands.token.authenticate", authenticate_mock)
    monkeypatch.setattr("perplexity_webui_scraper.cli.commands.token.Confirm.ask", Mock(return_value=False))

    result = runner.invoke(cli, ["token"])

    assert result.exit_code == 0, result.output
    prompt_email.assert_called_once_with(None)
    authenticate_mock.assert_called_once()


def test_token_deconvert_accepts_quoted_compact_token(monkeypatch: Any) -> None:
    monkeypatch.setattr(
        "perplexity_webui_scraper.cli.commands.token.Prompt.ask",
        Mock(return_value=f'"{_COMPACT_TOKEN}"'),
    )
    monkeypatch.setattr("perplexity_webui_scraper.cli.commands.token.Confirm.ask", Mock(return_value=False))

    result = runner.invoke(cli, ["token", "deconvert"])

    assert result.exit_code == 0, result.output
    assert _RAW_TOKEN in result.output


def test_token_convert_help_and_shortcut_work_without_loading_authentication(monkeypatch: Any) -> None:
    monkeypatch.setattr("perplexity_webui_scraper.cli.__main__._load_command", Mock(side_effect=AssertionError))
    result = runner.invoke(cli, ["token", "convert", "--help"])

    assert result.exit_code == 0, result.output
    assert "Restore a compact wsk_ token" not in result.output
    assert "Usage:" in result.output

    conversion = Mock()
    with (
        patch("perplexity_webui_scraper.cli.__main__._load_token_transform", return_value=conversion),
    ):
        shortcut = runner.invoke(cli, ["token", "-c"])

    assert shortcut.exit_code == 0, shortcut.output
    conversion.assert_called_once_with(None, deconvert=False, interactive=True)

    validation = Mock()
    with patch("perplexity_webui_scraper.cli.__main__._load_token_transform", return_value=validation):
        explicit_conversion = runner.invoke(cli, ["token", "--convert"])

    assert explicit_conversion.exit_code == 0, explicit_conversion.output
    validation.assert_called_once_with(None, deconvert=False, interactive=True)


def test_token_otp_prompt_repeats_locally_before_returning_a_valid_code() -> None:
    email = "person@example.test"
    valid_link = (
        "https://www.perplexity.ai/api/auth/callback/email?"
        "callbackUrl=https%3A%2F%2Fwww.perplexity.ai%2F%3Flogin-source%3DfloatingSignup"
        "&email=person%40example.test&token=950515"
    )
    responses = iter(["saas", "12345", "1234567", "95a515", valid_link, "950515"])
    output = StringIO()
    console = Console(file=output, color_system="standard", force_terminal=True, soft_wrap=True)

    with (
        patch("perplexity_webui_scraper.cli.commands.token.console", console),
        patch(
            "perplexity_webui_scraper.cli.commands.token.Prompt.ask",
            side_effect=lambda *_args, **_kwargs: next(responses),
        ) as prompt,
    ):
        assert _prompt_otp(email) == valid_link
        assert _prompt_otp(email) == "950515"

    assert prompt.call_count == 6
    assert all(prompt_call.kwargs.get("password") is True for prompt_call in prompt.call_args_list)
    assert output.getvalue().count("Invalid format.") == 4


def test_token_otp_and_totp_prompts_do_not_echo_secrets_via_getpass() -> None:
    email = "person@example.test"
    synthetic_link = (
        "https://www.perplexity.ai/api/auth/callback/email?"
        "callbackUrl=https%3A%2F%2Fwww.perplexity.ai%2F%3Flogin-source%3DfloatingSignup"
        "&email=person%40example.test&token=950515"
    )
    synthetic_totp = "654321"
    output = StringIO()
    console = Console(file=output, color_system="standard", force_terminal=True, soft_wrap=True)
    secrets = iter([synthetic_link, synthetic_totp])

    with (
        patch("perplexity_webui_scraper.cli.commands.token.console", console),
        patch("getpass.getpass", side_effect=lambda *_args, **_kwargs: next(secrets)) as getpass_mock,
    ):
        assert _prompt_otp(email) == synthetic_link
        assert _prompt_totp() == synthetic_totp

    assert getpass_mock.call_count == 2
    rendered = output.getvalue()
    assert synthetic_link not in rendered
    assert "950515" not in rendered
    assert synthetic_totp not in rendered


def test_token_completion_messages_request_clipboard_consent(monkeypatch: Any) -> None:
    output = StringIO()
    console = Console(
        file=output,
        color_system="standard",
        force_terminal=True,
        soft_wrap=True,
    )
    credential = "wsk_synthetic_credential"

    with (
        patch("perplexity_webui_scraper.cli.commands.token.console", console),
        patch("perplexity_webui_scraper.cli.commands.token.authenticate", return_value=credential),
        patch("perplexity_webui_scraper.cli.commands.token.Confirm.ask", return_value=True),
        patch("perplexity_webui_scraper.cli.commands.token.copy"),
        patch("perplexity_webui_scraper.cli.commands.token._prompt_email", return_value="person@example.test"),
    ):
        monkeypatch.setattr("perplexity_webui_scraper.cli.commands.token.sys_stdin_is_tty", lambda: True)
        console_input = Mock()
        monkeypatch.setattr("perplexity_webui_scraper.cli.commands.token.console.input", console_input)
        monkeypatch.setattr("perplexity_webui_scraper.cli.commands.token.run_command", run_token_command)
        run_token_command("person@example.test", standalone_mode=False)

    rendered = output.getvalue()
    assert "Credential copied to clipboard." in rendered
    assert "Keep this credential private; it grants access to your account." in rendered
    assert "Press ENTER to clear the screen and exit..." in console_input.call_args.args[0]


def test_token_authentication_uses_full_screen_until_enter(monkeypatch: Any) -> None:
    output = StringIO()
    screen_console = Console(
        file=output,
        color_system="standard",
        force_terminal=True,
        soft_wrap=True,
        _environ={"TERM": "xterm"},
    )
    input_prompt = Mock()
    monkeypatch.setattr("perplexity_webui_scraper.cli.commands.token.console", screen_console)
    monkeypatch.setattr("perplexity_webui_scraper.cli.commands.token.authenticate", Mock(return_value=_COMPACT_TOKEN))
    monkeypatch.setattr("perplexity_webui_scraper.cli.commands.token.Confirm.ask", Mock(return_value=False))
    monkeypatch.setattr(
        "perplexity_webui_scraper.cli.commands.token._prompt_email",
        Mock(return_value="person@example.test"),
    )
    monkeypatch.setattr("perplexity_webui_scraper.cli.commands.token.sys_stdin_is_tty", lambda: True)
    monkeypatch.setattr(screen_console, "input", input_prompt)

    result = runner.invoke(cli, ["token", "--email", "person@example.test"])

    assert result.exit_code == 0, result.output
    assert output.getvalue().count("\x1b[?1049h") == 1
    assert output.getvalue().count("\x1b[?1049l") == 1
    assert input_prompt.call_count == 1


def test_api_dispatch_passes_cli_options_to_launcher() -> None:
    api_launcher = Mock()
    with patch("perplexity_webui_scraper.cli.__main__._load_command", return_value=(api_launcher, "api")):
        api("127.0.0.1", 8080, True, "debug", "token", "gateway")

    api_launcher.assert_called_once_with(
        host="127.0.0.1",
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
