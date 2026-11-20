"""SSE line parsing and conversation state update logic.

This module handles all data extraction from the Perplexity SSE stream:
parsing raw bytes lines, processing structured JSON data chunks, extracting
clarifying questions, formatting citations, and updating conversation state.

All functions are pure (or near-pure) and operate on plain data structures,
making them independently testable without any HTTP or client machinery.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from ipaddress import ip_address
from typing import TYPE_CHECKING, Any, Literal
from urllib.parse import urlsplit

from orjson import JSONDecodeError, dumps, loads
from pydantic import ValidationError

from perplexity_webui_scraper._internal.constants import (
    CITATION_PATTERN,
    JSON_OBJECT_PATTERN,
)
from perplexity_webui_scraper._internal.exceptions import (
    RateLimitError,
    ResearchClarifyingQuestionsError,
    ResponseParsingError,
)
from perplexity_webui_scraper.core.response import ActivityEvent, SearchResultItem


MAX_SSE_FRAME_BYTES = 2 * 1024 * 1024
MAX_RAW_DATA_BYTES = 64 * 1024
MAX_WORKFLOW_STATE_BYTES = 4 * 1024 * 1024
MAX_ANSWER_BYTES = 1024 * 1024


if TYPE_CHECKING:
    from collections.abc import Iterable
    from re import Match


@dataclass
class SchematizedStreamState:
    """Mutable state needed to apply schematized WebUI stream updates."""

    workflow_block: dict[str, Any] | None = None
    answer: str | None = None
    chunks: list[str] = field(default_factory=list)
    markdown_chunks: list[str] = field(default_factory=list)
    activity: dict[str, ActivityEvent] = field(default_factory=dict)
    search_results: list[SearchResultItem] = field(default_factory=list)
    citation_results: list[SearchResultItem] = field(default_factory=list)


def _json_pointer_tokens(path: str) -> list[str]:
    """Decode an RFC 6901 JSON Pointer path."""
    if path == "":
        return []

    if not path.startswith("/"):
        raise ValueError(f"Invalid JSON Patch path: {path!r}")

    return [part.replace("~1", "/").replace("~0", "~") for part in path[1:].split("/")]


def _apply_list_patch(target: list[Any], op: Any, key: str, value: Any) -> None:
    """Apply an ``add``, ``replace``, or ``remove`` JSON Patch operation to a list."""
    if op == "add":
        if key == "-":
            target.append(value)
        else:
            target.insert(int(key), value)

        return

    if op == "replace":
        target[int(key)] = value

        return

    if op == "remove":
        target.pop(int(key))

        return

    raise ResponseParsingError("Unsupported JSON Patch operation") from None


def _apply_dict_patch(target: dict[str, Any], op: Any, key: str, value: Any) -> None:
    """Apply an ``add``, ``replace``, or ``remove`` JSON Patch operation to a mapping."""
    if op in {"add", "replace"}:
        if op == "replace" and key not in target:
            raise ResponseParsingError("JSON Patch replace target does not exist") from None

        target[key] = value

        return

    if op == "remove":
        target.pop(key, None)

        return

    raise ResponseParsingError("Unsupported JSON Patch operation") from None


def _apply_json_patch(document: Any, operation: dict[str, Any]) -> None:
    """Apply the JSON Patch subset emitted by the WebUI.

    Perplexity currently emits ``add``, ``replace`` and ``remove`` operations
    against object fields and list indexes.  Keeping this small implementation
    private avoids adding a dependency for a wire-format detail.
    """
    op = operation.get("op")
    path = operation.get("path", "")

    if not isinstance(path, str) or len(path) > 2048:
        raise ResponseParsingError("JSON Patch path exceeds the maximum allowed size") from None

    tokens = _json_pointer_tokens(path)

    if not tokens:
        raise ResponseParsingError("Root JSON Patch operations are not supported") from None

    target = document

    for token in tokens[:-1]:
        target = target[int(token)] if isinstance(target, list) else target[token]

    key = tokens[-1]

    if isinstance(target, list):
        _apply_list_patch(target, op, key, operation.get("value"))
        return

    if not isinstance(target, dict):
        raise ResponseParsingError("JSON Patch target must be an object or list") from None

    _apply_dict_patch(target, op, key, operation.get("value"))


def _apply_workflow_block(
    state: SchematizedStreamState,
    workflow_block: dict[str, Any],
    search_results: list[SearchResultItem],
    raw_data: dict[str, Any],
) -> None:
    """Store and project an incoming ``workflow_block`` event."""
    state.workflow_block = workflow_block
    _check_workflow_state_size(state)
    _update_activity(state, workflow_block, search_results)
    raw_data["workflow_block"] = _bounded_raw_value(workflow_block)


def _apply_diff_block(
    state: SchematizedStreamState,
    diff_block: dict[str, Any],
    search_results: list[SearchResultItem],
    raw_data: dict[str, Any],
) -> None:
    """Validate and apply JSON Patch updates to ``state.workflow_block``."""
    workflow_block = state.workflow_block

    if workflow_block is None:
        return

    patches = diff_block.get("patches", [])

    if not isinstance(patches, list):
        state.workflow_block = None
        raise ResponseParsingError("SSE diff patches field must be a list.") from None

    if len(patches) > 100:
        state.workflow_block = None
        raise ResponseParsingError("SSE diff contains more than 100 patch operations.") from None

    try:
        for patch in patches:
            if isinstance(patch, dict):
                _apply_json_patch(workflow_block, patch)
    except (ValueError, TypeError, IndexError, KeyError):
        state.workflow_block = None
        raise ResponseParsingError("Malformed SSE diff patch.") from None

    _check_workflow_state_size(state)
    _update_activity(state, workflow_block, search_results)
    raw_data["diff_block"] = _bounded_raw_value(diff_block)


def _apply_web_result_block(
    state: SchematizedStreamState,
    web_result_block: dict[str, Any],
    search_results: list[SearchResultItem],
    raw_data: dict[str, Any],
) -> list[SearchResultItem]:
    """Validate and merge incoming web search results into stream state."""
    if not isinstance(web_result_block.get("web_results"), list):
        raise ResponseParsingError("Web result block must contain a list.") from None

    updated_results = _extract_web_results(web_result_block)

    if updated_results is not None:
        search_results = updated_results
        state.citation_results = _citation_results(updated_results)
        state.search_results = _merge_search_results(state.search_results, updated_results)[:50]

    _update_activity(state, state.workflow_block, state.search_results or search_results)

    if state.activity.get("search_web") is not None:
        event = state.activity["search_web"]
        state.activity["search_web"] = ActivityEvent(
            kind=event.kind,
            status=event.status,
            label=event.label,
            queries=event.queries,
            results=_validated_search_results([*state.search_results, *event.results])[:50],
        )

    raw_data["web_result_block"] = _bounded_raw_value(web_result_block)

    return search_results


def _apply_schematized_block(
    state: SchematizedStreamState,
    block: dict[str, Any],
    citation_mode: Literal["default", "markdown", "clean"],
    search_results: list[SearchResultItem],
    raw_data: dict[str, Any],
) -> list[SearchResultItem]:
    """Dispatch one schematized SSE block to its handler."""
    workflow_block = block.get("workflow_block")

    if isinstance(workflow_block, dict):
        _apply_workflow_block(state, workflow_block, search_results, raw_data)

    diff_block = block.get("diff_block")

    if isinstance(diff_block, dict):
        _apply_diff_block(state, diff_block, search_results, raw_data)

    markdown_block = block.get("markdown_block")

    if isinstance(markdown_block, dict):
        citation_sources = state.citation_results or _citation_results(search_results)
        _process_markdown_block(markdown_block, citation_mode, citation_sources, state)
        raw_data["markdown_block"] = _bounded_raw_value(markdown_block)

    web_result_block = block.get("web_result_block")

    if isinstance(web_result_block, dict):
        search_results = _apply_web_result_block(state, web_result_block, search_results, raw_data)

    return search_results


def _finalize_schematized_blocks(
    data: dict[str, Any],
    citation_mode: Literal["default", "markdown", "clean"],
    search_results: list[SearchResultItem],
    state: SchematizedStreamState,
    raw_data: dict[str, Any],
) -> tuple[str | None, list[str], list[SearchResultItem], dict[str, Any]]:
    """Project final workflow text and completion flags after applying blocks."""
    citation_sources = state.citation_results or _citation_results(search_results)

    if state.workflow_block is not None:
        raw_data["workflow_block"] = _bounded_raw_value(state.workflow_block)
        extracted = _extract_workflow_text(state.workflow_block, citation_mode, citation_sources)

        if extracted is not None:
            state.answer, state.chunks, _ = extracted

    is_final = any(data.get(key) for key in ("text_completed", "final_sse_message", "final"))

    if is_final:
        state.activity = _complete_activity(state.activity)

        if state.answer is None and state.markdown_chunks:
            state.answer = format_citations("".join(state.markdown_chunks), citation_mode, citation_sources)

    return (state.answer if is_final else None), list(state.chunks), search_results, raw_data


def _process_schematized_blocks(
    data: dict[str, Any],
    search_results: list[SearchResultItem],
    citation_mode: Literal["default", "markdown", "clean"],
    state: SchematizedStreamState,
) -> tuple[str | None, list[str], list[SearchResultItem], dict[str, Any]]:
    """Process the ``workflow_block``/``diff_block`` stream format."""
    raw_blocks = data.get("blocks", [])
    raw_data: dict[str, Any] = {}

    if not isinstance(raw_blocks, list):
        raise ResponseParsingError("SSE blocks field must be a list.") from None

    if len(raw_blocks) > 100:
        raise ResponseParsingError("SSE event contains more than 100 blocks.") from None

    for block in raw_blocks:
        if isinstance(block, dict):
            search_results = _apply_schematized_block(state, block, citation_mode, search_results, raw_data)

    return _finalize_schematized_blocks(data, citation_mode, search_results, state, raw_data)


def _iter_search_web_items(steps: Any, item_type: str) -> Iterable[dict[str, Any]]:
    """Yield allowlisted workflow items matching *item_type* under ``search_web`` steps."""
    if not isinstance(steps, list):
        return

    for step in steps[:100]:
        if not isinstance(step, dict) or step.get("tool_name") != "search_web":
            continue

        raw_items = step.get("items", [])

        if not isinstance(raw_items, list):
            continue

        for item in raw_items[:100]:
            if isinstance(item, dict) and item.get("type") == item_type:
                yield item


def _extract_activity_queries(steps: Any) -> tuple[bool, list[str]]:
    """Extract query strings from ``WORKFLOW_ITEM_QUERIES`` steps."""
    query_evidence = False
    queries: list[str] = []

    for item in _iter_search_web_items(steps, "WORKFLOW_ITEM_QUERIES"):
        payload = item.get("payload")
        queries_payload = payload.get("queries_payload") if isinstance(payload, dict) else None
        raw_queries = queries_payload.get("queries") if isinstance(queries_payload, dict) else None

        if not isinstance(raw_queries, list):
            continue

        query_evidence = True

        for query in raw_queries[:20]:
            safe_query = _safe_activity_text(query)

            if safe_query is not None and safe_query not in queries and len(queries) < 20:
                queries.append(safe_query)

    return query_evidence, queries


def _extract_activity_sources(steps: Any) -> list[SearchResultItem]:
    """Extract raw source records from ``WORKFLOW_ITEM_SOURCES`` steps."""
    source_results: list[SearchResultItem] = []

    for item in _iter_search_web_items(steps, "WORKFLOW_ITEM_SOURCES"):
        payload = item.get("payload")
        sources_payload = payload.get("sources_payload") if isinstance(payload, dict) else None
        raw_sources = sources_payload.get("sources") if isinstance(sources_payload, dict) else None

        if not isinstance(raw_sources, list):
            continue

        for source in raw_sources[:50]:
            if not isinstance(source, dict):
                continue

            url = source.get("url")
            title = source.get("name")
            snippet = source.get("snippet")

            if isinstance(url, str) and isinstance(title, str) and isinstance(snippet, str):
                source_results.append(SearchResultItem(url=url, title=title, snippet=snippet))

    return source_results


def _merge_unique_queries(existing_queries: list[str], new_queries: list[str], limit: int = 20) -> list[str]:
    """Preserve query order while deduplicating and capping at *limit*."""
    combined_queries: list[str] = []

    for query in [*existing_queries, *new_queries]:
        if query not in combined_queries:
            combined_queries.append(query)

        if len(combined_queries) == limit:
            break

    return combined_queries


def _update_activity(
    state: SchematizedStreamState,
    workflow_block: dict[str, Any] | None,
    search_results: list[SearchResultItem],
) -> None:
    """Project allowlisted public search workflow fields into typed activity."""
    if not isinstance(workflow_block, dict):
        return

    steps = workflow_block.get("steps", [])
    query_evidence, queries = _extract_activity_queries(steps)

    if not query_evidence:
        return

    source_results = _extract_activity_sources(steps)
    results = _validated_search_results([*search_results, *source_results])[:50]
    status: Literal["in_progress", "completed"] = (
        "completed" if workflow_block.get("status") == "WORKFLOW_COMPLETED" else "in_progress"
    )
    existing = state.activity.get("search_web")
    combined_queries = _merge_unique_queries(existing.queries if existing else [], queries)

    state.activity["search_web"] = ActivityEvent(
        kind="search",
        status=status,
        label="Searching the web",
        queries=combined_queries,
        results=results,
    )


def _safe_activity_text(value: Any, max_length: int = 512) -> str | None:
    """Bound and reject control characters in user-visible query summaries."""
    if not isinstance(value, str):
        return None

    text = value.strip()

    if (
        not text
        or len(text) > max_length
        or any(ord(character) < 32 and character not in "\t\n\r" for character in text)
    ):
        return None

    return text


def _is_public_hostname(raw_hostname: str) -> bool:
    """Return whether *raw_hostname* is a routable non-local public host."""
    hostname = raw_hostname.lower().rstrip(".")

    if not hostname or hostname == "localhost" or hostname.endswith((".localhost", ".local")):
        return False

    try:
        return ip_address(hostname).is_global
    except ValueError:
        return True


def _normalize_public_https_url(url: Any) -> str | None:
    """Return a canonical fragment-free HTTPS URL for public hosts, or ``None``."""
    if not isinstance(url, str) or len(url) > 2048:
        return None

    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        return None

    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or (port is not None and not 1 <= port <= 65535)
        or not _is_public_hostname(parsed.hostname)
    ):
        return None

    return url.split("#", 1)[0]


def _upsert_search_result(
    results: list[SearchResultItem],
    seen_urls: set[str],
    canonical_url: str,
    item: SearchResultItem,
) -> None:
    """Update an existing URL entry in place or append a new bounded entry."""
    if canonical_url in seen_urls:
        for index, existing in enumerate(results):
            if existing.url == canonical_url:
                results[index] = item
                break

        return

    seen_urls.add(canonical_url)
    results.append(item)


def _citation_results(search_results: list[SearchResultItem]) -> list[SearchResultItem]:
    """Preserve 1-based source indices for citations without exposing unsafe URLs."""
    return [SearchResultItem(url=_normalize_public_https_url(result.url)) for result in search_results[:50]]


def _validated_search_results(search_results: list[SearchResultItem]) -> list[SearchResultItem]:
    """Return a bounded list of public HTTPS source metadata without private payloads."""
    results: list[SearchResultItem] = []
    seen_urls: set[str] = set()

    for result in search_results:
        canonical_url = _normalize_public_https_url(result.url)
        title = _safe_activity_text(result.title)
        snippet = _safe_activity_text(result.snippet, max_length=2048)

        if canonical_url is None or title is None or snippet is None:
            continue

        _upsert_search_result(
            results,
            seen_urls,
            canonical_url,
            SearchResultItem(url=canonical_url, title=title, snippet=snippet),
        )

        if len(results) == 50:
            break

    return results


def _merge_search_results(
    current_results: list[SearchResultItem],
    updated_results: list[SearchResultItem],
) -> list[SearchResultItem]:
    """Merge newly observed results into the current conversation's source list."""
    result_by_url = {result.url: result for result in current_results if result.url}

    for result in updated_results:
        if result.url:
            result_by_url[result.url] = result

    return list(result_by_url.values())


def _complete_activity(activity: dict[str, ActivityEvent]) -> dict[str, ActivityEvent]:
    """Return completed copies of events without mutating earlier snapshots."""
    return {
        key: ActivityEvent(
            kind=event.kind,
            status="completed",
            label=event.label,
            queries=event.queries,
            results=list(event.results),
        )
        for key, event in activity.items()
    }


def _bounded_raw_value(value: dict[str, Any]) -> dict[str, Any]:
    """Keep bounded raw diagnostics without retaining full upstream blocks."""
    serialized = dumps(value)

    if len(serialized) <= MAX_RAW_DATA_BYTES:
        return loads(serialized)

    return {"truncated": True, "original_size_bytes": len(serialized)}


def _check_workflow_state_size(state: SchematizedStreamState) -> None:
    """Prevent incremental JSON patches from growing retained workflow state without bound."""
    if state.workflow_block is None:
        return

    try:
        oversized = len(dumps(state.workflow_block)) > MAX_WORKFLOW_STATE_BYTES
    except TypeError:
        oversized = True

    if oversized:
        state.workflow_block = None
        raise ResponseParsingError("Workflow state exceeds the 4 MiB maximum allowed size.") from None


def _prefer_longer_text(text: str | None, chunks: list[str]) -> str | None:
    """Prefer the accumulated chunks when the stream's text field lags."""
    joined_chunks = "".join(chunks[:100])[:MAX_ANSWER_BYTES]

    if joined_chunks and (text is None or len(joined_chunks) > len(text)):
        return joined_chunks[:MAX_ANSWER_BYTES]

    return text[:MAX_ANSWER_BYTES] if text is not None else None


def _process_markdown_block(
    markdown_block: dict[str, Any],
    citation_mode: Literal["default", "markdown", "clean"],
    search_results: list[SearchResultItem],
    state: SchematizedStreamState,
) -> None:
    """Merge an incremental markdown block into the stream state."""
    raw_chunks = markdown_block.get("chunks")

    if isinstance(raw_chunks, list):
        offset = markdown_block.get("chunk_starting_offset", 0)

        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            offset = 0

        if offset == 0:
            state.markdown_chunks = []

        if offset > 100 or offset + len(raw_chunks) > 100:
            raise ResponseParsingError("Markdown chunk index exceeds the 100-chunk maximum.") from None

        while len(state.markdown_chunks) < offset:
            state.markdown_chunks.append("")

        for index, chunk in enumerate(raw_chunks[:100]):
            value = str(chunk)[:65_536] if chunk is not None else ""
            target = offset + index

            if target == len(state.markdown_chunks):
                state.markdown_chunks.append(value)
            elif target < len(state.markdown_chunks):
                state.markdown_chunks[target] = value
            else:
                if target > 100:
                    raise ResponseParsingError("Markdown chunk index exceeds the 100-chunk maximum.") from None

                state.markdown_chunks.extend([""] * (target - len(state.markdown_chunks)))
                state.markdown_chunks.append(value)

    state.chunks = [
        format_citations(chunk, citation_mode, search_results) or "" for chunk in state.markdown_chunks[:100]
    ]

    answer = markdown_block.get("answer")
    answer_text = answer[:1_048_576] if isinstance(answer, str) and answer else None
    answer_text = _prefer_longer_text(answer_text, state.markdown_chunks)

    if answer_text is not None:
        state.answer = format_citations(answer_text, citation_mode, search_results)


def _extract_web_results(web_result_block: dict[str, Any]) -> list[SearchResultItem] | None:
    """Convert schematized web results to the public search-result model."""
    raw_results = web_result_block.get("web_results")

    if not isinstance(raw_results, list):
        return None

    return [
        SearchResultItem(
            title=result.get("name") if isinstance(result.get("name"), str) else None,
            snippet=result.get("snippet") if isinstance(result.get("snippet"), str) else None,
            url=result.get("url") if isinstance(result.get("url"), str) else None,
        )
        for result in raw_results[:50]
        if isinstance(result, dict)
    ]


def _extract_workflow_text(
    workflow_block: dict[str, Any],
    citation_mode: Literal["default", "markdown", "clean"],
    search_results: list[SearchResultItem],
) -> tuple[str | None, list[str], list[SearchResultItem]] | None:
    """Extract answer text and chunks from a schematized workflow block."""
    steps = workflow_block.get("steps", [])

    for step in steps[:100] if isinstance(steps, list) else []:
        if not isinstance(step, dict):
            continue

        items = step.get("items", [])

        for item in items[:100] if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue

            payload = item.get("payload", {})
            text_payload = payload.get("text_payload", {}) if isinstance(payload, dict) else {}

            if not isinstance(text_payload, dict):
                continue

            if item.get("type") not in {None, "WORKFLOW_ITEM_TEXT"} or text_payload.get("variant") not in {
                None,
                "answer",
            }:
                continue

            raw_chunks = text_payload.get("chunks", [])
            chunks = (
                [str(chunk)[:65_536] for chunk in raw_chunks[:100] if chunk is not None]
                if isinstance(raw_chunks, list)
                else []
            )
            text = text_payload.get("text")
            answer_text = text[:1_048_576] if isinstance(text, str) and text else None
            answer_text = _prefer_longer_text(answer_text, chunks)
            answer = format_citations(answer_text, citation_mode, search_results)

            if chunks:
                chunks = [format_citations(chunk, citation_mode, search_results) or "" for chunk in chunks]

            if answer is not None or chunks:
                return answer, chunks, search_results

    return None


def _parse_sse_payload(payload: bytes | str) -> dict[str, Any]:
    """Decode a bounded SSE JSON payload and require a JSON object."""
    if not payload:
        raise ResponseParsingError("SSE data frame is empty.")

    parsed: Any = None
    malformed = False

    try:
        parsed = loads(payload)
    except JSONDecodeError:
        malformed = True

    if malformed:
        raise ResponseParsingError("SSE frame contains malformed JSON.")

    if not isinstance(parsed, dict):
        raise ResponseParsingError("SSE data frame must be a JSON object.")

    return parsed


def parse_sse_line(line: str | bytes) -> dict[str, Any] | None:
    """Parse a single SSE data line into a dict.

    SSE lines follow the format ``data: <json-payload>``.  Any line that does
    not start with this prefix is silently ignored.  The optional space after
    the colon is accepted because both variants occur in browser streams.

    Args:
        line: A raw SSE line as bytes or a string.

    Returns:
        Deserialized JSON dict, or ``None`` if the line is not a data line.

    Raises:
        ResponseParsingError: If the payload exceeds the frame size limit, is
            malformed JSON, or does not decode to a JSON object.
    """
    if isinstance(line, bytes):
        if line.startswith(b"data:"):
            payload = line[5:].lstrip()

            if payload == b"[DONE]":
                return None

            if len(payload) > MAX_SSE_FRAME_BYTES:
                raise ResponseParsingError("SSE frame exceeds the 2 MiB maximum allowed size.") from None

            return _parse_sse_payload(payload)
    elif line.startswith("data:"):
        payload = line[5:].lstrip()

        if payload == "[DONE]":
            return None

        if len(payload) > MAX_SSE_FRAME_BYTES or len(payload.encode("utf-8")) > MAX_SSE_FRAME_BYTES:
            raise ResponseParsingError("SSE frame exceeds the 2 MiB maximum allowed size.") from None

        return _parse_sse_payload(payload)

    return None


def process_sse_data(
    data: dict[str, Any],
    search_results: list[SearchResultItem],
    citation_mode: Literal["default", "markdown", "clean"],
    schematized_state: SchematizedStreamState | None = None,
) -> tuple[str | None, list[str], list[SearchResultItem], dict[str, Any]]:
    """Process a single SSE data chunk and extract state updates.

    Handles both the schematized block format (``blocks`` key) and the
    plain text format (``text`` key).  Recognizes ``FINAL`` and
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
    if not isinstance(data, dict):
        raise ResponseParsingError("SSE data payload must be a JSON object.")

    status = str(data.get("status", "")).upper()
    error_code = data.get("error_code")

    if error_code is not None:
        error_text = str(error_code)[:80]
        if "RATE_LIMIT" in error_text.upper():
            raise RateLimitError(error_text) from None

        raise ResponseParsingError("Query processing failed.") from None

    if status == "FAILED":
        raise ResponseParsingError(f"Query processing failed with status {status}.") from None

    if "blocks" in data:
        if schematized_state is None:
            schematized_state = SchematizedStreamState()

        try:
            return _process_schematized_blocks(data, search_results, citation_mode, schematized_state)
        except (ValueError, TypeError, IndexError, KeyError, ValidationError):
            raise ResponseParsingError("Malformed schematized SSE event.") from None

    if "text" not in data:
        if schematized_state is not None and (
            data.get("text_completed") or data.get("final_sse_message") or data.get("final")
        ):
            schematized_state.activity = _complete_activity(schematized_state.activity)
            return schematized_state.answer, list(schematized_state.chunks), search_results, {}

        return None, [], search_results, {}

    try:
        json_data = loads(data["text"])
    except JSONDecodeError:
        json_data = dict(data)
        text = data.get("text")
        json_data["answer"] = text[:1_048_576] if isinstance(text, str) else text

    if isinstance(json_data, list):
        return _process_block_list(json_data, search_results, citation_mode)

    if isinstance(json_data, dict):
        updated_results, answer, chunks, raw = _extract_state(json_data, search_results, citation_mode)

        return answer, chunks, updated_results, raw

    raise ResponseParsingError("Unexpected JSON structure in 'text' field") from None


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
    citation_mode: Literal["default", "markdown", "clean"],
    search_results: list[SearchResultItem],
) -> str | None:
    """Format citation markers using the requested citation mode."""
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
    citation_mode: Literal["default", "markdown", "clean"],
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
    if len(block_list) > 100:
        raise ResponseParsingError("SSE block list contains more than 100 items.") from None

    for item in block_list:
        if not isinstance(item, dict):
            continue

        step_type = item.get("step_type")

        if step_type == "RESEARCH_CLARIFYING_QUESTIONS":
            questions = extract_clarifying_questions(item)

            if len(questions) > 20:
                questions = questions[:20]

            raise ResearchClarifyingQuestionsError(questions)

        if step_type == "FINAL":
            raw_content = item.get("content", {})

            if not isinstance(raw_content, dict):
                raise ResponseParsingError("Final answer content must be an object.") from None

            answer_content = raw_content.get("answer")

            answer_data: dict[str, Any]

            if isinstance(answer_content, str) and JSON_OBJECT_PATTERN.match(answer_content):
                if len(answer_content) > MAX_SSE_FRAME_BYTES:
                    raise ResponseParsingError("Final answer JSON exceeds the 2 MiB maximum allowed size.") from None
                try:
                    answer_data = loads(answer_content)
                except JSONDecodeError:
                    raise ResponseParsingError("Final answer JSON is malformed.") from None
                if not isinstance(answer_data, dict):
                    raise ResponseParsingError("Final answer JSON must be an object.") from None
            else:
                answer_data = raw_content

            updated, answer, chunks, raw = _extract_state(answer_data, search_results, citation_mode)

            return answer, chunks, updated, raw

    return None, [], search_results, {}


def _extract_state(
    answer_data: dict[str, Any],
    current_results: list[SearchResultItem],
    citation_mode: Literal["default", "markdown", "clean"],
) -> tuple[list[SearchResultItem], str | None, list[str], dict[str, Any]]:
    """Extract answer, chunks, and search results from a parsed answer dict.

    Args:
        answer_data: The dict containing ``answer``, ``chunks``, ``web_results``.
        current_results: Previous search results (used if none in this chunk).
        citation_mode: Citation rendering mode.

    Returns:
        4-tuple of ``(search_results, answer, chunks, raw_data)``.
    """
    web_results = answer_data.get("web_results", [])
    updated_results = current_results
    citation_sources = _citation_results(current_results)

    if web_results:
        if not isinstance(web_results, list):
            raise ResponseParsingError("Web results must be a list.") from None

        raw_results = [
            SearchResultItem(
                title=r.get("name") if isinstance(r.get("name"), str) else None,
                snippet=r.get("snippet") if isinstance(r.get("snippet"), str) else None,
                url=r.get("url") if isinstance(r.get("url"), str) else None,
            )
            for r in web_results[:50]
            if isinstance(r, dict)
        ]
        updated_results = _validated_search_results(raw_results)
        citation_sources = _citation_results(raw_results)

    raw_answer = answer_data.get("answer")
    answer_text: str | None = raw_answer if isinstance(raw_answer, str) else None

    if raw_answer is not None and answer_text is None:
        raise ResponseParsingError("Answer must be text.") from None

    if answer_text is not None:
        answer_text = answer_text[:MAX_ANSWER_BYTES]

    formatted_answer = format_citations(answer_text, citation_mode, citation_sources)

    raw_chunks: list[Any] = answer_data.get("chunks", [])
    formatted_chunks: list[str] = []

    if raw_chunks:
        if not isinstance(raw_chunks, list):
            raise ResponseParsingError("Answer chunks must be a list.") from None

        formatted_chunks = [
            format_citations(str(chunk)[:65_536], citation_mode, citation_sources) or ""
            for chunk in raw_chunks[:100]
            if chunk is not None
        ]

    bounded_raw = _bounded_answer_projection(answer_data)

    return updated_results, formatted_answer, formatted_chunks, bounded_raw


def _bounded_answer_projection(answer_data: dict[str, Any]) -> dict[str, Any]:
    """Bound public answer/chunk/source projections while retaining final text."""
    projected = dict(answer_data)
    answer = projected.get("answer")

    if isinstance(answer, str):
        projected["answer"] = answer[:MAX_ANSWER_BYTES]
    elif answer is not None:
        raise ResponseParsingError("Answer must be text.") from None

    chunks = projected.get("chunks", [])

    if not isinstance(chunks, list):
        raise ResponseParsingError("Answer chunks must be a list.") from None

    projected["chunks"] = [str(chunk)[:65_536] for chunk in chunks[:100] if chunk is not None]

    web_results = projected.get("web_results", [])

    if not isinstance(web_results, list):
        raise ResponseParsingError("Web results must be a list.") from None

    projected["web_results"] = web_results[:50]
    serialized = dumps(projected)

    if len(serialized) > MAX_RAW_DATA_BYTES:
        return {
            "answer": projected.get("answer", ""),
            "raw_data_truncated": True,
            "original_size_bytes": len(serialized),
        }

    return projected
