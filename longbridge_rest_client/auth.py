"""OAuth 2.0 Authorization Code + PKCE support for Longbridge OpenAPI."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Mapping

from .errors import OAuthError


def _base64url(value: bytes) -> str:
    """Return an RFC 7636-compatible base64url value without padding."""

    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


@dataclass(frozen=True)
class OAuthSettings:
    """OAuth settings that an application must provide."""

    client_id: str
    client_secret: str | None = None
    base_url: str = "https://openapi.longbridge.com"
    redirect_uri: str = "http://127.0.0.1:8765/callback"
    scope: str = "openapi"
    token_path: Path | None = None
    timeout: float = 20.0

    @classmethod
    def from_env(cls) -> "OAuthSettings":
        """Create settings from environment variables without logging secrets."""

        client_id = os.getenv("LONGBRIDGE_OAUTH_CLIENT_ID", "").strip()
        if not client_id:
            raise OAuthError(
                "LONGBRIDGE_OAUTH_CLIENT_ID is required; register an OAuth client first."
            )
        client_secret = os.getenv("LONGBRIDGE_OAUTH_CLIENT_SECRET") or None
        return cls(
            client_id=client_id,
            client_secret=client_secret,
            base_url=os.getenv(
                "LONGBRIDGE_OPENAPI_BASE_URL",
                "https://openapi.longbridge.com",
            ).rstrip("/"),
            redirect_uri=os.getenv(
                "LONGBRIDGE_OAUTH_REDIRECT_URI",
                "http://127.0.0.1:8765/callback",
            ),
            scope=os.getenv("LONGBRIDGE_OAUTH_SCOPE", "openapi"),
        )


@dataclass
class OAuthToken:
    """Persisted OAuth token values."""

    access_token: str
    refresh_token: str | None = None
    expires_at: float | None = None
    token_type: str = "Bearer"

    @classmethod
    def from_response(cls, payload: Mapping[str, Any]) -> "OAuthToken":
        """Build a token from the OAuth token endpoint response."""

        access_token = str(payload.get("access_token", ""))
        if not access_token:
            raise OAuthError("OAuth token response did not contain access_token.")
        expires_in = payload.get("expires_in")
        expires_at = None
        if expires_in is not None:
            try:
                expires_at = time.time() + float(expires_in)
            except (TypeError, ValueError) as exc:
                raise OAuthError("OAuth token response has invalid expires_in.") from exc
        return cls(
            access_token=access_token,
            refresh_token=payload.get("refresh_token"),
            expires_at=expires_at,
            token_type=str(payload.get("token_type", "Bearer")),
        )

    @classmethod
    def from_file(cls, path: Path) -> "OAuthToken":
        """Read a token from a local JSON token cache."""

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return cls(
                access_token=str(payload["access_token"]),
                refresh_token=payload.get("refresh_token"),
                expires_at=payload.get("expires_at"),
                token_type=str(payload.get("token_type", "Bearer")),
            )
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise OAuthError(f"Cannot read OAuth token cache: {path}") from exc

    def to_dict(self) -> dict[str, Any]:
        """Return the token representation used by the local cache."""

        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
            "token_type": self.token_type,
        }

    def is_valid(self, *, clock: Callable[[], float] = time.time) -> bool:
        """Return whether the access token remains valid with a safety margin."""

        if not self.access_token:
            return False
        if self.expires_at is None:
            return True
        return clock() < float(self.expires_at) - 60.0


class OAuth2PKCE:
    """Manage Longbridge OAuth login, refresh, and local token persistence.

    The first call to :meth:`get_access_token` opens the browser when no valid
    cached token exists. Register the configured redirect URI in the OAuth
    application before starting the client.
    """

    authorization_path = "/oauth2/authorize"
    token_path = "/oauth2/token"

    def __init__(
        self,
        settings: OAuthSettings,
        *,
        browser_open: Callable[[str], bool] | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if not settings.client_id:
            raise OAuthError("OAuth client_id must not be empty.")
        self.settings = settings
        self._browser_open = browser_open or webbrowser.open
        self._clock = clock
        self._lock = Lock()
        self._token: OAuthToken | None = None

    @property
    def cache_path(self) -> Path:
        """Return the token cache path without exposing token contents."""

        if self.settings.token_path is not None:
            return Path(self.settings.token_path).expanduser()
        safe_client_id = "".join(
            character if character.isalnum() or character in "-_" else "_"
            for character in self.settings.client_id
        )
        return (
            Path.home()
            / ".longbridge"
            / "openapi"
            / "tokens"
            / f"{safe_client_id}.json"
        )

    def _load_cached_token(self) -> OAuthToken | None:
        path = self.cache_path
        if not path.exists():
            return None
        try:
            return OAuthToken.from_file(path)
        except OAuthError:
            return None

    def _save_token(self, token: OAuthToken) -> None:
        path = self.cache_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(token.to_dict(), indent=2), encoding="utf-8")
        try:
            path.chmod(0o600)
        except OSError:
            pass
        self._token = token

    def _post_form(self, values: Mapping[str, Any]) -> dict[str, Any]:
        """POST an OAuth form and decode its JSON response."""

        body = urllib.parse.urlencode(
            {key: value for key, value in values.items() if value is not None}
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{self.settings.base_url}{self.token_path}",
            data=body,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "longbridge-rest-client/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.settings.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            raise OAuthError(f"OAuth token request failed with HTTP {exc.code}: {raw}") from exc
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise OAuthError(f"OAuth token request failed: {exc}") from exc
        if not isinstance(payload, dict):
            raise OAuthError("OAuth token endpoint returned a non-object response.")
        if payload.get("error"):
            raise OAuthError(
                f"OAuth token endpoint returned {payload.get('error')}: "
                f"{payload.get('error_description', '')}".strip()
            )
        return payload

    def build_authorization_url(
        self,
        *,
        state: str | None = None,
        code_verifier: str | None = None,
    ) -> tuple[str, str, str]:
        """Build the authorization URL and return ``(url, state, verifier)``."""

        state = state or secrets.token_urlsafe(32)
        code_verifier = code_verifier or _base64url(secrets.token_bytes(32))
        challenge = _base64url(hashlib.sha256(code_verifier.encode("ascii")).digest())
        query = urllib.parse.urlencode(
            {
                "response_type": "code",
                "client_id": self.settings.client_id,
                "redirect_uri": self.settings.redirect_uri,
                "scope": self.settings.scope,
                "state": state,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )
        return (
            f"{self.settings.base_url}{self.authorization_path}?{query}",
            state,
            code_verifier,
        )

    def exchange_code(
        self,
        code: str,
        code_verifier: str,
        *,
        redirect_uri: str | None = None,
    ) -> OAuthToken:
        """Exchange an authorization code for an access and refresh token."""

        payload = self._post_form(
            {
                "grant_type": "authorization_code",
                "client_id": self.settings.client_id,
                "client_secret": self.settings.client_secret,
                "redirect_uri": redirect_uri or self.settings.redirect_uri,
                "code": code,
                "code_verifier": code_verifier,
            }
        )
        token = OAuthToken.from_response(payload)
        self._save_token(token)
        return token

    def refresh(self, refresh_token: str | None = None) -> OAuthToken:
        """Refresh an access token using the OAuth refresh-token grant."""

        refresh_token = refresh_token or (self._token and self._token.refresh_token)
        if not refresh_token:
            cached = self._load_cached_token()
            refresh_token = cached and cached.refresh_token
        if not refresh_token:
            raise OAuthError("No refresh_token is available.")
        payload = self._post_form(
            {
                "grant_type": "refresh_token",
                "client_id": self.settings.client_id,
                "client_secret": self.settings.client_secret,
                "refresh_token": refresh_token,
            }
        )
        token = OAuthToken.from_response(payload)
        if not token.refresh_token:
            token.refresh_token = refresh_token
        self._save_token(token)
        return token

    def complete_redirect(
        self,
        redirect_url: str,
        *,
        state: str,
        code_verifier: str,
    ) -> OAuthToken:
        """Validate a callback URL and exchange its authorization code."""

        parsed = urllib.parse.urlparse(redirect_url)
        values = urllib.parse.parse_qs(parsed.query)
        returned_state = values.get("state", [None])[0]
        if returned_state != state:
            raise OAuthError("OAuth state validation failed.")
        if values.get("error"):
            raise OAuthError(
                f"OAuth authorization failed: {values['error'][0]}"
            )
        code = values.get("code", [None])[0]
        if not code:
            raise OAuthError("OAuth callback did not contain an authorization code.")
        return self.exchange_code(code, code_verifier)

    def login_interactive(self, *, timeout: float = 300.0) -> OAuthToken:
        """Open a local browser callback flow and persist the resulting token."""

        parsed_redirect = urllib.parse.urlparse(self.settings.redirect_uri)
        if parsed_redirect.hostname not in {"127.0.0.1", "localhost"}:
            raise OAuthError(
                "Interactive login requires a localhost redirect_uri; use "
                "complete_redirect for a remote callback."
            )
        if parsed_redirect.port is None:
            raise OAuthError("Local redirect_uri must include an explicit port.")
        expected_path = parsed_redirect.path or "/"
        authorization_url, state, verifier = self.build_authorization_url()
        result: dict[str, str] = {}
        client = self

        class CallbackHandler(BaseHTTPRequestHandler):
            """Capture one OAuth callback without logging query parameters."""

            def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
                parsed = urllib.parse.urlparse(self.path)
                if parsed.path != expected_path:
                    self.send_response(404)
                    self.end_headers()
                    return
                result["url"] = urllib.parse.urlunparse(
                    ("http", parsed_redirect.netloc, parsed.path, "", parsed.query, "")
                )
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(
                    b"<html><body>Authorization received. You may close this window.</body></html>"
                )

            def log_message(self, format: str, *args: Any) -> None:
                return

        server = HTTPServer((parsed_redirect.hostname, parsed_redirect.port), CallbackHandler)
        server.timeout = 1.0
        deadline = self._clock() + timeout
        try:
            if not client._browser_open(authorization_url):
                print(f"Open this URL in a browser to authorize: {authorization_url}")
            while "url" not in result and self._clock() < deadline:
                server.handle_request()
        finally:
            server.server_close()
        if "url" not in result:
            raise OAuthError("Timed out waiting for the OAuth callback.")
        return self.complete_redirect(result["url"], state=state, code_verifier=verifier)

    def get_access_token(self) -> str:
        """Return a valid access token, refreshing or interactively obtaining it."""

        with self._lock:
            if self._token and self._token.is_valid(clock=self._clock):
                return self._token.access_token
            cached = self._load_cached_token()
            if cached and cached.is_valid(clock=self._clock):
                self._token = cached
                return cached.access_token
            refresh_token = (self._token and self._token.refresh_token) or (
                cached and cached.refresh_token
            )
            if refresh_token:
                try:
                    return self.refresh(refresh_token).access_token
                except OAuthError:
                    pass
            return self.login_interactive().access_token
