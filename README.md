# Octopus Energy OEJP — Home Assistant Custom Integration

A Home Assistant custom integration for the Octopus Energy Japan/Korea (OEJP) Kraken API.
It authenticates via the GraphQL `obtainKrakenToken` mutation and exposes account, property,
supply point, bill, and transaction data as HA sensors.

## Installation

### Manual install from zip

Build or download the release zip, then extract it into your Home Assistant config directory so the
integration lands at:

```text
/config/custom_components/octopusenergy_oejp/manifest.json
```

For a local build from this repository:

```bash
.venv/bin/python scripts/package_integration.py
```

This creates `dist/octopusenergy_oejp-<version>.zip`. The archive contains
`custom_components/octopusenergy_oejp/...` at the correct Home Assistant path and excludes local
caches, tests, reports, API notes, `.env` files, and secret-looking files.

After extracting the zip, restart Home Assistant. Home Assistant reads `manifest.json` and installs
the listed `requirements` such as `httpx>=0.27` when the custom integration is loaded. Then add the
integration via **Settings → Integrations → Add Integration → Octopus Energy OEJP**.

### Manual install by copy

If you are installing directly from a checkout, copy `custom_components/octopusenergy_oejp/` into
your Home Assistant `/config/custom_components/` directory, restart Home Assistant, and add the
integration from the UI. Do not copy `.env`, `.local/`, `reports/`, or test data into Home
Assistant.

## Configuration

| Field        | Required | Default                             | Description                  |
|--------------|----------|-------------------------------------|------------------------------|
| Email        | Yes      |                                     | OEJP Kraken account email    |
| Password     | Yes      |                                     | OEJP Kraken account password |
| API Base URL | No       | `https://api.oejp-kraken.energy`    | Override GraphQL base URL    |

The integration appends `/v1/graphql/` to the base URL.

## Sensors Created

**Summary (always created):**

| Sensor                     | State                          |
|----------------------------|-------------------------------|
| Account Count              | Number of accounts             |
| Property Count             | Number of properties           |
| Electricity Supply Points  | Total supply points            |
| Bills Total                | Total bill count               |
| Transactions Total         | Total transaction count        |
| Active Agreements          | Active supply agreements       |

**Per account** (one set per account; account numbers are shown as short fingerprints, not raw IDs):

| Sensor                                  | State                    |
|-----------------------------------------|--------------------------|
| Account `{fingerprint}` Balance         | Account balance          |
| Account `{fingerprint}` Status          | e.g. `ACTIVE`            |
| Account `{fingerprint}` Bills Total     | Bill count               |
| Account `{fingerprint}` Transactions    | Transaction count        |

**Per electricity supply point** (one set per point; supply point IDs/SPINs are not exposed in names):

| Sensor                                      | State               |
|---------------------------------------------|---------------------|
| Supply Point `{fingerprint}` Status                     | e.g. `ON_SUPPLY` / `ACTIVE` |
| Supply Point `{fingerprint}` Agreements                 | Agreement count             |
| Supply Point `{fingerprint}` Meter Count                | Meter count                 |
| Supply Point `{fingerprint}` Next Reading Date          | Next scheduled reading date |
| Supply Point `{fingerprint}` Next Next Reading Date     | Following reading date      |
| Supply Point `{fingerprint}` Reading Day Of Month       | Reading day number          |
| Supply Point `{fingerprint}` Latest Interval Reading Value | Latest monthly/interval value, if authorized |
| Supply Point `{fingerprint}` Latest Interval Reading Cost  | Latest interval cost estimate, if authorized |
| Supply Point `{fingerprint}` Latest Interval Reading Date  | Latest interval reading date, if authorized |
| Supply Point `{fingerprint}` Latest Half-Hour Reading Value | Latest half-hour value, if authorized |
| Supply Point `{fingerprint}` Latest Half-Hour Reading Cost  | Latest half-hour cost estimate, if authorized |
| Supply Point `{fingerprint}` Latest Half-Hour Average Power | Average W derived from latest half-hour kWh; not live instantaneous power |
| Supply Point `{fingerprint}` Latest Half-Hour Average Cost Rate | Effective JPY/kWh derived from latest half-hour cost/value |
| Supply Point `{fingerprint}` Latest Half-Hour Reading Time  | Latest half-hour start time, if authorized |
| Supply Point `{fingerprint}` Interval Readings Access      | `authorized`, `unauthorized`, `disabled`, or `error` |
| Supply Point `{fingerprint}` Half-Hour Readings Access     | `authorized`, `unauthorized`, `disabled`, or `error` |
| Supply Point `{fingerprint}` Today Consumption             | Current JST day half-hourly consumption in kWh |
| Supply Point `{fingerprint}` Today Cost                    | Current JST day half-hourly cost estimate in JPY |
| Supply Point `{fingerprint}` This Week Consumption         | Current Monday-start JST week consumption in kWh |
| Supply Point `{fingerprint}` This Week Cost                | Current Monday-start JST week cost estimate in JPY |
| Supply Point `{fingerprint}` This Month Consumption        | Current JST calendar month consumption in kWh |
| Supply Point `{fingerprint}` This Month Cost               | Current JST calendar month cost estimate in JPY |

Latest half-hour average power uses Home Assistant power metadata (`W`, measurement state class).
Latest half-hour average cost rate uses `JPY/kWh` with measurement state class. Both include
attributes naming `halfHourlyReadings` as the source plus the source reading start/end where
available; the power sensor is an interval average and is not instantaneous live power.

Aggregate consumption sensors use Home Assistant energy metadata (`kWh`, total state class).
Aggregate cost sensors use monetary metadata (`JPY`, total state class). Aggregate attributes include
`start`, `end`, `reading_count`, `total_consumption`, `total_cost`, `currency`, and
`source=halfHourlyReadings`. If any included half-hourly reading lacks `costEstimate`, the cost
sensor state is unavailable while consumption still sums from `value`.

## Data Update

The coordinator polls every 15 minutes with a persistent async `httpx` GraphQL client. Half-hourly
readings are fetched from the earlier of the current JST week start and month start through the
current time, which covers the today/week/month aggregate sensors.

## Local Development & Tests

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[test]"
cp .env.example .env   # fill in OCTOPUS_EMAIL / OCTOPUS_PASSWORD
```

Run tests (no credentials required — GraphQL is mocked):

```bash
.venv/bin/python -m pytest
```

Syntax check all modules:

```bash
.venv/bin/python -m compileall -q custom_components tests
```

A redacted real-account data report can be generated by running the integration API against `.env` credentials and writing `reports/real_account_data_report.md`. The committed report in `reports/` contains counts, field availability, optional consumption access status, and sensor availability without raw account/supply identifiers or address data.

## Security Notes

- `.env` and `.local/` are git-ignored. Do not commit them.
- The integration never logs passwords or tokens.
- Entity names, unique IDs, and diagnostic attributes use short SHA-256 fingerprints for account and supply-point identifiers instead of exposing raw account numbers/SPINs.
