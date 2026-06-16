"""Small .env reader for local demo credentials."""

from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(path: str | os.PathLike[str] = ".env", *, override: bool = False) -> dict[str, str]:
    """Load simple KEY=VALUE pairs into the process environment.

    This intentionally supports only common .env syntax and never logs values.
    Existing environment variables win unless ``override`` is true.
    """

    env_path = Path(path)
    values: dict[str, str] = {}
    if not env_path.exists():
        return values

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = _strip_inline_comment(value.strip())
        value = _strip_quotes(value)
        if not key:
            continue

        values[key] = value
        if override or key not in os.environ:
            os.environ[key] = value

    return values


def required_credential(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is required; set it in the environment or .env")
    return value


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _strip_inline_comment(value: str) -> str:
    if not value or value[0] in {"'", '"'}:
        return value
    return value.split(" #", 1)[0].rstrip()
