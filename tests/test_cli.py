"""Unified CLI command delegation tests."""

from __future__ import annotations

from sys import modules as sys_modules
from types import ModuleType
from typing import TYPE_CHECKING, Any
from unittest.mock import Mock, patch

from pytest import raises
from typer import Exit
from typer.testing import CliRunner

from perplexity_webui_scraper import ResponseParsingError
from perplexity_webui_scraper.cli.__main__ import cli
from perplexity_webui_scraper.cli.commands.chat import run as run_chat


if TYPE_CHECKING:
    from collections.abc import Iterator
    from typing import Self


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
        allow_risky_model=False,
        custom_model_mode="copilot",
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
                "--allow-risky-model",
                "--custom-model-mode",
                "search",
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
        allow_risky_model=True,
        custom_model_mode="search",
        token="my-token",
    )


def test_ask_setup_subcommand_delegates() -> None:
    modules, run_setup = _stub_module("perplexity_webui_scraper.cli.commands.chat", "setup")

    with patch.dict(sys_modules, modules):
        result = runner.invoke(cli, ["chat", "setup"])

    assert result.exit_code == 0
    run_setup.assert_called_once_with()


def test_chat_rejects_partial_coordinates() -> None:
    with raises(Exit) as exc_info:
        run_chat(
            query="Hello",
            model="perplexity/best",
            search_focus="web",
            source_focus="web",
            time_range="all",
            citation_mode="clean",
            language="en-US",
            files=None,
            timezone=None,
            latitude=1.0,
            longitude=None,
            space_uuid=None,
            save=False,
            copy=False,
            raw=False,
            token="test-token",
        )

    assert exc_info.value.exit_code == 1


def test_chat_reports_invalid_custom_identifier() -> None:
    with (
        patch("perplexity_webui_scraper.cli.commands.chat.Console") as console_type,
        raises(Exit) as exc_info,
    ):
        run_chat(
            query="Hello",
            model="custom:",
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
            allow_risky_model=True,
            token="test-token",
        )

    assert exc_info.value.exit_code == 1
    message = console_type.return_value.print.call_args.args[0]
    assert "Invalid custom model" in message
    assert "Custom model identifiers must contain" in message
    assert "Unknown model" not in message


def test_chat_retries_best_as_writing_on_processing_failure() -> None:
    class _Conversation:
        def __init__(self, fail: bool) -> None:
            self.fail = fail
            self.answer: str | None = None

        def ask(self, query: str, files: list[Any] | None = None, stream: bool = False) -> Iterator[object]:
            if self.fail:
                raise ResponseParsingError("Query processing failed: Error in processing query.")

            self.answer = "ok"
            return iter(())

    class _Client:
        def __init__(self, session_token: str) -> None:
            self.configs: list[Any] = []
            self.calls = 0

        def __enter__(self) -> Self:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def create_conversation(self, config: Any) -> _Conversation:
            self.configs.append(config)
            self.calls += 1
            return _Conversation(fail=self.calls == 1)

    fake_client = _Client("token")

    with patch("perplexity_webui_scraper.cli.commands.chat.Perplexity", return_value=fake_client):
        run_chat(
            query="oi",
            model="perplexity/best",
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
            raw=True,
            allow_risky_model=True,
            token="test-token",
        )

    assert len(fake_client.configs) == 2
    assert fake_client.configs[0].search_focus == "web"
    assert fake_client.configs[1].search_focus == "writing"


def test_chat_formats_response_parsing_error_without_traceback() -> None:
    class _Conversation:
        answer = None

        def ask(self, query: str, files: list[Any] | None = None, stream: bool = False) -> Iterator[object]:
            raise ResponseParsingError("Query processing failed: Error in processing query.")

    class _Client:
        def __init__(self, session_token: str) -> None:
            return None

        def __enter__(self) -> Self:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def create_conversation(self, config: Any) -> _Conversation:
            return _Conversation()

    with patch("perplexity_webui_scraper.cli.commands.chat.Perplexity", _Client), raises(Exit) as exc_info:
        run_chat(
            query="oi",
            model="perplexity/sonar-2",
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
            raw=True,
            token="test-token",
        )

    assert exc_info.value.exit_code == 1
