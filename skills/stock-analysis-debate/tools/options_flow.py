#!/usr/bin/env python3
"""Options-flow fetcher for the stock-analysis-debate skill.

Fetches the yfinance option chain (free, no API key) and derives
behavioral positioning metrics that complement sentiment/news analysis:

  - Put/Call Volume Ratio      — recent directional activity (short-term)
  - Put/Call Open-Interest Ratio — outstanding-position lean (longer-term)
  - IV skew (OTM Put IV − OTM Call IV) — relative cost of downside protection
  - Most-active contracts      — where the money is actually trading
  - High volume/OI contracts   — freshly opened positions (new activity)

Interpretation is deliberately left to the Options Flow Analyst prompt
(``prompts/options_flow_analyst.md``): a high PCR is NOT automatically
bearish (institutions buy puts to hedge long stock), and OI vs volume
carry different horizons. This module only computes and renders facts.

Usage (normally invoked from fetch_data.py):
    python options_flow.py <TICKER> <ANALYSIS_DATE> [--spot <PRICE>]

Output: plaintext block suitable for ``options.txt`` in the date output
directory. Degrades gracefully — any network/parse failure produces a
placeholder line, never an exception.
"""

from __future__ import annotations

import argparse
import logging
import math
import sys
from datetime import datetime

import pandas as pd
import yfinance as yf

from provider_runtime import retry_call

logger = logging.getLogger(__name__)

# yfinance fills IV with 0.00001 (or 0) for contracts with no quoted
# market; anything below this threshold is treated as unquoted junk.
MIN_VALID_IV = 0.01
# Only contracts with at least this volume count as "active".
MIN_ACTIVE_VOLUME = 100
# A contract with volume > OI * this factor is treated as freshly opened.
VOL_OI_ACTIVITY_FACTOR = 2.0
# Skip expiries with fewer than this many days until expiry (DTE < 1 is
# same-day gamma noise; DTE=0 data is not meaningful for positioning).
MIN_DTE = 1
# Percentage bands used to pick representative OTM strikes for the skew.
OTM_CALL_BAND = 1.05   # ~5% above spot
OTM_PUT_BAND = 0.95    # ~5% below spot


def _num(value) -> float:
    """Parse a numeric cell to float, or None when not a finite number."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _fmt_int(value) -> str:
    """Format an integer with thousands separators, N/A when absent."""
    return "N/A" if value is None else f"{int(value):,}"


def _fmt_ratio(value) -> str:
    """Format a ratio to 2 decimals, N/A when absent."""
    return "N/A" if value is None else f"{value:.2f}"


def _fmt_iv(value) -> str:
    """Format an IV as percent, N/A when absent/invalid."""
    if value is None or value < MIN_VALID_IV:
        return "N/A"
    return f"{value * 100:.1f}%"


def _days_to_expiry(expiry: str, analysis_date: str) -> int:
    """Calendar days between the analysis date and the expiry date."""
    try:
        exp = datetime.strptime(expiry, "%Y-%m-%d")
        ana = datetime.strptime(analysis_date, "%Y-%m-%d")
        return max(0, (exp - ana).days)
    except (ValueError, TypeError):
        return 0


def clean_chain(chain_df: pd.DataFrame) -> pd.DataFrame:
    """Normalize a yfinance chain DataFrame: drop junk rows, fill NaN.

    - Rows with no valid strike are dropped.
    - volume / openInterest NaN is filled with 0 (untraded contract).
    - Negative or invalid IV is set to NaN so it renders as N/A.
    """
    if chain_df is None or chain_df.empty:
        return pd.DataFrame(
            columns=["strike", "volume", "openInterest", "impliedVolatility"]
        )
    df = chain_df.copy()
    # Ensure every downstream accessor sees the canonical columns, even when
    # a caller passes a bare/partial frame (empty rows may carry no columns).
    for col in ("strike", "volume", "openInterest"):
        if col not in df.columns:
            df[col] = float("nan")
    if "impliedVolatility" not in df.columns:
        df["impliedVolatility"] = float("nan")
    df = df[df["strike"].notna()]
    for col in ("volume", "openInterest"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    df["impliedVolatility"] = pd.to_numeric(
        df["impliedVolatility"], errors="coerce"
    )
    df.loc[df["impliedVolatility"] < MIN_VALID_IV, "impliedVolatility"] = float("nan")
    return df


def _pick_strike(df: pd.DataFrame, target: float) -> float | None:
    """Return the strike closest to ``target`` among valid rows, else None."""
    if df is None or df.empty or "strike" not in df.columns:
        return None
    valid = df["strike"].dropna()
    if valid.empty:
        return None
    return float(valid.iloc[(valid - target).abs().argsort()[:1]].iloc[0])


def _iv_at_strike(df: pd.DataFrame, strike: float) -> float | None:
    """Return the IV of the row whose strike equals ``strike``, else None."""
    row = df[df["strike"] == strike]
    if row.empty:
        return None
    return _num(row["impliedVolatility"].iloc[0])


def _total(df: pd.DataFrame, column: str) -> float | None:
    """Sum a numeric column; None when the column is absent."""
    if column not in df.columns or df.empty:
        return None
    return float(df[column].sum())


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def _top_contract(df: pd.DataFrame, strike_col: str = "strike") -> str | None:
    """Describe the highest-volume contract, or None when none is active."""
    active = df[df["volume"] >= MIN_ACTIVE_VOLUME]
    if active.empty:
        return None
    top = active.loc[active["volume"].idxmax()]
    strike = _num(top.get("strike"))
    volume = _num(top.get("volume"))
    oi = _num(top.get("openInterest"))
    oi_str = _fmt_int(int(oi)) if oi is not None and oi > 0 else "no OI"
    return (
        f"${strike:.2f} strike, vol {_fmt_int(int(volume))} / {oi_str}"
        if strike is not None and volume is not None
        else None
    )


def _fresh_contracts(df: pd.DataFrame, limit: int = 3) -> list[str]:
    """Contracts whose volume implies newly opened positions (vol >> OI)."""
    active = df[
        (df["volume"] >= MIN_ACTIVE_VOLUME)
        & (df["openInterest"] > 0)
        & (df["volume"] > df["openInterest"] * VOL_OI_ACTIVITY_FACTOR)
    ]
    if active.empty:
        return []
    active = active.sort_values("volume", ascending=False).head(limit)
    out = []
    for _, row in active.iterrows():
        strike = _num(row.get("strike"))
        volume = _num(row.get("volume"))
        oi = _num(row.get("openInterest"))
        if strike is None or volume is None or oi is None:
            continue
        out.append(
            f"${strike:.2f} (vol {_fmt_int(int(volume))} vs OI {_fmt_int(int(oi))})"
        )
    return out


def compute_expiry_metrics(
    calls: pd.DataFrame,
    puts: pd.DataFrame,
    spot: float | None,
    expiry: str,
    analysis_date: str,
) -> dict:
    """Compute positioning metrics for one expiry; returns a plain dict."""
    calls = clean_chain(calls)
    puts = clean_chain(puts)

    call_volume = _total(calls, "volume")
    put_volume = _total(puts, "volume")
    call_oi = _total(calls, "openInterest")
    put_oi = _total(puts, "openInterest")

    result: dict = {
        "expiry": expiry,
        "dte": _days_to_expiry(expiry, analysis_date),
        "call_volume": call_volume,
        "put_volume": put_volume,
        "call_oi": call_oi,
        "put_oi": put_oi,
        "oi_available": bool(call_oi and put_oi),
        "pcr_volume": _ratio(put_volume, call_volume),
        "pcr_oi": _ratio(put_oi, call_oi),
        "atm_strike": None,
        "atm_call_iv": None,
        "atm_put_iv": None,
        "otm_call_iv": None,
        "otm_put_iv": None,
        "iv_skew_pp": None,
        "top_call": _top_contract(calls),
        "top_put": _top_contract(puts),
        "fresh_calls": _fresh_contracts(calls),
        "fresh_puts": _fresh_contracts(puts),
    }

    if spot is None or spot <= 0 or calls.empty or puts.empty:
        return result

    atm_strike = _pick_strike(calls, spot)
    if atm_strike is None:
        return result
    result["atm_strike"] = atm_strike
    result["atm_call_iv"] = _iv_at_strike(calls, atm_strike)
    result["atm_put_iv"] = _iv_at_strike(puts, atm_strike)

    otm_call_strike = _pick_strike(calls, spot * OTM_CALL_BAND)
    otm_put_strike = _pick_strike(puts, spot * OTM_PUT_BAND)
    result["otm_call_strike"] = otm_call_strike
    result["otm_put_strike"] = otm_put_strike
    result["otm_call_iv"] = _iv_at_strike(calls, otm_call_strike)
    result["otm_put_iv"] = _iv_at_strike(puts, otm_put_strike)

    put_iv = result["otm_put_iv"]
    call_iv = result["otm_call_iv"]
    if put_iv is not None and call_iv is not None:
        # Positive = downside protection priced richer than upside upside.
        result["iv_skew_pp"] = (put_iv - call_iv) * 100
    return result


def render_expiry(metrics: dict) -> list[str]:
    """Render one expiry's metrics as text lines (facts only, no verdicts)."""
    dte = metrics.get("dte")
    expiry_line = f"### Expiry {metrics.get('expiry')}" + (
        f" (DTE {dte})" if dte is not None else ""
    )
    lines = [
        expiry_line,
        f"- Put/Call Volume Ratio: {_fmt_ratio(metrics.get('pcr_volume'))}",
        "  (put volume "
        f"{_fmt_int(metrics.get('put_volume'))} vs call volume "
        f"{_fmt_int(metrics.get('call_volume'))})",
        f"- Put/Call Open-Interest Ratio: {_fmt_ratio(metrics.get('pcr_oi'))}",
        "  (put OI "
        f"{_fmt_int(metrics.get('put_oi'))} vs call OI "
        f"{_fmt_int(metrics.get('call_oi'))})",
    ]
    atm_strike = metrics.get("atm_strike")
    if atm_strike is not None:
        lines.append(
            f"- ATM strike: ${atm_strike:.2f} | ATM call IV {_fmt_iv(metrics.get('atm_call_iv'))}"
            f" | ATM put IV {_fmt_iv(metrics.get('atm_put_iv'))}"
        )
        otm_call_strike = metrics.get("otm_call_strike")
        otm_put_strike = metrics.get("otm_put_strike")
        skew = metrics.get("iv_skew_pp")
        if skew is not None:
            skew_desc = "downside protection priced richer" if skew > 0 else (
                "upside calls priced richer" if skew < 0 else "flat"
            )
            lines.append(
                f"- IV skew (OTM put IV − OTM call IV): {skew:+.1f}pp ({skew_desc})"
            )
        if otm_call_strike is not None:
            lines.append(
                f"  OTM call IV (${otm_call_strike:.2f}): {_fmt_iv(metrics.get('otm_call_iv'))}"
            )
        if otm_put_strike is not None:
            lines.append(
                f"  OTM put IV (${otm_put_strike:.2f}): {_fmt_iv(metrics.get('otm_put_iv'))}"
            )
    if metrics.get("top_call"):
        lines.append(f"- Most active call: {metrics['top_call']}")
    if metrics.get("top_put"):
        lines.append(f"- Most active put: {metrics['top_put']}")
    fresh_calls = metrics.get("fresh_calls") or []
    fresh_puts = metrics.get("fresh_puts") or []
    if fresh_calls or fresh_puts:
        lines.append("- Freshly opened positions (volume >> OI):")
        if fresh_calls:
            lines.append(f"  Calls: {', '.join(fresh_calls)}")
        if fresh_puts:
            lines.append(f"  Puts: {', '.join(fresh_puts)}")
    return lines


def render_options_report(
    expiry_metrics: list[dict],
    *,
    ticker: str,
    analysis_date: str,
    spot: float | None,
    fetched_at: str | None = None,
) -> str:
    """Render the full options.txt block for one ticker."""
    lines = [
        f"## Options Flow for {ticker} (analysis date {analysis_date})",
        f"Data source: yfinance option chain (real-time snapshot; no historical options data)",
        f"Spot reference price: {'N/A' if spot is None else f'${spot:.2f}'}",
    ]
    if fetched_at:
        lines.append(f"Fetched at: {fetched_at}")
    lines.append("")
    if not expiry_metrics:
        lines.append(
            f"<no options data found for {ticker} — Options Flow not rated>"
        )
        return "\n".join(lines)

    # Data-quality notes: surface snapshot limitations so the analyst does
    # not read a missing ratio as a directional signal.
    if all(not m.get("oi_available") for m in expiry_metrics):
        lines.append(
            "NOTE: open-interest data is unavailable in this snapshot "
            "(weekend/after-hours fetch or source limitation); "
            "put/call OI ratios are not rated."
        )
        lines.append("")
    if all(m.get("atm_strike") is not None and m.get("atm_call_iv") is None
           and m.get("atm_put_iv") is None for m in expiry_metrics):
        lines.append(
            "NOTE: ATM implied-volatility quotes are missing in this snapshot; "
            "IV levels and skew are not rated."
        )
        lines.append("")

    for metrics in expiry_metrics:
        lines.extend(render_expiry(metrics))
        lines.append("")
    return "\n".join(lines).rstrip()


def _fetch_expiries(ticker: str) -> list[str]:
    """Return yfinance expiry dates for ``ticker`` (resolved for HK formats)."""
    return list(retry_call(
        lambda: yf.Ticker(ticker).options or [],
        provider="yfinance", operation=f"{ticker}.option_expiries",
    ))


def fetch_options_report(
    ticker: str,
    analysis_date: str,
    *,
    spot_price: float | None = None,
    expiry_count: int = 2,
) -> str:
    """Fetch the option chain and return a ready-to-write ``options.txt`` block.

    Always returns a string — on any failure it returns a placeholder line
    so the caller can degrade gracefully. ``spot_price`` anchors the ATM /
    skew calculations; pass the latest close from OHLCV when available.
    """
    try:
        expiries = _fetch_expiries(ticker)
    except Exception as exc:  # noqa: BLE001 — yfinance raises broadly
        logger.warning("Options expiry fetch failed for %s: %s", ticker, exc)
        return f"<options data unavailable for {ticker}: {type(exc).__name__}>"

    # Skip near-zero-DTE expiries (same-day gamma noise); keep the next
    # ``expiry_count`` that are at least MIN_DTE days out.
    eligible = [
        e for e in expiries if _days_to_expiry(e, analysis_date) >= MIN_DTE
    ][:expiry_count]

    expiry_metrics: list[dict] = []
    for expiry in eligible:
        try:
            chain = retry_call(
                lambda selected_expiry=expiry: yf.Ticker(ticker).option_chain(
                    selected_expiry
                ),
                provider="yfinance",
                operation=f"{ticker}.option_chain.{expiry}",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Options chain fetch failed for %s @ %s: %s", ticker, expiry, exc
            )
            continue
        metrics = compute_expiry_metrics(
            chain.calls, chain.puts, spot_price, expiry, analysis_date
        )
        if metrics.get("call_volume") is None and metrics.get("call_oi") is None:
            continue  # empty chain — treat as no data for this expiry
        expiry_metrics.append(metrics)

    if not expiry_metrics:
        return (
            f"<no options data found for {ticker} — Options Flow not rated>"
        )
    return render_options_report(
        expiry_metrics,
        ticker=ticker,
        analysis_date=analysis_date,
        spot=spot_price,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch options-flow metrics and print an options.txt block"
    )
    parser.add_argument("ticker", help="Ticker symbol (US market)")
    parser.add_argument("analysis_date", help="Analysis date in YYYY-MM-DD")
    parser.add_argument("--spot", type=float, default=None,
                        help="Latest close used to anchor ATM/skew strikes")
    parser.add_argument("--expiry-count", type=int, default=2)
    args = parser.parse_args()

    print(
        fetch_options_report(
            args.ticker,
            args.analysis_date,
            spot_price=args.spot,
            expiry_count=args.expiry_count,
        )
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    main()
