# Perplexity WebUI Scraper

This project provides an unofficial Python client library designed for programmatic interaction with Perplexity AI. It enables developers to access Perplexity's features by simulating communications with its web user interface's internal endpoints.

## Installation

```bash
uv add git+https://github.com/henrique-coder/perplexity-webui-scraper.git --branch main
```

## Requirements

To effectively use this library, the following are essential:

- An **active Perplexity Pro subscription**.
- A **valid `__Secure-next-auth.session-token` cookie**. This token must be obtained from an authenticated Perplexity AI web session and is crucial for the library to authenticate its requests as the user. It's recommended to store this token in an environment variable (e.g., `PERPLEXITY_SESSION_TOKEN`).

### How to Obtain Your Session Token

1. **Open Perplexity AI in your browser** and log in to your account at [https://www.perplexity.ai](https://www.perplexity.ai)

2. **Open Developer Tools:**
   - **Chrome/Edge:** Press `F12` or `Ctrl+Shift+I` (Windows/Linux) / `Cmd+Option+I` (Mac)
   - **Firefox:** Press `F12` or `Ctrl+Shift+I` (Windows/Linux) / `Cmd+Option+I` (Mac)
   - **Safari:** Enable "Develop" menu in Preferences → Advanced, then press `Cmd+Option+I`

3. **Navigate to the Application/Storage tab:**
   - **Chrome/Edge:** Click on "Application" tab
   - **Firefox:** Click on "Storage" tab
   - **Safari:** Click on "Storage" tab

4. **Find your session token:**
   - Expand "Cookies" in the left sidebar
   - Click on `https://www.perplexity.ai`
   - Look for a cookie named `__Secure-next-auth.session-token`
   - Copy the **Value** of this cookie

5. **Store it securely:**
   - Create a `.env` file in your project root
   - Add: `PERPLEXITY_SESSION_TOKEN=your_token_here`
   - **Never commit this token to version control!**

**⚠️ Important Notes:**

- Your session token is sensitive and should be kept private
- Session tokens may expire - if you get a 403 error, obtain a new token
- Do not share your session token with others

## Quick Start

Here's a basic example of how to use the library to ask a question and stream the response:

```python
from os import getenv
from dotenv import load_dotenv
from rich.live import Live
from rich.panel import Panel

from perplexity_webui_scraper import Perplexity, CitationMode, ModelType, SearchFocus, SourceFocus, TimeRange


load_dotenv()

client = Perplexity(session_token=getenv("PERPLEXITY_SESSION_TOKEN"))

with Live(Panel("", title="Waiting for answer", border_style="white"), refresh_per_second=30, vertical_overflow="visible") as live:
    for chunk in client.ask(
        query="Explain in a simplified and easy-to-understand way what a chatbot is.",
        files=None,
        citation_mode=CitationMode.DEFAULT,
        model=ModelType.Best,
        save_to_library=False,
        search_focus=SearchFocus.WEB,
        source_focus=SourceFocus.WEB,
        time_range=TimeRange.ALL,
        language="en-US",
        timezone=None,
        coordinates=None,
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
