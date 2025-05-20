# Perplexity WebUI Scraper

This project provides an unofficial Python client library designed for programmatic interaction with Perplexity AI. It enables developers to access Perplexity's features by simulating communications with its web user interface's internal endpoints.

## Installation

You can install the library directly from GitHub using pip:

```bash
pip install --upgrade git+https://github.com/henrique-coder/perplexity-webui-scraper.git@main
```

## Requirements

To effectively use this library, the following are essential:

- An **active Perplexity Pro subscription**.
- A **valid `__Secure-next-auth.session-token` cookie**. This token must be obtained from an authenticated Perplexity AI web session and is crucial for the library to authenticate its requests as the user. It's recommended to store this token in an environment variable (e.g., `PERPLEXITY_SESSION_TOKEN`).

## Quick Start

Here's a basic example of how to use the library to ask a question and stream the response:

```python
from os import getenv
from dotenv import load_dotenv
from rich.console import Console
from rich.live import Live
from rich.panel import Panel

from perplexity_webui_scraper import Perplexity, CitationMode, ModelType, SearchFocus, SourceFocus, TimeRange


load_dotenv()
console = Console()

client = Perplexity(session_token=getenv("PERPLEXITY_SESSION_TOKEN"))

with Live(Panel("", title="Waiting for answer", border_style="white"), refresh_per_second=30, vertical_overflow="visible") as live:
    for chunk in client.ask(
        query="Explain in a simplified and easy-to-understand way what a chatbot is.",
        citation_mode=CitationMode.MARKDOWN,
        model=ModelType.Pro.Gemini25Pro,
        save_to_library=False,
        search_focus=SearchFocus.WEB,
        source_focus=SourceFocus.WEB,
        time_range=TimeRange.ALL,
        language="en-US",
        timezone="America/New_York",
        coordinates=(-0.123, -4.567),
    ).stream():
        if chunk.last_chunk:
            current_answer = chunk.answer or ""
            live.update(Panel(current_answer, title="Receiving tokens", border_style="blue"))

    final_answer = chunk.answer or "No answer received"
    live.update(Panel(final_answer, title="Final answer", border_style="green"))

```

## Important Disclaimers and Usage Guidelines

Please read the following carefully before using this library:

- **Unofficial Status:** Perplexity WebUI Scraper is an independent, community-driven project. It is **not** affiliated with, endorsed, sponsored, or officially supported by Perplexity AI in any way.
- **Reliance on Internal Mechanisms:** This library functions by interacting with internal API endpoints and mechanisms that Perplexity AI uses for its own web interface. These are not public or officially supported APIs. As such, they are subject to change, modification, or removal by Perplexity AI at any time, without prior notice. Such changes can, and likely will, render this library non-functional or cause unexpected behavior.
- **Risk and Responsibility:** You assume all risks associated with the use of this software. The maintainers of this project are not responsible for any direct or indirect consequences, disruptions, or potential issues that may arise from its use, including (but not limited to) any actions taken by Perplexity AI regarding your account.
- **Compliance and Ethical Use:** Users are solely responsible for ensuring that their use of this library adheres to Perplexity AI's Terms of Service, Acceptable Use Policy, and any other relevant guidelines. This library should be used in a manner that respects Perplexity's infrastructure and does not constitute abuse (e.g., by making an excessive number of requests).
- **Educational and Experimental Tool:** This library is provided primarily for educational and experimental purposes. It is intended to facilitate learning and exploration of programmatic interaction with web services. It is **not recommended for critical, production, or commercial applications** due to its inherent instability.

By using this library, you acknowledge and agree to these terms.
