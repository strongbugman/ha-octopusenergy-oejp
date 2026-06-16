from __future__ import annotations

import json

from octopusenergy_oejp_demo.client import OctopusOejpClient

from .conftest import Route


def test_authenticates_and_sends_bearer_header(fake_transport_factory):
    transport = fake_transport_factory(
        [
            Route("POST", "/v1/auth/login/", 200, {"access_token": "secret-token"}),
            Route("GET", "/v1/accounts/", 200, {"results": []}),
        ]
    )
    client = OctopusOejpClient(
        email="person@example.com",
        password="not-printed",
        base_url="https://api.example.test",
        auth_paths=("/v1/auth/login/",),
        transport=transport,
    )

    response = client.get_json("/v1/accounts/")

    assert response.data == {"results": []}
    auth_request, data_request = transport.requests
    assert json.loads(auth_request.body.decode("utf-8")) == {
        "email": "person@example.com",
        "password": "not-printed",
    }
    assert data_request.headers["Authorization"] == "Bearer secret-token"


def test_authentication_falls_back_to_next_configured_path(fake_transport_factory):
    transport = fake_transport_factory(
        [
            Route("POST", "/v1/auth/login/", 404, {"detail": "missing"}),
            Route("POST", "/v1/auth/token/", 200, {"token": "fallback-token"}),
            Route("GET", "/v1/accounts/", 200, {"results": []}),
        ]
    )
    client = OctopusOejpClient(
        email="person@example.com",
        password="not-printed",
        base_url="https://api.example.test",
        auth_paths=("/v1/auth/login/", "/v1/auth/token/"),
        transport=transport,
    )

    client.get_json("/v1/accounts/")

    assert client.authenticated_via == "/v1/auth/token/"
    assert [request.url for request in transport.requests] == [
        "https://api.example.test/v1/auth/login/",
        "https://api.example.test/v1/auth/token/",
        "https://api.example.test/v1/accounts/",
    ]
