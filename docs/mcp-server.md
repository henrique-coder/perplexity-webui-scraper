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

| Tool                           | Model ID                               | Name                         | Description                              | Min. Tier |
| ------------------------------ | -------------------------------------- | ---------------------------- | ---------------------------------------- | --------- |
| `pplx_best`                    | `perplexity/best`                      | Best                         | Perplexity Best (Auto-select).           | pro       |
| `pplx_deep_research`           | `perplexity/deep-research`             | Deep research                | Perplexity Deep Research.                | pro       |
| `pplx_sonar`                   | `perplexity/sonar-2`                   | Sonar 2                      | Perplexity Sonar 2.                      | pro       |
| `pplx_gpt54`                   | `openai/gpt-5.4`                       | GPT-5.4                      | OpenAI GPT-5.4.                          | pro       |
| `pplx_gpt54_thinking`          | `openai/gpt-5.4-thinking`              | GPT-5.4 Thinking             | OpenAI GPT-5.4 (Thinking).               | pro       |
| `pplx_gpt55_thinking`          | `openai/gpt-5.5-thinking`              | GPT-5.5 Thinking             | OpenAI GPT-5.5 (Thinking).               | max       |
| `pplx_glm52`                   | `z-ai/glm-5.2`                         | GLM 5.2                      | Z.ai's most advanced model.              | pro       |
| `pplx_gemini31_pro_think_low`  | `google/gemini-3.1-pro-thinking-low`   | Gemini 3.1 Pro Thinking Low  | Google Gemini 3.1 Pro (Thinking Low).    | pro       |
| `pplx_gemini31_pro_think_high` | `google/gemini-3.1-pro-thinking-high`  | Gemini 3.1 Pro Thinking High | Google Gemini 3.1 Pro (Thinking High).   | pro       |
| `pplx_claude_s46`              | `anthropic/claude-sonnet-4.6`          | Claude Sonnet 4.6            | Anthropic Claude Sonnet 4.6.             | pro       |
| `pplx_claude_s46_think`        | `anthropic/claude-sonnet-4.6-thinking` | Claude Sonnet 4.6 Thinking   | Anthropic Claude Sonnet 4.6 (Thinking).  | pro       |
| `pplx_claude_o47`              | `anthropic/claude-opus-4.7`            | Claude Opus 4.7              | Anthropic Claude Opus 4.7.               | max       |
| `pplx_claude_o47_think`        | `anthropic/claude-opus-4.7-thinking`   | Claude Opus 4.7 Thinking     | Anthropic Claude Opus 4.7 (Thinking).    | max       |
| `pplx_kimi_k26_instant`        | `moonshot/kimi-k2.6-instant`           | Kimi K2.6 Instant            | Moonshot AI Kimi K2.6 Instant.           | pro       |
| `pplx_kimi_k26_thinking`       | `moonshot/kimi-k2.6-thinking`          | Kimi K2.6 Thinking           | Moonshot AI Kimi K2.6 (Thinking).        | pro       |
| `pplx_nemotron3_super_think`   | `nvidia/nemotron-3-super-thinking`     | Nemotron 3 Super Thinking    | NVIDIA Nemotron 3 Super 120B (Thinking). | pro       |

**All tools support `source_focus`:** `web`, `academic`, `social`, `finance`, `all`
