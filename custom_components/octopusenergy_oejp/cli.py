"""CLI that fetches all OEJP sensor data from the real API and prints it.

Usage (module form):
    python -m custom_components.octopusenergy_oejp.cli [--format json|table]

Credentials (any of these work):
    - Environment variables: OEJP_EMAIL, OEJP_PASSWORD, OEJP_BASE_URL (optional)
    - A .env file in the current directory or project root
    - --env-file /path/to/.env
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .api import GraphQLClient, GraphQLError
from .models import (
    ACCESS_AUTHORIZED,
    AGGREGATE_PERIOD_THIS_MONTH,
    AGGREGATE_PERIOD_THIS_WEEK,
    AGGREGATE_PERIOD_TODAY,
    AccessStatus,
    ElectricitySupplyPoint,
    EnergySnapshot,
    access_status_from_graphql_error,
    aggregate_supply_point_cumulative_readings,
    aggregate_supply_point_half_hourly_readings,
    apply_half_hourly_readings,
    apply_interval_readings,
    current_half_hourly_fetch_window,
    parse_energy_snapshot,
)

_DEFAULT_BASE_URL = "https://api.oejp-kraken.energy"
_KWH = "kWh"
_JPY = "JPY"
_DEVICE_CLASS_ENERGY = "energy"
_DEVICE_CLASS_MONETARY = "monetary"
_STATE_CLASS_TOTAL = "total"
_STATE_CLASS_TOTAL_INCREASING = "total_increasing"


# ---------------------------------------------------------------------------
# Credential loading
# ---------------------------------------------------------------------------

def _parse_dotenv(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    with path.open(encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                result[key] = value
    return result


def _find_dotenv(explicit: str | None) -> Path | None:
    if explicit:
        return Path(explicit)
    for directory in [Path.cwd(), Path(__file__).parent.parent.parent]:
        candidate = directory / ".env"
        if candidate.is_file():
            return candidate
    return None


def load_credentials(dotenv_path: str | None = None) -> dict[str, str]:
    """Return credentials from environment / .env.  Never modifies os.environ."""
    env = dict(os.environ)
    env_file = _find_dotenv(dotenv_path)
    if env_file and env_file.is_file():
        for key, value in _parse_dotenv(env_file).items():
            if key not in env:
                env[key] = value
    return {
        "email": env.get("OEJP_EMAIL") or env.get("OCTOPUS_EMAIL", ""),
        "password": env.get("OEJP_PASSWORD") or env.get("OCTOPUS_PASSWORD", ""),
        "base_url": env.get("OEJP_BASE_URL") or env.get("OCTOPUS_BASE_URL", _DEFAULT_BASE_URL),
    }


# ---------------------------------------------------------------------------
# Snapshot fetching (mirrors coordinator logic, async, no HA dependency)
# ---------------------------------------------------------------------------

async def fetch_snapshot(email: str, password: str, base_url: str = _DEFAULT_BASE_URL) -> EnergySnapshot:
    """Login and fetch the full energy snapshot with readings."""
    graphql_url = base_url.rstrip("/") + "/v1/graphql/"
    async with GraphQLClient(url=graphql_url) as client:
        access_token = (await client.obtain_token(email=email, password=password)).access_token

        raw = await client.viewer_energy_snapshot(token=access_token)
        snapshot = parse_energy_snapshot(raw)

        from_dt, to_dt = current_half_hourly_fetch_window()
        for account in snapshot.viewer.accounts:
            interval_result = await client.account_interval_readings(
                token=access_token,
                account_number=account.number,
            )
            interval_access = (
                AccessStatus.authorized("intervalReadings")
                if interval_result.error is None
                else access_status_from_graphql_error("intervalReadings", interval_result.error)
            )
            apply_interval_readings(
                snapshot,
                interval_result.payload,
                interval_access,
                account_number=account.number,
            )

            hh_result = await client.account_half_hourly_readings(
                token=access_token,
                account_number=account.number,
                from_datetime=from_dt.isoformat(),
                to_datetime=to_dt.isoformat(),
            )
            hh_access = (
                AccessStatus.authorized("halfHourlyReadings")
                if hh_result.error is None
                else access_status_from_graphql_error("halfHourlyReadings", hh_result.error)
            )
            apply_half_hourly_readings(
                snapshot,
                hh_result.payload,
                hh_access,
                account_number=account.number,
            )

    return snapshot


# ---------------------------------------------------------------------------
# Sensor record building (mirrors sensor.py definitions, no HA dependency)
# ---------------------------------------------------------------------------

@dataclass
class SensorRecord:
    name: str
    state: Any
    unit: str | None = None
    device_class: str | None = None
    state_class: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _access_attrs(status: AccessStatus) -> dict[str, Any]:
    attrs: dict[str, Any] = {"field_name": status.field_name}
    if status.message:
        attrs["error_message"] = status.message
    if status.error_codes:
        attrs["error_codes"] = status.error_codes
    if status.error_paths:
        attrs["error_paths"] = status.error_paths
    return attrs


def _aggregate_state(point: ElectricitySupplyPoint, state: Any, reading_count: int) -> Any:
    if point.half_hourly_readings_access.status != ACCESS_AUTHORIZED and reading_count == 0:
        return None
    return state


def _aggregate_records(
    point: ElectricitySupplyPoint,
    prefix: str,
    base: dict[str, Any],
    *,
    now: Any = None,
) -> list[SensorRecord]:
    records: list[SensorRecord] = []
    specs = (
        (AGGREGATE_PERIOD_TODAY, "Today"),
        (AGGREGATE_PERIOD_THIS_WEEK, "This Week"),
        (AGGREGATE_PERIOD_THIS_MONTH, "This Month"),
    )
    for period, label in specs:
        aggregate = aggregate_supply_point_half_hourly_readings(point, period, now=now)
        attrs = {**base, **aggregate.as_attributes()}
        records.extend(
            [
                SensorRecord(
                    f"{prefix} {label} Consumption",
                    _aggregate_state(point, aggregate.total_consumption, aggregate.reading_count),
                    unit=_KWH,
                    device_class=_DEVICE_CLASS_ENERGY,
                    state_class=_STATE_CLASS_TOTAL,
                    attributes=attrs,
                ),
                SensorRecord(
                    f"{prefix} {label} Cost",
                    _aggregate_state(point, aggregate.total_cost, aggregate.reading_count),
                    unit=_JPY,
                    device_class=_DEVICE_CLASS_MONETARY,
                    state_class=_STATE_CLASS_TOTAL,
                    attributes=attrs,
                ),
            ]
        )
    return records


def _supply_point_records(
    point: ElectricitySupplyPoint,
    *,
    now: Any = None,
) -> list[SensorRecord]:
    fp = _fingerprint(point.id)
    prefix = f"Supply Point {fp}"
    base = {"meter_count": point.meter_count, "supply_point_fingerprint": fp}

    def rec(name: str, value: Any, **extra: Any) -> SensorRecord:
        return SensorRecord(f"{prefix} {name}", value, attributes={**base, **extra})

    ir = point.latest_interval_reading
    hhr = point.latest_half_hourly_reading

    records = [
        rec("Status", point.status),
        rec("Agreements", len(point.agreements)),
        rec("Meter Count", point.meter_count),
        rec("Next Reading Date", point.next_reading_date),
        rec("Next Next Reading Date", point.next_next_reading_date),
        rec("Reading Day Of Month", point.reading_date_day_of_month),
        rec("Latest Interval Reading Value", ir.value if ir else None),
        rec("Latest Interval Reading Cost", ir.cost_estimate if ir else None),
        rec("Latest Interval Reading Date",
            (ir.reading_date or ir.start_at) if ir else None),
        rec("Latest Half-Hour Reading Value", hhr.value if hhr else None),
        rec("Latest Half-Hour Reading Cost", hhr.cost_estimate if hhr else None),
        rec("Latest Half-Hour Reading Time", hhr.start_at if hhr else None),
        SensorRecord(
            f"{prefix} Interval Readings Access",
            point.interval_readings_access.status,
            attributes={**base, **_access_attrs(point.interval_readings_access)},
        ),
        SensorRecord(
            f"{prefix} Half-Hour Readings Access",
            point.half_hourly_readings_access.status,
            attributes={**base, **_access_attrs(point.half_hourly_readings_access)},
        ),
    ]
    records.extend(_aggregate_records(point, prefix, base, now=now))

    cumulative = aggregate_supply_point_cumulative_readings(point)
    cumulative_attrs = {**base, **cumulative.as_attributes()}
    records.extend(
        [
            SensorRecord(
                f"{prefix} Cumulative Consumption",
                None if cumulative.reading_count == 0 else cumulative.total_consumption,
                unit=_KWH,
                device_class=_DEVICE_CLASS_ENERGY,
                state_class=_STATE_CLASS_TOTAL_INCREASING,
                attributes=cumulative_attrs,
            ),
            SensorRecord(
                f"{prefix} Cumulative Cost",
                None if cumulative.reading_count == 0 else cumulative.total_cost,
                unit=_JPY,
                device_class=_DEVICE_CLASS_MONETARY,
                state_class=_STATE_CLASS_TOTAL,
                attributes=cumulative_attrs,
            ),
        ]
    )
    return records


def build_sensor_records(snapshot: EnergySnapshot, *, now: Any = None) -> list[SensorRecord]:
    """Build all sensor records from a snapshot, mirroring the HA sensor platform."""
    records: list[SensorRecord] = [
        SensorRecord("Account Count", snapshot.account_count),
        SensorRecord("Property Count", snapshot.property_count),
        SensorRecord("Electricity Supply Points", snapshot.supply_point_count),
        SensorRecord("Bills Total", snapshot.bills_total),
        SensorRecord("Transactions Total", snapshot.transactions_total),
        SensorRecord("Active Agreements", snapshot.active_agreement_count),
    ]

    for account in snapshot.viewer.accounts:
        fp = _fingerprint(account.number)
        prefix = f"Account {fp}"
        records += [
            SensorRecord(
                f"{prefix} Balance",
                account.balance,
                attributes={"account_fingerprint": fp, "status": account.status},
            ),
            SensorRecord(f"{prefix} Status", account.status),
            SensorRecord(f"{prefix} Bills Total", account.bills_total),
            SensorRecord(f"{prefix} Transactions Total", account.transactions_total),
        ]
        for prop in account.properties:
            for point in prop.electricity_supply_points:
                records.extend(_supply_point_records(point, now=now))

    return records


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------

def format_json(records: list[SensorRecord]) -> str:
    return json.dumps(
        [
            {
                "name": r.name,
                "state": r.state,
                "unit": r.unit,
                "device_class": r.device_class,
                "state_class": r.state_class,
                "attributes": r.attributes,
            }
            for r in records
        ],
        indent=2,
        default=str,
    )


def format_table(records: list[SensorRecord]) -> str:
    """Render sensor records as a Markdown table."""
    header = "| Name | State | Unit | Device Class | State Class | Attributes |"
    sep =    "|------|-------|------|--------------|-------------|------------|"
    lines = [header, sep]
    for r in records:
        state = "" if r.state is None else str(r.state)
        unit = r.unit or ""
        device_class = r.device_class or ""
        state_class = r.state_class or ""
        # Skip fingerprint-only attrs to reduce noise; keep semantic ones
        shown = {
            k: v for k, v in r.attributes.items()
            if k not in ("supply_point_fingerprint", "account_fingerprint", "meter_count")
        }
        attrs = "; ".join(f"{k}={v}" for k, v in shown.items())
        if len(attrs) > 100:
            attrs = attrs[:97] + "..."
        lines.append(
            f"| {r.name} | {state} | {unit} | {device_class} | {state_class} | {attrs} |"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch all OEJP Octopus Energy sensor data and print it."
    )
    parser.add_argument(
        "--format",
        choices=["json", "table"],
        default="json",
        help="Output format (default: json)",
    )
    parser.add_argument(
        "--env-file",
        default=None,
        metavar="PATH",
        help="Path to a .env credentials file (auto-detected if omitted)",
    )
    args = parser.parse_args(argv)

    creds = load_credentials(dotenv_path=args.env_file)
    if not creds["email"] or not creds["password"]:
        print(
            "Error: OEJP_EMAIL and OEJP_PASSWORD must be set "
            "(via environment variables or a .env file).",
            file=sys.stderr,
        )
        return 1

    try:
        snapshot = asyncio.run(fetch_snapshot(
            email=creds["email"],
            password=creds["password"],
            base_url=creds["base_url"],
        ))
    except GraphQLError as exc:
        print(f"Error fetching data: {exc}", file=sys.stderr)
        return 1

    records = build_sensor_records(snapshot)

    if args.format == "json":
        print(format_json(records))
    else:
        print(format_table(records))

    return 0


if __name__ == "__main__":
    sys.exit(main())
