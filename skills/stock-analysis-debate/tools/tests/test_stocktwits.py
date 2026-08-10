import pytest

from stocktwits import (
    normalize_symbol,
    parse_stream,
    fetch_stocktwits_messages,
)


def make_message(username, sentiment, body="hello world"):
    msg = {
        "created_at": "2026-08-03T10:00:00Z",
        "user": {"username": username},
        "entities": {"sentiment": {"basic": sentiment}} if sentiment else {},
        "body": body,
    }
    return msg


def test_normalize_symbol_upper_cases():
    assert normalize_symbol("aapl") == "AAPL"
    assert normalize_symbol("00700.HK") == "00700.HK"


def test_parse_stream_counts_bullish_bearish_unlabeled_and_ratio():
    data = {
        "messages": [
            make_message("bull1", "Bullish"),
            make_message("bull2", "Bullish"),
            make_message("bear1", "Bearish"),
            make_message("undecided", None),
        ]
    }
    text = parse_stream(data, limit=30)

    assert "Bullish: 2 (50%)" in text
    assert "Bearish: 1 (25%)" in text
    assert "Unlabeled: 1" in text
    assert "Total: 4 most-recent messages" in text
    assert "[2026-08-03T10:00:00Z · @bull1 · Bullish] hello world" in text
    assert "[2026-08-03T10:00:00Z · @undecided · no-label] hello world" in text


def test_parse_stream_returns_placeholder_for_empty_stream():
    assert parse_stream({}, 30) == "<no StockTwits messages found>"
    assert parse_stream({"messages": []}, 30) == "<no StockTwits messages found>"


def test_parse_stream_truncates_long_bodies():
    data = {"messages": [make_message("user", "Bullish", "x" * 400)]}
    text = parse_stream(data, limit=30)

    assert "x" * 281 not in text  # truncated at 280 + ellipsis
    assert "…" in text


def test_parse_stream_respects_limit():
    data = {"messages": [make_message(f"u{i}", "Bullish") for i in range(50)]}
    text = parse_stream(data, limit=10)

    assert text.count("· @u") == 10


def test_parse_stream_zero_ratio_when_no_messages_is_not_division_by_zero():
    data = {"messages": [make_message("u", None)]}
    text = parse_stream(data, limit=30)

    assert "Bullish: 0 (0%)" in text
    assert "Bearish: 0 (0%)" in text


def test_fetch_stocktwits_messages_degrades_on_network_error(monkeypatch):
    def fake_urlopen(req, timeout=None):
        raise ConnectionError("network down")

    monkeypatch.setattr("stocktwits.urlopen", fake_urlopen)
    text = fetch_stocktwits_messages("AAPL")

    assert "<stocktwits unavailable: ConnectionError>" in text
