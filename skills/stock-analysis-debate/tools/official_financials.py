"""Fetch and normalize free official financial disclosure data.

The module deliberately separates official filing discovery from numeric facts:
SEC Company Facts can provide structured XBRL values, while HKEX/CNINFO often
only provide links to disclosure documents.  A document link is never treated
as a numeric fact unless a supported structured payload is available.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import math
import os
from typing import Any

from official_filings import (
    _cninfo_filings,
    _hkex_filings,
    _sec_filings,
)


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
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "status": "unavailable",
        "selected_source": None,
        "numeric_source": None,
        "source_priority": [],
        "filings": [],
        "facts": [],
        "numeric_status": "unavailable",
        "numeric_reason": "official_source_unavailable",
        "source_metadata": {},
        "degradation": [],
        "errors": [],
        "fallback_policy": (
            "Only free official sources are configured; missing official facts "
            "remain absent and are not replaced by a commercial provider."
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


def fetch_official_financials(
    ticker: str,
    market: str,
    analysis_date: str,
    *,
    sec_user_agent: str | None = None,
) -> dict[str, Any]:
    """Return a stable official-financials contract for one instrument.

    There is intentionally no commercial-provider fallback in this function.
    The existing provider snapshots remain separate compatibility artifacts and
    cannot overwrite facts returned here.
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
        "role": "official_structured_numeric" if market.upper() == "US" else "official_disclosure",
    }]
    result["selected_source"] = source

    if source == "SEC_EDGAR_XBRL" and not (sec_user_agent or os.environ.get("SEC_USER_AGENT")):
        result["errors"].append({
            "stage": "routing",
            "reason": "SEC_USER_AGENT is required for compliant SEC access",
        })
        result["degradation"].append("sec_user_agent_missing")
        result["numeric_reason"] = "official_source_unavailable"
        return result

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
        return result

    raw = raw if isinstance(raw, dict) else {}
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
        for record in (raw.get("records") or [])
        if isinstance(record, dict)
    ]
    if raw.get("reason"):
        result["errors"].append({
            "stage": "official_fetch",
            "reason": str(raw["reason"]),
        })

    if source == "SEC_EDGAR_XBRL":
        result["facts"] = _normalize_sec_facts(
            raw, result["filings"], analysis_date
        )
        result["numeric_source"] = "SEC_EDGAR_XBRL" if result["facts"] else None
        if result["facts"]:
            result["status"] = "available"
            result["numeric_status"] = "available"
            result["numeric_reason"] = None
        elif result["filings"]:
            result["status"] = "partial"
            result["numeric_reason"] = "no_supported_sec_xbrl_fact_found"
            result["degradation"].append("official_filing_metadata_only")
        else:
            result["numeric_reason"] = "official_filing_records_unavailable"
            result["degradation"].append("official_source_unavailable")
    elif result["filings"]:
        result["status"] = "partial"
        result["numeric_reason"] = "official_disclosure_is_not_structured_xbrl"
        result["degradation"].extend([
            "official_disclosure_document_only",
            "numeric_facts_not_extracted_from_documents",
        ])
    else:
        result["numeric_reason"] = "official_filing_records_unavailable"
        result["degradation"].append("official_source_unavailable")
    return result
