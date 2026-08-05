from data_validation import build_validated_metrics, fetch_fx_rate


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
