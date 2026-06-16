from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import pytest

from octopusenergy_oejp_demo.client import ApiError, HttpResponse, PreparedRequest


@dataclass
class Route:
    method: str
    path: str
    status_code: int
    data: Any


class FakeTransport:
    def __init__(self, routes: list[Route]) -> None:
        self.routes = routes
        self.requests: list[PreparedRequest] = []

    def __call__(self, request: PreparedRequest) -> HttpResponse:
        self.requests.append(request)
        parsed = urlparse(request.url)
        for route in self.routes:
            if route.method == request.method and route.path == parsed.path:
                if route.status_code >= 400:
                    raise ApiError(
                        f"HTTP {route.status_code} for {request.method} {request.url}",
                        status_code=route.status_code,
                        url=request.url,
                        response_data=route.data,
                    )
                return HttpResponse(
                    status_code=route.status_code,
                    data=route.data,
                    headers={"Content-Type": "application/json"},
                    url=request.url,
                    raw_text=json.dumps(route.data),
                )
        raise ApiError(
            f"HTTP 404 for {request.method} {request.url}",
            status_code=404,
            url=request.url,
            response_data={"detail": "not found"},
        )


@pytest.fixture
def fake_transport_factory():
    def factory(routes: list[Route]) -> FakeTransport:
        return FakeTransport(routes)

    return factory
