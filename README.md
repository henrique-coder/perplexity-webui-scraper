<div align="center">

# Perplexity WebUI Scraper

Unofficial Python client for [Perplexity AI](https://www.perplexity.ai).

[![PyPI](https://img.shields.io/pypi/v/perplexity-webui-scraper?color=blue)](https://pypi.org/project/perplexity-webui-scraper)
[![Python](https://img.shields.io/pypi/pyversions/perplexity-webui-scraper)](https://pypi.org/project/perplexity-webui-scraper)
[![License](https://img.shields.io/github/license/henrique-coder/perplexity-webui-scraper?color=green)](./LICENSE)

</div>

---

## Installation

```bash
uv pip install perplexity-webui-scraper
```

## Requirements

- **Perplexity Pro subscription**
- **Session token** (`__Secure-next-auth.session-token` cookie from browser)

### Getting Your Session Token

1. Log in at [perplexity.ai](https://www.perplexity.ai)
2. Open DevTools (`F12`) → Application → Cookies
3. Copy `__Secure-next-auth.session-token` value
4. Store in `.env`: `PERPLEXITY_SESSION_TOKEN=your_token`

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

| Parameter       | Type           | Default       | Description         |
| --------------- | -------------- | ------------- | ------------------- |
| `query`         | `str`          | —             | Question (required) |
| `model`         | `Model`        | `Models.BEST` | AI model            |
| `files`         | `list[str]`    | `None`        | File paths          |
| `citation_mode` | `CitationMode` | `CLEAN`       | Citation format     |
| `stream`        | `bool`         | `False`       | Enable streaming    |

### Models

| Model                          | Description       |
| ------------------------------ | ----------------- |
| `Models.BEST`                  | Auto-select best  |
| `Models.RESEARCH`              | Deep research     |
| `Models.SONAR`                 | Fast queries      |
| `Models.GPT_51`                | OpenAI GPT-5.1    |
| `Models.CLAUDE_45_SONNET`      | Claude 4.5 Sonnet |
| `Models.GEMINI_3_PRO_THINKING` | Gemini 3.0 Pro    |
| `Models.GROK_41`               | xAI Grok 4.1      |

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

## Disclaimer

This is an **unofficial** library. It uses internal APIs that may change without notice. Use at your own risk. Not for production use.

By using this library, you agree to Perplexity AI's Terms of Service.
