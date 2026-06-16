# Octopus Energy OEJP Home Assistant Prototype

Greenfield Python demo for exploring the Octopus Energy Japan/Korea OEJP Kraken electricity REST API before turning it into a full Home Assistant custom integration.

The prototype is shaped around the OEJP REST guide at <https://developer.oejp-kraken.energy/guides/rest/>. The sandbox used to create this project could not resolve that host, so the default REST host and auth path are configurable with environment variables.

## What Is Included

- Standard-library Python REST client with sync methods and async wrappers.
- GraphQL bootstrap helper for `obtainKrakenToken`; the REST guide says authenticated REST calls use the token described in the GraphQL/authentication flow.
- CLI discovery command that authenticates with `OCTOPUS_EMAIL` and `OCTOPUS_PASSWORD`, fetches a GraphQL account/electricity snapshot, probes REST account/electricity endpoints with the same token, prints a redacted JSON summary, and writes raw successful data payloads to `.local/oejp_raw_payloads.json`.
- Home Assistant `custom_components/octopusenergy_oejp` skeleton: manifest, config flow, coordinator, and sensors.
- Pytest tests with mocked HTTP responses. No real credentials are used by tests.

## Setup

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[test]"
cp .env.example .env
```

Edit `.env`:

```bash
OCTOPUS_EMAIL=you@example.com
OCTOPUS_PASSWORD=your-password
```

Optional overrides:

```bash
OCTOPUS_BASE_URL=https://api.oejp-kraken.energy
OCTOPUS_AUTH_PATH=/v1/auth/login/
OCTOPUS_AUTH_SCHEME=Bearer
```

## Run The Demo

```bash
python -m octopusenergy_oejp_demo discover
```

or, after installing the package:

```bash
oejp-demo discover
```

The command prints only a redacted summary. Successful raw data payloads are written to `.local/oejp_raw_payloads.json`, which is ignored by git. Authentication token responses are not saved as raw payloads.

Useful options:

```bash
oejp-demo discover --output .local/my-run.json
oejp-demo discover --auth-path /v1/auth/login/
oejp-demo discover --max-pages 3 --max-derived-requests 25
```

## Discovery Behavior

The client first uses the GraphQL `obtainKrakenToken` mutation to turn the email/password login into a Kraken JWT, then fetches a safe account/electricity snapshot to discover account numbers, properties, supply points, agreements, bills, and transactions. It then uses that same JWT to probe likely REST resources.

In the verified OEJP account used during development, GraphQL account/electricity data was available, but the customer-facing REST account/electricity endpoints returned 403/404. That is reported explicitly by the CLI instead of being treated as a crash.

The REST probe starts with roots such as:

- `/v1/accounts/`
- `/v1/me/`
- `/v1/customer/`
- `/v1/properties/`
- `/v1/electricity-meter-points/`

It extracts account numbers, property IDs, electricity meter point IDs, and meter serials from successful payloads, then tries derived endpoints for account details, properties, meter points, agreements, tariffs, bills, payments, transactions, readings, and consumption. Missing endpoints are expected during discovery and are reported as failures without stopping the run.

## Tests

```bash
python -m pytest
```

The test suite injects a fake transport, so it does not contact OEJP Kraken and does not need `.env`.

## Home Assistant Skeleton

The `custom_components/octopusenergy_oejp` directory is intentionally a skeleton. It shows the expected integration boundaries:

- `config_flow.py` collects credentials and optional REST overrides.
- `coordinator.py` calls the demo discovery client asynchronously.
- `sensor.py` exposes prototype discovery status sensors.

This is not ready to copy directly into a production Home Assistant install. A later integration pass should replace broad endpoint discovery with stable entities based on confirmed payloads from your account.

## Security Notes

- Do not commit `.env` or `.local/` output files.
- The CLI never prints passwords or tokens.
- Raw payload files can contain account and energy-use data. They are useful for local reverse engineering but should be treated as private.
