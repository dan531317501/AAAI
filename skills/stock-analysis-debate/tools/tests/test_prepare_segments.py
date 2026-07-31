from prepare_segments import (
    gen_yaml_from_data,
    normalize_sankey_data,
    to_sankey_csv,
)


def _node(key, name, value, level, yoy="", show_value=None):
    return {
        "key": key,
        "name": name,
        "value": str(value),
        "show_value": str(value if show_value is None else show_value),
        "yoy": str(yoy),
        "level": level,
    }


def _period(period, ccpg, dcai, consolidated, elimination):
    gross = ccpg + dcai
    return {
        "fiscal_year": int(period.split()[1]),
        "period": period,
        "report": period,
        "currency": "USD",
        "reconciliation_status": "ok",
        "nodes": [
            _node("bus_ccpg", "CCPG", ccpg, 1, "999"),
            _node("bus_dcai", "DCAI", dcai, 1, "999"),
            _node("total_rev", "营业收入", gross, 2, "999", consolidated),
            _node("gp", "毛利润", 40, 3, "999"),
            _node("bus_elimination", "部门间冲销", elimination, 3),
            _node("oper_inc", "营业利润", 10, 4, "999"),
        ],
        "links": [
            {"source": "bus_ccpg", "target": "total_rev", "value": str(ccpg)},
            {"source": "bus_dcai", "target": "total_rev", "value": str(dcai)},
            {"source": "total_rev", "target": "gp", "value": "40"},
            {"source": "gp", "target": "oper_inc", "value": "10"},
            {
                "source": "total_rev",
                "target": "bus_elimination",
                "value": str(elimination),
            },
        ],
    }


def _periods():
    return [
        _period("Q2 2025", 100, 50, 130, 20),
        _period("Q1 2026", 120, 60, 150, 30),
        _period("Q2 2026", 150, 75, 190, 35),
    ]


def test_to_sankey_csv_outputs_enriched_nodes_with_derived_parent():
    csv = to_sankey_csv(_periods(), recent_n=1)
    lines = csv.strip().split("\n")

    assert lines[0] == (
        "period,node_key,name,level,parent_key,row_type,value,show_value,"
        "gross_segment_mix_percent,qoq,yoy,longbridge_yoy_raw,"
        "segment_completeness_status,missing_segment_revenue,"
        "reconciliation_status"
    )
    assert len(lines) == 7
    assert (
        "Q2 2026,bus_ccpg,CCPG,1,total_rev,business_segment,150,150,"
        "66.666667,25,50,999,ok,0,ok"
    ) in csv
    assert (
        "Q2 2026,total_rev,营业收入,2,,revenue_total,225,190,,"
        "26.666667,46.153846,999,ok,0,ok"
    ) in csv
    assert (
        "Q2 2026,gp,毛利润,3,total_rev,gross_profit,40,40,,0,0,"
        "999,ok,0,ok"
    ) in csv
    assert (
        "Q2 2026,oper_inc,营业利润,4,gp,operating_profit,10,10,,"
        "0,0,999,ok,0,ok"
    ) in csv
    assert "Q1 2026" not in csv


def test_to_sankey_csv_empty_input_has_stable_header():
    assert to_sankey_csv([]).strip() == (
        "period,node_key,name,level,parent_key,row_type,value,show_value,"
        "gross_segment_mix_percent,qoq,yoy,longbridge_yoy_raw,"
        "segment_completeness_status,missing_segment_revenue,"
        "reconciliation_status"
    )


def test_to_sankey_csv_exports_missing_segment_detection():
    period = _period("Q2 2026", 60, 20, 60, 20)
    period["nodes"] = [
        node for node in period["nodes"] if node["key"] != "bus_dcai"
    ]

    csv = to_sankey_csv([period])

    assert ",missing,20,ok" in csv


def test_to_sankey_csv_rejects_accounting_reconciliation_mismatch():
    period = _period("Q2 2026", 60, 20, 80, 20)

    try:
        to_sankey_csv([period])
    except ValueError as exc:
        assert str(exc) == "revenue sankey reconciliation failed: Q2 2026"
    else:
        raise AssertionError("mismatched sankey data should be rejected")


def test_normalize_sankey_data_drops_business_historical_without_mutation():
    legacy = {
        "metadata": {"provider": "old"},
        "business_historical": [{"report_period": "2026.Q2"}],
        "revenue_sankey": _periods(),
    }

    normalized = normalize_sankey_data(legacy, ticker="INTC")
    latest = normalized["revenue_sankey"][-1]
    ccpg = latest["nodes"][0]

    assert set(normalized) == {"metadata", "revenue_sankey"}
    assert "business_historical" not in normalized
    assert normalized["metadata"]["provider"] == "Longbridge"
    assert ccpg["qoq"] == "25"
    assert ccpg["yoy"] == "50"
    assert ccpg["row_type"] == "business_segment"
    assert latest["segment_completeness_status"] == "ok"
    assert normalize_sankey_data(normalized, ticker="INTC") == normalized
    assert "row_type" not in legacy["revenue_sankey"][-1]["nodes"][0]


def test_gen_yaml_uses_latest_level_one_sankey_nodes():
    data = normalize_sankey_data(
        {"revenue_sankey": _periods()},
        ticker="INTC",
    )

    result = gen_yaml_from_data(data)

    assert result["multi_segment"] is True
    assert [segment["name"] for segment in result["segments"]] == [
        "CCPG",
        "DCAI",
    ]


def test_gen_yaml_empty_returns_none():
    assert gen_yaml_from_data({"revenue_sankey": []}) is None
    assert gen_yaml_from_data({}) is None
