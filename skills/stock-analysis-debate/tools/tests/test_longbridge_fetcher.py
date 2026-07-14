from longbridge_fetcher import build_counter_id, parse_business_historical, parse_revenue_sankey


# 模拟长桥 API1 返回（精简）
_API1_SAMPLE = {
    "code": 0, "message": "success",
    "data": {
        "historical": [
            {
                "total": "32154000000", "currency": "CNY", "date": "20160630",
                "report_txt": "2017.Q1", "yoy": "",
                "business": [
                    {"name": "商业", "percent": "84.72", "value": "27241000000", "yoy": ""},
                    {"name": "云智能集团", "percent": "3.87", "value": "1243000000", "yoy": "20.11"},
                ],
            },
            {
                "total": "34292000000", "currency": "CNY", "date": "20160930",
                "report_txt": "2017.Q2", "yoy": "6.64",
                "business": [
                    {"name": "云智能集团", "percent": "4.35", "value": "1493000000", "yoy": "20.11"},
                ],
            },
        ]
    },
}


def test_counter_id_hk_strips_leading_zeros():
    assert build_counter_id("09988.HK") == "ST/HK/9988"
    assert build_counter_id("00700.HK") == "ST/HK/700"


def test_counter_id_us():
    assert build_counter_id("AAPL") == "ST/US/AAPL"
    assert build_counter_id("MSFT") == "ST/US/MSFT"


def test_counter_id_cn_returns_none():
    assert build_counter_id("600519.SH") is None
    assert build_counter_id("000858.SZ") is None


def test_parse_api1_returns_quarterly_segments():
    result = parse_business_historical(_API1_SAMPLE)
    assert len(result) == 2  # 两个季度
    q1 = result[0]
    assert q1["report_period"] == "2017.Q1"
    assert q1["total_revenue"] == "32154000000"
    assert q1["currency"] == "CNY"
    assert len(q1["segments"]) == 2
    seg = q1["segments"][1]
    assert seg["segment"] == "云智能集团"
    assert seg["revenue"] == "1243000000"
    assert seg["percent"] == "3.87"
    assert seg["yoy"] == "20.11"


def test_parse_api1_empty_returns_empty():
    assert parse_business_historical({"data": {"historical": []}}) == []


def test_parse_api1_null_safe():
    assert parse_business_historical({}) == []
    assert parse_business_historical(None) == []


_API2_SAMPLE = {
    "code": 0, "message": "success",
    "data": {
        "list": [
            {
                "fiscal_year": 2019, "report": "2019 财年三季报", "currency": "HKD",
                "nodes": [
                    {"key": "bus_116796", "name": "商业", "value": "117277656183", "yoy": "10", "level": 1},
                    {"key": "bus_133364", "name": "云智能集团", "value": "7538895063", "yoy": "30", "level": 1},
                    {"key": "total_rev", "name": "营业收入", "value": "133738698422", "yoy": "", "level": 2},
                ],
            },
        ]
    },
}


def test_parse_api2_returns_fiscal_year_segments():
    result = parse_revenue_sankey(_API2_SAMPLE)
    assert len(result) == 1
    fy = result[0]
    assert fy["fiscal_year"] == 2019
    assert fy["currency"] == "HKD"
    # level==1 的才是业务分部节点
    assert len(fy["segments"]) == 2
    names = [s["segment"] for s in fy["segments"]]
    assert "商业" in names and "云智能集团" in names


def test_parse_api2_empty():
    assert parse_revenue_sankey({"data": {"list": []}}) == []
    assert parse_revenue_sankey(None) == []
