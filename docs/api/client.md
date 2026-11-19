# Client

Pass either a raw `__Secure-pplx.session.<UUIDv4>=<JWE>` cookie pair or a compact `wsk_` credential as `session_token`. Both forms normalize to the same account session. Compact tokens are reversible obfuscation, not encryption or authenticated integrity.

`get_account_profile()` returns typed account data from `/api/auth/session` and falls back to `/rest/user/settings` when the session response lacks subscription data. The session request includes the account UUID parsed from the UUID-suffixed cookie name. Before each prompt, the client checks whether the selected available model requires a higher account tier.

Email authentication emits `wsk_` compact tokens. Convert a raw cookie or validate an existing compact token offline with `perplexity-webui-scraper token --convert`. The compact representation is reversible obfuscation, not encryption or authenticated integrity.

::: perplexity_webui_scraper.core.client.Perplexity
