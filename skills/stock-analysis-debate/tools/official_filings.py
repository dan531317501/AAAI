"""Discover official filings without asking an LLM to extract numeric facts."""

from __future__ import annotations

from datetime import datetime, timezone
from html import unescape
import os
import re
from typing import Any
from urllib.parse import urljoin

import requests

from provider_runtime import request_json, retry_call
from temporal_policy import financial_window_start


HEADERS = {
    "User-Agent": "Mozilla/5.0 stock-analysis-debate/1.0",
    "Accept": "application/json,text/html,application/xhtml+xml",
}
SEC_HEADERS = {
    **HEADERS,
    "User-Agent": os.environ.get(
        "SEC_USER_AGENT",
        "stock-analysis-debate/1.0 contact-not-configured",
    ),
}


def _result(status: str, provider: str, records: list[dict[str, Any]], **extra: Any) -> dict:
    return {
        "status": status,
        "provider": provider,
        "records": records,
        "numeric_ingestion": "structured_only",
        "llm_extraction_allowed": False,
        **extra,
    }


def _hkex_filings(ticker: str, analysis_date: str) -> dict:
    code = ticker.split(".")[0].zfill(5)
    stocks = request_json(
        "GET",
        "https://www1.hkexnews.hk/ncms/script/eds/activestock_sehk_e.json",
        provider="HKEXnews",
        operation="active_stock_list",
        headers=HEADERS,
        timeout=20,
        validator=lambda value: isinstance(value, list) and bool(value),
    )
    stock = next((item for item in stocks if str(item.get("c")) == code), None)
    if stock is None:
        return _result("unavailable", "HKEXnews", [], reason="stock code not found")

    url = (
        "https://www1.hkexnews.hk/search/titlesearch.xhtml"
        f"?category=0&lang=EN&market=SEHK&stockId={stock['i']}"
    )

    def fetch_html() -> str:
        response = requests.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        return response.text

    html = retry_call(
        fetch_html,
        provider="HKEXnews",
        operation="title_search",
        validator=lambda value: "titleSearchResultPanel" in value,
    )
    link_pattern = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
    cutoff = datetime.strptime(analysis_date, "%Y-%m-%d")
    window_start = financial_window_start(analysis_date)
    records = []
    rows = re.findall(r"<tr\b[^>]*>(.*?)</tr>", html, flags=re.IGNORECASE | re.DOTALL)
    for row_html in rows:
        released_match = re.search(
            r"(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2})",
            row_html,
        )
        if released_match is None:
            continue
        date_text, time_text = released_match.groups()
        released = datetime.strptime(f"{date_text} {time_text}", "%d/%m/%Y %H:%M")
        if not (window_start <= released.date() <= cutoff.date()):
            continue
        links = link_pattern.findall(row_html)
        if not links:
            continue
        headline_match = re.search(
            r'<(?:td|div)\b[^>]*class="[^"]*\bheadline\b[^"]*"[^>]*>'
            r'(.*?)</(?:td|div)>',
            row_html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        headline = ""
        if headline_match:
            headline = re.sub(
                r"\s+",
                " ",
                unescape(re.sub(r"<[^>]+>", " ", headline_match.group(1))),
            ).strip()
        for href, title_html in links:
            link_title = re.sub(
                r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", title_html))
            ).strip()
            title = headline or link_title
            lower = f"{headline} {link_title}".casefold()
            if not any(term in lower for term in (
                "results announcement", "annual results", "interim results",
                "quarterly results", "annual report", "interim report",
            )):
                continue
            records.append({
                "filed_at": released.isoformat(),
                "title": title,
                "url": urljoin("https://www1.hkexnews.hk", href),
                "source_type": "official_exchange_filing",
                "structured_numeric_data": False,
            })
    return _result(
        "available" if records else "partial",
        "HKEXnews",
        records[:12],
        stock_id=stock["i"],
        stock_code=code,
        search_url=url,
    )


def _sec_filings(
    ticker: str,
    analysis_date: str,
    sec_user_agent: str | None = None,
) -> dict:
    symbol = ticker.upper().replace(".", "-")
    sec_headers = {
        **SEC_HEADERS,
        "User-Agent": sec_user_agent or os.environ.get(
            "SEC_USER_AGENT", SEC_HEADERS["User-Agent"]
        ),
    }
    tickers = request_json(
        "GET",
        "https://www.sec.gov/files/company_tickers.json",
        provider="SEC EDGAR",
        operation="ticker_map",
        headers=sec_headers,
        timeout=20,
        validator=lambda value: isinstance(value, dict) and bool(value),
    )
    match = next(
        (
            value for value in tickers.values()
            if str(value.get("ticker", "")).upper() == symbol
        ),
        None,
    )
    if match is None:
        return _result("unavailable", "SEC EDGAR", [], reason="CIK not found")
    cik = str(match["cik_str"]).zfill(10)
    submissions_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    facts_url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    submissions = request_json(
        "GET", submissions_url, provider="SEC EDGAR",
        operation="submissions", headers=sec_headers, timeout=20,
        validator=lambda value: isinstance(value, dict) and "filings" in value,
    )
    facts = request_json(
        "GET", facts_url, provider="SEC EDGAR",
        operation="companyfacts", headers=sec_headers, timeout=30,
        validator=lambda value: isinstance(value, dict) and "facts" in value,
    )
    facts = _filter_companyfacts_as_of(facts, analysis_date)
    recent = submissions.get("filings", {}).get("recent", {})
    records = []
    cutoff = datetime.strptime(analysis_date, "%Y-%m-%d").date()
    window_start = financial_window_start(analysis_date)
    forms = recent.get("form", [])
    for index, form in enumerate(forms):
        if form not in ("10-K", "10-Q", "20-F", "40-F", "6-K"):
            continue
        filing_date = recent.get("filingDate", [])[index]
        filing_day = datetime.strptime(filing_date, "%Y-%m-%d").date()
        if not (window_start <= filing_day <= cutoff):
            continue
        accession = recent.get("accessionNumber", [])[index]
        primary = recent.get("primaryDocument", [])[index]
        accession_path = accession.replace("-", "")
        cik_plain = str(int(cik))
        records.append({
            "filed_at": filing_date,
            "form": form,
            "accession_number": accession,
            "url": f"https://www.sec.gov/Archives/edgar/data/{cik_plain}/{accession_path}/{primary}",
            "source_type": "official_exchange_filing",
            "structured_numeric_data": True,
        })
        if len(records) >= 12:
            break
    namespaces = sorted(facts.get("facts", {}).keys())
    return _result(
        "available" if records else "partial",
        "SEC EDGAR",
        records,
        cik=cik,
        submissions_url=submissions_url,
        companyfacts_url=facts_url,
        xbrl_namespaces=namespaces,
        structured_facts=facts,
    )


def _filter_companyfacts_as_of(facts: dict, analysis_date: str) -> dict:
    """Keep SEC facts filed and reported inside the rolling financial window."""
    cutoff = datetime.strptime(analysis_date, "%Y-%m-%d").date()
    window_start = financial_window_start(analysis_date)
    filtered = {key: value for key, value in facts.items() if key != "facts"}
    filtered_taxonomies = {}
    for taxonomy_name, concepts in facts.get("facts", {}).items():
        filtered_concepts = {}
        for concept_name, concept in concepts.items():
            filtered_units = {}
            for unit, rows in concept.get("units", {}).items():
                allowed_rows = []
                for row in rows:
                    try:
                        filed = datetime.strptime(str(row.get("filed")), "%Y-%m-%d").date()
                    except (TypeError, ValueError):
                        continue
                    if filed > cutoff:
                        continue
                    try:
                        period_end = datetime.strptime(
                            str(row.get("end")), "%Y-%m-%d"
                        ).date()
                    except (TypeError, ValueError):
                        continue
                    if window_start <= period_end <= cutoff:
                        allowed_rows.append(row)
                if allowed_rows:
                    filtered_units[unit] = allowed_rows
            if filtered_units:
                filtered_concepts[concept_name] = {
                    **{key: value for key, value in concept.items() if key != "units"},
                    "units": filtered_units,
                }
        if filtered_concepts:
            filtered_taxonomies[taxonomy_name] = filtered_concepts
    filtered["facts"] = filtered_taxonomies
    return filtered


def _cninfo_filings(ticker: str, analysis_date: str) -> dict:
    code = ticker.split(".")[0]
    upper = ticker.upper()
    is_shanghai = upper.endswith((".SH", ".SS")) or code.startswith(("5", "6", "9"))
    if upper.endswith(".BJ") or code.startswith(("4", "8")):
        return _result(
            "unavailable", "CNINFO", [],
            reason="Beijing Stock Exchange orgId mapping is not supported",
        )
    org_id = ("gssh" if is_shanghai else "gssz") + code.zfill(7)
    cutoff = datetime.strptime(analysis_date, "%Y-%m-%d")
    begin = financial_window_start(analysis_date).strftime("%Y-%m-%d")
    market = "sse" if is_shanghai else "szse"
    payload = request_json(
        "POST",
        "https://www.cninfo.com.cn/new/hisAnnouncement/query",
        provider="CNINFO",
        operation="announcement_query",
        data={
            "pageNum": 1,
            "pageSize": 30,
            "column": market,
            "tabName": "fulltext",
            "stock": f"{code},{org_id}",
            "category": "category_ndbg_szsh;category_bndbg_szsh;category_yjdbg_szsh;category_sjdbg_szsh",
            "seDate": f"{begin}~{analysis_date}",
            "searchkey": "",
            "secid": "",
            "sortName": "",
            "sortType": "",
            "isHLtitle": "true",
        },
        headers={
            **HEADERS,
            "Referer": "https://www.cninfo.com.cn/",
            "X-Requested-With": "XMLHttpRequest",
        },
        timeout=20,
        validator=lambda value: isinstance(value, dict),
    )
    records = []
    cutoff_date = cutoff.date()
    for item in payload.get("announcements", []) or []:
        announcement_time = item.get("announcementTime")
        try:
            timestamp = float(announcement_time)
            if timestamp > 10_000_000_000:
                timestamp /= 1000
            announcement_date = datetime.fromtimestamp(
                timestamp, tz=timezone.utc
            ).date()
        except (TypeError, ValueError, OverflowError, OSError):
            continue
        if not (financial_window_start(analysis_date) <= announcement_date <= cutoff_date):
            continue
        adjunct = item.get("adjunctUrl")
        records.append({
            "filed_at": item.get("announcementTime"),
            "title": re.sub(r"<[^>]+>", "", item.get("announcementTitle", "")),
            "url": urljoin("https://static.cninfo.com.cn/", adjunct or ""),
            "source_type": "official_designated_disclosure",
            "structured_numeric_data": False,
        })
    return _result(
        "available" if records else "partial",
        "CNINFO",
        records,
        organization_id=org_id,
        stock_code=code,
    )


def fetch_official_filings(ticker: str, market: str, analysis_date: str) -> dict:
    """Fetch official filing evidence; provider errors degrade to unavailable."""
    try:
        if market == "HK":
            return _hkex_filings(ticker, analysis_date)
        if market == "CN":
            return _cninfo_filings(ticker, analysis_date)
        if not os.environ.get("SEC_USER_AGENT"):
            return _result(
                "unavailable",
                "SEC EDGAR",
                [],
                reason=(
                    "SEC_USER_AGENT is required for compliant automated SEC access; "
                    "set it to an organization and real contact email"
                ),
            )
        return _sec_filings(ticker, analysis_date)
    except Exception as error:
        return _result(
            "unavailable",
            {"HK": "HKEXnews", "CN": "CNINFO"}.get(market, "SEC EDGAR"),
            [],
            reason=f"{type(error).__name__}: {error}",
        )
