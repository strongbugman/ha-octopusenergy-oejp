"""Command-line demo for OEJP Kraken REST discovery."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .client import OctopusOejpClient
from .discovery import discover_account_electricity_data, save_raw_payloads
from .env import load_dotenv, required_credential

DEFAULT_RAW_OUTPUT = ".local/oejp_raw_payloads.json"


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    load_dotenv(args.env_file)

    if args.command == "discover":
        return _run_discover(args)

    parser.print_help()
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="oejp-demo",
        description="Discover account/electricity data available through the OEJP Kraken REST API.",
    )
    parser.add_argument("--env-file", default=".env", help="Path to a local .env file.")
    subparsers = parser.add_subparsers(dest="command")

    discover = subparsers.add_parser("discover", help="Authenticate and probe documented REST endpoints.")
    discover.add_argument(
        "--output",
        default=os.environ.get("OCTOPUS_OUTPUT_PATH", DEFAULT_RAW_OUTPUT),
        help="Gitignored JSON file for raw successful data payloads.",
    )
    discover.add_argument(
        "--no-save-raw",
        action="store_true",
        help="Do not write raw successful payloads to disk.",
    )
    discover.add_argument(
        "--base-url",
        default=None,
        help="Override OCTOPUS_BASE_URL for this run.",
    )
    discover.add_argument(
        "--auth-path",
        default=None,
        help="Override OCTOPUS_AUTH_PATH for this run.",
    )
    discover.add_argument(
        "--auth-scheme",
        default=None,
        help="Override OCTOPUS_AUTH_SCHEME for this run.",
    )
    discover.add_argument("--timeout", type=float, default=30.0)
    discover.add_argument("--max-pages", type=int, default=10)
    discover.add_argument("--max-derived-requests", type=int, default=100)
    return parser


def _run_discover(args: argparse.Namespace) -> int:
    try:
        email = required_credential("OCTOPUS_EMAIL")
        password = required_credential("OCTOPUS_PASSWORD")
    except RuntimeError as exc:
        print(json.dumps({"error": str(exc)}, indent=2), file=sys.stderr)
        return 2

    base_url = args.base_url or os.environ.get("OCTOPUS_BASE_URL")
    auth_path = args.auth_path or os.environ.get("OCTOPUS_AUTH_PATH")
    auth_scheme = args.auth_scheme or os.environ.get("OCTOPUS_AUTH_SCHEME")

    client = OctopusOejpClient(
        email=email,
        password=password,
        base_url=base_url or "https://api.oejp-kraken.energy",
        auth_paths=(auth_path,) if auth_path else None,
        auth_scheme=auth_scheme or "Bearer",
        timeout=args.timeout,
    )
    report = discover_account_electricity_data(
        client,
        max_pages=args.max_pages,
        max_derived_requests=args.max_derived_requests,
    )

    output_path: str | None = None
    if not args.no_save_raw and report.raw_payloads:
        output_path = str(Path(args.output))
        save_raw_payloads(report, output_path)

    summary = report.summary(raw_output_path=output_path)
    summary["redacted_identifier_fingerprints"] = report.redacted_identifier_summary()
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if report.authenticated else 1


if __name__ == "__main__":
    raise SystemExit(main())
