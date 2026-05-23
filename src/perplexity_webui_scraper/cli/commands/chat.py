"""chat CLI command — query Perplexity AI directly from the terminal.

Streams tokens in real-time using Rich Live panels. Reads the session
token from encrypted local storage (see ``setup`` subcommand) or from
an explicit ``--token`` override.
"""

from __future__ import annotations

from contextlib import suppress
from queue import Empty, Queue
from sys import stdout
from threading import Thread
from time import time
from typing import TYPE_CHECKING, Any, cast

from pyperclip import PyperclipException
from pyperclip import copy as clipboard_copy
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from typer import Exit

from perplexity_webui_scraper import ConversationConfig, Coordinates, Perplexity
from perplexity_webui_scraper.cli.commands._token_store import (
    get_config_dir,
    get_default_model,
    is_configured,
    load_token,
    save_token,
    set_default_model,
)
from perplexity_webui_scraper.models.registry import MODELS


if TYPE_CHECKING:
    from perplexity_webui_scraper._internal.types import CitationMode, SearchFocus, SourceFocus, TimeRange


def _resolve_token(explicit_token: str | None) -> str | None:
    """Return the session token to use, preferring an explicit override."""
    if explicit_token:
        return explicit_token

    return load_token()


def run(
    query: str | None,
    model: str | None,
    search_focus: str,
    source_focus: str,
    time_range: str,
    citation_mode: str,
    language: str,
    files: list[str] | None,
    timezone: str | None,
    latitude: float | None,
    longitude: float | None,
    space_uuid: str | None,
    save: bool,
    copy: bool,
    raw: bool,
    token: str | None,
) -> None:
    """Execute a single query against Perplexity AI with streaming output."""
    console = Console()

    session_token = _resolve_token(token)
    if not session_token:
        console.print("[red]⛔ No session token configured.[/red]")
        console.print("Run [bold cyan]perplexity-webui-scraper chat setup[/bold cyan] to configure your token.")
        raise Exit(code=1)

    resolved_model = model or get_default_model()

    try:
        MODELS.resolve(resolved_model)
    except ValueError:
        console.print(f"[red]⛔ Unknown model: {resolved_model!r}[/red]")
        console.print("Run [bold cyan]perplexity-webui-scraper chat setup[/bold cyan] to change your default model.")
        raise Exit(code=1)  # noqa: B904

    coords = (
        Coordinates(latitude=latitude, longitude=longitude) if latitude is not None and longitude is not None else None
    )

    config = ConversationConfig(
        model=resolved_model,
        search_focus=cast("SearchFocus", search_focus),
        source_focus=cast("SourceFocus", source_focus),
        time_range=cast("TimeRange", time_range),
        citation_mode=cast("CitationMode", citation_mode),
        language=language,
        timezone=timezone,
        coordinates=coords,
        save_to_library=save,
        space_uuid=space_uuid,
    )

    typed_files = cast("list[Any] | None", list(files) if files else None)  # FileInput accepts str
    final_answer: str | None = None

    try:
        with Perplexity(session_token=session_token) as client:
            conversation = client.create_conversation(config)

            if not raw:
                console.print()
                console.print(
                    Panel(
                        "[bold cyan]Perplexity WebUI Scraper — Chat[/bold cyan]\n"
                        f"Model: [green]{resolved_model}[/green]",
                        border_style="cyan",
                    )
                )

            current_query = query
            skip_newline = False

            while True:
                if not current_query:
                    try:
                        if not raw:
                            if not skip_newline:
                                console.print()

                            console.print("[bold cyan]❯[/bold cyan] ", end="")  # noqa: RUF001
                            stdout.write("\033[1;97m")
                            stdout.flush()

                        skip_newline = False

                        try:
                            current_query = input().strip()
                        finally:
                            if not raw:
                                stdout.write("\033[0m")
                                stdout.flush()

                        if not current_query:
                            if not raw:
                                stdout.write("\033[1A\r\033[K")
                                stdout.flush()
                                skip_newline = True
                            continue
                    except (KeyboardInterrupt, EOFError):
                        if not raw:
                            console.print()

                        break
                elif not raw:
                    console.print(
                        f"\n[bold cyan]❯[/bold cyan] "  # noqa: RUF001
                        f"[bold bright_white]{current_query}[/bold bright_white]"
                    )

                if raw:
                    for _ in conversation.ask(current_query, files=typed_files, stream=True):
                        pass

                    if conversation.answer:
                        print(conversation.answer)  # noqa: T201

                    final_answer = conversation.answer
                else:
                    console.print()

                    q: Queue[tuple[str, Any]] = Queue()

                    def fetch_chunks(
                        query_str: str, files_list: list[Any] | None, queue_obj: Queue[tuple[str, Any]]
                    ) -> None:
                        try:
                            for chunk in conversation.ask(query_str, files=files_list, stream=True):
                                queue_obj.put(("chunk", chunk))
                        except Exception as e:
                            queue_obj.put(("error", e))
                        finally:
                            queue_obj.put(("done", None))

                    Thread(target=fetch_chunks, args=(current_query, typed_files, q), daemon=True).start()

                    start_time = time()
                    first_chunk_received = False

                    with Live(
                        "[bold yellow]Thinking... (0.0s)[/bold yellow]",
                        console=console,
                        refresh_per_second=10,
                    ) as live:
                        while True:
                            try:
                                msg_type, msg_data = q.get(timeout=0.1)
                                if msg_type == "chunk":
                                    if msg_data.answer:
                                        first_chunk_received = True
                                        live.update(Markdown(msg_data.answer))
                                elif msg_type == "error":
                                    raise msg_data
                                elif msg_type == "done":
                                    break
                            except Empty:
                                if not first_chunk_received:
                                    elapsed = time() - start_time
                                    live.update(f"[bold yellow]Thinking... ({elapsed:.1f}s)[/bold yellow]")

                    final_answer = conversation.answer

                if copy and final_answer:
                    with suppress(PyperclipException):
                        clipboard_copy(final_answer)
                        if not raw:
                            console.print("\n[dim]📋 Answer copied to clipboard.[/dim]")

                current_query = None
                typed_files = None

                if raw and query:
                    break

    except Exception as exc:
        error_msg = str(exc)
        if "authentication" in error_msg.lower() or "session" in error_msg.lower() or "401" in error_msg:
            console.print("[red]⛔ Authentication failed. Your token may be invalid or expired.[/red]")
            console.print("Run [bold cyan]perplexity-webui-scraper chat setup[/bold cyan] to reconfigure.")
            raise Exit(code=1)  # noqa: B904
        raise


def setup() -> None:
    """Interactive setup wizard for the chat command."""
    console = Console()

    console.print()
    console.print(
        Panel(
            "[bold cyan]Perplexity WebUI Scraper — Chat Setup[/bold cyan]",
            border_style="cyan",
            subtitle=f"Config: {get_config_dir()}",
        )
    )
    console.print()

    current_token = load_token()
    if current_token:
        masked = current_token[:12] + "..." + current_token[-8:]
        console.print(f"  [green]✔ Token configured:[/green] [dim]{masked}[/dim]")

        if Confirm.ask("  Replace with a new token?", console=console, default=False):
            _prompt_and_save_token(console)
    else:
        console.print("  [yellow]⚠ No token configured yet.[/yellow]")
        _prompt_and_save_token(console)

    if not is_configured():
        console.print("[red]⛔ Setup incomplete — no token saved.[/red]")
        raise Exit(code=1)

    console.print()

    current_model = get_default_model()
    console.print(f"  [green]✔ Default model:[/green] [bold]{current_model}[/bold]")

    try:
        MODELS.resolve(current_model)
    except ValueError:
        console.print(f"  [red]⚠ Model {current_model!r} no longer exists in the registry.[/red]")
        console.print("  Please select a valid model.")
        _prompt_and_save_model(console)
    else:
        if Confirm.ask("  Change default model?", console=console, default=False):
            _prompt_and_save_model(console)

    console.print()
    console.print("[bold green]✅ Setup complete! You can now use:[/bold green]")
    console.print('  [cyan]perplexity-webui-scraper chat "Your question here"[/cyan]')
    console.print()


def _prompt_and_save_token(console: object) -> None:
    """Prompt the user for a session token and save it."""
    rich_console = console if isinstance(console, Console) else Console()
    entered_token = Prompt.ask("  Paste your session token", console=rich_console, password=True)

    if not entered_token or not entered_token.strip():
        rich_console.print("[red]  Token cannot be empty.[/red]")
        return

    save_token(entered_token.strip())
    rich_console.print("[green]  ✔ Token saved and encrypted.[/green]")


def _prompt_and_save_model(console: object) -> None:
    """Prompt the user for a default model and save it."""
    rich_console = console if isinstance(console, Console) else Console()

    table = Table(title="Available Models", border_style="cyan", show_lines=False)
    table.add_column("#", style="dim", width=4)
    table.add_column("ID", style="bold")
    table.add_column("Name")
    table.add_column("Tier", style="dim")

    models = MODELS.list_all()
    for idx, m in enumerate(models, 1):
        table.add_row(str(idx), m.id, m.name, m.min_tier)

    rich_console.print()
    rich_console.print(table)

    choice = Prompt.ask(
        "  Enter model ID or number",
        console=rich_console,
        default="perplexity/best",
    )

    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(models):
            chosen = models[idx].id
        else:
            rich_console.print("[red]  Invalid number.[/red]")
            return
    else:
        chosen = choice

    try:
        MODELS.resolve(chosen)
    except ValueError:
        rich_console.print(f"[red]  Unknown model: {chosen!r}[/red]")
        return

    set_default_model(chosen)
    rich_console.print(f"[green]  ✔ Default model set to: {chosen}[/green]")
