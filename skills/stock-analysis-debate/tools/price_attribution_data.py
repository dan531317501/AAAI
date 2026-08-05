"""Best-effort market context for price-action attribution.

The generated artifacts are evidence inputs, not trading signals.  They make
relative returns and provider expectation records explicit while preserving a
clear Not Rated path when a source is unavailable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd
import yfinance as yf

from provider_runtime import retry_call


WINDOWS = (1, 5, 20)

BROAD_MARKET = {
    "US": ("broad_market", "S&P 500", "^GSPC"),
    "HK": ("broad_market", "Hang Seng Index", "^HSI"),
    "CN": ("broad_market", "CSI 300", "000300.SS"),
}

US_SECTOR_PROXIES = {
    "Basic Materials": ("Materials Select Sector SPDR", "XLB"),
    "Communication Services": ("Communication Services Select Sector SPDR", "XLC"),
    "Consumer Cyclical": ("Consumer Discretionary Select Sector SPDR", "XLY"),
    "Consumer Defensive": ("Consumer Staples Select Sector SPDR", "XLP"),
    "Energy": ("Energy Select Sector SPDR", "XLE"),
    "Financial Services": ("Financial Select Sector SPDR", "XLF"),
    "Healthcare": ("Health Care Select Sector SPDR", "XLV"),
    "Industrials": ("Industrial Select Sector SPDR", "XLI"),
    "Real Estate": ("Real Estate Select Sector SPDR", "XLRE"),
    "Technology": ("Technology Select Sector SPDR", "XLK"),
    "Utilities": ("Utilities Select Sector SPDR", "XLU"),
}


def select_comparators(market: str, ticker: str, sector: str | None) -> list[dict[str, str]]:
    """Choose transparent broad-market and sector/local-market comparators."""
    comparators: list[dict[str, str]] = []
    broad = BROAD_MARKET.get(market)
    if broad:
        kind, label, symbol = broad
        comparators.append({"kind": kind, "label": label, "symbol": symbol})

    if market == "US" and sector in US_SECTOR_PROXIES:
        label, symbol = US_SECTOR_PROXIES[sector]
        comparators.append({"kind": "sector_proxy", "label": label, "symbol": symbol})
    elif market == "HK" and sector in {
        "Technology",
        "Communication Services",
        "Consumer Cyclical",
    }:
        comparators.append(
            {"kind": "sector_proxy", "label": "Hang Seng TECH Index", "symbol": "^HSTECH"}
        )
    elif market == "CN":
        upper = ticker.upper()
        if upper.endswith((".SH", ".SS")) or upper.startswith("6"):
            comparators.append(
                {"kind": "local_market", "label": "SSE Composite", "symbol": "000001.SS"}
            )
        elif upper.endswith(".SZ") or upper.startswith(("0", "3")):
            comparators.append(
                {"kind": "local_market", "label": "SZSE Component", "symbol": "399001.SZ"}
            )

    return comparators


def _normalize_history(data: pd.DataFrame | None) -> pd.DataFrame:
    if data is None or data.empty or "Close" not in data.columns:
        return pd.DataFrame()
    normalized = data[[column for column in ("Close", "Volume") if column in data.columns]].copy()
    index = pd.to_datetime(normalized.index)
    if index.tz is not None:
        index = index.tz_localize(None)
    normalized.index = index.normalize()
    normalized.index.name = "Date"
    return normalized[~normalized.index.duplicated(keep="last")].sort_index()


def _round_number(value: Any, digits: int = 4) -> float | None:
    try:
        if pd.isna(value):
            return None
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _return_pct(start: Any, end: Any) -> float | None:
    start_value = _round_number(start, 10)
    end_value = _round_number(end, 10)
    if start_value in (None, 0) or end_value is None:
        return None
    return round((end_value / start_value - 1.0) * 100.0, 4)


def build_price_context(
    *,
    target_symbol: str,
    market: str,
    sector: str | None,
    target_history: pd.DataFrame,
    comparators: list[dict[str, str]],
    comparator_histories: dict[str, pd.DataFrame | None],
    analysis_date: str,
) -> dict[str, Any]:
    """Build deterministic 1/5/20-session absolute and relative returns."""
    target = _normalize_history(target_history)
    context: dict[str, Any] = {
        "metadata": {
            "target_symbol": target_symbol,
            "market": market,
            "sector": sector or "N/A",
            "analysis_date": analysis_date,
            "data_as_of_date": None,
            "window_definition": (
                "Nd return uses the latest close and the close N target trading sessions earlier"
            ),
            "source": "yfinance target/comparator daily history; target may include upstream fallback",
        },
        "comparators": [],
        "windows": {},
        "daily_series": [],
        "warnings": [],
    }

    if target.empty:
        context["warnings"].append("Target price history unavailable; relative performance Not Rated.")
        return context

    target_close = target["Close"].dropna()
    if target_close.empty:
        context["warnings"].append("Target closes unavailable; relative performance Not Rated.")
        return context

    context["metadata"]["data_as_of_date"] = target_close.index[-1].strftime("%Y-%m-%d")

    normalized_comparators: dict[str, pd.DataFrame] = {}
    for comparator in comparators:
        symbol = comparator["symbol"]
        normalized = _normalize_history(comparator_histories.get(symbol))
        normalized_comparators[symbol] = normalized
        entry = dict(comparator)
        entry["status"] = "available" if not normalized.empty else "not_rated"
        if normalized.empty:
            entry["reason"] = "price history unavailable"
            context["warnings"].append(
                f"{comparator['label']} ({symbol}) unavailable; related excess return Not Rated."
            )
        context["comparators"].append(entry)

    for sessions in WINDOWS:
        key = f"{sessions}d"
        if len(target_close) < sessions + 1:
            context["windows"][key] = {
                "status": "not_rated",
                "reason": f"requires {sessions + 1} target closes; found {len(target_close)}",
            }
            continue

        start_date = target_close.index[-(sessions + 1)]
        end_date = target_close.index[-1]
        target_return = _return_pct(target_close.loc[start_date], target_close.loc[end_date])
        window: dict[str, Any] = {
            "status": "available",
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "target_return_pct": target_return,
            "comparators": {},
        }

        for comparator in comparators:
            symbol = comparator["symbol"]
            data = normalized_comparators[symbol]
            result: dict[str, Any] = {
                "kind": comparator["kind"],
                "label": comparator["label"],
                "symbol": symbol,
            }
            if data.empty or start_date not in data.index or end_date not in data.index:
                result.update(
                    {
                        "status": "not_rated",
                        "reason": "comparator lacks an exact close on the target window endpoints",
                    }
                )
            else:
                comparator_return = _return_pct(
                    data.at[start_date, "Close"], data.at[end_date, "Close"]
                )
                result.update(
                    {
                        "status": "available",
                        "return_pct": comparator_return,
                        "target_excess_return_pct": (
                            round(target_return - comparator_return, 4)
                            if target_return is not None and comparator_return is not None
                            else None
                        ),
                    }
                )
            window["comparators"][comparator["kind"]] = result

        context["windows"][key] = window

    recent_dates = target.index[-60:]
    for date in recent_dates:
        row: dict[str, Any] = {
            "date": date.strftime("%Y-%m-%d"),
            "target_close": _round_number(target.at[date, "Close"]),
            "target_volume": (
                _round_number(target.at[date, "Volume"], 0) if "Volume" in target.columns else None
            ),
            "comparators": {},
        }
        for comparator in comparators:
            data = normalized_comparators[comparator["symbol"]]
            close = data.at[date, "Close"] if not data.empty and date in data.index else None
            row["comparators"][comparator["kind"]] = _round_number(close)
        context["daily_series"].append(row)

    return context


def _format_value(value: Any) -> str:
    if value is None:
        return "N/A"
    try:
        if pd.isna(value):
            return "N/A"
    except (TypeError, ValueError):
        pass
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    return str(value)


def _dated_frame(frame: pd.DataFrame | None) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    result = frame.copy()
    date_column = next(
        (column for column in ("GradeDate", "Earnings Date", "Date") if column in result.columns),
        None,
    )
    index = pd.to_datetime(
        result.pop(date_column) if date_column else result.index,
        errors="coerce",
    )
    if getattr(index, "tz", None) is not None:
        index = index.tz_localize(None)
    result.index = index
    return result[~result.index.isna()].sort_index(ascending=False)


def render_expectations_context(
    *,
    target_symbol: str,
    analysis_date: str,
    info: dict[str, Any] | None,
    earnings_dates: pd.DataFrame | None,
    upgrades_downgrades: pd.DataFrame | None,
    earnings_estimate: pd.DataFrame | None = None,
    revenue_estimate: pd.DataFrame | None = None,
    eps_trend: pd.DataFrame | None = None,
    eps_revisions: pd.DataFrame | None = None,
    retrieved_at: datetime | None = None,
) -> str:
    """Render expectation records with strict point-in-time caveats."""
    retrieved_at = retrieved_at or datetime.now(timezone.utc)
    info = info or {}
    analysis_cutoff = pd.Timestamp(analysis_date)
    lines = [
        f"# Expectations Context for {target_symbol}",
        "",
        f"Analysis Date: {analysis_date}",
        f"Retrieved At (UTC): {retrieved_at.astimezone(timezone.utc).isoformat()}",
        "Provider: yfinance",
        "",
        "## Point-in-Time Guardrail",
        "",
        "Provider consensus snapshot fields reflect retrieval-time state, not necessarily the market's pre-event expectation.",
        "They may describe current consensus but MUST NOT by themselves prove that a catalyst was unexpected or already priced in.",
        "For historical analysis dates earlier than retrieval date, snapshot fields are Not Rated as pre-event evidence.",
        "",
        "## Provider Snapshot",
        "",
        "| Field | Value |",
        "|---|---:|",
    ]

    snapshot_fields = (
        ("Recommendation", "recommendationKey"),
        ("Recommendation Mean", "recommendationMean"),
        ("Analyst Opinions", "numberOfAnalystOpinions"),
        ("Target Low Price", "targetLowPrice"),
        ("Target Mean Price", "targetMeanPrice"),
        ("Target Median Price", "targetMedianPrice"),
        ("Target High Price", "targetHighPrice"),
        ("Forward EPS", "forwardEps"),
        ("Forward P/E", "forwardPE"),
    )
    for label, key in snapshot_fields:
        lines.append(f"| {label} | {_format_value(info.get(key))} |")

    lines.extend([
        "",
        "## Latest-Quarter Historical Growth",
        "",
        "These are reported latest-quarter year-over-year fields, not analyst forecasts.",
        "",
        "| Field | Value | Currency |",
        "|---|---:|---|",
        f"| Revenue Growth (actual YoY) | {_format_value(info.get('revenueGrowth'))} | {_format_value(info.get('financialCurrency'))} |",
        f"| Earnings Growth (actual YoY) | {_format_value(info.get('earningsGrowth'))} | {_format_value(info.get('financialCurrency'))} |",
        "",
        "## Structured Analyst Estimates",
        "",
        "The following tables come from dedicated provider estimate endpoints. Currency is preserved per row.",
    ])

    def append_frame(title: str, frame: pd.DataFrame | None) -> None:
        lines.extend(["", f"### {title}", ""])
        if frame is None or frame.empty:
            lines.append("N/A — dedicated estimate endpoint unavailable.")
            return
        columns = [str(column) for column in frame.columns]
        lines.append("| Period | " + " | ".join(columns) + " |")
        lines.append("|---|" + "---:|" * len(columns))
        for period, row in frame.iterrows():
            lines.append(
                "| " + str(period) + " | "
                + " | ".join(_format_value(row.get(column)) for column in frame.columns)
                + " |"
            )

    append_frame("Earnings Estimate", earnings_estimate)
    append_frame("Revenue Estimate", revenue_estimate)
    append_frame("EPS Trend", eps_trend)
    append_frame("EPS Revisions", eps_revisions)

    lines.extend(
        [
            "",
            "## Earnings Records Available by Analysis Date",
            "",
            "These are provider event records. Treat EPS Estimate as historical consensus evidence only when the event date and record are complete.",
            "",
            "| Event Date | EPS Estimate | Reported EPS | Surprise (%) |",
            "|---|---:|---:|---:|",
        ]
    )
    earnings = _dated_frame(earnings_dates)
    if not earnings.empty:
        earnings = earnings[earnings.index.normalize() <= analysis_cutoff]
    if earnings.empty:
        lines.append("| N/A | N/A | N/A | N/A |")
    else:
        for event_date, row in earnings.head(8).iterrows():
            lines.append(
                "| "
                + " | ".join(
                    [
                        event_date.strftime("%Y-%m-%d"),
                        _format_value(row.get("EPS Estimate")),
                        _format_value(row.get("Reported EPS")),
                        _format_value(row.get("Surprise(%)")),
                    ]
                )
                + " |"
            )

    lines.extend(
        [
            "",
            "## Rating Actions Available by Analysis Date (90 Calendar Days)",
            "",
            "| Date | Firm | Action | From | To |",
            "|---|---|---|---|---|",
        ]
    )
    ratings = _dated_frame(upgrades_downgrades)
    if not ratings.empty:
        ratings = ratings[
            (ratings.index.normalize() <= analysis_cutoff)
            & (ratings.index.normalize() >= analysis_cutoff - pd.Timedelta(days=90))
        ]
    if ratings.empty:
        lines.append("| N/A | N/A | N/A | N/A | N/A |")
    else:
        for event_date, row in ratings.head(20).iterrows():
            lines.append(
                "| "
                + " | ".join(
                    [
                        event_date.strftime("%Y-%m-%d"),
                        _format_value(row.get("Firm")),
                        _format_value(row.get("Action")),
                        _format_value(row.get("FromGrade")),
                        _format_value(row.get("ToGrade")),
                    ]
                )
                + " |"
            )

    lines.extend(
        [
            "",
            "## Use Rules",
            "",
            "- Compute surprise from pre-event expectation versus actual result; a good absolute result is not automatically a positive surprise.",
            "- Do not infer 'fully priced in' from target prices, recommendation means, or price action alone.",
            "- Treat revenueGrowth and earningsGrowth as historical actual YoY fields, never as consensus forecasts.",
            "- When pre-event consensus, estimate revisions, or event timing is unavailable, mark the expectation gap or priced-in assessment Not Rated.",
            "- Media consensus figures require a dated source URL and must be labeled as third-party estimates.",
        ]
    )
    return "\n".join(lines)


def fetch_attribution_context(
    *,
    target_symbol: str,
    market: str,
    analysis_date: str,
    price_start: str,
    target_history: pd.DataFrame,
    include_retrieval_snapshot: bool = True,
) -> tuple[dict[str, Any], str]:
    """Fetch comparator prices and expectation records with graceful degradation."""
    stock = yf.Ticker(target_symbol) if include_retrieval_snapshot else None
    info = {}
    if stock is not None:
        try:
            info = retry_call(
                lambda: stock.info or {}, provider="yfinance",
                operation=f"{target_symbol}.info",
            )
        except Exception:
            info = {}

    sector = info.get("sector")
    comparators = select_comparators(market, target_symbol, sector)
    comparator_histories: dict[str, pd.DataFrame | None] = {}
    end_exclusive = (pd.Timestamp(analysis_date) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    for comparator in comparators:
        try:
            comparator_histories[comparator["symbol"]] = retry_call(
                lambda symbol=comparator["symbol"]: yf.Ticker(symbol).history(
                    start=price_start, end=end_exclusive
                ),
                provider="yfinance",
                operation=f"{comparator['symbol']}.history",
            )
        except Exception:
            comparator_histories[comparator["symbol"]] = None

    price_context = build_price_context(
        target_symbol=target_symbol,
        market=market,
        sector=sector,
        target_history=target_history,
        comparators=comparators,
        comparator_histories=comparator_histories,
        analysis_date=analysis_date,
    )

    if not include_retrieval_snapshot:
        expectations = (
            f"# Expectations Context for {target_symbol}\n\n"
            f"Analysis Date: {analysis_date}\n"
            "Analysis Mode: historical_replay\n\n"
            "Not Rated — retrieval-time consensus, earnings-event records, rating "
            "actions, targets, and revisions were excluded because the provider does "
            "not prove that this snapshot was visible at the historical cutoff.\n"
        )
        return price_context, expectations

    try:
        earnings_dates = retry_call(
            lambda: stock.get_earnings_dates(limit=12),
            provider="yfinance", operation=f"{target_symbol}.earnings_dates",
        )
    except Exception:
        earnings_dates = None
    try:
        upgrades_downgrades = retry_call(
            lambda: stock.upgrades_downgrades,
            provider="yfinance", operation=f"{target_symbol}.upgrades_downgrades",
        )
    except Exception:
        upgrades_downgrades = None

    estimates = {}
    for name in (
        "get_earnings_estimate",
        "get_revenue_estimate",
        "get_eps_trend",
        "get_eps_revisions",
    ):
        try:
            estimates[name] = retry_call(
                lambda method=name: getattr(stock, method)(),
                provider="yfinance",
                operation=f"{target_symbol}.{name}",
            )
        except Exception:
            estimates[name] = None

    expectations = render_expectations_context(
        target_symbol=target_symbol,
        analysis_date=analysis_date,
        info=info,
        earnings_dates=earnings_dates,
        upgrades_downgrades=upgrades_downgrades,
        earnings_estimate=estimates["get_earnings_estimate"],
        revenue_estimate=estimates["get_revenue_estimate"],
        eps_trend=estimates["get_eps_trend"],
        eps_revisions=estimates["get_eps_revisions"],
    )
    return price_context, expectations
