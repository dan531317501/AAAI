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


def test_hkex_document_only_result_does_not_extract_pdf_numbers(monkeypatch):
    monkeypatch.setattr(
        official_financials,
        "_hkex_filings",
        lambda ticker, analysis_date: {
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

    result = official_financials.fetch_official_financials(
        "01810.HK", "HK", "2026-08-04"
    )

    assert result["selected_source"] == "HKEX_OFFICIAL_DISCLOSURE"
    assert result["status"] == "partial"
    assert result["numeric_status"] == "unavailable"
    assert result["facts"] == []
    assert result["filings"][0]["filed_at"] == "2026-05-26"
    assert "numeric_facts_not_extracted_from_documents" in result["degradation"]


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
