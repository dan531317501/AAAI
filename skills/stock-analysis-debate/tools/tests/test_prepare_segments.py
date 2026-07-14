from prepare_segments import to_csv


def _quarters():
    return [
        {
            "report_period": "2025.Q4", "date": "20250331",
            "total_revenue": "32154000000", "currency": "CNY",
            "segments": [
                {"segment": "商业", "revenue": "27241000000", "percent": "84.72", "yoy": ""},
                {"segment": "云智能集团", "revenue": "1243000000", "percent": "3.87", "yoy": "20.11"},
            ],
        },
        {
            "report_period": "2025.Q3", "date": "20241231",
            "total_revenue": "30000000000", "currency": "CNY",
            "segments": [
                {"segment": "云智能集团", "revenue": "1100000000", "percent": "3.67", "yoy": "15.00"},
            ],
        },
    ]


def test_to_csv_header_and_rows():
    csv = to_csv(_quarters(), recent_n=8)
    lines = csv.strip().split("\n")
    assert lines[0] == "segment,report_period,total_revenue,revenue,percent,yoy"
    # 3行数据（Q4 2个分部 + Q3 1个分部）
    assert len(lines) == 4
    # 检查一行内容
    row = "云智能集团,2025.Q4,32154000000,1243000000,3.87,20.11"
    assert row in csv


def test_to_csv_truncates_to_recent_n():
    # recent_n=1 只取最近1个季度
    csv = to_csv(_quarters(), recent_n=1)
    lines = csv.strip().split("\n")
    # header + 2个分部（最近季度Q4有2个分部）
    assert len(lines) == 3
    assert "2025.Q4" in csv
    assert "2025.Q3" not in csv


def test_to_csv_empty_input():
    assert to_csv([], recent_n=8).strip() == "segment,report_period,total_revenue,revenue,percent,yoy"


from prepare_segments import gen_yaml_from_data


def test_gen_yaml_multi_segment():
    bh = [{"date": "20250331", "report_period": "2025.Q4", "total_revenue": "1000",
           "segments": [
               {"segment": "商业", "revenue": "900", "percent": "90", "yoy": ""},
               {"segment": "云智能集团", "revenue": "100", "percent": "10", "yoy": "20"},
           ]}]
    data = {"business_historical": bh, "revenue_sankey": []}
    out = gen_yaml_from_data(data)
    assert out["multi_segment"] is True
    assert out["data_source"] == "longbridge"
    assert any(s["name"] == "云智能集团" for s in out["segments"])


def test_gen_yaml_empty_returns_none():
    assert gen_yaml_from_data({"business_historical": [], "revenue_sankey": []}) is None
    assert gen_yaml_from_data({}) is None
