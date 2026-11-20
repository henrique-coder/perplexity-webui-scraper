"""Unit tests for user-facing incremental response snapshots from the Perplexity stream."""

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


def _make_conversation(
    sse_lines: list[str],
    sse_streams: list[list[str]] | None = None,
) -> Conversation:
    conversation = Conversation.__new__(Conversation)
    conversation._config = _FakeConfig()  # ty: ignore[invalid-assignment]
    conversation._citation_mode = "default"
    conversation._backend_uuid = None
    conversation._read_write_token = None
    conversation._answer = None
    conversation._activity = {}
    conversation._chunks = []
    conversation._search_results = []
    conversation._raw_data = {}
    conversation._schematized_state = SchematizedStreamState()
    conversation._stream_generator = None
    conversation._http = _FakeHttp(sse_lines, sse_streams=sse_streams)  # ty: ignore[invalid-assignment]

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
    latitude: float | None = None
    longitude: float | None = None
    save_to_library: bool = False
    space_uuid: str | None = None


class _FakeHttp:
    def __init__(self, lines: list[str], *, sse_streams: list[list[str]] | None = None) -> None:
        self._streams = sse_streams or [lines]
        self._stream_index = 0

    def stream_ask(self, _payload: dict[str, Any]) -> Iterator[str]:
        lines: list[str] = self._streams[self._stream_index]
        self._stream_index += 1
        yield from lines

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
            _workflow_frame(["Quantum computing "]),
            _workflow_frame(["Quantum computing ", "is "]),
            _workflow_frame(["Quantum computing ", "is interesting."], final=True),
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
    assert snapshots[0].chunks == ["Quantum computing "]
    assert snapshots[1].chunks == ["Quantum computing ", "is "]
    assert snapshots[2].answer == "Quantum computing is interesting."
    assert snapshots[-1].chunks == ["Quantum computing ", "is interesting."]
    assert conversation.answer == "Quantum computing is interesting."


def test_conversation_snapshots_include_safe_workflow_activity_and_public_sources() -> None:
    conversation = _make_conversation(
        [
            "data: "
            + dumps(
                {
                    "blocks": [
                        {
                            "intended_usage": "workflow_root",
                            "workflow_block": {
                                "status": "WORKFLOW_EXECUTING_STEPS",
                                "steps": [
                                    {
                                        "tool_name": "search_web",
                                        "status": "WORKFLOW_EXECUTING_STEPS",
                                        "items": [
                                            {
                                                "type": "WORKFLOW_ITEM_QUERIES",
                                                "payload": {"queries_payload": {"queries": ["public search query"]}},
                                            },
                                            {
                                                "type": "WORKFLOW_ITEM_SOURCES",
                                                "payload": {
                                                    "sources_payload": {
                                                        "sources": [
                                                            {
                                                                "name": "Example source",
                                                                "url": "https://example.com/article",
                                                                "snippet": "Public summary",
                                                                "meta_data": {"private": "drop"},
                                                            }
                                                        ]
                                                    }
                                                },
                                            },
                                            {
                                                "type": "PRIVATE_REASONING",
                                                "payload": {
                                                    "text_payload": {
                                                        "text": "private intermediate reasoning",
                                                        "chunks": ["private intermediate reasoning"],
                                                    }
                                                },
                                            },
                                        ],
                                    }
                                ],
                            },
                        },
                        {
                            "intended_usage": "web_results",
                            "web_result_block": {
                                "progress": "IN_PROGRESS",
                                "web_results": [
                                    {
                                        "name": "Example source",
                                        "url": "https://example.com/article",
                                        "snippet": "Public summary",
                                        "meta_data": {"private": "drop"},
                                    }
                                ],
                            },
                        },
                    ]
                }
            ).decode(),
            _workflow_frame(["Final public answer"], final=True),
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
        conversation.ask("Explain this topic.", stream=True)
        snapshots = list(conversation)

    activity = snapshots[0].activity
    assert len(activity) == 1
    assert activity[0].kind == "search"
    assert activity[0].status == "in_progress"
    assert activity[0].label == "Searching the web"
    assert activity[0].queries == ["public search query"]
    assert activity[0].results[0].model_dump() == {
        "url": "https://example.com/article",
        "title": "Example source",
        "snippet": "Public summary",
    }
    assert "PRIVATE_REASONING" not in str(activity)
    assert "drop" not in str(activity)

    assert snapshots[-1].answer == "Final public answer"
    assert snapshots[-1].activity[-1].status == "completed"
    assert snapshots[0].activity[0].status == "in_progress"
    assert snapshots[-1].activity[-1].results[0].url == "https://example.com/article"


def test_non_streaming_conversation_exposes_visible_activity() -> None:
    frame = dumps(
        {
            "blocks": [
                {
                    "workflow_block": {
                        "status": "WORKFLOW_COMPLETED",
                        "steps": [
                            {
                                "tool_name": "search_web",
                                "items": [
                                    {
                                        "type": "WORKFLOW_ITEM_QUERIES",
                                        "payload": {"queries_payload": {"queries": ["query text stays private"]}},
                                    },
                                    {
                                        "type": "WORKFLOW_ITEM_SOURCES",
                                        "payload": {
                                            "sources_payload": {
                                                "sources": [
                                                    {
                                                        "name": "Example source",
                                                        "url": "https://example.com/article",
                                                        "snippet": "Public summary",
                                                    }
                                                ]
                                            }
                                        },
                                    },
                                    {
                                        "type": "WORKFLOW_ITEM_TEXT",
                                        "payload": {
                                            "text_payload": {
                                                "variant": "answer",
                                                "text": "Final answer",
                                                "chunks": ["Final answer"],
                                            }
                                        },
                                    },
                                ],
                            }
                        ],
                    }
                }
            ],
            "final": True,
        }
    ).decode()
    conversation = _make_conversation([f"data: {frame}"])

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
        conversation.ask("Question", stream=False)

    assert conversation.answer == "Final answer"
    assert len(conversation.activity) == 1
    assert conversation.activity[0].status == "completed"
    assert conversation.activity[0].results[0].url == "https://example.com/article"
    assert conversation.activity[0].queries == ["query text stays private"]


def test_conversation_does_not_carry_search_results_to_a_new_turn() -> None:
    conversation = _make_conversation(
        [],
        sse_streams=[
            [
                "data: "
                + dumps(
                    {
                        "blocks": [
                            {
                                "web_result_block": {
                                    "web_results": [
                                        {
                                            "name": "Old source",
                                            "url": "https://old.example/article",
                                            "snippet": "Old summary",
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                ).decode(),
                _workflow_frame(["First answer"], final=True),
            ],
            [
                "data: "
                + dumps(
                    {
                        "blocks": [
                            {
                                "workflow_block": {"steps": [{"tool_name": "search_web", "items": []}]},
                                "web_result_block": {
                                    "web_results": [
                                        {
                                            "name": "New source",
                                            "url": "https://new.example/article",
                                            "snippet": "New summary",
                                        }
                                    ]
                                },
                            }
                        ]
                    }
                ).decode(),
                _workflow_frame(["Second answer"], final=True),
            ],
        ],
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
        conversation.ask("First turn", stream=True)
        list(conversation)
        conversation.ask("Second turn", stream=True)
        snapshots = list(conversation)

    assert [item.url for item in snapshots[-1].search_results] == ["https://new.example/article"]


def test_conversation_early_break_closes_stream_and_null_uuid_does_not_clobber() -> None:
    closed = False

    class _ClosingHttp(_FakeHttp):
        def stream_ask(self, _payload: dict[str, Any]) -> Iterator[str]:
            nonlocal closed
            try:
                yield "data: " + dumps({"backend_uuid": "thread-1", "read_write_token": "rw-1"}).decode()
                yield "data: " + dumps({"backend_uuid": None, "read_write_token": ""}).decode()
                yield _workflow_frame(["Done"], final=True)
            finally:
                closed = True

    conversation = _make_conversation([])
    conversation._http = _ClosingHttp([])  # ty: ignore[invalid-assignment]

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
        conversation.ask("Test", stream=True)
        iterator = iter(conversation)
        first = next(iterator)
        second = next(iterator)
        iterator.close()

    assert first.conversation_uuid == "thread-1"
    assert second.conversation_uuid == "thread-1"
    assert conversation.uuid == "thread-1"
    assert conversation._read_write_token == "rw-1"
    assert closed is True
    assert conversation._stream_generator is None
