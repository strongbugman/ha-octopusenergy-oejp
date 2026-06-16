"""Typed dataclasses for OEJP energy snapshot data."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Agreement:
    id: str
    valid_from: str | None
    valid_to: str | None
    product_typename: str | None


@dataclass
class Meter:
    serial_number: str


@dataclass
class ElectricitySupplyPoint:
    id: str
    spin: str | None
    status: str | None
    meters: list[Meter] = field(default_factory=list)
    agreements: list[Agreement] = field(default_factory=list)


@dataclass
class Property:
    id: str
    postcode: str | None
    address: str | None
    electricity_supply_points: list[ElectricitySupplyPoint] = field(default_factory=list)


@dataclass
class Transaction:
    id: str
    posted_date: str | None
    amount: Any
    title: str | None


@dataclass
class Bill:
    id: str


@dataclass
class MarketSupplyAgreement:
    id: str
    valid_from: str | None
    valid_to: str | None
    product_typename: str | None


@dataclass
class Account:
    number: str
    status: str | None
    balance: Any
    properties: list[Property] = field(default_factory=list)
    transactions_total: int = 0
    transactions_sample: list[Transaction] = field(default_factory=list)
    bills_total: int = 0
    bills_sample: list[Bill] = field(default_factory=list)
    market_supply_agreements_total: int = 0
    market_supply_agreements_sample: list[MarketSupplyAgreement] = field(default_factory=list)


@dataclass
class Viewer:
    id: str
    accounts: list[Account] = field(default_factory=list)


@dataclass
class EnergySnapshot:
    """Top-level snapshot from ViewerEnergySnapshot query."""

    viewer: Viewer

    @property
    def account_count(self) -> int:
        return len(self.viewer.accounts)

    @property
    def property_count(self) -> int:
        return sum(len(a.properties) for a in self.viewer.accounts)

    @property
    def supply_point_count(self) -> int:
        return sum(
            len(p.electricity_supply_points)
            for a in self.viewer.accounts
            for p in a.properties
        )

    @property
    def active_agreement_count(self) -> int:
        count = 0
        for account in self.viewer.accounts:
            count += account.market_supply_agreements_total
            for prop in account.properties:
                for point in prop.electricity_supply_points:
                    count += len(point.agreements)
        return count

    @property
    def bills_total(self) -> int:
        return sum(a.bills_total for a in self.viewer.accounts)

    @property
    def transactions_total(self) -> int:
        return sum(a.transactions_total for a in self.viewer.accounts)


# --- Parsers ---

def _parse_agreement(raw: dict[str, Any]) -> Agreement:
    product = raw.get("product") or {}
    return Agreement(
        id=raw.get("id") or "",
        valid_from=raw.get("validFrom"),
        valid_to=raw.get("validTo"),
        product_typename=product.get("__typename"),
    )


def _parse_meter(raw: dict[str, Any]) -> Meter:
    return Meter(serial_number=raw.get("serialNumber") or "")


def _parse_supply_point(raw: dict[str, Any]) -> ElectricitySupplyPoint:
    return ElectricitySupplyPoint(
        id=raw.get("id") or "",
        spin=raw.get("spin"),
        status=raw.get("status"),
        meters=[_parse_meter(m) for m in (raw.get("meters") or [])],
        agreements=[_parse_agreement(a) for a in (raw.get("agreements") or [])],
    )


def _parse_property(raw: dict[str, Any]) -> Property:
    return Property(
        id=raw.get("id") or "",
        postcode=raw.get("postcode"),
        address=raw.get("address"),
        electricity_supply_points=[
            _parse_supply_point(sp) for sp in (raw.get("electricitySupplyPoints") or [])
        ],
    )


def _parse_transaction(raw: dict[str, Any]) -> Transaction:
    return Transaction(
        id=raw.get("id") or "",
        posted_date=raw.get("postedDate"),
        amount=raw.get("amount"),
        title=raw.get("title"),
    )


def _parse_bill(raw: dict[str, Any]) -> Bill:
    return Bill(id=raw.get("id") or "")


def _parse_market_supply_agreement(raw: dict[str, Any]) -> MarketSupplyAgreement:
    product = raw.get("product") or {}
    return MarketSupplyAgreement(
        id=raw.get("id") or "",
        valid_from=raw.get("validFrom"),
        valid_to=raw.get("validTo"),
        product_typename=product.get("__typename"),
    )


def _parse_account(raw: dict[str, Any]) -> Account:
    transactions = raw.get("transactions") or {}
    bills = raw.get("bills") or {}
    market_agreements = raw.get("marketSupplyAgreements") or {}
    return Account(
        number=raw.get("number") or "",
        status=raw.get("status"),
        balance=raw.get("balance"),
        properties=[_parse_property(p) for p in (raw.get("properties") or [])],
        transactions_total=transactions.get("totalCount") or 0,
        transactions_sample=[
            _parse_transaction(e["node"])
            for e in (transactions.get("edges") or [])
            if e.get("node")
        ],
        bills_total=bills.get("totalCount") or 0,
        bills_sample=[
            _parse_bill(e["node"])
            for e in (bills.get("edges") or [])
            if e.get("node")
        ],
        market_supply_agreements_total=market_agreements.get("totalCount") or 0,
        market_supply_agreements_sample=[
            _parse_market_supply_agreement(e["node"])
            for e in (market_agreements.get("edges") or [])
            if e.get("node")
        ],
    )


def parse_energy_snapshot(raw_response: dict[str, Any]) -> EnergySnapshot:
    """Parse a raw GraphQL ViewerEnergySnapshot response into typed dataclasses."""
    viewer_raw = ((raw_response.get("data") or {}).get("viewer") or {})
    return EnergySnapshot(
        viewer=Viewer(
            id=viewer_raw.get("id") or "",
            accounts=[_parse_account(a) for a in (viewer_raw.get("accounts") or [])],
        )
    )
