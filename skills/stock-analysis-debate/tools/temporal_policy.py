"""Deterministic time semantics and point-in-time source policy."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo


CURRENT_RESEARCH = "current_research"
HISTORICAL_REPLAY = "historical_replay"
ANALYSIS_MODES = (CURRENT_RESEARCH, HISTORICAL_REPLAY)

MARKET_TIMEZONES = {
    "US": "America/New_York",
    "HK": "Asia/Hong_Kong",
    "CN": "Asia/Shanghai",
}

MARKET_QUOTE_CURRENCIES = {
    "US": "USD",
    "HK": "HKD",
    "CN": "CNY",
}

FINANCIAL_LOOKBACK_DAYS = 365


def _parse_date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be in YYYY-MM-DD format, got: {value}") from exc


def financial_window_start(analysis_date: str) -> date:
    """Return the inclusive start of the rolling financial-data window."""
    return _parse_date(analysis_date, "analysis date") - timedelta(
        days=FINANCIAL_LOOKBACK_DAYS
    )


def _source_policy(mode: str) -> dict[str, dict[str, str]]:
    date_bounded = {
        "status": "allowed",
        "temporal_basis": "observation_date_lte_analysis_timestamp",
    }
    event_bounded = {
        "status": "allowed",
        "temporal_basis": "published_or_filed_at_lte_analysis_timestamp",
    }
    current_snapshot = {
        "status": "allowed",
        "temporal_basis": "retrieval_time_snapshot_for_current_research_only",
    }
    policy = {
        "ohlcv": dict(date_bounded),
        "price_context": dict(date_bounded),
        "indicators": dict(date_bounded),
        "fx_rate": dict(date_bounded),
        "news": dict(event_bounded),
        "global_news": dict(current_snapshot),
        "official_filings": dict(event_bounded),
        "official_companyfacts": dict(event_bounded),
        "provider_snapshot": dict(current_snapshot),
        "analyst_estimates": dict(current_snapshot),
        "valuation_consensus": dict(current_snapshot),
        "expectations": dict(current_snapshot),
        "fundamentals": dict(current_snapshot),
        "financial_statements": dict(current_snapshot),
        "insider_transactions": dict(current_snapshot),
        "options": dict(current_snapshot),
        "macro_indicators": dict(current_snapshot),
        "prediction_markets": dict(current_snapshot),
        "revenue_sankey": dict(current_snapshot),
    }
    if mode == CURRENT_RESEARCH:
        return policy

    for source in (
        "provider_snapshot",
        "analyst_estimates",
        "valuation_consensus",
        "expectations",
        "fundamentals",
        "financial_statements",
        "insider_transactions",
        "options",
        "macro_indicators",
        "prediction_markets",
        "revenue_sankey",
        "global_news",
        "fx_rate",
    ):
        policy[source] = {
            "status": "not_rated",
            "temporal_basis": "no_verified_point_in_time_snapshot",
        }
    policy["news"]["coverage_limitation"] = (
        "Only records with a parseable publication timestamp at or before the cutoff are allowed; "
        "retrieval-time search coverage is not guaranteed complete."
    )
    return policy


def resolve_temporal_context(
    *,
    execution_date: str,
    analysis_mode: str,
    as_of_date: str | None,
    market: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Validate run dates and return the source-level temporal contract."""
    if analysis_mode not in ANALYSIS_MODES:
        raise ValueError(
            f"analysis_mode must be one of {', '.join(ANALYSIS_MODES)}, got: {analysis_mode}"
        )
    execution = _parse_date(execution_date, "execution date")
    now = now or datetime.now().astimezone()
    local_today = now.astimezone().date()
    if execution != local_today:
        raise ValueError(
            f"execution date must match the current local date {local_today.isoformat()}; "
            "use --analysis-mode historical_replay --as-of-date YYYY-MM-DD for a historical cutoff"
        )

    if analysis_mode == CURRENT_RESEARCH:
        if as_of_date and _parse_date(as_of_date, "as-of date") != execution:
            raise ValueError("current_research does not accept a historical --as-of-date")
        cutoff_date = execution
    else:
        if not as_of_date:
            raise ValueError("historical_replay requires --as-of-date YYYY-MM-DD")
        cutoff_date = _parse_date(as_of_date, "as-of date")
        if cutoff_date > execution:
            raise ValueError("historical replay cutoff cannot be after the execution date")

    timezone_name = MARKET_TIMEZONES.get(market, "UTC")
    market_timezone = ZoneInfo(timezone_name)
    cutoff = (
        now.astimezone(market_timezone)
        if analysis_mode == CURRENT_RESEARCH else
        datetime.combine(
            cutoff_date,
            time(23, 59, 59, 999999),
            tzinfo=market_timezone,
        )
    )
    retrieved_at = now.astimezone(timezone.utc).isoformat()
    return {
        "analysis_mode": analysis_mode,
        "execution_date": execution.isoformat(),
        "analysis_as_of_date": cutoff_date.isoformat(),
        "analysis_timestamp": cutoff.isoformat(),
        "analysis_timezone": timezone_name,
        "retrieved_at": retrieved_at,
        "point_in_time_enforced": analysis_mode == HISTORICAL_REPLAY,
        "source_statuses": _source_policy(analysis_mode),
    }


def historical_provider_snapshot(
    *, symbol: str, market: str, temporal_context: dict[str, Any]
) -> dict[str, Any]:
    """Return routing-only metadata without querying mutable provider snapshots."""
    quote_currency = MARKET_QUOTE_CURRENCIES.get(market)
    return {
        "symbol": symbol,
        "analysis_date": temporal_context["analysis_as_of_date"],
        "retrieved_at": temporal_context["retrieved_at"],
        "quote_currency": quote_currency,
        "financial_currency": None,
        "currency_evidence": {
            "quote_currency": "market_listing_convention" if quote_currency else None,
            "financial_currency": "not_rated_no_point_in_time_source",
        },
        "info": {},
        "analyst_tables": {},
        "temporal_status": "not_rated_no_verified_point_in_time_snapshot",
    }


def not_rated_text(domain: str, temporal_context: dict[str, Any]) -> str:
    """Render a consistent placeholder for a blocked historical source."""
    return (
        f"# {domain}\n\n"
        f"Analysis Mode: {temporal_context['analysis_mode']}\n"
        f"Analysis As Of: {temporal_context['analysis_timestamp']}\n"
        "Not Rated — the available provider endpoint is a retrieval-time snapshot "
        "and does not prove what was available at the historical cutoff.\n"
    )


def filter_historical_news(
    records: list[dict[str, Any]], analysis_timestamp: str
) -> tuple[list[dict[str, Any]], int]:
    """Keep only news with a parseable publication timestamp on/before cutoff."""
    cutoff = datetime.fromisoformat(analysis_timestamp)
    kept: list[dict[str, Any]] = []
    excluded = 0
    for record in records:
        raw_date = record.get("published_at") or record.get("date")
        parsed = None
        if raw_date:
            try:
                parsed = datetime.fromisoformat(str(raw_date).replace("Z", "+00:00"))
            except ValueError:
                try:
                    parsed = datetime.strptime(str(raw_date), "%Y-%m-%d %H:%M")
                except ValueError:
                    try:
                        parsed = datetime.strptime(str(raw_date).split(" ")[0], "%Y-%m-%d")
                    except ValueError:
                        parsed = None
        if parsed is None:
            excluded += 1
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=cutoff.tzinfo)
        if parsed.astimezone(cutoff.tzinfo) <= cutoff:
            kept.append(record)
        else:
            excluded += 1
    return kept, excluded
