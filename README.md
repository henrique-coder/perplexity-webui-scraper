<div align="center">

# Perplexity WebUI Scraper

Python scraper to extract AI responses from [Perplexity's](https://www.perplexity.ai) web interface.

[![PyPI](https://img.shields.io/pypi/v/perplexity-webui-scraper?color=blue)](https://pypi.org/project/perplexity-webui-scraper)
[![Python](https://img.shields.io/pypi/pyversions/perplexity-webui-scraper)](https://pypi.org/project/perplexity-webui-scraper)
[![License](https://img.shields.io/github/license/henrique-coder/perplexity-webui-scraper?color=green)](./LICENSE)

</div>

---

## Installation

```bash
uv pip install perplexity-webui-scraper  # from PyPI (stable)
uv pip install git+https://github.com/henrique-coder/perplexity-webui-scraper.git@dev  # from GitHub (development)
```

## Requirements

- **Perplexity Pro/Max account**
- **Session token** (`__Secure-next-auth.session-token` cookie from your browser)

### Getting Your Session Token

You can obtain your session token in two ways:

#### Option 1: Automatic (CLI Tool)

The package includes a CLI tool to automatically generate and save your session token:

```bash
get-perplexity-session-token
```

This interactive tool will:

1. Ask for your Perplexity email
2. Send a verification code to your email
3. Accept either a 6-digit code or magic link
4. Extract and display your session token
5. Optionally save it to your `.env` file

**Features:**

- Secure ephemeral session (cleared on exit)
- Automatic `.env` file management
- Support for both OTP codes and magic links
- Clean terminal interface with status updates

#### Option 2: Manual (Browser)

If you prefer to extract the token manually:

1. Log in at [perplexity.ai](https://www.perplexity.ai)
2. Open DevTools (`F12`) → Application/Storage → Cookies
3. Copy the value of `__Secure-next-auth.session-token`
4. Store in `.env`: `PERPLEXITY_SESSION_TOKEN="your_token"`

## Quick Start

```python
from perplexity_webui_scraper import Perplexity

client = Perplexity(session_token="YOUR_TOKEN")
conversation = client.create_conversation()

conversation.ask("What is quantum computing?")
print(conversation.answer)

# Follow-up
conversation.ask("Explain it simpler")
print(conversation.answer)
```

### Streaming

```python
for chunk in conversation.ask("Explain AI", stream=True):
    print(chunk.answer)
```

### With Options

```python
from perplexity_webui_scraper import (
    ConversationConfig,
    Coordinates,
    Models,
    SourceFocus,
)

config = ConversationConfig(
    model=Models.RESEARCH,
    source_focus=[SourceFocus.WEB, SourceFocus.ACADEMIC],
    language="en-US",
    coordinates=Coordinates(latitude=40.7128, longitude=-74.0060),
)

conversation = client.create_conversation(config)
conversation.ask("Latest AI research", files=["paper.pdf"])
```

## API

### `Perplexity(session_token, config?)`

| Parameter       | Type           | Description        |
| --------------- | -------------- | ------------------ |
| `session_token` | `str`          | Browser cookie     |
| `config`        | `ClientConfig` | Timeout, TLS, etc. |

### `Conversation.ask(query, model?, files?, citation_mode?, stream?)`

| Parameter       | Type                    | Default       | Description         |
| --------------- | ----------------------- | ------------- | ------------------- |
| `query`         | `str`                   | -             | Question (required) |
| `model`         | `Model`                 | `Models.BEST` | AI model            |
| `files`         | `list[str \| PathLike]` | `None`        | File paths          |
| `citation_mode` | `CitationMode`          | `CLEAN`       | Citation format     |
| `stream`        | `bool`                  | `False`       | Enable streaming    |

### Models

| Model                              | Description                                                               |
| ---------------------------------- | ------------------------------------------------------------------------- |
| `Models.RESEARCH`                  | Research - Fast and thorough for routine research                         |
| `Models.LABS`                      | Labs - Multi-step tasks with advanced troubleshooting                     |
| `Models.BEST`                      | Best - Automatically selects the most responsive model based on the query |
| `Models.SONAR`                     | Sonar - Perplexity's fast model                                           |
| `Models.GPT_52`                    | GPT-5.2 - OpenAI's latest model                                           |
| `Models.GPT_52_THINKING`           | GPT-5.2 Thinking - OpenAI's latest model with thinking                    |
| `Models.CLAUDE_45_OPUS`            | Claude Opus 4.5 - Anthropic's Opus reasoning model                        |
| `Models.CLAUDE_45_OPUS_THINKING`   | Claude Opus 4.5 Thinking - Anthropic's Opus reasoning model with thinking |
| `Models.GEMINI_3_PRO`              | Gemini 3 Pro - Google's newest reasoning model                            |
| `Models.GEMINI_3_FLASH`            | Gemini 3 Flash - Google's fast reasoning model                            |
| `Models.GEMINI_3_FLASH_THINKING`   | Gemini 3 Flash Thinking - Google's fast reasoning model with thinking     |
| `Models.GROK_41`                   | Grok 4.1 - xAI's latest advanced model                                    |
| `Models.GROK_41_THINKING`          | Grok 4.1 Thinking - xAI's latest reasoning model                          |
| `Models.KIMI_K2_THINKING`          | Kimi K2 Thinking - Moonshot AI's latest reasoning model                   |
| `Models.CLAUDE_45_SONNET`          | Claude Sonnet 4.5 - Anthropic's newest advanced model                     |
| `Models.CLAUDE_45_SONNET_THINKING` | Claude Sonnet 4.5 Thinking - Anthropic's newest reasoning model           |

### CitationMode

| Mode       | Output                |
| ---------- | --------------------- |
| `DEFAULT`  | `text[1]`             |
| `MARKDOWN` | `text[1](url)`        |
| `CLEAN`    | `text` (no citations) |

### ConversationConfig

| Parameter         | Default       | Description        |
| ----------------- | ------------- | ------------------ |
| `model`           | `Models.BEST` | Default model      |
| `citation_mode`   | `CLEAN`       | Citation format    |
| `save_to_library` | `False`       | Save to library    |
| `search_focus`    | `WEB`         | Search type        |
| `source_focus`    | `WEB`         | Source types       |
| `time_range`      | `ALL`         | Time filter        |
| `language`        | `"en-US"`     | Response language  |
| `timezone`        | `None`        | Timezone           |
| `coordinates`     | `None`        | Location (lat/lng) |

## Exceptions

The library provides specific exception types for better error handling:

| Exception                          | Description                                                  |
| ---------------------------------- | ------------------------------------------------------------ |
| `PerplexityError`                  | Base exception for all library errors                        |
| `AuthenticationError`              | Session token is invalid or expired (HTTP 403)               |
| `RateLimitError`                   | Rate limit exceeded (HTTP 429)                               |
| `FileUploadError`                  | File upload failed                                           |
| `FileValidationError`              | File validation failed (size, type, etc.)                    |
| `ResearchClarifyingQuestionsError` | Research mode is asking clarifying questions (not supported) |
| `ResponseParsingError`             | API response could not be parsed                             |
| `StreamingError`                   | Error during streaming response                              |

### Handling Research Mode Clarifying Questions

When using Research mode (`Models.RESEARCH`), the API may ask clarifying questions before providing an answer. Since programmatic interaction is not supported, the library raises a `ResearchClarifyingQuestionsError` with the questions:

```python
from perplexity_webui_scraper import (
    Perplexity,
    ResearchClarifyingQuestionsError,
)

try:
    conversation.ask("Research this topic", model=Models.RESEARCH)
except ResearchClarifyingQuestionsError as error:
    print("The AI needs clarification:")
    for question in error.questions:
        print(f"  - {question}")
    # Consider rephrasing your query to be more specific
```

## MCP Server (Model Context Protocol)

The library includes an MCP server that allows AI assistants (like Claude) to search using Perplexity AI directly.

### Installation

```bash
uv pip install perplexity-webui-scraper[mcp]
```

### Running the Server

```bash
# Set your session token
export PERPLEXITY_SESSION_TOKEN="your_token_here"  # For Linux/Mac
set PERPLEXITY_SESSION_TOKEN="your_token_here"  # For Windows

# Run with FastMCP
uv run fastmcp run src/perplexity_webui_scraper/mcp/server.py

# Or test with the dev inspector
uv run fastmcp dev src/perplexity_webui_scraper/mcp/server.py
```

### Claude Desktop Configuration

Add to `~/.config/claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "perplexity": {
      "command": "uv",
      "args": [
        "run",
        "fastmcp",
        "run",
        "path/to/perplexity_webui_scraper/mcp/server.py"
      ],
      "env": {
        "PERPLEXITY_SESSION_TOKEN": "your_token_here"
      }
    }
  }
}
```

### Available Tool

| Tool             | Description                                                                 |
| ---------------- | --------------------------------------------------------------------------- |
| `perplexity_ask` | Ask questions and get AI-generated answers with real-time data from the web |

**Parameters:**

| Parameter      | Type  | Default  | Description                                                   |
| -------------- | ----- | -------- | ------------------------------------------------------------- |
| `query`        | `str` | -        | Question to ask (required)                                    |
| `model`        | `str` | `"best"` | AI model (`best`, `research`, `gpt52`, `claude_sonnet`, etc.) |
| `source_focus` | `str` | `"web"`  | Source type (`web`, `academic`, `social`, `finance`, `all`)   |

## Disclaimer

This is an **unofficial** library. It uses internal APIs that may change without notice. Use at your own risk.

By using this library, you agree to Perplexity AI's Terms of Service.
