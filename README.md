# Octopus Energy OEJP — Home Assistant Custom Integration

A Home Assistant custom integration for the Octopus Energy Japan/Korea (OEJP) Kraken API.
It authenticates via the GraphQL `obtainKrakenToken` mutation and exposes account, property,
supply point, bill, and transaction data as HA sensors.

## Installation

Copy `custom_components/octopusenergy_oejp/` into your Home Assistant `config/custom_components/`
directory and restart HA. Then add the integration via **Settings → Integrations → Add Integration →
Octopus Energy OEJP**.

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
| Supply Point `{fingerprint}` Status         | e.g. `ACTIVE`       |
| Supply Point `{fingerprint}` Agreements     | Agreement count     |

## Data Update

The coordinator polls every 15 minutes using `async_add_executor_job` so the stdlib
`urllib` GraphQL call does not block the HA event loop.

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

## Security Notes

- `.env` and `.local/` are git-ignored. Do not commit them.
- The integration never logs passwords or tokens.
- Entity names, unique IDs, and diagnostic attributes use short SHA-256 fingerprints for account and supply-point identifiers instead of exposing raw account numbers/SPINs.
