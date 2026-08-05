from datetime import datetime, timedelta, timezone

import pytest
import requests

from prediction_markets import (
    DEFAULT_TOPICS,
    _parse_jina_response,
    _request,
    is_forward_looking,
    parse_json_list,
    rank_by_volume,
    render_markets,
    search_topic,
    fetch_prediction_markets,
)


def now() -> datetime:
    return datetime.now(timezone.utc)


def make_market(**overrides):
    market = {
        "question": "Will the Fed cut rates in September?",
        "outcomes": '["Yes", "No"]',
        "outcomePrices": '["0.76", "0.24"]',
        "volumeNum": 1234567,
        "endDate": (now() + timedelta(days=60)).isoformat(),
        "oneWeekPriceChange": 0.05,
        "closed": False,
    }
    market.update(overrides)
    return market


def test_parse_json_list_handles_strings_and_lists():
    assert parse_json_list('["Yes", "No"]') == ["Yes", "No"]
    assert parse_json_list(["Yes", "No"]) == ["Yes", "No"]
    assert parse_json_list("not-json") == []
    assert parse_json_list(None) == []


def test_is_forward_looking_keeps_open_future_markets():
    assert is_forward_looking(make_market(), now()) is True


def test_is_forward_looking_drops_closed_markets():
    assert is_forward_looking(make_market(closed=True), now()) is False


def test_is_forward_looking_drops_past_end_date():
    past = (now() - timedelta(days=1)).isoformat()
    assert is_forward_looking(make_market(endDate=past), now()) is False


def test_is_forward_looking_drops_markets_without_prices_or_outcomes():
    assert is_forward_looking(make_market(outcomePrices=None), now()) is False
    assert is_forward_looking(make_market(outcomes=[]), now()) is False


def test_is_forward_looking_keeps_market_with_unparseable_end_date():
    # A malformed endDate must not silently drop the market.
    assert is_forward_looking(make_market(endDate="not-a-date"), now()) is True


def test_render_markets_formats_probability_volume_and_week_change():
    text = render_markets(
        "Fed rate cut",
        [make_market()],
        limit=6,
    )

    assert '## Polymarket prediction markets: "Fed rate cut"' in text
    assert "**Will the Fed cut rates in September?** — Yes 76%" in text
    assert "$1,234,567 volume" in text
    assert "1-week +5.0pp" in text


def test_rank_by_volume_orders_markets_most_traded_first():
    markets = [
        make_market(question="Low volume", volumeNum=100),
        make_market(question="High volume", volumeNum=999999),
        make_market(question="Mid volume", volumeNum=500),
    ]
    ranked = rank_by_volume(markets)

    assert [m["question"] for m in ranked] == [
        "High volume", "Mid volume", "Low volume",
    ]


def test_render_markets_truncates_to_limit_without_ranking():
    markets = [
        make_market(question="First", volumeNum=100),
        make_market(question="Second", volumeNum=999999),
        make_market(question="Third", volumeNum=500),
    ]
    text = render_markets("topic", markets, limit=2)

    assert "First" in text
    assert "Second" in text
    assert "Third" not in text


def test_render_markets_reports_no_match_without_inventing_markets():
    text = render_markets("nothing matches", [], limit=6)

    assert "No open prediction markets matched 'nothing matches'" in text


def test_render_markets_skips_market_with_unparseable_price():
    markets = [make_market(question="Broken", outcomePrices='["abc", "def"]')]
    text = render_markets("topic", markets, limit=6)

    assert "Broken" not in text


def test_parse_jina_response_extracts_json_payload():
    text = (
        "Title: \n\nURL Source: https://gamma-api.polymarket.com/x\n\n"
        "Published Time: Mon, 03 Aug 2026 10:42:29 GMT\n\n"
        "Markdown Content:\n{\"events\":[{\"id\":\"1\"}]}"
    )
    assert _parse_jina_response(text) == {"events": [{"id": "1"}]}


def test_parse_jina_response_raises_without_json_payload():
    with pytest.raises(ValueError):
        _parse_jina_response("<html>blocked</html>")


def test_request_falls_back_to_jina_proxy_when_direct_blocked(monkeypatch):
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(url)
        if url.startswith("https://gamma-api.polymarket.com"):
            raise requests.exceptions.ConnectionError("blocked")
        return type("Resp", (), {
            "raise_for_status": lambda self: None,
            "text": "Markdown Content:\n{\"events\":[{\"id\":\"1\"}]}",
        })()

    monkeypatch.setattr("prediction_markets.requests.get", fake_get)
    result = _request("public-search", {"q": "recession"})

    assert result == {"events": [{"id": "1"}]}
    assert calls.count("https://gamma-api.polymarket.com/public-search") == 2
    assert len([url for url in calls if url.startswith("https://r.jina.ai/")]) == 1
    assert "r.jina.ai" in calls[-1]


def test_request_raises_original_error_when_proxy_also_fails(monkeypatch):
    def fake_get(url, params=None, timeout=None):
        raise requests.exceptions.ConnectionError("still blocked")

    monkeypatch.setattr("prediction_markets.requests.get", fake_get)
    with pytest.raises(requests.exceptions.ConnectionError):
        _request("public-search", {"q": "recession"})


def test_search_topic_degrades_on_network_error(monkeypatch):
    def fake_request(path, params):
        raise requests.exceptions.ConnectionError("network down")

    monkeypatch.setattr("prediction_markets._request", fake_request)
    text = search_topic("Fed rate cut")

    assert "prediction-market data unavailable: ConnectionError" in text
    assert "not rated for this topic" in text


def test_fetch_prediction_markets_keeps_topics_independent(monkeypatch):
    def fake_search(topic, limit=None):
        return f"## topic: {topic} (limit={limit})\n"

    monkeypatch.setattr("prediction_markets.search_topic", fake_search)
    text = fetch_prediction_markets()

    assert "## topic: Fed rate cut (limit=6)" in text
    assert "## topic: recession (limit=6)" in text
    assert "## topic: US election (limit=6)" in text


def test_default_topics_are_macro_relevant():
    assert DEFAULT_TOPICS == ["Fed rate cut", "recession", "US election"]
