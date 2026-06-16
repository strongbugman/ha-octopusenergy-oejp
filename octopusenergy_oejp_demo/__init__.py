"""Prototype client and CLI for the OEJP Kraken electricity REST API."""

from .client import (
    ApiError,
    AuthError,
    HttpResponse,
    OctopusOejpClient,
    PreparedRequest,
)
from .discovery import (
    DiscoveryReport,
    async_discover_account_electricity_data,
    discover_account_electricity_data,
)

__all__ = [
    "ApiError",
    "AuthError",
    "DiscoveryReport",
    "HttpResponse",
    "OctopusOejpClient",
    "PreparedRequest",
    "async_discover_account_electricity_data",
    "discover_account_electricity_data",
]
