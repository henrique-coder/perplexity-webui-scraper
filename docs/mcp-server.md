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

| Tool                           | Model ID                              | Name                     | Description                                    | Min. Tier |
| ------------------------------ | ------------------------------------- | ------------------------ | ---------------------------------------------- | --------- |
| `pplx_best`                    | `perplexity/best`                     | Best                     | Adapts to each query.                          | free      |
| `pplx_deep_research`           | `perplexity/deep-research`            | Deep research            | Fast and thorough for routine research.        | pro       |
| `pplx_sonar`                   | `perplexity/sonar-2`                  | Sonar 2                  | Perplexity's latest in-house model.            | pro       |
| `pplx_gpt56_terra`             | `openai/gpt-5.6-terra`                | GPT-5.6 Terra            | OpenAI's versatile model.                      | pro       |
| `pplx_gpt56_terra_thinking`    | `openai/gpt-5.6-terra-thinking`       | GPT-5.6 Terra Thinking   | OpenAI's versatile model with thinking.        | pro       |
| `pplx_gpt56_sol`               | `openai/gpt-5.6-sol`                  | GPT-5.6 Sol              | OpenAI's most powerful model.                  | max       |
| `pplx_gpt56_sol_thinking`      | `openai/gpt-5.6-sol-thinking`         | GPT-5.6 Sol Thinking     | OpenAI's most powerful model with thinking.    | max       |
| `pplx_claude_s50`              | `anthropic/claude-sonnet-5`           | Claude Sonnet 5          | Anthropic's fast model.                        | pro       |
| `pplx_claude_s50_think`        | `anthropic/claude-sonnet-5-thinking`  | Claude Sonnet 5 Thinking | Anthropic's newest reasoning model.            | pro       |
| `pplx_claude_o48`              | `anthropic/claude-opus-4.8`           | Claude Opus 4.8          | Anthropic's most advanced model.               | max       |
| `pplx_claude_o48_think`        | `anthropic/claude-opus-4.8-thinking`  | Claude Opus 4.8 Thinking | Anthropic's most advanced model with thinking. | max       |
| `pplx_glm52`                   | `z-ai/glm-5.2`                        | GLM 5.2                  | Z.ai's most advanced model.                    | pro       |
| `pplx_gemini31_pro_think_low`  | `google/gemini-3.1-pro-thinking-low`  | Gemini 3.1 Pro           | Google's latest model.                         | pro       |
| `pplx_gemini31_pro_think_high` | `google/gemini-3.1-pro-thinking-high` | Gemini 3.1 Pro Thinking  | Google's latest model with thinking.           | pro       |
| `pplx_kimi_k26_instant`        | `moonshot/kimi-k2.6-instant`          | Kimi K2.6                | Moonshot AI's latest model.                    | pro       |
| `pplx_kimi_k26_thinking`       | `moonshot/kimi-k2.6-thinking`         | Kimi K2.6 Thinking       | Moonshot AI's latest model with Thinking.      | pro       |
| `pplx_nemotron3_super_think`   | `nvidia/nemotron-3-super-thinking`    | Nemotron 3 Super         | NVIDIA's Nemotron 3 Super 120B model.          | pro       |
| `pplx_nemotron3_ultra_think`   | `nvidia/nemotron-3-ultra-thinking`    | Nemotron 3 Ultra         | NVIDIA's Nemotron 3 Ultra 550B model.          | pro       |

**All tools support `source_focus`:** `web`, `academic`, `social`, `finance`, `all`
