import pytest

from financial_audit import append_audit, compute_point_in_time_metrics


FUNDAMENTALS = """# Company Fundamentals for INTC

Market Cap: 435297189888
Price to Book: 3.8914192
EBITDA: 16839999488
Book Value: 22.177
"""

BALANCE_SHEET = """# Balance Sheet
,2026-06-30,2026-03-31
Ordinary Shares Number,5043000000,5023000000
Common Stock Equity,87542000000,111394000000
Total Debt,50537000000,45031000000
Cash Cash Equivalents And Short Term Investments,29727000000,32789000000
"""

INCOME_STATEMENT = """# Income Statement
,2026-06-30,2026-03-31
Total Revenue,16128000000,13577000000
Total Operating Income As Reported,1796000000,-3136000000
Operating Income,1966000000,934000000
Restructuring And Mergern Acquisition,161000000,74000000
Other Special Charges,7000000,31000000
"""

OHLCV = """Date,Open,High,Low,Close,Volume
2026-07-27,92.46,94.98,86.94,91.67,133247300
2026-07-28,,,,,148828659
"""


def test_point_in_time_pb_uses_latest_quarter_equity_and_shares():
    metrics = compute_point_in_time_metrics(
        FUNDAMENTALS, BALANCE_SHEET, INCOME_STATEMENT, OHLCV
    )

    assert metrics["price_date"] == "2026-07-27"
    assert metrics["financial_period"] == "2026-06-30"
    assert metrics["book_value_per_share"] == pytest.approx(17.3591, rel=1e-4)
    assert metrics["price_to_book"] == pytest.approx(5.2808, rel=1e-4)
    assert metrics["price_to_book"] != pytest.approx(3.8914192)


def test_ev_to_ebitda_keeps_currency_units_and_point_in_time_market_cap():
    metrics = compute_point_in_time_metrics(
        FUNDAMENTALS, BALANCE_SHEET, INCOME_STATEMENT, OHLCV
    )

    assert metrics["point_in_time_market_cap"] == pytest.approx(462_291_810_000)
    assert metrics["simplified_enterprise_value"] == pytest.approx(483_101_810_000)
    assert metrics["ev_to_provider_ttm_ebitda"] == pytest.approx(28.6878, rel=1e-4)


def test_gaap_operating_income_prefers_as_reported_field():
    metrics = compute_point_in_time_metrics(
        FUNDAMENTALS, BALANCE_SHEET, INCOME_STATEMENT, OHLCV
    )

    assert metrics["gaap_operating_income_as_reported"] == 1_796_000_000
    assert metrics["derived_operating_income_before_reported_adjustments"] == (
        1_966_000_000
    )
    assert metrics["operating_income_reconciliation_gap"] == 170_000_000
    assert metrics["identified_operating_adjustments"] == 168_000_000
    assert metrics["operating_adjustment_residual"] == 2_000_000
    assert metrics["gaap_operating_margin"] == pytest.approx(0.11136, rel=1e-4)


def test_append_audit_replaces_existing_section_instead_of_duplicating_it():
    once = append_audit(
        FUNDAMENTALS, BALANCE_SHEET, INCOME_STATEMENT, OHLCV
    )
    twice = append_audit(
        once, BALANCE_SHEET, INCOME_STATEMENT, OHLCV
    )

    assert twice.count("## Point-in-Time Valuation and GAAP Operating Profit Audit") == 1
    assert "Point-in-Time Price to Book: 5.2808" in twice
    assert "Point-in-Time EV / Provider TTM EBITDA: 28.6878" in twice
    assert "GAAP Operating Income As Reported: 1796000000" in twice
