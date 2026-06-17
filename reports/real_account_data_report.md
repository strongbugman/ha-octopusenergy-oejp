# OEJP Real Account Data Report

Generated: `2026-06-16T09:27:19.017465+00:00`

This report is redacted. It excludes email, password, tokens, raw account numbers, raw property IDs, raw supply point IDs/SPINs, and addresses.

## Summary

| Metric | Value |
|---|---:|
| Accounts | 1 |
| Properties | 1 |
| Electricity supply points | 1 |
| Meters | 0 |
| Agreements | 3 |
| Bills total | 14 |
| Transactions total | 0 |

## GraphQL optional consumption access

| Field | Status | Error codes | Message |
|---|---|---|---|
| `intervalReadings` | `unauthorized` | `KT-CT-4501` | Unauthorized. |
| `halfHourlyReadings` | `unauthorized` | `KT-CT-4501` | Unauthorized. |

## Accounts and supply points

### Account 1 `66712481bd54`

| Field | Availability |
|---|---|
| `status` | present |
| `balance` | present |
| `bills_total` | present |
| `transactions_total` | present |
| `market_supply_agreements_total` | present |

- Properties: `1`
- Bill samples returned: `5`
- Transaction samples returned: `0`
- Market agreement samples returned: `1`

#### Property 1 `663572073b85`

- Address field present: `True`
- Postcode field present: `True`
- Supply points: `1`

##### Supply point 1 `04f51345ce6f`

| Field | Value / Availability |
|---|---|
| `status` | `ON_SUPPLY` |
| `spin_present` | `True` |
| `next_reading_date` | `2026-04-15` |
| `next_next_reading_date` | `2026-05-15` |
| `reading_date_day_of_month` | `16` |
| `meter_count` | `0` |
| `agreement_count` | `2` |
| `supply_details_count` | `0` |
| `supply_periods_count` | `0` |
| `interval_readings_count` | `0` |
| `half_hourly_readings_count` | `0` |
| `interval_access` | `unauthorized` |
| `half_hourly_access` | `unauthorized` |

Latest interval reading: `not available`
Latest half-hour reading: `not available`

## Sensors expected to populate

### Summary sensors

- `Account Count`: available
- `Property Count`: available
- `Electricity Supply Points`: available
- `Bills Total`: available
- `Transactions Total`: available
- `Active Agreements`: available

### Account sensors

- `Balance`: 1/1 accounts available
- `Status`: 1/1 accounts available
- `Bills Total`: 1/1 accounts available
- `Transactions Total`: 1/1 accounts available

### Supply point sensors

- `Status`: 1/1 supply points available
- `Agreements`: 1/1 supply points available
- `Meter Count`: 1/1 supply points available
- `Next Reading Date`: 1/1 supply points available
- `Next Next Reading Date`: 1/1 supply points available
- `Reading Day Of Month`: 1/1 supply points available
- `Latest Interval Reading Value`: 0/1 supply points available
- `Latest Interval Reading Cost`: 0/1 supply points available
- `Latest Interval Reading Date`: 0/1 supply points available
- `Latest Half-Hour Reading Value`: 0/1 supply points available
- `Latest Half-Hour Reading Cost`: 0/1 supply points available
- `Latest Half-Hour Reading Time`: 0/1 supply points available
- `Interval Readings Access`: 1/1 supply points available
- `Half-Hour Readings Access`: 1/1 supply points available
