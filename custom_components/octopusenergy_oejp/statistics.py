"""Statistics injection for Octopus Energy OEJP."""

from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .models import EnergySnapshot, ElectricitySupplyPoint

_LOGGER = logging.getLogger(__name__)
_UTC = timezone.utc


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


def _last_stored_sum(last_stats: object, stat_id: str, first_hour: datetime) -> float:
    """Extract the previous cumulative sum for a statistic, or 0.0 if unavailable."""
    if not last_stats or not isinstance(last_stats, dict):
        return 0.0
    rows = last_stats.get(stat_id)
    if not rows:
        return 0.0
    row = rows[0]
    if not isinstance(row, dict):
        return 0.0
    last_start = row.get("start")
    last_sum = row.get("sum")
    if last_start is None or last_sum is None:
        return 0.0
    # Only use the previous sum if the last stored stat precedes our new window.
    # If the last stored stat falls inside our window, async_add_external_statistics
    # will overwrite it and the sum continuity from the first new point is sufficient.
    if last_start >= first_hour:
        return 0.0
    return float(last_sum)


async def _write_supply_point_statistics(
    hass: HomeAssistant,
    point: ElectricitySupplyPoint,
    domain: str,
    async_add_external_statistics: object,
    StatisticData: type,
    StatisticMetaData: type,
    get_last_statistics: object,
) -> None:
    """Write hourly energy (and where available cost) statistics for one supply point."""
    if not point.half_hourly_readings:
        return

    hourly_energy, hourly_cost = _build_hourly_buckets(point)
    if not hourly_energy:
        return

    fp = _fingerprint(point.id)
    sorted_energy_hours = sorted(hourly_energy)

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

    # Retrieve the last stored sum so new rows are strictly monotonic.
    energy_base_sum = 0.0
    try:
        last_energy_stats = await hass.async_add_executor_job(  # type: ignore[misc]
            get_last_statistics, hass, 1, energy_stat_id, False, {"sum"}
        )
        energy_base_sum = _last_stored_sum(last_energy_stats, energy_stat_id, sorted_energy_hours[0])
    except Exception:  # noqa: BLE001
        pass

    energy_running_sum = energy_base_sum
    energy_stats = []
    for hour in sorted_energy_hours:
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
        sorted_cost_hours = sorted(hourly_cost)
        cost_stat_id = f"{domain}:{fp}_cost"
        cost_meta = StatisticMetaData(
            statistic_id=cost_stat_id,
            source=domain,
            name=f"Supply Point {fp} Electricity Cost",
            unit_of_measurement="JPY",
            has_mean=False,
            has_sum=True,
        )

        cost_base_sum = 0.0
        try:
            last_cost_stats = await hass.async_add_executor_job(  # type: ignore[misc]
                get_last_statistics, hass, 1, cost_stat_id, False, {"sum"}
            )
            cost_base_sum = _last_stored_sum(last_cost_stats, cost_stat_id, sorted_cost_hours[0])
        except Exception:  # noqa: BLE001
            pass

        cost_running_sum = cost_base_sum
        cost_stats = []
        for hour in sorted_cost_hours:
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
            get_last_statistics,
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
        await _write_supply_point_statistics(
            hass,
            point,
            DOMAIN,
            async_add_external_statistics,
            StatisticData,
            StatisticMetaData,
            get_last_statistics,
        )
