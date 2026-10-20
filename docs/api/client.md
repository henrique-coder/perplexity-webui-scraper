# Client

Create one `Perplexity` client per session token and reuse it across conversations. Use a context manager or call `close()` when the client is no longer needed.

`get_account_profile()` returns typed account data from `/api/auth/session` and falls back to `/rest/user/settings` when the session response lacks subscription data. Before each prompt, the client checks whether the selected available model requires a higher account tier.

::: perplexity_webui_scraper.core.client.Perplexity
