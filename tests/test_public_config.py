from __future__ import annotations

from os import PathLike
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import Mock, patch

from orjson import dumps
from pydantic import ValidationError
from pytest import raises

from perplexity_webui_scraper import (
    CitationMode,
    LogLevel,
    Perplexity,
    ResearchInteraction,
    SearchFocus,
    SourceFocus,
    TimeRange,
)
from perplexity_webui_scraper.api.schemas.request import PerplexityExtensions
from perplexity_webui_scraper.auth.cookies import (
    CookieCredential,
    extract_session_cookie,
    parse_session_cookie_name,
    parse_session_credential,
)
from perplexity_webui_scraper.config.client import ClientConfig
from perplexity_webui_scraper.config.conversation import ConversationConfig
from perplexity_webui_scraper.core.file_types import FileInput
from perplexity_webui_scraper.core.files import validate_files
from perplexity_webui_scraper.core.payload import build_payload
from perplexity_webui_scraper.models.registry import MODELS


if TYPE_CHECKING:
    from pathlib import Path


class _CoordinateConversationConfig:
    def __init__(self, **values: object) -> None:
        self.model = "perplexity/best"
        self.search_focus = "web"
        self.source_focus = "web"
        self.time_range = "all"
        self.language = "en-US"
        self.timezone = None
        self.save_to_library = False
        self.space_uuid = None
        self.latitude = values.get("latitude")
        self.longitude = values.get("longitude")


def _accept_file_inputs(files: list[FileInput]) -> list[FileInput]:
    return files


def _build_payload_for_coordinates(latitude: float, longitude: float) -> dict[str, Any]:
    config = _CoordinateConversationConfig(latitude=latitude, longitude=longitude)
    return build_payload(
        query="location test",
        model=MODELS.resolve("perplexity/best"),
        file_urls=[],
        config=cast("ConversationConfig", config),
        backend_uuid=None,
        read_write_token=None,
    )


def test_conversation_config_accepts_direct_coordinate_values() -> None:
    config = ConversationConfig.model_validate({"latitude": -23.5, "longitude": -46.6})

    assert config.__dict__["latitude"] == -23.5
    assert config.__dict__["longitude"] == -46.6


def test_conversation_config_rejects_partial_coordinates() -> None:
    with raises(ValidationError, match="provided together"):
        ConversationConfig.model_validate({"latitude": -23.5})


def test_conversation_config_rejects_coordinates_outside_geographic_ranges() -> None:
    with raises(ValidationError):
        ConversationConfig.model_validate({"latitude": 90.01, "longitude": 0})

    with raises(ValidationError):
        ConversationConfig.model_validate({"latitude": 0, "longitude": -180.01})

    with raises(ValidationError):
        ConversationConfig.model_validate({"latitude": float("nan"), "longitude": 0})


def test_chat_api_extension_literals_remain_validated_and_described() -> None:
    schema = PerplexityExtensions.model_json_schema()
    config_schema = ConversationConfig.model_json_schema()

    extension = PerplexityExtensions(citation_mode="markdown", search_focus="writing", time_range="all")
    assert extension.citation_mode == "markdown"
    with raises(ValidationError):
        PerplexityExtensions.model_validate({"search_focus": "invalid", "time_range": "all"})

    assert schema["properties"]["citation_mode"]["anyOf"][0]["enum"] == ["default", "markdown", "clean"]
    assert schema["properties"]["search_focus"]["anyOf"][0]["enum"] == ["web", "writing"]
    assert "web" in str(config_schema["properties"]["source_focus"]["anyOf"][0].get("description", ""))
    assert "loguru" not in schema["properties"]["citation_mode"].get("description", "")


def test_client_config_rejects_invalid_logging_level() -> None:
    with raises(ValidationError):
        ClientConfig.model_validate({"logging_level": "verbose"})


def test_public_type_aliases_remain_importable() -> None:
    assert all(
        alias is not None
        for alias in (CitationMode, LogLevel, ResearchInteraction, SearchFocus, SourceFocus, TimeRange)
    )
    assert FileInput == str | PathLike[str] | bytes | tuple[bytes, str] | tuple[bytes, str, str]


def test_file_input_forms_share_the_runtime_validator(tmp_path: Path) -> None:
    sample = tmp_path / "sample.txt"
    sample.write_text("sample", encoding="utf-8")
    local = tmp_path / "local.txt"
    local.write_text("local", encoding="utf-8")
    raw = b"sample"

    file_inputs: list[FileInput] = [local, sample, raw, (raw, "named.txt"), (raw, "typed.txt", "text/plain")]
    files = validate_files(list(_accept_file_inputs(file_inputs)))

    assert [file.filename for file in files] == ["local.txt", "sample.txt", "file", "named.txt", "typed.txt"]


def test_coordinates_are_passed_directly_to_payload_builder() -> None:
    payload = _build_payload_for_coordinates(-23.5, -46.6)

    assert payload["params"]["client_coordinates"] == {
        "location_lat": -23.5,
        "location_lng": -46.6,
        "name": "",
    }


def test_auth_cookie_extraction_rejects_non_uuid_cookie_names() -> None:
    account_id = "00000000-0000-0000-0000-000000000000"

    assert parse_session_cookie_name(f"__Secure-pplx.session.{account_id}") == (
        "__Secure-pplx.session",
        account_id,
    )
    assert parse_session_cookie_name("__Secure-next-auth.session-token") is None
    assert parse_session_cookie_name("__Secure-pplx.session.unrecognized") is None
    assert parse_session_cookie_name("__Secure-pplx.session") is None


def test_auth_cookie_extraction_returns_none_when_no_supported_cookie_is_present() -> None:
    assert extract_session_cookie({"unrelated": "value"}) is None


def test_auth_cookie_extraction_prefers_uuid_cookie_when_both_cookies_exist() -> None:
    cookies = {
        "__Secure-next-auth.session-token": "legacy-value",
        "__Secure-pplx.session.00000000-0000-0000-0000-000000000000": "dynamic-value",
    }

    assert extract_session_cookie(cookies) == (
        "__Secure-pplx.session.00000000-0000-0000-0000-000000000000",
        "dynamic-value",
    )


def test_auth_cookie_extraction_uses_active_account_cookie_when_multiple_exist() -> None:
    cookies = {
        "__Secure-pplx.session.00000000-0000-0000-0000-000000000000": "one",
        "__Secure-pplx.session.11111111-1111-1111-1111-111111111111": "two",
        "__Host-pplx-last-active-account": "11111111-1111-1111-1111-111111111111",
    }

    assert extract_session_cookie(cookies) == (
        "__Secure-pplx.session.11111111-1111-1111-1111-111111111111",
        "two",
    )


def test_auth_cookie_extraction_rejects_active_account_without_matching_cookie() -> None:
    cookies = {
        "__Secure-pplx.session.00000000-0000-0000-0000-000000000000": "first",
        "__Host-pplx-last-active-account": "11111111-1111-1111-1111-111111111111",
    }

    with raises(ValueError, match="active Perplexity account"):
        extract_session_cookie(cookies, "11111111-1111-1111-1111-111111111111")


def test_auth_cookie_extraction_rejects_invalid_active_account_id() -> None:
    cookies = {
        "__Secure-pplx.session.00000000-0000-0000-0000-000000000000": "first",
        "__Host-pplx-last-active-account": "not-a-uuid",
    }

    with raises(ValueError, match="identifier is invalid"):
        extract_session_cookie(cookies)


def test_auth_cookie_extraction_rejects_ambiguous_uuid_cookies() -> None:
    cookies = {
        "__Secure-pplx.session.00000000-0000-0000-0000-000000000000": "one",
        "__Secure-pplx.session.11111111-1111-1111-1111-111111111111": "two",
    }

    with raises(ValueError, match="ambiguous"):
        extract_session_cookie(cookies)


def test_auth_cookie_extraction_ignores_empty_uuid_cookie_values() -> None:
    cookies = {"__Secure-pplx.session.00000000-0000-0000-0000-000000000000": ""}

    assert extract_session_cookie(cookies) is None


def test_session_credential_requires_uuid_cookie_pair() -> None:
    account_id = "123e4567-e89b-42d3-a456-426614174000"
    name = f"__Secure-pplx.session.{account_id}"
    cookie_value = "eyJhbGciOiJkaXIiLCJlbmMiOiJBMjU2R0NNIn0..EBESExQVFhcYGRob.AQIDBAUGBw.MDEyMzQ1Njc4OTo7PD0-Pw"

    assert parse_session_credential(f"{name}={cookie_value}") == (name, cookie_value)

    with raises(ValueError, match=r"UUID|cookie"):
        parse_session_credential("__Secure-next-auth.session-token=legacy-value")

    with raises(ValueError, match="optional session cookie"):
        parse_session_credential("legacy-value")


def test_session_credential_accepts_compact_token_and_normalizes_to_cookie_pair() -> None:
    compact_token = "wsk_1LlYHVDOBjIiT2Z5Re7RX82sRkpZ5DPQbXq7WcWjQyJlxphkNEnW1yoqjF8SLIqNqCvaOJkw"
    expected = CookieCredential(
        "__Secure-pplx.session.123e4567-e89b-42d3-a456-426614174000",
        "eyJhbGciOiJkaXIiLCJlbmMiOiJBMjU2R0NNIn0..EBESExQVFhcYGRob.AQIDBAUGBw.MDEyMzQ1Njc4OTo7PD0-Pw",
    )

    assert parse_session_credential(compact_token) == expected


def test_public_client_requires_and_installs_uuid_cookie_pair() -> None:
    account_id = "123e4567-e89b-42d3-a456-426614174000"
    cookie_value = "eyJhbGciOiJkaXIiLCJlbmMiOiJBMjU2R0NNIn0..EBESExQVFhcYGRob.AQIDBAUGBw.MDEyMzQ1Njc4OTo7PD0-Pw"
    credential = f"__Secure-pplx.session.{account_id}={cookie_value}"

    client = Perplexity(session_token=credential)
    cookie = next(item for item in client._http._session.cookies.jar if item.name.startswith("__Secure-pplx.session."))

    assert cookie.name == f"__Secure-pplx.session.{account_id}"
    assert cookie.value == cookie_value

    response = Mock(status_code=200, content=dumps({"user": {"id": account_id}}))
    with patch.object(client._http._session, "get", return_value=response):
        profile = client.get_account_session()

    assert profile.user is not None and profile.user.id == account_id
    client.close()

    with raises(ValueError, match=r"UUID|cookie"):
        Perplexity(session_token="legacy-value")
