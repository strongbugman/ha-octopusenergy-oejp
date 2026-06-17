# OEJP Cumulative Sensor Update Report

## Implemented

Added per-supply-point cumulative sensors:

| Sensor | Unit | Device Class | State Class |
|---|---|---|---|
| Cumulative Consumption | kWh | energy | total_increasing |
| Cumulative Cost | JPY | monetary | total |

The cumulative values combine confirmed `intervalReadings` with `halfHourlyReadings` newer than the latest confirmed interval boundary, avoiding double counting where possible.

## Local verification

Commands run:

```bash
.venv/bin/python -m pytest
.venv/bin/python -m compileall -q custom_components tests scripts
.venv/bin/python scripts/fetch_sensors.py --format json
.venv/bin/python scripts/fetch_sensors.py --format table
.venv/bin/python scripts/package_integration.py
```

Results:

```text
83 passed in 0.16s
compileall passed
CLI returned 32 sensor records
Package contains 10 integration files
```

Package:

```text
dist/octopusenergy_oejp-0.1.0.zip
size: 20477 bytes
sha256: 4f75c7bfc7a2705ac5113a2ed51874062ccc6141337579157fed2080a0c330e0
```

## Real account CLI values

| Sensor | State | Unit | Device Class | State Class |
|---|---:|---|---|---|
| Cumulative Consumption | 4017.0 | kWh | energy | total_increasing |
| Cumulative Cost | 118361.32 | JPY | monetary | total |
| Today Consumption | 0.4 | kWh | energy | total |
| This Week Consumption | 15.0 | kWh | energy | total |
| This Month Consumption | 138.6 | kWh | energy | total |

## Home Assistant installation verification

Installed to:

```text
/config/custom_components/octopusenergy_oejp/
```

HA config check:

```text
homeassistant.check_config: success
```

Home Assistant was restarted and API came back online.

HA states now include:

| Entity | State | Device Class | State Class | Unit |
|---|---:|---|---|---|
| sensor.supply_point_04f51345ce6f_cumulative_consumption | 4017.0 | energy | total_increasing | kWh |
| sensor.supply_point_04f51345ce6f_cumulative_cost | 118361.32 | monetary | total | JPY |
