#!/usr/bin/env python3
"""
Stock data fetcher for TradingAgents skill.
Fetches all required data for a given ticker and date via yfinance + stockstats.

Usage:
    python fetch_data.py <TICKER> <EXECUTION_DATE> [--output-dir <dir>]
    python fetch_data.py <TICKER> <DATE> --ticker-data-dir <dir>
    python fetch_data.py <TICKER> <EXECUTION_DATE> --analysis-mode historical_replay --as-of-date <DATE>

Example:
    python fetch_data.py AAPL <TODAY>
    python fetch_data.py AAPL <TODAY> --analysis-mode historical_replay --as-of-date 2024-01-10

Output:
    {output_dir}/{TICKER}/{DATE}/
        ohlcv.csv           # OHLCV price data for the configured lookback
        price_context.toon  # 1/5/20-session absolute/relative returns
        expectations.txt    # Earnings surprise and analyst-expectation context
        indicators.txt      # All technical indicators
        news.txt            # Company-specific news (strict 60-day window)
        global_news.txt     # Macro/global news
        fundamentals.txt    # Company fundamentals overview
        balance_sheet.csv   # Balance sheet
        cashflow.csv        # Cash flow statement
        income_stmt.csv     # Income statement
        insider.txt         # Insider transactions
        options.txt         # Options flow (put/call ratios, IV skew; US only)
        macro_indicators.txt # FRED macro series (rates, inflation, labor)
        prediction_markets.txt # Polymarket event probabilities
        official_filings.toon  # Official filing discovery evidence
        official_companyfacts.toon # SEC raw Company Facts when available
        official_financials.toon # Unified official facts and fail-closed status
        validated_metrics.toon # Typed numeric contract consumed by analysts
        summary.toon        # Metadata summary

    With --ticker-data-dir:
    {ticker_data_dir}/{DATE}/
"""

import argparse
import os
import sys
import time
from datetime import datetime, timedelta

from output_layout import resolve_ticker_paths

import pandas as pd
import yfinance as yf
from stockstats import wrap

from news_filter import (
    dedup_by_title,
    filter_by_date_window,
    filter_noise,
    render_news_evidence,
    split_recent_and_history,
)
from longbridge_fetcher import (fetch_range_klines, fetch_revenue_sankey,
                                get_revenue_sankey_metadata,
                                parse_range_klines, parse_revenue_sankey)
from financial_audit import append_audit, compute_point_in_time_metrics
from options_flow import fetch_options_report
from macro_data import fetch_macro_report
from prediction_markets import fetch_prediction_markets
from price_attribution_data import fetch_attribution_context
from reddit import fetch_reddit_posts
from stocktwits import fetch_stocktwits_messages
from data_validation import (
    build_validated_metrics,
    fetch_fx_rate,
    fetch_provider_snapshot,
    render_validation_report,
)
from official_filings import fetch_official_filings
from official_financials import fetch_official_financials
from provider_runtime import (
    RetryPolicy,
    clear_retry_events,
    get_retry_events,
    retry_call,
)
from structured_io import read_structured_file, write_structured_file
from temporal_policy import (
    CURRENT_RESEARCH,
    FINANCIAL_LOOKBACK_DAYS,
    HISTORICAL_REPLAY,
    filter_historical_news,
    historical_provider_snapshot,
    not_rated_text,
    resolve_temporal_context,
)

# Look-back windows
PRICE_LOOKBACK_DAYS = 350  # ~230+ trading days, comfortable margin for 200 SMA
NEWS_LOOKBACK_DAYS = 60

# Supported technical indicators (matching the original catalog)
INDICATORS = [
    "close_50_sma",
    "close_200_sma",
    "close_10_ema",
    "macd",
    "macds",
    "macdh",
    "rsi",
    "boll",
    "boll_ub",
    "boll_lb",
    "atr",
    "vwma",
    "mfi",
]


def detect_market(ticker: str) -> str:
    """Detect market from ticker suffix.

    Note: HK stock codes use 5 digits, typically with leading zeros
    (e.g., 00700.HK, 02097.HK). Leading zeros are meaningful and MUST
    be preserved for ALL APIs (yfinance, Sina Finance).
    """
    upper = ticker.upper()
    if ".HK" in upper:
        return "HK"
    if ".SH" in upper or ".SS" in upper or ".SZ" in upper or ".BJ" in upper:
        return "CN"
    if upper.replace(".", "").isdigit():
        if len(upper.split(".")[0]) == 6:
            return "CN"
        return "HK"
    return "US"


def normalize_ticker(ticker: str) -> str:
    """Normalize ticker for yfinance.

    Note on HK stocks: yfinance is inconsistent with HK ticker formats.
    Some stocks require leading zeros (00700.HK, 00005.HK), others
    require stripped codes (3690.HK not 03690.HK). resolve_ticker()
    handles this by testing both formats before fetching data.
    """
    upper = ticker.upper()
    # Convert .SH (Chinese convention for Shanghai) to .SS (yfinance format)
    if ".SH" in upper:
        return upper.replace(".SH", ".SS")
    # .SS and .SZ are already correct yfinance formats
    return upper


def resolve_hk_ticker(ticker: str) -> str:
    """Resolve the correct yfinance ticker for HK stocks by testing all variants.

    yfinance's HK ticker database is inconsistent:
    - 00700.HK ✅ but 700.HK ❌ (Tencent)
    - 3690.HK ✅ but 03690.HK ❌ (Meituan)
    - 00005.HK ✅ but 5.HK ❌ (HSBC)

    Iterates all intermediate zero-stripped variants (via _hk_ticker_variants),
    tests each with info, and returns the variant with the richest info response.
    """
    if ".HK" not in ticker.upper():
        return normalize_ticker(ticker)

    best_ticker = ticker
    best_keys = 0
    for variant in _hk_ticker_variants(ticker):
        try:
            t = yf.Ticker(variant)
            info = retry(lambda: t.info)
            if info and len(info) > best_keys:
                best_keys = len(info)
                best_ticker = variant
        except Exception:
            continue

    return best_ticker


def retry(func, max_retries=4, delay=1):
    """Compatibility wrapper backed by classified exponential retries."""
    return retry_call(
        func,
        provider="yfinance",
        operation="legacy_call",
        policy=RetryPolicy(
            max_attempts=max_retries,
            base_delay_seconds=delay,
            max_delay_seconds=max(delay, 8),
        ),
    )


def _hk_ticker_variants(ticker: str) -> list:
    """生成港股 ticker 逐次去掉一个前置零的变体列表。

    yfinance 各 API 端点对港股 ticker 格式敏感：
    例 00005.HK info 正常但 get_news() 返回 0 条，0005.HK 则正常。
    生成所有中间格式，用于自动重试。

    03690 -> [03690.HK, 3690.HK]
    00700 -> [00700.HK, 0700.HK, 700.HK]
    00005 -> [00005.HK, 0005.HK, 005.HK, 05.HK, 5.HK]
    """
    code = ticker.upper().split(".")[0]
    variants = []
    for i in range(len(code)):
        vc = code[i:]
        if not vc:
            continue
        variants.append(f"{vc}.HK")
        if vc[0] != "0":
            break
    return variants


def _yf_hk_call(ticker: str, call_fn):
    """对港股 ticker 的 yfinance API 调用进行前置零切割重试。

    依次尝试 ticker 变体，返回第一个非空结果。
    避免因 yfinance 端点对 ticker 格式不一致导致 LLM 重复调用。

    Args:
        ticker: 港股 ticker（如 00005.HK）
        call_fn: callable，接受 ticker 变体字符串，返回 API 结果
    """
    for variant in _hk_ticker_variants(ticker):
        try:
            result = call_fn(variant)
            if result is None:
                continue
            if isinstance(result, dict) and len(result) <= 1:
                continue
            if hasattr(result, "empty") and result.empty:
                continue
            if isinstance(result, (list, tuple)) and len(result) == 0:
                continue
            return result
        except Exception:
            continue
    return None


def _latest_expected_weekday(end_date: str) -> pd.Timestamp:
    """返回分析日当天，周末则返回此前最近的工作日。"""
    expected = pd.Timestamp(end_date).normalize()
    while expected.weekday() >= 5:
        expected -= pd.Timedelta(days=1)
    return expected


def _normalize_price_index(data: pd.DataFrame) -> pd.DataFrame:
    """将行情索引统一成无时区的日粒度 DatetimeIndex。"""
    if data is None or data.empty:
        return pd.DataFrame()
    normalized = data.copy()
    index = pd.to_datetime(normalized.index)
    if index.tz is not None:
        index = index.tz_localize(None)
    index = index.normalize()
    normalized.index = index
    normalized.index.name = "Date"
    return normalized[~normalized.index.duplicated(keep="last")].sort_index()


def fetch_price_data(ticker: str, start_date: str, end_date: str,
                     market: str = None) -> tuple:
    """优先获取 yfinance 行情，缺少最新交易日时用长桥补全。"""
    symbol = normalize_ticker(ticker)
    if market is None:
        market = detect_market(ticker)

    # yfinance 的 end 为开区间；加一天才能包含分析日当天。
    yf_end = (pd.Timestamp(end_date) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    try:
        if market == "HK":
            data = _yf_hk_call(
                ticker,
                lambda v: retry(
                    lambda: yf.Ticker(v).history(start=start_date, end=yf_end)
                ),
            )
        else:
            data = retry(
                lambda: yf.Ticker(symbol).history(start=start_date, end=yf_end)
            )
    except Exception as e:
        print(f"  [yfinance OHLCV] error: {e}", file=sys.stderr)
        data = None

    data = _normalize_price_index(data)
    expected_date = _latest_expected_weekday(end_date)
    yf_latest = data.index.max() if not data.empty else None
    source = "yfinance"

    if yf_latest is None or yf_latest < expected_date:
        payload = fetch_range_klines(ticker, market)
        records = parse_range_klines(payload, market)
        fallback = pd.DataFrame.from_records(records)
        if not fallback.empty:
            fallback["Date"] = pd.to_datetime(fallback["Date"])
            fallback = fallback.set_index("Date")
            fallback = _normalize_price_index(fallback)
            start = pd.Timestamp(start_date)
            end = pd.Timestamp(end_date)
            fallback = fallback[(fallback.index >= start) & (fallback.index <= end)]

            lb_latest = fallback.index.max() if not fallback.empty else None
            if lb_latest is not None and (yf_latest is None or lb_latest > yf_latest):
                # 同日记录以主数据源 yfinance 为准，只追加其缺失日期。
                missing = fallback.index.difference(data.index)
                volume_unavailable = (
                    market == "CN"
                    and "Volume" in fallback.columns
                    and fallback.loc[missing, "Volume"].isna().any()
                )
                data = pd.concat([data, fallback.loc[missing]]).sort_index()
                source = (
                    "yfinance + Longbridge fallback"
                    if yf_latest is not None
                    else "Longbridge fallback"
                )
                if volume_unavailable:
                    source += "; CN Longbridge volume Not Rated"

    return data, source


def fetch_ohlcv(ticker: str, start_date: str, end_date: str,
                 market: str = None, quote_currency: str | None = None) -> str:
    """Fetch OHLCV data and return as CSV string."""
    symbol = normalize_ticker(ticker)
    if market is None:
        market = detect_market(ticker)

    data, source = fetch_price_data(ticker, start_date, end_date, market)
    if data.empty:
        return f"# No OHLCV data found for {ticker}\n"

    for col in ["Open", "High", "Low", "Close", "Adj Close"]:
        if col in data.columns:
            data[col] = data[col].round(2)

    currency = quote_currency or "UNKNOWN"

    header = (
        f"# Stock data for {symbol} from {start_date} to {end_date}\n"
        f"# Market: {market}\n"
        f"# Currency: {currency}\n"
        f"# Price source: {source}\n"
        f"# Total records: {len(data)}\n\n"
    )
    return header + data.to_csv()


def fetch_indicators(ticker: str, curr_date: str, lookback_days: int = 30,
                      market: str = None) -> str:
    """Fetch technical indicators via stockstats."""
    symbol = normalize_ticker(ticker)
    if market is None:
        market = detect_market(ticker)
    curr_date_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    start_date = (curr_date_dt - timedelta(days=PRICE_LOOKBACK_DAYS)).strftime("%Y-%m-%d")

    data, _ = fetch_price_data(ticker, start_date, curr_date, market)
    if data.empty:
        return "# No price data available for indicators\n"

    # Prepare data for stockstats
    df = data.reset_index()
    df.columns = [c.lower().replace(" ", "_") for c in df.columns]
    column_map = {
        "date": "Date", "open": "Open", "high": "High",
        "low": "Low", "close": "Close", "volume": "Volume",
    }
    # Handle Adj Close column
    for col in df.columns:
        if "adj" in col.lower() and "close" in col.lower():
            column_map[col] = "Adj Close"
            break

    df_renamed = df.rename(columns=column_map)
    df_renamed["Date"] = pd.to_datetime(df_renamed["Date"])

    try:
        stock_df = wrap(df_renamed)
    except Exception as e:
        return f"# Error computing indicators: {e}\n"

    # Build result for the lookback window
    start_window = curr_date_dt - timedelta(days=lookback_days)
    result_lines = [f"## Technical Indicators for {symbol} ({start_window.strftime('%Y-%m-%d')} to {curr_date})\n"]

    for indicator in INDICATORS:
        result_lines.append(f"\n### {indicator}")
        try:
            stock_df[indicator]  # trigger computation
            indicator_data = stock_df[["Date", indicator]].dropna(subset=[indicator])
            indicator_data = indicator_data[indicator_data["Date"] >= pd.Timestamp(start_window)]

            if indicator_data.empty:
                result_lines.append("  No data available for this period.")
                continue

            for _, row in indicator_data.iterrows():
                date_str = row["Date"].strftime("%Y-%m-%d") if hasattr(row["Date"], "strftime") else str(row["Date"])
                val = row[indicator]
                val_str = f"{val:.4f}" if isinstance(val, float) and not pd.isna(val) else str(val)
                result_lines.append(f"  {date_str}: {val_str}")
        except Exception as e:
            result_lines.append(f"  Error: {e}")

    return "\n".join(result_lines)


def fetch_news(ticker: str, start_date: str, end_date: str) -> str:
    """Fetch company-specific news via yfinance."""
    symbol = normalize_ticker(ticker)
    try:
        stock = yf.Ticker(symbol)
        news = retry(lambda: stock.get_news(count=20))

        if not news:
            return f"# No news found for {ticker}\n"

        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        lines = [f"## {ticker} News ({start_date} to {end_date})\n"]
        count = 0

        for article in news:
            content = article.get("content", article)
            title = content.get("title", article.get("title", "No title"))
            summary = content.get("summary", article.get("summary", ""))
            provider = content.get("provider", {}).get("displayName", article.get("publisher", "Unknown"))
            url_obj = content.get("canonicalUrl") or content.get("clickThroughUrl") or {}
            link = url_obj.get("url", article.get("link", ""))
            pub_date_str = content.get("pubDate", "")

            # Filter by date
            if pub_date_str:
                try:
                    pub_date = datetime.fromisoformat(pub_date_str.replace("Z", "+00:00"))
                    pub_date_naive = pub_date.replace(tzinfo=None)
                    if not (start_dt <= pub_date_naive <= end_dt + timedelta(days=1)):
                        continue
                except (ValueError, AttributeError):
                    pass

            lines.append(f"### {title} (source: {provider})")
            if summary:
                lines.append(f"{summary}")
            if link:
                lines.append(f"Link: {link}")
            lines.append("")
            count += 1

        if count == 0:
            return f"# No news found for {ticker} in date range\n"
        return "\n".join(lines)

    except Exception as e:
        return f"# Error fetching news for {ticker}: {e}\n"


def fetch_global_news(curr_date: str, lookback_days: int = 7, limit: int = 10) -> str:
    """Fetch global macro news via yfinance Search."""
    search_queries = [
        "stock market economy",
        "Federal Reserve interest rates",
        "inflation economic outlook",
        "global markets trading",
    ]

    all_news = []
    seen_titles = set()

    try:
        for query in search_queries:
            search = retry(lambda q=query: yf.Search(query=q, news_count=limit, enable_fuzzy_query=True))
            if search.news:
                for article in search.news:
                    content = article.get("content", article)
                    title = content.get("title", article.get("title", ""))
                    if title and title not in seen_titles:
                        seen_titles.add(title)
                        all_news.append(article)
            if len(all_news) >= limit:
                break

        if not all_news:
            return f"# No global news found for {curr_date}\n"

        curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
        start_date = (curr_dt - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

        lines = [f"## Global Market News ({start_date} to {curr_date})\n"]

        for article in all_news[:limit]:
            content = article.get("content", article)
            title = content.get("title", article.get("title", "No title"))
            provider = content.get("provider", {}).get("displayName", article.get("publisher", "Unknown"))
            url_obj = content.get("canonicalUrl") or content.get("clickThroughUrl") or {}
            link = url_obj.get("url", article.get("link", ""))
            summary = content.get("summary", article.get("summary", ""))

            lines.append(f"### {title} (source: {provider})")
            if summary:
                lines.append(f"{summary}")
            if link:
                lines.append(f"Link: {link}")
            lines.append("")

        return "\n".join(lines)

    except Exception as e:
        return f"# Error fetching global news: {e}\n"


def fetch_fundamentals(ticker: str, market: str = None) -> str:
    """Fetch company fundamentals from yfinance."""
    symbol = normalize_ticker(ticker)
    if market is None:
        market = detect_market(ticker)
    try:
        if market == "HK":
            info = _yf_hk_call(ticker, lambda v: retry(lambda: yf.Ticker(v).info))
        else:
            stock = yf.Ticker(symbol)
            info = retry(lambda: stock.info)

        if not info:
            return f"# No fundamentals data found for {ticker}\n"

        fields = [
            ("Name", "longName"),
            ("Sector", "sector"),
            ("Industry", "industry"),
            ("Market Cap", "marketCap"),
            ("PE Ratio (TTM)", "trailingPE"),
            ("Forward PE", "forwardPE"),
            ("PEG Ratio", "pegRatio"),
            ("Price to Book", "priceToBook"),
            ("EPS (TTM)", "trailingEps"),
            ("Forward EPS", "forwardEps"),
            ("Dividend Yield", "dividendYield"),
            ("Beta", "beta"),
            ("52 Week High", "fiftyTwoWeekHigh"),
            ("52 Week Low", "fiftyTwoWeekLow"),
            ("50 Day Average", "fiftyDayAverage"),
            ("200 Day Average", "twoHundredDayAverage"),
            ("Revenue (TTM)", "totalRevenue"),
            ("Gross Profit", "grossProfits"),
            ("EBITDA", "ebitda"),
            ("Net Income", "netIncomeToCommon"),
            ("Profit Margin", "profitMargins"),
            ("Operating Margin", "operatingMargins"),
            ("Return on Equity", "returnOnEquity"),
            ("Return on Assets", "returnOnAssets"),
            ("Debt to Equity", "debtToEquity"),
            ("Current Ratio", "currentRatio"),
            ("Book Value", "bookValue"),
            ("Free Cash Flow", "freeCashflow"),
        ]

        lines = [f"# Company Fundamentals for {symbol}\n"]
        for label, key in fields:
            value = info.get(key)
            if value is not None:
                lines.append(f"{label}: {value}")

        return "\n".join(lines)

    except Exception as e:
        return f"# Error fetching fundamentals for {ticker}: {e}\n"


def fetch_financial_stmt(ticker: str, stmt_type: str, freq: str = "quarterly",
                         curr_date: str = None, market: str = None) -> str:
    """
    Fetch financial statement (balance_sheet, cashflow, income_stmt) from yfinance.
    Filters data to avoid look-ahead bias using curr_date.
    """
    symbol = normalize_ticker(ticker)
    if market is None:
        market = detect_market(ticker)
    try:
        if freq.lower() == "quarterly":
            attr_map = {
                "balance_sheet": "quarterly_balance_sheet",
                "cashflow": "quarterly_cashflow",
                "income_stmt": "quarterly_income_stmt",
            }
        else:
            attr_map = {
                "balance_sheet": "balance_sheet",
                "cashflow": "cashflow",
                "income_stmt": "income_stmt",
            }

        attr = attr_map.get(stmt_type)
        if attr is None:
            return f"# Unknown statement type: {stmt_type}\n"

        if market == "HK":
            data = _yf_hk_call(
                ticker,
                lambda v: retry(lambda: getattr(yf.Ticker(v), attr)),
            )
        else:
            stock = yf.Ticker(symbol)
            data = retry(lambda: getattr(stock, attr))

        if data is None or (hasattr(data, "empty") and data.empty):
            return f"# No {stmt_type} data found for {ticker}\n"

        # Filter by date to avoid look-ahead bias and retain only recent data.
        if curr_date and not data.empty:
            curr_dt = pd.Timestamp(curr_date)
            window_start = curr_dt - pd.Timedelta(days=FINANCIAL_LOOKBACK_DAYS)
            valid_cols = [
                c for c in data.columns
                if window_start <= pd.Timestamp(c) <= curr_dt
            ]
            data = data[valid_cols]

        if data.empty:
            return f"# No {stmt_type} data available before {curr_date}\n"

        stmt_names = {
            "balance_sheet": "Balance Sheet",
            "cashflow": "Cash Flow",
            "income_stmt": "Income Statement",
        }

        period_note = (
            f"# ⚠️ PERIOD TYPE: {freq.upper()} — Each column is a SINGLE FISCAL QUARTER, NOT a full year.\n"
            f"# To get full-year figures, sum all 4 quarters of the same fiscal year.\n"
            f"# Example: 2025-12-31 column = Q4 2025 (Oct-Dec), NOT FY2025.\n"
        ) if freq.lower() == "quarterly" else ""

        header = f"# {stmt_names.get(stmt_type, stmt_type)} for {symbol} ({freq})\n"
        return period_note + header + data.to_csv()

    except Exception as e:
        return f"# Error fetching {stmt_type} for {ticker}: {e}\n"


def fetch_insider_transactions(ticker: str) -> str:
    """Fetch insider transactions from yfinance."""
    symbol = normalize_ticker(ticker)
    try:
        stock = yf.Ticker(symbol)
        data = retry(lambda: stock.insider_transactions)

        if data is None or data.empty:
            return f"# No insider transactions data found for {ticker}\n"

        header = f"# Insider Transactions for {symbol}\n"
        return header + data.to_csv()

    except Exception as e:
        return f"# Error fetching insider transactions for {ticker}: {e}\n"


def fetch_cn_news(ticker: str, start_date: str, end_date: str) -> str:
    """Fetch A-share market news + official announcements via Sina Finance & Eastmoney.

    Primary source: Sina Finance (新浪财经) for market-level news —
    media coverage, analyst commentary, industry trends mentioning the company.
    Secondary source: Eastmoney (东方财富) for official company filings —
    dividend notices, shareholder meetings, regulatory announcements.

    Note: A-share codes are always 6 digits, no leading zeros.
    HK stock codes may have leading zeros. yfinance's HK ticker database
    is inconsistent — resolve_hk_ticker() handles both formats automatically.
    """
    try:
        import requests
    except ImportError:
        return f"# Error: requests library not available for CN news\n"

    # Extract 6-digit code
    code = ticker.split(".")[0]
    if len(code) != 6 or not code.isdigit():
        return f"# Not a valid A-share code: {ticker}\n"

    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    lines = [f"## {ticker} News ({start_date} to {end_date})\n"]
    total_count = 0

    # --- Source 1: Sina Finance (market news) ---
    try:
        # Determine Sina prefix: sh=Shanghai (6xxxxx), sz=Shenzhen (0xxxxx/3xxxxx)
        first_digit = code[0]
        is_shanghai = first_digit == "6"
        prefix = f"sh{code}" if is_shanghai else f"sz{code}"

        url = f"https://vip.stock.finance.sina.com.cn/corp/go.php/vCB_AllNewsStock/symbol/{prefix}.phtml"
        resp = retry_call(
            lambda: requests.get(
                url, timeout=15, headers={"User-Agent": "Mozilla/5.0"}
            ),
            provider="Sina Finance", operation=f"{ticker}.cn_news",
        )
        resp.encoding = "gb2312"

        # Extract news: DATE&nbsp;TIME&nbsp;&nbsp;<a target='_blank' href='URL'>TITLE</a>
        # Note: &nbsp; is NOT matched by \s, so use (?:&nbsp;|\s)*
        import re
        items = re.findall(
            r"(\d{4}-\d{2}-\d{2})&nbsp;(\d{2}:\d{2})(?:&nbsp;|\s)*<a[^>]*href='([^']*)'[^>]*>([^<]+)</a>",
            resp.text,
        )

        lines.append("### Market News (source: Sina Finance 新浪财经)\n")
        sina_count = 0

        for date_str, time_str, link, title in items:
            title = title.strip()
            if len(title) < 8:
                continue
            try:
                d = datetime.strptime(date_str, "%Y-%m-%d")
                if not (start_dt <= d <= end_dt + timedelta(days=1)):
                    continue
            except ValueError:
                continue

            lines.append(f"**{title}**")
            lines.append(f"  Date: {date_str} {time_str}")
            if link:
                lines.append(f"  Link: {link}")
            lines.append("")
            sina_count += 1

        lines.append(f"  ({sina_count} articles)\n")
        total_count += sina_count
    except Exception as e:
        lines.append(f"### Market News (source: Sina Finance)")
        lines.append(f"  Error: {e}\n")

    # --- Source 2: Eastmoney (official announcements) ---
    try:
        url_em = "https://np-anotice-stock.eastmoney.com/api/security/ann"
        params = {
            "page_size": 20,
            "page_index": 1,
            "ann_type": "A",
            "client_source": "web",
            "stock_list": code,
        }
        resp_em = retry_call(
            lambda: requests.get(url_em, params=params, timeout=15),
            provider="Eastmoney", operation=f"{ticker}.announcements",
        )
        resp_em.raise_for_status()
        data_em = resp_em.json()

        em_items = data_em.get("data", {}).get("list", [])

        lines.append("### Official Announcements (source: Eastmoney 东方财富)\n")
        em_count = 0

        for item in em_items:
            notice_date_str = item.get("notice_date", "")
            title = item.get("title", "No title")
            if notice_date_str:
                try:
                    notice_date = datetime.strptime(notice_date_str.split(" ")[0], "%Y-%m-%d")
                    if not (start_dt <= notice_date <= end_dt + timedelta(days=1)):
                        continue
                except ValueError:
                    pass

            ann_id = item.get("art_code", "")
            lines.append(f"**{title}**")
            lines.append(f"  Date: {notice_date_str}")
            if ann_id:
                lines.append(f"  Link: https://data.eastmoney.com/notices/detail/{code}/{ann_id}.html")
            lines.append("")
            em_count += 1

        lines.append(f"  ({em_count} announcements)\n")
        total_count += em_count
    except Exception as e:
        lines.append(f"### Official Announcements (source: Eastmoney)")
        lines.append(f"  Error: {e}\n")

    if total_count == 0:
        return f"# No news or announcements found for {ticker} in date range\n"
    return "\n".join(lines)


def fetch_hk_news(ticker: str, start_date: str, end_date: str) -> str:
    """Fetch HK stock market news via Sina Finance.

    HK stocks don't have good coverage on yfinance get_news().
    Sina Finance provides HK stock news pages with market-level articles.

    HK stock codes (e.g., 00700.HK, 02097.HK) MUST preserve leading zeros
    for ALL APIs — yfinance needs '00700.HK', Sina needs 'hk00700'.
    Verified 2026-07-13: '700.HK' and 'hk700' both fail to return correct
    stock data/stock-specific news.
    """

    # Keep original 5-digit code with leading zeros
    # e.g., "00700.HK" -> code="00700"
    code = ticker.split(".")[0]

    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    lines = [f"## {ticker} News ({start_date} to {end_date})\n"]
    total_count = 0

    try:
        import requests
    except ImportError:
        return f"# Error: requests library not available for HK news\n"

    # Sina Finance: hk + original 5-digit code with leading zeros (e.g., hk00700)
    # Verified: both yfinance AND Sina require leading zeros for HK stocks.
    try:
        prefix = f"hk{code}"
        url = f"https://vip.stock.finance.sina.com.cn/corp/go.php/vCB_AllNewsStock/symbol/{prefix}.phtml"
        resp = retry_call(
            lambda: requests.get(
                url, timeout=15, headers={"User-Agent": "Mozilla/5.0"}
            ),
            provider="Sina Finance", operation=f"{ticker}.hk_news",
        )
        resp.encoding = "gb2312"

        import re
        items = re.findall(
            r"(\d{4}-\d{2}-\d{2})&nbsp;(\d{2}:\d{2})(?:&nbsp;|\s)*<a[^>]*href='([^']*)'[^>]*>([^<]+)</a>",
            resp.text,
        )

        lines.append("### Market News (source: Sina Finance 新浪财经)\n")
        count = 0
        for date_str, time_str, link, title in items:
            title = title.strip()
            if len(title) < 8:
                continue
            try:
                d = datetime.strptime(date_str, "%Y-%m-%d")
                if not (start_dt <= d <= end_dt + timedelta(days=1)):
                    continue
            except ValueError:
                continue

            lines.append(f"**{title}**")
            lines.append(f"  Date: {date_str} {time_str}")
            if link:
                lines.append(f"  Link: {link}")
            lines.append("")
            count += 1

        lines.append(f"  ({count} articles)\n")
        total_count += count
    except Exception as e:
        lines.append(f"### Market News (source: Sina Finance)")
        lines.append(f"  Error: {e}\n")

    if total_count == 0:
        return f"# No news found for {ticker} in date range\n"
    return "\n".join(lines)


def _sina_fetch_all_pages(prefix: str, start_dt, end_dt, max_pages: int = 20) -> list:
    """翻页抓取新浪 vCB_AllNewsStock，返回原始 article list。

    prefix: 如 hk00700 / sh600519
    终止：抓到日期早于 start_dt，或连续两页无新增，或达 max_pages。
    """
    import re
    import requests
    all_items = []
    empty_streak = 0
    for page in range(1, max_pages + 1):
        url = f"http://vip.stock.finance.sina.com.cn/corp/view/vCB_AllNewsStock.php?symbol={prefix}&Page={page}"
        try:
            resp = retry_call(
                lambda request_url=url: requests.get(
                    request_url,
                    timeout=15,
                    headers={"User-Agent": "Mozilla/5.0"},
                ),
                provider="Sina Finance",
                operation=f"{prefix}.news_page_{page}",
            )
            resp.encoding = "gb2312"
        except Exception as e:
            print(f"  [sina page {page}] error: {e}", flush=True)
            break

        items = re.findall(
            r"(\d{4}-\d{2}-\d{2})&nbsp;(\d{2}:\d{2})(?:&nbsp;|\s)*<a[^>]*href='([^']*)'[^>]*>([^<]+)</a>",
            resp.text,
        )
        if not items:
            empty_streak += 1
            if empty_streak >= 2:
                break
            continue
        empty_streak = 0

        oldest_this_page = None
        for date_str, time_str, link, title in items:
            title = title.strip()
            if len(title) < 8:
                continue
            try:
                d = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                continue
            if oldest_this_page is None or d < oldest_this_page:
                oldest_this_page = d
            all_items.append({
                "title": title,
                "date": f"{date_str} {time_str}",
                "provider": "Sina Finance",
                "link": link,
                "summary": "",
            })

        if oldest_this_page and oldest_this_page < start_dt:
            break
    return all_items


def fetch_hk_news_raw(ticker: str, start_date: str, end_date: str) -> list:
    """抓取 HK 新闻原始列表。优先 yfinance（质量高），不足时降级到新浪财经。

    yfinance 对港股的新闻覆盖质量远优于新浪财经（新浪噪声多，大量不相关文章）。
    当 yfinance 返回 >= 5 条新闻时直接使用 yfinance 结果；否则降级使用新浪财经。
    HK 市场的 yfinance 调用已内置前置零切割重试（_yf_news_to_list）。
    """
    code = ticker.split(".")[0]
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    # 优先使用 yfinance（质量高、噪声少），自动去前置零重试
    yf_items = _yf_news_to_list(ticker, start_date, end_date, market="HK")
    if len(yf_items) >= 5:
        print(f"  [hk news] using yfinance with {len(yf_items)} articles")
        return yf_items
    if yf_items:
        print(f"  [hk news] yfinance returned only {len(yf_items)} articles, supplementing with Sina")
    else:
        print(f"  [hk news] yfinance returned 0 articles, falling back to Sina")

    # 降级：使用新浪财经（合并 yfinance 结果以补充）
    prefix = f"hk{code}"
    sina_items = _sina_fetch_all_pages(prefix, start_dt, end_dt)
    return yf_items + sina_items


def fetch_cn_news_raw(ticker: str, start_date: str, end_date: str) -> list:
    """抓取 CN 新浪市场新闻 + 东方财富公告，返回原始 list。"""
    import re
    import requests
    code = ticker.split(".")[0]
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    items = []

    first_digit = code[0]
    prefix = f"sh{code}" if first_digit == "6" else f"sz{code}"
    items.extend(_sina_fetch_all_pages(prefix, start_dt, end_dt))

    try:
        url_em = "https://np-anotice-stock.eastmoney.com/api/security/ann"
        params = {"page_size": 20, "page_index": 1, "ann_type": "A",
                  "client_source": "web", "stock_list": code}
        resp_em = retry_call(
            lambda: requests.get(url_em, params=params, timeout=15),
            provider="Eastmoney", operation=f"{ticker}.raw_announcements",
        )
        resp_em.raise_for_status()
        for item in resp_em.json().get("data", {}).get("list", []):
            nd = item.get("notice_date", "")
            title = item.get("title", "No title")
            try:
                nd_dt = datetime.strptime(nd.split(" ")[0], "%Y-%m-%d")
                if not (start_dt <= nd_dt <= end_dt + timedelta(days=1)):
                    continue
            except (ValueError, AttributeError):
                pass
            items.append({
                "title": title,
                "date": nd,
                "provider": "Eastmoney",
                "link": f"https://data.eastmoney.com/notices/detail/{code}/{item.get('art_code','')}.html",
                "summary": "",
            })
    except Exception as e:
        print(f"  [eastmoney] error: {e}", flush=True)
    return items


def _yf_news_to_list(ticker: str, start_date: str, end_date: str,
                      market: str = None) -> list:
    """yfinance get_news 转成统一 article list（美股/港股通用，HK 自动去前置零重试）。"""
    if market is None:
        market = detect_market(ticker)
    out = []
    try:
        if market == "HK":
            news = _yf_hk_call(
                ticker,
                lambda v: retry(lambda: yf.Ticker(v).get_news(count=30)),
            )
        else:
            symbol = normalize_ticker(ticker)
            stock = yf.Ticker(symbol)
            news = retry(lambda: stock.get_news(count=30))
        if not news:
            return out
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        for article in news:
            content = article.get("content", article)
            title = content.get("title", "")
            pub_date_str = content.get("pubDate", "")
            provider = content.get("provider", {}).get("displayName", "")
            url_obj = content.get("canonicalUrl") or content.get("clickThroughUrl") or {}
            link = url_obj.get("url", "")
            date_field = ""
            published_at = ""
            if pub_date_str:
                try:
                    parsed_date = datetime.fromisoformat(pub_date_str.replace("Z", "+00:00"))
                    published_at = parsed_date.isoformat()
                    parsed_date_naive = parsed_date.replace(tzinfo=None)
                    if not (start_dt <= parsed_date_naive <= end_dt + timedelta(days=1)):
                        continue
                    date_field = parsed_date_naive.strftime("%Y-%m-%d %H:%M")
                except (ValueError, AttributeError):
                    date_field = pub_date_str
            out.append({"title": title, "date": date_field, "provider": provider,
                        "published_at": published_at,
                        "link": link, "summary": content.get("summary", "")})
    except Exception as e:
        print(f"  [yf news] error: {e}", flush=True)
    return out


def process_and_write_news(raw_items: list, curr_date: str, news_start: str,
                           out_path: str, lookback_days: int = 60,
                           market: str = "US",
                           temporal_excluded: int = 0) -> int:
    """对原始新闻跑去噪+去重，将正文和处理审计合并写入 news.txt。

    返回最终保留条数，并清理同目录下旧版 news_meta.txt，避免留下过期审计副本。

    HK/US 市场（yfinance 新闻，质量高）：先做严格日期窗口过滤，再做
    filter_noise + dedup_by_title，不做分层过滤。

    CN 市场（新浪财经新闻，噪声多）：先做严格日期窗口过滤，再做
    filter_noise -> split_recent_and_history (近7天全留，8-60天仅留高信号)
    -> dedup_by_title。
    """
    raw_count = len(raw_items)
    dated_items, out_of_window_count, missing_date_count = filter_by_date_window(
        raw_items,
        curr_date,
        lookback_days=lookback_days,
    )
    after_noise = filter_noise(dated_items)
    noise_count = len(dated_items) - len(after_noise)

    if market in ("HK", "US"):
        # yfinance 新闻质量高，跳过 split_recent_and_history
        recent = after_noise[:]  # 全部视为 recent
        history = []
        combined = after_noise
    else:
        # CN 市场（新浪），做分层过滤
        recent, history = split_recent_and_history(after_noise, curr_date,
                                                   recent_days=7, lookback_days=lookback_days)
        combined = recent + history

    after_dedup = dedup_by_title(combined)
    dedup_count = len(combined) - len(after_dedup)

    news_text, evidence_stats = render_news_evidence(
        after_dedup, news_start, curr_date
    )
    audit = [
        f"## News Processing Audit ({news_start} to {curr_date})",
        f"market: {market}",
        f"raw_fetched: {raw_count}",
        f"date_window_kept: {len(dated_items)}",
        f"date_window_excluded: {out_of_window_count}",
        f"missing_or_unparseable_publication_time: {missing_date_count}",
        f"after_noise_filter: {len(after_noise)} (removed {noise_count})",
    ]
    if market == "CN":
        audit.extend([
            f"recent_7d_kept: {len(recent)}",
            f"history_8_60d_kept: {len(history)}",
        ])
    else:
        audit.append("split_skipped: HK/US yfinance news, full retention")
    audit.extend([
        f"after_dedup: {len(after_dedup)} (removed {dedup_count})",
        f"final_kept: {len(after_dedup)}",
        f"historical_timestamp_excluded: {temporal_excluded}",
        f"content_level_summary: {evidence_stats['summary']}",
        f"content_level_title_only: {evidence_stats['title_only']}",
        "social_data_available: separate (stocktwits.txt, reddit.txt)",
    ])
    audit_text = "\n".join(audit)
    with open(out_path, "w") as f:
        f.write(f"{news_text}\n\n{audit_text}")

    legacy_meta_path = os.path.join(os.path.dirname(out_path), "news_meta.txt")
    if os.path.exists(legacy_meta_path):
        os.remove(legacy_meta_path)
    return len(after_dedup)


def fetch_cn_global_news(curr_date: str, lookback_days: int = 7) -> str:
    """Fetch Chinese macro/economic news via Baidu economic calendar.

    Provides Chinese economic data releases and policy events relevant
    to A-share market analysis.
    """
    lines = []

    try:
        import akshare as ak

        df = ak.news_economic_baidu(date=curr_date)
        if not df.empty:
            # Filter for China-related events
            cn_events = df[df["地区"] == "中国"]
            lines.append(f"## Chinese Economic Calendar ({curr_date})\n")
            lines.append(f"Source: Baidu Economic Calendar (百度经济日历)\n")
            for _, row in cn_events.iterrows():
                event = row.get("事件", "")
                actual = row.get("公布", "")
                expected = row.get("预期", "")
                previous = row.get("前值", "")
                time_str = row.get("时间", "")
                lines.append(
                    f"- {time_str} | {event}: actual={actual}, "
                    f"expected={expected}, previous={previous}"
                )
            lines.append("")
    except Exception as e:
        lines.append(f"# Note: CN economic calendar unavailable: {e}\n")

    # Also try to get market index news
    try:
        import akshare as ak
        cctv_news = ak.news_cctv(date=curr_date)
        if not cctv_news.empty:
            lines.append(f"## CCTV News Headlines ({curr_date})\n")
            for _, row in cctv_news.head(5).iterrows():
                lines.append(f"- {row.get('title', '')}")
            lines.append("")
    except Exception:
        pass  # CCTV news is optional

    if len(lines) == 0:
        return f"# No Chinese macro news available for {curr_date}\n"

    return "\n".join(lines)


def _latest_close_from_ohlcv(ohlcv_text: str) -> float | None:
    """Parse the latest Close from an ohlcv.csv text block (header comments ignored)."""
    import io

    try:
        df = pd.read_csv(io.StringIO(ohlcv_text), comment="#")
    except Exception:
        return None
    if df.empty or "Close" not in df.columns:
        return None
    close = df["Close"].dropna()
    return float(close.iloc[-1]) if not close.empty else None


def _price_frame_from_ohlcv(ohlcv_text: str) -> pd.DataFrame:
    """Parse the generated OHLCV artifact for attribution calculations."""
    import io

    try:
        frame = pd.read_csv(io.StringIO(ohlcv_text), comment="#", parse_dates=["Date"])
    except Exception:
        return pd.DataFrame()
    if frame.empty or "Date" not in frame.columns or "Close" not in frame.columns:
        return pd.DataFrame()
    return frame.set_index("Date")


def _compute_data_quality(ticker_dir: str, ticker: str, analysis_as_of_date: str,
                          ohlcv_text: str, market: str,
                          execution_date: str | None = None,
                          temporal_context: dict | None = None) -> dict:
    """Compute data quality metadata: trading days, indicator sufficiency, period labels.

    Returns a dict consumed by agents to avoid:
      - computing 200 SMA from <200 data points
      - treating quarterly financials as annual
      - mixing timestamps from different dates
    """
    import re

    execution_date = execution_date or analysis_as_of_date

    # Count trading days from OHLCV
    trading_days = 0
    last_ohlcv_date = None
    for line in ohlcv_text.split("\n"):
        if re.match(r"^\d{4}-\d{2}-\d{2},", line):
            trading_days += 1
            last_ohlcv_date = line.split(",")[0]

    # 周末以此前最近工作日为目标；交易所节假日仍保持保守告警。
    expected_price_date = _latest_expected_weekday(analysis_as_of_date).strftime("%Y-%m-%d")
    data_fresh = (
        last_ohlcv_date == expected_price_date
    ) if last_ohlcv_date else False
    as_of_date = last_ohlcv_date or analysis_as_of_date

    # Indicator sufficiency
    indicator_rules = {
        "close_50_sma": {"min_days": 50, "sufficient": trading_days >= 50},
        "close_200_sma": {"min_days": 200, "sufficient": trading_days >= 200},
        "close_10_ema": {"min_days": 10, "sufficient": trading_days >= 10},
        "macd": {"min_days": 35, "sufficient": trading_days >= 35},
        "rsi": {"min_days": 20, "sufficient": trading_days >= 20},
        "boll": {"min_days": 25, "sufficient": trading_days >= 25},
        "atr": {"min_days": 20, "sufficient": trading_days >= 20},
    }

    # Period labels for financial statements
    period_labels = {
        "income_stmt": "QUARTERLY — each column is a single fiscal quarter, NOT a full year",
        "balance_sheet": "QUARTERLY — each column is a single fiscal quarter-end snapshot",
        "cashflow": "QUARTERLY — each column is a single fiscal quarter",
    }

    quality = {
        "ticker": ticker,
        "market": market,
        "analysis_date": analysis_as_of_date,
        "execution_date": execution_date,
        "analysis_as_of_date": analysis_as_of_date,
        "temporal_context": temporal_context or {},
        "data_as_of_date": as_of_date,
        "expected_price_date": expected_price_date,
        "data_fresh": data_fresh,
        "trading_days": trading_days,
        "warning_no_200_sma": not indicator_rules["close_200_sma"]["sufficient"],
        "indicator_sufficiency": indicator_rules,
        "period_labels": period_labels,
        "notes": [],
    }

    # Build warnings
    if not data_fresh:
        quality["notes"].append(
            f"WARNING: OHLCV data ends at {as_of_date}, not the expected latest "
            f"trading date {expected_price_date}. "
            f"All analysis prices are as-of {as_of_date}. Do NOT use {analysis_as_of_date} prices "
            f"in the same report without explicitly noting the timestamp mismatch."
        )
    if not indicator_rules["close_200_sma"]["sufficient"]:
        quality["notes"].append(
            f"WARNING: Only {trading_days} trading days available. "
            f"200 SMA requires 200+ days. Must output N/A for 200 SMA, "
            f"never substitute 50 SMA value."
        )

    return quality


def _load_valuation_consensus(
    input_path: str,
    *,
    ticker: str,
    analysis_date: str,
    wait_for_explicit: bool = False,
    poll_timeout: float = 300.0,
    poll_interval: float = 2.0,
) -> dict:
    """Read web valuation evidence, waiting for a parallel writer when
    ``--valuation-consensus-file`` was passed explicitly."""
    deadline = time.monotonic() + poll_timeout if wait_for_explicit else None
    while True:
        try:
            candidate = read_structured_file(input_path)
            if isinstance(candidate, dict):
                return candidate
            break  # decoded but not a dict -> unusable
        except FileNotFoundError:
            pass  # may not be written yet by the parallel research sub-agent
        except (ValueError, RuntimeError):
            break  # corrupt or unreadable -> fall back immediately
        if deadline is None or time.monotonic() >= deadline:
            break
        time.sleep(poll_interval)
    return {
        "schema_version": "1.0",
        "ticker": ticker,
        "analysis_date": analysis_date,
        "status": "unavailable",
        "blocking_reasons": ["network_valuation_evidence_not_written"],
        "web_consensus": [],
        "peers": [],
    }


def main():
    parser = argparse.ArgumentParser(description="Fetch stock data for TradingAgents analysis")
    parser.add_argument("ticker", help="Ticker symbol (e.g., AAPL, 600519.SH, 00700.HK)")
    parser.add_argument("date", help="Execution date in YYYY-MM-DD format; must be today's local date")
    parser.add_argument(
        "--analysis-mode",
        choices=(CURRENT_RESEARCH, HISTORICAL_REPLAY),
        default=CURRENT_RESEARCH,
        help="Current research by default; historical replay requires --as-of-date",
    )
    parser.add_argument(
        "--as-of-date",
        default=None,
        help="Historical replay cutoff in YYYY-MM-DD format (market-timezone end of day)",
    )
    parser.add_argument(
        "--valuation-consensus-file",
        default=None,
        help=(
            "Structured web valuation evidence written before data collection; "
            "defaults to DATA_DIR/valuation_consensus when present"
        ),
    )
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument(
        "--output-dir",
        default=None,
        help="Base output directory; appends TICKER/DATE (default: ./data)",
    )
    output_group.add_argument(
        "--ticker-data-dir",
        default=None,
        help="Exact ticker-level data directory; appends DATE only",
    )
    args = parser.parse_args()

    ticker = args.ticker.strip().upper()
    execution_date = args.date.strip()
    clear_retry_events()

    market = detect_market(ticker)
    try:
        temporal_context = resolve_temporal_context(
            execution_date=execution_date,
            analysis_mode=args.analysis_mode,
            as_of_date=args.as_of_date,
            market=market,
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    curr_date = temporal_context["analysis_as_of_date"]
    curr_date_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    historical_replay = args.analysis_mode == HISTORICAL_REPLAY

    # Setup output directory
    output_dir = args.output_dir or os.path.join(
        os.path.dirname(__file__),
        "..",
        "data",
    )
    ticker_root, ticker_dir = resolve_ticker_paths(
        ticker,
        execution_date,
        base_output_dir=output_dir,
        ticker_data_dir=args.ticker_data_dir,
    )
    os.makedirs(ticker_dir, exist_ok=True)

    print(f"Fetching data for {ticker}; execution date {execution_date}, as of {curr_date}...")
    print(f"Output directory: {ticker_dir}")

    # Calculate date ranges
    price_start = (curr_date_dt - timedelta(days=PRICE_LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    news_start = (curr_date_dt - timedelta(days=NEWS_LOOKBACK_DAYS)).strftime("%Y-%m-%d")

    results = {
        "ticker": ticker,
        "date": execution_date,
        "analysis_as_of_date": curr_date,
        "analysis_mode": args.analysis_mode,
        "temporal_context": temporal_context,
        "market": market,
        "output_dir": ticker_dir,
        "files": {},
    }

    # Resolve yfinance ticker for HK stocks (yfinance is inconsistent:
    # 00700.HK works but 03690.HK doesn't; 3690.HK works but 700.HK doesn't)
    if market == "HK" and not historical_replay:
        yf_ticker = resolve_hk_ticker(ticker)
        if yf_ticker != ticker:
            print(f"  Note: resolved HK ticker {ticker} -> {yf_ticker} for yfinance")
    else:
        yf_ticker = normalize_ticker(ticker)

    # Resolve currency and analyst-table semantics before any calculation.
    print("  [0] Fetching instrument metadata and currency context...")
    if historical_replay:
        provider_snapshot = historical_provider_snapshot(
            symbol=normalize_ticker(yf_ticker),
            market=market,
            temporal_context=temporal_context,
        )
    else:
        provider_snapshot = fetch_provider_snapshot(
            normalize_ticker(yf_ticker), curr_date
        )
    quote_currency = provider_snapshot.get("quote_currency")
    financial_currency = provider_snapshot.get("financial_currency")
    fx = (
        {
            "status": "unavailable",
            "reason": "historical replay has no verified point-in-time financial currency snapshot",
        }
        if historical_replay else
        fetch_fx_rate(quote_currency, financial_currency, curr_date)
    )

    metadata_path = write_structured_file(
        os.path.join(ticker_dir, "instrument_metadata"),
        {
            key: value for key, value in provider_snapshot.items()
            if key not in ("info", "analyst_tables")
        },
    )
    results["files"]["instrument_metadata"] = metadata_path
    estimates_path = write_structured_file(
        os.path.join(ticker_dir, "analyst_estimates"),
        {
            "provider": "yfinance",
            "retrieved_at": provider_snapshot.get("retrieved_at"),
            "financial_currency": financial_currency,
            "status": (
                "not_rated_no_verified_point_in_time_snapshot"
                if historical_replay else "available"
            ),
            "tables": provider_snapshot.get("analyst_tables", {}),
        },
    )
    results["files"]["analyst_estimates"] = estimates_path

    # 1. OHLCV
    print("  [1/8] Fetching OHLCV data...")
    ohlcv = fetch_ohlcv(
        yf_ticker, price_start, curr_date, market=market,
        quote_currency=quote_currency,
    )
    path = os.path.join(ticker_dir, "ohlcv.csv")
    with open(path, "w") as f:
        f.write(ohlcv)
    results["files"]["ohlcv"] = path

    # 1a. Relative-performance and expectation context for the second-wave
    # Price Action Attribution Analyst. Each artifact degrades independently;
    # unavailable comparator or consensus evidence remains explicitly Not Rated.
    print("  [1a] Fetching price-attribution context...")
    try:
        price_context, expectations_text = fetch_attribution_context(
            target_symbol=normalize_ticker(yf_ticker),
            market=market,
            analysis_date=curr_date,
            price_start=price_start,
            target_history=_price_frame_from_ohlcv(ohlcv),
            include_retrieval_snapshot=not historical_replay,
        )
    except Exception as e:
        price_context = {
            "metadata": {
                "target_symbol": normalize_ticker(yf_ticker),
                "market": market,
                "analysis_date": curr_date,
            },
            "comparators": [],
            "windows": {},
            "daily_series": [],
            "warnings": [
                f"Attribution context unavailable: {type(e).__name__}: {e}. Relative performance Not Rated."
            ],
        }
        expectations_text = (
            f"# Expectations Context for {normalize_ticker(yf_ticker)}\n\n"
            f"<expectations data unavailable: {type(e).__name__}: {e} — expectation gap and priced-in assessment Not Rated>\n"
        )

    path = write_structured_file(
        os.path.join(ticker_dir, "price_context"),
        price_context,
    )
    results["files"]["price_context"] = path

    path = os.path.join(ticker_dir, "expectations.txt")
    with open(path, "w") as f:
        f.write(expectations_text)
    results["files"]["expectations"] = path

    # 1b. Options flow (US only — yfinance option chains are reliable only
    # for US-listed equities; HK coverage is sparse and CN has none)
    print("  [1b] Fetching options flow...")
    if market == "US" and not historical_replay:
        options_text = fetch_options_report(
            yf_ticker,
            curr_date,
            spot_price=_latest_close_from_ohlcv(ohlcv),
        )
        path = os.path.join(ticker_dir, "options.txt")
        with open(path, "w") as f:
            f.write(options_text)
        results["files"]["options"] = path
    else:
        options_text = (
            not_rated_text("Options", temporal_context)
            if historical_replay else
            f"<options data unavailable for {ticker}: option chains are not "
            f"fetched for {market} market — Options Flow not rated>"
        )
        path = os.path.join(ticker_dir, "options.txt")
        with open(path, "w") as f:
            f.write(options_text)
        results["files"]["options"] = path

    # 2. Technical indicators
    print("  [2/8] Computing technical indicators...")
    indicators = fetch_indicators(yf_ticker, curr_date, market=market)
    path = os.path.join(ticker_dir, "indicators.txt")
    with open(path, "w") as f:
        f.write(indicators)
    results["files"]["indicators"] = path

    # 3. News (route by market, 翻页+过滤流水)
    print("  [3/8] Fetching company news...")
    news_path = os.path.join(ticker_dir, "news.txt")
    if market == "CN":
        raw = fetch_cn_news_raw(ticker, news_start, curr_date)
    elif market == "HK":
        raw = fetch_hk_news_raw(ticker, news_start, curr_date)
    else:
        raw = _yf_news_to_list(yf_ticker, news_start, curr_date, market=market)
    temporal_excluded = 0
    if historical_replay:
        raw, temporal_excluded = filter_historical_news(
            raw, temporal_context["analysis_timestamp"]
        )
    process_and_write_news(raw, curr_date, news_start, news_path,
                           lookback_days=NEWS_LOOKBACK_DAYS, market=market,
                           temporal_excluded=temporal_excluded)
    results["files"]["news"] = news_path

    # 3b. StockTwits retail sentiment (all markets; degrades to placeholder)
    print("  [3b] Fetching StockTwits messages...")
    stocktwits_text = fetch_stocktwits_messages(yf_ticker)
    path = os.path.join(ticker_dir, "stocktwits.txt")
    with open(path, "w") as f:
        f.write(stocktwits_text)
    results["files"]["stocktwits"] = path

    # 3c. Reddit community discussion (all markets; degrades to placeholder)
    print("  [3c] Fetching Reddit posts...")
    reddit_text = fetch_reddit_posts(yf_ticker)
    path = os.path.join(ticker_dir, "reddit.txt")
    with open(path, "w") as f:
        f.write(reddit_text)
    results["files"]["reddit"] = path

    # 4. Global news (route by market)
    print("  [4/8] Fetching global news...")
    global_news_parts = []
    if historical_replay:
        global_news = not_rated_text("Global News", temporal_context)
    else:
        if market == "CN":
            cn_macro = fetch_cn_global_news(curr_date)
            global_news_parts.append(cn_macro)
        yf_global = fetch_global_news(curr_date)
        global_news_parts.append(yf_global)
        global_news = "\n\n".join(global_news_parts)
    path = os.path.join(ticker_dir, "global_news.txt")
    with open(path, "w") as f:
        f.write(global_news)
    results["files"]["global_news"] = path

    # 4b. FRED macro indicators (all markets; degrades to placeholder
    # when FRED_API_KEY is unset)
    print("  [4b] Fetching FRED macro indicators...")
    macro_text = (
        not_rated_text("Macro Indicators", temporal_context)
        if historical_replay else fetch_macro_report(curr_date)
    )
    path = os.path.join(ticker_dir, "macro_indicators.txt")
    with open(path, "w") as f:
        f.write(macro_text)
    results["files"]["macro_indicators"] = path

    # 4c. Polymarket prediction markets (all markets; no API key needed)
    print("  [4c] Fetching Polymarket prediction markets...")
    pm_text = (
        not_rated_text("Prediction Markets", temporal_context)
        if historical_replay else fetch_prediction_markets()
    )
    path = os.path.join(ticker_dir, "prediction_markets.txt")
    with open(path, "w") as f:
        f.write(pm_text)
    results["files"]["prediction_markets"] = path

    # 5. Fundamentals
    print("  [5/8] Fetching fundamentals...")
    fundamentals = (
        not_rated_text("Fundamentals", temporal_context)
        if historical_replay else fetch_fundamentals(yf_ticker, market=market)
    )
    fundamentals = (
        f"{fundamentals.rstrip()}\n"
        f"Quote Currency: {quote_currency or 'N/A'}\n"
        f"Financial Currency: {financial_currency or 'N/A'}\n"
    )
    path = os.path.join(ticker_dir, "fundamentals.txt")
    with open(path, "w") as f:
        f.write(fundamentals)
    results["files"]["fundamentals"] = path

    # 6. Balance sheet
    print("  [6/8] Fetching balance sheet...")
    balance_sheet = (
        not_rated_text("Balance Sheet", temporal_context)
        if historical_replay else
        fetch_financial_stmt(yf_ticker, "balance_sheet", "quarterly", curr_date, market=market)
    )
    path = os.path.join(ticker_dir, "balance_sheet.csv")
    with open(path, "w") as f:
        f.write(balance_sheet)
    results["files"]["balance_sheet"] = path

    # 7. Cash flow
    print("  [7/8] Fetching cash flow...")
    cashflow = (
        not_rated_text("Cash Flow", temporal_context)
        if historical_replay else
        fetch_financial_stmt(yf_ticker, "cashflow", "quarterly", curr_date, market=market)
    )
    path = os.path.join(ticker_dir, "cashflow.csv")
    with open(path, "w") as f:
        f.write(cashflow)
    results["files"]["cashflow"] = path

    # 8. Income statement
    print("  [8/8] Fetching income statement...")
    income_stmt = (
        not_rated_text("Income Statement", temporal_context)
        if historical_replay else
        fetch_financial_stmt(yf_ticker, "income_stmt", "quarterly", curr_date, market=market)
    )
    path = os.path.join(ticker_dir, "income_stmt.csv")
    with open(path, "w") as f:
        f.write(income_stmt)
    results["files"]["income_stmt"] = path

    # Recompute valuation and operating-profit metrics from aligned local data.
    # This prevents stale provider P/B snapshots, unit errors in EV/EBITDA, and
    # confusion between GAAP reported and derived operating income.
    verified_fx_rate = fx.get("rate") if fx.get("status") == "verified" else None
    audit_metrics = compute_point_in_time_metrics(
        fundamentals, balance_sheet, income_stmt, ohlcv,
        quote_currency=quote_currency,
        financial_currency=financial_currency,
        fx_rate=verified_fx_rate,
    )
    fundamentals = append_audit(
        fundamentals, balance_sheet, income_stmt, ohlcv,
        quote_currency=quote_currency,
        financial_currency=financial_currency,
        fx_rate=verified_fx_rate,
    )
    fundamentals_path = results["files"]["fundamentals"]
    with open(fundamentals_path, "w") as f:
        f.write(fundamentals)

    # 9. Insider transactions (best-effort)
    print("  [9/9] Fetching insider transactions...")
    insider = (
        not_rated_text("Insider Transactions", temporal_context)
        if historical_replay else fetch_insider_transactions(yf_ticker)
    )
    path = os.path.join(ticker_dir, "insider.txt")
    with open(path, "w") as f:
        f.write(insider)
    results["files"]["insider"] = path

    # 10. Segments (仅 HK/US)
    print("  [10] Fetching business segments...")
    sankey_data = None
    if market in ("HK", "US") and not historical_replay:
        sankey_path = os.path.join(ticker_dir, "revenue_sankey")
        rs_raw = fetch_revenue_sankey(ticker)
        rs_parsed = parse_revenue_sankey(rs_raw)
        sankey_data = {
            "metadata": get_revenue_sankey_metadata(ticker),
            "revenue_sankey": rs_parsed,
        }
        sankey_path = write_structured_file(sankey_path, sankey_data)
        results["files"]["revenue_sankey"] = sankey_path

        yaml_path = os.path.join(ticker_root, "segments.yaml")
        if not os.path.exists(yaml_path):
            if not rs_parsed:
                open(os.path.join(ticker_dir, "segments_fetch_failed.flag"), "w").close()
                print("    longbridge returned no sankey data -> segments_fetch_failed.flag", flush=True)
            else:
                open(os.path.join(ticker_dir, "segments_missing.flag"), "w").close()
                print("    segments.yaml missing -> segments_missing.flag", flush=True)
    elif market == "CN":
        print("  [10] Skipped (CN market, no segment analysis)", flush=True)
    else:
        print("  [10] Skipped (historical replay has no point-in-time segment snapshot)", flush=True)

    # 10b. Official disclosure evidence and unified financial facts.
    # Official XBRL and deterministically parsed PDF/HTML facts have priority;
    # the existing free-provider statement artifacts only fill missing keys.
    print("  [10b] Fetching official filing evidence...")
    official = fetch_official_filings(ticker, market, curr_date)
    structured_facts = official.get("structured_facts")
    official_for_output = dict(official)
    official_for_output.pop("structured_facts", None)
    official_path = write_structured_file(
        os.path.join(ticker_dir, "official_filings"),
        official_for_output,
    )
    results["files"]["official_filings"] = official_path
    if structured_facts is not None:
        facts_path = write_structured_file(
            os.path.join(ticker_dir, "official_companyfacts"),
            structured_facts,
        )
        results["files"]["official_companyfacts"] = facts_path

    print("  [10c] Fetching unified official financial facts...")
    official_financials = fetch_official_financials(
        ticker,
        market,
        curr_date,
        official_disclosures=official,
        api_fallback={
            "symbol": yf_ticker,
            "financial_currency": financial_currency,
            "statements": {
                "income_stmt": income_stmt,
                "balance_sheet": balance_sheet,
                "cashflow": cashflow,
            },
        },
    )
    official_financials_path = write_structured_file(
        os.path.join(ticker_dir, "official_financials"),
        official_financials,
    )
    results["files"]["official_financials"] = official_financials_path

    # Web valuation evidence is an explicit input written by the parallel
    # market-consensus research sub-agent. It is read lazily right before
    # validation (rather than at startup) so fetch_data can run concurrently
    # with that sub-agent; it is never inferred from article text or silently
    # replaced with provider target-price guesses.
    valuation_consensus_input = args.valuation_consensus_file or os.path.join(
        ticker_dir, "valuation_consensus"
    )
    valuation_consensus = _load_valuation_consensus(
        valuation_consensus_input,
        ticker=ticker,
        analysis_date=curr_date,
        wait_for_explicit=args.valuation_consensus_file is not None,
    )
    valuation_consensus_path = write_structured_file(
        os.path.join(ticker_dir, "valuation_consensus"),
        valuation_consensus,
    )
    results["files"]["valuation_consensus"] = str(valuation_consensus_path)

    # 10d. Generate the fail-closed numeric contract consumed by every LLM role.
    print("  [10d] Building deterministic validated metrics...")
    contract = build_validated_metrics(
        ticker=ticker,
        market=market,
        analysis_date=curr_date,
        snapshot=provider_snapshot,
        fx=fx,
        audit_metrics=audit_metrics,
        official_filings=official_for_output,
        official_structured_facts=structured_facts,
        official_financials=official_financials,
        sankey_data=sankey_data,
        valuation_consensus=valuation_consensus,
        temporal_context=temporal_context,
    )
    validated_path = write_structured_file(
        os.path.join(ticker_dir, "validated_metrics"),
        contract,
    )
    results["files"]["validated_metrics"] = validated_path
    validation_report_path = os.path.join(ticker_dir, "validation_report.md")
    with open(validation_report_path, "w") as f:
        f.write(render_validation_report(contract))
    results["files"]["validation_report"] = validation_report_path
    forward_pe_path = write_structured_file(
        os.path.join(ticker_dir, "forward_pe_valuation"),
        contract["forward_pe_valuation"],
    )
    results["files"]["forward_pe_valuation"] = str(forward_pe_path)

    # 11. Data quality audit
    print("  [11] Computing data quality metadata...")
    quality = _compute_data_quality(
        ticker_dir, ticker, curr_date, ohlcv, market,
        execution_date=execution_date,
        temporal_context=temporal_context,
    )
    quality.update({
        "currency": contract["currency"],
        "official_filings": contract["official_filings"],
        "validation_gates": contract["gates"],
        "validated_metrics_status": contract["quality"]["status"],
        "provider_retry_events": get_retry_events(),
    })
    quality_path = write_structured_file(
        os.path.join(ticker_dir, "data_quality"),
        quality,
    )
    results["files"]["data_quality"] = quality_path

    # Write summary
    summary_path = write_structured_file(
        os.path.join(ticker_dir, "summary"),
        results,
    )

    completion = (
        "verified" if contract["quality"]["status"] == "verified"
        else "completed with explicit degradation"
    )
    print(f"\nData fetch {completion}. Summary: {summary_path}")
    print(f"All files in: {ticker_dir}")


if __name__ == "__main__":
    main()
