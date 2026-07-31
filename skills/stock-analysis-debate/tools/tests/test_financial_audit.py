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

MU_FUNDAMENTALS = """# Company Fundamentals for MU

PE Ratio (TTM): 16.695171
Forward PE: 5.689233
EPS (TTM): 52.39
Forward EPS: 153.73953
EBITDA: 68222001152
"""

MU_BALANCE_SHEET = """# Balance Sheet
,2026-05-31
Ordinary Shares Number,1129393151
Common Stock Equity,100724000000
Total Debt,6376000000
Cash Cash Equivalents And Short Term Investments,26022000000
"""

MU_INCOME_STATEMENT = """# Income Statement
,2026-05-31,2026-02-28,2025-11-30,2025-08-31,2025-05-31
Diluted EPS,24.67,12.07,4.60,2.83,1.68
Total Revenue,41456000000,23860000000,13643000000,11315000000,9301000000
Total Operating Income As Reported,33318000000,16135000000,6136000000,3654000000,2169000000
Operating Income,33318000000,16135000000,6136000000,3693000000,2169000000
"""

MU_OHLCV = """Date,Open,High,Low,Close,Volume
2026-07-29,833.00,841.80,737.88,739.00,69846000
2026-07-30,793.14,882.50,789.00,874.66,61964700
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


def test_ttm_valuation_prefers_four_quarter_eps_when_provider_snapshot_conflicts():
    metrics = compute_point_in_time_metrics(
        MU_FUNDAMENTALS,
        MU_BALANCE_SHEET,
        MU_INCOME_STATEMENT,
        MU_OHLCV,
    )

    assert metrics["provider_ttm_eps"] == 52.39
    assert metrics["statement_ttm_diluted_eps"] == pytest.approx(44.17)
    assert metrics["statement_ttm_pe"] == pytest.approx(874.66 / 44.17)
    assert metrics["ttm_eps_periods"] == [
        "2026-05-31",
        "2026-02-28",
        "2025-11-30",
        "2025-08-31",
    ]
    assert metrics["ttm_eps_difference"] == pytest.approx(
        abs(52.39 - 44.17) / 44.17
    )
    assert metrics["ttm_valuation_reconciliation_status"] == "mismatch"
    assert metrics["preferred_ttm_eps"] == pytest.approx(44.17)
    assert metrics["preferred_ttm_pe"] == pytest.approx(874.66 / 44.17)
    assert metrics["preferred_ttm_source"] == "quarterly income statement"
    assert metrics["status"] == "conflict"


def test_ttm_valuation_is_verified_when_provider_and_statement_values_reconcile():
    statement_ttm_pe = 874.66 / 44.17
    fundamentals = MU_FUNDAMENTALS.replace(
        "PE Ratio (TTM): 16.695171",
        f"PE Ratio (TTM): {statement_ttm_pe}",
    ).replace("EPS (TTM): 52.39", "EPS (TTM): 44.17")

    metrics = compute_point_in_time_metrics(
        fundamentals,
        MU_BALANCE_SHEET,
        MU_INCOME_STATEMENT,
        MU_OHLCV,
    )

    assert metrics["ttm_valuation_reconciliation_status"] == "verified"
    assert metrics["status"] == "complete"
    assert metrics["ttm_eps_difference"] == pytest.approx(0)
    assert metrics["ttm_pe_difference"] == pytest.approx(0)


def test_ttm_valuation_does_not_invent_statement_value_with_fewer_than_four_quarters():
    incomplete_income_statement = """# Income Statement
,2026-05-31,2026-02-28,2025-11-30
Diluted EPS,24.67,12.07,4.60
Total Revenue,41456000000,23860000000,13643000000
Total Operating Income As Reported,33318000000,16135000000,6136000000
Operating Income,33318000000,16135000000,6136000000
"""

    metrics = compute_point_in_time_metrics(
        MU_FUNDAMENTALS,
        MU_BALANCE_SHEET,
        incomplete_income_statement,
        MU_OHLCV,
    )

    assert metrics["statement_ttm_diluted_eps"] is None
    assert metrics["statement_ttm_pe"] is None
    assert metrics["ttm_valuation_reconciliation_status"] == "provider_only"
    assert metrics["preferred_ttm_eps"] is None
    assert metrics["preferred_ttm_pe"] is None
    assert metrics["preferred_ttm_source"] is None
    assert metrics["status"] == "partial"


def test_ttm_valuation_does_not_backfill_a_missing_recent_quarter_with_older_eps():
    gapped_income_statement = """# Income Statement
,2026-05-31,2026-02-28,2025-11-30,2025-08-31,2025-05-31
Diluted EPS,24.67,12.07,,2.83,1.68
Total Revenue,41456000000,23860000000,13643000000,11315000000,9301000000
Total Operating Income As Reported,33318000000,16135000000,6136000000,3654000000,2169000000
Operating Income,33318000000,16135000000,6136000000,3693000000,2169000000
"""

    metrics = compute_point_in_time_metrics(
        MU_FUNDAMENTALS,
        MU_BALANCE_SHEET,
        gapped_income_statement,
        MU_OHLCV,
    )

    assert metrics["ttm_eps_periods"] == [
        "2026-05-31",
        "2026-02-28",
        "2025-08-31",
    ]
    assert metrics["statement_ttm_diluted_eps"] is None
    assert metrics["ttm_valuation_reconciliation_status"] == "provider_only"
