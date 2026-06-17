# OEJP HTTPX Async Refactor Test Report

Change tested: all GraphQL HTTP calls were migrated from stdlib `urllib` to `httpx.AsyncClient`, with async API methods and connection reuse through a persistent client instance.

## Commands run

```bash
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python -m pytest
.venv/bin/python -m compileall -q custom_components tests scripts
.venv/bin/python scripts/fetch_sensors.py --format json
.venv/bin/python scripts/fetch_sensors.py --format table
```

## Verification

```text
62 passed in 0.11s
compileall passed
script CLI returned 24 sensor records
module CLI returned 24 sensor records
stdlib HTTP scan: no urllib/urlopen/ssl.create_default_context/async_add_executor_job hits in project Python files
```

## Notes

- `httpx>=0.27` is now declared in `pyproject.toml` and Home Assistant `manifest.json` requirements.
- The unit tests include a connection-reuse test that asserts `httpx.AsyncClient` is instantiated once across multiple GraphQL calls on the same `GraphQLClient`.
- Authentication behavior remains unchanged: raw `obtainKrakenToken.token` access token in the `Authorization` header, no `JWT ` prefix, never `refreshToken`.
- Consumption queries still use official `account(accountNumber: $accountNumber)` shape.

## Real account sensor data

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
