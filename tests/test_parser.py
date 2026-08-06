from __future__ import annotations

from pytest import raises

from perplexity_webui_scraper._internal.exceptions import RateLimitError, ResponseParsingError
from perplexity_webui_scraper.core.parser import SchematizedStreamState, parse_sse_line, process_sse_data


def test_process_sse_data_raises_rate_limit_for_free_tier_error() -> None:
    with raises(RateLimitError) as exc_info:
        process_sse_data(
            {
                "error_code": "FREE_TIER_RATE_LIMITED",
                "experience": "upgrade",
                "status": "failed",
                "final_sse_message": True,
            },
            [],
            "clean",
        )

    assert exc_info.value.status_code == 429
    assert "FREE_TIER_RATE_LIMITED" in exc_info.value.message


def test_parse_sse_line_accepts_optional_space_and_done_marker() -> None:
    assert parse_sse_line(b'data:{"status":"PENDING"}') == {"status": "PENDING"}
    assert parse_sse_line("data: [DONE]") is None


def test_process_sse_data_handles_lowercase_failed_status() -> None:
    with raises(ResponseParsingError, match="Error in processing query"):
        process_sse_data(
            {
                "status": "failed",
                "text": "Error in processing query.",
            },
            [],
            "clean",
        )


def test_process_sse_data_handles_schematized_workflow_and_diffs() -> None:
    state = SchematizedStreamState()
    initial = {
        "blocks": [
            {
                "intended_usage": "workflow_root",
                "workflow_block": {
                    "status": "WORKFLOW_EXECUTING_STEPS",
                    "steps": [
                        {
                            "items": [
                                {
                                    "payload": {
                                        "text_payload": {
                                            "text": "",
                                            "chunks": ["Pong! How can I help you to"],
                                        }
                                    }
                                }
                            ]
                        }
                    ],
                },
            }
        ],
        "text_completed": False,
        "final_sse_message": False,
    }

    answer, chunks, _, raw = process_sse_data(initial, [], "default", state)
    assert answer is None
    assert chunks == ["Pong! How can I help you to"]
    assert raw["workflow_block"]["status"] == "WORKFLOW_EXECUTING_STEPS"

    update = {
        "blocks": [
            {
                "diff_block": {
                    "field": "workflow_block",
                    "patches": [
                        {"op": "replace", "path": "/status", "value": "WORKFLOW_COMPLETED"},
                        {
                            "op": "replace",
                            "path": "/steps/0/items/0/payload/text_payload/text",
                            "value": "Pong! How can I help you today?",
                        },
                        {"op": "add", "path": "/steps/0/items/0/payload/text_payload/chunks/1", "value": "day?"},
                    ],
                }
            }
        ],
        "text_completed": True,
        "final_sse_message": False,
    }

    answer, chunks, _, raw = process_sse_data(update, [], "default", state)
    assert answer == "Pong! How can I help you today?"
    assert chunks == ["Pong! How can I help you to", "day?"]
    assert raw["workflow_block"]["status"] == "WORKFLOW_COMPLETED"


def test_process_sse_data_ignores_schematized_control_blocks_without_text() -> None:
    state = SchematizedStreamState()
    answer, chunks, results, raw = process_sse_data(
        {"blocks": [{"answer_tabs_block": {"modes": [{"answer_mode_type": "ANSWER"}]}}]},
        [],
        "default",
        state,
    )

    assert answer is None
    assert chunks == []
    assert results == []
    assert raw == {}


def test_process_sse_data_supports_schematized_final_event_without_new_block() -> None:
    state = SchematizedStreamState()
    process_sse_data(
        {
            "blocks": [
                {
                    "workflow_block": {
                        "steps": [{"items": [{"payload": {"text_payload": {"text": "Done", "chunks": ["Done"]}}}]}]
                    }
                }
            ]
        },
        [],
        "default",
        state,
    )

    answer, chunks, _, _ = process_sse_data({"final": True}, [], "default", state)
    assert answer == "Done"
    assert chunks == ["Done"]


def test_process_sse_data_merges_markdown_chunks_and_web_results() -> None:
    state = SchematizedStreamState()
    _, chunks, results, _ = process_sse_data(
        {
            "blocks": [
                {
                    "web_result_block": {
                        "progress": "IN_PROGRESS",
                        "web_results": [{"name": "Example", "url": "https://example.com", "snippet": "Source"}],
                    }
                },
                {"markdown_block": {"progress": "IN_PROGRESS", "chunks": ["P"], "chunk_starting_offset": 0}},
            ]
        },
        [],
        "default",
        state,
    )
    assert chunks == ["P"]
    assert results[0].title == "Example"

    answer, chunks, results, _ = process_sse_data(
        {
            "blocks": [
                {
                    "markdown_block": {
                        "progress": "DONE",
                        "chunks": ["P", "ONG."],
                        "chunk_starting_offset": 0,
                        "answer": "PONG.",
                    }
                }
            ],
            "text_completed": True,
        },
        results,
        "default",
        state,
    )
    assert answer == "PONG."
    assert chunks == ["P", "ONG."]
    assert results[0].url == "https://example.com"


def test_process_sse_data_uses_markdown_chunks_when_final_answer_is_omitted() -> None:
    state = SchematizedStreamState()
    answer, chunks, _, _ = process_sse_data(
        {
            "blocks": [{"markdown_block": {"progress": "IN_PROGRESS", "chunks": ["PONG"]}}],
            "text_completed": True,
            "final": True,
        },
        [],
        "default",
        state,
    )
    assert answer == "PONG"
    assert chunks == ["PONG"]
