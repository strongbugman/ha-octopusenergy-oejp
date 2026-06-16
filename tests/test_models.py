"""Tests for dataclass parsing in models.py."""

from __future__ import annotations

from tests.conftest import SAMPLE_SNAPSHOT_RESPONSE
from custom_components.octopusenergy_oejp.models import (
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
