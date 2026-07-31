#!/usr/bin/env python3
"""Build point-in-time valuation and GAAP operating-profit audit metrics."""

from __future__ import annotations

import argparse
import csv
import io
import math
from pathlib import Path
from typing import Any


AUDIT_HEADING = "## Point-in-Time Valuation and GAAP Operating Profit Audit"


def _parse_number(value: str | None) -> float | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        number = float(value)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def _parse_fundamentals(text: str) -> dict[str, float]:
    values: dict[str, float] = {}
    for line in text.splitlines():
        if ":" not in line or line.startswith("#"):
            continue
        label, raw_value = line.split(":", 1)
        number = _parse_number(raw_value)
        if number is not None:
            values[label.strip()] = number
    return values


def _parse_statement(text: str) -> tuple[list[str], dict[str, list[str]]]:
    data_lines = [
        line for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not data_lines:
        return [], {}

    rows = list(csv.reader(io.StringIO("\n".join(data_lines))))
    if not rows:
        return [], {}

    periods = [value.strip() for value in rows[0][1:]]
    values: dict[str, list[str]] = {}
    for row in rows[1:]:
        if row:
            values[row[0].strip()] = row[1:]
    return periods, values


def _statement_value(
    periods: list[str],
    rows: dict[str, list[str]],
    label: str,
    period: str,
) -> float | None:
    try:
        period_index = periods.index(period)
    except ValueError:
        return None
    row = rows.get(label)
    if row is None or period_index >= len(row):
        return None
    return _parse_number(row[period_index])


def _latest_close(ohlcv_text: str) -> tuple[str | None, float | None]:
    data_lines = [
        line for line in ohlcv_text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not data_lines:
        return None, None

    latest_date: str | None = None
    latest_value: float | None = None
    for row in csv.DictReader(io.StringIO("\n".join(data_lines))):
        close = _parse_number(row.get("Close"))
        date = (row.get("Date") or "").strip()
        if close is not None and date and (latest_date is None or date > latest_date):
            latest_date = date
            latest_value = close
    return latest_date, latest_value


def compute_point_in_time_metrics(
    fundamentals_text: str,
    balance_sheet_text: str,
    income_stmt_text: str,
    ohlcv_text: str,
) -> dict[str, Any]:
    """Compute valuation and operating-profit metrics from aligned local inputs."""
    fundamentals = _parse_fundamentals(fundamentals_text)
    balance_periods, balance_rows = _parse_statement(balance_sheet_text)
    income_periods, income_rows = _parse_statement(income_stmt_text)
    price_date, current_price = _latest_close(ohlcv_text)

    common_periods = [period for period in balance_periods if period in income_periods]
    financial_period = max(common_periods) if common_periods else None
    result: dict[str, Any] = {
        "price_date": price_date,
        "financial_period": financial_period,
        "current_price": current_price,
    }
    if financial_period is None:
        result["status"] = "partial"
        result["warnings"] = ["No common balance-sheet and income-statement period."]
        return result

    def balance(label: str) -> float | None:
        return _statement_value(
            balance_periods, balance_rows, label, financial_period
        )

    def income(label: str) -> float | None:
        return _statement_value(income_periods, income_rows, label, financial_period)

    shares = balance("Ordinary Shares Number")
    common_equity = balance("Common Stock Equity")
    total_debt = balance("Total Debt")
    cash_and_investments = balance(
        "Cash Cash Equivalents And Short Term Investments"
    )
    provider_ttm_ebitda = fundamentals.get("EBITDA")
    total_revenue = income("Total Revenue")
    reported_operating_income = income("Total Operating Income As Reported")
    derived_operating_income = income("Operating Income")
    restructuring = income("Restructuring And Mergern Acquisition")
    other_special_charges = income("Other Special Charges")

    point_in_time_market_cap = (
        current_price * shares
        if current_price is not None and shares not in (None, 0)
        else None
    )
    book_value_per_share = (
        common_equity / shares
        if common_equity is not None and shares not in (None, 0)
        else None
    )
    price_to_book = (
        current_price / book_value_per_share
        if current_price is not None and book_value_per_share not in (None, 0)
        else None
    )
    enterprise_value = (
        point_in_time_market_cap + total_debt - cash_and_investments
        if point_in_time_market_cap is not None
        and total_debt is not None
        and cash_and_investments is not None
        else None
    )
    ev_to_ebitda = (
        enterprise_value / provider_ttm_ebitda
        if enterprise_value is not None and provider_ttm_ebitda not in (None, 0)
        else None
    )
    reported_operating_margin = (
        reported_operating_income / total_revenue
        if reported_operating_income is not None and total_revenue not in (None, 0)
        else None
    )
    operating_income_gap = (
        derived_operating_income - reported_operating_income
        if derived_operating_income is not None
        and reported_operating_income is not None
        else None
    )
    identified_operating_adjustments = (
        restructuring + other_special_charges
        if restructuring is not None and other_special_charges is not None
        else None
    )
    operating_adjustment_residual = (
        operating_income_gap - identified_operating_adjustments
        if operating_income_gap is not None
        and identified_operating_adjustments is not None
        else None
    )

    result.update({
        "ordinary_shares": shares,
        "common_stock_equity": common_equity,
        "point_in_time_market_cap": point_in_time_market_cap,
        "book_value_per_share": book_value_per_share,
        "price_to_book": price_to_book,
        "total_debt": total_debt,
        "cash_and_short_term_investments": cash_and_investments,
        "simplified_enterprise_value": enterprise_value,
        "provider_ttm_ebitda": provider_ttm_ebitda,
        "ev_to_provider_ttm_ebitda": ev_to_ebitda,
        "total_revenue": total_revenue,
        "gaap_operating_income_as_reported": reported_operating_income,
        "gaap_operating_margin": reported_operating_margin,
        "derived_operating_income_before_reported_adjustments": (
            derived_operating_income
        ),
        "operating_income_reconciliation_gap": operating_income_gap,
        "restructuring_and_merger_acquisition": restructuring,
        "other_special_charges": other_special_charges,
        "identified_operating_adjustments": identified_operating_adjustments,
        "operating_adjustment_residual": operating_adjustment_residual,
    })

    required = (
        current_price,
        shares,
        common_equity,
        point_in_time_market_cap,
        book_value_per_share,
        price_to_book,
        enterprise_value,
        provider_ttm_ebitda,
        ev_to_ebitda,
        total_revenue,
        reported_operating_income,
        reported_operating_margin,
    )
    result["status"] = "complete" if all(v is not None for v in required) else "partial"
    result["warnings"] = []
    if reported_operating_income is None and derived_operating_income is not None:
        result["warnings"].append(
            "GAAP 'Total Operating Income As Reported' is unavailable; "
            "do not relabel derived 'Operating Income' as GAAP."
        )
    return result


def _amount(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.0f}"


def _ratio(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.4f}"


def render_audit(metrics: dict[str, Any]) -> str:
    """Render an analyst-readable audit section for fundamentals.txt."""
    lines = [
        AUDIT_HEADING,
        "",
        "This section is computed from the latest valid OHLCV close and the "
        "latest common fiscal period in the quarterly statements.",
        f"Audit Status: {metrics.get('status', 'partial')}",
        f"Price Date: {metrics.get('price_date') or 'N/A'}",
        f"Financial Statement Period: {metrics.get('financial_period') or 'N/A'}",
        f"Current Price: {_ratio(metrics.get('current_price'))}",
        f"Ordinary Shares: {_amount(metrics.get('ordinary_shares'))}",
        f"Common Stock Equity: {_amount(metrics.get('common_stock_equity'))}",
        "Point-in-Time Market Cap: "
        f"{_amount(metrics.get('point_in_time_market_cap'))}",
        f"Book Value Per Share: {_ratio(metrics.get('book_value_per_share'))}",
        f"Point-in-Time Price to Book: {_ratio(metrics.get('price_to_book'))}",
        f"Total Debt: {_amount(metrics.get('total_debt'))}",
        "Cash and Short-Term Investments: "
        f"{_amount(metrics.get('cash_and_short_term_investments'))}",
        "Simplified Enterprise Value: "
        f"{_amount(metrics.get('simplified_enterprise_value'))}",
        f"Provider TTM EBITDA: {_amount(metrics.get('provider_ttm_ebitda'))}",
        "Point-in-Time EV / Provider TTM EBITDA: "
        f"{_ratio(metrics.get('ev_to_provider_ttm_ebitda'))}",
        f"Quarterly Total Revenue: {_amount(metrics.get('total_revenue'))}",
        "GAAP Operating Income As Reported: "
        f"{_amount(metrics.get('gaap_operating_income_as_reported'))}",
        f"GAAP Operating Margin: {_ratio(metrics.get('gaap_operating_margin'))}",
        "Derived Operating Income Before Reported Adjustments: "
        f"{_amount(metrics.get('derived_operating_income_before_reported_adjustments'))}",
        "Operating Income Reconciliation Gap: "
        f"{_amount(metrics.get('operating_income_reconciliation_gap'))}",
        "Restructuring and Merger/Acquisition: "
        f"{_amount(metrics.get('restructuring_and_merger_acquisition'))}",
        f"Other Special Charges: {_amount(metrics.get('other_special_charges'))}",
        "Identified Operating Adjustments: "
        f"{_amount(metrics.get('identified_operating_adjustments'))}",
        "Operating Adjustment Residual: "
        f"{_amount(metrics.get('operating_adjustment_residual'))}",
        "",
        "Use Rules:",
        "- Prefer this point-in-time market cap, book value per share, and P/B "
        "over the provider snapshot fields above.",
        "- EV/EBITDA must use Simplified Enterprise Value divided by Provider "
        "TTM EBITDA; keep both numerator and denominator in the same base currency.",
        "- Use GAAP Operating Income As Reported for GAAP operating-profit and "
        "margin claims. The derived Operating Income field is not a substitute.",
    ]
    for warning in metrics.get("warnings", []):
        lines.append(f"- WARNING: {warning}")
    return "\n".join(lines)


def append_audit(
    fundamentals_text: str,
    balance_sheet_text: str,
    income_stmt_text: str,
    ohlcv_text: str,
) -> str:
    """Replace any existing audit section and append a freshly computed one."""
    base = fundamentals_text.split(AUDIT_HEADING, 1)[0].rstrip()
    metrics = compute_point_in_time_metrics(
        fundamentals_text, balance_sheet_text, income_stmt_text, ohlcv_text
    )
    return f"{base}\n\n{render_audit(metrics)}\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Append point-in-time valuation and GAAP profit audit"
    )
    parser.add_argument("--fundamentals", required=True)
    parser.add_argument("--balance-sheet", required=True)
    parser.add_argument("--income-statement", required=True)
    parser.add_argument("--ohlcv", required=True)
    args = parser.parse_args()

    fundamentals_path = Path(args.fundamentals)
    updated = append_audit(
        fundamentals_path.read_text(),
        Path(args.balance_sheet).read_text(),
        Path(args.income_statement).read_text(),
        Path(args.ohlcv).read_text(),
    )
    fundamentals_path.write_text(updated)


if __name__ == "__main__":
    main()
