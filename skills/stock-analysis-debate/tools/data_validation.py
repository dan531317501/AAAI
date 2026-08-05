"""Build the only numeric contract that downstream LLM agents may consume."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
from typing import Any

import pandas as pd
import yfinance as yf

from provider_runtime import retry_call


VALID_STATUSES = {
    "verified", "single_source", "partial", "conflict", "stale",
    "unavailable", "translated_only",
}


def _finite(value: Any) -> float | int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return int(number) if number.is_integer() else number


def _frame_records(frame: pd.DataFrame | None) -> list[dict[str, Any]]:
    if frame is None or frame.empty:
        return []
    records = []
    for period, row in frame.iterrows():
        record: dict[str, Any] = {"period": str(period)}
        for column, value in row.items():
            numeric = _finite(value)
            record[str(column)] = numeric if numeric is not None else (
                None if pd.isna(value) else str(value)
            )
        records.append(record)
    return records


def fetch_provider_snapshot(symbol: str, analysis_date: str) -> dict[str, Any]:
    """Fetch currencies and dedicated analyst tables from explicit API fields."""
    stock = yf.Ticker(symbol)
    try:
        info = retry_call(
            lambda: stock.info or {}, provider="yfinance",
            operation=f"{symbol}.validation_info",
            validator=lambda value: isinstance(value, dict) and bool(value),
        )
    except Exception:
        info = {}
    try:
        history_metadata = retry_call(
            lambda: stock.history_metadata or {}, provider="yfinance",
            operation=f"{symbol}.history_metadata",
            validator=lambda value: isinstance(value, dict) and bool(value),
        )
    except Exception:
        history_metadata = {}

    frames: dict[str, pd.DataFrame | None] = {}
    for key, method in (
        ("earnings_estimate", "get_earnings_estimate"),
        ("revenue_estimate", "get_revenue_estimate"),
        ("eps_trend", "get_eps_trend"),
        ("eps_revisions", "get_eps_revisions"),
        ("growth_estimates", "get_growth_estimates"),
    ):
        try:
            frames[key] = retry_call(
                lambda name=method: getattr(stock, name)(),
                provider="yfinance", operation=f"{symbol}.{method}",
            )
        except Exception:
            frames[key] = None

    estimate_currencies = sorted({
        str(record["currency"])
        for key in ("earnings_estimate", "revenue_estimate", "eps_trend", "eps_revisions")
        for record in _frame_records(frames[key])
        if record.get("currency")
    })
    quote_currency = info.get("currency") or history_metadata.get("currency")
    financial_currency = info.get("financialCurrency") or (
        estimate_currencies[0] if len(estimate_currencies) == 1 else None
    )
    return {
        "symbol": symbol,
        "analysis_date": analysis_date,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "quote_currency": quote_currency,
        "financial_currency": financial_currency,
        "currency_evidence": {
            "info.currency": info.get("currency"),
            "info.financialCurrency": info.get("financialCurrency"),
            "history_metadata.currency": history_metadata.get("currency"),
            "estimate_currencies": estimate_currencies,
        },
        "info": info,
        "analyst_tables": {
            key: _frame_records(frame) for key, frame in frames.items()
        },
    }


def fetch_fx_rate(
    from_currency: str | None,
    to_currency: str | None,
    analysis_date: str,
) -> dict[str, Any]:
    """Fetch a dated FX rate, attempting direct then inverse Yahoo pairs."""
    if not from_currency or not to_currency:
        return {"status": "unavailable", "reason": "currency metadata missing"}
    source = from_currency.upper()
    target = to_currency.upper()
    if source == target:
        return {
            "status": "verified", "from_currency": source,
            "to_currency": target, "rate": 1.0,
            "rate_date": analysis_date, "provider": "identity",
        }

    end = pd.Timestamp(analysis_date) + pd.Timedelta(days=1)
    start = end - pd.Timedelta(days=14)
    attempts = [
        (f"{source}{target}=X", False),
        (f"{target}{source}=X", True),
    ]
    for pair, inverse in attempts:
        try:
            history = retry_call(
                lambda p=pair: yf.Ticker(p).history(
                    start=start.strftime("%Y-%m-%d"),
                    end=end.strftime("%Y-%m-%d"),
                ),
                provider="yfinance", operation=f"fx.{pair}",
            )
        except Exception:
            continue
        if history is None or history.empty or "Close" not in history:
            continue
        closes = history["Close"].dropna()
        if closes.empty:
            continue
        raw_rate = _finite(closes.iloc[-1])
        if raw_rate is None or raw_rate <= 0:
            continue
        rate = 1.0 / raw_rate if inverse else float(raw_rate)
        index_value = pd.Timestamp(closes.index[-1])
        if index_value.tz is not None:
            index_value = index_value.tz_localize(None)
        age = (pd.Timestamp(analysis_date) - index_value.normalize()).days
        return {
            "status": "verified" if age <= 7 else "stale",
            "from_currency": source,
            "to_currency": target,
            "rate": rate,
            "rate_date": index_value.strftime("%Y-%m-%d"),
            "provider": "yfinance",
            "provider_symbol": pair,
            "inverted": inverse,
            "age_calendar_days": age,
        }
    return {
        "status": "unavailable", "from_currency": source,
        "to_currency": target, "reason": "no valid direct or inverse FX pair",
    }


def _metric(
    metric_id: str,
    value: Any,
    *,
    unit: str,
    currency: str | None,
    period: str | None,
    provider: str,
    source_field: str,
    status: str = "single_source",
    allowed_uses: list[str] | None = None,
    quality_flags: list[str] | None = None,
) -> dict[str, Any]:
    if status not in VALID_STATUSES:
        raise ValueError(f"invalid metric status: {status}")
    number = _finite(value)
    if number is None:
        status = "unavailable"
    if status == "unavailable":
        number = None
    return {
        "metric_id": metric_id,
        "value": number,
        "unit": unit,
        "currency": currency,
        "period": period,
        "provider": provider,
        "source_field": source_field,
        "status": status,
        "quality_flags": quality_flags or [],
        "allowed_uses": allowed_uses or [],
    }


def _sec_official_metrics(
    structured_facts: dict[str, Any] | None,
    analysis_date: str,
) -> list[dict[str, Any]]:
    """Normalize a conservative subset of SEC XBRL facts without guessing tags."""
    facts = (structured_facts or {}).get("facts", {})
    taxonomy = facts.get("us-gaap") or facts.get("ifrs-full") or {}
    concepts = {
        "official_revenue": (
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "Revenues",
        ),
        "official_net_income": ("NetIncomeLoss", "ProfitLoss"),
        "official_stockholders_equity": (
            "StockholdersEquity",
            "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        ),
        "official_cash": ("CashAndCashEquivalentsAtCarryingValue",),
        "official_diluted_eps": ("EarningsPerShareDiluted",),
    }
    cutoff = pd.Timestamp(analysis_date)
    result = []
    for metric_id, candidates in concepts.items():
        concept_name = next((name for name in candidates if name in taxonomy), None)
        if concept_name is None:
            continue
        concept = taxonomy[concept_name]
        candidates_rows = []
        for unit, rows in concept.get("units", {}).items():
            for row in rows:
                filed = pd.to_datetime(row.get("filed"), errors="coerce")
                if pd.isna(filed) or filed > cutoff:
                    continue
                if row.get("form") not in ("10-K", "10-Q", "20-F", "40-F", "6-K"):
                    continue
                value = _finite(row.get("val"))
                if value is None:
                    continue
                candidates_rows.append((filed, str(row.get("end", "")), unit, row, value))
        if not candidates_rows:
            continue
        _, end, unit, row, value = max(
            candidates_rows, key=lambda item: (item[0], item[1])
        )
        result.append(_metric(
            metric_id,
            value,
            unit=unit,
            currency=(unit if len(unit) == 3 and unit.isalpha() else None),
            period=end or None,
            provider="SEC EDGAR XBRL",
            source_field=f"{concept_name}.units.{unit}",
            status="verified",
            allowed_uses=["official_fundamental_cross_check"],
            quality_flags=[
                f"form={row.get('form')}",
                f"fiscal_period={row.get('fp')}",
                f"filed={row.get('filed')}",
            ],
        ))
    return result


def build_validated_metrics(
    *,
    ticker: str,
    market: str,
    analysis_date: str,
    snapshot: dict[str, Any],
    fx: dict[str, Any],
    audit_metrics: dict[str, Any],
    official_filings: dict[str, Any],
    sankey_data: dict[str, Any] | None,
    official_structured_facts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a fail-closed, typed numeric contract for downstream agents."""
    info = snapshot.get("info", {})
    quote_currency = snapshot.get("quote_currency")
    financial_currency = snapshot.get("financial_currency")
    metrics = [
        _metric(
            "latest_quarter_revenue_growth_yoy", info.get("revenueGrowth"),
            unit="ratio", currency=financial_currency, period="latest_reported_quarter",
            provider="yfinance", source_field="info.revenueGrowth",
            allowed_uses=["historical_growth"],
            quality_flags=["historical_actual_not_consensus"],
        ),
        _metric(
            "latest_quarter_earnings_growth_yoy", info.get("earningsGrowth"),
            unit="ratio", currency=financial_currency, period="latest_reported_quarter",
            provider="yfinance", source_field="info.earningsGrowth",
            allowed_uses=["historical_growth"],
            quality_flags=["historical_actual_not_consensus"],
        ),
        _metric(
            "current_price", audit_metrics.get("current_price"),
            unit="currency_per_share", currency=quote_currency,
            period=audit_metrics.get("price_date"), provider="local_audit",
            source_field="ohlcv.latest.Close", status="verified",
            allowed_uses=["valuation", "technical_analysis"],
        ),
        _metric(
            "statement_ttm_diluted_eps",
            audit_metrics.get("statement_ttm_diluted_eps"),
            unit="currency_per_share", currency=financial_currency,
            period="TTM", provider="local_audit",
            source_field="income_stmt.Diluted EPS",
            status=(
                "verified" if audit_metrics.get("ttm_valuation_reconciliation_status")
                in ("verified", "statement_only") else "unavailable"
            ),
            allowed_uses=["valuation"],
            quality_flags=([] if audit_metrics.get("ttm_periods_contiguous") else ["non_contiguous_quarters"]),
        ),
        _metric(
            "point_in_time_pe", audit_metrics.get("statement_ttm_pe"),
            unit="multiple", currency=None, period=audit_metrics.get("price_date"),
            provider="local_audit", source_field="converted_price / statement_ttm_eps",
            status="verified" if audit_metrics.get("valuation_currency_status") == "verified" else "unavailable",
            allowed_uses=["valuation"],
        ),
        _metric(
            "point_in_time_pb", audit_metrics.get("price_to_book"),
            unit="multiple", currency=None, period=audit_metrics.get("price_date"),
            provider="local_audit", source_field="converted_price / book_value_per_share",
            status="verified" if audit_metrics.get("valuation_currency_status") == "verified" else "unavailable",
            allowed_uses=["valuation"],
        ),
        _metric(
            "point_in_time_ev_to_ebitda", audit_metrics.get("ev_to_provider_ttm_ebitda"),
            unit="multiple", currency=None, period=audit_metrics.get("price_date"),
            provider="local_audit", source_field="converted_enterprise_value / provider_ttm_ebitda",
            status="verified" if audit_metrics.get("valuation_currency_status") == "verified" else "unavailable",
            allowed_uses=["valuation"],
        ),
    ]

    for table_name in ("earnings_estimate", "revenue_estimate", "eps_trend", "eps_revisions"):
        for record in snapshot.get("analyst_tables", {}).get(table_name, []):
            for field, value in record.items():
                if field in ("period", "currency"):
                    continue
                metrics.append(_metric(
                    f"{table_name}.{record['period']}.{field}", value,
                    unit="count" if "Analyst" in field or field.lower().startswith(("up", "down")) else "provider_native",
                    currency=record.get("currency"), period=record["period"],
                    provider="yfinance", source_field=f"{table_name}.{field}",
                    allowed_uses=["expectation_analysis"],
                ))
    metrics.extend(_sec_official_metrics(official_structured_facts, analysis_date))

    translated_currencies = sorted({
        str(period.get("currency"))
        for period in (sankey_data or {}).get("revenue_sankey", [])
        if period.get("currency")
    })
    currency_ready = (
        quote_currency is not None
        and financial_currency is not None
        and fx.get("status") == "verified"
    )
    ttm_ready = (
        audit_metrics.get("statement_ttm_diluted_eps") is not None
        and audit_metrics.get("ttm_periods_contiguous") is True
    )
    exact_pe_ready = currency_ready and ttm_ready
    exact_pb_ready = currency_ready and audit_metrics.get("price_to_book") is not None
    exact_ev_ready = (
        currency_ready
        and audit_metrics.get("ev_to_provider_ttm_ebitda") is not None
    )
    valuation_ready = exact_pe_ready or exact_pb_ready or exact_ev_ready
    consensus_ready = bool(snapshot.get("analyst_tables", {}).get("earnings_estimate"))
    conflicts = [m["metric_id"] for m in metrics if m["status"] == "conflict"]
    return {
        "schema_version": "1.0",
        "ticker": ticker,
        "market": market,
        "analysis_date": analysis_date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "llm_policy": {
            "allowed_input": "Only metrics in this file whose status and allowed_uses permit the claim.",
            "missing_value": "Output N/A or Not Rated; never estimate or interpolate.",
            "allowed_math": "Simple arithmetic over validated metrics only.",
            "raw_provider_values_allowed": False,
        },
        "currency": {
            "quote_currency": quote_currency,
            "financial_currency": financial_currency,
            "evidence": snapshot.get("currency_evidence", {}),
            "fx": fx,
            "status": "verified" if currency_ready else "unavailable",
        },
        "official_filings": {
            key: value for key, value in official_filings.items()
            if key != "structured_facts"
        },
        "source_priority": [
            "official_structured_disclosure",
            "standardized_market_or_financial_api",
            "third_party_translated_presentation",
        ],
        "third_party_translation": {
            "provider": "Longbridge",
            "currencies": translated_currencies,
            "status": "translated_only" if translated_currencies else "unavailable",
            "allowed_uses": ["segment_mix_context"],
            "prohibited_uses": ["official_operating_growth", "cross_currency_valuation"],
        },
        "metrics": metrics,
        "gates": {
            "allow_exact_valuation": valuation_ready,
            "allow_exact_pe": exact_pe_ready,
            "allow_exact_pb": exact_pb_ready,
            "allow_exact_ev_to_ebitda": exact_ev_ready,
            "allow_target_price": exact_pe_ready and consensus_ready,
            "allow_strong_rating": exact_pe_ready and consensus_ready and not conflicts,
            "allow_segment_growth": False,
        },
        "quality": {
            "status": (
                "verified"
                if exact_pe_ready and exact_pb_ready and exact_ev_ready and consensus_ready
                else "partial"
            ),
            "ttm_periods_contiguous": audit_metrics.get("ttm_periods_contiguous"),
            "conflicting_metrics": conflicts,
            "notes": [
                "Official filing discovery does not authorize LLM extraction from PDFs.",
                "Longbridge currency is a translated provider presentation unless original currency and FX are supplied.",
            ],
        },
    }


def render_validation_report(contract: dict[str, Any]) -> str:
    gates = contract.get("gates", {})
    currency = contract.get("currency", {})
    quality = contract.get("quality", {})
    unavailable = [
        metric["metric_id"] for metric in contract.get("metrics", [])
        if metric.get("status") == "unavailable"
    ]
    return "\n".join([
        "# Deterministic Data Validation Report",
        "",
        f"Ticker: {contract.get('ticker')}",
        f"Analysis Date: {contract.get('analysis_date')}",
        f"Quality Status: {quality.get('status', 'partial')}",
        f"Quote Currency: {currency.get('quote_currency') or 'N/A'}",
        f"Financial Currency: {currency.get('financial_currency') or 'N/A'}",
        f"FX Status: {currency.get('fx', {}).get('status', 'unavailable')}",
        f"TTM Periods Contiguous: {quality.get('ttm_periods_contiguous')}",
        "",
        "## Gates",
        "",
        *[f"- {name}: {str(value).lower()}" for name, value in gates.items()],
        "",
        "## Unavailable Metrics",
        "",
        *( [f"- {metric_id}" for metric_id in unavailable] or ["- None"] ),
        "",
        "LLM rule: use the validated_metrics structured artifact only; unavailable or disallowed metrics must be N/A or Not Rated.",
    ])
