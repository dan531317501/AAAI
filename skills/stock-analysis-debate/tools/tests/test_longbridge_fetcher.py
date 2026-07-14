from longbridge_fetcher import build_counter_id, parse_business_historical, parse_revenue_sankey, derive_segments_yaml


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


def test_derive_multi_segment_true():
    quarters = [
        {"date": "20250331", "report_period": "2025.Q4", "total_revenue": "32154000000",
         "segments": [
             {"segment": "商业", "revenue": "27241000000", "percent": "84.72", "yoy": ""},
             {"segment": "云智能集团", "revenue": "1243000000", "percent": "3.87", "yoy": "20"},
         ]},
    ]
    out = derive_segments_yaml(quarters)
    assert out["multi_segment"] is True
    assert out["data_source"] == "longbridge"
    names = [s["name"] for s in out["segments"]]
    assert "商业" in names and "云智能集团" in names


def test_derive_single_other_dominant_is_not_multi():
    # 只有"所有其他"且占比95% -> multi_segment False
    quarters = [
        {"date": "20250331", "report_period": "2025.Q4", "total_revenue": "1000",
         "segments": [{"segment": "所有其他", "revenue": "950", "percent": "95", "yoy": ""}]},
    ]
    out = derive_segments_yaml(quarters)
    assert out["multi_segment"] is False


def test_derive_aliases_for_known_segment():
    quarters = [
        {"date": "20250331", "report_period": "2025.Q4", "total_revenue": "1000",
         "segments": [{"segment": "云智能集团", "revenue": "100", "percent": "10", "yoy": ""}]},
    ]
    out = derive_segments_yaml(quarters)
    seg = [s for s in out["segments"] if s["name"] == "云智能集团"][0]
    assert "阿里云" in seg["aliases"]


def test_derive_empty_returns_none():
    assert derive_segments_yaml([]) is None


def test_derive_excludes_accounting_pseudo_segments():
    # 未分摊/分部间抵消是会计调整项，不应进清单，不计入 real_segs
    quarters = [
        {"date": "20250331", "report_period": "2025.Q4", "total_revenue": "1000",
         "segments": [
             {"segment": "云智能集团", "revenue": "500", "percent": "50", "yoy": "20"},
             {"segment": "未分摊", "revenue": "100", "percent": "10", "yoy": ""},
             {"segment": "分部间抵消", "revenue": "-50", "percent": "-5", "yoy": ""},
             {"segment": "所有其他", "revenue": "450", "percent": "45", "yoy": ""},
         ]},
    ]
    out = derive_segments_yaml(quarters)
    names = [s["name"] for s in out["segments"]]
    assert names == ["云智能集团"]  # 只剩真实业务分部
    assert "未分摊" not in names
    assert "分部间抵消" not in names
    assert "所有其他" not in names
    assert out["multi_segment"] is False  # real_segs 只有1个


def test_derive_english_segment_name_aliases():
    # 长桥最新季度可能返回英文分部名，aliases 应能匹配
    quarters = [
        {"date": "20250331", "report_period": "2025.Q4", "total_revenue": "1000",
         "segments": [
             {"segment": "Alibaba China E-commerce Group", "revenue": "600", "percent": "60", "yoy": "10"},
             {"segment": "云智能集团", "revenue": "400", "percent": "40", "yoy": "30"},
         ]},
    ]
    out = derive_segments_yaml(quarters)
    assert out["multi_segment"] is True
    ecom = [s for s in out["segments"] if s["name"] == "Alibaba China E-commerce Group"][0]
    assert "淘宝" in ecom["aliases"]
    assert "天猫" in ecom["aliases"]
