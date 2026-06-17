# OEJP Aggregate Consumption/Cost Sensors Report

Change implemented via Codex from the BottlecapDave HomeAssistant-OctopusEnergy cost tracker design notes.

## Implemented

- Added JST-boundary aggregation helpers for half-hourly readings:
  - today
  - current week, Monday-start
  - current month
- Added per-supply-point sensors:
  - Today Consumption
  - Today Cost
  - This Week Consumption
  - This Week Cost
  - This Month Consumption
  - This Month Cost
- Consumption sensors expose:
  - unit: `kWh`
  - device class: `energy`
  - state class: `total`
- Cost sensors expose:
  - unit: `JPY`
  - device class: `monetary`
  - state class: `total`
- Aggregate attributes include:
  - `start`
  - `end`
  - `reading_count`
  - `total_consumption`
  - `total_cost`
  - `currency`
  - `source=halfHourlyReadings`
- If any included reading lacks `costEstimate`, cost aggregate state becomes `None`, while consumption still sums from `value`.
- CLI JSON/table output now includes aggregate sensors and `unit` / `device_class` / `state_class` metadata.

## Commands run

```bash
.venv/bin/python -m pytest
.venv/bin/python -m compileall -q custom_components tests scripts
.venv/bin/python scripts/fetch_sensors.py --format json
.venv/bin/python scripts/fetch_sensors.py --format table
```

## Verification

```text
71 passed in 0.10s
compileall passed
real CLI returned 30 sensor records
```

## Real account aggregate sensor data

| Name | State | Unit | Device Class | State Class |
|------|-------|------|--------------|-------------|
| Latest Interval Reading Value | 280.00000 |  |  |  |
| Latest Interval Reading Cost | 8096.40 |  |  |  |
| Latest Interval Reading Date | 2026-06-17 |  |  |  |
| Latest Half-Hour Reading Value | 0.300000000000000000 |  |  |  |
| Latest Half-Hour Reading Cost | 9.32 |  |  |  |
| Latest Half-Hour Reading Time | 2026-06-16T15:30:00+00:00 |  |  |  |
| Interval Readings Access | authorized |  |  |  |
| Half-Hour Readings Access | authorized |  |  |  |
| Today Consumption | 0.4 | kWh | energy | total |
| Today Cost | 12.42 | JPY | monetary | total |
| This Week Consumption | 15.0 | kWh | energy | total |
| This Week Cost | 465.52 | JPY | monetary | total |
| This Month Consumption | 138.6 | kWh | energy | total |
| This Month Cost | 3690.66 | JPY | monetary | total |
