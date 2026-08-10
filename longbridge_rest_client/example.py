"""Minimal runnable example: configure OAuth, then call a REST endpoint."""

from __future__ import annotations

from longbridge_rest_client import LongbridgeClient


def main() -> None:
    # Set LONGBRIDGE_OAUTH_CLIENT_ID before running this example.
    # The first call opens a browser for OAuth consent and caches the token.
    client = LongbridgeClient.from_env()
    response = client.list_securities(market="US", category="Overnight")
    print(response)


if __name__ == "__main__":
    main()
