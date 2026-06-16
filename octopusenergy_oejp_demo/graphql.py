"""GraphQL helpers used to bootstrap OEJP account-user credentials.

The REST guide says authenticated REST calls can use the same token described by
GraphQL/authentication docs. For account users, the practical bootstrap endpoint
is the `obtainKrakenToken` GraphQL mutation. This module keeps that behavior out
of the REST transport while still allowing the discovery demo to prove which
account/electricity data is available for the supplied login.
"""

from __future__ import annotations

import json
import ssl
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .redaction import scrub_error_text

DEFAULT_GRAPHQL_URL = "https://api.oejp-kraken.energy/v1/graphql/"

OBTAIN_TOKEN_MUTATION = """
mutation ObtainKrakenToken($email: String!, $password: String!) {
  obtainKrakenToken(input: {email: $email, password: $password}) {
    token
    refreshToken
    refreshExpiresIn
    payload
  }
}
"""

VIEWER_ENERGY_QUERY = """
query ViewerEnergySnapshot {
  viewer {
    id
    accounts {
      number
      status
      balance
      transactions(first: 5) {
        totalCount
        edges { node { id postedDate amount title } }
      }
      bills(first: 5) {
        totalCount
        edges { node { id } }
      }
      ... on Account {
        properties {
          id
          postcode
          address
          electricitySupplyPoints {
            id
            spin
            status
            meters { serialNumber }
            agreements { id validFrom validTo product { __typename } }
          }
        }
        marketSupplyAgreements(first: 10, active: true) {
          totalCount
          edges { node { id validFrom validTo product { __typename } } }
        }
      }
    }
  }
}
"""


class GraphQLError(RuntimeError):
    """Raised when the OEJP GraphQL endpoint returns errors or cannot be reached."""

    def __init__(self, message: str, *, response_data: Any | None = None) -> None:
        super().__init__(message)
        self.response_data = response_data


@dataclass(frozen=True)
class GraphQLToken:
    token: str
    raw_payload: dict[str, Any]


class GraphQLClient:
    """Tiny standard-library GraphQL client for this demo."""

    def __init__(self, *, url: str = DEFAULT_GRAPHQL_URL, timeout: float = 30.0) -> None:
        self.url = url
        self.timeout = timeout

    def execute(self, query: str, variables: dict[str, Any] | None = None, *, token: str | None = None) -> dict[str, Any]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "ha-octopusenergy-oejp-demo/0.1.0",
        }
        if token:
            headers["Authorization"] = f"JWT {token}"
        request = Request(
            self.url,
            data=json.dumps({"query": query, "variables": variables or {}}, separators=(",", ":")).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout, context=ssl.create_default_context()) as response:  # noqa: S310
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            raise GraphQLError(f"GraphQL HTTP {exc.code}: {scrub_error_text(raw)}") from exc
        except (URLError, TimeoutError) as exc:
            raise GraphQLError(f"GraphQL network error: {scrub_error_text(str(exc))}") from exc
        except json.JSONDecodeError as exc:
            raise GraphQLError("GraphQL response was not JSON") from exc

        if payload.get("errors"):
            raise GraphQLError("GraphQL returned errors", response_data=payload)
        return payload

    def obtain_token(self, *, email: str, password: str) -> GraphQLToken:
        payload = self.execute(OBTAIN_TOKEN_MUTATION, {"email": email, "password": password})
        data = ((payload.get("data") or {}).get("obtainKrakenToken") or {})
        token = data.get("token")
        if not token:
            raise GraphQLError("obtainKrakenToken did not return a token", response_data=payload)
        return GraphQLToken(token=token, raw_payload=payload)

    def viewer_energy_snapshot(self, *, token: str) -> dict[str, Any]:
        return self.execute(VIEWER_ENERGY_QUERY, token=token)


def summarize_viewer_energy_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    viewer = ((snapshot.get("data") or {}).get("viewer") or {})
    accounts = viewer.get("accounts") or []
    properties = []
    supply_points = []
    meters = []
    active_agreements = 0
    bill_total = 0
    transaction_total = 0
    for account in accounts:
        account_properties = account.get("properties") or []
        properties.extend(account_properties)
        bill_total += ((account.get("bills") or {}).get("totalCount") or 0)
        transaction_total += ((account.get("transactions") or {}).get("totalCount") or 0)
        active_agreements += ((account.get("marketSupplyAgreements") or {}).get("totalCount") or 0)
        for prop in account_properties:
            points = prop.get("electricitySupplyPoints") or []
            supply_points.extend(points)
            for point in points:
                meters.extend(point.get("meters") or [])
                active_agreements += len(point.get("agreements") or [])
    return {
        "accounts": len(accounts),
        "properties": len(properties),
        "electricity_supply_points": len(supply_points),
        "meters": len(meters),
        "active_or_point_agreements": active_agreements,
        "bills_total": bill_total,
        "transactions_total": transaction_total,
    }


def account_numbers_from_snapshot(snapshot: dict[str, Any]) -> set[str]:
    viewer = ((snapshot.get("data") or {}).get("viewer") or {})
    return {str(account.get("number")) for account in (viewer.get("accounts") or []) if account.get("number")}


def property_ids_from_snapshot(snapshot: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    viewer = ((snapshot.get("data") or {}).get("viewer") or {})
    for account in viewer.get("accounts") or []:
        for prop in account.get("properties") or []:
            if prop.get("id"):
                ids.add(str(prop["id"]))
    return ids


def meter_identifiers_from_snapshot(snapshot: dict[str, Any]) -> tuple[set[str], set[str]]:
    supply_points: set[str] = set()
    meters: set[str] = set()
    viewer = ((snapshot.get("data") or {}).get("viewer") or {})
    for account in viewer.get("accounts") or []:
        for prop in account.get("properties") or []:
            for point in prop.get("electricitySupplyPoints") or []:
                if point.get("id"):
                    supply_points.add(str(point["id"]))
                if point.get("spin"):
                    supply_points.add(str(point["spin"]))
                for meter in point.get("meters") or []:
                    if meter.get("serialNumber"):
                        meters.add(str(meter["serialNumber"]))
    return supply_points, meters
