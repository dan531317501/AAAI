import math

import pandas as pd
import pytest

from options_flow import (
    clean_chain,
    compute_expiry_metrics,
    render_options_report,
    _days_to_expiry,
    _fresh_contracts,
    _pick_strike,
)


def make_chain(
    strikes=(200.0, 205.0, 210.0, 215.0, 220.0),
    volume=(100.0, 200.0, 300.0, 400.0, 500.0),
    oi=(1000.0, 2000.0, 3000.0, 4000.0, 5000.0),
    iv=(0.20, 0.21, 0.22, 0.23, 0.24),
    in_the_money=(False,) * 5,
):
    return pd.DataFrame(
        {
            "strike": strikes,
            "lastPrice": [1.0] * len(strikes),
            "volume": volume,
            "openInterest": oi,
            "impliedVolatility": iv,
            "inTheMoney": in_the_money,
        }
    )


CALLS = make_chain()
PUTS = make_chain(
    strikes=(185.0, 190.0, 195.0, 200.0, 205.0),
    volume=(600.0, 500.0, 400.0, 300.0, 200.0),
    oi=(6000.0, 5000.0, 4000.0, 3000.0, 2000.0),
    iv=(0.26, 0.25, 0.24, 0.23, 0.22),
    in_the_money=(False,) * 5,
)


def test_clean_chain_fills_nan_volume_and_drops_junk_iv():
    dirty = make_chain(
        volume=(100.0, None, 300.0, 400.0, 500.0),
        iv=(0.20, 0.00001, 0.22, 0.23, 0.24),
    )
    cleaned = clean_chain(dirty)

    assert cleaned["volume"].iloc[1] == 0.0
    assert math.isnan(cleaned["impliedVolatility"].iloc[1])


def test_pcr_ratios_use_volume_and_open_interest():
    metrics = compute_expiry_metrics(
        CALLS, PUTS, spot=205.0, expiry="2026-08-05", analysis_date="2026-08-03"
    )

    assert metrics["call_volume"] == 1500.0
    assert metrics["put_volume"] == 2000.0
    assert metrics["pcr_volume"] == pytest.approx(2000.0 / 1500.0)
    assert metrics["pcr_oi"] == pytest.approx(20000.0 / 15000.0)
    assert metrics["dte"] == 2


def test_pcr_is_none_when_call_volume_is_zero():
    calls_zero_volume = make_chain(volume=(0.0, 0.0, 0.0, 0.0, 0.0))
    metrics = compute_expiry_metrics(
        calls_zero_volume, PUTS, spot=205.0, expiry="2026-08-05",
        analysis_date="2026-08-03",
    )

    assert metrics["pcr_volume"] is None
    assert metrics["pcr_oi"] is not None


def test_atm_strike_and_iv_anchor_to_spot():
    metrics = compute_expiry_metrics(
        CALLS, PUTS, spot=205.0, expiry="2026-08-05", analysis_date="2026-08-03"
    )

    assert metrics["atm_strike"] == 205.0
    assert metrics["atm_call_iv"] == pytest.approx(0.21)
    assert metrics["atm_put_iv"] == pytest.approx(0.22)


def test_atm_picks_nearest_strike_when_spot_is_between_strikes():
    metrics = compute_expiry_metrics(
        CALLS, PUTS, spot=207.0, expiry="2026-08-05", analysis_date="2026-08-03"
    )

    assert metrics["atm_strike"] == 205.0


def test_iv_skew_positive_when_downside_protection_is_richer():
    metrics = compute_expiry_metrics(
        CALLS, PUTS, spot=205.0, expiry="2026-08-05", analysis_date="2026-08-03"
    )

    # OTM call: nearest strike to 205*1.05=215.25 → 215 (iv 0.23)
    # OTM put: nearest strike to 205*0.95=194.75 → 195 (iv 0.24)
    assert metrics["otm_call_strike"] == 215.0
    assert metrics["otm_put_strike"] == 195.0
    assert metrics["iv_skew_pp"] == pytest.approx((0.24 - 0.23) * 100)


def test_iv_skew_negative_when_calls_are_richer():
    calls = make_chain(
        strikes=(200.0, 205.0, 210.0, 215.0, 220.0),
        iv=(0.30, 0.30, 0.30, 0.30, 0.30),
    )
    puts = make_chain(
        strikes=(185.0, 190.0, 195.0, 200.0, 205.0),
        iv=(0.22, 0.22, 0.22, 0.22, 0.22),
    )
    metrics = compute_expiry_metrics(
        calls, puts, spot=205.0, expiry="2026-08-05", analysis_date="2026-08-03"
    )

    assert metrics["iv_skew_pp"] == pytest.approx(-8.0)


def test_skew_is_none_when_either_otm_iv_is_invalid():
    calls = make_chain(
        strikes=(200.0, 205.0, 210.0, 215.0, 220.0),
        iv=(0.20, 0.21, 0.22, 0.00001, 0.24),  # 215 OTM call IV junk
    )
    metrics = compute_expiry_metrics(
        calls, PUTS, spot=205.0, expiry="2026-08-05", analysis_date="2026-08-03"
    )

    assert metrics["iv_skew_pp"] is None


def test_no_spot_skips_iv_section_but_keeps_ratios():
    metrics = compute_expiry_metrics(
        CALLS, PUTS, spot=None, expiry="2026-08-05", analysis_date="2026-08-03"
    )

    assert metrics["pcr_volume"] is not None
    assert metrics["atm_strike"] is None
    assert metrics["iv_skew_pp"] is None


def test_most_active_contract_ignores_below_threshold_volume():
    low_volume_calls = make_chain(volume=(1.0, 2.0, 3.0, 4.0, 5.0))
    metrics = compute_expiry_metrics(
        low_volume_calls, PUTS, spot=205.0, expiry="2026-08-05",
        analysis_date="2026-08-03",
    )

    assert metrics["top_call"] is None
    assert metrics["top_put"] is not None  # puts still have 600 volume


def test_fresh_contracts_flag_volume_greater_than_double_oi():
    active = make_chain(volume=(300.0, 0.0, 0.0, 0.0, 0.0), oi=(100.0, 0.0, 0.0, 0.0, 0.0))
    fresh = _fresh_contracts(clean_chain(active))

    assert len(fresh) == 1
    assert "200.00" in fresh[0]


def test_fresh_contracts_are_empty_without_active_volume():
    quiet = make_chain(volume=(10.0, 10.0, 10.0, 10.0, 10.0), oi=(100.0,) * 5)
    assert _fresh_contracts(clean_chain(quiet)) == []


def test_pick_strike_returns_none_for_empty_frame():
    assert _pick_strike(pd.DataFrame(), 100.0) is None


def test_days_to_expiry_handles_invalid_dates():
    assert _days_to_expiry("not-a-date", "2026-08-03") == 0
    assert _days_to_expiry("2026-08-05", "2026-08-03") == 2
    assert _days_to_expiry("2026-08-03", "2026-08-03") == 0


def test_render_report_includes_ratios_and_skew():
    metrics = compute_expiry_metrics(
        CALLS, PUTS, spot=205.0, expiry="2026-08-05", analysis_date="2026-08-03"
    )
    text = render_options_report(
        [metrics], ticker="TEST", analysis_date="2026-08-03", spot=205.0
    )

    assert "Put/Call Volume Ratio: 1.33" in text
    assert "Put/Call Open-Interest Ratio: 1.33" in text
    assert "IV skew (OTM put IV − OTM call IV): +1.0pp" in text
    assert "Most active call" in text
    assert "Freshly opened positions" not in text  # no vol >> OI in fixture


def test_render_report_lists_freshly_opened_positions():
    fresh_calls = make_chain(volume=(300.0, 0.0, 0.0, 0.0, 0.0), oi=(100.0, 0.0, 0.0, 0.0, 0.0))
    metrics = compute_expiry_metrics(
        fresh_calls, PUTS, spot=205.0, expiry="2026-08-05", analysis_date="2026-08-03"
    )
    text = render_options_report(
        [metrics], ticker="TEST", analysis_date="2026-08-03", spot=205.0
    )

    assert "Freshly opened positions (volume >> OI):" in text
    assert "Calls: $200.00" in text


def test_render_report_notes_when_open_interest_is_unavailable():
    metrics = compute_expiry_metrics(
        CALLS, PUTS, spot=205.0, expiry="2026-08-05", analysis_date="2026-08-03"
    )
    # Force OI unavailable to simulate a weekend/after-hours snapshot.
    metrics["oi_available"] = False
    text = render_options_report(
        [metrics], ticker="TEST", analysis_date="2026-08-03", spot=205.0
    )

    assert "open-interest data is unavailable in this snapshot" in text
    assert "put/call OI ratios are not rated" in text


def test_render_report_marks_no_data_placeholder():
    text = render_options_report([], ticker="TEST", analysis_date="2026-08-03", spot=None)

    assert "<no options data found for TEST — Options Flow not rated>" in text


def test_render_report_skips_iv_lines_without_spot():
    metrics = compute_expiry_metrics(
        CALLS, PUTS, spot=None, expiry="2026-08-05", analysis_date="2026-08-03"
    )
    text = render_options_report(
        [metrics], ticker="TEST", analysis_date="2026-08-03", spot=None
    )

    assert "Put/Call Volume Ratio: 1.33" in text
    assert "ATM strike" not in text


def test_render_report_uses_n_a_for_missing_ratios():
    empty_calls = make_chain(volume=(0.0,) * 5, oi=(0.0,) * 5)
    empty_puts = make_chain(
        strikes=(185.0, 190.0, 195.0, 200.0, 205.0),
        volume=(0.0,) * 5, oi=(0.0,) * 5,
    )
    metrics = compute_expiry_metrics(
        empty_calls, empty_puts, spot=205.0, expiry="2026-08-05",
        analysis_date="2026-08-03",
    )
    text = render_options_report(
        [metrics], ticker="TEST", analysis_date="2026-08-03", spot=205.0
    )

    assert "Put/Call Volume Ratio: N/A" in text
    assert "Put/Call Open-Interest Ratio: N/A" in text
