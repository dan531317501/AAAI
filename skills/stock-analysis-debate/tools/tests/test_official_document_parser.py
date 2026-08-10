import official_document_parser


def _html_payload():
    return b"""
    <html><body>
      <div>in USD'000</div>
      <div>Year ended December 31,</div>
      <div>2025 2024 2025 as compared with 2024 (%)</div>
      <div>2023</div>
      <div>Revenue 9,326,799 8,029,921 16.2 6,321,560</div>
      <div>Profit for the year attributable to owners of the Company
           685,131 492,748 39.0 902,526</div>
      <div>Net cash generated from operating activities
           3,194,303 3,175,555 0.6 3,358,294</div>
      <div>Diluted earnings per share $0.09 $0.06 50.0 $0.11</div>
    </body></html>
    """


def test_html_document_extracts_periods_units_and_source_provenance():
    result = official_document_parser.parse_document_payload(
        _html_payload(),
        "text/html",
        {
            "url": "https://example.test/smic-results.html",
            "filed_at": "2026-03-26T18:43:00",
            "source": "HKEX_OFFICIAL_DISCLOSURE",
            "provider": "HKEXnews",
        },
        "2026-08-07",
        "USD",
    )

    assert result["status"] == "available"
    revenue = next(item for item in result["facts"] if item["metric"] == "revenue")
    assert revenue["value"] == 9326799000
    assert revenue["currency"] == "USD"
    assert revenue["period_end"] == "2025-12-31"
    assert revenue["period_type"] == "annual"
    assert revenue["official"] is True
    assert revenue["source_page"] == 1
    assert revenue["source_url"].endswith("smic-results.html")
    assert revenue["extraction_method"] == "html_text_regex"

    operating_cash_flow = next(
        item for item in result["facts"] if item["metric"] == "operating_cash_flow"
    )
    assert operating_cash_flow["value"] == 3194303000

    eps = next(item for item in result["facts"] if item["metric"] == "diluted_eps")
    assert eps["value"] == 0.09
    assert eps["unit"] == "USD/share"


def test_document_without_text_is_rejected_for_api_degradation():
    try:
        official_document_parser.parse_document_payload(
            b"%PDF-1.7\n",
            "application/pdf",
            {"url": "https://example.test/scanned.pdf"},
            "2026-08-07",
            "USD",
        )
    except Exception as error:
        assert "could not be parsed" in str(error) or "text layer" in str(error)
    else:
        raise AssertionError("a PDF without a usable text layer must fail closed")


def test_q1_pdf_style_rows_keep_units_periods_and_attribution():
    result = official_document_parser._parse_text_pages(
        [{
            "page_number": 4,
            "text": """
            Summary of First Quarter 2026 Operating Results
            Amounts in US$ thousands, except for earnings per share
            1Q26 4Q25 QoQ 1Q25 YoY
            Revenue 2,505,487 2,488,710 0.7% 2,247,201 11.5%
            Profit for the period 230,912 203,375 13.5% 323,422 -28.6%
            Other operating income 58,800 213,768
            Profit for the period attributable to:
            Owners of the Company 197,448 172,851 14.2% 188,035 5.0%
            Earnings per share(1)
            Basic $0.02 $0.02 $0.02
            Diluted $0.02 $0.02 $0.02
            The Company's capital expenditure in 2025 was $8.1 billion.
            Capital expenditure was $1,562.8 million in 1Q26, compared to $2,407.5 million in 4Q25.
            """,
        }],
        analysis_date="2026-08-07",
        financial_currency="USD",
        source="HKEX_OFFICIAL_DISCLOSURE",
        provider="HKEXnews",
        source_url="https://example.test/q1.pdf",
        extraction_method="pdf_text_regex",
    )

    q1 = [item for item in result if item["period_end"] == "2026-03-31"]
    revenue = next(item for item in q1 if item["metric"] == "revenue")
    attributable = next(
        item for item in q1 if item["metric"] == "net_income_attributable_to_parent"
    )
    net_income = next(item for item in q1 if item["metric"] == "net_income")
    eps = next(item for item in q1 if item["metric"] == "diluted_eps")
    capex = next(item for item in q1 if item["metric"] == "capital_expenditure")

    assert revenue["value"] == 2505487000
    assert attributable["value"] == 197448000
    assert net_income["value"] == 230912000
    assert eps["value"] == 0.02
    assert capex["value"] == 1562800000
    assert not any(item["metric"] == "operating_income" for item in q1)
    assert all(
        item["raw_unit"] == "USD thousand"
        for item in q1
        if item["metric"] not in {"capital_expenditure", "diluted_eps", "basic_eps"}
    )
    assert eps["raw_unit"] == "USD/share"
    assert capex["raw_unit"] == "USD million"


def test_balance_sheet_date_headers_produce_instant_periods():
    result = official_document_parser._parse_text_pages(
        [{
            "page_number": 10,
            "text": """
            CONDENSED CONSOLIDATED STATEMENT OF FINANCIAL POSITION
            (In US$ thousands)
            As of
            March 31, 2026 December 31, 2025
            TOTAL ASSETS 54,973,904 52,271,308
            """,
        }],
        analysis_date="2026-08-07",
        financial_currency="USD",
        source="HKEX_OFFICIAL_DISCLOSURE",
        provider="HKEXnews",
        source_url="https://example.test/q1.pdf",
        extraction_method="pdf_text_regex",
    )

    current = next(item for item in result if item["period_end"] == "2026-03-31")
    assert current["metric"] == "total_assets"
    assert current["value"] == 54973904000
    assert current["period_type"] == "instant"
    assert current["period_start"] is None


def test_parse_official_documents_keeps_document_error_audit(monkeypatch):
    def fake_download(record, provider):
        if record["url"].endswith("bad.pdf"):
            raise ValueError("unreadable")
        return _html_payload(), "text/html"

    result = official_document_parser.parse_official_documents(
        [
            {"url": "https://example.test/good.html", "title": "Results"},
            {"url": "https://example.test/bad.pdf", "title": "Annual report"},
        ],
        "2026-08-07",
        "USD",
        downloader=fake_download,
        provider="HKEXnews",
    )

    assert len(result["facts"]) >= 3
    assert [item["status"] for item in result["documents"]] == ["available", "unavailable"]
    assert "unreadable" in result["documents"][1]["error"]


def test_parse_official_documents_prefers_precise_statement_over_summary(monkeypatch):
    payloads = {
        "https://example.test/summary.html": b"""
        <div>Official results summary for the three months ended March 31, 2026.</div>
        <div>1Q26 4Q25</div>
        <div>Revenue $2,505.5 million $2,488.7 million</div>
        """,
        "https://example.test/detail.html": b"""
        <div>Official condensed consolidated statement of profit or loss and other comprehensive income.</div>
        <div>Amounts in US$ thousands</div>
        <div>1Q26 4Q25</div>
        <div>Revenue 2,505,487 2,488,710</div>
        """,
    }

    def fake_download(record, provider):
        return payloads[record["url"]], "text/html"

    result = official_document_parser.parse_official_documents(
        [
            {"url": "https://example.test/summary.html", "title": "Summary"},
            {"url": "https://example.test/detail.html", "title": "Detail"},
        ],
        "2026-08-07",
        "USD",
        downloader=fake_download,
        provider="HKEXnews",
    )

    revenue = next(
        item for item in result["facts"]
        if item["metric"] == "revenue" and item["period_end"] == "2026-03-31"
    )
    assert revenue["value"] == 2505487000
    assert revenue["raw_unit"] == "USD thousand"
    assert revenue["source_url"].endswith("detail.html")
