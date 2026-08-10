#!/usr/bin/env python3
"""StockTwits social-sentiment fetcher for the skill.

Ported from TradingAgents' ``tradingagents/dataflows/stocktwits.py``. Fetches
the public per-symbol message stream — no API key, no OAuth — where every
message carries a user-labeled sentiment tag (Bullish / Bearish / no-label)
plus the message body and timestamp. Rendered as a plaintext block for
``stocktwits.txt``, giving the Social Media Analyst a retail-trader sentiment
sample with an explicit Bullish/Bearish ratio.

Degrades gracefully: any HTTP/parse failure or an unknown symbol returns a
placeholder line, never an exception.

Usage (normally invoked from fetch_data.py):
    python stocktwits.py <TICKER> [--limit 30]
"""

from __future__ import annotations

import argparse
import http.client
import json
import logging
import sys
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

_API = "https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"
_UA = "tradingagents/0.2 (+https://github.com/TauricResearch/TradingAgents)"
# Body excerpt cap: StockTwits posts are short but can exceed a prompt line.
MAX_BODY_CHARS = 280


def normalize_symbol(ticker: str) -> str:
    """Map a ticker to StockTwits' symbol form (upper-cased).

    Crypto pairs would map to ``<BASE>.X`` in TradingAgents; this skill covers
    US/CN/HK equities only, so the plain upper-cased ticker is used.
    """
    return ticker.strip().upper()


def parse_stream(data: dict, limit: int = 30) -> str:
    """Render a StockTwits stream JSON payload as a plaintext block.

    Returns a placeholder when the payload has no messages. Counts
    Bullish/Bearish/no-label messages and reports the ratio so the analyst
    gets a base rate alongside the raw posts.
    """
    messages = data.get("messages", []) if isinstance(data, dict) else []
    if not messages:
        return "<no StockTwits messages found>"

    lines = []
    bullish = bearish = unlabeled = 0
    for message in messages[:limit]:
        created = message.get("created_at", "")
        user = (message.get("user") or {}).get("username", "?")
        entities = message.get("entities") or {}
        sentiment_obj = entities.get("sentiment") or {}
        sentiment = (
            sentiment_obj.get("basic")
            if isinstance(sentiment_obj, dict)
            else None
        )
        body = (message.get("body") or "").replace("\n", " ").strip()
        if len(body) > MAX_BODY_CHARS:
            body = body[:MAX_BODY_CHARS] + "…"

        if sentiment == "Bullish":
            bullish += 1
            tag = "Bullish"
        elif sentiment == "Bearish":
            bearish += 1
            tag = "Bearish"
        else:
            unlabeled += 1
            tag = "no-label"
        lines.append(f"[{created} · @{user} · {tag}] {body}")

    total = bullish + bearish + unlabeled
    bull_pct = round(100 * bullish / total) if total else 0
    bear_pct = round(100 * bearish / total) if total else 0
    summary = (
        f"Bullish: {bullish} ({bull_pct}%) · "
        f"Bearish: {bearish} ({bear_pct}%) · "
        f"Unlabeled: {unlabeled} · "
        f"Total: {total} most-recent messages"
    )
    return summary + "\n\n" + "\n".join(lines)


def fetch_stocktwits_messages(
    ticker: str,
    limit: int = 30,
    timeout: float = 10.0,
) -> str:
    """Fetch recent StockTwits messages for ``ticker`` as a plaintext block."""
    url = _API.format(ticker=normalize_symbol(ticker))
    req = Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
    except (OSError, http.client.HTTPException, json.JSONDecodeError) as exc:
        # OSError covers URLError/TimeoutError/connection resets; HTTPException
        # covers chunked-transfer errors (IncompleteRead/BadStatusLine).
        logger.warning("StockTwits fetch failed for %s: %s", ticker, exc)
        return f"<stocktwits unavailable: {type(exc).__name__}>"

    return parse_stream(data, limit)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch StockTwits messages and print a stocktwits.txt block"
    )
    parser.add_argument("ticker", help="Ticker symbol")
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args()

    print(fetch_stocktwits_messages(args.ticker, limit=args.limit))


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    main()
