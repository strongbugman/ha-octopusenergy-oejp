"""Tests for dataclass parsing in models.py."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from tests.conftest import SAMPLE_SNAPSHOT_RESPONSE
from custom_components.octopusenergy_oejp.models import (
    ACCESS_AUTHORIZED,
    ACCESS_UNAUTHORIZED,
    AGGREGATE_PERIOD_THIS_MONTH,
    AGGREGATE_PERIOD_THIS_WEEK,
    AGGREGATE_PERIOD_TODAY,
    AccessStatus,
    Account,
    Agreement,
    Bill,
    CumulativeReadingAggregate,
    ElectricityHalfHourReading,
    ElectricityIntervalReading,
    ElectricitySupplyPoint,
    EnergySnapshot,
    MarketSupplyAgreement,
    Meter,
    Property,
    Transaction,
    Viewer,
    access_status_from_graphql_error,
    aggregate_supply_point_cumulative_readings,
    aggregate_supply_point_half_hourly_readings,
    apply_half_hourly_readings,
    apply_interval_readings,
    current_half_hourly_fetch_window,
    current_half_hourly_periods,
    latest_half_hourly_average_cost_rate_attributes,
    latest_half_hourly_average_cost_rate_jpy_per_kwh,
    latest_half_hourly_average_power_attributes,
    latest_half_hourly_average_power_watts,
    parse_energy_snapshot,
)

JST = ZoneInfo("Asia/Tokyo")


def test_parse_viewer_id():
    snapshot = parse_energy_snapshot(SAMPLE_SNAPSHOT_RESPONSE)
    assert isinstance(snapshot, EnergySnapshot)
    assert isinstance(snapshot.viewer, Viewer)
    assert snapshot.viewer.id == "VWR-001"


def test_parse_account_fields():
    account = parse_energy_snapshot(SAMPLE_SNAPSHOT_RESPONSE).viewer.accounts[0]
    assert isinstance(account, Account)
    assert account.number == "A-1234567"
    assert account.status == "ACTIVE"
    assert account.balance == 1500


def test_parse_account_transaction_totals():
    account = parse_energy_snapshot(SAMPLE_SNAPSHOT_RESPONSE).viewer.accounts[0]
    assert account.transactions_total == 42
    assert len(account.transactions_sample) == 1
    txn = account.transactions_sample[0]
    assert isinstance(txn, Transaction)
    assert txn.id == "T-001"
    assert txn.posted_date == "2024-01-15"
    assert txn.amount == -500
    assert txn.title == "Payment"


def test_parse_account_bill_totals():
    account = parse_energy_snapshot(SAMPLE_SNAPSHOT_RESPONSE).viewer.accounts[0]
    assert account.bills_total == 12
    assert len(account.bills_sample) == 1
    assert isinstance(account.bills_sample[0], Bill)
    assert account.bills_sample[0].id == "B-001"


def test_parse_property():
    prop = parse_energy_snapshot(SAMPLE_SNAPSHOT_RESPONSE).viewer.accounts[0].properties[0]
    assert isinstance(prop, Property)
    assert prop.id == "P-001"
    assert prop.postcode == "100-0001"
    assert prop.address == "Tokyo, Chiyoda 1-1"


def test_parse_electricity_supply_point():
    point = (
        parse_energy_snapshot(SAMPLE_SNAPSHOT_RESPONSE)
        .viewer.accounts[0].properties[0].electricity_supply_points[0]
    )
    assert isinstance(point, ElectricitySupplyPoint)
    assert point.id == "ESP-001"
    assert point.spin == "SP-0001"
    assert point.status == "ACTIVE"


def test_parse_meter():
    point = (
        parse_energy_snapshot(SAMPLE_SNAPSHOT_RESPONSE)
        .viewer.accounts[0].properties[0].electricity_supply_points[0]
    )
    assert len(point.meters) == 1
    assert isinstance(point.meters[0], Meter)
    assert point.meters[0].serial_number == "M-0001"


def test_parse_agreement():
    point = (
        parse_energy_snapshot(SAMPLE_SNAPSHOT_RESPONSE)
        .viewer.accounts[0].properties[0].electricity_supply_points[0]
    )
    assert len(point.agreements) == 1
    agr = point.agreements[0]
    assert isinstance(agr, Agreement)
    assert agr.id == "AGR-001"
    assert agr.valid_from == "2023-04-01"
    assert agr.valid_to is None
    assert agr.product_typename == "HalfHourlyTariff"


def test_parse_market_supply_agreements():
    account = parse_energy_snapshot(SAMPLE_SNAPSHOT_RESPONSE).viewer.accounts[0]
    assert account.market_supply_agreements_total == 2
    assert len(account.market_supply_agreements_sample) == 1
    msa = account.market_supply_agreements_sample[0]
    assert isinstance(msa, MarketSupplyAgreement)
    assert msa.id == "MSA-001"
    assert msa.product_typename == "OctogonerTariff"


def test_snapshot_computed_counts():
    snapshot = parse_energy_snapshot(SAMPLE_SNAPSHOT_RESPONSE)
    assert snapshot.account_count == 1
    assert snapshot.property_count == 1
    assert snapshot.supply_point_count == 1
    assert snapshot.bills_total == 12
    assert snapshot.transactions_total == 42
    # 2 market supply agreements + 1 point agreement
    assert snapshot.active_agreement_count == 3


def test_parse_empty_viewer():
    raw = {"data": {"viewer": {"id": "X", "accounts": []}}}
    snapshot = parse_energy_snapshot(raw)
    assert snapshot.account_count == 0
    assert snapshot.property_count == 0
    assert snapshot.supply_point_count == 0
    assert snapshot.bills_total == 0
    assert snapshot.transactions_total == 0
    assert snapshot.active_agreement_count == 0


def test_parse_missing_data_keys():
    raw: dict = {"data": {}}
    snapshot = parse_energy_snapshot(raw)
    assert snapshot.viewer.id == ""
    assert snapshot.account_count == 0


def test_parse_account_with_no_properties():
    raw = {
        "data": {
            "viewer": {
                "id": "V",
                "accounts": [
                    {
                        "number": "A-999",
                        "status": "INACTIVE",
                        "balance": 0,
                        "transactions": {"totalCount": 0, "edges": []},
                        "bills": {"totalCount": 0, "edges": []},
                        "marketSupplyAgreements": {"totalCount": 0, "edges": []},
                    }
                ],
            }
        }
    }
    snapshot = parse_energy_snapshot(raw)
    assert snapshot.account_count == 1
    assert snapshot.property_count == 0
    assert snapshot.supply_point_count == 0


def test_parse_reading_schedule_fields():
    point = (
        parse_energy_snapshot(SAMPLE_SNAPSHOT_RESPONSE)
        .viewer.accounts[0].properties[0].electricity_supply_points[0]
    )
    assert point.next_reading_date is None
    assert point.next_next_reading_date is None
    assert point.reading_date_day_of_month is None
    assert point.meter_count == 1


def test_apply_interval_readings_authorized():
    snapshot = parse_energy_snapshot(SAMPLE_SNAPSHOT_RESPONSE)
    raw = {
        "data": {
            "viewer": {
                "accounts": [
                    {
                        "properties": [
                            {
                                "electricitySupplyPoints": [
                                    {
                                        "id": "ESP-001",
                                        "intervalReadings": [
                                            {
                                                "readingDate": "2026-05-15",
                                                "startAt": "2026-04-15T00:00:00+09:00",
                                                "endAt": "2026-05-15T00:00:00+09:00",
                                                "value": "123.45",
                                                "costEstimate": "4567",
                                                "hasHalfHourlyDataForPeriod": True,
                                            }
                                        ],
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        }
    }

    apply_interval_readings(snapshot, raw, AccessStatus.authorized("intervalReadings"))
    point = next(snapshot.iter_supply_points())
    assert point.interval_readings_access.status == ACCESS_AUTHORIZED
    assert point.latest_interval_reading is not None
    assert point.latest_interval_reading.value == "123.45"
    assert point.latest_interval_reading.cost_estimate == "4567"


def test_apply_half_hourly_readings_authorized():
    snapshot = parse_energy_snapshot(SAMPLE_SNAPSHOT_RESPONSE)
    raw = {
        "data": {
            "viewer": {
                "accounts": [
                    {
                        "properties": [
                            {
                                "electricitySupplyPoints": [
                                    {
                                        "id": "ESP-001",
                                        "halfHourlyReadings": [
                                            {
                                                "startAt": "2026-05-15T10:00:00+09:00",
                                                "endAt": "2026-05-15T10:30:00+09:00",
                                                "value": "0.42",
                                                "costEstimate": "12.3",
                                                "consumptionRateBand": "standard",
                                            }
                                        ],
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        }
    }

    apply_half_hourly_readings(snapshot, raw, AccessStatus.authorized("halfHourlyReadings"))
    point = next(snapshot.iter_supply_points())
    assert point.half_hourly_readings_access.status == ACCESS_AUTHORIZED
    assert point.latest_half_hourly_reading is not None
    assert point.latest_half_hourly_reading.value == "0.42"


def test_current_half_hourly_period_boundaries_are_jst():
    now = datetime(2026, 6, 17, 12, 34, 56, tzinfo=JST)
    periods = current_half_hourly_periods(now)

    assert periods[AGGREGATE_PERIOD_TODAY][0].isoformat() == "2026-06-17T00:00:00+09:00"
    assert periods[AGGREGATE_PERIOD_TODAY][1].isoformat() == "2026-06-18T00:00:00+09:00"
    assert periods[AGGREGATE_PERIOD_THIS_WEEK][0].isoformat() == "2026-06-15T00:00:00+09:00"
    assert periods[AGGREGATE_PERIOD_THIS_MONTH][0].isoformat() == "2026-06-01T00:00:00+09:00"


def test_current_half_hourly_fetch_window_covers_week_before_month_start():
    now = datetime(2026, 7, 1, 12, 0, tzinfo=JST)
    start, end = current_half_hourly_fetch_window(now)

    assert start.isoformat() == "2026-06-29T00:00:00+09:00"
    assert end.isoformat() == "2026-07-01T12:00:00+09:00"


def test_aggregate_half_hourly_readings_by_current_periods():
    snapshot = parse_energy_snapshot(SAMPLE_SNAPSHOT_RESPONSE)
    point = next(snapshot.iter_supply_points())
    point.half_hourly_readings = [
        ElectricityHalfHourReading(
            "2026-06-17T00:00:00+09:00",
            "2026-06-17T00:30:00+09:00",
            "0.5",
            "15.2",
            "standard",
        ),
        ElectricityHalfHourReading(
            "2026-06-16T23:30:00+09:00",
            "2026-06-17T00:00:00+09:00",
            "0.4",
            "12",
            "standard",
        ),
        ElectricityHalfHourReading(
            "2026-06-14T23:30:00+09:00",
            "2026-06-15T00:00:00+09:00",
            "0.3",
            "9",
            "standard",
        ),
    ]

    now = datetime(2026, 6, 17, 12, 0, tzinfo=JST)
    today = aggregate_supply_point_half_hourly_readings(
        point, AGGREGATE_PERIOD_TODAY, now=now
    )
    week = aggregate_supply_point_half_hourly_readings(
        point, AGGREGATE_PERIOD_THIS_WEEK, now=now
    )
    month = aggregate_supply_point_half_hourly_readings(
        point, AGGREGATE_PERIOD_THIS_MONTH, now=now
    )

    assert today.reading_count == 1
    assert today.total_consumption == pytest.approx(0.5)
    assert today.total_cost == pytest.approx(15.2)
    assert week.reading_count == 2
    assert week.total_consumption == pytest.approx(0.9)
    assert week.total_cost == pytest.approx(27.2)
    assert month.reading_count == 3
    assert month.total_consumption == pytest.approx(1.2)
    assert month.total_cost == pytest.approx(36.2)
    assert today.as_attributes()["source"] == "halfHourlyReadings"
    assert today.as_attributes()["currency"] == "JPY"


def test_aggregate_uses_jst_boundary_for_utc_readings():
    snapshot = parse_energy_snapshot(SAMPLE_SNAPSHOT_RESPONSE)
    point = next(snapshot.iter_supply_points())
    point.half_hourly_readings = [
        ElectricityHalfHourReading(
            "2026-06-16T15:30:00+00:00",
            "2026-06-16T16:00:00+00:00",
            "0.7",
            "21",
            "standard",
        ),
        ElectricityHalfHourReading(
            "2026-06-16T14:30:00+00:00",
            "2026-06-16T15:00:00+00:00",
            "0.9",
            "27",
            "standard",
        ),
    ]

    aggregate = aggregate_supply_point_half_hourly_readings(
        point,
        AGGREGATE_PERIOD_TODAY,
        now=datetime(2026, 6, 17, 12, 0, tzinfo=JST),
    )

    assert aggregate.reading_count == 1
    assert aggregate.total_consumption == pytest.approx(0.7)
    assert aggregate.total_cost == pytest.approx(21)


def test_aggregate_cost_is_none_when_any_cost_estimate_missing():
    snapshot = parse_energy_snapshot(SAMPLE_SNAPSHOT_RESPONSE)
    point = next(snapshot.iter_supply_points())
    point.half_hourly_readings = [
        ElectricityHalfHourReading(
            "2026-06-17T00:00:00+09:00",
            "2026-06-17T00:30:00+09:00",
            "0.5",
            None,
            "standard",
        )
    ]

    aggregate = aggregate_supply_point_half_hourly_readings(
        point,
        AGGREGATE_PERIOD_TODAY,
        now=datetime(2026, 6, 17, 12, 0, tzinfo=JST),
    )

    assert aggregate.reading_count == 1
    assert aggregate.total_consumption == pytest.approx(0.5)
    assert aggregate.total_cost is None


def test_latest_half_hourly_average_power_uses_latest_numeric_value():
    snapshot = parse_energy_snapshot(SAMPLE_SNAPSHOT_RESPONSE)
    point = next(snapshot.iter_supply_points())
    point.half_hourly_readings = [
        ElectricityHalfHourReading(
            "2026-06-17T00:00:00+09:00",
            "2026-06-17T00:30:00+09:00",
            "0.25",
            "7.5",
            "standard",
        ),
        ElectricityHalfHourReading(
            "2026-06-17T00:30:00+09:00",
            "2026-06-17T01:00:00+09:00",
            "0.42",
            "12.3",
            "standard",
        ),
    ]

    assert latest_half_hourly_average_power_watts(point) == pytest.approx(840.0)
    attrs = latest_half_hourly_average_power_attributes(point)
    assert attrs["source"] == "halfHourlyReadings"
    assert attrs["source_reading_start"] == "2026-06-17T00:30:00+09:00"
    assert attrs["source_reading_end"] == "2026-06-17T01:00:00+09:00"
    assert attrs["source_value_kwh"] == 0.42
    assert "not instantaneous live power" in attrs["note"]


@pytest.mark.parametrize("reading_value", [None, "", "not-a-number"])
def test_latest_half_hourly_average_power_none_when_value_missing_or_non_numeric(reading_value):
    snapshot = parse_energy_snapshot(SAMPLE_SNAPSHOT_RESPONSE)
    point = next(snapshot.iter_supply_points())
    point.half_hourly_readings = [
        ElectricityHalfHourReading(
            "2026-06-17T00:30:00+09:00",
            "2026-06-17T01:00:00+09:00",
            reading_value,
            "12.3",
            "standard",
        )
    ]

    assert latest_half_hourly_average_power_watts(point) is None


def test_latest_half_hourly_average_cost_rate_uses_latest_cost_and_value():
    snapshot = parse_energy_snapshot(SAMPLE_SNAPSHOT_RESPONSE)
    point = next(snapshot.iter_supply_points())
    point.half_hourly_readings = [
        ElectricityHalfHourReading(
            "2026-06-17T00:30:00+09:00",
            "2026-06-17T01:00:00+09:00",
            "0.5",
            "15",
            "standard",
        )
    ]

    assert latest_half_hourly_average_cost_rate_jpy_per_kwh(point) == pytest.approx(30.0)
    attrs = latest_half_hourly_average_cost_rate_attributes(point)
    assert attrs["source"] == "halfHourlyReadings"
    assert attrs["source_reading_start"] == "2026-06-17T00:30:00+09:00"
    assert attrs["source_value_kwh"] == 0.5
    assert attrs["source_cost_jpy"] == 15.0
    assert attrs["currency"] == "JPY"
    assert "costEstimate" in attrs["calculation"]


@pytest.mark.parametrize(
    ("reading_value", "cost_estimate"),
    [
        ("0", "15"),
        (None, "15"),
        ("0.5", None),
        ("not-a-number", "15"),
        ("0.5", "not-a-number"),
    ],
)
def test_latest_half_hourly_average_cost_rate_none_when_inputs_invalid(
    reading_value,
    cost_estimate,
):
    snapshot = parse_energy_snapshot(SAMPLE_SNAPSHOT_RESPONSE)
    point = next(snapshot.iter_supply_points())
    point.half_hourly_readings = [
        ElectricityHalfHourReading(
            "2026-06-17T00:30:00+09:00",
            "2026-06-17T01:00:00+09:00",
            reading_value,
            cost_estimate,
            "standard",
        )
    ]

    assert latest_half_hourly_average_cost_rate_jpy_per_kwh(point) is None


def test_latest_half_hourly_derived_values_none_when_no_reading():
    snapshot = parse_energy_snapshot(SAMPLE_SNAPSHOT_RESPONSE)
    point = next(snapshot.iter_supply_points())
    point.half_hourly_readings = []

    assert latest_half_hourly_average_power_watts(point) is None
    assert latest_half_hourly_average_cost_rate_jpy_per_kwh(point) is None
    attrs = latest_half_hourly_average_power_attributes(point)
    assert attrs["source"] == "halfHourlyReadings"
    assert "source_reading_start" not in attrs


def test_access_status_from_unauthorized_graphql_error():
    class FakeGraphQLError(Exception):
        response_data = {
            "errors": [
                {
                    "message": "Unauthorized.",
                    "path": ["viewer", "accounts", 0, "intervalReadings"],
                    "extensions": {"errorCode": "KT-CT-4501"},
                }
            ]
        }

    status = access_status_from_graphql_error("intervalReadings", FakeGraphQLError("GraphQL returned errors"))
    assert status.status == ACCESS_UNAUTHORIZED
    assert status.error_codes == ["KT-CT-4501"]
    assert status.error_paths == ["viewer.accounts.0.intervalReadings"]


def test_apply_readings_skips_null_partial_payload_points():
    snapshot = parse_energy_snapshot(SAMPLE_SNAPSHOT_RESPONSE)
    raw = {"data": {"viewer": {"accounts": [{"properties": [{"electricitySupplyPoints": [None]}]}]}}}
    status = AccessStatus(field_name="intervalReadings", status=ACCESS_UNAUTHORIZED)
    apply_interval_readings(snapshot, raw, status)
    point = next(snapshot.iter_supply_points())
    assert point.interval_readings == []
    assert point.interval_readings_access.status == ACCESS_UNAUTHORIZED


# ---------------------------------------------------------------------------
# Cumulative reading aggregate tests
# ---------------------------------------------------------------------------

def test_aggregate_cumulative_sums_all_interval_readings():
    snapshot = parse_energy_snapshot(SAMPLE_SNAPSHOT_RESPONSE)
    point = next(snapshot.iter_supply_points())
    point.interval_readings = [
        ElectricityIntervalReading(
            "2026-04-15", "2026-03-15T00:00:00+09:00", "2026-04-15T00:00:00+09:00",
            "100.0", "3000", True,
        ),
        ElectricityIntervalReading(
            "2026-05-15", "2026-04-15T00:00:00+09:00", "2026-05-15T00:00:00+09:00",
            "120.0", "3600", True,
        ),
    ]
    point.half_hourly_readings = []

    agg = aggregate_supply_point_cumulative_readings(point)

    assert agg.interval_reading_count == 2
    assert agg.half_hourly_reading_count == 0
    assert agg.reading_count == 2
    assert agg.total_consumption == pytest.approx(220.0)
    assert agg.total_cost == pytest.approx(6600.0)
    assert agg.currency == "JPY"
    assert agg.cost_note is None
    assert agg.start.isoformat() == "2026-03-15T00:00:00+09:00"
    assert agg.latest_confirmed_end.isoformat() == "2026-05-15T00:00:00+09:00"

    attrs = agg.as_attributes()
    assert "intervalReadings" in attrs["sources"]
    assert "halfHourlyReadings" not in attrs["sources"]
    assert attrs["interval_reading_count"] == 2
    assert attrs["half_hourly_reading_count"] == 0
    assert attrs["reading_count"] == 2
    assert attrs["latest_confirmed_end"] == "2026-05-15T00:00:00+09:00"
    assert attrs["start"] == "2026-03-15T00:00:00+09:00"
    assert "cost_note" not in attrs


def test_aggregate_cumulative_appends_hh_after_interval_boundary():
    snapshot = parse_energy_snapshot(SAMPLE_SNAPSHOT_RESPONSE)
    point = next(snapshot.iter_supply_points())
    point.interval_readings = [
        ElectricityIntervalReading(
            "2026-05-15", "2026-04-15T00:00:00+09:00", "2026-05-15T00:00:00+09:00",
            "100.0", "3000", True,
        ),
    ]
    # start < end_at of interval → excluded (covered by interval billing period)
    # start == end_at of interval → included (first open period)
    # start > end_at of interval → included
    point.half_hourly_readings = [
        ElectricityHalfHourReading(
            "2026-05-14T23:00:00+09:00", "2026-05-14T23:30:00+09:00",
            "0.5", "15", "standard",
        ),
        ElectricityHalfHourReading(
            "2026-05-15T00:00:00+09:00", "2026-05-15T00:30:00+09:00",
            "0.4", "12", "standard",
        ),
        ElectricityHalfHourReading(
            "2026-05-15T12:00:00+09:00", "2026-05-15T12:30:00+09:00",
            "0.3", "9", "standard",
        ),
    ]

    agg = aggregate_supply_point_cumulative_readings(point)

    assert agg.interval_reading_count == 1
    assert agg.half_hourly_reading_count == 2
    assert agg.reading_count == 3
    assert agg.total_consumption == pytest.approx(100.7)
    assert agg.total_cost == pytest.approx(3021.0)
    assert agg.latest_confirmed_end.isoformat() == "2026-05-15T00:00:00+09:00"
    attrs = agg.as_attributes()
    assert "intervalReadings" in attrs["sources"]
    assert "halfHourlyReadings" in attrs["sources"]


def test_aggregate_cumulative_uses_all_hh_when_no_interval_readings():
    snapshot = parse_energy_snapshot(SAMPLE_SNAPSHOT_RESPONSE)
    point = next(snapshot.iter_supply_points())
    point.interval_readings = []
    point.half_hourly_readings = [
        ElectricityHalfHourReading(
            "2026-05-01T00:00:00+09:00", "2026-05-01T00:30:00+09:00",
            "0.5", "15", "standard",
        ),
        ElectricityHalfHourReading(
            "2026-05-01T00:30:00+09:00", "2026-05-01T01:00:00+09:00",
            "0.6", "18", "standard",
        ),
    ]

    agg = aggregate_supply_point_cumulative_readings(point)

    assert agg.interval_reading_count == 0
    assert agg.half_hourly_reading_count == 2
    assert agg.reading_count == 2
    assert agg.total_consumption == pytest.approx(1.1)
    assert agg.total_cost == pytest.approx(33.0)
    assert agg.latest_confirmed_end is None
    assert agg.start.isoformat() == "2026-05-01T00:00:00+09:00"
    attrs = agg.as_attributes()
    assert "intervalReadings" not in attrs["sources"]
    assert "halfHourlyReadings" in attrs["sources"]
    assert "latest_confirmed_end" not in attrs


def test_aggregate_cumulative_cost_note_when_cost_missing():
    snapshot = parse_energy_snapshot(SAMPLE_SNAPSHOT_RESPONSE)
    point = next(snapshot.iter_supply_points())
    point.interval_readings = [
        ElectricityIntervalReading(
            "2026-05-15", "2026-04-15T00:00:00+09:00", "2026-05-15T00:00:00+09:00",
            "100.0", None, True,
        ),
    ]
    point.half_hourly_readings = []

    agg = aggregate_supply_point_cumulative_readings(point)

    assert agg.total_consumption == pytest.approx(100.0)
    assert agg.total_cost is None
    assert agg.cost_note is not None
    assert "1 reading(s) missing costEstimate" in agg.cost_note
    attrs = agg.as_attributes()
    assert "cost_note" in attrs
    assert attrs["total_cost"] is None


def test_aggregate_cumulative_empty_readings():
    snapshot = parse_energy_snapshot(SAMPLE_SNAPSHOT_RESPONSE)
    point = next(snapshot.iter_supply_points())
    point.interval_readings = []
    point.half_hourly_readings = []

    agg = aggregate_supply_point_cumulative_readings(point)

    assert agg.reading_count == 0
    assert agg.total_consumption == pytest.approx(0.0)
    assert agg.total_cost is None
    assert agg.cost_note is None
    assert agg.start is None
    assert agg.latest_confirmed_end is None
    attrs = agg.as_attributes()
    assert attrs["sources"] == []
    assert "start" not in attrs
    assert "latest_confirmed_end" not in attrs


def test_aggregate_cumulative_interval_reading_date_fallback():
    """reading_date (plain YYYY-MM-DD) is used as JST midnight boundary when end_at is absent."""
    snapshot = parse_energy_snapshot(SAMPLE_SNAPSHOT_RESPONSE)
    point = next(snapshot.iter_supply_points())
    point.interval_readings = [
        ElectricityIntervalReading(
            "2026-05-15", "2026-04-15T00:00:00+09:00", None,
            "100.0", "3000", False,
        ),
    ]
    point.half_hourly_readings = [
        ElectricityHalfHourReading(
            "2026-05-14T12:00:00+09:00", "2026-05-14T12:30:00+09:00",
            "0.5", "15", "standard",
        ),
        ElectricityHalfHourReading(
            "2026-05-15T00:00:00+09:00", "2026-05-15T00:30:00+09:00",
            "0.4", "12", "standard",
        ),
    ]

    agg = aggregate_supply_point_cumulative_readings(point)

    # reading_date "2026-05-15" → JST midnight 2026-05-15T00:00:00+09:00
    # HH at 2026-05-14T12:00 → start < 2026-05-15T00:00 → excluded
    # HH at 2026-05-15T00:00 → start >= 2026-05-15T00:00 → included
    assert agg.interval_reading_count == 1
    assert agg.half_hourly_reading_count == 1
    assert agg.total_consumption == pytest.approx(100.4)
    assert agg.latest_confirmed_end.isoformat() == "2026-05-15T00:00:00+09:00"
