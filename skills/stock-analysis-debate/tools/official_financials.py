"""Fetch and normalize free official financial disclosure data.

The module deliberately separates official filing discovery from numeric facts:
SEC Company Facts can provide structured XBRL values, while HKEX/CNINFO often
only provide links to disclosure documents.  A document link is never treated
as a numeric fact unless a supported structured payload is available.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import csv
from io import StringIO
import math
import os
import re
from typing import Any

from official_filings import (
    _cninfo_filings,
    _hkex_filings,
    _sec_filings,
)
from official_document_parser import (
    canonical_metric_for_label,
    parse_official_documents,
)
from temporal_policy import FINANCIAL_LOOKBACK_DAYS, financial_window_start


SCHEMA_VERSION = "1.0"
SEC_FORMS = {"10-K", "10-Q", "20-F", "40-F", "6-K"}

# Only standard taxonomy tags are mapped.  Custom issuer tags are intentionally
# left in the raw SEC payload and do not become canonical facts automatically.
CANONICAL_TAGS: dict[str, tuple[str, ...]] = {
    "revenue": (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "Revenues",
        "Revenue",
    ),
    "cost_of_revenue": ("CostOfRevenue", "CostOfGoodsAndServicesSold"),
    "gross_profit": ("GrossProfit",),
    "operating_income": ("OperatingIncomeLoss", "ProfitLossFromOperatingActivities"),
    "pretax_income": (
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
        "ProfitLossBeforeTax",
    ),
    "income_tax_expense": ("IncomeTaxExpenseBenefit", "IncomeTaxExpenseContinuingOperations"),
    "net_income": ("NetIncomeLoss", "ProfitLoss"),
    "net_income_attributable_to_parent": (
        "NetIncomeLossAttributableToParent",
        "ProfitLossAttributableToOwnersOfParent",
    ),
    "diluted_eps": ("EarningsPerShareDiluted",),
    "basic_eps": ("EarningsPerShareBasic",),
    "cash_and_equivalents": (
        "CashAndCashEquivalentsAtCarryingValue",
        "CashAndDueFromBanks",
        "Cash",
    ),
    "short_term_investments": ("ShortTermInvestments", "MarketableSecuritiesCurrent"),
    "total_assets": ("Assets",),
    "total_liabilities": ("Liabilities",),
    "stockholders_equity": (
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        "Equity",
    ),
    "debt_current": ("DebtCurrent", "LongTermDebtCurrent"),
    "debt_noncurrent": ("LongTermDebtNoncurrent", "LongTermDebt"),
    "operating_cash_flow": ("NetCashProvidedByUsedInOperatingActivities",),
    "capital_expenditure": ("PaymentsToAcquirePropertyPlantAndEquipment",),
}

TAG_TO_METRIC = {
    tag: metric for metric, tags in CANONICAL_TAGS.items() for tag in tags
}


def _empty_result(ticker: str, market: str, analysis_date: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "ticker": ticker,
        "market": market,
        "analysis_date": analysis_date,
        "financial_window": {
            "lookback_days": FINANCIAL_LOOKBACK_DAYS,
            "start_date": financial_window_start(analysis_date).isoformat(),
            "end_date": analysis_date,
            "period_basis": "period_end",
            "filing_basis": "filed_at",
        },
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "status": "unavailable",
        "selected_source": None,
        "numeric_source": None,
        "source_priority": [],
        "filings": [],
        "facts": [],
        "numeric_status": "unavailable",
        "official_numeric_status": "unavailable",
        "numeric_reason": "official_source_unavailable",
        "source_metadata": {},
        "document_parsing": [],
        "api_fallback": {
            "used": False,
            "provider": None,
            "fact_count": 0,
        },
        "degradation": [],
        "errors": [],
        "fallback_policy": (
            "Official structured facts and deterministic PDF/HTML facts have "
            "priority; free API facts only fill missing metric-period keys and "
            "never replace official values."
        ),
    }


def _source_for(ticker: str, market: str) -> tuple[str | None, str | None]:
    upper = ticker.upper()
    normalized_market = market.upper()
    if normalized_market == "US":
        return "SEC_EDGAR_XBRL", "SEC EDGAR"
    if normalized_market == "HK":
        return "HKEX_OFFICIAL_DISCLOSURE", "HKEXnews"
    if normalized_market in {"SSE", "SZSE"}:
        return f"{normalized_market}_OFFICIAL_DISCLOSURE", "CNINFO"
    if normalized_market == "CN":
        code = upper.split(".")[0]
        is_sse = upper.endswith((".SH", ".SS")) or code.startswith(("5", "6", "9"))
        return (
            "SSE_OFFICIAL_DISCLOSURE" if is_sse else "SZSE_OFFICIAL_DISCLOSURE",
            "CNINFO",
        )
    return None, None


def _parse_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        # CNINFO announcementTime is milliseconds since Unix epoch.
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp /= 1000
        try:
            return datetime.fromtimestamp(timestamp, tz=timezone.utc).date()
        except (OverflowError, OSError, ValueError):
            return None
    text = str(value).strip()
    if text.isdigit():
        return _parse_date(int(text))
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return datetime.strptime(text[:10], "%Y-%m-%d").date()
        except ValueError:
            return None


def _date_text(value: Any) -> str | None:
    parsed = _parse_date(value)
    return parsed.isoformat() if parsed else None


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return int(number) if number.is_integer() else number


def _currency_from_unit(unit: str) -> str | None:
    candidate = unit.split("/", 1)[0].strip().upper()
    return candidate if len(candidate) == 3 and candidate.isalpha() else None


def _period_type(row: dict[str, Any]) -> str:
    start = _parse_date(row.get("start"))
    end = _parse_date(row.get("end"))
    if end is None:
        return "unknown"
    if start is None or start == end:
        return "instant"
    duration = (end - start).days + 1
    form = str(row.get("form") or "")
    fiscal_period = str(row.get("fp") or "").upper()
    if fiscal_period == "FY" or duration >= 300 or form in {"10-K", "20-F", "40-F"} and duration >= 300:
        return "annual"
    if 75 <= duration <= 110:
        return "quarter"
    if 150 <= duration <= 210 or 240 <= duration <= 300:
        return "ytd"
    return "unknown"


def _normalize_filing(record: dict[str, Any], source: str, provider: str) -> dict[str, Any]:
    structured = bool(record.get("structured_numeric_data"))
    return {
        "source": source,
        "provider": provider,
        "source_type": record.get("source_type"),
        "source_url": record.get("url"),
        "filed_at": _date_text(record.get("filed_at")),
        "filed_at_raw": record.get("filed_at"),
        "title": record.get("title"),
        "form": record.get("form"),
        "accession_number": record.get("accession_number"),
        "document_type": (
            "structured" if structured else "official_disclosure_document"
        ),
        "structured_numeric_data": structured,
    }


def _filing_url_map(filings: list[dict[str, Any]]) -> dict[str, str]:
    return {
        str(filing["accession_number"]): filing["source_url"]
        for filing in filings
        if filing.get("accession_number") and filing.get("source_url")
    }


def _normalize_sec_facts(
    raw: dict[str, Any],
    filings: list[dict[str, Any]],
    analysis_date: str,
) -> list[dict[str, Any]]:
    payload = raw.get("structured_facts") or {}
    filing_urls = _filing_url_map(filings)
    cutoff = _parse_date(analysis_date)
    window_start = financial_window_start(analysis_date)
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()

    for taxonomy, concepts in (payload.get("facts") or {}).items():
        # Company Facts exposes standard taxonomies; retaining this guard keeps
        # the contract conservative if a provider adds custom namespaces later.
        if taxonomy not in {"us-gaap", "ifrs-full"} or not isinstance(concepts, dict):
            continue
        for tag, concept in concepts.items():
            metric = TAG_TO_METRIC.get(tag)
            if metric is None or not isinstance(concept, dict):
                continue
            for unit, rows in (concept.get("units") or {}).items():
                if not isinstance(rows, list):
                    continue
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    filed = _parse_date(row.get("filed"))
                    if filed is None:
                        continue
                    if cutoff and filed and filed > cutoff:
                        continue
                    form = row.get("form")
                    if form and form not in SEC_FORMS:
                        continue
                    value = _number(row.get("val"))
                    if value is None:
                        continue
                    period_start = _date_text(row.get("start"))
                    period_end = _date_text(row.get("end"))
                    period_end_date = _parse_date(period_end)
                    if period_end_date is None or not (
                        window_start <= period_end_date <= cutoff
                    ):
                        continue
                    accession = row.get("accn")
                    source_url = filing_urls.get(str(accession)) or raw.get(
                        "companyfacts_url"
                    )
                    key = (
                        metric,
                        value,
                        unit,
                        period_start,
                        period_end,
                        filed,
                        accession,
                    )
                    if key in seen:
                        continue
                    seen.add(key)
                    normalized.append({
                        "metric": metric,
                        "value": value,
                        "unit": str(unit),
                        "currency": _currency_from_unit(str(unit)),
                        "basis": None,
                        "period_start": period_start,
                        "period_end": period_end,
                        "period_type": _period_type(row),
                        "filed_at": filed.isoformat() if filed else None,
                        "form": form,
                        "fiscal_year": row.get("fy"),
                        "fiscal_period": row.get("fp"),
                        "frame": row.get("frame"),
                        "accession_number": accession,
                        "source": "SEC_EDGAR_XBRL",
                        "provider": "SEC EDGAR",
                        "source_url": source_url,
                        "raw_taxonomy": taxonomy,
                        "raw_tag": tag,
                        "raw_unit": str(unit),
                        "extraction_method": "sec_companyfacts_xbrl",
                        "official": True,
                    })
    normalized.sort(
        key=lambda fact: (
            fact.get("period_end") or "",
            fact.get("filed_at") or "",
            fact.get("metric") or "",
        ),
        reverse=True,
    )
    return normalized


def _csv_number(value: Any) -> int | float | None:
    if value is None or str(value).strip() in {"", "-", "--", "nan", "NaN", "None"}:
        return None
    return _number(str(value).replace(",", "").replace("(", "-").replace(")", ""))


def _quarter_start(period_end: str) -> str | None:
    parsed = _parse_date(period_end)
    if parsed is None:
        return None
    if parsed.month not in {3, 6, 9, 12}:
        return None
    start_month = parsed.month - 2
    return f"{parsed.year}-{start_month:02d}-01"


def _normalize_api_statement_facts(
    statements: dict[str, str] | None,
    *,
    financial_currency: str | None,
    symbol: str,
    analysis_date: str,
) -> list[dict[str, Any]]:
    """Normalize existing free-provider statement artifacts for per-fact fallback."""
    facts: list[dict[str, Any]] = []
    source_url = f"https://finance.yahoo.com/quote/{symbol}/financials"
    for statement_type, content in (statements or {}).items():
        if not isinstance(content, str) or not content.strip():
            continue
        rows = list(csv.reader(StringIO(content)))
        header_index = next(
            (
                index for index, row in enumerate(rows)
                if len(row) > 1 and any(_parse_date(cell) for cell in row[1:])
            ),
            None,
        )
        if header_index is None:
            continue
        header = rows[header_index]
        periods = [(_parse_date(cell), cell) for cell in header[1:]]
        for row in rows[header_index + 1:]:
            if not row:
                continue
            label = str(row[0]).strip()
            metric = canonical_metric_for_label(label)
            if metric is None:
                continue
            period_type = "instant" if statement_type == "balance_sheet" else "quarter"
            for offset, (period_end, raw_period) in enumerate(periods, start=1):
                if period_end is None or period_end.isoformat() > analysis_date:
                    continue
                if period_end < financial_window_start(analysis_date):
                    continue
                if offset >= len(row):
                    continue
                value = _csv_number(row[offset])
                if value is None:
                    continue
                unit = financial_currency or "provider_native"
                if metric in {"basic_eps", "diluted_eps"}:
                    unit = f"{financial_currency}/share" if financial_currency else "provider_native/share"
                facts.append({
                    "metric": metric,
                    "value": value,
                    "unit": unit,
                    "currency": financial_currency,
                    "period_start": (
                        None if period_type == "instant" else _quarter_start(period_end.isoformat())
                    ),
                    "period_end": period_end.isoformat(),
                    "period_type": period_type,
                    "filed_at": None,
                    "fiscal_year": period_end.year,
                    "fiscal_period": (
                        "FY" if period_type == "instant" else f"Q{((period_end.month - 1) // 3) + 1}"
                    ),
                    "source": "YFINANCE_FREE_API",
                    "provider": "yfinance",
                    "source_url": source_url,
                    "source_page": None,
                    "source_excerpt": f"{statement_type},{label},{raw_period}",
                    "extraction_method": "yfinance_statement_csv",
                    "raw_tag": label,
                    "raw_unit": unit,
                    "official": False,
                    "fallback_reason": "official_document_metric_missing_or_unparseable",
                    "retrieved_at": analysis_date,
                })
    return facts


def _fact_key(fact: dict[str, Any]) -> tuple[Any, ...]:
    return (
        fact.get("metric"),
        fact.get("period_end"),
        fact.get("period_type"),
    )


def _in_financial_window(value: Any, analysis_date: str) -> bool:
    parsed = _parse_date(value)
    if parsed is None:
        return False
    cutoff = _parse_date(analysis_date)
    return financial_window_start(analysis_date) <= parsed <= cutoff


def _filter_facts_to_window(
    facts: list[dict[str, Any]], analysis_date: str
) -> list[dict[str, Any]]:
    return [
        fact for fact in facts
        if isinstance(fact, dict)
        and _in_financial_window(fact.get("period_end"), analysis_date)
    ]


def _merge_official_and_fallback(
    official_facts: list[dict[str, Any]],
    fallback_facts: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """Keep the first official fact for a key and fill only missing keys."""
    merged: list[dict[str, Any]] = []
    keys: set[tuple[Any, ...]] = set()
    for fact in official_facts:
        key = _fact_key(fact)
        if key in keys:
            continue
        keys.add(key)
        merged.append(fact)
    fallback_count = 0
    for fact in fallback_facts:
        key = _fact_key(fact)
        if key in keys:
            continue
        keys.add(key)
        merged.append(fact)
        fallback_count += 1
    merged.sort(
        key=lambda fact: (
            fact.get("period_end") or "",
            fact.get("metric") or "",
            bool(fact.get("official")),
        ),
        reverse=True,
    )
    return merged, fallback_count


def fetch_official_financials(
    ticker: str,
    market: str,
    analysis_date: str,
    *,
    sec_user_agent: str | None = None,
    official_disclosures: dict[str, Any] | None = None,
    api_fallback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return official facts plus per-metric free API supplements.

    Official XBRL or deterministically parsed document facts always win. The
    optional API fallback is intentionally accepted as already-fetched
    statement artifacts so the main workflow does not issue duplicate provider
    requests.
    """
    result = _empty_result(ticker, market, analysis_date)
    source, provider = _source_for(ticker, market)
    if source is None or provider is None:
        result["errors"].append({
            "stage": "routing",
            "reason": f"unsupported_market:{market}",
        })
        result["degradation"].append("unsupported_market")
        return result

    result["source_priority"] = [{
        "priority": 1,
        "source": source,
        "provider": provider,
        "role": "official_structured_numeric" if market.upper() == "US" else "official_document_or_structured",
    }]
    result["selected_source"] = source
    if api_fallback:
        result["source_priority"].append({
            "priority": 2,
            "source": "YFINANCE_FREE_API",
            "provider": "yfinance",
            "role": "free_api_fallback",
        })

    if source == "SEC_EDGAR_XBRL" and not (sec_user_agent or os.environ.get("SEC_USER_AGENT")):
        result["errors"].append({
            "stage": "routing",
            "reason": "SEC_USER_AGENT is required for compliant SEC access",
        })
        result["degradation"].append("sec_user_agent_missing")
        result["numeric_reason"] = "official_source_unavailable"
        return result

    if official_disclosures is not None:
        raw = official_disclosures
    else:
        try:
            if source == "SEC_EDGAR_XBRL":
                raw = _sec_filings(
                    ticker,
                    analysis_date,
                    sec_user_agent=sec_user_agent,
                )
            elif source == "HKEX_OFFICIAL_DISCLOSURE":
                raw = _hkex_filings(ticker, analysis_date)
            else:
                raw = _cninfo_filings(ticker, analysis_date)
        except Exception as error:  # provider failures are explicit and fail closed
            result["errors"].append({
                "stage": "official_fetch",
                "reason": f"{type(error).__name__}: {error}",
            })
            result["degradation"].append("official_source_unavailable")
            raw = {}

    raw = raw if isinstance(raw, dict) else {}
    recent_records = [
        record for record in (raw.get("records") or [])
        if isinstance(record, dict)
        and _in_financial_window(record.get("filed_at"), analysis_date)
    ]
    result["source_metadata"] = {
        key: raw[key]
        for key in (
            "cik", "stock_code", "organization_id", "stock_id",
            "search_url", "submissions_url", "companyfacts_url",
            "xbrl_namespaces",
        )
        if raw.get(key) is not None
    }
    result["filings"] = [
        _normalize_filing(record, source, provider)
        for record in recent_records
    ]
    if raw.get("reason"):
        result["errors"].append({
            "stage": "official_fetch",
            "reason": str(raw["reason"]),
        })

    official_facts: list[dict[str, Any]] = []
    if source == "SEC_EDGAR_XBRL":
        official_facts = _normalize_sec_facts(
            raw, result["filings"], analysis_date
        )

    document_records = [
        {**record, "source": source, "provider": provider}
        for record in recent_records
        if not record.get("structured_numeric_data")
    ]
    if document_records:
        document_result = parse_official_documents(
            document_records,
            analysis_date,
            (api_fallback or {}).get("financial_currency"),
            provider=provider,
        )
        result["document_parsing"] = document_result["documents"]
        official_facts.extend(document_result["facts"])
        if not document_result["facts"]:
            result["degradation"].append("official_document_parse_failed")
    elif source != "SEC_EDGAR_XBRL" and result["filings"]:
        result["degradation"].append("official_document_records_unavailable")

    official_facts = _filter_facts_to_window(official_facts, analysis_date)
    fallback_facts = _normalize_api_statement_facts(
        (api_fallback or {}).get("statements"),
        financial_currency=(api_fallback or {}).get("financial_currency"),
        symbol=(api_fallback or {}).get("symbol") or ticker,
        analysis_date=analysis_date,
    )
    fallback_facts = _filter_facts_to_window(fallback_facts, analysis_date)
    result["facts"], fallback_count = _merge_official_and_fallback(
        official_facts,
        fallback_facts,
    )
    official_count = sum(1 for fact in result["facts"] if fact.get("official"))
    result["official_numeric_status"] = "available" if official_count else "unavailable"
    result["api_fallback"] = {
        "used": fallback_count > 0,
        "provider": "yfinance" if fallback_count > 0 else None,
        "fact_count": fallback_count,
        "attempted_fact_count": len(fallback_facts),
    }
    if fallback_count:
        result["degradation"].append("api_fallback_used")
    result["numeric_status"] = "available" if result["facts"] else "unavailable"
    if official_count:
        result["numeric_source"] = source
        result["status"] = "available"
        result["numeric_reason"] = None
    elif fallback_count:
        result["numeric_source"] = "YFINANCE_FREE_API"
        result["status"] = "partial"
        result["numeric_reason"] = "official_document_facts_unavailable_api_fallback_used"
    elif result["filings"]:
        result["status"] = "partial"
        result["numeric_reason"] = (
            "no_supported_sec_xbrl_fact_found"
            if source == "SEC_EDGAR_XBRL"
            else "official_document_facts_unavailable"
        )
        result["degradation"].append("official_filing_metadata_only")
    else:
        result["numeric_reason"] = "official_filing_records_unavailable"
        result["degradation"].append("official_source_unavailable")
    return result
