from __future__ import annotations

import json
import tempfile
import unittest
import urllib.parse
from pathlib import Path
from unittest.mock import patch

from longbridge_rest_client.auth import OAuth2PKCE, OAuthSettings, OAuthToken
from longbridge_rest_client.client import LongbridgeClient
from longbridge_rest_client.errors import LongbridgeAPIError


class FakeOAuth:
    def get_access_token(self) -> str:
        return "test-access-token"


class FakeResponse:
    def __init__(self, payload: object, status: int = 200) -> None:
        self.payload = payload
        self.status = status

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class LongbridgeClientTests(unittest.TestCase):
    def test_create_watchlist_group_sends_auth_and_json_body(self) -> None:
        captured: dict[str, object] = {}

        def fake_urlopen(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return FakeResponse({"code": 0, "message": "success", "data": {"id": "1"}})

        client = LongbridgeClient(FakeOAuth(), base_url="https://example.test")
        with patch("longbridge_rest_client.client.urllib.request.urlopen", fake_urlopen):
            response = client.create_watchlist_group(
                "Research",
                securities=["AAPL.US", "700.HK"],
            )

        request = captured["request"]
        self.assertEqual(response["data"]["id"], "1")
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-access-token")
        self.assertEqual(
            json.loads(request.data.decode("utf-8")),
            {"name": "Research", "securities": ["AAPL.US", "700.HK"]},
        )

    def test_array_query_values_are_repeated_and_optional_values_are_omitted(self) -> None:
        captured: dict[str, object] = {}

        def fake_urlopen(request, timeout):
            captured["request"] = request
            return FakeResponse({"code": 0, "message": "success", "data": {"list": []}})

        client = LongbridgeClient(FakeOAuth(), base_url="https://example.test")
        with patch("longbridge_rest_client.client.urllib.request.urlopen", fake_urlopen):
            client.list_cash_flow(symbol=["AAPL.US", "700.HK"], page=2)

        request = captured["request"]
        query = urllib.parse.parse_qs(urllib.parse.urlparse(request.full_url).query)
        self.assertEqual(query["symbol"], ["AAPL.US", "700.HK"])
        self.assertEqual(query["page"], ["2"])
        self.assertNotIn("size", query)

    def test_nonzero_application_code_is_not_treated_as_success(self) -> None:
        def fake_urlopen(request, timeout):
            return FakeResponse({"code": 401001, "message": "token empty"})

        client = LongbridgeClient(FakeOAuth(), base_url="https://example.test")
        with patch("longbridge_rest_client.client.urllib.request.urlopen", fake_urlopen):
            with self.assertRaises(LongbridgeAPIError) as context:
                client.market_temperature("US")
        self.assertEqual(context.exception.code, 401001)

    def test_oauth_authorization_url_uses_pkce_and_state(self) -> None:
        auth = OAuth2PKCE(
            OAuthSettings(
                client_id="client-123",
                redirect_uri="http://127.0.0.1:8765/callback",
            )
        )
        url, state, verifier = auth.build_authorization_url()
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        self.assertEqual(query["client_id"], ["client-123"])
        self.assertEqual(query["state"], [state])
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertTrue(query["code_challenge"][0])
        self.assertGreaterEqual(len(verifier), 43)

    def test_oauth_token_cache_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            token_path = Path(directory) / "token.json"
            token = OAuthToken(
                access_token="access",
                refresh_token="refresh",
                expires_at=2_000_000_000,
            )
            token_path.write_text(json.dumps(token.to_dict()), encoding="utf-8")
            loaded = OAuthToken.from_file(token_path)
            self.assertEqual(loaded.access_token, "access")
            self.assertEqual(loaded.refresh_token, "refresh")
            self.assertTrue(loaded.is_valid(clock=lambda: 1_000_000_000))


if __name__ == "__main__":
    unittest.main()
