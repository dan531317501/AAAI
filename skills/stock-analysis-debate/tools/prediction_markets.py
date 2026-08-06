#!/usr/bin/env python3
"""Polymarket prediction-market fetcher for the skill.

Ported from TradingAgents' ``tradingagents/dataflows/polymarket.py``. Surfaces
live, market-implied probabilities for forward-looking events (Fed decisions,
recession, elections, geopolitics) to the News Analyst — what the crowd prices
to happen next, complementing news (what happened) and FRED macro data (where
things stand).

Uses Polymarket's public Gamma API (https://gamma-api.polymarket.com) — no
key, no auth. Each market's ``outcomePrices`` are the implied probabilities of
its outcomes (a "Yes" at 0.76 means the market prices a 76% chance).

Usage (normally invoked from fetch_data.py):
    python prediction_markets.py <ANALYSIS_DATE> [--limit 6]
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import datetime, timezone
from urllib.parse import urlencode

import requests

from provider_runtime import RetryPolicy, retry_call

logger = logging.getLogger(__name__)

GAMMA_BASE = "https://gamma-api.polymarket.com"
# Jina AI Reader proxy: relays any public URL when the target host is
# unreachable from the local network (Polymarket's domains are blocked on some
# networks; the proxy itself is reachable). Free tier, no key required.
JINA_PROXY_BASE = "https://r.jina.ai/"

# Network timeout (seconds). Shorter than the other fetchers on purpose: the
# skill prefetches several topics per run, and a dead endpoint should degrade
# fast rather than stall the whole pipeline (3 topics x timeout).
REQUEST_TIMEOUT = 15

# Default number of markets per topic, ranked by traded volume.
DEFAULT_LIMIT = 6

# Event topics prefetched for every run — macro and geopolitical events that
# are broadly relevant to any market. Sector/company-specific topics are left
# to the analyst to reason about from these signals.
DEFAULT_TOPICS = [
    "Fed rate cut",
    "recession",
    "US election",
]


def _parse_jina_response(text: str) -> dict:
    """Extract the JSON payload from a Jina Reader proxy response.

    Jina renders the proxied document as markdown, so a JSON API response
    arrives as a ``Markdown Content:`` block carrying the raw JSON text.
    """
    match = re.search(r"Markdown Content:\s*(\{.*\})\s*$", text, re.S)
    if not match:
        raise ValueError("Jina proxy response did not contain a JSON payload")
    return json.loads(match.group(1))


def _request(path: str, params: dict) -> dict:
    """GET a Gamma API endpoint; Jina Reader proxy first, direct as fallback.

    Polymarket's domains are blocked on some networks, so route the request
    through the Jina Reader proxy first — it relays the request from its own
    servers and stays reachable where Polymarket is not. The original
    exception is re-raised when both paths fail so the caller sees one
    consistent failure.
    """
    url = f"{GAMMA_BASE}/{path}"
    query = url + ("?" + urlencode(params) if params else "")
    try:
        def proxy_call():
            proxied = requests.get(
                JINA_PROXY_BASE + query, timeout=REQUEST_TIMEOUT
            )
            proxied.raise_for_status()
            return _parse_jina_response(proxied.text)

        return retry_call(
            proxy_call,
            provider="Jina Reader",
            operation=f"polymarket_proxy.{path}",
            policy=RetryPolicy(
                max_attempts=2,
                base_delay_seconds=0.25,
                max_delay_seconds=0.25,
            ),
            validator=lambda value: isinstance(value, dict),
        )
    except (requests.RequestException, ValueError) as proxy_exc:
        logger.warning("Jina proxy failed (%s); trying direct Gamma API", proxy_exc)
        try:
            def direct_call():
                response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
                response.raise_for_status()
                return response.json()

            return retry_call(
                direct_call,
                provider="Polymarket Gamma",
                operation=path,
                policy=RetryPolicy(
                    max_attempts=2,
                    base_delay_seconds=0.25,
                    max_delay_seconds=0.25,
                ),
                validator=lambda value: isinstance(value, dict),
            )
        except (requests.RequestException, ValueError) as direct_exc:
            logger.warning("Direct Gamma API also failed: %s", direct_exc)
            raise proxy_exc from direct_exc


def parse_json_list(value) -> list:
    """Gamma encodes ``outcomes``/``outcomePrices`` as JSON-string arrays."""
    if isinstance(value, list):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return []


def is_forward_looking(market: dict, now: datetime) -> bool:
    """Keep only open markets that resolve in the future.

    ``closed`` is the reliable resolved flag (``active`` stays True even for
    settled markets), and a past ``endDate`` means the event already resolved —
    either way it is not a forward-looking signal.
    """
    if market.get("closed"):
        return False
    end_date = market.get("endDate")
    if end_date:
        try:
            if datetime.fromisoformat(end_date.replace("Z", "+00:00")) < now:
                return False
        except ValueError:
            pass
    return bool(parse_json_list(market.get("outcomePrices"))) and bool(
        parse_json_list(market.get("outcomes"))
    )


def rank_by_volume(markets: list[dict]) -> list[dict]:
    """Rank markets by traded volume, highest first (deepest = most reliable)."""
    return sorted(markets, key=lambda market: market.get("volumeNum") or 0, reverse=True)


def render_markets(topic: str, markets: list[dict], limit: int) -> str:
    """Render a list of candidate markets for one topic as markdown lines."""
    header = (
        f'## Polymarket prediction markets: "{topic}"\n'
        f"Live, market-implied probabilities (higher traded volume = deeper, "
        f"more reliable). A probability is the crowd's priced odds of the event, "
        f"not a forecast to take as certain.\n"
    )
    if not markets:
        return header + (
            f"\nNo open prediction markets matched '{topic}'. Polymarket "
            f"coverage is concentrated in macro, political, geopolitical, and "
            f"crypto events; a specific equity may have none.\n"
        )

    lines = []
    for market in markets[:limit]:
        prices = parse_json_list(market.get("outcomePrices"))
        outcomes = parse_json_list(market.get("outcomes"))
        try:
            prob = float(prices[0])
        except (ValueError, IndexError):
            continue
        label = outcomes[0] if outcomes else "Yes"
        volume = market.get("volumeNum") or 0
        end_date = (market.get("endDate") or "")[:10]
        week_change = market.get("oneWeekPriceChange")
        week_str = (
            f", 1-week {week_change * 100:+.1f}pp"
            if isinstance(week_change, (int, float)) and week_change
            else ""
        )
        lines.append(
            f"- **{market.get('question')}** — {label} {prob:.0%} "
            f"(${volume:,.0f} volume, resolves {end_date}{week_str})"
        )
    return header + "\n" + "\n".join(lines) + "\n"


def search_topic(topic: str, limit: int | None = None) -> str:
    """Return prediction-market probabilities for one event topic.

    Degrades to a placeholder on expected provider transport or payload
    errors, so one unavailable topic never aborts the pipeline.
    """
    if limit is None:
        limit = DEFAULT_LIMIT
    try:
        data = _request("public-search", {"q": topic, "limit_per_type": 20})
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Polymarket search failed for %r: %s", topic, exc)
        return (
            f'## Polymarket prediction markets: "{topic}"\n'
            f"<prediction-market data unavailable: {type(exc).__name__} — "
            f"not rated for this topic>\n"
        )

    now = datetime.now(timezone.utc)
    candidates = [
        market
        for event in data.get("events", [])
        for market in event.get("markets", [])
        if is_forward_looking(market, now)
    ]
    return render_markets(topic, rank_by_volume(candidates), limit)


def fetch_prediction_markets(
    topics: list[str] | None = None,
    limit: int | None = None,
) -> str:
    """Fetch the default topic set into one ``prediction_markets.txt`` block.

    Each topic degrades independently, so one failed topic never blanks the
    whole block.
    """
    if topics is None:
        topics = DEFAULT_TOPICS
    if limit is None:
        limit = DEFAULT_LIMIT
    blocks = [f"# Polymarket Prediction Markets (fetched {datetime.now(timezone.utc).date()})\n"]
    for topic in topics:
        blocks.append(search_topic(topic, limit))
    return "\n".join(blocks)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch Polymarket prediction markets and print a prediction_markets.txt block"
    )
    parser.add_argument("analysis_date", help="Analysis date in YYYY-MM-DD (informational)")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    args = parser.parse_args()

    print(fetch_prediction_markets(limit=args.limit))


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    main()
