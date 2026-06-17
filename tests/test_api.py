"""Tests for GraphQLClient in api.py (httpx mocked, no real network)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
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


def _mock_http(data: dict) -> MagicMock:
    """Return a mock httpx.AsyncClient whose .post() resolves to the given data."""
    resp = MagicMock()
    resp.json.return_value = data
    resp.raise_for_status.return_value = None
    resp.status_code = 200
    resp.text = json.dumps(data)

    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=resp)
    return mock_client


async def test_obtain_token_returns_graphql_token():
    client = GraphQLClient()
    client._http = _mock_http(TOKEN_RESPONSE)
    result = await client.obtain_token(email="user@example.com", password="secret")

    assert isinstance(result, GraphQLToken)
    assert result.access_token == "test-jwt-token"
    assert result.refresh_token == "test-refresh-token"
    assert result.token == result.access_token
    assert result.payload["refreshToken"] == "test-refresh-token"


async def test_obtain_token_raises_when_no_token():
    client = GraphQLClient()
    client._http = _mock_http({"data": {"obtainKrakenToken": {}}})
    with pytest.raises(GraphQLError, match="did not return an access token"):
        await client.obtain_token(email="user@example.com", password="bad")


async def test_execute_attaches_raw_authorization_header():
    captured_headers: list[dict] = []

    async def fake_post(url, *, content, headers):
        captured_headers.append(dict(headers))
        resp = MagicMock()
        resp.json.return_value = SAMPLE_SNAPSHOT_RESPONSE
        resp.raise_for_status.return_value = None
        return resp

    client = GraphQLClient()
    mock_http = MagicMock()
    mock_http.post = fake_post
    client._http = mock_http

    await client.viewer_energy_snapshot(token="test-jwt-token")

    assert len(captured_headers) == 1
    assert captured_headers[0]["Authorization"] == "test-jwt-token"


async def test_execute_raises_on_graphql_errors():
    error_payload = {"errors": [{"message": "Unauthenticated"}]}
    client = GraphQLClient()
    client._http = _mock_http(error_payload)
    with pytest.raises(GraphQLError, match="GraphQL returned errors"):
        await client.execute("query { viewer { id } }", token="bad")


async def test_fetch_snapshot_calls_obtain_token_then_query():
    call_count = 0

    async def fake_post(url, *, content, headers):
        nonlocal call_count
        call_count += 1
        resp = MagicMock()
        resp.json.return_value = TOKEN_RESPONSE if call_count == 1 else SAMPLE_SNAPSHOT_RESPONSE
        resp.raise_for_status.return_value = None
        return resp

    client = GraphQLClient()
    mock_http = MagicMock()
    mock_http.post = fake_post
    client._http = mock_http

    result = await client.fetch_snapshot(email="user@example.com", password="secret")

    assert call_count == 2
    assert result == SAMPLE_SNAPSHOT_RESPONSE


async def test_execute_raises_graphql_error_on_http_error():
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "bad creds"
    http_exc = httpx.HTTPStatusError(
        "401 Unauthorized", request=MagicMock(), response=mock_response
    )
    mock_response.raise_for_status.side_effect = http_exc

    client = GraphQLClient()
    mock_http = MagicMock()
    mock_http.post = AsyncMock(return_value=mock_response)
    client._http = mock_http

    with pytest.raises(GraphQLError, match="GraphQL HTTP 401"):
        await client.execute("query { viewer { id } }")


async def test_execute_raises_graphql_error_on_network_error():
    client = GraphQLClient()
    mock_http = MagicMock()
    mock_http.post = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
    client._http = mock_http

    with pytest.raises(GraphQLError, match="GraphQL network error"):
        await client.execute("query { viewer { id } }")


async def test_execute_optional_returns_partial_payload_and_error_on_graphql_error():
    partial_payload = {
        "errors": [{"message": "Unauthorized.", "extensions": {"errorCode": "KT-CT-4501"}}],
        "data": {"viewer": {"accounts": []}},
    }
    client = GraphQLClient()
    client._http = _mock_http(partial_payload)
    result = await client.execute_optional("query { viewer { id } }", token="test-jwt-token")

    assert result.payload == partial_payload
    assert isinstance(result.error, GraphQLError)


async def test_account_half_hourly_readings_passes_account_and_datetime_variables():
    captured: list[dict] = []

    async def fake_post(url, *, content, headers):
        captured.append(json.loads(content.decode("utf-8")))
        resp = MagicMock()
        resp.json.return_value = SAMPLE_SNAPSHOT_RESPONSE
        resp.raise_for_status.return_value = None
        return resp

    client = GraphQLClient()
    mock_http = MagicMock()
    mock_http.post = fake_post
    client._http = mock_http

    result = await client.account_half_hourly_readings(
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


async def test_account_interval_readings_passes_account_number_variable():
    captured: list[dict] = []

    async def fake_post(url, *, content, headers):
        captured.append(json.loads(content.decode("utf-8")))
        resp = MagicMock()
        resp.json.return_value = SAMPLE_SNAPSHOT_RESPONSE
        resp.raise_for_status.return_value = None
        return resp

    client = GraphQLClient()
    mock_http = MagicMock()
    mock_http.post = fake_post
    client._http = mock_http

    result = await client.account_interval_readings(
        token="test-jwt-token",
        account_number="A-1234567",
    )

    assert result.error is None
    assert captured[0]["variables"] == {"accountNumber": "A-1234567"}
    assert "account(accountNumber: $accountNumber)" in captured[0]["query"]


async def test_same_http_client_reused_across_calls():
    """The same httpx.AsyncClient instance is used for multiple requests (no new connection per call)."""
    resp = MagicMock()
    resp.json.return_value = SAMPLE_SNAPSHOT_RESPONSE
    resp.raise_for_status.return_value = None

    mock_http_instance = MagicMock()
    mock_http_instance.post = AsyncMock(return_value=resp)

    with patch("httpx.AsyncClient", return_value=mock_http_instance) as MockAsyncClient:
        client = GraphQLClient()
        await client.execute("query { viewer { id } }", token="tok")
        await client.execute("query { viewer { id } }", token="tok")

        assert MockAsyncClient.call_count == 1, "httpx.AsyncClient must be instantiated only once"
        assert mock_http_instance.post.call_count == 2
