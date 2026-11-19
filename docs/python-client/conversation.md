# Conversation

`Conversation` stores the state for one backend thread. Create it with `client.create_conversation()` and reuse it for follow-up prompts. With `stream=True`, `ask()` returns `self` and yields `Response` snapshots as the stream is parsed.

```python
conversation = client.create_conversation()
conversation.ask("What is quantum entanglement?")
print(conversation.answer)

# Follow-up continues the same backend thread
conversation.ask("Give an everyday analogy.")
print(conversation.answer)
```

## Properties

| Property         | Type                         | Description                                                             |
| ---------------- | ---------------------------- | ----------------------------------------------------------------------- |
| `answer`         | <code>str &#124; None</code> | Most recent final answer text (`None` until a response completes).      |
| `search_results` | `list[SearchResultItem]`     | Web sources cited in the most recent response.                          |
| `activity`       | `list[ActivityEvent]`        | Allowlisted user-visible search activity from the most recent response. |
| `uuid`           | <code>str &#124; None</code> | Backend conversation UUID (`None` before the first query completes).    |

## `Conversation.ask(...)`

Send a query to Perplexity and return `self` for method chaining or streaming iteration.

```python
for snapshot in conversation.ask("Explain TLS 1.3", stream=True):
    print(snapshot.last_chunk or "", end="", flush=True)
```

| Parameter           | Type                                                              | Default | Description                                                                                   |
| ------------------- | ----------------------------------------------------------------- | ------- | --------------------------------------------------------------------------------------------- |
| `query`             | `str`                                                             | —       | Prompt text to send.                                                                          |
| `model`             | <code>str &#124; None</code>                                      | `None`  | Per-query model ID override. Falls back to `ConversationConfig.model` or `"perplexity/best"`. |
| `files`             | <code>list[FileInput] &#124; None</code>                          | `None`  | Optional file or image attachments (requires a paid Perplexity account).                      |
| `citation_mode`     | <code>Literal["default", "markdown", "clean"] &#124; None</code>  | `None`  | Per-query citation format override.                                                           |
| `stream`            | `bool`                                                            | `False` | When `True`, iterate over the returned `Conversation` to consume `Response` snapshots.        |
| `allow_risky_model` | <code>bool &#124; None</code>                                     | `None`  | Per-query acknowledgement for a model whose status is `"unknown"` or `"unavailable"`.         |
| `custom_model_mode` | <code>Literal["copilot", "search", "research"] &#124; None</code> | `None`  | Per-query backend mode override for `custom:<identifier>` models.                             |
