"""Reusable REST client for the OEJP Kraken electricity API prototype."""

from __future__ import annotations

import asyncio
import json
import os
import ssl
from dataclasses import dataclass
from typing import Any, Callable, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import Request, urlopen

from .redaction import scrub_error_text

DEFAULT_BASE_URL = "https://api.oejp-kraken.energy"
DEFAULT_AUTH_PATHS = (
    "/v1/auth/login/",
    "/v1/auth/token/",
    "/v1/tokens/obtain/",
    "/v1/token-auth/",
)
DEFAULT_AUTH_SCHEME = "Bearer"
TOKEN_KEYS = ("access", "access_token", "token", "auth_token", "jwt", "id_token")


@dataclass(frozen=True)
class PreparedRequest:
    method: str
    url: str
    headers: dict[str, str]
    body: bytes | None = None
    timeout: float = 30.0


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    data: Any
    headers: dict[str, str]
    url: str
    raw_text: str = ""


class ApiError(RuntimeError):
    """Raised when a REST call returns a non-successful response."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        url: str | None = None,
        response_data: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.url = url
        self.response_data = response_data


class AuthError(ApiError):
    """Raised when none of the configured auth endpoints works."""


Transport = Callable[[PreparedRequest], HttpResponse]


class UrllibTransport:
    """Small JSON HTTP transport backed by urllib."""

    def __call__(self, request: PreparedRequest) -> HttpResponse:
        req = Request(
            request.url,
            data=request.body,
            headers=request.headers,
            method=request.method,
        )
        context = ssl.create_default_context()
        try:
            with urlopen(req, timeout=request.timeout, context=context) as response:  # noqa: S310
                raw = response.read().decode("utf-8")
                return HttpResponse(
                    status_code=response.status,
                    data=_decode_json(raw),
                    headers=dict(response.headers.items()),
                    url=response.url,
                    raw_text=raw,
                )
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            raise ApiError(
                f"HTTP {exc.code} for {request.method} {request.url}",
                status_code=exc.code,
                url=request.url,
                response_data=_decode_json(raw),
            ) from exc
        except URLError as exc:
            reason = scrub_error_text(str(exc.reason))
            raise ApiError(f"Network error for {request.method} {request.url}: {reason}", url=request.url) from exc


class OctopusOejpClient:
    """REST API client with sync methods and async wrappers.

    The OEJP REST guide is the contract this prototype follows. Runtime URL/path
    overrides are deliberately exposed because Kraken environments can differ by
    tenant and rollout stage.
    """

    def __init__(
        self,
        *,
        email: str,
        password: str,
        base_url: str = DEFAULT_BASE_URL,
        auth_paths: Iterable[str] | None = None,
        auth_scheme: str = DEFAULT_AUTH_SCHEME,
        timeout: float = 30.0,
        transport: Transport | None = None,
    ) -> None:
        if not email:
            raise ValueError("email is required")
        if not password:
            raise ValueError("password is required")
        self.email = email
        self._password = password
        self.base_url = base_url.rstrip("/") + "/"
        self.auth_paths = tuple(auth_paths or DEFAULT_AUTH_PATHS)
        self.auth_scheme = auth_scheme
        self.timeout = timeout
        self._transport = transport or UrllibTransport()
        self._token: str | None = None
        self.authenticated_via: str | None = None

    @classmethod
    def from_env(cls, *, transport: Transport | None = None, timeout: float = 30.0) -> "OctopusOejpClient":
        auth_path = os.environ.get("OCTOPUS_AUTH_PATH")
        auth_paths = (auth_path,) if auth_path else None
        return cls(
            email=os.environ["OCTOPUS_EMAIL"],
            password=os.environ["OCTOPUS_PASSWORD"],
            base_url=os.environ.get("OCTOPUS_BASE_URL", DEFAULT_BASE_URL),
            auth_paths=auth_paths,
            auth_scheme=os.environ.get("OCTOPUS_AUTH_SCHEME", DEFAULT_AUTH_SCHEME),
            timeout=timeout,
            transport=transport,
        )

    @property
    def is_authenticated(self) -> bool:
        return self._token is not None

    def authenticate(self) -> None:
        if self._token:
            return

        attempts: list[dict[str, Any]] = []
        for path in self.auth_paths:
            try:
                response = self.request(
                    "POST",
                    path,
                    json_body={"email": self.email, "password": self._password},
                    authenticated=False,
                )
            except ApiError as exc:
                attempts.append(
                    {
                        "path": path,
                        "status_code": exc.status_code,
                        "error": scrub_error_text(str(exc)),
                    }
                )
                continue

            token = _find_token(response.data)
            if token:
                self._token = token
                self.authenticated_via = path
                return

            attempts.append(
                {
                    "path": path,
                    "status_code": response.status_code,
                    "error": "response did not contain a recognized access token field",
                }
            )

        raise AuthError(
            "Authentication failed for all configured REST auth endpoints",
            response_data={"attempts": attempts},
        )

    async def async_authenticate(self) -> None:
        await asyncio.to_thread(self.authenticate)

    def get_json(self, path_or_url: str, *, params: dict[str, Any] | None = None) -> HttpResponse:
        self.authenticate()
        return self.request("GET", path_or_url, params=params, authenticated=True)

    async def async_get_json(self, path_or_url: str, *, params: dict[str, Any] | None = None) -> HttpResponse:
        return await asyncio.to_thread(self.get_json, path_or_url, params=params)

    def request(
        self,
        method: str,
        path_or_url: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any | None = None,
        authenticated: bool = True,
    ) -> HttpResponse:
        url = self._make_url(path_or_url, params=params)
        headers = {
            "Accept": "application/json",
            "User-Agent": "ha-octopusenergy-oejp-demo/0.1.0",
        }
        body: bytes | None = None
        if json_body is not None:
            body = json.dumps(json_body, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if authenticated:
            if not self._token:
                raise AuthError("client is not authenticated")
            headers["Authorization"] = f"{self.auth_scheme} {self._token}"

        response = self._transport(
            PreparedRequest(
                method=method.upper(),
                url=url,
                headers=headers,
                body=body,
                timeout=self.timeout,
            )
        )
        if response.status_code >= 400:
            raise ApiError(
                f"HTTP {response.status_code} for {method.upper()} {url}",
                status_code=response.status_code,
                url=url,
                response_data=response.data,
            )
        return response

    def _make_url(self, path_or_url: str, *, params: dict[str, Any] | None = None) -> str:
        parsed = urlparse(path_or_url)
        if parsed.scheme and parsed.netloc:
            url = path_or_url
        else:
            url = urljoin(self.base_url, path_or_url.lstrip("/"))
        if params:
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}{urlencode(params, doseq=True)}"
        return url


def _decode_json(raw: str) -> Any:
    if raw == "":
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _find_token(data: Any) -> str | None:
    if isinstance(data, dict):
        for key in TOKEN_KEYS:
            token = data.get(key)
            if isinstance(token, str) and token:
                return token
        for value in data.values():
            token = _find_token(value)
            if token:
                return token
    elif isinstance(data, list):
        for value in data:
            token = _find_token(value)
            if token:
                return token
    return None
