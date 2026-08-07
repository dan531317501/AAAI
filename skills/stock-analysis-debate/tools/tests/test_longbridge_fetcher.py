from decimal import Decimal

import longbridge_fetcher
from longbridge_fetcher import (
    build_counter_id,
    classify_sankey_node,
    classify_segment_row,
    derive_segments_yaml,
    fetch_revenue_sankey,
    get_revenue_sankey_metadata,
    parse_revenue_sankey,
)


def _node(key, name, value, level, yoy="", show_value=None):
    return {
        "key": key,
        "name": name,
        "value": str(value),
        "show_value": str(value if show_value is None else show_value),
        "yoy": str(yoy),
        "level": level,
        "color": "#5A74FF",
    }


def _period(period, ccpg, dcai, other, consolidated, elimination):
    gross = ccpg + dcai + other
    nodes = [
        _node("bus_ccpg", "CCPG", ccpg, 1, "999"),
        _node("bus_dcai", "DCAI", dcai, 1, "999"),
        _node("bus_other", "其他", other, 1, "999"),
        _node("total_rev", "营业收入", gross, 2, "999", consolidated),
        _node("gp", "毛利润", 40, 3, "999"),
        _node("bus_elimination", "部门间冲销", elimination, 3, ""),
        _node("oper_inc", "营业利润", 10, 4, "999"),
    ]
    links = [
        {"source": "bus_ccpg", "target": "total_rev", "value": str(ccpg)},
        {"source": "bus_dcai", "target": "total_rev", "value": str(dcai)},
        {"source": "bus_other", "target": "total_rev", "value": str(other)},
        {"source": "total_rev", "target": "gp", "value": "40"},
        {"source": "gp", "target": "oper_inc", "value": "10"},
        {
            "source": "total_rev",
            "target": "bus_elimination",
            "value": str(elimination),
        },
    ]
    return {
        "fiscal_year": int(period.split()[1]),
        "period": period,
        "report": period,
        "currency": "USD",
        "nodes": nodes,
        "links": links,
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


def test_sankey_metadata_records_single_source_and_derived_semantics():
    metadata = get_revenue_sankey_metadata("INTC")

    assert metadata["provider"] == "Longbridge"
    assert metadata["currency_semantics"]["status"] == "translated_only"
    assert "official_operating_growth" in metadata["currency_semantics"]["prohibited_uses"]
    assert set(metadata["request_url_templates"]) == {"revenue_sankey"}
    assert "business_historical" not in metadata["request_url_templates"]
    assert "previous fiscal quarter" in metadata["quarterly_growth_semantics"]["qoq"]
    assert "same fiscal quarter" in metadata["quarterly_growth_semantics"]["yoy"]
    assert "nodes[].yoy" in (
        metadata["quarterly_growth_semantics"]["longbridge_yoy_raw"]
    )
    assert metadata["counter_id"] == "ST/US/INTC"
    assert metadata["request_urls"]["revenue_sankey"].endswith(
        "counter_id=ST%2FUS%2FINTC&report=qf"
    )


def test_parse_sankey_enriches_nodes_and_recalculates_growth():
    response = {
        "code": 0,
        "data": {
            "list": [
                _period("Q2 2025", 100, 50, 10, 140, 20),
                _period("Q1 2026", 120, 60, 10, 160, 30),
                _period("Q2 2026", 150, 75, 15, 205, 35),
            ],
        },
    }

    periods = parse_revenue_sankey(response)
    latest = periods[-1]
    ccpg = next(node for node in latest["nodes"] if node["key"] == "bus_ccpg")
    total = next(node for node in latest["nodes"] if node["key"] == "total_rev")
    elimination = next(
        node for node in latest["nodes"] if node["key"] == "bus_elimination"
    )

    assert "segments" not in latest
    assert latest["gross_segment_revenue_before_elimination"] == "240"
    assert latest["consolidated_revenue"] == "205"
    assert latest["intersegment_eliminations"] == "-35"
    assert latest["reconciliation_delta"] == "0"
    assert latest["reconciliation_status"] == "ok"
    assert latest["segment_completeness_delta"] == "0"
    assert latest["missing_segment_revenue"] == "0"
    assert latest["segment_completeness_status"] == "ok"

    assert ccpg["row_type"] == "business_segment"
    assert ccpg["gross_segment_mix_percent"] == "62.5"
    assert ccpg["qoq"] == "25"
    assert ccpg["yoy"] == "50"
    assert ccpg["longbridge_yoy_raw"] == "999"
    assert total["row_type"] == "revenue_total"
    assert total["qoq"] == "28.125"
    assert total["yoy"] == "46.428571"
    assert elimination["row_type"] == "intersegment_elimination"
    assert elimination["gross_segment_mix_percent"] == ""


def test_parse_sankey_detects_missing_level_one_revenue():
    item = _period("Q2 2026", 60, 20, 0, 60, 20)
    item["nodes"] = [
        node for node in item["nodes"]
        if node["key"] not in ("bus_dcai", "bus_other")
    ]

    parsed = parse_revenue_sankey({"data": {"list": [item]}})[0]

    assert parsed["gross_segment_revenue_before_elimination"] == "80"
    assert parsed["segment_completeness_delta"] == "-20"
    assert parsed["missing_segment_revenue"] == "20"
    assert parsed["segment_completeness_status"] == "missing"
    assert parsed["reconciliation_status"] == "ok"


def test_parse_sankey_detects_inconsistent_excess_level_one_revenue():
    item = _period("Q2 2026", 60, 20, 0, 60, 20)
    item["nodes"].append(_node("bus_bad", "其他", 1000, 1))

    parsed = parse_revenue_sankey({"data": {"list": [item]}})[0]

    assert parsed["segment_completeness_status"] == "inconsistent"
    assert Decimal(parsed["segment_completeness_delta"]) > 0
    assert parsed["missing_segment_revenue"] == ""


def test_fetch_sankey_uses_qf_report(monkeypatch):
    captured = {}

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"code": 0, "data": {"list": []}}

    def fake_get(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return Response()

    monkeypatch.setattr(longbridge_fetcher.requests, "get", fake_get)

    assert fetch_revenue_sankey("INTC")["code"] == 0
    assert captured["url"].endswith(
        "counter_id=ST%2FUS%2FINTC&report=qf"
    )


def test_parse_sankey_empty_returns_empty():
    assert parse_revenue_sankey({"data": {"list": []}}) == []
    assert parse_revenue_sankey(None) == []


def test_classify_sankey_nodes():
    assert classify_sankey_node(_node("gp", "毛利润", 10, 3)) == "gross_profit"
    assert classify_sankey_node(
        _node("cost_rev", "营业成本", 10, 3)
    ) == "cost_of_revenue"
    assert classify_sankey_node(
        _node("bus_x", "Intel Foundry", 10, 1)
    ) == "business_segment"
    assert classify_sankey_node(_node("bus_o", "其他", 10, 1)) == "other"


def test_classify_intersegment_elimination_label_variants():
    for name in (
        "部门间冲销",
        "部门间抵销",
        "分部间抵消",
        "Intersegment Eliminations",
        "Inter-segment elimination",
    ):
        assert classify_segment_row(name) == "intersegment_elimination"


def test_derive_segments_yaml_from_latest_sankey_period():
    periods = parse_revenue_sankey({
        "data": {
            "list": [
                _period("Q1 2026", 100, 50, 10, 140, 20),
                _period("Q2 2026", 150, 75, 15, 205, 35),
            ],
        },
    })

    result = derive_segments_yaml(periods)

    assert result["multi_segment"] is True
    assert result["data_source"] == "longbridge"
    assert [segment["name"] for segment in result["segments"]] == [
        "CCPG",
        "DCAI",
    ]
    assert "Level-1 completeness=ok" in result["judgment_basis"]


def test_derive_segments_yaml_empty_returns_none():
    assert derive_segments_yaml([]) is None
