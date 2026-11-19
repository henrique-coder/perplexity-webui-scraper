# Perplexity WebUI Scraper

Unofficial Python client for Perplexity's WebUI-backed conversation endpoints.

The client accepts raw UUID session-cookie pairs and compact `wsk_` credentials; email authentication emits compact form. `wsk_` is reversible obfuscation, not encryption or authenticated integrity. Install optional extras for token retrieval, the API server, or MCP.

## Features

- JSON-backed model registry with availability metadata
- Multi-turn conversations
- Document and image attachments
- Synchronous response streaming
- MCP server with one tool per registered model
- REST API with OpenAI-compatible Chat Completions

## Disclaimer

This is an **unofficial** library. It uses internal APIs that may change without notice. Use at your own risk.

By using this library, you agree to Perplexity AI's [Terms of Service](https://www.perplexity.ai/hub/legal/terms-of-service).
