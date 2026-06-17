"""Typed dataclasses for OEJP energy snapshot data."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable
from zoneinfo import ZoneInfo


ACCESS_AUTHORIZED = "authorized"
ACCESS_DISABLED = "disabled"
ACCESS_ERROR = "error"
ACCESS_NOT_REQUESTED = "not_requested"
ACCESS_UNAUTHORIZED = "unauthorized"
AGGREGATE_PERIOD_TODAY = "today"
AGGREGATE_PERIOD_THIS_WEEK = "this_week"
AGGREGATE_PERIOD_THIS_MONTH = "this_month"
HALF_HOURLY_AGGREGATE_PERIODS = (
    AGGREGATE_PERIOD_TODAY,
    AGGREGATE_PERIOD_THIS_WEEK,
    AGGREGATE_PERIOD_THIS_MONTH,
)
HALF_HOURLY_READINGS_SOURCE = "halfHourlyReadings"
INTERVAL_READINGS_SOURCE = "intervalReadings"
JPY_CURRENCY = "JPY"
JST = ZoneInfo("Asia/Tokyo")
HALF_HOUR_HOURS = Decimal("0.5")
WATTS_PER_KILOWATT = Decimal("1000")


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


@dataclass(frozen=True)
class HalfHourlyReadingAggregate:
    """Aggregated half-hourly consumption/cost for a single current period."""

    start: datetime
    end: datetime
    reading_count: int
    total_consumption: float
    total_cost: float | None
    currency: str = JPY_CURRENCY
    source: str = HALF_HOURLY_READINGS_SOURCE

    def as_attributes(self) -> dict[str, Any]:
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "reading_count": self.reading_count,
            "total_consumption": self.total_consumption,
            "total_cost": self.total_cost,
            "currency": self.currency,
            "source": self.source,
        }


@dataclass(frozen=True)
class CumulativeReadingAggregate:
    """Cumulative consumption/cost across all available interval and half-hourly readings.

    All intervalReadings are summed as confirmed billing periods. Half-hourly
    readings whose start_at >= the latest interval reading end_at (falling back
    to reading_date as JST midnight when end_at is absent) are then added to
    extend coverage without double-counting. When no interval readings exist all
    halfHourlyReadings are included directly.
    """

    total_consumption: float
    total_cost: float | None
    currency: str
    interval_reading_count: int
    half_hourly_reading_count: int
    reading_count: int
    start: datetime | None
    latest_confirmed_end: datetime | None
    cost_note: str | None

    def as_attributes(self) -> dict[str, Any]:
        sources: list[str] = []
        if self.interval_reading_count > 0:
            sources.append(INTERVAL_READINGS_SOURCE)
        if self.half_hourly_reading_count > 0:
            sources.append(HALF_HOURLY_READINGS_SOURCE)
        attrs: dict[str, Any] = {
            "sources": sources,
            "reading_count": self.reading_count,
            "interval_reading_count": self.interval_reading_count,
            "half_hourly_reading_count": self.half_hourly_reading_count,
            "total_consumption": self.total_consumption,
            "total_cost": self.total_cost,
            "currency": self.currency,
        }
        if self.start is not None:
            attrs["start"] = self.start.isoformat()
        if self.latest_confirmed_end is not None:
            attrs["latest_confirmed_end"] = self.latest_confirmed_end.isoformat()
        if self.cost_note is not None:
            attrs["cost_note"] = self.cost_note
        return attrs


@dataclass(frozen=True)
class LatestHalfHourlyDerivedAttributes:
    """Attributes for values derived from the latest half-hourly reading."""

    calculation: str
    note: str
    source: str = HALF_HOURLY_READINGS_SOURCE
    source_reading_start: str | None = None
    source_reading_end: str | None = None
    source_value_kwh: float | None = None
    source_cost_jpy: float | None = None
    currency: str | None = None

    def as_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {
            "source": self.source,
            "calculation": self.calculation,
            "note": self.note,
        }
        if self.source_reading_start is not None:
            attrs["source_reading_start"] = self.source_reading_start
        if self.source_reading_end is not None:
            attrs["source_reading_end"] = self.source_reading_end
        if self.source_value_kwh is not None:
            attrs["source_value_kwh"] = self.source_value_kwh
        if self.source_cost_jpy is not None:
            attrs["source_cost_jpy"] = self.source_cost_jpy
        if self.currency is not None:
            attrs["currency"] = self.currency
        return attrs


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


def _as_jst(value: datetime | None = None) -> datetime:
    if value is None:
        value = datetime.now(JST)
    if value.tzinfo is None:
        value = value.replace(tzinfo=JST)
    return value.astimezone(JST).replace(microsecond=0)


def current_half_hourly_periods(
    now: datetime | None = None,
) -> dict[str, tuple[datetime, datetime]]:
    """Return current day/week/month boundaries in JST.

    The week period starts on Monday, matching the default cost-tracker pattern.
    """

    local_now = _as_jst(now)
    today_start = datetime.combine(local_now.date(), time.min, tzinfo=JST)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)
    if month_start.month == 12:
        next_month_start = month_start.replace(year=month_start.year + 1, month=1)
    else:
        next_month_start = month_start.replace(month=month_start.month + 1)
    return {
        AGGREGATE_PERIOD_TODAY: (today_start, today_start + timedelta(days=1)),
        AGGREGATE_PERIOD_THIS_WEEK: (week_start, week_start + timedelta(days=7)),
        AGGREGATE_PERIOD_THIS_MONTH: (month_start, next_month_start),
    }


def current_half_hourly_fetch_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    """Return the smallest half-hourly fetch window needed for all current aggregates."""

    periods = current_half_hourly_periods(now)
    from_datetime = min(start for start, _ in periods.values())
    to_datetime = _as_jst(now)
    return from_datetime, to_datetime


def aggregate_supply_point_half_hourly_readings(
    point: ElectricitySupplyPoint,
    period: str,
    *,
    now: datetime | None = None,
) -> HalfHourlyReadingAggregate:
    """Aggregate one supply point's half-hourly readings for a current JST period."""

    periods = current_half_hourly_periods(now)
    try:
        start, end = periods[period]
    except KeyError as exc:
        raise ValueError(f"Unknown half-hourly aggregate period: {period}") from exc
    return aggregate_half_hourly_readings(point.half_hourly_readings, start=start, end=end)


def aggregate_supply_point_half_hourly_periods(
    point: ElectricitySupplyPoint,
    *,
    now: datetime | None = None,
) -> dict[str, HalfHourlyReadingAggregate]:
    """Aggregate one supply point's half-hourly readings for all current periods."""

    return {
        period: aggregate_supply_point_half_hourly_readings(point, period, now=now)
        for period in HALF_HOURLY_AGGREGATE_PERIODS
    }


def aggregate_half_hourly_readings(
    readings: Iterable[ElectricityHalfHourReading],
    *,
    start: datetime,
    end: datetime,
) -> HalfHourlyReadingAggregate:
    """Aggregate half-hourly readings that start within ``[start, end)`` in JST."""

    start = _as_jst(start)
    end = _as_jst(end)
    total_consumption = Decimal("0")
    total_cost = Decimal("0")
    cost_complete = True
    reading_count = 0

    for reading in readings:
        reading_start = _parse_reading_datetime(reading.start_at)
        if reading_start is None or not start <= reading_start < end:
            continue
        reading_count += 1

        consumption = _decimal_or_none(reading.value)
        if consumption is not None:
            total_consumption += consumption

        cost = _decimal_or_none(reading.cost_estimate)
        if cost is None:
            cost_complete = False
        else:
            total_cost += cost

    return HalfHourlyReadingAggregate(
        start=start,
        end=end,
        reading_count=reading_count,
        total_consumption=float(total_consumption),
        total_cost=float(total_cost) if cost_complete else None,
    )


def aggregate_supply_point_cumulative_readings(
    point: ElectricitySupplyPoint,
) -> CumulativeReadingAggregate:
    """Aggregate all available readings as a running cumulative total.

    All intervalReadings are summed first as confirmed billing periods.
    halfHourlyReadings whose start_at >= the latest interval reading end_at
    (falling back to reading_date as JST midnight) are then added without
    double-counting. When no interval readings exist, all halfHourlyReadings
    are included directly.
    """
    interval_consumption = Decimal("0")
    interval_cost = Decimal("0")
    interval_cost_complete = True
    interval_missing = 0
    interval_count = 0
    earliest_start: datetime | None = None
    latest_confirmed_end: datetime | None = None

    for reading in point.interval_readings:
        consumption = _decimal_or_none(reading.value)
        if consumption is None:
            continue
        interval_count += 1
        interval_consumption += consumption

        cost = _decimal_or_none(reading.cost_estimate)
        if cost is None:
            interval_cost_complete = False
            interval_missing += 1
        else:
            interval_cost += cost

        start = _parse_reading_datetime(reading.start_at)
        if start is not None and (earliest_start is None or start < earliest_start):
            earliest_start = start

        end = _parse_reading_datetime(reading.end_at) or _parse_reading_date_as_jst(
            reading.reading_date
        )
        if end is not None and (latest_confirmed_end is None or end > latest_confirmed_end):
            latest_confirmed_end = end

    hh_consumption = Decimal("0")
    hh_cost = Decimal("0")
    hh_cost_complete = True
    hh_missing = 0
    hh_count = 0

    for reading in point.half_hourly_readings:
        start = _parse_reading_datetime(reading.start_at)
        if start is None:
            continue
        if latest_confirmed_end is not None and start < latest_confirmed_end:
            continue  # already covered by interval readings

        consumption = _decimal_or_none(reading.value)
        if consumption is None:
            continue
        hh_count += 1
        hh_consumption += consumption

        cost = _decimal_or_none(reading.cost_estimate)
        if cost is None:
            hh_cost_complete = False
            hh_missing += 1
        else:
            hh_cost += cost

        if interval_count == 0 and (earliest_start is None or start < earliest_start):
            earliest_start = start

    total_count = interval_count + hh_count
    total_missing = interval_missing + hh_missing
    if total_count == 0:
        total_cost: float | None = None
        cost_note = None
    elif interval_cost_complete and hh_cost_complete:
        total_cost = float(interval_cost + hh_cost)
        cost_note = None
    else:
        total_cost = None
        cost_note = f"cost unavailable: {total_missing} reading(s) missing costEstimate"

    return CumulativeReadingAggregate(
        total_consumption=float(interval_consumption + hh_consumption),
        total_cost=total_cost,
        currency=JPY_CURRENCY,
        interval_reading_count=interval_count,
        half_hourly_reading_count=hh_count,
        reading_count=total_count,
        start=earliest_start,
        latest_confirmed_end=latest_confirmed_end,
        cost_note=cost_note,
    )


def latest_half_hourly_average_power_watts(point: ElectricitySupplyPoint) -> float | None:
    """Return W from the latest half-hourly kWh reading, or ``None`` if unavailable."""

    reading = point.latest_half_hourly_reading
    if reading is None:
        return None

    consumption_kwh = _decimal_or_none(reading.value)
    if consumption_kwh is None:
        return None

    return float(consumption_kwh / HALF_HOUR_HOURS * WATTS_PER_KILOWATT)


def latest_half_hourly_average_cost_rate_jpy_per_kwh(
    point: ElectricitySupplyPoint,
) -> float | None:
    """Return JPY/kWh from the latest half-hourly cost/value, or ``None``."""

    reading = point.latest_half_hourly_reading
    if reading is None:
        return None

    consumption_kwh = _decimal_or_none(reading.value)
    if consumption_kwh is None or consumption_kwh == 0:
        return None

    cost_jpy = _decimal_or_none(reading.cost_estimate)
    if cost_jpy is None:
        return None

    return float(cost_jpy / consumption_kwh)


def latest_half_hourly_average_power_attributes(
    point: ElectricitySupplyPoint,
) -> dict[str, Any]:
    """Attributes for the latest half-hour average power derived sensor."""

    return _latest_half_hourly_derived_attributes(
        point,
        calculation="latest half-hour reading value kWh / 0.5h converted to W",
        note="Average power over the latest half-hour reading; not instantaneous live power.",
    ).as_attributes()


def latest_half_hourly_average_cost_rate_attributes(
    point: ElectricitySupplyPoint,
) -> dict[str, Any]:
    """Attributes for the latest half-hour average cost-rate derived sensor."""

    return _latest_half_hourly_derived_attributes(
        point,
        calculation="latest half-hour reading costEstimate / latest half-hour reading value",
        note="Effective cost rate derived from the latest half-hour reading cost and value.",
        include_cost=True,
        currency=JPY_CURRENCY,
    ).as_attributes()


def _latest_half_hourly_derived_attributes(
    point: ElectricitySupplyPoint,
    *,
    calculation: str,
    note: str,
    include_cost: bool = False,
    currency: str | None = None,
) -> LatestHalfHourlyDerivedAttributes:
    reading = point.latest_half_hourly_reading
    if reading is None:
        return LatestHalfHourlyDerivedAttributes(
            calculation=calculation,
            note=note,
            currency=currency,
        )

    consumption_kwh = _decimal_or_none(reading.value)
    cost_jpy = _decimal_or_none(reading.cost_estimate) if include_cost else None
    return LatestHalfHourlyDerivedAttributes(
        calculation=calculation,
        note=note,
        source_reading_start=reading.start_at,
        source_reading_end=reading.end_at,
        source_value_kwh=None if consumption_kwh is None else float(consumption_kwh),
        source_cost_jpy=None if cost_jpy is None else float(cost_jpy),
        currency=currency,
    )


def _parse_reading_date_as_jst(value: str | None) -> datetime | None:
    """Parse a plain date string (YYYY-MM-DD) as JST midnight."""
    if not value:
        return None
    try:
        from datetime import date as _date
        d = _date.fromisoformat(value)
        return datetime.combine(d, time.min, tzinfo=JST)
    except ValueError:
        return None


def _parse_reading_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return _as_jst(parsed)


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not result.is_finite():
        return None
    return result


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
