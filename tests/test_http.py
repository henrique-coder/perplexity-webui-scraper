from __future__ import annotations

from typing import Any, cast

from perplexity_webui_scraper.http.client import HTTPClient


class _HTTPStatusError(Exception):
    def __init__(self, response: _FakeResponse) -> None:
        self.response = response
        super().__init__(f"HTTP {response.status_code}")


class _FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        self.url = "https://www.perplexity.ai/rest/test"
        self.text = "rate limited" if status_code == 429 else "ok"

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise _HTTPStatusError(self)


class _FakeSession:
    def __init__(self) -> None:
        self.calls = 0

    def post(self, url: str, json: dict[str, Any] | None = None, stream: bool = False) -> _FakeResponse:
        self.calls += 1
        return _FakeResponse(429 if self.calls == 1 else 200)

    def close(self) -> None:
        return None


def test_http_client_retries_translated_rate_limit_error() -> None:
    client = HTTPClient(
        "token",
        max_retries=1,
        retry_base_delay=0,
        retry_jitter=0,
        rotate_fingerprint=False,
        requests_per_second=0,
    )
    client.close()
    fake_session = _FakeSession()
    client._session = cast("Any", fake_session)

    response = client.post("/rest/test", json={"query": "hello"})

    assert response.status_code == 200
    assert fake_session.calls == 2
