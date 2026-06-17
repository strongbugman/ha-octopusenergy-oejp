#!/usr/bin/env python3
"""Executable entry point for the OEJP sensor fetch CLI.

Usage:
    python scripts/fetch_sensors.py [--format json|table] [--env-file .env]

Credentials (any of these work):
    OEJP_EMAIL=your@email.com
    OEJP_PASSWORD=yourpassword
    OEJP_BASE_URL=https://api.oejp-kraken.energy  # optional

Can also be run as a module from the repo root:
    python -m custom_components.octopusenergy_oejp.cli
"""

import sys
from pathlib import Path

# Make the repo root importable regardless of working directory
sys.path.insert(0, str(Path(__file__).parent.parent))

from custom_components.octopusenergy_oejp.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
