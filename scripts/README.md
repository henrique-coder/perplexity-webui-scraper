# Model availability smoke test

Run a short availability check for catalog models.

The script reads `PERPLEXITY_SESSION_TOKEN` from `.env` and writes results to `reports/model-smoke-results.json`. The token is not included in the report.

Models above the account tier are recorded as `blocked_by_account_tier`. Other models run concurrently. HTTP 429 responses are retried once, then recorded as `rate_limited`.

```bash
uv run --no-sync python scripts/smoke_test_models.py --workers 4
```

Statuses: `passed`, `empty_response`, `blocked_by_account_tier`, `rate_limited`, `authentication_error`, `http_error`, `model_rejected`, `response_error`, or `error`.
