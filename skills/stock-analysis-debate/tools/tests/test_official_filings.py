import official_filings


def test_hkex_filing_discovery_resolves_stock_id_and_keeps_results_only(monkeypatch):
    monkeypatch.setattr(
        official_filings,
        "request_json",
        lambda *args, **kwargs: [
            {"i": 190371, "c": "01810", "n": "XIAOMI-W", "s": 17455}
        ],
    )
    html = """
    <div id="titleSearchResultPanel">
      <tr><td class="text-right release-time">26/05/2026 17:25</td>
      <td class="stock-short-name">XIAOMI-W</td>
      <td class="headline"><a href="/listedco/result.pdf">RESULTS ANNOUNCEMENT FOR Q1</a></td></tr>
      <tr><td class="text-right release-time">27/05/2026 18:00</td>
      <td class="stock-short-name">XIAOMI-W</td>
      <td class="headline"><a href="/listedco/buyback.pdf">Next Day Disclosure Return</a></td></tr>
      <tr><td class="text-right release-time">26/05/2025 17:25</td>
      <td class="stock-short-name">XIAOMI-W</td>
      <td class="headline"><a href="/listedco/old-results.pdf">ANNUAL RESULTS</a></td></tr>
    </div>
    """
    monkeypatch.setattr(
        official_filings,
        "retry_call",
        lambda func, **kwargs: html,
    )

    result = official_filings._hkex_filings("01810.HK", "2026-08-04")

    assert result["status"] == "available"
    assert result["stock_id"] == 190371
    assert len(result["records"]) == 1
    assert result["records"][0]["url"] == "https://www1.hkexnews.hk/listedco/result.pdf"
    assert result["records"][0]["structured_numeric_data"] is False
    assert result["llm_extraction_allowed"] is False


def test_hkex_filing_discovery_matches_results_in_headline_field(monkeypatch):
    monkeypatch.setattr(
        official_filings,
        "request_json",
        lambda *args, **kwargs: [{"i": 7249, "c": "00981", "n": "SMIC"}],
    )
    html = """
    <div id="titleSearchResultPanel">
      <tr>
        <td class="release-time">14/05/2026 18:17</td>
        <td class="headline">
          Announcements and Notices - [Quarterly Results]<br/>
          SMIC REPORTS UNAUDITED RESULTS FOR THE THREE MONTHS ENDED MARCH 31, 2026
        </td>
        <td class="doc-link">
          <a href="/listedco/q1-2026.pdf">An announcement has just been published</a>
        </td>
      </tr>
    </div>
    """
    monkeypatch.setattr(
        official_filings,
        "retry_call",
        lambda func, **kwargs: html,
    )

    result = official_filings._hkex_filings("00981.HK", "2026-08-07")

    assert result["status"] == "available"
    assert len(result["records"]) == 1
    assert "Quarterly Results" in result["records"][0]["title"]
    assert result["records"][0]["url"].endswith("q1-2026.pdf")


def test_official_filing_failure_degrades_without_fabricating_records(monkeypatch):
    monkeypatch.setattr(
        official_filings,
        "_hkex_filings",
        lambda *args: (_ for _ in ()).throw(ConnectionError("down")),
    )

    result = official_filings.fetch_official_filings(
        "01810.HK", "HK", "2026-08-04"
    )

    assert result["status"] == "unavailable"
    assert result["records"] == []
    assert result["numeric_ingestion"] == "structured_only"


def test_cninfo_derives_exchange_org_id_and_returns_periodic_reports(monkeypatch):
    captured = {}

    def fake_request(method, url, **kwargs):
        captured.update(kwargs)
        return {
            "announcements": [
                {
                    "announcementTime": 1777046400000,
                    "announcementTitle": "贵州茅台2026年第一季度报告",
                    "adjunctUrl": "finalpage/2026-04-25/report.PDF",
                }
            ]
        }

    monkeypatch.setattr(official_filings, "request_json", fake_request)

    result = official_filings._cninfo_filings("600519.SH", "2026-08-04")

    assert result["organization_id"] == "gssh0600519"
    assert captured["data"]["stock"] == "600519,gssh0600519"
    assert captured["data"]["column"] == "sse"
    assert captured["data"]["seDate"] == "2025-08-04~2026-08-04"
    assert result["records"][0]["url"].endswith(
        "finalpage/2026-04-25/report.PDF"
    )


def test_sec_adapter_resolves_cik_and_preserves_structured_companyfacts(monkeypatch):
    def fake_request(method, url, **kwargs):
        if url.endswith("company_tickers.json"):
            return {"0": {"ticker": "AAPL", "cik_str": 320193}}
        if "/submissions/" in url:
            return {
                "filings": {
                    "recent": {
                        "form": ["10-Q", "8-K"],
                        "filingDate": ["2026-07-31", "2026-07-30"],
                        "accessionNumber": ["0000320193-26-000001", "x"],
                        "primaryDocument": ["aapl-20260630.htm", "x.htm"],
                    }
                }
            }
        return {
            "facts": {
                "us-gaap": {
                    "RevenueFromContractWithCustomerExcludingAssessedTax": {
                        "label": "Revenue",
                            "units": {
                                "USD": [
                                {"filed": "2026-07-31", "end": "2026-06-30", "val": 10},
                                {"filed": "2026-08-05", "end": "2026-06-30", "val": 20},
                            ]
                        },
                    }
                }
            }
        }

    monkeypatch.setattr(official_filings, "request_json", fake_request)

    result = official_filings._sec_filings("AAPL", "2026-08-04")

    assert result["status"] == "available"
    assert result["cik"] == "0000320193"
    assert result["xbrl_namespaces"] == ["us-gaap"]
    assert result["records"][0]["structured_numeric_data"] is True
    assert result["structured_facts"]["facts"]["us-gaap"]
    rows = result["structured_facts"]["facts"]["us-gaap"][
        "RevenueFromContractWithCustomerExcludingAssessedTax"
    ]["units"]["USD"]
    assert [row["filed"] for row in rows] == ["2026-07-31"]


def test_companyfacts_day_before_filing_hides_the_fact():
    facts = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [{"filed": "2026-07-31", "val": 10}]
                    }
                }
            }
        }
    }

    filtered = official_filings._filter_companyfacts_as_of(facts, "2026-07-30")

    assert filtered["facts"] == {}


def test_companyfacts_excludes_periods_older_than_one_year():
    facts = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {"filed": "2026-07-31", "end": "2025-08-04", "val": 1},
                            {"filed": "2026-07-31", "end": "2025-08-03", "val": 2},
                        ]
                    }
                }
            }
        }
    }

    filtered = official_filings._filter_companyfacts_as_of(facts, "2026-08-04")

    rows = filtered["facts"]["us-gaap"]["Revenues"]["units"]["USD"]
    assert [row["val"] for row in rows] == [1]
