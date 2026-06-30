# Client

The `Perplexity` client is the main entry point for the library. Create one instance per session token and reuse it across conversations.

`get_account_profile()` returns typed account data from `/api/auth/session`, falling back to `/rest/user/settings` when the session response is incomplete. Prompt requests use that same account-tier check to reject models that require a higher account tier before sending the prompt.

::: perplexity_webui_scraper.core.client.Perplexity
