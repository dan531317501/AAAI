from longbridge_fetcher import build_counter_id


def test_counter_id_hk_strips_leading_zeros():
    assert build_counter_id("09988.HK") == "ST/HK/9988"
    assert build_counter_id("00700.HK") == "ST/HK/700"


def test_counter_id_us():
    assert build_counter_id("AAPL") == "ST/US/AAPL"
    assert build_counter_id("MSFT") == "ST/US/MSFT"


def test_counter_id_cn_returns_none():
    assert build_counter_id("600519.SH") is None
    assert build_counter_id("000858.SZ") is None
