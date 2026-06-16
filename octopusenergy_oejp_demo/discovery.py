"""Endpoint discovery and reporting for account/electricity data."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .client import ApiError, AuthError, HttpResponse, OctopusOejpClient
from .graphql import (
    GraphQLError,
    GraphQLClient,
    account_numbers_from_snapshot,
    meter_identifiers_from_snapshot,
    property_ids_from_snapshot,
    summarize_viewer_energy_snapshot,
)
from .redaction import redact_json, redact_path, scrub_error_text, summarize_identifiers

ROOT_ENDPOINTS = (
    ("accounts", "/v1/accounts/"),
    ("me", "/v1/me/"),
    ("customer", "/v1/customer/"),
    ("customers_me", "/v1/customers/me/"),
    ("properties", "/v1/properties/"),
    ("electricity_meter_points", "/v1/electricity-meter-points/"),
)

ACCOUNT_ENDPOINT_TEMPLATES = (
    ("account_detail", "/v1/accounts/{account}/"),
    ("account_properties", "/v1/accounts/{account}/properties/"),
    ("account_electricity_meter_points", "/v1/accounts/{account}/electricity-meter-points/"),
    ("account_agreements", "/v1/accounts/{account}/agreements/"),
    ("account_tariffs", "/v1/accounts/{account}/tariffs/"),
    ("account_bills", "/v1/accounts/{account}/bills/"),
    ("account_payments", "/v1/accounts/{account}/payments/"),
    ("account_transactions", "/v1/accounts/{account}/transactions/"),
    ("account_meter_readings", "/v1/accounts/{account}/meter-readings/"),
    ("account_electricity_consumption", "/v1/accounts/{account}/electricity-consumption/"),
)

PROPERTY_ENDPOINT_TEMPLATES = (
    ("property_detail", "/v1/properties/{property}/"),
    ("property_electricity_meter_points", "/v1/properties/{property}/electricity-meter-points/"),
)

METER_POINT_ENDPOINT_TEMPLATES = (
    ("electricity_meter_point_detail", "/v1/electricity-meter-points/{meter_point}/"),
    ("electricity_meter_point_meters", "/v1/electricity-meter-points/{meter_point}/meters/"),
    ("electricity_meter_point_agreements", "/v1/electricity-meter-points/{meter_point}/agreements/"),
    ("electricity_meter_point_consumption", "/v1/electricity-meter-points/{meter_point}/consumption/"),
    ("electricity_meter_point_readings", "/v1/electricity-meter-points/{meter_point}/readings/"),
)

METER_ENDPOINT_TEMPLATES = (
    (
        "meter_consumption",
        "/v1/electricity-meter-points/{meter_point}/meters/{meter}/consumption/",
    ),
    (
        "meter_readings",
        "/v1/electricity-meter-points/{meter_point}/meters/{meter}/readings/",
    ),
)

ACCOUNT_KEYS = {
    "account",
    "account_id",
    "account_number",
    "account_no",
    "accountno",
    "accountnumber",
    "number",
}
PROPERTY_KEYS = {"property", "property_id", "propertyid"}
METER_POINT_KEYS = {
    "electricity_meter_point",
    "electricity_meter_point_id",
    "electricitymeterpointid",
    "meter_point",
    "meter_point_id",
    "meterpointid",
    "mpan",
    "nmi",
    "service_point",
    "service_point_id",
    "supply_point",
    "supply_point_id",
}
METER_KEYS = {
    "meter",
    "meter_id",
    "meter_number",
    "meter_serial_number",
    "meter_serial",
    "serial",
    "serial_number",
    "serialnumber",
}


@dataclass
class EndpointResult:
    name: str
    path: str
    ok: bool
    status_code: int | None = None
    page_count: int = 0
    item_count: int | None = None
    error: str | None = None

    def to_summary(self) -> dict[str, Any]:
        summary = {
            "name": self.name,
            "path": redact_path(self.path),
            "ok": self.ok,
            "status_code": self.status_code,
            "page_count": self.page_count,
        }
        if self.item_count is not None:
            summary["item_count"] = self.item_count
        if self.error:
            error = scrub_error_text(self.error)
            error = error.replace(self.path, redact_path(self.path))
            summary["error"] = error
        return summary


@dataclass
class DiscoveryReport:
    authenticated: bool = False
    auth_path: str | None = None
    graphql_authenticated: bool = False
    graphql_snapshot_summary: dict[str, Any] | None = None
    graphql_error: dict[str, Any] | None = None
    endpoints: list[EndpointResult] = field(default_factory=list)
    accounts: set[str] = field(default_factory=set)
    properties: set[str] = field(default_factory=set)
    meter_points: set[str] = field(default_factory=set)
    meters: set[str] = field(default_factory=set)
    raw_payloads: dict[str, dict[str, Any]] = field(default_factory=dict)
    auth_error: dict[str, Any] | None = None

    def summary(self, *, raw_output_path: str | None = None) -> dict[str, Any]:
        successful = sum(1 for endpoint in self.endpoints if endpoint.ok)
        failed = sum(1 for endpoint in self.endpoints if not endpoint.ok)
        summary: dict[str, Any] = {
            "authenticated": self.authenticated,
            "auth_path": redact_path(self.auth_path) if self.auth_path else None,
            "graphql_authenticated": self.graphql_authenticated,
            "graphql_energy_snapshot": self.graphql_snapshot_summary,
            "endpoint_counts": {
                "attempted": len(self.endpoints),
                "successful": successful,
                "failed": failed,
            },
            "discovered": {
                "accounts": len(self.accounts),
                "properties": len(self.properties),
                "electricity_meter_points": len(self.meter_points),
                "meters": len(self.meters),
            },
            "endpoint_results": [endpoint.to_summary() for endpoint in self.endpoints],
        }
        if raw_output_path:
            summary["raw_successful_payloads_file"] = raw_output_path
        if self.auth_error:
            summary["auth_error"] = redact_json(self.auth_error)
        if self.graphql_error:
            summary["graphql_error"] = redact_json(self.graphql_error)
        return summary

    def redacted_identifier_summary(self) -> dict[str, Any]:
        return {
            "accounts": summarize_identifiers(tuple(self.accounts)),
            "properties": summarize_identifiers(tuple(self.properties)),
            "electricity_meter_points": summarize_identifiers(tuple(self.meter_points)),
            "meters": summarize_identifiers(tuple(self.meters)),
        }


def _bootstrap_from_graphql(client: OctopusOejpClient, report: DiscoveryReport) -> None:
    password = getattr(client, "_password", None)
    if not client.email or not password or client._transport.__class__.__name__ != "UrllibTransport":  # noqa: SLF001
        return

    graphql = GraphQLClient(timeout=client.timeout)
    try:
        token = graphql.obtain_token(email=client.email, password=password)
        snapshot = graphql.viewer_energy_snapshot(token=token.token)
    except GraphQLError as exc:
        report.graphql_authenticated = False
        report.graphql_error = {
            "message": scrub_error_text(str(exc)),
            "details": exc.response_data,
        }
        return

    report.graphql_authenticated = True
    report.graphql_snapshot_summary = summarize_viewer_energy_snapshot(snapshot)
    report.accounts.update(account_numbers_from_snapshot(snapshot))
    report.properties.update(property_ids_from_snapshot(snapshot))
    meter_points, meters = meter_identifiers_from_snapshot(snapshot)
    report.meter_points.update(meter_points)
    report.meters.update(meters)
    report.raw_payloads["graphql_viewer_energy_snapshot"] = {
        "name": "graphql_viewer_energy_snapshot",
        "path": "graphql:ViewerEnergySnapshot",
        "pages": [snapshot],
    }

    # Reuse the GraphQL JWT for REST probes. The REST guide says the same token
    # can be passed via the Authorization header; OEJP accepts the Kraken token
    # using the JWT scheme for GraphQL, and REST rejects/404s are then meaningful
    # endpoint availability results rather than auth-bootstrap failures.
    client._token = token.token  # noqa: SLF001 - local prototype bootstrap
    client.auth_scheme = "JWT"
    client.authenticated_via = "graphql:obtainKrakenToken"


def discover_account_electricity_data(
    client: OctopusOejpClient,
    *,
    max_pages: int = 10,
    max_derived_requests: int = 100,
) -> DiscoveryReport:
    """Authenticate and discover account/electricity resources available to credentials.

    The OEJP REST docs point account-user authentication at the GraphQL token
    flow. We therefore bootstrap a JWT with `obtainKrakenToken`, fetch one
    GraphQL electricity/account snapshot to discover identifiers, then probe the
    REST endpoint catalogue and record which REST resources work for the same
    credentials.
    """

    report = DiscoveryReport()
    _bootstrap_from_graphql(client, report)

    try:
        client.authenticate()
        report.authenticated = True
        report.auth_path = client.authenticated_via
    except AuthError as exc:
        report.authenticated = False
        report.auth_error = {
            "message": scrub_error_text(str(exc)),
            "details": exc.response_data,
        }
        if not report.graphql_authenticated:
            return report

    attempted_paths: set[str] = set()
    derived_requests = 0

    for name, path in ROOT_ENDPOINTS:
        _attempt_endpoint(client, report, name, path, attempted_paths, max_pages=max_pages)

    while derived_requests < max_derived_requests:
        next_requests = _build_derived_requests(report)
        next_requests = [
            (name, path)
            for name, path in next_requests
            if path not in attempted_paths
        ]
        if not next_requests:
            break

        for name, path in next_requests:
            if derived_requests >= max_derived_requests:
                break
            _attempt_endpoint(client, report, name, path, attempted_paths, max_pages=max_pages)
            derived_requests += 1

    return report


async def async_discover_account_electricity_data(
    client: OctopusOejpClient,
    *,
    max_pages: int = 10,
    max_derived_requests: int = 100,
) -> DiscoveryReport:
    import asyncio

    return await asyncio.to_thread(
        discover_account_electricity_data,
        client,
        max_pages=max_pages,
        max_derived_requests=max_derived_requests,
    )


def save_raw_payloads(report: DiscoveryReport, output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.raw_payloads, indent=2, sort_keys=True), encoding="utf-8")


def _attempt_endpoint(
    client: OctopusOejpClient,
    report: DiscoveryReport,
    name: str,
    path: str,
    attempted_paths: set[str],
    *,
    max_pages: int,
) -> None:
    attempted_paths.add(path)
    try:
        pages = _fetch_pages(client, path, max_pages=max_pages)
    except ApiError as exc:
        report.endpoints.append(
            EndpointResult(
                name=name,
                path=path,
                ok=False,
                status_code=exc.status_code,
                error=scrub_error_text(str(exc)),
            )
        )
        return

    response = pages[-1]
    payload = [page.data for page in pages] if len(pages) > 1 else pages[0].data
    item_count = _count_items(payload)
    report.endpoints.append(
        EndpointResult(
            name=name,
            path=path,
            ok=True,
            status_code=response.status_code,
            page_count=len(pages),
            item_count=item_count,
        )
    )
    report.raw_payloads[_payload_key(name, path)] = {
        "name": name,
        "path": path,
        "pages": [page.data for page in pages],
    }
    _extract_identifiers(payload, report)


def _fetch_pages(client: OctopusOejpClient, path: str, *, max_pages: int) -> list[HttpResponse]:
    pages: list[HttpResponse] = []
    next_path: str | None = path
    for _ in range(max_pages):
        if not next_path:
            break
        response = client.get_json(next_path)
        pages.append(response)
        next_path = _next_page(response.data)
    return pages


def _next_page(data: Any) -> str | None:
    if not isinstance(data, dict):
        return None
    next_value = data.get("next") or data.get("next_page") or data.get("nextPage")
    if isinstance(next_value, str) and next_value:
        parsed = urlparse(next_value)
        if parsed.scheme and parsed.netloc:
            return next_value
        return next_value
    return None


def _build_derived_requests(report: DiscoveryReport) -> list[tuple[str, str]]:
    requests: list[tuple[str, str]] = []
    for account in sorted(report.accounts):
        for name, template in ACCOUNT_ENDPOINT_TEMPLATES:
            requests.append((name, template.format(account=account)))
    for property_id in sorted(report.properties):
        for name, template in PROPERTY_ENDPOINT_TEMPLATES:
            requests.append((name, template.format(property=property_id)))
    for meter_point in sorted(report.meter_points):
        for name, template in METER_POINT_ENDPOINT_TEMPLATES:
            requests.append((name, template.format(meter_point=meter_point)))
        for meter in sorted(report.meters):
            for name, template in METER_ENDPOINT_TEMPLATES:
                requests.append((name, template.format(meter_point=meter_point, meter=meter)))
    return requests


def _extract_identifiers(value: Any, report: DiscoveryReport) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = _normalize_key(key)
            if _is_scalar_identifier(item):
                text = str(item)
                if normalized in ACCOUNT_KEYS:
                    report.accounts.add(text)
                elif normalized in PROPERTY_KEYS:
                    report.properties.add(text)
                elif normalized in METER_POINT_KEYS:
                    report.meter_points.add(text)
                elif normalized in METER_KEYS:
                    report.meters.add(text)
            _extract_identifiers(item, report)
    elif isinstance(value, list):
        for item in value:
            _extract_identifiers(item, report)


def _normalize_key(key: str) -> str:
    return key.replace("-", "_").replace(" ", "_").lower()


def _is_scalar_identifier(value: Any) -> bool:
    return isinstance(value, (str, int)) and str(value).strip() != ""


def _count_items(payload: Any) -> int | None:
    if isinstance(payload, list):
        if payload and all(isinstance(page, dict) and "results" in page for page in payload):
            return sum(_count_items(page) or 0 for page in payload)
        return len(payload)
    if isinstance(payload, dict):
        for key in ("results", "items", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return len(value)
        return 1
    return None


def _payload_key(name: str, path: str) -> str:
    safe_path = path.strip("/").replace("/", "__").replace("{", "").replace("}", "")
    safe_path = safe_path.replace("?", "_").replace("&", "_").replace("=", "-")
    return f"{name}__{safe_path or 'root'}"
