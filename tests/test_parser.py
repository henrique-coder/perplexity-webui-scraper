from __future__ import annotations

from typing import Any

from pytest import mark, raises

from perplexity_webui_scraper._internal.exceptions import RateLimitError, ResponseParsingError
from perplexity_webui_scraper.core.parser import (
    MAX_ANSWER_BYTES,
    MAX_RAW_DATA_BYTES,
    MAX_SSE_FRAME_BYTES,
    MAX_WORKFLOW_STATE_BYTES,
    SchematizedStreamState,
    _extract_state,
    parse_sse_line,
    process_sse_data,
)


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


def test_process_sse_data_sanitizes_rate_limit_error_text() -> None:
    sensitive_text = "synthetic-rate-limit-marker"

    with raises(RateLimitError) as exc_info:
        process_sse_data({"error_code": "RATE_LIMIT", "text": sensitive_text}, [], "clean")

    assert sensitive_text not in str(exc_info.value)


def test_parse_sse_line_accepts_optional_space_and_done_marker() -> None:
    assert parse_sse_line(b'data:{"status":"PENDING"}') == {"status": "PENDING"}
    assert parse_sse_line("data: [DONE]") is None


def test_sse_rejects_oversize_lines() -> None:
    line = b"data: " + b"x" * (MAX_SSE_FRAME_BYTES + 1)

    with raises(ResponseParsingError, match="maximum allowed size"):
        parse_sse_line(line)


def test_parse_sse_line_enforces_size_limit_for_text_frames() -> None:
    oversized_text = "é" * (MAX_SSE_FRAME_BYTES // 2 + 1)

    with raises(ResponseParsingError, match="maximum allowed size"):
        parse_sse_line(f"data: {oversized_text}")


def test_parse_sse_line_accepts_frame_at_size_limit() -> None:
    line = b'{"status":"' + b"x" * (MAX_SSE_FRAME_BYTES - len(b'{"status":"x"}')) + b'"}'
    parsed = parse_sse_line(b"data:" + line)

    assert parsed is not None
    assert len(parsed["status"]) == MAX_SSE_FRAME_BYTES - len(b'{"status":"x"}')


def test_schematized_raw_data_truncates_at_limit() -> None:
    state = SchematizedStreamState()
    _, _, _, raw = process_sse_data(
        {"blocks": [{"workflow_block": {"diagnostic": "x" * (MAX_RAW_DATA_BYTES + 1)}}]}, [], "default", state
    )

    assert raw["workflow_block"]["truncated"] is True
    assert raw["workflow_block"]["original_size_bytes"] > MAX_RAW_DATA_BYTES
    assert state.workflow_block is not None


def test_schematized_workflow_state_is_capped() -> None:
    state = SchematizedStreamState()

    with raises(ResponseParsingError, match="4 MiB maximum allowed size"):
        process_sse_data(
            {
                "blocks": [
                    {
                        "workflow_block": {
                            "status": "WORKFLOW_EXECUTING_STEPS",
                            "steps": [],
                            "diagnostic": "x" * (MAX_WORKFLOW_STATE_BYTES + 1),
                        }
                    }
                ]
            },
            [],
            "default",
            state,
        )

    assert state.workflow_block is None


def test_schematized_blocks_and_diff_operations_are_count_bounded() -> None:
    with raises(ResponseParsingError, match="100 blocks"):
        process_sse_data({"blocks": [{}] * 101}, [], "default")

    state = SchematizedStreamState(workflow_block={"steps": []})
    with raises(ResponseParsingError, match="100 patch operations"):
        process_sse_data(
            {"blocks": [{"diff_block": {"patches": [{}] * 101}}]},
            [],
            "default",
            state,
        )

    assert state.workflow_block is None


def test_schematized_markdown_chunk_growth_is_bounded() -> None:
    state = SchematizedStreamState()

    with raises(ResponseParsingError, match="100-chunk maximum"):
        process_sse_data(
            {
                "blocks": [
                    {
                        "markdown_block": {
                            "chunk_starting_offset": 100,
                            "chunks": ["overflow"],
                        }
                    }
                ]
            },
            [],
            "default",
            state,
        )

    assert state.markdown_chunks == []


def test_process_sse_data_bounds_legacy_answer_text() -> None:
    sensitive_answer = "answer" * 200_000
    _, _, _, raw = process_sse_data({"text": sensitive_answer}, [], "clean")

    assert len(raw["answer"]) == 1_048_576


def test_malformed_incremental_patch_does_not_expose_patch_path() -> None:
    sensitive_path = "/private-token-field"
    state = SchematizedStreamState(workflow_block={"steps": []})

    with raises(ResponseParsingError) as exc_info:
        process_sse_data(
            {
                "blocks": [
                    {
                        "diff_block": {
                            "patches": [{"op": "replace", "path": sensitive_path}],
                        }
                    }
                ]
            },
            [],
            "default",
            state,
        )

    assert sensitive_path not in str(exc_info.value)
    assert state.workflow_block == {"steps": []}


def test_legacy_raw_projection_caps_chunk_count_and_answer_size() -> None:
    long_answer = "a" * (MAX_ANSWER_BYTES + 100)
    raw = {"answer": long_answer, "chunks": ["chunk"] * 105}

    _, answer, chunks, raw_data = _extract_state(
        {"answer": "short", "chunks": ["chunk"] * 105},
        [],
        "clean",
    )

    assert answer == "short"
    assert len(chunks) == 100
    assert len(raw_data["chunks"]) == 100

    _, answer, _, raw_data = _extract_state(raw, [], "clean")
    assert answer is not None and len(answer) == MAX_ANSWER_BYTES
    assert len(raw_data["answer"]) == MAX_ANSWER_BYTES


def test_legacy_raw_projection_drops_large_unstructured_fields() -> None:
    answer_data = {
        "answer": "final answer",
        "chunks": [],
        "large_debug": "x" * (MAX_RAW_DATA_BYTES + 1),
    }

    _, answer, _, raw = _extract_state(answer_data, [], "clean")

    assert answer == "final answer"
    assert raw["raw_data_truncated"] is True
    assert "large_debug" not in raw


def test_process_sse_data_handles_lowercase_failed_status() -> None:
    with raises(ResponseParsingError, match="Query processing failed") as exc_info:
        process_sse_data({"status": "failed", "text": "Error in processing query."}, [], "clean")

    assert exc_info.value.raw_data is None


def test_process_sse_data_does_not_expose_upstream_error_text() -> None:
    sensitive_text = "synthetic-parser-marker"

    with raises(ResponseParsingError) as exc_info:
        process_sse_data({"status": "failed", "text": sensitive_text}, [], "clean")

    assert sensitive_text not in str(exc_info.value)
    assert exc_info.value.raw_data is None


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


def test_process_sse_data_prefers_longer_workflow_chunks_over_stale_text() -> None:
    state = SchematizedStreamState()
    answer, chunks, _, _ = process_sse_data(
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
                                                "text": "The Berlin Wall fell in 1",
                                                "chunks": ["The Berlin Wall fell in 1989."],
                                            }
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                }
            ],
            "final": True,
        },
        [],
        "default",
        state,
    )

    assert answer == "The Berlin Wall fell in 1989."
    assert chunks == ["The Berlin Wall fell in 1989."]


@mark.parametrize(
    "payload",
    [
        b"data: []",
        b"data: [1, 2]",
        b"data: 1",
        b'data: "x"',
        b"data: true",
        b"data: null",
        "data: []",
        "data: 1",
        'data: "x"',
        b"data: {malformed",
        b"data: ",
    ],
)
def test_parse_sse_line_rejects_non_object_and_malformed_json(payload: bytes | str) -> None:
    with raises(ResponseParsingError):
        parse_sse_line(payload)


@mark.parametrize("payload", [[], [1], 1, "x", True, None])
def test_process_sse_data_rejects_non_object_payload(payload: Any) -> None:
    with raises(ResponseParsingError, match="JSON object"):
        process_sse_data(payload, [], "default")


def test_schematized_web_result_block_sanitizes_activity_and_preserves_long_snippets() -> None:
    state = SchematizedStreamState()
    long_snippet = "s" * 1000
    too_long_snippet = "s" * 2049

    process_sse_data(
        {
            "blocks": [
                {
                    "workflow_block": {
                        "steps": [
                            {
                                "tool_name": "search_web",
                                "items": [
                                    {
                                        "type": "WORKFLOW_ITEM_QUERIES",
                                        "payload": {"queries_payload": {"queries": ["search"]}},
                                    }
                                ],
                            }
                        ]
                    }
                },
                {
                    "web_result_block": {
                        "web_results": [
                            {"name": "Valid", "url": "https://example.com/ok", "snippet": long_snippet},
                            {"name": "Metadata", "url": "http://169.254.169.254/latest", "snippet": "secret"},
                            {"name": "DotLocalhost", "url": "https://localhost./admin", "snippet": "local"},
                            {"name": "EmptyUserinfo", "url": "https://@example.com/user", "snippet": "user"},
                            {"name": "TooLong", "url": "https://example.com/long", "snippet": too_long_snippet},
                        ]
                    }
                },
            ]
        },
        [],
        "default",
        state,
    )

    assert [item.url for item in state.activity["search_web"].results] == ["https://example.com/ok"]
    assert state.activity["search_web"].results[0].snippet == long_snippet


def test_large_final_payload_preserves_web_results_and_markdown_block_links_citations() -> None:
    large_final = {
        "answer": "Result [1]",
        "chunks": ["Result [1]"],
        "web_results": [{"name": "Example", "url": "https://example.com/source", "snippet": "Summary"}],
        "large_extra": "x" * (MAX_RAW_DATA_BYTES + 100),
    }

    updated, answer, chunks, raw = _extract_state(large_final, [], "markdown")

    assert answer == "Result [1](https://example.com/source)"
    assert chunks == ["Result [1](https://example.com/source)"]
    assert [item.url for item in updated] == ["https://example.com/source"]
    assert raw["raw_data_truncated"] is True

    state = SchematizedStreamState()
    answer, chunks, _, _ = process_sse_data(
        {
            "blocks": [
                {
                    "web_result_block": {
                        "web_results": [{"name": "Example", "url": "https://example.com/source", "snippet": "Summary"}]
                    }
                },
                {
                    "markdown_block": {
                        "progress": "DONE",
                        "chunks": ["Cited [1]"],
                        "chunk_starting_offset": 0,
                        "answer": "Cited [1]",
                    }
                },
            ],
            "text_completed": True,
        },
        [],
        "markdown",
        state,
    )

    assert answer == "Cited [1](https://example.com/source)"
    assert chunks == ["Cited [1](https://example.com/source)"]


def test_process_sse_data_does_not_treat_non_answer_workflow_text_as_final() -> None:
    state = SchematizedStreamState()
    answer, chunks, _, _ = process_sse_data(
        {
            "blocks": [
                {
                    "workflow_block": {
                        "steps": [
                            {
                                "items": [
                                    {
                                        "type": "WORKFLOW_ITEM_REASONING",
                                        "payload": {
                                            "text_payload": {
                                                "variant": "reasoning",
                                                "text": "private intermediate reasoning",
                                                "chunks": ["private intermediate reasoning"],
                                            }
                                        },
                                    }
                                ]
                            },
                            {
                                "items": [
                                    {
                                        "type": "PRIVATE_REASONING",
                                        "payload": {
                                            "text_payload": {
                                                "text": "untyped private reasoning",
                                                "chunks": ["untyped private reasoning"],
                                            }
                                        },
                                    }
                                ]
                            },
                            {
                                "items": [
                                    {
                                        "type": "WORKFLOW_ITEM_TEXT",
                                        "payload": {
                                            "text_payload": {
                                                "variant": "answer",
                                                "text": "Public final answer",
                                                "chunks": ["Public final answer"],
                                            }
                                        },
                                    }
                                ]
                            },
                        ]
                    }
                }
            ],
            "final": True,
        },
        [],
        "default",
        state,
    )

    assert answer == "Public final answer"
    assert chunks == ["Public final answer"]


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


def test_schematized_activity_completes_when_final_marker_has_no_blocks() -> None:
    state = SchematizedStreamState()
    process_sse_data(
        {
            "blocks": [
                {
                    "workflow_block": {
                        "status": "WORKFLOW_EXECUTING_STEPS",
                        "steps": [
                            {
                                "tool_name": "search_web",
                                "items": [
                                    {
                                        "type": "WORKFLOW_ITEM_QUERIES",
                                        "payload": {"queries_payload": {"queries": ["public search query"]}},
                                    }
                                ],
                            }
                        ],
                    }
                }
            ]
        },
        [],
        "default",
        state,
    )

    assert state.activity["search_web"].status == "in_progress"
    process_sse_data({"final": True}, [], "default", state)

    assert state.activity["search_web"].status == "completed"


def test_schematized_activity_requires_a_search_query_item() -> None:
    state = SchematizedStreamState()
    process_sse_data(
        {
            "blocks": [
                {
                    "workflow_block": {
                        "status": "WORKFLOW_EXECUTING_STEPS",
                        "steps": [
                            {
                                "tool_name": "search_web",
                                "items": [
                                    {
                                        "type": "WORKFLOW_ITEM_SOURCES",
                                        "payload": {
                                            "sources_payload": {
                                                "sources": [
                                                    {
                                                        "name": "Example",
                                                        "url": "https://example.com/article",
                                                        "snippet": "Summary",
                                                    }
                                                ]
                                            }
                                        },
                                    }
                                ],
                            }
                        ],
                    }
                }
            ]
        },
        [],
        "default",
        state,
    )

    assert state.activity == {}


def test_schematized_activity_allows_an_observed_empty_query_list() -> None:
    state = SchematizedStreamState()
    process_sse_data(
        {
            "blocks": [
                {
                    "workflow_block": {
                        "status": "WORKFLOW_EXECUTING_STEPS",
                        "steps": [
                            {
                                "tool_name": "search_web",
                                "items": [
                                    {
                                        "type": "WORKFLOW_ITEM_QUERIES",
                                        "payload": {"queries_payload": {"queries": []}},
                                    }
                                ],
                            }
                        ],
                    }
                }
            ]
        },
        [],
        "default",
        state,
    )

    assert state.activity["search_web"].queries == []


def test_schematized_activity_skips_malformed_source_fields() -> None:
    state = SchematizedStreamState()
    process_sse_data(
        {
            "blocks": [
                {
                    "workflow_block": {
                        "status": "WORKFLOW_EXECUTING_STEPS",
                        "steps": [
                            {
                                "tool_name": "search_web",
                                "items": [
                                    {
                                        "type": "WORKFLOW_ITEM_QUERIES",
                                        "payload": {"queries_payload": {"queries": ["question"]}},
                                    },
                                    {
                                        "type": "WORKFLOW_ITEM_SOURCES",
                                        "payload": {
                                            "sources_payload": {
                                                "sources": [
                                                    {
                                                        "name": "Valid source",
                                                        "url": "https://example.com/valid",
                                                        "snippet": "Valid summary",
                                                    },
                                                    {
                                                        "name": {"private": "not a string"},
                                                        "url": "https://example.com/invalid-title",
                                                        "snippet": "Summary",
                                                    },
                                                    {
                                                        "name": "Invalid URL",
                                                        "url": ["https://example.com/article"],
                                                        "snippet": "Summary",
                                                    },
                                                    {
                                                        "name": "Invalid snippet",
                                                        "url": "https://example.com/invalid-snippet",
                                                        "snippet": {"private": "not a string"},
                                                    },
                                                ]
                                            }
                                        },
                                    },
                                ],
                            }
                        ],
                    },
                }
            ]
        },
        [],
        "default",
        state,
    )

    assert [result.url for result in state.activity["search_web"].results] == ["https://example.com/valid"]


def test_schematized_activity_bounds_queries_and_filters_unsafe_sources() -> None:
    state = SchematizedStreamState()
    queries = [f"query {index}" for index in range(25)]
    results = [
        {"name": "Public", "url": "https://example.com/article#section", "snippet": "summary"},
        {"name": "Duplicate", "url": "https://example.com/article", "snippet": "updated summary"},
        {"name": "Plain HTTP", "url": "http://example.org/article", "snippet": "summary"},
        {"name": "Localhost", "url": "https://localhost/article", "snippet": "summary"},
        {"name": "Private IP", "url": "https://10.0.0.1/article", "snippet": "summary"},
        {"name": "Credential URL", "url": "https://user:password@example.net/article", "snippet": "summary"},
        {"name": "Long snippet", "url": "https://long.example/article", "snippet": "x" * 2049},
    ]

    process_sse_data(
        {
            "blocks": [
                {
                    "workflow_block": {
                        "status": "WORKFLOW_EXECUTING_STEPS",
                        "steps": [
                            {
                                "tool_name": "search_web",
                                "items": [
                                    {
                                        "type": "WORKFLOW_ITEM_QUERIES",
                                        "payload": {"queries_payload": {"queries": queries}},
                                    },
                                    {
                                        "type": "WORKFLOW_ITEM_SOURCES",
                                        "payload": {"sources_payload": {"sources": results}},
                                    },
                                ],
                            }
                        ],
                    }
                }
            ]
        },
        [],
        "default",
        state,
    )

    activity = state.activity["search_web"]
    assert activity.kind == "search"
    assert activity.queries == queries[:20]
    assert [result.url for result in activity.results] == ["https://example.com/article"]
    assert activity.results[0].title == "Duplicate"


def test_schematized_activity_query_limit_applies_across_updates() -> None:
    state = SchematizedStreamState()
    for suffix in ("first", "second"):
        steps = [
            {
                "tool_name": "search_web",
                "items": [
                    {
                        "type": "WORKFLOW_ITEM_QUERIES",
                        "payload": {
                            "queries_payload": {"queries": [f"{suffix} step 0 query {index}" for index in range(15)]}
                        },
                    }
                ],
            }
        ]

        if suffix == "second":
            steps.append(
                {
                    "tool_name": "search_web",
                    "items": [
                        {
                            "type": "WORKFLOW_ITEM_QUERIES",
                            "payload": {
                                "queries_payload": {"queries": [f"second step 1 query {index}" for index in range(15)]}
                            },
                        }
                    ],
                }
            )

        process_sse_data(
            {
                "blocks": [
                    {
                        "workflow_block": {
                            "status": "WORKFLOW_EXECUTING_STEPS",
                            "steps": steps,
                        }
                    }
                ]
            },
            [],
            "default",
            state,
        )

    activity = state.activity["search_web"]
    assert activity.status == "in_progress"
    assert activity.queries == [f"first step 0 query {index}" for index in range(15)] + [
        f"second step 0 query {index}" for index in range(5)
    ]


def test_schematized_activity_rejects_invalid_public_source_urls() -> None:
    state = SchematizedStreamState()
    urls = [
        "https://example.com/valid",
        "https://printer.local/article",
        "https://[fd00::1]/article",
        "https://example.com:invalid/article",
        f"https://example.com/{'x' * 2048}",
    ]
    sources = [{"name": f"Source {index}", "url": url, "snippet": "Summary"} for index, url in enumerate(urls)]

    process_sse_data(
        {
            "blocks": [
                {
                    "workflow_block": {
                        "steps": [
                            {
                                "tool_name": "search_web",
                                "items": [
                                    {
                                        "type": "WORKFLOW_ITEM_QUERIES",
                                        "payload": {"queries_payload": {"queries": ["public query"]}},
                                    },
                                    {
                                        "type": "WORKFLOW_ITEM_SOURCES",
                                        "payload": {"sources_payload": {"sources": sources}},
                                    },
                                ],
                            }
                        ]
                    }
                }
            ]
        },
        [],
        "default",
        state,
    )

    assert [result.url for result in state.activity["search_web"].results] == ["https://example.com/valid"]


def test_schematized_activity_caps_source_results_at_fifty() -> None:
    state = SchematizedStreamState()
    sources = [
        {"name": f"Source {index}", "url": f"https://example.com/{index}", "snippet": "Summary"} for index in range(55)
    ]

    process_sse_data(
        {
            "blocks": [
                {
                    "workflow_block": {
                        "steps": [
                            {
                                "tool_name": "search_web",
                                "items": [
                                    {
                                        "type": "WORKFLOW_ITEM_QUERIES",
                                        "payload": {"queries_payload": {"queries": ["public query"]}},
                                    },
                                    {
                                        "type": "WORKFLOW_ITEM_SOURCES",
                                        "payload": {"sources_payload": {"sources": sources[:30]}},
                                    },
                                    {
                                        "type": "WORKFLOW_ITEM_SOURCES",
                                        "payload": {"sources_payload": {"sources": sources[30:]}},
                                    },
                                ],
                            }
                        ]
                    }
                }
            ]
        },
        [],
        "default",
        state,
    )

    results = state.activity["search_web"].results
    assert len(results) == 50
    assert results[0].url == "https://example.com/0"
    assert results[-1].url == "https://example.com/49"


def test_schematized_activity_caps_accumulated_results_across_updates() -> None:
    state = SchematizedStreamState()

    for start in (0, 30):
        sources = [
            {"name": f"Source {index}", "url": f"https://example.com/{index}", "snippet": "Summary"}
            for index in range(start, start + 30)
        ]
        process_sse_data(
            {
                "blocks": [
                    {
                        "workflow_block": {
                            "steps": [
                                {
                                    "tool_name": "search_web",
                                    "items": [
                                        {
                                            "type": "WORKFLOW_ITEM_QUERIES",
                                            "payload": {"queries_payload": {"queries": ["public query"]}},
                                        }
                                    ],
                                }
                            ]
                        }
                    },
                    {"web_result_block": {"web_results": sources}},
                ]
            },
            state.search_results,
            "default",
            state,
        )

    expected_urls = [f"https://example.com/{index}" for index in range(50)]
    assert [result.url for result in state.search_results] == expected_urls
    assert [result.url for result in state.activity["search_web"].results] == expected_urls


def test_schematized_activity_requires_an_observed_search_web_step() -> None:
    state = SchematizedStreamState()
    process_sse_data(
        {
            "blocks": [
                {
                    "workflow_block": {
                        "steps": [
                            {
                                "tool_name": "other_tool",
                                "items": [
                                    {
                                        "type": "WORKFLOW_ITEM_QUERIES",
                                        "payload": {"queries_payload": {"queries": ["not a search"]}},
                                    }
                                ],
                            }
                        ]
                    }
                }
            ]
        },
        [],
        "default",
        state,
    )

    assert state.activity == {}


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


def test_process_sse_data_prefers_markdown_chunks_over_stale_answer() -> None:
    state = SchematizedStreamState()
    answer, chunks, _, _ = process_sse_data(
        {
            "blocks": [
                {
                    "markdown_block": {
                        "progress": "IN_PROGRESS",
                        "chunks": ["The Berlin Wall fell in 1"],
                        "chunk_starting_offset": 0,
                        "answer": "The Berlin Wall fell in 1",
                    }
                }
            ],
            "text_completed": False,
        },
        [],
        "default",
        state,
    )

    assert answer is None
    assert chunks == ["The Berlin Wall fell in 1"]

    answer, chunks, _, _ = process_sse_data(
        {
            "blocks": [
                {
                    "markdown_block": {
                        "progress": "DONE",
                        "chunks": ["989."],
                        "chunk_starting_offset": 1,
                    }
                }
            ],
            "text_completed": True,
            "final": True,
        },
        [],
        "default",
        state,
    )

    assert answer == "The Berlin Wall fell in 1989."
    assert chunks == ["The Berlin Wall fell in 1", "989."]
