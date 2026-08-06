import pandas as pd
import pytest

from data_validation import (
    build_validated_metrics,
    fetch_fx_rate,
    fetch_provider_snapshot,
    render_validation_report,
)


def _snapshot():
    return {
        "quote_currency": "HKD",
        "financial_currency": "CNY",
        "currency_evidence": {
            "info.currency": "HKD",
            "info.financialCurrency": "CNY",
        },
        "info": {"revenueGrowth": -0.109, "earningsGrowth": -0.581},
        "analyst_tables": {
            "earnings_estimate": [
                {"period": "0y", "avg": 1.08, "numberOfAnalysts": 17, "currency": "CNY"}
            ],
            "revenue_estimate": [],
            "eps_trend": [],
            "eps_revisions": [],
        },
    }


def _audit():
    return {
        "current_price": 28.0,
        "price_date": "2026-08-04",
        "statement_ttm_diluted_eps": 1.0,
        "statement_ttm_pe": 25.7,
        "price_to_book": 3.0,
        "ev_to_provider_ttm_ebitda": 10.0,
        "ttm_valuation_reconciliation_status": "verified",
        "ttm_periods_contiguous": True,
        "valuation_currency_status": "verified",
    }


def test_provider_snapshot_does_not_infer_financial_currency_from_estimates(monkeypatch):
    class FakeTicker:
        info = {"currency": "HKD", "financialCurrency": None}
        history_metadata = {"currency": "HKD"}

        def get_earnings_estimate(self):
            return pd.DataFrame([{"currency": "CNY"}])

        def get_revenue_estimate(self):
            return pd.DataFrame()

        def get_eps_trend(self):
            return pd.DataFrame()

        def get_eps_revisions(self):
            return pd.DataFrame()

        def get_growth_estimates(self):
            return pd.DataFrame()

    monkeypatch.setattr("data_validation.yf.Ticker", lambda symbol: FakeTicker())

    snapshot = fetch_provider_snapshot("01810.HK", "2026-08-07")

    assert snapshot["quote_currency"] == "HKD"
    assert snapshot["financial_currency"] is None
    assert snapshot["currency_evidence"]["estimate_currencies"] == ["CNY"]


def test_validated_contract_separates_actual_growth_from_consensus():
    contract = build_validated_metrics(
        ticker="01810.HK", market="HK", analysis_date="2026-08-04",
        snapshot=_snapshot(),
        fx={"status": "verified", "rate": 0.92},
        audit_metrics=_audit(),
        official_filings={"status": "available", "provider": "HKEXnews", "records": []},
        sankey_data={"revenue_sankey": [{"currency": "HKD"}]},
    )

    actual = next(
        metric for metric in contract["metrics"]
        if metric["metric_id"] == "latest_quarter_revenue_growth_yoy"
    )
    assert actual["value"] == -0.109
    assert actual["allowed_uses"] == ["historical_growth"]
    assert "historical_actual_not_consensus" in actual["quality_flags"]
    assert contract["third_party_translation"]["status"] == "translated_only"
    assert contract["gates"]["allow_exact_valuation"] is True


def test_llm_policy_allows_current_run_artifacts_without_gate_bypass():
    contract = build_validated_metrics(
        ticker="01810.HK", market="HK", analysis_date="2026-08-04",
        snapshot=_snapshot(),
        fx={"status": "verified", "rate": 0.92},
        audit_metrics=_audit(),
        official_filings={"status": "available", "provider": "HKEXnews", "records": []},
        sankey_data=None,
    )

    policy = contract["llm_policy"]
    assert policy["raw_provider_values_allowed"] is True
    assert policy["validated_metric_bypass_allowed"] is False
    assert "Current-run DATA_DIR artifacts listed in SKILL.md" in policy["allowed_input"]
    assert "Prefer tool-derived values" in policy["allowed_math"]


def test_valid_target_price_gate_records_method_period_and_inputs():
    contract = build_validated_metrics(
        ticker="01810.HK", market="HK", analysis_date="2026-08-04",
        snapshot=_snapshot(),
        fx={"status": "verified", "rate": 0.92},
        audit_metrics=_audit(),
        official_filings={"status": "available", "provider": "HKEXnews", "records": []},
        sankey_data=None,
    )

    detail = contract["gate_details"]["allow_target_price"]
    assert contract["gates"]["allow_target_price"] is True
    assert contract["gates"]["allow_strong_rating"] is True
    assert detail["allowed"] is True
    assert detail["blocking_reasons"] == []
    assert detail["forecast_period"] == "0y"
    assert detail["valuation_method"] == "forward_eps_x_explicit_scenario_pe"
    assert detail["sensitivity_required"] is True
    assert "earnings_estimate.0y.avg" in detail["required_metric_ids"]


@pytest.mark.parametrize(
    "eps,pe,expected_reason",
    [
        (None, None, "ttm_eps_not_positive"),
        (0, None, "ttm_eps_not_positive"),
        (-1, -28, "ttm_eps_not_positive"),
        (1, None, "point_in_time_pe_unavailable"),
    ],
)
def test_invalid_pe_inputs_close_pe_target_and_strong_rating(eps, pe, expected_reason):
    audit = _audit()
    audit["statement_ttm_diluted_eps"] = eps
    audit["statement_ttm_pe"] = pe
    contract = build_validated_metrics(
        ticker="01810.HK", market="HK", analysis_date="2026-08-04",
        snapshot=_snapshot(),
        fx={"status": "verified", "rate": 0.92},
        audit_metrics=audit,
        official_filings={"status": "available", "provider": "HKEXnews", "records": []},
        sankey_data=None,
    )

    assert contract["gates"]["allow_exact_pe"] is False
    assert contract["gates"]["allow_target_price"] is False
    assert contract["gates"]["allow_strong_rating"] is False
    assert expected_reason in contract["gate_details"]["allow_exact_pe"]["blocking_reasons"]


@pytest.mark.parametrize(
    "updates,expected_reason",
    [
        ({"avg": None}, "forecast_eps_not_positive"),
        ({"avg": -0.5}, "forecast_eps_not_positive"),
        ({"numberOfAnalysts": 0}, "forecast_analyst_count_invalid"),
        ({"currency": "USD"}, "forecast_currency_mismatch"),
        ({"period": "0q"}, "annual_forecast_period_missing"),
    ],
)
def test_invalid_consensus_row_closes_target_and_strong_rating(updates, expected_reason):
    snapshot = _snapshot()
    snapshot["analyst_tables"]["earnings_estimate"][0].update(updates)
    contract = build_validated_metrics(
        ticker="01810.HK", market="HK", analysis_date="2026-08-04",
        snapshot=snapshot,
        fx={"status": "verified", "rate": 0.92},
        audit_metrics=_audit(),
        official_filings={"status": "available", "provider": "HKEXnews", "records": []},
        sankey_data=None,
    )

    reasons = contract["gate_details"]["allow_target_price"]["blocking_reasons"]
    assert contract["gates"]["allow_target_price"] is False
    assert contract["gates"]["allow_strong_rating"] is False
    assert expected_reason in reasons


def test_provider_statement_mismatch_is_disclosed_and_blocks_target_confidence():
    audit = _audit()
    audit["ttm_valuation_reconciliation_status"] = "mismatch"
    contract = build_validated_metrics(
        ticker="01810.HK", market="HK", analysis_date="2026-08-04",
        snapshot=_snapshot(),
        fx={"status": "verified", "rate": 0.92},
        audit_metrics=audit,
        official_filings={"status": "available", "provider": "HKEXnews", "records": []},
        sankey_data=None,
    )

    assert contract["gates"]["allow_exact_pe"] is False
    assert contract["gates"]["allow_target_price"] is False
    assert contract["gates"]["allow_strong_rating"] is False
    assert "provider_vs_statement_ttm_valuation" in contract["quality"]["conflicting_metrics"]
    assert "provider_statement_ttm_conflict" in contract["gate_details"]["allow_target_price"]["blocking_reasons"]
    report = render_validation_report(contract)
    assert "provider_statement_ttm_conflict" in report


def test_share_count_basis_conflict_closes_all_exact_valuation_methods():
    audit = _audit()
    audit["share_count_basis_status"] = "potential_mismatch"
    contract = build_validated_metrics(
        ticker="BABA", market="US", analysis_date="2026-08-04",
        snapshot=_snapshot(),
        fx={"status": "verified", "rate": 1.0},
        audit_metrics=audit,
        official_filings={"status": "partial", "provider": "SEC EDGAR", "records": []},
        sankey_data=None,
    )

    assert contract["gates"]["allow_exact_pe"] is False
    assert contract["gates"]["allow_exact_pb"] is False
    assert contract["gates"]["allow_exact_ev_to_ebitda"] is False
    assert contract["gates"]["allow_exact_valuation"] is False
    assert "share_count_basis_mismatch" in contract["quality"]["conflicting_metrics"]


def test_missing_fx_blocks_all_exact_cross_currency_valuation_values():
    audit = _audit()
    audit["valuation_currency_status"] = "unavailable"
    contract = build_validated_metrics(
        ticker="01810.HK", market="HK", analysis_date="2026-08-04",
        snapshot=_snapshot(),
        fx={"status": "unavailable"},
        audit_metrics=audit,
        official_filings={"status": "partial", "provider": "HKEXnews", "records": []},
        sankey_data=None,
    )

    assert contract["gates"]["allow_exact_valuation"] is False
    valuation = {
        metric["metric_id"]: metric for metric in contract["metrics"]
        if metric["metric_id"] in (
            "point_in_time_pe", "point_in_time_pb", "point_in_time_ev_to_ebitda"
        )
    }
    assert all(metric["status"] == "unavailable" for metric in valuation.values())
    assert all(metric["value"] is None for metric in valuation.values())


def test_same_currency_fx_is_identity_without_network():
    assert fetch_fx_rate("USD", "USD", "2026-08-04") == {
        "status": "verified",
        "from_currency": "USD",
        "to_currency": "USD",
        "rate": 1.0,
        "rate_date": "2026-08-04",
        "provider": "identity",
    }


def test_sec_structured_fact_is_normalized_as_official_metric():
    facts = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {
                                "val": 100,
                                "end": "2026-06-30",
                                "filed": "2026-07-31",
                                "form": "10-Q",
                                "fp": "Q3",
                            }
                        ]
                    }
                }
            }
        }
    }
    contract = build_validated_metrics(
        ticker="AAPL", market="US", analysis_date="2026-08-04",
        snapshot={
            **_snapshot(),
            "quote_currency": "USD",
            "financial_currency": "USD",
        },
        fx={"status": "verified", "rate": 1.0},
        audit_metrics=_audit(),
        official_filings={"status": "available", "provider": "SEC EDGAR", "records": []},
        sankey_data=None,
        official_structured_facts=facts,
    )

    metric = next(
        item for item in contract["metrics"]
        if item["metric_id"] == "official_revenue"
    )
    assert metric["value"] == 100
    assert metric["provider"] == "SEC EDGAR XBRL"
    assert metric["status"] == "verified"
    assert metric["allowed_uses"] == ["official_fundamental_cross_check"]


def test_historical_replay_closes_snapshot_dependent_gates_even_if_values_are_present():
    temporal_context = {
        "analysis_mode": "historical_replay",
        "execution_date": "2026-08-06",
        "analysis_as_of_date": "2024-05-01",
        "analysis_timestamp": "2024-05-01T23:59:59.999999-04:00",
        "point_in_time_enforced": True,
        "source_statuses": {
            "ohlcv": {"status": "allowed"},
            "analyst_estimates": {"status": "not_rated"},
        },
    }
    contract = build_validated_metrics(
        ticker="AAPL", market="US", analysis_date="2024-05-01",
        snapshot=_snapshot(),
        fx={"status": "verified", "rate": 0.92},
        audit_metrics=_audit(),
        official_filings={"status": "available", "provider": "SEC EDGAR", "records": []},
        sankey_data=None,
        temporal_context=temporal_context,
    )

    reason = "historical_replay_non_point_in_time_valuation_inputs"
    assert contract["schema_version"] == "1.2"
    assert contract["llm_policy"]["raw_provider_values_allowed"] is False
    assert contract["gates"]["allow_exact_valuation"] is False
    assert contract["gates"]["allow_target_price"] is False
    assert contract["gates"]["allow_strong_rating"] is False
    assert reason in contract["gate_details"]["allow_exact_pe"]["blocking_reasons"]
