from datetime import datetime, timezone

import pandas as pd

from price_attribution_data import (
    build_price_context,
    render_expectations_context,
    select_comparators,
)


def _history(closes):
    dates = pd.date_range("2026-07-01", periods=len(closes), freq="B")
    return pd.DataFrame(
        {"Close": closes, "Volume": [1000 + index for index in range(len(closes))]},
        index=dates,
    )


def test_select_comparators_uses_market_and_sector_specific_proxies():
    assert select_comparators("US", "AMZN", "Consumer Cyclical") == [
        {"kind": "broad_market", "label": "S&P 500", "symbol": "^GSPC"},
        {
            "kind": "sector_proxy",
            "label": "Consumer Discretionary Select Sector SPDR",
            "symbol": "XLY",
        },
    ]
    assert select_comparators("HK", "00700.HK", "Communication Services") == [
        {"kind": "broad_market", "label": "Hang Seng Index", "symbol": "^HSI"},
        {"kind": "sector_proxy", "label": "Hang Seng TECH Index", "symbol": "^HSTECH"},
    ]
    assert select_comparators("CN", "600519.SH", "Consumer Defensive") == [
        {"kind": "broad_market", "label": "CSI 300", "symbol": "000300.SS"},
        {"kind": "local_market", "label": "SSE Composite", "symbol": "000001.SS"},
    ]


def test_price_context_computes_absolute_and_excess_returns_for_fixed_windows():
    target = _history([100 + index for index in range(25)])
    broad = _history([200 + index for index in range(25)])
    sector = _history([300 + 2 * index for index in range(25)])
    comparators = [
        {"kind": "broad_market", "label": "Broad", "symbol": "BROAD"},
        {"kind": "sector_proxy", "label": "Sector", "symbol": "SECTOR"},
    ]

    context = build_price_context(
        target_symbol="TEST",
        market="US",
        sector="Technology",
        target_history=target,
        comparators=comparators,
        comparator_histories={"BROAD": broad, "SECTOR": sector},
        analysis_date="2026-08-04",
    )

    expected_target_5d = round((124 / 119 - 1) * 100, 4)
    expected_broad_5d = round((224 / 219 - 1) * 100, 4)
    assert context["windows"]["5d"]["target_return_pct"] == expected_target_5d
    assert (
        context["windows"]["5d"]["comparators"]["broad_market"][
            "target_excess_return_pct"
        ]
        == round(expected_target_5d - expected_broad_5d, 4)
    )
    assert context["windows"]["20d"]["status"] == "available"
    assert len(context["daily_series"]) == 25


def test_price_context_marks_missing_comparator_not_rated_without_losing_target_return():
    context = build_price_context(
        target_symbol="TEST",
        market="US",
        sector=None,
        target_history=_history([100, 101, 102, 103, 104, 105]),
        comparators=[{"kind": "broad_market", "label": "Broad", "symbol": "BROAD"}],
        comparator_histories={"BROAD": None},
        analysis_date="2026-08-04",
    )

    assert context["windows"]["5d"]["target_return_pct"] == 5.0
    assert (
        context["windows"]["5d"]["comparators"]["broad_market"]["status"]
        == "not_rated"
    )
    assert "relative performance Not Rated" not in context["warnings"][0]
    assert "unavailable" in context["warnings"][0]


def test_expectations_context_filters_future_events_and_warns_about_snapshot_timing():
    earnings = pd.DataFrame(
        {
            "EPS Estimate": [2.0, 3.0],
            "Reported EPS": [2.2, None],
            "Surprise(%)": [10.0, None],
        },
        index=pd.to_datetime(["2026-07-30", "2026-10-30"], utc=True),
    )
    ratings = pd.DataFrame(
        {
            "Firm": ["Before", "After"],
            "Action": ["up", "down"],
            "FromGrade": ["Hold", "Buy"],
            "ToGrade": ["Buy", "Hold"],
        },
        index=pd.to_datetime(["2026-07-15", "2026-08-10"], utc=True),
    )

    text = render_expectations_context(
        target_symbol="TEST",
        analysis_date="2026-08-04",
        info={"targetMeanPrice": 123.0, "recommendationKey": "buy"},
        earnings_dates=earnings,
        upgrades_downgrades=ratings,
        retrieved_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
    )

    assert "2026-07-30" in text
    assert "2026-10-30" not in text
    assert "Before" in text
    assert "After" not in text
    assert "MUST NOT by themselves prove" in text
    assert "| Target Mean Price | 123 |" in text


def test_expectations_context_accepts_rating_date_column():
    ratings = pd.DataFrame(
        {
            "GradeDate": ["2026-08-01"],
            "Firm": ["Example Research"],
            "Action": ["up"],
            "FromGrade": ["Hold"],
            "ToGrade": ["Buy"],
        }
    )

    text = render_expectations_context(
        target_symbol="TEST",
        analysis_date="2026-08-04",
        info={},
        earnings_dates=None,
        upgrades_downgrades=ratings,
        retrieved_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
    )

    assert "2026-08-01" in text
    assert "Example Research" in text


def test_expectations_context_labels_info_growth_as_historical_actual():
    estimate = pd.DataFrame(
        {"avg": [1.08], "numberOfAnalysts": [17], "currency": ["CNY"]},
        index=["0y"],
    )
    text = render_expectations_context(
        target_symbol="01810.HK",
        analysis_date="2026-08-04",
        info={
            "revenueGrowth": -0.109,
            "earningsGrowth": -0.581,
            "financialCurrency": "CNY",
        },
        earnings_dates=None,
        upgrades_downgrades=None,
        earnings_estimate=estimate,
        retrieved_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
    )

    assert "Latest-Quarter Historical Growth" in text
    assert "Revenue Growth (actual YoY)" in text
    assert "Structured Analyst Estimates" in text
    assert "| 0y | 1.08 | 17 | CNY |" in text
