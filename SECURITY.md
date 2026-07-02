# Security Policy

## Supported Versions

Security fixes are applied to the latest released version of `perplexity-webui-scraper`. Older versions may not receive patches.

## Reporting a Vulnerability

Do not disclose security vulnerabilities publicly.

Preferred reporting path:

1. Use GitHub private vulnerability reporting if it is enabled for this repository.
2. If private reporting is not available, open a minimal public issue asking for private maintainer contact. Do not include exploit details, tokens, cookies, private prompts, account data, or reproduction payloads in the public issue.

Please include privately:

- A clear description of the vulnerability.
- A minimal reproduction when possible.
- Affected versions or commits.
- Potential impact.
- Any suggested fix or mitigation.

## Sensitive Data

Never include real Perplexity session tokens, cookies, account IDs, private prompts, uploaded documents, screenshots containing secrets, or browser request headers with credentials in public issues, discussions, pull requests, or logs.

## Scope

In scope:

- Leaks of session tokens or authentication material caused by this project.
- Unsafe handling of uploaded files.
- Vulnerabilities in the local REST API or MCP server exposed by this project.
- Packaging or CI issues that could compromise published artifacts.

Out of scope:

- Vulnerabilities in Perplexity itself.
- Abuse of Perplexity accounts or subscription limitations.
- Issues requiring access to someone else's account without permission.
- Social engineering, spam, or denial-of-service testing.
