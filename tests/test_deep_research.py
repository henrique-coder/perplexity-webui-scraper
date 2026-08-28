from __future__ import annotations

from typing import Any, cast

from orjson import dumps
from pytest import raises

from perplexity_webui_scraper import ConversationConfig
from perplexity_webui_scraper._internal.exceptions import ResearchClarifyingQuestionsError
from perplexity_webui_scraper.core.conversation import Conversation


class _Response:
    def json(self) -> dict[str, Any]:
        return {"user": {"subscription_tier": "pro"}}


class _HTTP:
    def __init__(self, streams: list[list[str]]) -> None:
        self.streams = iter(streams)
        self.payloads: list[dict[str, Any]] = []
        self.searches: list[str] = []

    def get(self, _url: str, rate_limited: bool = True) -> _Response:
        return _Response()

    def init_search(self, query: str) -> None:
        self.searches.append(query)

    def stream_ask(self, payload: dict[str, Any]) -> list[str]:
        self.payloads.append(payload)

        return next(self.streams)


def _event(payload: dict[str, Any]) -> str:
    return f"data: {dumps(payload).decode()}"


def _clarification_stream() -> list[str]:
    return [
        _event({"backend_uuid": "thread-1", "read_write_token": "token-1"}),
        _event(
            {
                "text": dumps(
                    [
                        {
                            "step_type": "RESEARCH_CLARIFYING_QUESTIONS",
                            "content": {"questions": ["Qual período devo analisar?"]},
                        }
                    ]
                ).decode()
            }
        ),
    ]


def _final_stream() -> list[str]:
    return [
        _event(
            {
                "text": dumps([{"step_type": "FINAL", "content": {"answer": "Pesquisa concluída."}}]).decode(),
                "final": True,
            }
        )
    ]


def test_deep_research_answers_clarification_automatically() -> None:
    http = _HTTP([_clarification_stream(), _final_stream()])
    conversation = Conversation(
        cast("Any", http),
        ConversationConfig(model="perplexity/deep-research"),
    )

    conversation.ask("Analise o mercado", model="perplexity/deep-research")

    assert conversation.answer == "Pesquisa concluída."
    assert len(http.payloads) == 2
    assert http.payloads[1]["params"]["last_backend_uuid"] == "thread-1"
    assert "escolhendo as opções mais razoáveis" not in http.payloads[1]["query_str"]
    assert "Qual período devo analisar?" in http.payloads[1]["query_str"]


def test_deep_research_manual_mode_exposes_clarification() -> None:
    http = _HTTP([_clarification_stream()])
    conversation = Conversation(
        cast("Any", http),
        ConversationConfig(model="perplexity/deep-research", research_interaction="manual"),
    )

    with raises(ResearchClarifyingQuestionsError, match="Qual período"):
        conversation.ask("Analise o mercado", model="perplexity/deep-research")

    assert len(http.payloads) == 1
