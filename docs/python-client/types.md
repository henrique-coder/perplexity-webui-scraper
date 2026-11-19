# Configuration values

`ConversationConfig` and `ClientConfig` validate their literal string fields when instantiated. Pass the strings directly; no alias imports are needed.

## Citation mode

`citation_mode` accepts `"default"`, `"markdown"`, or `"clean"`:

- `"default"` leaves citation markers such as `[1]` unchanged.
- `"markdown"` converts markers to links when a source URL is available.
- `"clean"` removes citation markers.

## Search focus

`search_focus` accepts `"web"` or `"writing"`:

- `"web"` enables web search and sources.
- `"writing"` generates without search.

## Source focus

`source_focus` accepts one source or a list:

- `"web"`: general web sources.
- `"academic"`: scholarly sources.
- `"social"`: social posts and discussions.
- `"finance"`: financial filings.
- `"all"`: web and academic sources.

## Time range

`time_range` accepts `"all"`, `"day"`, `"week"`, `"month"`, or `"year"`. `"all"` applies no recency filter.

## Research interaction

`research_interaction` accepts `"auto"` or `"manual"`. Automatic mode answers Deep Research clarification questions using reasonable assumptions. Manual mode raises `ResearchClarifyingQuestionsError` to the caller.

## Logging level

`logging_level` accepts `"disabled"`, `"debug"`, `"info"`, `"warning"`, `"error"`, or `"critical"`. The default, `"disabled"`, suppresses library logs.

## Latitude and longitude

Pass `latitude` and `longitude` as separate numeric fields in `ConversationConfig`. Set both or neither.

```python
from perplexity_webui_scraper import ConversationConfig

config = ConversationConfig(latitude=-23.5, longitude=-46.6)
```

Latitude must be between -90 and 90 degrees. Longitude must be between -180 and 180 degrees.

## File inputs

`Conversation.ask(files=...)` accepts local paths, raw bytes, `(bytes, filename)` tuples, and `(bytes, filename, mimetype)` tuples. The runtime validator rejects unsupported tuple shapes, empty content, oversized files, and missing paths. See [file attachments](usage.md#file-attachments) for examples.

`FileInput` is also exported from the top-level `perplexity_webui_scraper` package for annotations. Most callers can pass a list directly without importing it.
