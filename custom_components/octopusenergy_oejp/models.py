"""Typed dataclasses for OEJP energy snapshot data."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Iterable


ACCESS_AUTHORIZED = "authorized"
ACCESS_DISABLED = "disabled"
ACCESS_ERROR = "error"
ACCESS_NOT_REQUESTED = "not_requested"
ACCESS_UNAUTHORIZED = "unauthorized"


@dataclass
class AccessStatus:
    """Access state for optional or potentially restricted GraphQL fields."""

    field_name: str
    status: str = ACCESS_NOT_REQUESTED
    message: str | None = None
    error_codes: list[str] = field(default_factory=list)
    error_paths: list[str] = field(default_factory=list)

    @classmethod
    def authorized(cls, field_name: str) -> AccessStatus:
        return cls(field_name=field_name, status=ACCESS_AUTHORIZED)

    @classmethod
    def not_requested(cls, field_name: str) -> AccessStatus:
        return cls(field_name=field_name, status=ACCESS_NOT_REQUESTED)


@dataclass
class ProductSummary:
    typename: str | None = None
    code: str | None = None
    display_name: str | None = None
    full_name: str | None = None
    market_name: str | None = None


@dataclass
class Agreement:
    id: str
    valid_from: str | None
    valid_to: str | None
    product: ProductSummary = field(default_factory=ProductSummary)

    @property
    def product_typename(self) -> str | None:
        return self.product.typename


@dataclass
class Meter:
    serial_number: str
    capacity: int | None = None


@dataclass
class SupplyDetails:
    amperage: int | None
    kva: int | None
    kw: Any
    valid_from: str | None


@dataclass
class SupplyPeriod:
    id: str
    supply_start_at: str | None
    supply_end_at: str | None
    is_billable: bool | None


@dataclass
class ElectricityIntervalReading:
    reading_date: str | None
    start_at: str | None
    end_at: str | None
    value: Any
    cost_estimate: Any
    has_half_hourly_data_for_period: bool | None


@dataclass
class ElectricityHalfHourReading:
    start_at: str | None
    end_at: str | None
    value: Any
    cost_estimate: Any
    consumption_rate_band: str | None


@dataclass
class ElectricitySupplyPoint:
    id: str
    spin: str | None
    status: str | None
    next_reading_date: str | None = None
    next_next_reading_date: str | None = None
    reading_date_day_of_month: int | None = None
    meters: list[Meter] = field(default_factory=list)
    agreements: list[Agreement] = field(default_factory=list)
    supply_details: list[SupplyDetails] = field(default_factory=list)
    supply_periods: list[SupplyPeriod] = field(default_factory=list)
    interval_readings: list[ElectricityIntervalReading] = field(default_factory=list)
    half_hourly_readings: list[ElectricityHalfHourReading] = field(default_factory=list)
    interval_readings_access: AccessStatus = field(
        default_factory=lambda: AccessStatus.not_requested("intervalReadings")
    )
    half_hourly_readings_access: AccessStatus = field(
        default_factory=lambda: AccessStatus.not_requested("halfHourlyReadings")
    )

    @property
    def meter_count(self) -> int:
        return len(self.meters)

    @property
    def latest_interval_reading(self) -> ElectricityIntervalReading | None:
        if not self.interval_readings:
            return None
        return max(
            self.interval_readings,
            key=lambda r: r.start_at or r.reading_date or "",
        )

    @property
    def latest_half_hourly_reading(self) -> ElectricityHalfHourReading | None:
        if not self.half_hourly_readings:
            return None
        return max(self.half_hourly_readings, key=lambda r: r.start_at or "")


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
    typename: str | None = None
    created_at: str | None = None
    balance_carried_forward: Any = None
    billing_document_identifier: str | None = None
    is_issued: bool | None = None
    is_held: bool | None = None
    is_reversed: bool | None = None
    has_statement: bool | None = None
    reason_code: str | None = None


@dataclass
class Bill:
    id: str
    typename: str | None = None
    bill_type: str | None = None
    from_date: str | None = None
    to_date: str | None = None
    issued_date: str | None = None


@dataclass
class MarketSupplyAgreement:
    id: str
    valid_from: str | None
    valid_to: str | None
    product: ProductSummary = field(default_factory=ProductSummary)

    @property
    def product_typename(self) -> str | None:
        return self.product.typename


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
        return sum(1 for _ in self.iter_supply_points())

    @property
    def meter_count(self) -> int:
        return sum(point.meter_count for point in self.iter_supply_points())

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

    def iter_supply_points(self) -> Iterable[ElectricitySupplyPoint]:
        for account in self.viewer.accounts:
            for prop in account.properties:
                yield from prop.electricity_supply_points

    def iter_account_supply_points(
        self,
        account_number: str | None = None,
    ) -> Iterable[ElectricitySupplyPoint]:
        for account in self.viewer.accounts:
            if account_number is not None and account.number != account_number:
                continue
            for prop in account.properties:
                yield from prop.electricity_supply_points


# --- Parsers ---

def _parse_product(raw: dict[str, Any] | None) -> ProductSummary:
    raw = raw or {}
    return ProductSummary(
        typename=raw.get("__typename"),
        code=raw.get("code"),
        display_name=raw.get("displayName"),
        full_name=raw.get("fullName"),
        market_name=raw.get("marketName"),
    )


def _parse_agreement(raw: dict[str, Any]) -> Agreement:
    return Agreement(
        id=str(raw.get("id") or ""),
        valid_from=raw.get("validFrom"),
        valid_to=raw.get("validTo"),
        product=_parse_product(raw.get("product")),
    )


def _parse_meter(raw: dict[str, Any]) -> Meter:
    return Meter(
        serial_number=raw.get("serialNumber") or "",
        capacity=raw.get("capacity"),
    )


def _parse_supply_details(raw: dict[str, Any]) -> SupplyDetails:
    return SupplyDetails(
        amperage=raw.get("amperage"),
        kva=raw.get("kva"),
        kw=raw.get("kw"),
        valid_from=raw.get("validFrom"),
    )


def _parse_supply_period(raw: dict[str, Any]) -> SupplyPeriod:
    return SupplyPeriod(
        id=str(raw.get("id") or ""),
        supply_start_at=raw.get("supplyStartAt"),
        supply_end_at=raw.get("supplyEndAt"),
        is_billable=raw.get("isBillable"),
    )


def _parse_interval_reading(raw: dict[str, Any]) -> ElectricityIntervalReading:
    return ElectricityIntervalReading(
        reading_date=raw.get("readingDate"),
        start_at=raw.get("startAt"),
        end_at=raw.get("endAt"),
        value=raw.get("value"),
        cost_estimate=raw.get("costEstimate"),
        has_half_hourly_data_for_period=raw.get("hasHalfHourlyDataForPeriod"),
    )


def _parse_half_hourly_reading(raw: dict[str, Any]) -> ElectricityHalfHourReading:
    return ElectricityHalfHourReading(
        start_at=raw.get("startAt"),
        end_at=raw.get("endAt"),
        value=raw.get("value"),
        cost_estimate=raw.get("costEstimate"),
        consumption_rate_band=raw.get("consumptionRateBand"),
    )


def _parse_supply_point(raw: dict[str, Any]) -> ElectricitySupplyPoint:
    return ElectricitySupplyPoint(
        id=raw.get("id") or "",
        spin=raw.get("spin"),
        status=raw.get("status"),
        next_reading_date=raw.get("nextReadingDate"),
        next_next_reading_date=raw.get("nextNextReadingDate"),
        reading_date_day_of_month=raw.get("readingDateDayOfMonth"),
        meters=[_parse_meter(m) for m in (raw.get("meters") or [])],
        agreements=[_parse_agreement(a) for a in (raw.get("agreements") or [])],
        supply_details=[
            _parse_supply_details(details) for details in (raw.get("supplyDetails") or [])
        ],
        supply_periods=[
            _parse_supply_period(period) for period in (raw.get("supplyPeriods") or [])
        ],
        interval_readings=[
            _parse_interval_reading(reading) for reading in (raw.get("intervalReadings") or [])
        ],
        half_hourly_readings=[
            _parse_half_hourly_reading(reading)
            for reading in (raw.get("halfHourlyReadings") or [])
        ],
        interval_readings_access=(
            AccessStatus.authorized("intervalReadings")
            if "intervalReadings" in raw
            else AccessStatus.not_requested("intervalReadings")
        ),
        half_hourly_readings_access=(
            AccessStatus.authorized("halfHourlyReadings")
            if "halfHourlyReadings" in raw
            else AccessStatus.not_requested("halfHourlyReadings")
        ),
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
        typename=raw.get("__typename"),
        created_at=raw.get("createdAt"),
        balance_carried_forward=raw.get("balanceCarriedForward"),
        billing_document_identifier=raw.get("billingDocumentIdentifier"),
        is_issued=raw.get("isIssued"),
        is_held=raw.get("isHeld"),
        is_reversed=raw.get("isReversed"),
        has_statement=raw.get("hasStatement"),
        reason_code=raw.get("reasonCode"),
    )


def _parse_bill(raw: dict[str, Any]) -> Bill:
    return Bill(
        id=raw.get("id") or "",
        typename=raw.get("__typename"),
        bill_type=raw.get("billType"),
        from_date=raw.get("fromDate"),
        to_date=raw.get("toDate"),
        issued_date=raw.get("issuedDate"),
    )


def _parse_market_supply_agreement(raw: dict[str, Any]) -> MarketSupplyAgreement:
    return MarketSupplyAgreement(
        id=str(raw.get("id") or ""),
        valid_from=raw.get("validFrom"),
        valid_to=raw.get("validTo"),
        product=_parse_product(raw.get("product")),
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


def _raw_supply_points(raw_response: dict[str, Any] | None) -> Iterable[dict[str, Any]]:
    if not raw_response:
        return
    data = raw_response.get("data") or {}
    account_raw = data.get("account")
    if isinstance(account_raw, dict):
        accounts = [account_raw]
    else:
        viewer_raw = data.get("viewer") or {}
        accounts = viewer_raw.get("accounts") or []
    for account in accounts:
        for prop in account.get("properties") or []:
            for point in prop.get("electricitySupplyPoints") or []:
                if isinstance(point, dict):
                    yield point


def _supply_points_by_id(
    snapshot: EnergySnapshot,
    account_number: str | None = None,
) -> dict[str, ElectricitySupplyPoint]:
    return {
        point.id: point
        for point in snapshot.iter_account_supply_points(account_number)
        if point.id
    }


def _copy_status(status: AccessStatus) -> AccessStatus:
    return replace(
        status,
        error_codes=list(status.error_codes),
        error_paths=list(status.error_paths),
    )


def apply_interval_readings(
    snapshot: EnergySnapshot,
    raw_response: dict[str, Any] | None,
    access_status: AccessStatus,
    *,
    account_number: str | None = None,
) -> EnergySnapshot:
    """Attach optional interval readings and access status to supply points."""
    for point in snapshot.iter_account_supply_points(account_number):
        point.interval_readings_access = _copy_status(access_status)

    points_by_id = _supply_points_by_id(snapshot, account_number)
    for raw_point in _raw_supply_points(raw_response):
        point = points_by_id.get(raw_point.get("id") or "")
        if point is None:
            continue
        point.interval_readings = [
            _parse_interval_reading(reading)
            for reading in (raw_point.get("intervalReadings") or [])
        ]
        point.interval_readings_access = AccessStatus.authorized("intervalReadings")
    return snapshot


def apply_half_hourly_readings(
    snapshot: EnergySnapshot,
    raw_response: dict[str, Any] | None,
    access_status: AccessStatus,
    *,
    account_number: str | None = None,
) -> EnergySnapshot:
    """Attach optional half-hourly readings and access status to supply points."""
    for point in snapshot.iter_account_supply_points(account_number):
        point.half_hourly_readings_access = _copy_status(access_status)

    points_by_id = _supply_points_by_id(snapshot, account_number)
    for raw_point in _raw_supply_points(raw_response):
        point = points_by_id.get(raw_point.get("id") or "")
        if point is None:
            continue
        point.half_hourly_readings = [
            _parse_half_hourly_reading(reading)
            for reading in (raw_point.get("halfHourlyReadings") or [])
        ]
        point.half_hourly_readings_access = AccessStatus.authorized("halfHourlyReadings")
    return snapshot


def access_status_from_graphql_error(field_name: str, error: BaseException) -> AccessStatus:
    """Build a redacted access status from a GraphQLError-like exception."""
    response_data = getattr(error, "response_data", None) or {}
    errors = response_data.get("errors") or []
    messages = [_clean_message(e.get("message")) for e in errors if e.get("message")]
    codes = [_error_code(e) for e in errors]
    paths = [_error_path(e.get("path")) for e in errors if e.get("path")]
    fallback_message = _clean_message(str(error))
    message = "; ".join(m for m in messages if m) or fallback_message
    status = _classify_access_status(messages, codes, fallback_message)
    return AccessStatus(
        field_name=field_name,
        status=status,
        message=message or None,
        error_codes=[code for code in codes if code],
        error_paths=[path for path in paths if path],
    )


def _error_code(error: dict[str, Any]) -> str | None:
    extensions = error.get("extensions") or {}
    for key in ("errorCode", "code", "errorClass"):
        value = extensions.get(key)
        if value:
            return str(value)
    return None


def _error_path(path: Any) -> str:
    if not isinstance(path, list):
        return str(path)
    return ".".join(str(part) for part in path)


def _clean_message(message: str | None, max_len: int = 200) -> str:
    if not message:
        return ""
    return " ".join(message.split())[:max_len]


def _classify_access_status(
    messages: list[str],
    codes: list[str | None],
    fallback_message: str,
) -> str:
    text = " ".join([*messages, *(c or "" for c in codes), fallback_message]).lower()
    if "disabled graphql field" in text or "disabled" in text or "kt-ct-1113" in text:
        return ACCESS_DISABLED
    if "unauthorized" in text or "not authorized" in text or "kt-ct-1111" in text:
        return ACCESS_UNAUTHORIZED
    return ACCESS_ERROR
