# Usage Guide

Create a client with your stored `session_token` to start a conversation.

## Quick Start

```python
from perplexity_webui_scraper import Perplexity

client = Perplexity(session_token="YOUR_TOKEN")
conversation = client.create_conversation()

conversation.ask("What is quantum computing?")
print(conversation.answer)

# Continue the same conversation
conversation.ask("Explain it simpler")
print(conversation.answer)
```

## Streaming Responses

Set `stream=True` and read `last_chunk` as each parsed chunk arrives:

```python
for chunk in conversation.ask("Explain AI", stream=True):
    if chunk.last_chunk:
        print(chunk.last_chunk, end="", flush=True)
```

## With Configuration Options

Pass a `ConversationConfig` when creating a conversation:

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

File attachments require a paid Perplexity account. Free accounts can use text prompts, but file uploads are blocked before any upload request is attempted.

The `ask()` method accepts the forms covered by the `FileInput` type:

```python
from pathlib import Path

from curl_cffi.requests import get
from perplexity_webui_scraper import FileInput  # for type annotations

# 1. Local file path (str or Path)
conversation.ask("Describe this image", files=["photo.jpg"])
conversation.ask("Summarize this", files=[Path("document.pdf")])

# 2. Raw bytes; filename defaults to "file" and MIME type to "application/octet-stream"
image_bytes: bytes = get("https://example.com/image.jpg").content
conversation.ask("What's in this image?", files=[image_bytes])

# 3. Bytes and filename; MIME type is guessed from the extension
conversation.ask("Analyze this", files=[(image_bytes, "photo.jpg")])

# 4. Bytes, filename, and explicit MIME type
pdf_bytes = Path("report.pdf").read_bytes()
conversation.ask("Read this PDF", files=[(pdf_bytes, "report.pdf", "application/pdf")])

# Combine forms in one call
conversation.ask("Compare these", files=["local.jpg", (image_bytes, "remote.png")])
```

## Posting to a Perplexity Space

Pass a [Space](https://www.perplexity.ai/spaces) UUID through `space_uuid` to store the thread in that Space.

```python
from perplexity_webui_scraper import ConversationConfig, Perplexity

client = Perplexity(session_token="YOUR_TOKEN")

conversation = client.create_conversation(
    ConversationConfig(
        model="openai/gpt-5.6-terra",
        space_uuid="12345678-1234-1234-1234-123456789abc",  # your Space UUID
    )
)

conversation.ask("Research notes for project X")
print(conversation.answer)
```

The URL slug, such as `questions-abcdef123456`, is not the Space UUID. To find the UUID, submit a query inside the Space, inspect the `perplexity_ask` request in the browser Network panel, and copy `target_collection_uuid` from its JSON payload.

The client accepts at most 30 files per prompt and rejects files larger than 50 MB before upload.
