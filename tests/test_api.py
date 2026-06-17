"""Tests for GraphQLClient in api.py (urllib mocked, no real network)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from custom_components.octopusenergy_oejp.api import GraphQLClient, GraphQLError, GraphQLToken
from tests.conftest import SAMPLE_SNAPSHOT_RESPONSE

TOKEN_RESPONSE = {
    "data": {
        "obtainKrakenToken": {
            "token": "test-jwt-token",
            "refreshToken": "test-refresh-token",
            "refreshExpiresIn": 3600,
            "payload": {"email": "user@example.com"},
        }
    }
}


def _mock_response(data: dict) -> MagicMock:
    body = json.dumps(data).encode("utf-8")
    resp = MagicMock()
    resp.read.return_value = body
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


def test_obtain_token_returns_graphql_token():
    client = GraphQLClient()
    with patch("custom_components.octopusenergy_oejp.api.urlopen") as mock_open:
        mock_open.return_value = _mock_response(TOKEN_RESPONSE)
        result = client.obtain_token(email="user@example.com", password="secret")

    assert isinstance(result, GraphQLToken)
    assert result.access_token == "test-jwt-token"
    assert result.refresh_token == "test-refresh-token"
    assert result.token == result.access_token
    assert result.payload["refreshToken"] == "test-refresh-token"


def test_obtain_token_raises_when_no_token():
    client = GraphQLClient()
    with patch("custom_components.octopusenergy_oejp.api.urlopen") as mock_open:
        mock_open.return_value = _mock_response({"data": {"obtainKrakenToken": {}}})
        with pytest.raises(GraphQLError, match="did not return an access token"):
            client.obtain_token(email="user@example.com", password="bad")


def test_execute_attaches_raw_authorization_header():
    captured = []

    def fake_urlopen(request, timeout, context):
        captured.append(request)
        return _mock_response(SAMPLE_SNAPSHOT_RESPONSE)

    client = GraphQLClient()
    with patch("custom_components.octopusenergy_oejp.api.urlopen", side_effect=fake_urlopen):
        client.viewer_energy_snapshot(token="test-jwt-token")

    assert len(captured) == 1
    assert captured[0].get_header("Authorization") == "test-jwt-token"


def test_execute_raises_on_graphql_errors():
    error_payload = {"errors": [{"message": "Unauthenticated"}]}
    client = GraphQLClient()
    with patch("custom_components.octopusenergy_oejp.api.urlopen") as mock_open:
        mock_open.return_value = _mock_response(error_payload)
        with pytest.raises(GraphQLError, match="GraphQL returned errors"):
            client.execute("query { viewer { id } }", token="bad")


def test_fetch_snapshot_calls_obtain_token_then_query():
    call_count = 0

    def fake_urlopen(request, timeout, context):
        nonlocal call_count
        call_count += 1
        return _mock_response(TOKEN_RESPONSE if call_count == 1 else SAMPLE_SNAPSHOT_RESPONSE)

    client = GraphQLClient()
    with patch("custom_components.octopusenergy_oejp.api.urlopen", side_effect=fake_urlopen):
        result = client.fetch_snapshot(email="user@example.com", password="secret")

    assert call_count == 2
    assert result == SAMPLE_SNAPSHOT_RESPONSE


def test_execute_raises_graphql_error_on_http_error():
    from urllib.error import HTTPError
    from io import BytesIO

    client = GraphQLClient()
    exc = HTTPError(url="https://example.com", code=401, msg="Unauthorized", hdrs={}, fp=BytesIO(b"bad creds"))
    with patch("custom_components.octopusenergy_oejp.api.urlopen", side_effect=exc):
        with pytest.raises(GraphQLError, match="GraphQL HTTP 401"):
            client.execute("query { viewer { id } }")


def test_execute_raises_graphql_error_on_url_error():
    from urllib.error import URLError

    client = GraphQLClient()
    with patch("custom_components.octopusenergy_oejp.api.urlopen", side_effect=URLError("connection refused")):
        with pytest.raises(GraphQLError, match="GraphQL network error"):
            client.execute("query { viewer { id } }")


def test_execute_optional_returns_partial_payload_and_error_on_graphql_error():
    partial_payload = {
        "errors": [{"message": "Unauthorized.", "extensions": {"errorCode": "KT-CT-4501"}}],
        "data": {"viewer": {"accounts": []}},
    }
    client = GraphQLClient()
    with patch("custom_components.octopusenergy_oejp.api.urlopen") as mock_open:
        mock_open.return_value = _mock_response(partial_payload)
        result = client.execute_optional("query { viewer { id } }", token="test-jwt-token")

    assert result.payload == partial_payload
    assert isinstance(result.error, GraphQLError)


def test_account_half_hourly_readings_passes_account_and_datetime_variables():
    captured = []

    def fake_urlopen(request, timeout, context):
        captured.append(json.loads(request.data.decode("utf-8")))
        return _mock_response(SAMPLE_SNAPSHOT_RESPONSE)

    client = GraphQLClient()
    with patch("custom_components.octopusenergy_oejp.api.urlopen", side_effect=fake_urlopen):
        result = client.account_half_hourly_readings(
            token="test-jwt-token",
            account_number="A-1234567",
            from_datetime="2026-01-01T00:00:00+09:00",
            to_datetime="2026-01-02T00:00:00+09:00",
        )

    assert result.error is None
    assert captured[0]["variables"] == {
        "accountNumber": "A-1234567",
        "fromDatetime": "2026-01-01T00:00:00+09:00",
        "toDatetime": "2026-01-02T00:00:00+09:00",
    }
    assert "account(accountNumber: $accountNumber)" in captured[0]["query"]


def test_account_interval_readings_passes_account_number_variable():
    captured = []

    def fake_urlopen(request, timeout, context):
        captured.append(json.loads(request.data.decode("utf-8")))
        return _mock_response(SAMPLE_SNAPSHOT_RESPONSE)

    client = GraphQLClient()
    with patch("custom_components.octopusenergy_oejp.api.urlopen", side_effect=fake_urlopen):
        result = client.account_interval_readings(
            token="test-jwt-token",
            account_number="A-1234567",
        )

    assert result.error is None
    assert captured[0]["variables"] == {"accountNumber": "A-1234567"}
    assert "account(accountNumber: $accountNumber)" in captured[0]["query"]
