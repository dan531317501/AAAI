"""Output-path helpers shared by stock-analysis tools."""

import os


def resolve_ticker_paths(
    ticker: str,
    date: str,
    *,
    base_output_dir: str,
    ticker_data_dir: str | None = None,
) -> tuple[str, str]:
    """Return the ticker-level root and date-level data directory."""
    if ticker_data_dir:
        ticker_root = os.path.normpath(ticker_data_dir)
    else:
        ticker_root = os.path.join(base_output_dir, ticker.replace(".", "_"))
    return ticker_root, os.path.join(ticker_root, date)
