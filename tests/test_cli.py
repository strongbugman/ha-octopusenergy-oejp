"""Tests for the CLI sensor-fetch module.

All tests use the shared SAMPLE_SNAPSHOT_RESPONSE fixture from conftest.py;
no real API calls are made.
"""

from __future__ import annotations

from datetime import datetime
import json
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from custom_components.octopusenergy_oejp.cli import (
    build_sensor_records,
    format_json,
    format_table,
    load_credentials,
    main,
)
from custom_components.octopusenergy_oejp.models import (
    AccessStatus,
    ElectricityHalfHourReading,
    ElectricityIntervalReading,
    parse_energy_snapshot,
)
from custom_components.octopusenergy_oejp.cli import _supply_point_records

from .conftest import SAMPLE_SNAPSHOT_RESPONSE

JST = ZoneInfo("Asia/Tokyo")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_snapshot():
    return parse_energy_snapshot(SAMPLE_SNAPSHOT_RESPONSE)


# ---------------------------------------------------------------------------
# load_credentials
# ---------------------------------------------------------------------------

def test_load_credentials_from_env_vars(monkeypatch):
    monkeypatch.setenv("OEJP_EMAIL", "user@example.com")
    monkeypatch.setenv("OEJP_PASSWORD", "secret123")
    monkeypatch.setenv("OEJP_BASE_URL", "https://custom.example.com")
    creds = load_credentials()
    assert creds["email"] == "user@example.com"
    assert creds["password"] == "secret123"
    assert creds["base_url"] == "https://custom.example.com"


def test_load_credentials_from_legacy_octopus_env_vars(monkeypatch):
    monkeypatch.delenv("OEJP_EMAIL", raising=False)
    monkeypatch.delenv("OEJP_PASSWORD", raising=False)
    monkeypatch.delenv("OEJP_BASE_URL", raising=False)
    monkeypatch.setenv("OCTOPUS_EMAIL", "octopus@example.com")
    monkeypatch.setenv("OCTOPUS_PASSWORD", "octopus-secret")
    monkeypatch.setenv("OCTOPUS_BASE_URL", "https://legacy.example.com")
    creds = load_credentials()
    assert creds["email"] == "octopus@example.com"
    assert creds["password"] == "octopus-secret"
    assert creds["base_url"] == "https://legacy.example.com"


def test_load_credentials_default_base_url(monkeypatch):
    monkeypatch.setenv("OEJP_EMAIL", "user@example.com")
    monkeypatch.setenv("OEJP_PASSWORD", "pw")
    monkeypatch.delenv("OEJP_BASE_URL", raising=False)
    creds = load_credentials()
    assert creds["base_url"] == "https://api.oejp-kraken.energy"


def test_load_credentials_from_dotenv_file(monkeypatch, tmp_path):
    monkeypatch.delenv("OEJP_EMAIL", raising=False)
    monkeypatch.delenv("OEJP_PASSWORD", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("OEJP_EMAIL=dotenv@example.com\nOEJP_PASSWORD=dotenvpass\n")
    creds = load_credentials(dotenv_path=str(env_file))
    assert creds["email"] == "dotenv@example.com"
    assert creds["password"] == "dotenvpass"


def test_load_credentials_env_overrides_dotenv(monkeypatch, tmp_path):
    """Environment variables take precedence over .env file values."""
    monkeypatch.setenv("OEJP_EMAIL", "env@example.com")
    env_file = tmp_path / ".env"
    env_file.write_text("OEJP_EMAIL=file@example.com\nOEJP_PASSWORD=filepw\n")
    creds = load_credentials(dotenv_path=str(env_file))
    assert creds["email"] == "env@example.com"


def test_load_dotenv_skips_comments_and_blank_lines(monkeypatch, tmp_path):
    monkeypatch.delenv("OEJP_EMAIL", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("# this is a comment\n\nOEJP_EMAIL=real@example.com\n")
    creds = load_credentials(dotenv_path=str(env_file))
    assert creds["email"] == "real@example.com"


def test_load_dotenv_strips_quotes(monkeypatch, tmp_path):
    monkeypatch.delenv("OEJP_PASSWORD", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text('OEJP_EMAIL=x@x.com\nOEJP_PASSWORD="quoted_pass"\n')
    creds = load_credentials(dotenv_path=str(env_file))
    assert creds["password"] == "quoted_pass"


def test_load_credentials_empty_when_nothing_set(monkeypatch):
    monkeypatch.delenv("OEJP_EMAIL", raising=False)
    monkeypatch.delenv("OEJP_PASSWORD", raising=False)
    creds = load_credentials(dotenv_path="/nonexistent/.env")
    assert creds["email"] == ""
    assert creds["password"] == ""


# ---------------------------------------------------------------------------
# build_sensor_records — summary sensors
# ---------------------------------------------------------------------------

def test_build_sensor_records_contains_summary_sensors(sample_snapshot):
    records = build_sensor_records(sample_snapshot)
    names = {r.name for r in records}
    assert "Account Count" in names
    assert "Property Count" in names
    assert "Electricity Supply Points" in names
    assert "Bills Total" in names
    assert "Transactions Total" in names
    assert "Active Agreements" in names


def test_build_sensor_records_summary_values(sample_snapshot):
    records = build_sensor_records(sample_snapshot)
    by_name = {r.name: r for r in records}
    assert by_name["Account Count"].state == 1
    assert by_name["Property Count"].state == 1
    assert by_name["Electricity Supply Points"].state == 1
    assert by_name["Bills Total"].state == 12
    assert by_name["Transactions Total"].state == 42


# ---------------------------------------------------------------------------
# build_sensor_records — account sensors
# ---------------------------------------------------------------------------

def test_build_sensor_records_account_balance_attributes(sample_snapshot):
    records = build_sensor_records(sample_snapshot)
    balance = next(r for r in records if "Balance" in r.name and "Account" in r.name)
    assert "account_fingerprint" in balance.attributes
    assert "status" in balance.attributes
    assert balance.attributes["status"] == "ACTIVE"
    assert balance.state == 1500


def test_build_sensor_records_account_status(sample_snapshot):
    records = build_sensor_records(sample_snapshot)
    status_rec = next(r for r in records if r.name.endswith("Status") and "Account" in r.name)
    assert status_rec.state == "ACTIVE"


def test_build_sensor_records_account_bills_total(sample_snapshot):
    records = build_sensor_records(sample_snapshot)
    bills = next(r for r in records if "Bills Total" in r.name and "Account" in r.name)
    assert bills.state == 12


# ---------------------------------------------------------------------------
# build_sensor_records — supply point sensors
# ---------------------------------------------------------------------------

def test_build_sensor_records_supply_point_count(sample_snapshot):
    records = build_sensor_records(sample_snapshot)
    # "Supply Point {fp} ..." sensors only — filter by startswith to exclude
    # the summary "Electricity Supply Points" sensor
    sp_records = [r for r in records if r.name.startswith("Supply Point")]
    # 16 latest/status/access sensors + 6 period aggregate sensors + 2 cumulative sensors per supply point
    assert len(sp_records) == 24


def test_build_sensor_records_supply_point_has_fingerprint_attr(sample_snapshot):
    records = build_sensor_records(sample_snapshot)
    sp_records = [r for r in records if r.name.startswith("Supply Point")]
    assert all("supply_point_fingerprint" in r.attributes for r in sp_records)


def test_build_sensor_records_supply_point_status(sample_snapshot):
    records = build_sensor_records(sample_snapshot)
    status_rec = next(
        r for r in records if r.name.startswith("Supply Point") and r.name.endswith("Status")
    )
    assert status_rec.state == "ACTIVE"


def test_build_sensor_records_supply_point_meter_count(sample_snapshot):
    records = build_sensor_records(sample_snapshot)
    meter_rec = next(
        r for r in records if r.name.startswith("Supply Point") and r.name.endswith("Meter Count")
    )
    assert meter_rec.state == 1


def test_build_sensor_records_access_sensors_present(sample_snapshot):
    records = build_sensor_records(sample_snapshot)
    interval_access = next(
        r for r in records if r.name.startswith("Supply Point") and r.name.endswith("Interval Readings Access")
    )
    hh_access = next(
        r for r in records if r.name.startswith("Supply Point") and r.name.endswith("Half-Hour Readings Access")
    )
    assert interval_access.state is not None
    assert hh_access.state is not None
    assert "field_name" in interval_access.attributes


def test_build_sensor_records_no_raw_ids_in_names(sample_snapshot):
    records = build_sensor_records(sample_snapshot)
    for r in records:
        assert "A-1234567" not in r.name
        assert "ESP-001" not in r.name


def test_build_sensor_records_aggregate_metadata_and_attributes(sample_snapshot):
    point = next(sample_snapshot.iter_supply_points())
    point.half_hourly_readings_access = AccessStatus.authorized("halfHourlyReadings")
    point.half_hourly_readings = [
        ElectricityHalfHourReading(
            "2026-06-17T00:00:00+09:00",
            "2026-06-17T00:30:00+09:00",
            "0.5",
            "15.2",
            "standard",
        )
    ]

    records = build_sensor_records(
        sample_snapshot,
        now=datetime(2026, 6, 17, 12, 0, tzinfo=JST),
    )
    consumption = next(r for r in records if r.name.endswith("Today Consumption"))
    cost = next(r for r in records if r.name.endswith("Today Cost"))

    assert consumption.state == 0.5
    assert consumption.unit == "kWh"
    assert consumption.device_class == "energy"
    assert consumption.state_class == "total"
    assert consumption.attributes["source"] == "halfHourlyReadings"
    assert consumption.attributes["currency"] == "JPY"
    assert consumption.attributes["reading_count"] == 1
    assert consumption.attributes["total_consumption"] == 0.5
    assert consumption.attributes["total_cost"] == 15.2
    assert cost.state == 15.2
    assert cost.unit == "JPY"
    assert cost.device_class == "monetary"
    assert cost.state_class == "total"


def test_build_sensor_records_latest_half_hour_average_metadata_and_attributes(sample_snapshot):
    point = next(sample_snapshot.iter_supply_points())
    point.half_hourly_readings = [
        ElectricityHalfHourReading(
            "2026-06-17T00:30:00+09:00",
            "2026-06-17T01:00:00+09:00",
            "0.5",
            "15",
            "standard",
        )
    ]

    records = build_sensor_records(sample_snapshot)
    power = next(r for r in records if r.name.endswith("Latest Half-Hour Average Power"))
    rate = next(r for r in records if r.name.endswith("Latest Half-Hour Average Cost Rate"))

    assert power.state == 1000.0
    assert power.unit == "W"
    assert power.device_class == "power"
    assert power.state_class == "measurement"
    assert power.attributes["source"] == "halfHourlyReadings"
    assert power.attributes["source_reading_start"] == "2026-06-17T00:30:00+09:00"
    assert "not instantaneous live power" in power.attributes["note"]

    assert rate.state == 30.0
    assert rate.unit == "JPY/kWh"
    assert rate.device_class is None
    assert rate.state_class == "measurement"
    assert rate.attributes["source_cost_jpy"] == 15.0
    assert rate.attributes["currency"] == "JPY"


def test_build_sensor_records_cost_aggregate_none_when_cost_missing(sample_snapshot):
    point = next(sample_snapshot.iter_supply_points())
    point.half_hourly_readings_access = AccessStatus.authorized("halfHourlyReadings")
    point.half_hourly_readings = [
        ElectricityHalfHourReading(
            "2026-06-17T00:00:00+09:00",
            "2026-06-17T00:30:00+09:00",
            "0.5",
            None,
            "standard",
        )
    ]

    records = build_sensor_records(
        sample_snapshot,
        now=datetime(2026, 6, 17, 12, 0, tzinfo=JST),
    )
    consumption = next(r for r in records if r.name.endswith("Today Consumption"))
    cost = next(r for r in records if r.name.endswith("Today Cost"))

    assert consumption.state == 0.5
    assert cost.state is None
    assert cost.attributes["total_consumption"] == 0.5
    assert cost.attributes["total_cost"] is None


# ---------------------------------------------------------------------------
# format_json
# ---------------------------------------------------------------------------

def test_format_json_returns_valid_json(sample_snapshot):
    records = build_sensor_records(sample_snapshot)
    output = format_json(records)
    data = json.loads(output)
    assert isinstance(data, list)
    assert len(data) == len(records)


def test_format_json_record_schema(sample_snapshot):
    records = build_sensor_records(sample_snapshot)
    data = json.loads(format_json(records))
    first = data[0]
    assert set(first.keys()) == {
        "name",
        "state",
        "unit",
        "device_class",
        "state_class",
        "attributes",
    }


def test_format_json_latest_half_hour_average_fields(sample_snapshot):
    point = next(sample_snapshot.iter_supply_points())
    point.half_hourly_readings = [
        ElectricityHalfHourReading(
            "2026-06-17T00:30:00+09:00",
            "2026-06-17T01:00:00+09:00",
            "0.5",
            "15",
            "standard",
        )
    ]

    records = build_sensor_records(sample_snapshot)
    data = json.loads(format_json(records))
    power = next(r for r in data if r["name"].endswith("Latest Half-Hour Average Power"))
    rate = next(r for r in data if r["name"].endswith("Latest Half-Hour Average Cost Rate"))

    assert power["state"] == 1000.0
    assert power["unit"] == "W"
    assert power["device_class"] == "power"
    assert power["state_class"] == "measurement"
    assert rate["state"] == 30.0
    assert rate["unit"] == "JPY/kWh"
    assert rate["device_class"] is None
    assert rate["state_class"] == "measurement"


def test_format_json_no_raw_account_ids(sample_snapshot):
    records = build_sensor_records(sample_snapshot)
    output = format_json(records)
    assert "A-1234567" not in output
    assert "ESP-001" not in output


def test_format_json_attributes_are_dicts(sample_snapshot):
    records = build_sensor_records(sample_snapshot)
    data = json.loads(format_json(records))
    for item in data:
        assert isinstance(item["attributes"], dict)


# ---------------------------------------------------------------------------
# format_table
# ---------------------------------------------------------------------------

def test_format_table_has_markdown_header(sample_snapshot):
    records = build_sensor_records(sample_snapshot)
    output = format_table(records)
    lines = output.splitlines()
    assert "| Name |" in lines[0]
    assert "| State |" in lines[0]
    assert "---" in lines[1]


def test_format_table_row_count_matches_records(sample_snapshot):
    records = build_sensor_records(sample_snapshot)
    output = format_table(records)
    data_rows = [
        l for l in output.splitlines()
        if l.startswith("|") and "---" not in l and "Name" not in l
    ]
    assert len(data_rows) == len(records)


def test_format_table_no_raw_account_ids(sample_snapshot):
    records = build_sensor_records(sample_snapshot)
    output = format_table(records)
    assert "A-1234567" not in output
    assert "ESP-001" not in output


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

def test_main_returns_1_without_credentials(monkeypatch, capsys):
    monkeypatch.delenv("OEJP_EMAIL", raising=False)
    monkeypatch.delenv("OEJP_PASSWORD", raising=False)
    result = main(["--format", "json", "--env-file", "/nonexistent/.env"])
    assert result == 1
    assert "OEJP_EMAIL" in capsys.readouterr().err


def test_main_json_output_with_mocked_fetch(monkeypatch, capsys, sample_snapshot):
    monkeypatch.setenv("OEJP_EMAIL", "test@example.com")
    monkeypatch.setenv("OEJP_PASSWORD", "secret")
    with patch("custom_components.octopusenergy_oejp.cli.fetch_snapshot", return_value=sample_snapshot):
        result = main(["--format", "json"])
    assert result == 0
    data = json.loads(capsys.readouterr().out)
    assert isinstance(data, list)
    assert any(r["name"] == "Account Count" for r in data)


def test_main_table_output_with_mocked_fetch(monkeypatch, capsys, sample_snapshot):
    monkeypatch.setenv("OEJP_EMAIL", "test@example.com")
    monkeypatch.setenv("OEJP_PASSWORD", "secret")
    with patch("custom_components.octopusenergy_oejp.cli.fetch_snapshot", return_value=sample_snapshot):
        result = main(["--format", "table"])
    assert result == 0
    out = capsys.readouterr().out
    assert "| Name |" in out
    assert "Account Count" in out


def test_main_returns_1_on_api_error(monkeypatch, capsys):
    monkeypatch.setenv("OEJP_EMAIL", "test@example.com")
    monkeypatch.setenv("OEJP_PASSWORD", "secret")
    from custom_components.octopusenergy_oejp.api import GraphQLError
    with patch(
        "custom_components.octopusenergy_oejp.cli.fetch_snapshot",
        side_effect=GraphQLError("auth failed"),
    ):
        result = main(["--format", "json"])
    assert result == 1
    assert "auth failed" in capsys.readouterr().err


def test_supply_point_records_include_cumulative_sensors():
    snapshot = parse_energy_snapshot(SAMPLE_SNAPSHOT_RESPONSE)
    point = next(snapshot.iter_supply_points())
    point.interval_readings = [
        ElectricityIntervalReading(
            "2026-05-15", "2026-04-15T00:00:00+09:00", "2026-05-15T00:00:00+09:00",
            "100.0", "3000", True,
        ),
    ]
    point.half_hourly_readings = [
        ElectricityHalfHourReading(
            "2026-05-15T00:00:00+09:00", "2026-05-15T00:30:00+09:00",
            "0.4", "12", "standard",
        ),
    ]

    records = _supply_point_records(point)
    cumul_names = [r.name for r in records if "Cumulative" in r.name]
    assert len(cumul_names) == 2

    consumption_rec = next(r for r in records if r.name.endswith("Cumulative Consumption"))
    assert consumption_rec.unit == "kWh"
    assert consumption_rec.device_class == "energy"
    assert consumption_rec.state_class == "total_increasing"
    assert consumption_rec.state == pytest.approx(100.4)
    attrs = consumption_rec.attributes
    assert attrs["interval_reading_count"] == 1
    assert attrs["half_hourly_reading_count"] == 1
    assert attrs["reading_count"] == 2
    assert "intervalReadings" in attrs["sources"]
    assert "halfHourlyReadings" in attrs["sources"]
    assert attrs["total_cost"] == pytest.approx(3012.0)
    assert "cost_note" not in attrs
    assert "meter_count" in attrs
    assert "supply_point_fingerprint" in attrs

    cost_rec = next(r for r in records if r.name.endswith("Cumulative Cost"))
    assert cost_rec.unit == "JPY"
    assert cost_rec.device_class == "monetary"
    assert cost_rec.state_class == "total"
    assert cost_rec.state == pytest.approx(3012.0)


def test_supply_point_records_cumulative_none_when_no_readings():
    snapshot = parse_energy_snapshot(SAMPLE_SNAPSHOT_RESPONSE)
    point = next(snapshot.iter_supply_points())
    point.interval_readings = []
    point.half_hourly_readings = []

    records = _supply_point_records(point)
    consumption_rec = next(r for r in records if r.name.endswith("Cumulative Consumption"))
    cost_rec = next(r for r in records if r.name.endswith("Cumulative Cost"))

    assert consumption_rec.state is None
    assert cost_rec.state is None
    assert consumption_rec.attributes["reading_count"] == 0
    assert consumption_rec.attributes["sources"] == []


def test_build_sensor_records_includes_cumulative():
    snapshot = parse_energy_snapshot(SAMPLE_SNAPSHOT_RESPONSE)
    records = build_sensor_records(snapshot)
    names = [r.name for r in records]

    cumulative_names = [n for n in names if "Cumulative" in n]
    assert len(cumulative_names) == 2, f"Expected 2 cumulative records, got: {cumulative_names}"

    for rec in records:
        assert "ESP-001" not in rec.name
        assert "A-1234567" not in rec.name
