"""Statistics injection for Octopus Energy OEJP."""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone
from hashlib import md5
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .models import EnergySnapshot, ElectricitySupplyPoint

_LOGGER = logging.getLogger(__name__)
_UTC = timezone.utc


import hashlib


def _fingerprint(s: str) -> str:
    """Return a 12-character SHA-256 hex digest of s."""
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:12]


def _hour_start_utc(dt_str: str | None) -> datetime | None:
    """Parse an ISO datetime string and return the UTC hour start, or None."""
    if not dt_str:
        return None
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        dt_utc = dt.astimezone(_UTC)
        return dt_utc.replace(minute=0, second=0, microsecond=0)
    except (ValueError, TypeError):
        return None


def _float_or_none(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return None


def _build_hourly_buckets(
    point: ElectricitySupplyPoint,
) -> tuple[dict[datetime, float], dict[datetime, float]]:
    """Aggregate half-hourly readings into (hourly_energy, hourly_cost) dicts.

    Cost is only included for hours where every half-hourly reading has a cost.
    Hours with no energy value are skipped entirely.
    """
    hourly_energy: dict[datetime, float] = defaultdict(float)
    hourly_cost: dict[datetime, float] = defaultdict(float)
    # Track whether any reading in a given hour is missing its cost.
    hour_cost_incomplete: set[datetime] = set()

    for reading in point.half_hourly_readings:
        hour = _hour_start_utc(reading.start_at)
        if hour is None:
            continue
        energy = _float_or_none(reading.value)
        if energy is None:
            continue
        hourly_energy[hour] += energy

        cost = _float_or_none(reading.cost_estimate)
        if cost is None:
            hour_cost_incomplete.add(hour)
        else:
            hourly_cost[hour] += cost

    # Remove hours with incomplete cost so the caller sees only complete hours.
    for hour in hour_cost_incomplete:
        hourly_cost.pop(hour, None)

    return dict(hourly_energy), dict(hourly_cost)


def _write_supply_point_statistics(
    hass: HomeAssistant,
    point: ElectricitySupplyPoint,
    domain: str,
    async_add_external_statistics: object,
    StatisticData: type,
    StatisticMetaData: type,
) -> None:
    """Write hourly energy (and where available cost) statistics for one supply point."""
    if not point.half_hourly_readings:
        return

    hourly_energy, hourly_cost = _build_hourly_buckets(point)
    if not hourly_energy:
        return

    fp = _fingerprint(point.id)

    # --- Energy ---
    energy_stat_id = f"{domain}:{fp}_energy"
    energy_meta = StatisticMetaData(
        statistic_id=energy_stat_id,
        source=domain,
        name=f"Supply Point {fp} Electricity Consumption",
        unit_of_measurement="kWh",
        has_mean=False,
        has_sum=True,
    )
    energy_running_sum = 0.0
    energy_stats = []
    for hour in sorted(hourly_energy):
        energy_running_sum += hourly_energy[hour]
        energy_stats.append(
            StatisticData(
                start=hour,
                state=hourly_energy[hour],
                sum=energy_running_sum,
            )
        )
    async_add_external_statistics(hass, energy_meta, energy_stats)  # type: ignore[operator]

    # --- Cost (only for hours with complete data) ---
    if hourly_cost:
        cost_stat_id = f"{domain}:{fp}_cost"
        cost_meta = StatisticMetaData(
            statistic_id=cost_stat_id,
            source=domain,
            name=f"Supply Point {fp} Electricity Cost",
            unit_of_measurement="JPY",
            has_mean=False,
            has_sum=True,
        )
        cost_running_sum = 0.0
        cost_stats = []
        for hour in sorted(hourly_cost):
            cost_running_sum += hourly_cost[hour]
            cost_stats.append(
                StatisticData(
                    start=hour,
                    state=hourly_cost[hour],
                    sum=cost_running_sum,
                )
            )
        async_add_external_statistics(hass, cost_meta, cost_stats)  # type: ignore[operator]

    _LOGGER.debug(
        "Inserted %d hourly energy and %d hourly cost stat points for supply point %s",
        len(energy_stats),
        len(hourly_cost),
        fp,
    )


async def async_insert_statistics(
    hass: HomeAssistant,
    snapshot: EnergySnapshot,
) -> None:
    """Write hourly energy and cost statistics to the Home Assistant recorder."""
    try:
        from homeassistant.components.recorder.statistics import (  # noqa: PLC0415
            async_add_external_statistics,
            StatisticData,
            StatisticMetaData,
        )
    except ImportError:
        _LOGGER.debug(
            "homeassistant.components.recorder.statistics not available; "
            "skipping statistics injection"
        )
        return

    from .const import DOMAIN  # noqa: PLC0415

    for point in snapshot.iter_supply_points():
        if not point.id:
            continue
        _write_supply_point_statistics(
            hass,
            point,
            DOMAIN,
            async_add_external_statistics,
            StatisticData,
            StatisticMetaData,
        )
