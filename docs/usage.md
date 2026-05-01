# Usage Guide

Once you have your `session_token` stored, you can begin automating conversations.

## Quick Start

```python
from perplexity_webui_scraper import Perplexity

client = Perplexity(session_token="YOUR_TOKEN")
conversation = client.create_conversation()

conversation.ask("What is quantum computing?")
print(conversation.answer)

# Follow-up (context is preserved automatically)
conversation.ask("Explain it simpler")
print(conversation.answer)
```

## Streaming Responses

If you do not want to wait for the entire response to generate before acting on it, you can stream chunks to the terminal simply natively:

```python
for chunk in conversation.ask("Explain AI", stream=True):
    if chunk.answer:
        print(chunk.answer, end="\r")
```

## With Configuration Options

You can set global parameters or pass specific configurations for individual routines natively:

```python
from perplexity_webui_scraper import (
    ConversationConfig,
    Coordinates,
)

config = ConversationConfig(
    model="perplexity/best",
    citation_mode="markdown",
    source_focus=["web", "academic"],
    language="en-US",
    coordinates=Coordinates(latitude=12.3456, longitude=-98.7654),
)

conversation = client.create_conversation(config)
conversation.ask("Latest AI research", files=["paper.pdf"])
print(conversation.answer)
```

## File Attachments (`FileInput`)

The `ask()` method accepts files in multiple formats natively via the `FileInput` protocol:

```python
from perplexity_webui_scraper import FileInput  # for type annotations

# 1. Local file path (str or Path)
conversation.ask("Describe this image", files=["photo.jpg"])
conversation.ask("Summarize this", files=[Path("document.pdf")])

# 2. Raw bytes — filename defaults to "file", mimetype to "application/octet-stream"
import requests
image_bytes: bytes = requests.get("https://example.com/image.jpg").content
conversation.ask("What's in this image?", files=[image_bytes])

# 3. Bytes + filename — mimetype is guessed from the filename extension
conversation.ask("Analyze this", files=[(image_bytes, "photo.jpg")])

# 4. Bytes + filename + explicit mimetype — full control
conversation.ask("Read this PDF", files=[(pdf_bytes, "report.pdf", "application/pdf")])

# Mix and match different types in one single call
conversation.ask("Compare these", files=["local.jpg", (remote_bytes, "remote.png")])
```

## Posting to a Perplexity Space

You can route a conversation into a specific [Space](https://www.perplexity.ai/spaces) by passing its UUID via `space_uuid`. The thread will be saved inside that Space automatically.

```python
from perplexity_webui_scraper import ConversationConfig, Perplexity

client = Perplexity(session_token="YOUR_TOKEN")

conversation = client.create_conversation(
    ConversationConfig(
        model="gpt-5.4",
        space_uuid="12345678-1234-1234-1234-123456789abc",  # your Space UUID
    )
)

conversation.ask("Research notes for project X")
print(conversation.answer)
```

> **How to find the Space UUID** — the URL slug (e.g. `questions-abcdef123456`) is **not** the UUID. Obtain it via:
>
> - **Browser DevTools**: make any query inside the Space → Network tab → `perplexity_ask` request → copy `target_collection_uuid` from the JSON payload.
> - **[Complexity browser extension](https://github.com/pnd280/complexity)**: surfaces Space UUIDs directly in the Perplexity UI.

> **Note:** Perplexity accepts up to 30 files per prompt natively in its WebUI logic. Each file has a maximum standard size of 50 MB, however, large text files might block execution natively due to context ceilings. Use appropriately.
