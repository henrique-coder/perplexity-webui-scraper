# Introduction

Python scraper to extract AI responses from [Perplexity's](https://www.perplexity.ai) web interface.

The library uses Perplexity's internal WebUI endpoints with a browser session token. It provides a Python client, file uploads, streamed responses, an MCP server, and an OpenAI-compatible REST API.

## Key Features

- JSON-backed model registry with availability metadata
- Multi-turn conversations
- Document and image attachments
- Synchronous response streaming
- MCP server with one tool per registered model
- REST API for the supported OpenAI chat-completions fields

## Disclaimer

This is an **unofficial** library. It uses internal APIs that may change without notice. Use at your own risk.

By using this library, you agree to Perplexity AI's [Terms of Service](https://www.perplexity.ai/hub/legal/terms-of-service).
