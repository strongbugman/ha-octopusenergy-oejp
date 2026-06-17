# OEJP Sensor CLI Real Account Output

Generated from real account using:

```bash
.venv/bin/python scripts/fetch_sensors.py --format json
.venv/bin/python scripts/fetch_sensors.py --format table
```

Verification:

```text
60 passed in 0.14s
compileall passed
CLI returned 24 sensor records
```

## Sensor data

| Name | State | Unit | Attributes |
|------|-------|------|------------|
| Account Count | 1 |  |  |
| Property Count | 1 |  |  |
| Electricity Supply Points | 1 |  |  |
| Bills Total | 14 |  |  |
| Transactions Total | 0 |  |  |
| Active Agreements | 3 |  |  |
| Account 66712481bd54 Balance | 0 |  | status=ACTIVE |
| Account 66712481bd54 Status | ACTIVE |  |  |
| Account 66712481bd54 Bills Total | 14 |  |  |
| Account 66712481bd54 Transactions Total | 0 |  |  |
| Supply Point 04f51345ce6f Status | ON_SUPPLY |  |  |
| Supply Point 04f51345ce6f Agreements | 2 |  |  |
| Supply Point 04f51345ce6f Meter Count | 0 |  |  |
| Supply Point 04f51345ce6f Next Reading Date | 2026-04-15 |  |  |
| Supply Point 04f51345ce6f Next Next Reading Date | 2026-05-15 |  |  |
| Supply Point 04f51345ce6f Reading Day Of Month | 16 |  |  |
| Supply Point 04f51345ce6f Latest Interval Reading Value |  |  |  |
| Supply Point 04f51345ce6f Latest Interval Reading Cost |  |  |  |
| Supply Point 04f51345ce6f Latest Interval Reading Date |  |  |  |
| Supply Point 04f51345ce6f Latest Half-Hour Reading Value |  |  |  |
| Supply Point 04f51345ce6f Latest Half-Hour Reading Cost |  |  |  |
| Supply Point 04f51345ce6f Latest Half-Hour Reading Time |  |  |  |
| Supply Point 04f51345ce6f Interval Readings Access | unauthorized |  | field_name=intervalReadings; error_message=Unauthorized.; error_codes=['KT-CT-4501']; error_paths... |
| Supply Point 04f51345ce6f Half-Hour Readings Access | unauthorized |  | field_name=halfHourlyReadings; error_message=Unauthorized.; error_codes=['KT-CT-4501']; error_pat... |

