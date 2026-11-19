# Configuration

::: perplexity_webui_scraper.config.client.ClientConfig

---

## Conversation configuration

::: perplexity_webui_scraper.config.conversation.ConversationConfig

---

## Location values

`ConversationConfig` and the API extension accept `latitude` and `longitude` as separate fields. Set both or neither. Latitude ranges from -90 through 90 degrees; longitude ranges from -180 through 180 degrees.

In a REST API request, the object is nested under the `perplexity` key:

```json
{"perplexity": {"latitude": -23.5, "longitude": -46.6}}
```
