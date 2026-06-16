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
    assert result.token == "test-jwt-token"
    assert result.payload["refreshToken"] == "test-refresh-token"


def test_obtain_token_raises_when_no_token():
    client = GraphQLClient()
    with patch("custom_components.octopusenergy_oejp.api.urlopen") as mock_open:
        mock_open.return_value = _mock_response({"data": {"obtainKrakenToken": {}}})
        with pytest.raises(GraphQLError, match="did not return a token"):
            client.obtain_token(email="user@example.com", password="bad")


def test_execute_attaches_jwt_authorization_header():
    captured = []

    def fake_urlopen(request, timeout, context):
        captured.append(request)
        return _mock_response(SAMPLE_SNAPSHOT_RESPONSE)

    client = GraphQLClient()
    with patch("custom_components.octopusenergy_oejp.api.urlopen", side_effect=fake_urlopen):
        client.viewer_energy_snapshot(token="test-jwt-token")

    assert len(captured) == 1
    assert captured[0].get_header("Authorization") == "JWT test-jwt-token"


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
