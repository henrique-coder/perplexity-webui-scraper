"""SSE line parsing and conversation state update logic.

This module handles all data extraction from the Perplexity SSE stream:
parsing raw bytes lines, processing structured JSON data chunks, extracting
clarifying questions, formatting citations, and updating conversation state.

All functions are pure (or near-pure) and operate on plain data structures,
making them independently testable without any HTTP or client machinery.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from orjson import JSONDecodeError, loads

from perplexity_webui_scraper._internal.constants import (
    CITATION_PATTERN,
    JSON_OBJECT_PATTERN,
)
from perplexity_webui_scraper._internal.exceptions import (
    ResearchClarifyingQuestionsError,
    ResponseParsingError,
)


if TYPE_CHECKING:
    from re import Match

    from perplexity_webui_scraper._internal.types import CitationMode
    from perplexity_webui_scraper.core.response import SearchResultItem


def parse_sse_line(line: str | bytes) -> dict[str, Any] | None:
    """Parse a single SSE data line into a dict.

    SSE lines follow the format ``data: <json-payload>``.  Any line that does
    not start with this prefix is silently ignored.

    Args:
        line: A raw SSE line as bytes or a string.

    Returns:
        Deserialized JSON dict, or ``None`` if the line is not a data line.
    """
    if isinstance(line, bytes):
        if line.startswith(b"data: "):
            return loads(line[6:])
    elif line.startswith("data: "):
        return loads(line[6:])

    return None


def process_sse_data(
    data: dict[str, Any],
    search_results: list[SearchResultItem],
    citation_mode: CitationMode,
) -> tuple[str | None, list[str], list[SearchResultItem], dict[str, Any]]:
    """Process a single SSE data chunk and extract state updates.

    Handles both the schematized block format (``blocks`` key) and the
    plain text format (``text`` key).  Recognises ``FINAL`` and
    ``RESEARCH_CLARIFYING_QUESTIONS`` step types.

    Args:
        data: Deserialized SSE data dict.
        search_results: Current list of search results (used for citation
            formatting).
        citation_mode: Current citation rendering mode.

    Returns:
        A 4-tuple of ``(answer, chunks, updated_search_results, raw_data)``.
        Any element may be ``None`` / empty if the chunk does not contain it.

    Raises:
        ResearchClarifyingQuestionsError: If the response is a clarification
            request from Deep Research mode.
        ResponseParsingError: If the response has an unexpected structure or
            signals a failure status.
    """
    if data.get("status") == "FAILED":
        raise ResponseParsingError(
            f"Query processing failed: {data.get('text', 'Unknown error')}",
            raw_data=str(data),
        )

    if "text" not in data and "blocks" not in data:
        return None, [], search_results, {}

    try:
        json_data = loads(data["text"])
    except KeyError as error:
        raise ValueError("Missing 'text' field in SSE data chunk") from error
    except JSONDecodeError:
        json_data = dict(data)
        json_data["answer"] = data.get("text")

    if isinstance(json_data, list):
        return _process_block_list(json_data, search_results, citation_mode)

    if isinstance(json_data, dict):
        updated_results, answer, chunks, raw = _extract_state(json_data, search_results, citation_mode)
        return answer, chunks, updated_results, raw

    raise ResponseParsingError(
        "Unexpected JSON structure in 'text' field",
        raw_data=str(json_data),
    )


def extract_clarifying_questions(item: dict[str, Any]) -> list[str]:
    """Extract clarifying question strings from a ``RESEARCH_CLARIFYING_QUESTIONS`` step.

    Handles all known content shapes:

    - ``{"questions": [...]}``
    - ``{"clarifying_questions": [...]}``
    - Any dict value that is a string containing ``"?"``
    - Plain list of strings
    - Plain string

    Args:
        item: The raw step item dict from the SSE block list.

    Returns:
        List of clarifying question strings.  Empty list if none found.
    """
    questions: list[str] = []
    content = item.get("content", {})

    if isinstance(content, dict):
        if "questions" in content:
            raw = content["questions"]
            if isinstance(raw, list):
                questions = [str(q) for q in raw if q]
        elif "clarifying_questions" in content:
            raw = content["clarifying_questions"]
            if isinstance(raw, list):
                questions = [str(q) for q in raw if q]
        elif not questions:
            for value in content.values():
                if isinstance(value, str) and "?" in value:
                    questions.append(value)
    elif isinstance(content, list):
        questions = [str(q) for q in content if q]
    elif isinstance(content, str):
        questions = [content]

    return questions


def format_citations(
    text: str | None,
    citation_mode: CitationMode,
    search_results: list[SearchResultItem],
) -> str | None:
    """Apply citation formatting to response text.

    Args:
        text: The raw answer text (may contain ``[1]``, ``[2]`` … markers).
        citation_mode: Controls rendering behaviour.
        search_results: Current search result list for URL lookup.

    Returns:
        Formatted text, or the original text if ``citation_mode == "default"``
        or the text is ``None`` / empty.
    """
    if not text or citation_mode == "default":
        return text

    def replacer(m: Match[str]) -> str:
        """Replace a single citation marker according to the current mode."""
        num = m.group(1)

        if not num.isdigit():
            return m.group(0)

        if citation_mode == "clean":
            return ""

        idx = int(num) - 1

        if 0 <= idx < len(search_results):
            url = search_results[idx].url or ""

            if citation_mode == "markdown" and url:
                return f"[{num}]({url})"

        return m.group(0)

    return CITATION_PATTERN.sub(replacer, text)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _process_block_list(
    block_list: list[Any],
    search_results: list[SearchResultItem],
    citation_mode: CitationMode,
) -> tuple[str | None, list[str], list[SearchResultItem], dict[str, Any]]:
    """Process a list of step blocks, looking for FINAL or clarifying questions.

    Args:
        block_list: List of step dicts from the ``text`` field.
        search_results: Current search results for citation lookup.
        citation_mode: Citation rendering mode.

    Returns:
        Same 4-tuple as :func:`process_sse_data`.

    Raises:
        ResearchClarifyingQuestionsError: If a clarification step is found.
    """
    for item in block_list:
        step_type = item.get("step_type")

        if step_type == "RESEARCH_CLARIFYING_QUESTIONS":
            questions = extract_clarifying_questions(item)
            raise ResearchClarifyingQuestionsError(questions)

        if step_type == "FINAL":
            raw_content: dict[str, Any] = item.get("content", {})
            answer_content = raw_content.get("answer")

            answer_data: dict[str, Any]

            if isinstance(answer_content, str) and JSON_OBJECT_PATTERN.match(answer_content):
                from orjson import loads as _loads  # noqa: PLC0415

                answer_data = _loads(answer_content)
            else:
                answer_data = raw_content

            updated, answer, chunks, raw = _extract_state(answer_data, search_results, citation_mode)
            return answer, chunks, updated, raw

    return None, [], search_results, {}


def _extract_state(
    answer_data: dict[str, Any],
    current_results: list[SearchResultItem],
    citation_mode: CitationMode,
) -> tuple[list[SearchResultItem], str | None, list[str], dict[str, Any]]:
    """Extract answer, chunks, and search results from a parsed answer dict.

    Args:
        answer_data: The dict containing ``answer``, ``chunks``, ``web_results``.
        current_results: Previous search results (used if none in this chunk).
        citation_mode: Citation rendering mode.

    Returns:
        4-tuple of ``(search_results, answer, chunks, raw_data)``.
    """
    from perplexity_webui_scraper.core.response import SearchResultItem  # noqa: PLC0415

    web_results = answer_data.get("web_results", [])
    updated_results = current_results

    if web_results:
        updated_results = [
            SearchResultItem(
                title=r.get("name"),
                snippet=r.get("snippet"),
                url=r.get("url"),
            )
            for r in web_results
            if isinstance(r, dict)
        ]

    answer_text: str | None = answer_data.get("answer")
    formatted_answer = format_citations(answer_text, citation_mode, updated_results)

    raw_chunks: list[Any] = answer_data.get("chunks", [])
    formatted_chunks: list[str] = []

    if raw_chunks:
        formatted_chunks = [
            c
            for chunk in raw_chunks
            if chunk is not None
            for c in (format_citations(chunk, citation_mode, updated_results),)
            if c is not None
        ]

    return updated_results, formatted_answer, formatted_chunks, answer_data
