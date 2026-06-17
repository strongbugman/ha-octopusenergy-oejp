# OEJP Sensor CLI Real Account Output — Account Number Reading Queries

Change tested: consumption queries now follow the official example and call `account(accountNumber: $accountNumber)` instead of reading through `viewer.accounts`.

Authentication remains: raw `obtainKrakenToken.token` access token in `Authorization`, no `JWT ` prefix, never `refreshToken`.

Commands run:

```bash
.venv/bin/python -m pytest
.venv/bin/python -m compileall -q custom_components tests scripts
.venv/bin/python scripts/fetch_sensors.py --format json
.venv/bin/python scripts/fetch_sensors.py --format table
```

Verification:

```text
61 passed in 0.14s
compileall passed
CLI returned 24 sensor records
```

Result: `intervalReadings` and `halfHourlyReadings` are now authorized and return real consumption data.

## Sensor data

| Name | State | Unit | Attributes |
|------|-------|------|------------|
| Account Count | 1 |  |  |
| Property Count | 1 |  |  |
| Electricity Supply Points | 1 |  |  |
| Bills Total | 15 |  |  |
| Transactions Total | 0 |  |  |
| Active Agreements | 3 |  |  |
| Account 66712481bd54 Balance | 0 |  | status=ACTIVE |
| Account 66712481bd54 Status | ACTIVE |  |  |
| Account 66712481bd54 Bills Total | 15 |  |  |
| Account 66712481bd54 Transactions Total | 0 |  |  |
| Supply Point 04f51345ce6f Status | ON_SUPPLY |  |  |
| Supply Point 04f51345ce6f Agreements | 2 |  |  |
| Supply Point 04f51345ce6f Meter Count | 0 |  |  |
| Supply Point 04f51345ce6f Next Reading Date | 2026-04-15 |  |  |
| Supply Point 04f51345ce6f Next Next Reading Date | 2026-05-15 |  |  |
| Supply Point 04f51345ce6f Reading Day Of Month | 16 |  |  |
| Supply Point 04f51345ce6f Latest Interval Reading Value | 280.00000 |  |  |
| Supply Point 04f51345ce6f Latest Interval Reading Cost | 8096.40 |  |  |
| Supply Point 04f51345ce6f Latest Interval Reading Date | 2026-06-17 |  |  |
| Supply Point 04f51345ce6f Latest Half-Hour Reading Value | 0.200000000000000000 |  |  |
| Supply Point 04f51345ce6f Latest Half-Hour Reading Cost | 5.19 |  |  |
| Supply Point 04f51345ce6f Latest Half-Hour Reading Time | 2026-06-16T12:30:00+00:00 |  |  |
| Supply Point 04f51345ce6f Interval Readings Access | authorized |  | field_name=intervalReadings |
| Supply Point 04f51345ce6f Half-Hour Readings Access | authorized |  | field_name=halfHourlyReadings |
