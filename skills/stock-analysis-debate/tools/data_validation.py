"""Build the fail-closed validation contract for covered numeric metrics."""

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
    # Analyst-estimate tables may use a presentation/modeling currency that
    # differs from the financial statements. Never promote it to the
    # statement currency; missing explicit metadata must fail closed.
    financial_currency = info.get("financialCurrency")
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


def _positive_metric_ready(metric: dict[str, Any] | None) -> bool:
    """Return whether a valuation input is usable and economically meaningful."""
    return bool(
        metric
        and metric.get("status") in {"verified", "single_source"}
        and isinstance(metric.get("value"), (int, float))
        and not isinstance(metric.get("value"), bool)
        and math.isfinite(metric["value"])
        and metric["value"] > 0
    )


def _select_target_consensus(
    snapshot: dict[str, Any], financial_currency: str | None,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Select a positive annual EPS consensus row without annualizing quarterly data."""
    rows = snapshot.get("analyst_tables", {}).get("earnings_estimate", [])
    candidates: list[dict[str, Any]] = []
    observed_reasons: set[str] = set()
    if not rows:
        return None, ["earnings_estimate_missing"]

    for record in rows:
        period = str(record.get("period") or "").strip()
        average = _finite(record.get("avg"))
        analyst_count = _finite(record.get("numberOfAnalysts"))
        currency = str(record.get("currency") or "").strip().upper()

        if period not in {"0y", "+1y"}:
            observed_reasons.add("annual_forecast_period_missing")
            continue
        if average is None or average <= 0:
            observed_reasons.add("forecast_eps_not_positive")
            continue
        if analyst_count is None or analyst_count <= 0:
            observed_reasons.add("forecast_analyst_count_invalid")
            continue
        if not financial_currency or currency != financial_currency.upper():
            observed_reasons.add("forecast_currency_mismatch")
            continue
        candidates.append({
            "period": period,
            "avg": average,
            "numberOfAnalysts": analyst_count,
            "currency": currency,
        })

    if not candidates:
        return None, sorted(observed_reasons or {"valid_earnings_consensus_missing"})
    candidates.sort(key=lambda row: (row["period"] != "+1y", row["period"]))
    return candidates[0], []


def _gate_detail(
    *,
    blocking_reasons: list[str],
    required_metric_ids: list[str],
    **context: Any,
) -> dict[str, Any]:
    return {
        "allowed": not blocking_reasons,
        "blocking_reasons": blocking_reasons,
        "required_metric_ids": required_metric_ids,
        **context,
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


def _official_financial_metrics(
    official_financials: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Expose normalized official facts without collapsing different periods."""
    result = []
    for index, fact in enumerate((official_financials or {}).get("facts", [])):
        if not isinstance(fact, dict):
            continue
        value = _finite(fact.get("value"))
        metric = str(fact.get("metric") or "").strip()
        if value is None or not metric:
            continue
        period = fact.get("period_end") or fact.get("period_type") or "unknown"
        metric_id = f"official_financials.{metric}.{period}.{index}"
        normalized = _metric(
            metric_id,
            value,
            unit=str(fact.get("unit") or "provider_native"),
            currency=fact.get("currency"),
            period=period,
            provider=str(fact.get("provider") or fact.get("source") or "official"),
            source_field=(
                f"{fact.get('source', 'official')}."
                f"{fact.get('raw_taxonomy', 'unknown')}."
                f"{fact.get('raw_tag', metric)}."
                f"{fact.get('raw_unit', fact.get('unit', 'unknown'))}"
            ),
            status="verified",
            allowed_uses=[
                "official_financials",
                "official_fundamental_cross_check",
                "historical_growth",
            ],
            quality_flags=[
                f"period_type={fact.get('period_type', 'unknown')}",
                f"filed={fact.get('filed_at')}",
            ],
        )
        normalized.update({
            "canonical_metric": metric,
            "period_start": fact.get("period_start"),
            "period_end": fact.get("period_end"),
            "period_type": fact.get("period_type"),
            "fiscal_year": fact.get("fiscal_year"),
            "fiscal_period": fact.get("fiscal_period"),
            "source_url": fact.get("source_url"),
            "accession_number": fact.get("accession_number"),
            "raw_tag": fact.get("raw_tag"),
        })
        result.append(normalized)
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
    official_financials: dict[str, Any] | None = None,
    temporal_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a fail-closed, typed numeric contract for downstream agents."""
    temporal_context = temporal_context or {
        "analysis_mode": "current_research",
        "execution_date": analysis_date,
        "analysis_as_of_date": analysis_date,
        "analysis_timestamp": analysis_date,
        "point_in_time_enforced": False,
        "source_statuses": {},
    }
    historical_replay = temporal_context.get("analysis_mode") == "historical_replay"
    info = snapshot.get("info", {})
    quote_currency = snapshot.get("quote_currency")
    financial_currency = snapshot.get("financial_currency")
    target_consensus, consensus_blocking_reasons = _select_target_consensus(
        snapshot, financial_currency
    )
    reconciliation_status = audit_metrics.get("ttm_valuation_reconciliation_status")
    reconciliation_conflict = reconciliation_status == "mismatch"
    share_count_conflict = (
        audit_metrics.get("share_count_basis_status") == "potential_mismatch"
    )
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
            allowed_uses=["valuation", "technical_analysis", "target_price_input"],
        ),
        _metric(
            "statement_ttm_diluted_eps",
            audit_metrics.get("statement_ttm_diluted_eps"),
            unit="currency_per_share", currency=financial_currency,
            period="TTM", provider="local_audit",
            source_field="income_stmt.Diluted EPS",
            status=(
                "conflict"
                if reconciliation_conflict or share_count_conflict
                else (
                    "verified" if audit_metrics.get("ttm_valuation_reconciliation_status")
                    in ("verified", "statement_only") else "unavailable"
                )
            ),
            allowed_uses=["valuation", "target_price_input"],
            quality_flags=(
                (["provider_statement_mismatch"] if reconciliation_conflict else [])
                + (["share_count_basis_mismatch"] if share_count_conflict else [])
                + ([] if audit_metrics.get("ttm_periods_contiguous") else ["non_contiguous_quarters"])
            ),
        ),
        _metric(
            "point_in_time_pe", audit_metrics.get("statement_ttm_pe"),
            unit="multiple", currency=None, period=audit_metrics.get("price_date"),
            provider="local_audit", source_field="converted_price / statement_ttm_eps",
            status=(
                "unavailable"
                if audit_metrics.get("valuation_currency_status") != "verified"
                else ("conflict" if reconciliation_conflict or share_count_conflict else "verified")
            ),
            allowed_uses=["valuation", "target_price_input"],
            quality_flags=(
                (["provider_statement_mismatch"] if reconciliation_conflict else [])
                + (["share_count_basis_mismatch"] if share_count_conflict else [])
            ),
        ),
        _metric(
            "point_in_time_pb", audit_metrics.get("price_to_book"),
            unit="multiple", currency=None, period=audit_metrics.get("price_date"),
            provider="local_audit", source_field="converted_price / book_value_per_share",
            status=(
                "unavailable"
                if audit_metrics.get("valuation_currency_status") != "verified"
                else ("conflict" if share_count_conflict else "verified")
            ),
            allowed_uses=["valuation"],
        ),
        _metric(
            "point_in_time_ev_to_ebitda", audit_metrics.get("ev_to_provider_ttm_ebitda"),
            unit="multiple", currency=None, period=audit_metrics.get("price_date"),
            provider="local_audit", source_field="converted_enterprise_value / provider_ttm_ebitda",
            status=(
                "unavailable"
                if audit_metrics.get("valuation_currency_status") != "verified"
                else ("conflict" if share_count_conflict else "verified")
            ),
            allowed_uses=["valuation"],
        ),
    ]

    for table_name in ("earnings_estimate", "revenue_estimate", "eps_trend", "eps_revisions"):
        for record in snapshot.get("analyst_tables", {}).get(table_name, []):
            for field, value in record.items():
                if field in ("period", "currency"):
                    continue
                target_input = bool(
                    target_consensus
                    and table_name == "earnings_estimate"
                    and record.get("period") == target_consensus["period"]
                    and field in {"avg", "numberOfAnalysts"}
                )
                metrics.append(_metric(
                    f"{table_name}.{record['period']}.{field}", value,
                    unit="count" if "Analyst" in field or field.lower().startswith(("up", "down")) else "provider_native",
                    currency=record.get("currency"), period=record["period"],
                    provider="yfinance", source_field=f"{table_name}.{field}",
                    allowed_uses=(
                        ["expectation_analysis", "target_price_input"]
                        if target_input else ["expectation_analysis"]
                    ),
                ))
    metrics.extend(_sec_official_metrics(official_structured_facts, analysis_date))
    metrics.extend(_official_financial_metrics(official_financials))

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
    metrics_by_id = {metric["metric_id"]: metric for metric in metrics}

    exact_pe_reasons: list[str] = []
    if historical_replay:
        exact_pe_reasons.append("historical_replay_non_point_in_time_valuation_inputs")
    if not currency_ready:
        exact_pe_reasons.append("valuation_currency_unverified")
    if not _positive_metric_ready(metrics_by_id.get("current_price")):
        exact_pe_reasons.append("current_price_not_positive")
    if not _positive_metric_ready(metrics_by_id.get("statement_ttm_diluted_eps")):
        exact_pe_reasons.append("ttm_eps_not_positive")
    if audit_metrics.get("ttm_periods_contiguous") is not True:
        exact_pe_reasons.append("ttm_quarters_not_contiguous")
    if not _positive_metric_ready(metrics_by_id.get("point_in_time_pe")):
        exact_pe_reasons.append("point_in_time_pe_unavailable")
    if share_count_conflict:
        exact_pe_reasons.append("share_count_basis_mismatch")
    exact_pe_ready = not exact_pe_reasons

    exact_pb_reasons: list[str] = []
    if historical_replay:
        exact_pb_reasons.append("historical_replay_non_point_in_time_valuation_inputs")
    if not currency_ready:
        exact_pb_reasons.append("valuation_currency_unverified")
    if not _positive_metric_ready(metrics_by_id.get("point_in_time_pb")):
        exact_pb_reasons.append("point_in_time_pb_unavailable")
    if share_count_conflict:
        exact_pb_reasons.append("share_count_basis_mismatch")
    exact_pb_ready = not exact_pb_reasons

    exact_ev_reasons: list[str] = []
    if historical_replay:
        exact_ev_reasons.append("historical_replay_non_point_in_time_valuation_inputs")
    if not currency_ready:
        exact_ev_reasons.append("valuation_currency_unverified")
    if not _positive_metric_ready(metrics_by_id.get("point_in_time_ev_to_ebitda")):
        exact_ev_reasons.append("point_in_time_ev_to_ebitda_unavailable")
    if share_count_conflict:
        exact_ev_reasons.append("share_count_basis_mismatch")
    exact_ev_ready = not exact_ev_reasons

    valuation_ready = exact_pe_ready or exact_pb_ready or exact_ev_ready
    conflicts = [m["metric_id"] for m in metrics if m["status"] == "conflict"]
    if reconciliation_conflict:
        conflicts.append("provider_vs_statement_ttm_valuation")
    if share_count_conflict:
        conflicts.append("share_count_basis_mismatch")

    target_required_metric_ids = [
        "current_price",
        "statement_ttm_diluted_eps",
        "point_in_time_pe",
    ]
    if target_consensus:
        target_required_metric_ids.extend([
            f"earnings_estimate.{target_consensus['period']}.avg",
            f"earnings_estimate.{target_consensus['period']}.numberOfAnalysts",
        ])
    target_reasons = list(exact_pe_reasons) + list(consensus_blocking_reasons)
    if reconciliation_conflict:
        target_reasons.append("provider_statement_ttm_conflict")
    if share_count_conflict:
        target_reasons.append("share_count_basis_mismatch")
    for metric_id in target_required_metric_ids:
        metric = metrics_by_id.get(metric_id)
        if not metric or "target_price_input" not in metric.get("allowed_uses", []):
            target_reasons.append(f"target_price_use_not_allowed:{metric_id}")
    target_reasons = list(dict.fromkeys(target_reasons))
    target_ready = not target_reasons

    strong_rating_reasons = list(target_reasons)
    strong_rating_ready = not strong_rating_reasons
    strong_rating_decision_requirements = [
        "valid_relative_return_evidence",
        "traceable_catalyst_evidence",
        "traceable_thesis_invalidation_condition",
    ]

    gate_details = {
        "allow_exact_valuation": _gate_detail(
            blocking_reasons=(
                [] if valuation_ready else ["no_exact_valuation_method_available"]
            ),
            required_metric_ids=[],
            available_methods=[
                method for method, ready in (
                    ("trailing_pe", exact_pe_ready),
                    ("price_to_book", exact_pb_ready),
                    ("ev_to_ebitda", exact_ev_ready),
                ) if ready
            ],
        ),
        "allow_exact_pe": _gate_detail(
            blocking_reasons=exact_pe_reasons,
            required_metric_ids=[
                "current_price", "statement_ttm_diluted_eps", "point_in_time_pe"
            ],
        ),
        "allow_exact_pb": _gate_detail(
            blocking_reasons=exact_pb_reasons,
            required_metric_ids=["current_price", "point_in_time_pb"],
        ),
        "allow_exact_ev_to_ebitda": _gate_detail(
            blocking_reasons=exact_ev_reasons,
            required_metric_ids=["point_in_time_ev_to_ebitda"],
        ),
        "allow_target_price": _gate_detail(
            blocking_reasons=target_reasons,
            required_metric_ids=target_required_metric_ids,
            valuation_method="forward_eps_x_explicit_scenario_pe",
            forecast_period=(target_consensus or {}).get("period"),
            sensitivity_required=True,
        ),
        "allow_strong_rating": _gate_detail(
            blocking_reasons=strong_rating_reasons,
            required_metric_ids=target_required_metric_ids,
            phase_7_requirements=strong_rating_decision_requirements,
            note="Numeric prerequisites only; Phase 7 requirements are also mandatory.",
        ),
        "allow_segment_growth": _gate_detail(
            blocking_reasons=["segment_growth_not_validated"],
            required_metric_ids=[],
        ),
    }
    official_financials_contract = official_financials or {
        "schema_version": "1.0",
        "status": "unavailable",
        "numeric_status": "unavailable",
        "numeric_reason": "official_financials_not_fetched",
        "filings": [],
        "facts": [],
    }
    official_numeric_status = official_financials_contract.get(
        "numeric_status", "unavailable"
    )
    quality_notes = [
        "Official filing discovery does not authorize LLM extraction from PDFs.",
        "Only normalized official facts with source, period, unit, and currency metadata enter the official financials layer.",
        "Longbridge currency is a translated provider presentation unless original currency and FX are supplied.",
    ]
    if official_numeric_status != "available":
        quality_notes.append(
            "Official numeric facts are unavailable; no official value was fabricated or replaced by a commercial provider."
        )
    if historical_replay:
        quality_notes.append(
            "Historical replay excludes retrieval-time snapshots without verified point-in-time availability."
        )
    return {
        "schema_version": "1.2",
        "ticker": ticker,
        "market": market,
        "analysis_date": analysis_date,
        "execution_date": temporal_context.get("execution_date", analysis_date),
        "analysis_as_of_date": temporal_context.get("analysis_as_of_date", analysis_date),
        "temporal_context": temporal_context,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "llm_policy": {
            "allowed_input": "Current-run DATA_DIR artifacts listed in SKILL.md, with source field and period/as-of date; metrics covered by this file also require an allowed status and allowed_uses.",
            "missing_value": "Output N/A or Not Rated; never estimate or interpolate.",
            "allowed_math": "Prefer tool-derived values; allow presentation-only rounding/unit scaling and explicit workflow-required target-price or position formulas.",
            "raw_provider_values_allowed": not historical_replay,
            "raw_provider_value_scope": (
                "Only sources marked allowed in temporal_context.source_statuses; cite the source field and period/as-of date."
                if historical_replay else
                "Listed current-run DATA_DIR artifacts only; cite the source field and period/as-of date."
            ),
            "validated_metric_bypass_allowed": False,
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
        "official_financials": official_financials_contract,
        "source_priority": [
            "official_structured_disclosure",
            "official_disclosure_document",
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
            "allow_target_price": target_ready,
            "allow_strong_rating": strong_rating_ready,
            "allow_segment_growth": False,
        },
        "gate_details": gate_details,
        "quality": {
            "status": (
                "verified"
                if exact_pe_ready and exact_pb_ready and exact_ev_ready and target_consensus
                else "partial"
            ),
            "ttm_periods_contiguous": audit_metrics.get("ttm_periods_contiguous"),
            "conflicting_metrics": conflicts,
            "official_numeric_status": official_numeric_status,
            "notes": quality_notes,
        },
    }


def render_validation_report(contract: dict[str, Any]) -> str:
    gates = contract.get("gates", {})
    gate_details = contract.get("gate_details", {})
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
        f"Execution Date: {contract.get('execution_date', contract.get('analysis_date'))}",
        f"Analysis Mode: {contract.get('temporal_context', {}).get('analysis_mode', 'current_research')}",
        f"Analysis Timestamp: {contract.get('temporal_context', {}).get('analysis_timestamp', contract.get('analysis_date'))}",
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
        "## Gate Blocking Reasons",
        "",
        *(
            [
                f"- {name}: {', '.join(detail.get('blocking_reasons', [])) or 'None'}"
                for name, detail in gate_details.items()
            ]
            or ["- None"]
        ),
        "",
        "## Unavailable Metrics",
        "",
        *( [f"- {metric_id}" for metric_id in unavailable] or ["- None"] ),
        "",
        "LLM rule: use only sources allowed by temporal_context plus the listed current-run DATA_DIR artifacts, with source and period; for metrics covered by validated_metrics, unavailable or disallowed values remain N/A or Not Rated and cannot be restored from another artifact.",
    ])
