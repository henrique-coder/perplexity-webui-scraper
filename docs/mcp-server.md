# MCP Server (Model Context Protocol)

The library includes an MCP server that exposes every model as a separate tool for AI assistants like Claude Desktop and Antigravity. Enable only the models you need to keep agent context size small.

## Configuration

Add to your MCP config file (no installation required via npm, handled by python `uvx` native tools):

**Claude Desktop** (`~/.config/claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "perplexity-webui-scraper": {
      "command": "uvx",
      "args": [
        "--from",
        "perplexity-webui-scraper[mcp]@latest",
        "perplexity-webui-scraper",
        "mcp"
      ],
      "env": {
        "PERPLEXITY_SESSION_TOKEN": "your_token_here"
      }
    }
  }
}
```

**From GitHub prod branch:**

```json
{
  "mcpServers": {
    "perplexity-webui-scraper": {
      "command": "uvx",
      "args": [
        "--from",
        "perplexity-webui-scraper[mcp]@git+https://github.com/henrique-coder/perplexity-webui-scraper.git@prod",
        "perplexity-webui-scraper",
        "mcp"
      ],
      "env": {
        "PERPLEXITY_SESSION_TOKEN": "your_token_here"
      }
    }
  }
}
```

**From local directory (for development):**

```json
{
  "mcpServers": {
    "perplexity-webui-scraper": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/perplexity-webui-scraper",
        "run",
        "perplexity-webui-scraper",
        "mcp"
      ],
      "env": {
        "PERPLEXITY_SESSION_TOKEN": "your_token_here"
      }
    }
  }
}
```

## Optional Podman Image

For containerized stdio setups only:

```bash
# Pull published MCP image
podman pull ghcr.io/henrique-coder/perplexity-webui-scraper:mcp

# Run MCP server (requires token)
podman run --rm -it -e PERPLEXITY_SESSION_TOKEN=your_token ghcr.io/henrique-coder/perplexity-webui-scraper:mcp
```

This is niche. Prefer `uvx` for normal MCP client setups.

## Available Tools

Each tool uses a specific AI model. Enable only the ones you need:

| Tool                         | Model                      | Description                                                        | Min. Tier |
| ---------------------------- | -------------------------- | ------------------------------------------------------------------ | --------- |
| `pplx_ask`                   | Pro                        | Automatically selects the most responsive model based on the query | pro       |
| `pplx_deep_research`         | Deep research              | Fast and thorough for routine research                             | pro       |
| `pplx_sonar`                 | Sonar                      | Perplexity's latest model                                          | pro       |
| `pplx_gemini31_pro`          | Gemini 3.1 Pro             | Google's latest model                                              | pro       |
| `pplx_gemini31_pro_think`    | Gemini 3.1 Pro Thinking    | Google's latest model with thinking                                | pro       |
| `pplx_gpt54`                 | GPT-5.4                    | OpenAI's latest model                                              | pro       |
| `pplx_gpt54_thinking`        | GPT-5.4 Thinking           | OpenAI's latest model with thinking                                | pro       |
| `pplx_claude_s46`            | Claude Sonnet 4.6          | Anthropic's fast model                                             | pro       |
| `pplx_claude_s46_think`      | Claude Sonnet 4.6 Thinking | Anthropic's newest reasoning model                                 | pro       |
| `pplx_claude_o46`            | Claude Opus 4.6            | Anthropic's most advanced model                                    | max       |
| `pplx_claude_o46_think`      | Claude Opus 4.6 Thinking   | Anthropic's Opus reasoning model with thinking                     | max       |
| `pplx_nemotron3_super_think` | Nemotron 3 Super Thinking  | NVIDIA's Nemotron 3 Super 120B model with thinking                 | pro       |

**All tools support `source_focus`:** `web`, `academic`, `social`, `finance`, `all`
