# Conversation

`Conversation` stores the state for one backend thread. Create it with `client.create_conversation()` and reuse it for follow-up prompts. With `stream=True`, `ask()` returns `self` and yields response snapshots as the stream is parsed.

::: perplexity_webui_scraper.core.conversation.Conversation
