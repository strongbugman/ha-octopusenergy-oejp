"""Tests for sensor entity value lookup and privacy-safe identifiers."""

from __future__ import annotations

from types import SimpleNamespace

from homeassistant.config_entries import ConfigEntry

from custom_components.octopusenergy_oejp.models import parse_energy_snapshot
from custom_components.octopusenergy_oejp.sensor import (
    ACCOUNT_SENSORS,
    SUPPLY_POINT_SENSORS,
    OctopusOejpAccountSensor,
    OctopusOejpSupplyPointSensor,
    _fingerprint,
)
from tests.conftest import SAMPLE_SNAPSHOT_RESPONSE


def _coordinator():
    return SimpleNamespace(data=parse_energy_snapshot(SAMPLE_SNAPSHOT_RESPONSE))


def test_account_sensor_uses_redacted_name_unique_id_and_attributes():
    entry = ConfigEntry(entry_id="entry-1")
    account_number = "A-1234567"
    sensor = OctopusOejpAccountSensor(
        _coordinator(),
        entry,
        account_number,
        ACCOUNT_SENSORS[0],
    )

    assert sensor.native_value == 1500
    assert account_number not in sensor._attr_name
    assert account_number not in sensor._attr_unique_id
    assert sensor.extra_state_attributes == {
        "account_fingerprint": _fingerprint(account_number),
        "status": "ACTIVE",
    }


def test_supply_point_sensor_uses_redacted_unique_id_and_attributes():
    entry = ConfigEntry(entry_id="entry-1")
    account_number = "A-1234567"
    point_id = "ESP-001"
    sensor = OctopusOejpSupplyPointSensor(
        _coordinator(),
        entry,
        account_number,
        point_id,
        SUPPLY_POINT_SENSORS[0],
        "Supply Point Redacted Status",
    )

    assert sensor.native_value == "ACTIVE"
    assert account_number not in sensor._attr_unique_id
    assert point_id not in sensor._attr_unique_id
    assert sensor.extra_state_attributes == {
        "meter_count": 1,
        "supply_point_fingerprint": _fingerprint(point_id),
    }
