"""Tests for sensor entity value lookup and privacy-safe identifiers."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from homeassistant.config_entries import ConfigEntry

from custom_components.octopusenergy_oejp.models import (
    ACCESS_AUTHORIZED,
    AccessStatus,
    ElectricityHalfHourReading,
    parse_energy_snapshot,
)
from custom_components.octopusenergy_oejp.sensor import (
    ACCOUNT_SENSORS,
    SUPPLY_POINT_SENSORS,
    OctopusOejpAccountSensor,
    OctopusOejpSupplyPointSensor,
    _fingerprint,
)
from tests.conftest import SAMPLE_SNAPSHOT_RESPONSE

JST = ZoneInfo("Asia/Tokyo")


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


def test_supply_point_access_sensor_exposes_status_and_error_attributes():
    from custom_components.octopusenergy_oejp.models import ACCESS_UNAUTHORIZED

    coordinator = _coordinator()
    point = next(coordinator.data.iter_supply_points())
    point.interval_readings_access = AccessStatus(
        field_name="intervalReadings",
        status=ACCESS_UNAUTHORIZED,
        message="Unauthorized.",
        error_codes=["KT-CT-4501"],
        error_paths=["viewer.accounts.0.intervalReadings"],
    )
    spec = next(s for s in SUPPLY_POINT_SENSORS if s.key == "interval_readings_access")
    sensor = OctopusOejpSupplyPointSensor(
        coordinator,
        ConfigEntry(entry_id="entry-1"),
        "A-1234567",
        "ESP-001",
        spec,
        "Supply Point Redacted Interval Readings Access",
    )

    assert sensor.native_value == ACCESS_UNAUTHORIZED
    attrs = sensor.extra_state_attributes
    assert attrs["field_name"] == "intervalReadings"
    assert attrs["error_codes"] == ["KT-CT-4501"]
    assert attrs["error_paths"] == ["viewer.accounts.0.intervalReadings"]


def test_supply_point_aggregate_consumption_sensor_metadata_and_attributes():
    coordinator = _coordinator()
    point = next(coordinator.data.iter_supply_points())
    now = datetime.now(JST).replace(microsecond=0)
    start = now.replace(hour=0, minute=0, second=0)
    point.half_hourly_readings_access = AccessStatus.authorized("halfHourlyReadings")
    point.half_hourly_readings = [
        ElectricityHalfHourReading(
            start.isoformat(),
            start.replace(minute=30).isoformat(),
            "0.42",
            "12.3",
            "standard",
        )
    ]
    spec = next(s for s in SUPPLY_POINT_SENSORS if s.key == "today_consumption")
    sensor = OctopusOejpSupplyPointSensor(
        coordinator,
        ConfigEntry(entry_id="entry-1"),
        "A-1234567",
        "ESP-001",
        spec,
        "Supply Point Redacted Today Consumption",
    )

    assert sensor.native_value == 0.42
    assert sensor._attr_native_unit_of_measurement == "kWh"
    assert sensor._attr_device_class == "energy"
    assert sensor._attr_state_class == "total"
    attrs = sensor.extra_state_attributes
    assert attrs["source"] == "halfHourlyReadings"
    assert attrs["currency"] == "JPY"
    assert attrs["reading_count"] == 1
    assert attrs["total_consumption"] == 0.42
    assert attrs["total_cost"] == 12.3


def test_supply_point_aggregate_cost_sensor_is_none_when_cost_missing():
    coordinator = _coordinator()
    point = next(coordinator.data.iter_supply_points())
    now = datetime.now(JST).replace(microsecond=0)
    start = now.replace(hour=0, minute=0, second=0)
    point.half_hourly_readings_access = AccessStatus(
        field_name="halfHourlyReadings",
        status=ACCESS_AUTHORIZED,
    )
    point.half_hourly_readings = [
        ElectricityHalfHourReading(
            start.isoformat(),
            start.replace(minute=30).isoformat(),
            "0.42",
            None,
            "standard",
        )
    ]
    spec = next(s for s in SUPPLY_POINT_SENSORS if s.key == "today_cost")
    sensor = OctopusOejpSupplyPointSensor(
        coordinator,
        ConfigEntry(entry_id="entry-1"),
        "A-1234567",
        "ESP-001",
        spec,
        "Supply Point Redacted Today Cost",
    )

    assert sensor.native_value is None
    assert sensor._attr_native_unit_of_measurement == "JPY"
    assert sensor._attr_device_class == "monetary"
    assert sensor._attr_state_class == "total"
    attrs = sensor.extra_state_attributes
    assert attrs["total_consumption"] == 0.42
    assert attrs["total_cost"] is None


def test_supply_point_latest_half_hour_average_power_sensor_metadata_and_attributes():
    coordinator = _coordinator()
    point = next(coordinator.data.iter_supply_points())
    point.half_hourly_readings = [
        ElectricityHalfHourReading(
            "2026-06-17T00:30:00+09:00",
            "2026-06-17T01:00:00+09:00",
            "0.42",
            "12.3",
            "standard",
        )
    ]
    spec = next(s for s in SUPPLY_POINT_SENSORS if s.key == "latest_half_hourly_average_power")
    sensor = OctopusOejpSupplyPointSensor(
        coordinator,
        ConfigEntry(entry_id="entry-1"),
        "A-1234567",
        "ESP-001",
        spec,
        "Supply Point Redacted Latest Half-Hour Average Power",
    )

    assert sensor.native_value == 840.0
    assert sensor._attr_native_unit_of_measurement == "W"
    assert sensor._attr_device_class == "power"
    assert sensor._attr_state_class == "measurement"
    attrs = sensor.extra_state_attributes
    assert attrs["source"] == "halfHourlyReadings"
    assert attrs["source_reading_start"] == "2026-06-17T00:30:00+09:00"
    assert attrs["source_reading_end"] == "2026-06-17T01:00:00+09:00"
    assert attrs["source_value_kwh"] == 0.42
    assert "not instantaneous live power" in attrs["note"]


def test_supply_point_latest_half_hour_average_cost_rate_sensor_metadata_and_attributes():
    coordinator = _coordinator()
    point = next(coordinator.data.iter_supply_points())
    point.half_hourly_readings = [
        ElectricityHalfHourReading(
            "2026-06-17T00:30:00+09:00",
            "2026-06-17T01:00:00+09:00",
            "0.5",
            "15",
            "standard",
        )
    ]
    spec = next(s for s in SUPPLY_POINT_SENSORS if s.key == "latest_half_hourly_average_cost_rate")
    sensor = OctopusOejpSupplyPointSensor(
        coordinator,
        ConfigEntry(entry_id="entry-1"),
        "A-1234567",
        "ESP-001",
        spec,
        "Supply Point Redacted Latest Half-Hour Average Cost Rate",
    )

    assert sensor.native_value == 30.0
    assert sensor._attr_native_unit_of_measurement == "JPY/kWh"
    assert sensor._attr_device_class is None
    assert sensor._attr_state_class == "measurement"
    attrs = sensor.extra_state_attributes
    assert attrs["source"] == "halfHourlyReadings"
    assert attrs["source_reading_start"] == "2026-06-17T00:30:00+09:00"
    assert attrs["source_value_kwh"] == 0.5
    assert attrs["source_cost_jpy"] == 15.0
    assert attrs["currency"] == "JPY"
