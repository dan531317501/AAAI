import pandas as pd

import fetch_data
import longbridge_fetcher
from longbridge_fetcher import (build_kline_counter_id, fetch_range_klines,
                                parse_range_klines)


def _yf_frame(dates, closes):
    return pd.DataFrame(
        {
            "Open": closes,
            "High": closes,
            "Low": closes,
            "Close": closes,
            "Volume": [100] * len(dates),
        },
        index=pd.to_datetime(dates),
    )


def _kline(date, close):
    timestamp = int((pd.Timestamp(date, tz="UTC") + pd.Timedelta(hours=12)).timestamp())
    return {
        "timestamp": str(timestamp),
        "open": str(close),
        "high": str(close + 1),
        "low": str(close - 1),
        "close": str(close),
        "amount": "200",
    }


def test_build_kline_counter_id_supports_us_hk_and_a_shares():
    assert build_kline_counter_id("AAPL") == "ST/US/AAPL"
    assert build_kline_counter_id("00700.HK") == "ST/HK/700"
    assert build_kline_counter_id("00700") == "ST/HK/700"
    assert build_kline_counter_id("600519.SH") == "ST/SH/600519"
    assert build_kline_counter_id("600519.SS") == "ST/SH/600519"
    assert build_kline_counter_id("000858.SZ") == "ST/SZ/000858"
    assert build_kline_counter_id("600519", market="CN") == "ST/SH/600519"
    assert build_kline_counter_id("000858", market="CN") == "ST/SZ/000858"
    assert build_kline_counter_id("920982.BJ") is None


def test_parse_range_klines_skips_invalid_rows_and_sorts_by_date():
    payload = {
        "code": 0,
        "data": {
            "klines": [
                _kline("2026-07-30", 30),
                {"timestamp": "bad", "close": "1"},
                _kline("2026-07-29", 29),
            ]
        },
    }

    assert parse_range_klines(payload) == [
        {
            "Date": "2026-07-29",
            "Open": 29.0,
            "High": 30.0,
            "Low": 28.0,
            "Close": 29.0,
            "Volume": 200.0,
        },
        {
            "Date": "2026-07-30",
            "Open": 30.0,
            "High": 31.0,
            "Low": 29.0,
            "Close": 30.0,
            "Volume": 200.0,
        },
    ]


def test_parse_range_klines_uses_market_timezone_for_a_share_date():
    payload = {
        "code": 0,
        "data": {
            "klines": [
                {
                    "timestamp": "1785340800",
                    "open": "10",
                    "high": "11",
                    "low": "9",
                    "close": "10",
                    "amount": "100",
                }
            ]
        },
    }

    assert parse_range_klines(payload, "CN")[0]["Date"] == "2026-07-30"


def test_parse_range_klines_converts_cn_lots_to_shares():
    payload = {
        "code": 0,
        "data": {
            "klines": [{
                "timestamp": "1785340800",
                "open": "10",
                "high": "11",
                "low": "9",
                "close": "10",
                "amount": "100",
                "balance": "100000",
            }]
        },
    }

    assert parse_range_klines(payload, "CN")[0]["Volume"] == 10000.0


def test_parse_range_klines_preserves_cn_share_volume():
    payload = {
        "code": 0,
        "data": {
            "klines": [{
                "timestamp": "1785340800",
                "open": "10",
                "high": "11",
                "low": "9",
                "close": "10",
                "amount": "10000",
                "balance": "100000",
            }]
        },
    }

    assert parse_range_klines(payload, "CN")[0]["Volume"] == 10000.0


def test_parse_range_klines_marks_ambiguous_cn_volume_unavailable():
    payload = {
        "code": 0,
        "data": {
            "klines": [{
                "timestamp": "1785340800",
                "open": "10",
                "high": "11",
                "low": "9",
                "close": "10",
                "amount": "100",
            }]
        },
    }

    assert parse_range_klines(payload, "CN")[0]["Volume"] is None


def test_parse_range_klines_does_not_scale_hk_volume():
    payload = {
        "code": 0,
        "data": {
            "klines": [{
                "timestamp": "1785340800",
                "open": "10",
                "high": "11",
                "low": "9",
                "close": "10",
                "amount": "100",
                "balance": "100000",
            }]
        },
    }

    assert parse_range_klines(payload, "HK")[0]["Volume"] == 100.0


def test_fetch_range_klines_sends_only_required_header(monkeypatch):
    captured = {}

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"code": 0, "data": {"klines": []}}

    def fake_get(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return Response()

    monkeypatch.setattr(longbridge_fetcher.requests, "get", fake_get)

    assert fetch_range_klines("AAPL", "US")["code"] == 0
    assert captured["headers"] == {"x-app-id": "longbridge"}
    assert captured["params"]["counter_id"] == "ST/US/AAPL"
    assert captured["params"]["time_range"] == 3


def test_current_yfinance_data_does_not_call_longbridge(monkeypatch):
    current = _yf_frame(["2026-07-29", "2026-07-30"], [29, 30])
    requested = {}

    class Ticker:
        def history(self, start, end):
            requested["end"] = end
            return current

    monkeypatch.setattr(fetch_data.yf, "Ticker", lambda ticker: Ticker())
    monkeypatch.setattr(
        fetch_data,
        "fetch_range_klines",
        lambda *args: (_ for _ in ()).throw(
            AssertionError("fresh yfinance data must not call Longbridge")
        ),
    )

    data, source = fetch_data.fetch_price_data(
        "AAPL", "2026-07-01", "2026-07-30", "US"
    )

    assert requested["end"] == "2026-07-31"
    assert data.index.max() == pd.Timestamp("2026-07-30")
    assert source == "yfinance"


def test_stale_yfinance_data_is_completed_without_overwriting_existing_day(
    monkeypatch,
):
    stale = _yf_frame(["2026-07-28", "2026-07-29"], [28, 29])
    payload = {
        "code": 0,
        "data": {
            "klines": [
                _kline("2026-07-29", 999),
                _kline("2026-07-30", 30),
            ]
        },
    }

    class Ticker:
        def history(self, start, end):
            return stale

    monkeypatch.setattr(fetch_data.yf, "Ticker", lambda ticker: Ticker())
    monkeypatch.setattr(fetch_data, "fetch_range_klines", lambda *args: payload)

    data, source = fetch_data.fetch_price_data(
        "AAPL", "2026-07-01", "2026-07-30", "US"
    )

    assert list(data.index) == list(
        pd.to_datetime(["2026-07-28", "2026-07-29", "2026-07-30"])
    )
    assert data.loc["2026-07-29", "Close"] == 29
    assert data.loc["2026-07-30", "Close"] == 30
    assert source == "yfinance + Longbridge fallback"


def test_longbridge_supplies_prices_when_yfinance_fails(monkeypatch):
    payload = {
        "code": 0,
        "data": {"klines": [_kline("2026-07-29", 29), _kline("2026-07-30", 30)]},
    }

    class Ticker:
        def history(self, start, end):
            raise RuntimeError("provider unavailable")

    monkeypatch.setattr(fetch_data.yf, "Ticker", lambda ticker: Ticker())
    monkeypatch.setattr(fetch_data, "retry", lambda func, **kwargs: func())
    monkeypatch.setattr(fetch_data, "fetch_range_klines", lambda *args: payload)

    data, source = fetch_data.fetch_price_data(
        "AAPL", "2026-07-01", "2026-07-30", "US"
    )

    assert list(data["Close"]) == [29.0, 30.0]
    assert source == "Longbridge fallback"


def test_cn_fallback_marks_ambiguous_volume_not_rated(monkeypatch):
    payload = {
        "code": 0,
        "data": {"klines": [_kline("2026-07-29", 29), _kline("2026-07-30", 30)]},
    }

    class Ticker:
        def history(self, start, end):
            raise RuntimeError("provider unavailable")

    monkeypatch.setattr(fetch_data.yf, "Ticker", lambda ticker: Ticker())
    monkeypatch.setattr(fetch_data, "retry", lambda func, **kwargs: func())
    monkeypatch.setattr(fetch_data, "fetch_range_klines", lambda *args: payload)

    data, source = fetch_data.fetch_price_data(
        "600519.SH", "2026-07-01", "2026-07-30", "CN"
    )

    assert data["Volume"].isna().all()
    assert "CN Longbridge volume Not Rated" in source


def test_weekend_quality_accepts_previous_friday_as_latest_trading_day():
    ohlcv = (
        "# Stock data\n"
        "Date,Open,High,Low,Close,Volume\n"
        "2026-07-31,1,1,1,1,100\n"
    )

    quality = fetch_data._compute_data_quality(
        "/unused", "AAPL", "2026-08-02", ohlcv, "US"
    )

    assert quality["expected_price_date"] == "2026-07-31"
    assert quality["data_as_of_date"] == "2026-07-31"
    assert quality["data_fresh"] is True
