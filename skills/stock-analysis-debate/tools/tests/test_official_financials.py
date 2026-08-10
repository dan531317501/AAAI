import official_financials
from data_validation import build_validated_metrics


def _sec_result():
    return {
        "status": "available",
        "provider": "SEC EDGAR",
        "records": [
            {
                "filed_at": "2026-07-31",
                "form": "10-Q",
                "accession_number": "0000000000-26-000001",
                "url": "https://www.sec.gov/Archives/quarterly.htm",
                "structured_numeric_data": True,
            }
        ],
        "companyfacts_url": "https://data.sec.gov/api/xbrl/companyfacts/CIK0000000000.json",
        "structured_facts": {
            "facts": {
                "us-gaap": {
                    "Revenues": {
                        "units": {
                            "USD": [
                                {
                                    "val": 120,
                                    "start": "2026-04-01",
                                    "end": "2026-06-30",
                                    "filed": "2026-07-31",
                                    "form": "10-Q",
                                    "fp": "Q2",
                                    "accn": "0000000000-26-000001",
                                },
                                {
                                    "val": 240,
                                    "start": "2026-01-01",
                                    "end": "2026-06-30",
                                    "filed": "2026-07-31",
                                    "form": "10-Q",
                                    "fp": "Q2",
                                    "accn": "0000000000-26-000001",
                                },
                            ]
                        }
                    },
                    "Assets": {
                        "units": {
                            "USD": [
                                {
                                    "val": 1000,
                                    "end": "2026-06-30",
                                    "filed": "2026-07-31",
                                    "form": "10-Q",
                                    "fp": "Q2",
                                    "accn": "0000000000-26-000001",
                                }
                            ]
                        }
                    },
                    "IssuerCustomRevenue": {
                        "units": {"USD": [{"val": 999, "end": "2026-06-30"}]}
                    },
                }
            }
        },
    }


def test_sec_returns_canonical_facts_without_converting_ytd_to_quarter(monkeypatch):
    monkeypatch.setattr(
        official_financials,
        "_sec_filings",
        lambda ticker, analysis_date, **kwargs: _sec_result(),
    )

    result = official_financials.fetch_official_financials(
        "AAPL", "US", "2026-08-04", sec_user_agent="Example contact@example.com"
    )

    assert result["status"] == "available"
    assert result["numeric_status"] == "available"
    assert result["numeric_source"] == "SEC_EDGAR_XBRL"
    assert not any(fact["raw_tag"] == "IssuerCustomRevenue" for fact in result["facts"])
    revenue = [fact for fact in result["facts"] if fact["metric"] == "revenue"]
    assert {fact["period_type"] for fact in revenue} == {"quarter", "ytd"}
    assert all(fact["source_url"].endswith("quarterly.htm") for fact in revenue)
    assets = next(fact for fact in result["facts"] if fact["metric"] == "total_assets")
    assert assets["period_type"] == "instant"
    assert assets["currency"] == "USD"


def test_hkex_document_facts_are_normalized_with_official_provenance(monkeypatch):
    monkeypatch.setattr(
        official_financials,
        "parse_official_documents",
        lambda *args, **kwargs: {
            "documents": [{"status": "available", "fact_count": 1}],
            "facts": [{
                "metric": "revenue",
                "value": 1200,
                "unit": "USD",
                "currency": "USD",
                "period_start": "2026-01-01",
                "period_end": "2026-03-31",
                "period_type": "quarter",
                "filed_at": "2026-05-26",
                "source": "HKEX_OFFICIAL_DISCLOSURE",
                "provider": "HKEXnews",
                "source_url": "https://www1.hkexnews.hk/listedco/result.pdf",
                "source_page": 15,
                "source_excerpt": "Revenue 1,200",
                "extraction_method": "pdf_text_regex",
                "official": True,
            }],
        },
    )

    result = official_financials.fetch_official_financials(
        "01810.HK",
        "HK",
        "2026-08-04",
        official_disclosures={
            "status": "available",
            "provider": "HKEXnews",
            "records": [{
                "filed_at": "2026-05-26T17:25:00",
                "title": "2026 Q1 Results Announcement",
                "url": "https://www1.hkexnews.hk/listedco/result.pdf",
                "structured_numeric_data": False,
            }],
        },
    )

    assert result["selected_source"] == "HKEX_OFFICIAL_DISCLOSURE"
    assert result["status"] == "available"
    assert result["numeric_status"] == "available"
    assert result["official_numeric_status"] == "available"
    assert result["facts"][0]["source_page"] == 15
    assert result["facts"][0]["official"] is True
    assert result["filings"][0]["filed_at"] == "2026-05-26"


def test_free_api_fallback_fills_missing_period_without_overwriting_official_fact(monkeypatch):
    monkeypatch.setattr(
        official_financials,
        "parse_official_documents",
        lambda *args, **kwargs: {
            "documents": [{"status": "available", "fact_count": 1}],
            "facts": [{
                "metric": "revenue",
                "value": 100,
                "unit": "USD",
                "currency": "USD",
                "period_start": "2026-04-01",
                "period_end": "2026-06-30",
                "period_type": "quarter",
                "source": "HKEX_OFFICIAL_DISCLOSURE",
                "provider": "HKEXnews",
                "source_url": "https://example.test/result.pdf",
                "source_page": 15,
                "extraction_method": "pdf_text_regex",
                "official": True,
            }],
        },
    )
    result = official_financials.fetch_official_financials(
        "01810.HK",
        "HK",
        "2026-08-04",
        official_disclosures={
            "provider": "HKEXnews",
            "records": [{
                "url": "https://example.test/result.pdf",
                "filed_at": "2026-05-26T17:25:00",
            }],
        },
        api_fallback={
            "symbol": "01810.HK",
            "financial_currency": "USD",
            "statements": {
                "income_stmt": (
                    ",2026-06-30,2026-03-31\n"
                    "Total Revenue,999,90\n"
                    "Net Income,10,9\n"
                ),
            },
        },
    )

    revenue = next(
        item for item in result["facts"]
        if item["metric"] == "revenue" and item["period_end"] == "2026-06-30"
    )
    assert revenue["value"] == 100
    assert revenue["official"] is True
    fallback_net_income = next(
        item for item in result["facts"] if item["metric"] == "net_income"
    )
    assert fallback_net_income["value"] == 10
    assert fallback_net_income["official"] is False
    assert result["api_fallback"]["used"] is True
    assert result["api_fallback"]["fact_count"] >= 1


def test_document_and_api_failure_remain_fail_closed(monkeypatch):
    monkeypatch.setattr(
        official_financials,
        "parse_official_documents",
        lambda *args, **kwargs: {"documents": [{"status": "unavailable"}], "facts": []},
    )
    result = official_financials.fetch_official_financials(
        "01810.HK",
        "HK",
        "2026-08-04",
        official_disclosures={
            "provider": "HKEXnews",
            "records": [{"url": "https://example.test/result.pdf"}],
        },
        api_fallback={"symbol": "01810.HK", "statements": {}},
    )

    assert result["numeric_status"] == "unavailable"
    assert result["official_numeric_status"] == "unavailable"
    assert result["facts"] == []


def test_financial_window_excludes_old_document_and_api_facts(monkeypatch):
    monkeypatch.setattr(
        official_financials,
        "parse_official_documents",
        lambda *args, **kwargs: {
            "documents": [{"status": "available", "fact_count": 2}],
            "facts": [
                {
                    "metric": "revenue",
                    "value": 100,
                    "unit": "USD",
                    "currency": "USD",
                    "period_start": "2025-07-01",
                    "period_end": "2025-09-30",
                    "period_type": "quarter",
                    "source": "HKEX_OFFICIAL_DISCLOSURE",
                    "provider": "HKEXnews",
                    "official": True,
                },
                {
                    "metric": "revenue",
                    "value": 200,
                    "unit": "USD",
                    "currency": "USD",
                    "period_start": "2025-04-01",
                    "period_end": "2025-06-30",
                    "period_type": "quarter",
                    "source": "HKEX_OFFICIAL_DISCLOSURE",
                    "provider": "HKEXnews",
                    "official": True,
                },
            ],
        },
    )
    result = official_financials.fetch_official_financials(
        "01810.HK",
        "HK",
        "2026-08-04",
        official_disclosures={
            "provider": "HKEXnews",
            "records": [{
                "url": "https://example.test/result.pdf",
                "filed_at": "2026-05-26T17:25:00",
            }],
        },
        api_fallback={
            "symbol": "01810.HK",
            "financial_currency": "USD",
            "statements": {
                "income_stmt": (
                    ",2025-08-04,2025-08-03\n"
                    "Total Revenue,30,20\n"
                ),
            },
        },
    )

    periods = {(fact["metric"], fact["period_end"]) for fact in result["facts"]}
    assert ("revenue", "2025-08-04") in periods
    assert ("revenue", "2025-08-03") not in periods
    assert ("revenue", "2025-06-30") not in periods
    assert result["financial_window"] == {
        "lookback_days": 365,
        "start_date": "2025-08-04",
        "end_date": "2026-08-04",
        "period_basis": "period_end",
        "filing_basis": "filed_at",
    }


def test_sse_and_szse_use_exchange_specific_official_source(monkeypatch):
    monkeypatch.setattr(
        official_financials,
        "_cninfo_filings",
        lambda ticker, analysis_date: {
            "status": "available",
            "provider": "CNINFO",
            "records": [{
                "filed_at": 1777046400000,
                "title": "Quarterly Report",
                "url": "https://static.cninfo.com.cn/report.pdf",
                "structured_numeric_data": False,
            }],
        },
    )

    sse = official_financials.fetch_official_financials(
        "600519.SH", "CN", "2026-08-04"
    )
    szse = official_financials.fetch_official_financials(
        "000001.SZ", "CN", "2026-08-04"
    )

    assert sse["selected_source"] == "SSE_OFFICIAL_DISCLOSURE"
    assert szse["selected_source"] == "SZSE_OFFICIAL_DISCLOSURE"
    assert sse["facts"] == [] and szse["facts"] == []
    assert sse["numeric_status"] == "unavailable"
    assert szse["numeric_status"] == "unavailable"


def test_official_provider_failure_returns_no_synthetic_fact(monkeypatch):
    monkeypatch.setattr(
        official_financials,
        "_sec_filings",
        lambda ticker, analysis_date, **kwargs: (_ for _ in ()).throw(
            ConnectionError("SEC unavailable")
        ),
    )

    result = official_financials.fetch_official_financials(
        "AAPL", "US", "2026-08-04", sec_user_agent="Example contact@example.com"
    )

    assert result["status"] == "unavailable"
    assert result["numeric_status"] == "unavailable"
    assert result["filings"] == []
    assert result["facts"] == []
    assert result["errors"][0]["stage"] == "official_fetch"


def test_sec_access_without_contact_user_agent_fails_closed(monkeypatch):
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    result = official_financials.fetch_official_financials(
        "AAPL", "US", "2026-08-04"
    )

    assert result["status"] == "unavailable"
    assert result["facts"] == []
    assert "sec_user_agent_missing" in result["degradation"]


def test_validated_contract_keeps_official_fact_period_and_source_metadata():
    official = {
        "schema_version": "1.0",
        "status": "available",
        "numeric_status": "available",
        "facts": [{
            "metric": "revenue",
            "value": 120,
            "unit": "USD",
            "currency": "USD",
            "period_start": "2026-04-01",
            "period_end": "2026-06-30",
            "period_type": "quarter",
            "filed_at": "2026-07-31",
            "source": "SEC_EDGAR_XBRL",
            "provider": "SEC EDGAR",
            "source_url": "https://www.sec.gov/Archives/quarterly.htm",
            "raw_taxonomy": "us-gaap",
            "raw_tag": "Revenues",
            "raw_unit": "USD",
        }],
        "filings": [],
    }
    contract = build_validated_metrics(
        ticker="AAPL",
        market="US",
        analysis_date="2026-08-04",
        snapshot={
            "quote_currency": "USD",
            "financial_currency": "USD",
            "currency_evidence": {},
            "info": {},
            "analyst_tables": {},
        },
        fx={"status": "verified", "rate": 1.0},
        audit_metrics={},
        official_filings={"status": "available", "records": []},
        official_financials=official,
        sankey_data=None,
    )

    metric = next(
        item for item in contract["metrics"]
        if item.get("canonical_metric") == "revenue"
    )
    assert metric["value"] == 120
    assert metric["period_type"] == "quarter"
    assert metric["source_url"].endswith("quarterly.htm")
    assert contract["official_financials"] is official
    assert contract["quality"]["official_numeric_status"] == "available"


def test_validated_contract_marks_free_api_fact_as_fallback():
    official = {
        "schema_version": "1.0",
        "status": "partial",
        "numeric_status": "available",
        "official_numeric_status": "unavailable",
        "facts": [{
            "metric": "revenue",
            "value": 90,
            "unit": "USD",
            "currency": "USD",
            "period_start": "2026-01-01",
            "period_end": "2026-03-31",
            "period_type": "quarter",
            "filed_at": None,
            "source": "YFINANCE_FREE_API",
            "provider": "yfinance",
            "source_url": "https://finance.yahoo.com/quote/AAPL/financials",
            "raw_tag": "Total Revenue",
            "raw_unit": "USD",
            "extraction_method": "yfinance_statement_csv",
            "official": False,
            "fallback_reason": "official_document_metric_missing_or_unparseable",
        }],
        "filings": [],
    }
    contract = build_validated_metrics(
        ticker="AAPL",
        market="US",
        analysis_date="2026-08-04",
        snapshot={
            "quote_currency": "USD",
            "financial_currency": "USD",
            "currency_evidence": {},
            "info": {},
            "analyst_tables": {},
        },
        fx={"status": "verified", "rate": 1.0},
        audit_metrics={},
        official_filings={"status": "partial", "records": []},
        official_financials=official,
        sankey_data=None,
    )

    metric = next(
        item for item in contract["metrics"]
        if item.get("canonical_metric") == "revenue"
    )
    assert metric["official"] is False
    assert metric["status"] == "single_source"
    assert metric["allowed_uses"] == ["financial_statement_fallback", "historical_growth"]
    assert metric["fallback_reason"] == "official_document_metric_missing_or_unparseable"
    assert contract["quality"]["official_numeric_status"] == "unavailable"
