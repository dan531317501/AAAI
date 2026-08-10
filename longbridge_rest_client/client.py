"""Dependency-free HTTP client for Longbridge's documented REST OpenAPI."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Mapping, Sequence

from .auth import OAuth2PKCE, OAuthSettings
from .errors import LongbridgeAPIError, LongbridgeHTTPError


JSON = Any


def _query_values(params: Mapping[str, Any] | None) -> list[tuple[str, str]]:
    """Convert Python query values to repeated URL query pairs."""

    pairs: list[tuple[str, str]] = []
    for key, value in (params or {}).items():
        if value is None:
            continue
        values = value if isinstance(value, (list, tuple)) else [value]
        for item in values:
            if isinstance(item, bool):
                encoded = "true" if item else "false"
            else:
                encoded = str(item)
            pairs.append((key, encoded))
    return pairs


def _body_values(values: Mapping[str, Any]) -> dict[str, Any]:
    """Remove omitted optional JSON body fields while preserving false and zero."""

    return {key: value for key, value in values.items() if value is not None}


class LongbridgeClient:
    """Longbridge REST API client using OAuth 2.0 Bearer authentication.

    This client implements the 29 operations in the official REST OpenAPI
    specification. Real-time quotes, depth, broker queues, and trade ticks are
    delivered through the separate quote WebSocket/TCP protocol.
    """

    def __init__(
        self,
        oauth: OAuth2PKCE,
        *,
        base_url: str | None = None,
        timeout: float = 20.0,
        user_agent: str = "longbridge-rest-client/1.0",
    ) -> None:
        self.oauth = oauth
        self.base_url = (base_url or oauth.settings.base_url).rstrip("/")
        self.timeout = timeout
        self.user_agent = user_agent

    @classmethod
    def from_env(cls, **kwargs: Any) -> "LongbridgeClient":
        """Create a client from ``LONGBRIDGE_OAUTH_*`` environment variables."""

        return cls(OAuth2PKCE(OAuthSettings.from_env()), **kwargs)

    def login(self) -> str:
        """Complete OAuth login if needed and return the active access token."""

        return self.oauth.get_access_token()

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        body: Mapping[str, Any] | None = None,
    ) -> JSON:
        """Execute one authenticated request and return the original JSON payload."""

        query = urllib.parse.urlencode(_query_values(params))
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{query}"
        data = None
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.oauth.get_access_token()}",
            "User-Agent": self.user_agent,
        }
        if body is not None:
            data = json.dumps(dict(body), ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
                status = response.status
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            status = exc.code
            payload = self._decode_json(raw)
            code, message = self._error_values(payload, f"HTTP {status}")
            raise LongbridgeHTTPError(
                status,
                message,
                code=code,
                payload=payload,
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise LongbridgeHTTPError(0, str(exc)) from exc
        if status < 200 or status >= 300:
            payload = self._decode_json(raw)
            code, message = self._error_values(payload, f"HTTP {status}")
            raise LongbridgeHTTPError(status, message, code=code, payload=payload)
        payload = self._decode_json(raw)
        if isinstance(payload, dict) and "code" in payload:
            code = payload.get("code")
            if code not in (0, "0", None):
                raise LongbridgeAPIError(
                    code,
                    str(payload.get("message", "Longbridge API request failed")),
                    payload=payload,
                )
        return payload

    @staticmethod
    def _decode_json(raw: bytes) -> JSON:
        """Decode a JSON body while keeping empty successful responses as ``None``."""

        if not raw:
            return None
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LongbridgeHTTPError(0, "Longbridge returned invalid JSON") from exc

    @staticmethod
    def _error_values(payload: JSON, fallback: str) -> tuple[int | str | None, str]:
        """Extract common error fields from either an envelope or raw JSON."""

        if isinstance(payload, dict):
            return payload.get("code"), str(payload.get("message", fallback))
        return None, fallback

    @staticmethod
    def _required(name: str, value: str) -> str:
        """Validate a required non-empty string before sending a request."""

        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty string")
        return value

    # Watchlist Management

    def list_watchlist_groups(self) -> JSON:
        """GET /v1/watchlist/groups — Request: none; response: groups and securities."""

        return self._request("GET", "/v1/watchlist/groups")

    def create_watchlist_group(
        self,
        name: str,
        securities: Sequence[str] | None = None,
    ) -> JSON:
        """POST /v1/watchlist/groups — Request: name, optional securities; response: group id."""

        payload = {"name": self._required("name", name), "securities": securities}
        return self._request("POST", "/v1/watchlist/groups", body=_body_values(payload))

    def update_watchlist_group(
        self,
        group_id: str,
        *,
        name: str | None = None,
        mode: str | None = None,
        securities: Sequence[str] | None = None,
    ) -> JSON:
        """PUT /v1/watchlist/groups — Request: id/name/mode/securities; response: empty data."""

        if mode is not None and mode not in {"add", "remove", "replace"}:
            raise ValueError("mode must be add, remove, or replace")
        payload = {
            "id": self._required("group_id", group_id),
            "name": name,
            "mode": mode,
            "securities": securities,
        }
        return self._request("PUT", "/v1/watchlist/groups", body=_body_values(payload))

    def delete_watchlist_group(self, group_id: str, *, purge: bool = False) -> JSON:
        """DELETE /v1/watchlist/groups — Request: id and purge; response: empty data."""

        return self._request(
            "DELETE",
            "/v1/watchlist/groups",
            params={"id": self._required("group_id", group_id), "purge": purge},
        )

    # Quote and market snapshot

    def list_securities(self, market: str, category: str) -> JSON:
        """GET /v1/quote/get_security_list — Request: market/category; response: securities."""

        return self._request(
            "GET",
            "/v1/quote/get_security_list",
            params={
                "market": self._required("market", market),
                "category": self._required("category", category),
            },
        )

    def list_market_temperature(
        self,
        market: str,
        start_date: str,
        end_date: str,
    ) -> JSON:
        """GET /v1/quote/history_market_temperature — Request: market/date range; response: points."""

        return self._request(
            "GET",
            "/v1/quote/history_market_temperature",
            params={
                "market": self._required("market", market),
                "start_date": self._required("start_date", start_date),
                "end_date": self._required("end_date", end_date),
            },
        )

    def market_temperature(self, market: str) -> JSON:
        """GET /v1/quote/market_temperature — Request: market; response: temperature snapshot."""

        return self._request(
            "GET",
            "/v1/quote/market_temperature",
            params={"market": self._required("market", market)},
        )

    # Portfolio and cash

    def list_cash_flow(
        self,
        *,
        start_time: int | None = None,
        end_time: int | None = None,
        business_type: int | None = None,
        symbol: Sequence[str] | None = None,
        page: int | None = None,
        size: int | None = None,
    ) -> JSON:
        """GET /v1/asset/cashflow — Request: time/type/symbol/page filters; response: cash-flow list."""

        return self._request(
            "GET",
            "/v1/asset/cashflow",
            params={
                "start_time": start_time,
                "end_time": end_time,
                "business_type": business_type,
                "symbol": symbol,
                "page": page,
                "size": size,
            },
        )

    def account_cash(self, *, currency: str | None = None) -> JSON:
        """GET /v1/asset/account — Request: optional currency; response: cash and margin data."""

        return self._request("GET", "/v1/asset/account", params={"currency": currency})

    def list_stock_positions(self, *, symbol: Sequence[str] | None = None) -> JSON:
        """GET /v1/asset/stock — Request: optional symbols; response: stock positions."""

        return self._request("GET", "/v1/asset/stock", params={"symbol": symbol})

    def list_fund_positions(self, *, symbol: Sequence[str] | None = None) -> JSON:
        """GET /v1/asset/fund — Request: optional fund symbols; response: fund positions."""

        return self._request("GET", "/v1/asset/fund", params={"symbol": symbol})

    # Statements

    def list_statements(
        self,
        *,
        statement_type: int | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> JSON:
        """GET /v1/statement/list — Request: statement type/page; response: date/file_key list."""

        return self._request(
            "GET",
            "/v1/statement/list",
            params={
                "statement_type": statement_type,
                "page": page,
                "page_size": page_size,
            },
        )

    def get_statement_download_url(self, file_key: str) -> JSON:
        """GET /v1/statement/download — Request: file_key; response: presigned URL."""

        return self._request(
            "GET",
            "/v1/statement/download",
            params={"file_key": self._required("file_key", file_key)},
        )

    # News and community content

    def list_filings(self, symbol: str) -> JSON:
        """GET /v1/quote/filings — Request: symbol; response: regulatory filing items."""

        return self._request(
            "GET",
            "/v1/quote/filings",
            params={"symbol": self._required("symbol", symbol)},
        )

    def list_news(self, symbol: str) -> JSON:
        """GET /v1/content/{symbol}/news — Request: path symbol; response: news items."""

        symbol = urllib.parse.quote(self._required("symbol", symbol), safe="")
        return self._request("GET", f"/v1/content/{symbol}/news")

    def list_topics(self, symbol: str) -> JSON:
        """GET /v1/content/{symbol}/topics — Request: path symbol; response: topic summaries."""

        symbol = urllib.parse.quote(self._required("symbol", symbol), safe="")
        return self._request("GET", f"/v1/content/{symbol}/topics")

    def list_my_topics(
        self,
        *,
        page: int | None = None,
        size: int | None = None,
        topic_type: str | None = None,
    ) -> JSON:
        """GET /v1/content/topics/mine — Request: page/size/type; response: owned topics."""

        if topic_type is not None and topic_type not in {"article", "post"}:
            raise ValueError("topic_type must be article or post")
        return self._request(
            "GET",
            "/v1/content/topics/mine",
            params={"page": page, "size": size, "topic_type": topic_type},
        )

    def create_topic(
        self,
        body: str,
        *,
        title: str | None = None,
        topic_type: str | None = None,
        tickers: Sequence[str] | None = None,
        hashtags: Sequence[str] | None = None,
    ) -> JSON:
        """POST /v1/content/topics — Request: body/title/type/tickers/hashtags; response: topic."""

        if topic_type is not None and topic_type not in {"article", "post"}:
            raise ValueError("topic_type must be article or post")
        payload = {
            "title": title,
            "body": self._required("body", body),
            "topic_type": topic_type,
            "tickers": tickers,
            "hashtags": hashtags,
        }
        return self._request("POST", "/v1/content/topics", body=_body_values(payload))

    def topic_detail(self, topic_id: str) -> JSON:
        """GET /v1/content/topics/{id} — Request: topic id; response: topic detail."""

        topic_id = urllib.parse.quote(self._required("topic_id", topic_id), safe="")
        return self._request("GET", f"/v1/content/topics/{topic_id}")

    def list_topic_replies(
        self,
        topic_id: str,
        *,
        page: int | None = None,
        size: int | None = None,
    ) -> JSON:
        """GET /v1/content/topics/{topic_id}/comments — Request: topic/page/size; response: comments."""

        topic_id = urllib.parse.quote(self._required("topic_id", topic_id), safe="")
        return self._request(
            "GET",
            f"/v1/content/topics/{topic_id}/comments",
            params={"page": page, "size": size},
        )

    def create_topic_reply(
        self,
        topic_id: str,
        body: str,
        *,
        reply_to_id: str | None = None,
    ) -> JSON:
        """POST /v1/content/topics/{topic_id}/comments — Request: body/reply_to_id; response: comment."""

        topic_id = urllib.parse.quote(self._required("topic_id", topic_id), safe="")
        return self._request(
            "POST",
            f"/v1/content/topics/{topic_id}/comments",
            body=_body_values(
                {"body": self._required("body", body), "reply_to_id": reply_to_id}
            ),
        )

    # Trade and order management

    def list_history_executions(
        self,
        *,
        start_at: int | None = None,
        end_at: int | None = None,
        order_id: str | None = None,
        symbol: str | None = None,
        page: int | None = None,
    ) -> JSON:
        """GET /v1/trade/execution/history — Request: time/order/symbol/page filters; response: trades."""

        return self._request(
            "GET",
            "/v1/trade/execution/history",
            params={
                "start_at": start_at,
                "end_at": end_at,
                "order_id": order_id,
                "symbol": symbol,
                "page": page,
            },
        )

    def order_detail(self, order_id: str) -> JSON:
        """GET /v1/trade/order — Request: order_id; response: complete order detail."""

        return self._request(
            "GET",
            "/v1/trade/order",
            params={"order_id": self._required("order_id", order_id)},
        )

    def replace_order(
        self,
        order_id: str,
        *,
        quantity: str | None = None,
        price: str | None = None,
        trigger_price: str | None = None,
        limit_offset: str | None = None,
        trailing_amount: str | None = None,
        trailing_percent: str | None = None,
        limit_depth_level: int | None = None,
        trigger_count: int | None = None,
        monitor_price: str | None = None,
        remark: str | None = None,
    ) -> JSON:
        """PUT /v1/trade/order — Request: order replacement fields; response: empty data."""

        payload = {
            "order_id": self._required("order_id", order_id),
            "quantity": quantity,
            "price": price,
            "trigger_price": trigger_price,
            "limit_offset": limit_offset,
            "trailing_amount": trailing_amount,
            "trailing_percent": trailing_percent,
            "limit_depth_level": limit_depth_level,
            "trigger_count": trigger_count,
            "monitor_price": monitor_price,
            "remark": remark,
        }
        return self._request("PUT", "/v1/trade/order", body=_body_values(payload))

    def cancel_order(self, order_id: str) -> JSON:
        """DELETE /v1/trade/order — Request: order_id; response: empty data."""

        return self._request(
            "DELETE",
            "/v1/trade/order",
            params={"order_id": self._required("order_id", order_id)},
        )

    def estimate_max_buy_quantity(
        self,
        symbol: str,
        order_type: str,
        side: str,
        *,
        price: str | None = None,
        currency: str | None = None,
        market: str | None = None,
        fractional_shares: bool | None = None,
        order_id: str | None = None,
    ) -> JSON:
        """GET /v1/trade/estimate/buy_limit — Request: order estimate fields; response: cash/margin limits."""

        return self._request(
            "GET",
            "/v1/trade/estimate/buy_limit",
            params={
                "symbol": self._required("symbol", symbol),
                "order_type": self._required("order_type", order_type),
                "side": self._required("side", side),
                "price": price,
                "currency": currency,
                "market": market,
                "fractional_shares": fractional_shares,
                "order_id": order_id,
            },
        )

    def list_history_orders(
        self,
        *,
        start_at: int | None = None,
        end_at: int | None = None,
        symbol: str | None = None,
        market: str | None = None,
        side: str | None = None,
        status: Sequence[str] | None = None,
        page: int | None = None,
        size: int | None = None,
    ) -> JSON:
        """GET /v1/trade/order/history — Request: order filters/page; response: historical orders."""

        return self._request(
            "GET",
            "/v1/trade/order/history",
            params={
                "start_at": start_at,
                "end_at": end_at,
                "symbol": symbol,
                "market": market,
                "side": side,
                "status": status,
                "page": page,
                "size": size,
            },
        )

    def list_today_executions(
        self,
        *,
        order_id: str | None = None,
        symbol: str | None = None,
    ) -> JSON:
        """GET /v1/trade/execution/today — Request: optional order/symbol; response: today's trades."""

        return self._request(
            "GET",
            "/v1/trade/execution/today",
            params={"order_id": order_id, "symbol": symbol},
        )

    def list_today_orders(
        self,
        *,
        symbol: str | None = None,
        market: str | None = None,
        side: str | None = None,
        status: Sequence[str] | None = None,
        order_id: str | None = None,
        page: int | None = None,
        size: int | None = None,
    ) -> JSON:
        """GET /v1/trade/order/today — Request: order filters/page; response: today's orders."""

        return self._request(
            "GET",
            "/v1/trade/order/today",
            params={
                "symbol": symbol,
                "market": market,
                "side": side,
                "status": status,
                "order_id": order_id,
                "page": page,
                "size": size,
            },
        )
