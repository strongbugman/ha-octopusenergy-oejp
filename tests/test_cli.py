"""Tests for the CLI sensor-fetch module.

All tests use the shared SAMPLE_SNAPSHOT_RESPONSE fixture from conftest.py;
no real API calls are made.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from custom_components.octopusenergy_oejp.cli import (
    SensorRecord,
    build_sensor_records,
    format_json,
    format_table,
    load_credentials,
    main,
)
from custom_components.octopusenergy_oejp.models import parse_energy_snapshot

from .conftest import SAMPLE_SNAPSHOT_RESPONSE


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
    # 14 sensors per supply point × 1 supply point in sample data
    assert len(sp_records) == 14


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
    assert set(first.keys()) == {"name", "state", "unit", "device_class", "attributes"}


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
