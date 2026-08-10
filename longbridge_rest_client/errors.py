"""Exception types raised by the Longbridge REST client."""

from __future__ import annotations

from typing import Any


class LongbridgeError(Exception):
    """Base exception for client and authentication failures."""


class OAuthError(LongbridgeError):
    """Raised when OAuth discovery, authorization, token exchange, or refresh fails."""


class LongbridgeHTTPError(LongbridgeError):
    """Raised when the REST gateway returns a non-success HTTP status."""

    def __init__(
        self,
        status: int,
        message: str,
        *,
        code: int | str | None = None,
        payload: Any = None,
    ) -> None:
        self.status = status
        self.code = code
        self.message = message
        self.payload = payload
        detail = f"HTTP {status}"
        if code is not None:
            detail += f" / code {code}"
        super().__init__(f"{detail}: {message}")


class LongbridgeAPIError(LongbridgeError):
    """Raised when the gateway returns an application-level non-zero code."""

    def __init__(
        self,
        code: int | str,
        message: str,
        *,
        payload: Any = None,
    ) -> None:
        self.code = code
        self.message = message
        self.payload = payload
        super().__init__(f"Longbridge API error {code}: {message}")
