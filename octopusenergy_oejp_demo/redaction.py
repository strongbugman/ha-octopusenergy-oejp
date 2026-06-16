"""Redaction helpers for console-safe summaries."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from typing import Any

SENSITIVE_KEY_PARTS = (
    "authorization",
    "cookie",
    "credential",
    "email",
    "jwt",
    "password",
    "refresh",
    "secret",
    "session",
    "token",
)


def redact_json(value: Any) -> Any:
    """Recursively redact secrets and likely personal identifiers."""

    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if is_sensitive_key(key_text):
                redacted[key_text] = "[REDACTED]"
            else:
                redacted[key_text] = redact_json(item)
        return redacted

    if isinstance(value, list):
        return [redact_json(item) for item in value]

    if isinstance(value, tuple):
        return tuple(redact_json(item) for item in value)

    return value


def is_sensitive_key(key: str) -> bool:
    normalized = key.replace("-", "_").lower()
    return any(part in normalized for part in SENSITIVE_KEY_PARTS)


def fingerprint(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return f"sha256:{digest[:12]}"


def redact_path(path: str) -> str:
    """Redact likely identifiers in REST paths while retaining endpoint shape."""

    substitutions = {
        "accounts": "{account}",
        "electricity-meter-points": "{meter_point}",
        "meters": "{meter}",
        "properties": "{property}",
        "agreements": "{agreement}",
    }
    parts = path.split("/")
    redacted: list[str] = []
    redact_next: str | None = None
    for part in parts:
        if not part:
            redacted.append(part)
            continue
        if redact_next:
            redacted.append(redact_next)
            redact_next = None
            continue
        redacted.append(part)
        if part in substitutions:
            redact_next = substitutions[part]
    return "/".join(redacted)


def summarize_identifiers(values: Sequence[str]) -> list[dict[str, str]]:
    unique = sorted({value for value in values if value})
    return [{"fingerprint": fingerprint(value)} for value in unique]


def scrub_error_text(text: str, *, max_length: int = 240) -> str:
    text = re.sub(r"Bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [REDACTED]", text)
    text = re.sub(r"JWT\s+[A-Za-z0-9._~+/=-]+", "JWT [REDACTED]", text)
    text = re.sub(r"Token\s+[A-Za-z0-9._~+/=-]+", "Token [REDACTED]", text)
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."
