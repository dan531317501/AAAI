#!/usr/bin/env python3
"""Reddit community-discussion fetcher for the skill.

Ported from TradingAgents' ``tradingagents/dataflows/reddit.py``. Searches the
public Atom/RSS search feed of finance subreddits (r/wallstreetbets,
r/stocks, r/investing) for ticker mentions over the past 7 days and renders
them as a plaintext block for ``reddit.txt`` — community discussion and
engagement evidence for the Social Media Analyst.

No API key required. The richer JSON search endpoint is reliably WAF-blocked
for public clients, so this uses RSS only; RSS carries no score/comment
counts, so those metrics are omitted honestly rather than printed as zero.
On a 429 the fetcher backs off once, honouring ``Retry-After``.

Usage (normally invoked from fetch_data.py):
    python reddit.py <TICKER> [--limit 5]
"""

from __future__ import annotations

import argparse
import html
import http.client
import json
import logging
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

_API = "https://www.reddit.com/r/{sub}/search.json?{qs}"
_RSS = "https://www.reddit.com/r/{sub}/search.rss?{qs}"
# A descriptive, identified User-Agent (per Reddit's API etiquette).
_UA = "tradingagents/0.2 (+https://github.com/TauricResearch/TradingAgents)"
_ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}

# Default subreddits ordered roughly by signal density for ticker-specific
# discussion. wallstreetbets has the most volume but most noise; stocks /
# investing trend more measured.
DEFAULT_SUBREDDITS = ("wallstreetbets", "stocks", "investing")

# Self-text excerpt cap per post.
MAX_SELFTEXT_CHARS = 240


def _search_qs(ticker: str, limit: int) -> str:
    return urlencode({
        "q": ticker,
        "restrict_sr": "on",
        "sort": "new",
        "t": "week",  # last 7 days
        "limit": limit,
    })


def _iso_to_timestamp(iso_str: str | None) -> float | None:
    """Parse an Atom ``published`` timestamp to a UTC epoch, or None."""
    if not iso_str:
        return None
    try:
        normalized = iso_str[:-1] + "+00:00" if iso_str.endswith("Z") else iso_str
        return datetime.fromisoformat(normalized).timestamp()
    except (ValueError, TypeError):
        return None


def _strip_html(content: str) -> str:
    """Reduce the HTML body Reddit embeds in an Atom entry to plain text."""
    if not content:
        return ""
    # Reddit wraps the real selftext between SC_OFF / SC_ON markers.
    if "<!-- SC_OFF -->" in content and "<!-- SC_ON -->" in content:
        content = content.split("<!-- SC_OFF -->")[1].split("<!-- SC_ON -->")[0]
    text = re.sub(r"<[^>]+>", " ", content)
    return " ".join(html.unescape(text).split())


def parse_atom(xml_text: str, limit: int) -> list[dict]:
    """Parse an Atom search-feed XML payload into a list of post dicts.

    RSS carries no score/comment counts, so ``score`` and ``num_comments``
    are None and the post is tagged ``source="rss"`` for honest display.
    Returns [] on a parse error.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    posts = []
    for entry in root.findall("atom:entry", _ATOM_NS)[:limit]:
        title_el = entry.find("atom:title", _ATOM_NS)
        published_el = entry.find("atom:published", _ATOM_NS)
        content_el = entry.find("atom:content", _ATOM_NS)
        posts.append({
            "title": (title_el.text if title_el is not None else "") or "",
            "score": None,
            "num_comments": None,
            "created_utc": _iso_to_timestamp(
                published_el.text if published_el is not None else None
            ),
            "selftext": _strip_html(content_el.text if content_el is not None else ""),
            "source": "rss",
        })
    return posts


def render_posts(posts: list[dict], sub: str, ticker: str) -> str:
    """Render one subreddit's posts as a plaintext block, or a placeholder."""
    if not posts:
        return (
            f"r/{sub}: <no posts found mentioning {ticker.upper()} in the past 7 days>"
        )

    via_rss = any(p.get("source") == "rss" for p in posts)
    header = f"r/{sub} — {len(posts)} recent posts mentioning {ticker.upper()}"
    header += " (via RSS feed; scores/comments unavailable):" if via_rss else ":"
    lines = [header]
    for post in posts:
        title = (post.get("title") or "").replace("\n", " ").strip()
        created = post.get("created_utc")
        created_str = (
            time.strftime("%Y-%m-%d", time.gmtime(created)) if created else "?"
        )
        # Score / comment counts are absent on the RSS path — show only the
        # date rather than printing fake zeros.
        meta = created_str
        selftext = (post.get("selftext") or "").replace("\n", " ").strip()
        if len(selftext) > MAX_SELFTEXT_CHARS:
            selftext = selftext[:MAX_SELFTEXT_CHARS] + "…"
        lines.append(
            f"  [{meta}] {title}"
            + (f"\n    body excerpt: {selftext}" if selftext else "")
        )
    return "\n".join(lines)


def _fetch_subreddit_rss(
    ticker: str,
    sub: str,
    limit: int,
    timeout: float,
    _retry: bool = True,
) -> list[dict]:
    """Fetch and parse one subreddit's search feed; [] on failure."""
    url = _RSS.format(sub=sub, qs=_search_qs(ticker, limit))
    req = Request(url, headers={"User-Agent": _UA})
    try:
        with urlopen(req, timeout=timeout) as resp:
            return parse_atom(resp.read().decode("utf-8", errors="replace"), limit)
    except HTTPError as exc:
        if exc.code == 429 and _retry:
            wait = 5.0
            retry_after = (exc.headers.get("Retry-After") if exc.headers else None)
            try:
                wait = min(float(retry_after), 30.0) if retry_after else 5.0
            except (TypeError, ValueError):
                wait = 5.0
            logger.warning(
                "Reddit RSS 429 for r/%s · %s — backing off %.1fs then retrying once",
                sub, ticker, wait,
            )
            time.sleep(wait)
            return _fetch_subreddit_rss(ticker, sub, limit, timeout, _retry=False)
        logger.warning("Reddit RSS fetch failed for r/%s · %s: %s", sub, ticker, exc)
        return []
    except (OSError, http.client.HTTPException) as exc:
        # OSError covers URLError/TimeoutError/connection resets.
        logger.warning("Reddit RSS fetch failed for r/%s · %s: %s", sub, ticker, exc)
        return []


def fetch_reddit_posts(
    ticker: str,
    subreddits: tuple[str, ...] = DEFAULT_SUBREDDITS,
    limit_per_sub: int = 5,
    timeout: float = 10.0,
    inter_request_delay: float = 1.0,
) -> str:
    """Fetch Reddit posts mentioning ``ticker`` as a plaintext block."""
    blocks = []
    total_posts = 0
    for index, sub in enumerate(subreddits):
        if index > 0:
            time.sleep(inter_request_delay)
        posts = _fetch_subreddit_rss(ticker, sub, limit_per_sub, timeout)
        total_posts += len(posts)
        blocks.append(render_posts(posts, sub, ticker))

    if total_posts == 0:
        return (
            f"<no Reddit posts found mentioning {ticker.upper()} across "
            f"{', '.join(f'r/{s}' for s in subreddits)} in the past 7 days>"
        )
    return "\n\n".join(blocks)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch Reddit posts and print a reddit.txt block"
    )
    parser.add_argument("ticker", help="Ticker symbol")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    print(fetch_reddit_posts(args.ticker, limit_per_sub=args.limit))


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    main()
