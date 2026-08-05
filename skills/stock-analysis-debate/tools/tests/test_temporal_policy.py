from datetime import datetime, timezone

import pytest

from temporal_policy import (
    CURRENT_RESEARCH,
    HISTORICAL_REPLAY,
    filter_historical_news,
    historical_provider_snapshot,
    resolve_temporal_context,
)


NOW = datetime(2026, 8, 6, 4, 30, tzinfo=timezone.utc)


def test_current_research_requires_the_real_execution_date():
    with pytest.raises(ValueError, match="execution date must match"):
        resolve_temporal_context(
            execution_date="2026-08-05",
            analysis_mode=CURRENT_RESEARCH,
            as_of_date=None,
            market="US",
            now=NOW,
        )


def test_current_research_uses_retrieval_time_not_end_of_day_as_cutoff():
    context = resolve_temporal_context(
        execution_date="2026-08-06",
        analysis_mode=CURRENT_RESEARCH,
        as_of_date=None,
        market="US",
        now=NOW,
    )

    assert context["analysis_timestamp"] == "2026-08-06T00:30:00-04:00"
    assert context["retrieved_at"] == "2026-08-06T04:30:00+00:00"


def test_historical_replay_separates_execution_date_and_market_cutoff():
    context = resolve_temporal_context(
        execution_date="2026-08-06",
        analysis_mode=HISTORICAL_REPLAY,
        as_of_date="2024-05-01",
        market="US",
        now=NOW,
    )

    assert context["execution_date"] == "2026-08-06"
    assert context["analysis_as_of_date"] == "2024-05-01"
    assert context["analysis_timestamp"].startswith("2024-05-01T23:59:59.999999-04:00")
    assert context["source_statuses"]["ohlcv"]["status"] == "allowed"
    assert context["source_statuses"]["analyst_estimates"]["status"] == "not_rated"
    assert context["source_statuses"]["macro_indicators"]["status"] == "not_rated"


def test_historical_replay_requires_a_non_future_cutoff():
    with pytest.raises(ValueError, match="requires --as-of-date"):
        resolve_temporal_context(
            execution_date="2026-08-06",
            analysis_mode=HISTORICAL_REPLAY,
            as_of_date=None,
            market="HK",
            now=NOW,
        )
    with pytest.raises(ValueError, match="cannot be after"):
        resolve_temporal_context(
            execution_date="2026-08-06",
            analysis_mode=HISTORICAL_REPLAY,
            as_of_date="2026-08-07",
            market="HK",
            now=NOW,
        )


def test_historical_snapshot_contains_routing_currency_but_no_mutable_facts():
    context = resolve_temporal_context(
        execution_date="2026-08-06",
        analysis_mode=HISTORICAL_REPLAY,
        as_of_date="2024-05-01",
        market="HK",
        now=NOW,
    )
    snapshot = historical_provider_snapshot(
        symbol="00700.HK", market="HK", temporal_context=context
    )

    assert snapshot["quote_currency"] == "HKD"
    assert snapshot["financial_currency"] is None
    assert snapshot["info"] == {}
    assert snapshot["analyst_tables"] == {}


def test_historical_news_excludes_missing_invalid_and_future_timestamps():
    kept, excluded = filter_historical_news(
        [
            {"title": "visible", "date": "2024-05-01 12:00"},
            {
                "title": "future",
                "date": "2024-05-01 23:00",
                "published_at": "2024-05-02T04:30:00+00:00",
            },
            {"title": "missing", "date": ""},
            {"title": "invalid", "date": "unknown"},
        ],
        "2024-05-01T23:59:59.999999-04:00",
    )

    assert [record["title"] for record in kept] == ["visible"]
    assert excluded == 3
