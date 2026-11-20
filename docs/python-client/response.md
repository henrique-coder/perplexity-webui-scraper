# Response models

The Python client exposes response snapshots, cited web sources, and allowlisted search activity records.

## `Response`

Snapshot yielded by `Conversation.ask(..., stream=True)` during SSE streaming.

| Field               | Type                         | Default | Description                                                         |
| ------------------- | ---------------------------- | ------- | ------------------------------------------------------------------- |
| `answer`            | <code>str &#124; None</code> | `None`  | Accumulated answer text formatted according to `citation_mode`.     |
| `chunks`            | `list[str]`                  | `[]`    | Bounded list of incremental text chunks received so far.            |
| `last_chunk`        | <code>str &#124; None</code> | `None`  | Most recently received text chunk.                                  |
| `search_results`    | `list[SearchResultItem]`     | `[]`    | Web sources cited in the response so far.                           |
| `activity`          | `list[ActivityEvent]`        | `[]`    | Allowlisted user-visible search activity events.                    |
| `conversation_uuid` | <code>str &#124; None</code> | `None`  | Backend conversation UUID assigned by Perplexity.                   |
| `raw_data`          | `dict[str, Any]`             | `{}`    | Bounded projection of upstream SSE fields retained for diagnostics. |

## `SearchResultItem`

Frozen Pydantic model representing one cited web source in `Conversation.search_results`, `Response.search_results`, or `ActivityEvent.results`.

| Field     | Type                         | Default | Description                                         |
| --------- | ---------------------------- | ------- | --------------------------------------------------- |
| `url`     | <code>str &#124; None</code> | `None`  | Canonical `http`/`https` source URL.                |
| `title`   | <code>str &#124; None</code> | `None`  | Source page or document title.                      |
| `snippet` | <code>str &#124; None</code> | `None`  | Excerpt or summary snippet associated with the URL. |

## `ActivityEvent`

User-visible search activity item exposed in `Conversation.activity` and `Response.activity`.

| Field     | Type                                  | Default | Description                                    |
| --------- | ------------------------------------- | ------- | ---------------------------------------------- |
| `kind`    | `Literal["search"]`                   | —       | Activity category (`"search"`).                |
| `status`  | `Literal["in_progress", "completed"]` | —       | Current execution state of the search step.    |
| `label`   | `str`                                 | —       | Human-readable activity label.                 |
| `queries` | `list[str]`                           | `[]`    | Search queries executed in this step.          |
| `results` | `list[SearchResultItem]`              | `[]`    | Validated web sources discovered by this step. |
