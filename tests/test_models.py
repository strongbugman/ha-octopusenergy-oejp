"""Tests for dataclass parsing in models.py."""

from __future__ import annotations

from tests.conftest import SAMPLE_SNAPSHOT_RESPONSE
from custom_components.octopusenergy_oejp.models import (
    ACCESS_AUTHORIZED,
    ACCESS_UNAUTHORIZED,
    AccessStatus,
    Account,
    Agreement,
    Bill,
    ElectricitySupplyPoint,
    EnergySnapshot,
    MarketSupplyAgreement,
    Meter,
    Property,
    Transaction,
    Viewer,
    access_status_from_graphql_error,
    apply_half_hourly_readings,
    apply_interval_readings,
    parse_energy_snapshot,
)


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
