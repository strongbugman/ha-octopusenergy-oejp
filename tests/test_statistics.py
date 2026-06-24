"""Tests for statistics injection."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from custom_components.octopusenergy_oejp.models import (
    ElectricityHalfHourReading,
    parse_energy_snapshot,
)
from custom_components.octopusenergy_oejp.statistics import (
    _build_hourly_buckets,
    _fingerprint,
    _float_or_none,
    _hour_start_utc,
    async_insert_statistics,
)
from tests.conftest import SAMPLE_SNAPSHOT_RESPONSE

UTC = timezone.utc


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------

def test_fingerprint_returns_12_char_hex():
    fp = _fingerprint("ESP-001")
    assert len(fp) == 12
    assert all(c in "0123456789abcdef" for c in fp)


def test_fingerprint_is_stable():
    assert _fingerprint("ESP-001") == _fingerprint("ESP-001")


def test_fingerprint_differs_for_different_inputs():
    assert _fingerprint("ESP-001") != _fingerprint("ESP-002")


def test_fingerprint_uses_sha256():
    assert _fingerprint("ESP-001") == "d68b35ae7f3f"
    assert _fingerprint("hello") == "2cf24dba5fb0"


def test_float_or_none_handles_valid_values():
    assert _float_or_none("1.5") == 1.5
    assert _float_or_none(2) == 2.0
    assert _float_or_none(0) == 0.0


def test_float_or_none_returns_none_for_invalid():
    assert _float_or_none(None) is None
    assert _float_or_none("") is None
    assert _float_or_none("abc") is None


def test_hour_start_utc_floors_to_hour():
    result = _hour_start_utc("2024-01-15T09:30:00+09:00")
    assert result is not None
    assert result.tzinfo == UTC
    assert result.hour == 0  # 09:30 JST = 00:30 UTC → floor to 00:00 UTC
    assert result.minute == 0
    assert result.second == 0


def test_hour_start_utc_handles_z_suffix():
    result = _hour_start_utc("2024-01-15T09:30:00Z")
    assert result is not None
    assert result.hour == 9
    assert result.minute == 0


def test_hour_start_utc_returns_none_for_invalid():
    assert _hour_start_utc(None) is None
    assert _hour_start_utc("") is None
    assert _hour_start_utc("not-a-date") is None


# ---------------------------------------------------------------------------
# _build_hourly_buckets tests
# ---------------------------------------------------------------------------

def _make_point_with_readings(readings):
    """Return a supply point with the given half-hourly readings list."""
    snapshot = parse_energy_snapshot(SAMPLE_SNAPSHOT_RESPONSE)
    point = next(snapshot.iter_supply_points())
    point.half_hourly_readings = readings
    return point


def test_build_hourly_buckets_sums_two_half_hours():
    point = _make_point_with_readings([
        ElectricityHalfHourReading("2024-01-15T00:00:00+00:00", "2024-01-15T00:30:00+00:00", "0.3", "9.0", None),
        ElectricityHalfHourReading("2024-01-15T00:30:00+00:00", "2024-01-15T01:00:00+00:00", "0.4", "12.0", None),
    ])
    hour = datetime(2024, 1, 15, 0, 0, 0, tzinfo=UTC)
    energy, cost = _build_hourly_buckets(point)
    assert energy[hour] == pytest.approx(0.7)
    assert cost[hour] == pytest.approx(21.0)


def test_build_hourly_buckets_excludes_incomplete_cost_hours():
    point = _make_point_with_readings([
        ElectricityHalfHourReading("2024-01-15T00:00:00+00:00", "2024-01-15T00:30:00+00:00", "0.3", "9.0", None),
        ElectricityHalfHourReading("2024-01-15T00:30:00+00:00", "2024-01-15T01:00:00+00:00", "0.4", None, None),
    ])
    hour = datetime(2024, 1, 15, 0, 0, 0, tzinfo=UTC)
    energy, cost = _build_hourly_buckets(point)
    assert hour in energy
    assert hour not in cost


def test_build_hourly_buckets_empty_readings():
    point = _make_point_with_readings([])
    energy, cost = _build_hourly_buckets(point)
    assert energy == {}
    assert cost == {}


def test_build_hourly_buckets_skips_missing_energy():
    point = _make_point_with_readings([
        ElectricityHalfHourReading("2024-01-15T00:00:00+00:00", "2024-01-15T00:30:00+00:00", None, "9.0", None),
    ])
    energy, cost = _build_hourly_buckets(point)
    assert energy == {}


# ---------------------------------------------------------------------------
# async_insert_statistics integration tests
# ---------------------------------------------------------------------------

def _run(coro):
    return asyncio.run(coro)


def test_async_insert_statistics_calls_add_external_statistics():
    snapshot = parse_energy_snapshot(SAMPLE_SNAPSHOT_RESPONSE)
    point = next(snapshot.iter_supply_points())
    point.half_hourly_readings = [
        ElectricityHalfHourReading(
            "2024-01-15T00:00:00+00:00",
            "2024-01-15T00:30:00+00:00",
            "0.3",
            "9.0",
            None,
        ),
        ElectricityHalfHourReading(
            "2024-01-15T00:30:00+00:00",
            "2024-01-15T01:00:00+00:00",
            "0.4",
            "12.0",
            None,
        ),
    ]

    calls: list[tuple[Any, Any, Any]] = []

    from homeassistant.components.recorder.statistics import (
        StatisticData,
        StatisticMetaData,
    )

    def _mock_add(hass, metadata, statistics):
        calls.append((hass, metadata, list(statistics)))

    hass = MagicMock()

    with patch(
        "custom_components.octopusenergy_oejp.statistics.async_add_external_statistics",
        side_effect=_mock_add,
        create=True,
    ):
        # Patch the import inside async_insert_statistics to use stub classes.
        with patch.dict(
            "sys.modules",
            {
                "homeassistant.components.recorder.statistics": type(
                    "_mod",
                    (),
                    {
                        "async_add_external_statistics": staticmethod(_mock_add),
                        "get_last_statistics": staticmethod(lambda *args, **kwargs: {}),
                        "StatisticData": StatisticData,
                        "StatisticMetaData": StatisticMetaData,
                    },
                )()
            },
        ):
            _run(async_insert_statistics(hass, snapshot))

    assert len(calls) == 2  # energy + cost
    _hass, energy_meta, energy_stats = calls[0]
    assert energy_meta.unit_of_measurement == "kWh"
    assert energy_meta.has_sum is True
    assert len(energy_stats) == 1
    assert energy_stats[0].sum == pytest.approx(0.7)
    assert energy_stats[0].state == pytest.approx(0.7)

    _hass, cost_meta, cost_stats = calls[1]
    assert cost_meta.unit_of_measurement == "JPY"
    assert cost_stats[0].sum == pytest.approx(21.0)


def test_async_insert_statistics_skips_point_with_no_readings():
    snapshot = parse_energy_snapshot(SAMPLE_SNAPSHOT_RESPONSE)
    point = next(snapshot.iter_supply_points())
    point.half_hourly_readings = []

    calls: list[Any] = []

    from homeassistant.components.recorder.statistics import StatisticData, StatisticMetaData

    def _mock_add(hass, metadata, statistics):
        calls.append(metadata)

    hass = MagicMock()
    with patch.dict(
        "sys.modules",
        {
            "homeassistant.components.recorder.statistics": type(
                "_mod",
                (),
                {
                    "async_add_external_statistics": staticmethod(_mock_add),
                    "get_last_statistics": staticmethod(lambda *args, **kwargs: {}),
                    "StatisticData": StatisticData,
                    "StatisticMetaData": StatisticMetaData,
                },
            )()
        },
    ):
        _run(async_insert_statistics(hass, snapshot))

    assert calls == []


def test_async_insert_statistics_graceful_when_recorder_absent():
    snapshot = parse_energy_snapshot(SAMPLE_SNAPSHOT_RESPONSE)
    hass = MagicMock()

    import sys
    saved = sys.modules.pop("homeassistant.components.recorder.statistics", None)
    try:
        _run(async_insert_statistics(hass, snapshot))
    finally:
        if saved is not None:
            sys.modules["homeassistant.components.recorder.statistics"] = saved
