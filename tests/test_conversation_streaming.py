"""Unit tests for user-facing incremental Responses from the Perplexity stream."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

from orjson import dumps

from perplexity_webui_scraper.core.conversation import Conversation
from perplexity_webui_scraper.core.parser import SchematizedStreamState
from perplexity_webui_scraper.models.registry import MODELS


if TYPE_CHECKING:
    from collections.abc import Iterator
    from typing import Any


def _make_conversation(sse_lines: list[str]) -> Conversation:
    conversation = Conversation.__new__(Conversation)
    conversation._config = _FakeConfig()  # ty: ignore[invalid-assignment]
    conversation._citation_mode = "default"
    conversation._backend_uuid = None
    conversation._read_write_token = None
    conversation._answer = None
    conversation._chunks = []
    conversation._search_results = []
    conversation._raw_data = {}
    conversation._schematized_state = SchematizedStreamState()
    conversation._stream_generator = None
    conversation._http = _FakeHttp(sse_lines)  # ty: ignore[invalid-assignment]

    return conversation


class _FakeConfig:
    research_interaction: str = "auto"
    model: str = "perplexity/best"
    allow_risky_model: bool = False
    custom_model_mode: str = "copilot"
    citation_mode: str = "default"
    search_focus: str = "web"
    source_focus: str = "web"
    time_range: str = "all"
    language: str = "en-US"
    timezone: str | None = None
    coordinates: None = None
    save_to_library: bool = False
    space_uuid: str | None = None


class _FakeHttp:
    def __init__(self, lines: list[str]) -> None:
        self.lines = lines

    def stream_ask(self, _payload: dict[str, Any]) -> Iterator[str]:
        yield from self.lines

    def init_search(self, _query: str) -> None:
        pass


def _workflow_frame(chunks: list[str], *, final: bool = False) -> str:
    return (
        "data: "
        + dumps(
            {
                "blocks": [
                    {
                        "workflow_block": {
                            "steps": [
                                {
                                    "items": [
                                        {
                                            "payload": {
                                                "text_payload": {
                                                    "text": "".join(chunks) if final else "",
                                                    "chunks": chunks,
                                                    "is_streaming": not final,
                                                }
                                            }
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                ],
                "final": final,
                "message_mode": "FULL" if final else "STREAMING",
                "text_completed": final,
            }
        ).decode()
    )


def test_conversation_yields_progressive_full_snapshots_then_final_answer() -> None:
    conversation = _make_conversation(
        [
            _workflow_frame(["Computação "]),
            _workflow_frame(["Computação ", "quântica "]),
            _workflow_frame(["Computação ", "quântica ", "é interessante."], final=True),
        ]
    )

    with (
        patch.object(
            Conversation,
            "_validate_request_access",
            autospec=True,
            side_effect=lambda self, model, has_files: model,
        ),
        patch(
            "perplexity_webui_scraper.core.conversation.MODELS.resolve_for_use",
            return_value=MODELS.resolve("perplexity/best"),
        ),
    ):
        conversation.ask("Explain quantum computing.", stream=True)
        snapshots = list(conversation)

    assert len(snapshots) == 3
    assert snapshots[0].answer is None
    assert snapshots[0].chunks == ["Computação "]
    assert snapshots[1].chunks == ["Computação ", "quântica "]
    assert snapshots[2].answer == "Computação quântica é interessante."
    assert snapshots[-1].chunks == ["Computação ", "quântica ", "é interessante."]
    assert conversation.answer == "Computação quântica é interessante."
