import sys
from types import SimpleNamespace

import pandas as pd
import pytest

from fetch_data import fetch_cn_global_news

from macro_data import (
    DEFAULT_INDICATORS,
    MACRO_SERIES,
    fetch_macro_report,
    fetch_series,
    render_series_block,
    resolve_series_id,
)


POINTS = [
    ("2026-07-01", "3.0"),
    ("2026-08-01", "3.5"),
]


def test_alias_resolution_maps_known_aliases_to_series_ids():
    assert resolve_series_id("cpi") == "CPIAUCSL"
    assert resolve_series_id("CPI") == "CPIAUCSL"
    assert resolve_series_id("core_pce") == "PCEPILFE"
    assert resolve_series_id("10y_2y_spread") == "T10Y2Y"
    assert resolve_series_id("yield_curve") == "T10Y2Y"
    assert resolve_series_id("fed funds rate") == "FEDFUNDS"  # spaces normalized


def test_alias_resolution_passes_raw_series_ids_through():
    assert resolve_series_id("CPIAUCSL") == "CPIAUCSL"
    assert resolve_series_id("DGS10") == "DGS10"


def test_alias_resolution_rejects_descriptive_phrases():
    with pytest.raises(ValueError):
        resolve_series_id("bank of japan rate")
    with pytest.raises(ValueError):
        resolve_series_id("inflation in the united states over the next decade")


def test_default_indicator_set_covers_rates_inflation_labor():
    assert "fed_funds_rate" in DEFAULT_INDICATORS
    assert "10y_treasury" in DEFAULT_INDICATORS
    assert "yield_curve" in DEFAULT_INDICATORS
    assert "cpi" in DEFAULT_INDICATORS
    assert "core_cpi" in DEFAULT_INDICATORS
    assert "unemployment_rate" in DEFAULT_INDICATORS
    for indicator in DEFAULT_INDICATORS:
        assert indicator in MACRO_SERIES


def test_render_series_block_reports_latest_and_window_change():
    text = render_series_block(
        title="Consumer Price Index",
        series_id="CPIAUCSL",
        units="Index 1982-1984=100",
        frequency="Monthly",
        seasonal="Seasonally Adjusted",
        start_date="2025-08-03",
        curr_date="2026-08-03",
        points=POINTS,
    )

    assert "### Consumer Price Index (CPIAUCSL)" in text
    assert "- Units: Index 1982-1984=100" in text
    assert "- Frequency: Monthly (Seasonally Adjusted)" in text
    assert "**Latest:** 3.5 (2026-08-01)" in text
    assert "**Change over window:** +0.50 (+16.67%)" in text
    assert "| 2026-07-01 | 3.0 |" in text


def test_render_series_block_handles_non_numeric_values():
    text = render_series_block(
        title="Series",
        series_id="SERIESID",
        units="",
        frequency="",
        seasonal="",
        start_date="2026-01-01",
        curr_date="2026-08-03",
        points=[("2026-01-01", "."), ("2026-02-01", "N/A")],
    )

    assert "**Latest:** N/A (2026-02-01)" in text
    assert "Change over window" not in text


def test_render_series_block_marks_empty_window():
    text = render_series_block(
        title="Series",
        series_id="SERIESID",
        units="",
        frequency="",
        seasonal="",
        start_date="2026-01-01",
        curr_date="2026-08-03",
        points=[],
    )

    assert "No observations for SERIESID in this window" in text


def test_render_series_block_truncates_long_windows_to_max_rows():
    points = [(f"2026-01-{day:02d}", "1.0") for day in range(1, 51)]
    text = render_series_block(
        title="Series",
        series_id="SERIESID",
        units="",
        frequency="Daily",
        seasonal="",
        start_date="2025-08-03",
        curr_date="2026-08-03",
        points=points,
    )

    assert "showing the most recent 40 of 50 observations" in text
    assert text.count("| 2026-01-") == 40


def test_fetch_series_rejects_bad_alias_without_network():
    text = fetch_series("bank of japan rate", "2026-08-03", 365)

    assert "FRED:" in text
    assert "not a known macro alias" in text


def test_fetch_macro_report_degrades_without_api_key(monkeypatch):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    text = fetch_macro_report("2026-08-03")

    assert "FRED_API_KEY environment variable is not set" in text
    assert "macro indicators not rated" in text


def test_fetch_macro_report_keeps_other_series_when_one_fails(monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "dummy-key")
    monkeypatch.setattr(
        "macro_data.fetch_series",
        lambda indicator, curr_date, look_back_days: (
            f"### {indicator}\n<macro data unavailable: TestError>"
            if indicator == "cpi"
            else f"### {indicator}\nOK"
        ),
    )

    text = fetch_macro_report("2026-08-03")

    assert "### cpi" in text
    assert "<macro data unavailable: TestError>" in text
    assert "### fed_funds_rate" in text
    assert "OK" in text


def test_cn_macro_data_preserves_source_text_but_uses_english_generated_labels(monkeypatch):
    calendar = pd.DataFrame([
        {
            "地区": "中国",
            "事件": "制造业采购经理指数",
            "公布": "50.2",
            "预期": "49.9",
            "前值": "49.8",
            "时间": "09:30",
        }
    ])
    fake_akshare = SimpleNamespace(
        news_economic_baidu=lambda date: calendar,
        news_cctv=lambda date: pd.DataFrame(),
    )
    monkeypatch.setitem(sys.modules, "akshare", fake_akshare)

    text = fetch_cn_global_news("2026-08-07")

    assert "制造业采购经理指数" in text
    assert "actual=50.2, expected=49.9, previous=49.8" in text
    assert "实际=" not in text
    assert "预期=" not in text
    assert "前值=" not in text
