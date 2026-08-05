"""SSE line parsing and conversation state update logic.

This module handles all data extraction from the Perplexity SSE stream:
parsing raw bytes lines, processing structured JSON data chunks, extracting
clarifying questions, formatting citations, and updating conversation state.

All functions are pure (or near-pure) and operate on plain data structures,
making them independently testable without any HTTP or client machinery.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from orjson import JSONDecodeError, loads

from perplexity_webui_scraper._internal.constants import (
    CITATION_PATTERN,
    JSON_OBJECT_PATTERN,
)
from perplexity_webui_scraper._internal.exceptions import (
    RateLimitError,
    ResearchClarifyingQuestionsError,
    ResponseParsingError,
)


if TYPE_CHECKING:
    from re import Match

    from perplexity_webui_scraper._internal.types import CitationMode
    from perplexity_webui_scraper.core.response import SearchResultItem


@dataclass
class SchematizedStreamState:
    """Mutable state needed to apply schematized WebUI stream updates."""

    workflow_block: dict[str, Any] | None = None
    answer: str | None = None
    chunks: list[str] = field(default_factory=list)
    markdown_chunks: list[str] = field(default_factory=list)


def _json_pointer_tokens(path: str) -> list[str]:
    """Decode an RFC 6901 JSON Pointer path."""
    if path == "":
        return []
    if not path.startswith("/"):
        raise ValueError(f"Invalid JSON Patch path: {path!r}")
    return [part.replace("~1", "/").replace("~0", "~") for part in path[1:].split("/")]


def _apply_json_patch(document: Any, operation: dict[str, Any]) -> None:
    """Apply the JSON Patch subset emitted by the WebUI.

    Perplexity currently emits ``add``, ``replace`` and ``remove`` operations
    against object fields and list indexes.  Keeping this small implementation
    private avoids adding a dependency for a wire-format detail.
    """
    op = operation.get("op")
    tokens = _json_pointer_tokens(str(operation.get("path", "")))
    if not tokens:
        raise ValueError("Root JSON Patch operations are not supported")

    target = document
    for token in tokens[:-1]:
        target = target[int(token)] if isinstance(target, list) else target[token]
    key = tokens[-1]

    if isinstance(target, list):
        if op == "add":
            if key == "-":
                target.append(operation.get("value"))
            else:
                target.insert(int(key), operation.get("value"))
        elif op == "replace":
            target[int(key)] = operation.get("value")
        elif op == "remove":
            target.pop(int(key))
        else:
            raise ValueError(f"Unsupported JSON Patch operation: {op!r}")
        return

    if not isinstance(target, dict):
        raise TypeError("JSON Patch target must be an object or list")
    if op in {"add", "replace"}:
        target[key] = operation.get("value")
    elif op == "remove":
        target.pop(key, None)
    else:
        raise ValueError(f"Unsupported JSON Patch operation: {op!r}")


def _process_schematized_blocks(
    data: dict[str, Any],
    search_results: list[SearchResultItem],
    citation_mode: CitationMode,
    state: SchematizedStreamState,
) -> tuple[str | None, list[str], list[SearchResultItem], dict[str, Any]]:
    """Process the ``workflow_block``/``diff_block`` stream format."""
    raw_blocks = data.get("blocks", [])
    raw_data: dict[str, Any] = {}
    for block in raw_blocks if isinstance(raw_blocks, list) else []:
        if not isinstance(block, dict):
            continue

        workflow_block = block.get("workflow_block")
        if isinstance(workflow_block, dict):
            state.workflow_block = deepcopy(workflow_block)
            raw_data["workflow_block"] = deepcopy(workflow_block)

        diff_block = block.get("diff_block")
        if isinstance(diff_block, dict) and state.workflow_block is not None:
            for patch in diff_block.get("patches", []):
                if isinstance(patch, dict):
                    _apply_json_patch(state.workflow_block, patch)
            raw_data["diff_block"] = deepcopy(diff_block)

        markdown_block = block.get("markdown_block")
        if isinstance(markdown_block, dict):
            _process_markdown_block(markdown_block, citation_mode, state)
            raw_data["markdown_block"] = deepcopy(markdown_block)

        web_result_block = block.get("web_result_block")
        if isinstance(web_result_block, dict):
            updated_results = _extract_web_results(web_result_block)
            if updated_results is not None:
                search_results = updated_results
            raw_data["web_result_block"] = deepcopy(web_result_block)

    if state.workflow_block is not None:
        extracted = _extract_workflow_text(state.workflow_block, citation_mode, search_results)
        if extracted is not None:
            state.answer, state.chunks, search_results = extracted

    is_final = bool(data.get("text_completed") or data.get("final_sse_message") or data.get("final"))
    if is_final and state.answer is None and state.markdown_chunks:
        state.answer = format_citations("".join(state.markdown_chunks), citation_mode, search_results)
    answer = state.answer if is_final else None
    if state.workflow_block is not None:
        raw_data["workflow_block"] = deepcopy(state.workflow_block)
    raw = raw_data
    return answer, list(state.chunks), search_results, raw


def _process_markdown_block(
    markdown_block: dict[str, Any],
    citation_mode: CitationMode,
    state: SchematizedStreamState,
) -> None:
    """Merge an incremental markdown block into the stream state."""
    raw_chunks = markdown_block.get("chunks", [])
    if isinstance(raw_chunks, list):
        offset = markdown_block.get("chunk_starting_offset", 0)
        if not isinstance(offset, int) or offset < 0:
            offset = 0
        if offset == 0:
            state.markdown_chunks = []
        while len(state.markdown_chunks) < offset:
            state.markdown_chunks.append("")
        for index, chunk in enumerate(raw_chunks):
            value = format_citations(str(chunk), citation_mode, []) if chunk is not None else ""
            target = offset + index
            if target == len(state.markdown_chunks):
                state.markdown_chunks.append(value or "")
            elif target < len(state.markdown_chunks):
                state.markdown_chunks[target] = value or ""
            else:
                state.markdown_chunks.extend([""] * (target - len(state.markdown_chunks)))
                state.markdown_chunks.append(value or "")

    answer = markdown_block.get("answer")
    if isinstance(answer, str) and answer:
        state.answer = format_citations(answer, citation_mode, [])
    state.chunks = list(state.markdown_chunks) or state.chunks


def _extract_web_results(web_result_block: dict[str, Any]) -> list[SearchResultItem] | None:
    """Convert schematized web results to the public search-result model."""
    from perplexity_webui_scraper.core.response import SearchResultItem  # noqa: PLC0415

    raw_results = web_result_block.get("web_results")
    if not isinstance(raw_results, list):
        return None
    return [
        SearchResultItem(
            title=result.get("name"),
            snippet=result.get("snippet"),
            url=result.get("url"),
        )
        for result in raw_results
        if isinstance(result, dict)
    ]


def _extract_workflow_text(
    workflow_block: dict[str, Any],
    citation_mode: CitationMode,
    search_results: list[SearchResultItem],
) -> tuple[str | None, list[str], list[SearchResultItem]] | None:
    """Extract answer text and chunks from a schematized workflow block."""
    steps = workflow_block.get("steps", [])
    for step in steps if isinstance(steps, list) else []:
        if not isinstance(step, dict):
            continue
        items = step.get("items", [])
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            payload = item.get("payload", {})
            text_payload = payload.get("text_payload", {}) if isinstance(payload, dict) else {}
            if not isinstance(text_payload, dict):
                continue
            raw_chunks = text_payload.get("chunks", [])
            chunks = [str(chunk) for chunk in raw_chunks if chunk is not None] if isinstance(raw_chunks, list) else []
            text = text_payload.get("text")
            answer = format_citations(text if isinstance(text, str) and text else None, citation_mode, search_results)
            if chunks:
                chunks = [format_citations(chunk, citation_mode, search_results) or "" for chunk in chunks]
            if answer is not None or chunks:
                return answer, chunks, search_results
    return None


def parse_sse_line(line: str | bytes) -> dict[str, Any] | None:
    """Parse a single SSE data line into a dict.

    SSE lines follow the format ``data: <json-payload>``.  Any line that does
    not start with this prefix is silently ignored.  The optional space after
    the colon is accepted because both variants occur in browser streams.

    Args:
        line: A raw SSE line as bytes or a string.

    Returns:
        Deserialized JSON dict, or ``None`` if the line is not a data line.
    """
    if isinstance(line, bytes):
        if line.startswith(b"data:"):
            payload = line[5:].lstrip()
            if payload == b"[DONE]":
                return None
            return loads(payload)
    elif line.startswith("data:"):
        payload = line[5:].lstrip()
        if payload == "[DONE]":
            return None
        return loads(payload)

    return None


def process_sse_data(
    data: dict[str, Any],
    search_results: list[SearchResultItem],
    citation_mode: CitationMode,
    schematized_state: SchematizedStreamState | None = None,
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
        schematized_state: Optional state used to apply incremental WebUI
            workflow patches across multiple SSE events.

    Returns:
        A 4-tuple of ``(answer, chunks, updated_search_results, raw_data)``.
        Any element may be ``None`` / empty if the chunk does not contain it.

    Raises:
        ResearchClarifyingQuestionsError: If the response is a clarification
            request from Deep Research mode.
        ResponseParsingError: If the response has an unexpected structure or
            signals a failure status.
    """
    status = str(data.get("status", "")).upper()
    error_code = data.get("error_code")

    if error_code is not None:
        message = str(data.get("text") or error_code)

        if "RATE_LIMIT" in str(error_code).upper():
            raise RateLimitError(message)

        raise ResponseParsingError(
            f"Query processing failed: {message}",
            raw_data=str(data),
        )

    if status == "FAILED":
        raise ResponseParsingError(
            f"Query processing failed: {data.get('text', 'Unknown error')}",
            raw_data=str(data),
        )

    if "blocks" in data:
        if schematized_state is None:
            schematized_state = SchematizedStreamState()
        return _process_schematized_blocks(data, search_results, citation_mode, schematized_state)

    if "text" not in data:
        if schematized_state is not None and (
            data.get("text_completed") or data.get("final_sse_message") or data.get("final")
        ):
            return schematized_state.answer, list(schematized_state.chunks), search_results, {}
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
