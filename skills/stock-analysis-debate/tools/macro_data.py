#!/usr/bin/env python3
"""FRED (Federal Reserve Economic Data) macro fetcher for the skill.

Ported from TradingAgents' ``tradingagents/dataflows/fred.py``. Fetches
macroeconomic time series — policy rates, Treasury yields, inflation, labor —
from the St. Louis Fed's free API and renders them as a plaintext block for
``macro_indicators.txt``, grounding the News Analyst's macro commentary in
actual numbers rather than headlines alone.

A free API key (https://fred.stlouisfed.org/docs/api/api_key.html) is read
from the ``FRED_API_KEY`` environment variable. Without it the module degrades
gracefully to a placeholder — the caller never has to special-case it.

Usage (normally invoked from fetch_data.py):
    python macro_data.py <ANALYSIS_DATE> [--lookback-days 365]
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timedelta

import requests

logger = logging.getLogger(__name__)

FRED_API_BASE = "https://api.stlouisfed.org/fred"

# Network timeout (seconds) so a stalled request cannot hang the pipeline.
REQUEST_TIMEOUT = 30

# Default trailing window. A year captures the trend and the YoY base for most
# monthly/quarterly series.
DEFAULT_LOOKBACK_DAYS = 365

# Rows cap per series in the rendered table: recent values matter most, and
# daily series (yields, VIX) over a long window would flood the analyst.
MAX_ROWS = 40

# Curated human-friendly aliases -> FRED series IDs.
MACRO_SERIES = {
    # Policy rate & Treasury yields
    "fed_funds_rate": "FEDFUNDS",
    "federal_funds_rate": "FEDFUNDS",
    "fed_funds": "FEDFUNDS",
    "2y_treasury": "DGS2",
    "10y_treasury": "DGS10",
    "30y_treasury": "DGS30",
    "10y_2y_spread": "T10Y2Y",
    "yield_curve": "T10Y2Y",
    # Inflation
    "cpi": "CPIAUCSL",
    "core_cpi": "CPILFESL",
    "pce": "PCEPI",
    "core_pce": "PCEPILFE",
    "inflation_expectations": "T10YIE",
    # Growth & output
    "real_gdp": "GDPC1",
    "gdp": "GDP",
    "industrial_production": "INDPRO",
    # Labor
    "unemployment_rate": "UNRATE",
    "unemployment": "UNRATE",
    "nonfarm_payrolls": "PAYEMS",
    "payrolls": "PAYEMS",
    "initial_claims": "ICSA",
    # Money & markets
    "m2": "M2SL",
    "money_supply": "M2SL",
    "vix": "VIXCLS",
    "dollar_index": "DTWEXBGS",
    # Sentiment & housing
    "consumer_sentiment": "UMCSENT",
    "housing_starts": "HOUST",
    "retail_sales": "RSAFS",
}

# Core indicators prefetched for every run (a curated subset of the alias
# table: rates, inflation, labor, and the yield curve).
DEFAULT_INDICATORS = [
    "fed_funds_rate",
    "10y_treasury",
    "yield_curve",
    "cpi",
    "core_cpi",
    "unemployment_rate",
]


def get_api_key() -> str:
    """Retrieve the FRED API key from the environment."""
    api_key = os.getenv("FRED_API_KEY")
    if not api_key:
        raise ValueError(
            "FRED_API_KEY environment variable is not set. Get a free key at "
            "https://fred.stlouisfed.org/docs/api/api_key.html."
        )
    return api_key


def resolve_series_id(indicator: str) -> str:
    """Map a friendly alias to a FRED series ID, or pass a raw ID through.

    Raises ``ValueError`` when the input is neither a known alias nor a
    plausible series ID (FRED IDs are short and alphanumeric).
    """
    key = indicator.strip().lower().replace(" ", "_").replace("-", "_")
    if key in MACRO_SERIES:
        return MACRO_SERIES[key]
    candidate = indicator.strip().upper()
    if not candidate or len(candidate) > 30 or any(c.isspace() for c in candidate):
        raise ValueError(
            f"'{indicator}' is not a known macro alias or a valid FRED series ID. "
            f"Use an alias (e.g. 'cpi', 'unemployment', '10y_treasury') or a raw "
            f"FRED series ID (e.g. 'CPIAUCSL')."
        )
    return candidate


def _request(path: str, params: dict) -> dict:
    """GET a FRED endpoint, surfacing FRED's JSON error body on a bad request."""
    api_params = {**params, "api_key": get_api_key(), "file_type": "json"}
    response = requests.get(
        f"{FRED_API_BASE}/{path}", params=api_params, timeout=REQUEST_TIMEOUT
    )
    if response.status_code == 400:
        try:
            message = response.json().get("error_message", response.text)
        except ValueError:
            message = response.text
        raise ValueError(f"FRED request failed: {message}")
    response.raise_for_status()
    return response.json()


def render_series_block(
    *,
    title: str,
    series_id: str,
    units: str,
    frequency: str,
    seasonal: str,
    start_date: str,
    curr_date: str,
    points: list[tuple[str, str]],
) -> str:
    """Render one series' observations (date, value) as a markdown block."""
    lines = [
        f"### {title} ({series_id})",
        f"- Units: {units}",
        f"- Frequency: {frequency}" + (f" ({seasonal})" if seasonal else ""),
        f"- Window: {start_date} to {curr_date}",
    ]
    if not points:
        lines.append(
            f"\nNo observations for {series_id} in this window. The series may "
            f"report less frequently than the window length."
        )
        return "\n".join(lines)

    first_date, first_val = points[0]
    last_date, last_val = points[-1]
    try:
        delta = float(last_val) - float(first_val)
        base = float(first_val)
        pct = f" ({delta / base * 100:+.2f}%)" if base != 0 else ""
        summary = (
            f"\n**Latest:** {last_val} ({last_date}) | "
            f"**Change over window:** {delta:+.2f}{pct} "
            f"from {first_val} ({first_date})\n"
        )
    except ValueError:
        summary = f"\n**Latest:** {last_val} ({last_date})\n"

    shown = points
    note = ""
    if len(points) > MAX_ROWS:
        shown = points[-MAX_ROWS:]
        note = f"\n_(showing the most recent {MAX_ROWS} of {len(points)} observations)_\n"

    table = (
        "\n| Date | Value |\n| --- | --- |\n"
        + "\n".join(f"| {d} | {v} |" for d, v in shown)
        + "\n"
    )
    return "\n".join(lines) + "\n" + summary + note + table


def fetch_series(indicator: str, curr_date: str, look_back_days: int) -> str:
    """Fetch one FRED series as a markdown block; degraded on any failure."""
    try:
        series_id = resolve_series_id(indicator)
    except ValueError as e:
        return f"### {indicator}\nFRED: {e}\n"

    end_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    start_date = (end_dt - timedelta(days=look_back_days)).strftime("%Y-%m-%d")

    try:
        meta = _request("series", {"series_id": series_id}).get("seriess") or []
        info = meta[0]
        title = info.get("title", series_id)
        units = info.get("units_short") or info.get("units", "")
        frequency = info.get("frequency", "")
        seasonal = info.get("seasonal_adjustment_short", "")

        observations = _request(
            "series/observations",
            {
                "series_id": series_id,
                "observation_start": start_date,
                "observation_end": curr_date,
                "sort_order": "asc",
            },
        ).get("observations", [])
    except (requests.RequestException, ValueError, IndexError) as exc:
        logger.warning("FRED fetch failed for %s: %s", indicator, exc)
        return f"### {indicator} ({series_id})\n<macro data unavailable: {type(exc).__name__}>\n"

    # FRED encodes a missing observation as ".".
    points = [
        (o["date"], o["value"])
        for o in observations
        if o.get("value") not in (".", None, "")
    ]

    return render_series_block(
        title=title,
        series_id=series_id,
        units=units,
        frequency=frequency,
        seasonal=seasonal,
        start_date=start_date,
        curr_date=curr_date,
        points=points,
    )


def fetch_macro_report(
    curr_date: str,
    indicators: list[str] | None = None,
    look_back_days: int = DEFAULT_LOOKBACK_DAYS,
) -> str:
    """Fetch the configured set of FRED series into one ``macro_indicators.txt`` block.

    Each series degrades independently (placeholder per series), so a single
    failed series never blanks the whole block. Returns a global placeholder
    only when FRED is entirely unusable (no API key).
    """
    if indicators is None:
        indicators = DEFAULT_INDICATORS

    try:
        get_api_key()
    except ValueError as exc:
        logger.warning("FRED unavailable: %s", exc)
        return (
            f"## FRED Macro Indicators ({curr_date})\n"
            f"<macro data unavailable: {exc} — macro indicators not rated>"
        )

    blocks = [f"## FRED Macro Indicators ({curr_date})\n"]
    for indicator in indicators:
        blocks.append(fetch_series(indicator, curr_date, look_back_days))
    return "\n\n".join(blocks)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch FRED macro indicators and print a macro_indicators.txt block"
    )
    parser.add_argument("analysis_date", help="Analysis date in YYYY-MM-DD")
    parser.add_argument("--lookback-days", type=int, default=DEFAULT_LOOKBACK_DAYS)
    args = parser.parse_args()

    print(fetch_macro_report(args.analysis_date, look_back_days=args.lookback_days))


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    main()
