"""GraphQL client for the OEJP Kraken API (stdlib-only, no HA dependency)."""

from __future__ import annotations

import json
import re
import ssl
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

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
        edges {
          node {
            __typename
            id
            postedDate
            createdAt
            amount
            balanceCarriedForward
            isIssued
            isHeld
            isReversed
            hasStatement
            title
            billingDocumentIdentifier
            reasonCode
          }
        }
      }
      bills(first: 5) {
        totalCount
        edges {
          node {
            __typename
            id
            billType
            fromDate
            toDate
            issuedDate
          }
        }
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
            nextReadingDate
            nextNextReadingDate
            readingDateDayOfMonth
            supplyDetails {
              amperage
              kva
              kw
              validFrom
            }
            meters {
              serialNumber
              capacity
            }
            agreements {
              id
              validFrom
              validTo
              product {
                __typename
                ... on ElectricitySingleStepProduct {
                  code
                  displayName
                }
                ... on ElectricitySteppedProduct {
                  code
                  displayName
                }
                ... on ElectricityFitProduct {
                  code
                  displayName
                }
                ... on GasTieredProduct {
                  code
                  displayName
                }
              }
            }
          }
        }
        marketSupplyAgreements(first: 10, active: true) {
          totalCount
          edges {
            node {
              id
              validFrom
              validTo
              product {
                __typename
                code
                displayName
                fullName
                marketName
              }
            }
          }
        }
      }
    }
  }
}
"""

ACCOUNT_INTERVAL_READINGS_QUERY = """
query AccountIntervalReadings($accountNumber: String!) {
  account(accountNumber: $accountNumber) {
    properties {
      electricitySupplyPoints {
        id
        intervalReadings(sortOrder: DESC) {
          readingDate
          startAt
          endAt
          value
          costEstimate
          hasHalfHourlyDataForPeriod
        }
      }
    }
  }
}
"""

ACCOUNT_HALF_HOURLY_READINGS_QUERY = """
query AccountHalfHourlyReadings(
  $accountNumber: String!
  $fromDatetime: DateTime
  $toDatetime: DateTime
) {
  account(accountNumber: $accountNumber) {
    properties {
      electricitySupplyPoints {
        id
        status
        agreements {
          validFrom
        }
        halfHourlyReadings(
          fromDatetime: $fromDatetime
          toDatetime: $toDatetime
        ) {
          consumptionRateBand
          consumptionStep
          costEstimate
          startAt
          value
        }
      }
    }
  }
}
"""

_AUTH_RE = re.compile(r"(Authorization:\s*(?:Bearer|JWT|Token)\s+)\S+", re.IGNORECASE)


def _scrub(text: str, max_len: int = 240) -> str:
    return _AUTH_RE.sub(r"\1[REDACTED]", text)[:max_len]


class GraphQLError(RuntimeError):
    def __init__(self, message: str, *, response_data: Any | None = None) -> None:
        super().__init__(message)
        self.response_data = response_data


@dataclass(frozen=True)
class GraphQLToken:
    """Tokens returned by obtainKrakenToken.

    The GraphQL schema calls the authenticated request token `token`; this is
    the access/Kraken JWT to send in the Authorization header.  `refreshToken`
    is only retained separately for future refresh support and must not be used
    for normal API queries.
    """

    access_token: str
    refresh_token: str | None
    payload: dict[str, Any]

    @property
    def token(self) -> str:
        """Backward-compatible alias for the access token."""
        return self.access_token


@dataclass(frozen=True)
class GraphQLOptionalResult:
    payload: dict[str, Any] | None = None
    error: GraphQLError | None = None


class GraphQLClient:
    """Stdlib-only GraphQL client for the OEJP Kraken API."""

    def __init__(self, *, url: str = DEFAULT_GRAPHQL_URL, timeout: float = 30.0) -> None:
        self.url = url
        self.timeout = timeout

    def execute(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
        *,
        token: str | None = None,
    ) -> dict[str, Any]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "ha-octopusenergy-oejp/0.1.0",
        }
        if token:
            headers["Authorization"] = token
        request = Request(
            self.url,
            data=json.dumps(
                {"query": query, "variables": variables or {}},
                separators=(",", ":"),
            ).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout, context=ssl.create_default_context()) as response:  # noqa: S310
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            raise GraphQLError(f"GraphQL HTTP {exc.code}: {_scrub(raw)}") from exc
        except (URLError, TimeoutError) as exc:
            raise GraphQLError(f"GraphQL network error: {_scrub(str(exc))}") from exc
        except json.JSONDecodeError as exc:
            raise GraphQLError("GraphQL response was not JSON") from exc

        if payload.get("errors"):
            raise GraphQLError("GraphQL returned errors", response_data=payload)
        return payload

    def execute_optional(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
        *,
        token: str | None = None,
    ) -> GraphQLOptionalResult:
        try:
            return GraphQLOptionalResult(payload=self.execute(query, variables, token=token))
        except GraphQLError as exc:
            partial_payload = (
                exc.response_data
                if isinstance(exc.response_data, dict) and exc.response_data.get("data")
                else None
            )
            return GraphQLOptionalResult(payload=partial_payload, error=exc)

    def obtain_token(self, *, email: str, password: str) -> GraphQLToken:
        payload = self.execute(OBTAIN_TOKEN_MUTATION, {"email": email, "password": password})
        data = ((payload.get("data") or {}).get("obtainKrakenToken") or {})
        access_token = data.get("token")
        if not access_token:
            raise GraphQLError("obtainKrakenToken did not return an access token", response_data=payload)
        return GraphQLToken(
            access_token=access_token,
            refresh_token=data.get("refreshToken"),
            payload=data,
        )

    def viewer_energy_snapshot(self, *, token: str) -> dict[str, Any]:
        return self.execute(VIEWER_ENERGY_QUERY, token=token)

    def account_interval_readings(
        self,
        *,
        token: str,
        account_number: str,
    ) -> GraphQLOptionalResult:
        return self.execute_optional(
            ACCOUNT_INTERVAL_READINGS_QUERY,
            {"accountNumber": account_number},
            token=token,
        )

    def account_half_hourly_readings(
        self,
        *,
        token: str,
        account_number: str,
        from_datetime: str,
        to_datetime: str,
    ) -> GraphQLOptionalResult:
        return self.execute_optional(
            ACCOUNT_HALF_HOURLY_READINGS_QUERY,
            {
                "accountNumber": account_number,
                "fromDatetime": from_datetime,
                "toDatetime": to_datetime,
            },
            token=token,
        )

    def fetch_snapshot(self, *, email: str, password: str) -> dict[str, Any]:
        """Login then fetch the full ViewerEnergySnapshot."""
        gql_token = self.obtain_token(email=email, password=password)
        return self.viewer_energy_snapshot(token=gql_token.token)
