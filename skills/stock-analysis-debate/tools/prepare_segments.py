"""把长桥 revenue-sankey 数据标准化并导出紧凑 CSV。"""
import argparse
import copy
import csv
import io
import json
import os
import re

from longbridge_fetcher import (
    derive_segments_yaml,
    get_revenue_sankey_metadata,
    normalize_revenue_sankey,
)
from output_layout import resolve_ticker_paths


def _sankey_period(item: dict) -> str:
    return str(
        item.get("period")
        or item.get("report")
        or item.get("fiscal_year")
        or ""
    )


def _sankey_period_sort_key(item: dict) -> tuple:
    period = _sankey_period(item)
    match = re.search(r"Q([1-4])\s*(\d{4})", period, flags=re.IGNORECASE)
    if match:
        return int(match.group(2)), int(match.group(1))

    report = str(item.get("report", ""))
    match = re.search(r"(\d{4}).*?([一二三四])季", report)
    if match:
        quarter = {"一": 1, "二": 2, "三": 3, "四": 4}[match.group(2)]
        return int(match.group(1)), quarter

    try:
        return int(item.get("fiscal_year", 0)), 0
    except (TypeError, ValueError):
        return 0, 0


def _sankey_parent_key(node: dict, links: list) -> str:
    """从桑基 links 推导单层父节点；源节点自带 parent_key 时优先使用。"""
    if node.get("parent_key") not in (None, ""):
        return str(node["parent_key"])

    key = node.get("key")
    try:
        level = int(node.get("level"))
    except (TypeError, ValueError):
        return ""

    if level == 1:
        candidates = [
            link.get("target")
            for link in links
            if link.get("source") == key
        ]
    elif level > 2:
        candidates = [
            link.get("source")
            for link in links
            if link.get("target") == key
        ]
    else:
        candidates = []

    unique = []
    for candidate in candidates:
        if candidate not in (None, "") and candidate not in unique:
            unique.append(str(candidate))
    return "|".join(unique)


def to_sankey_csv(periods: list, recent_n: int = 8) -> str:
    """输出最近期间的完整桑基节点及本地派生分析字段。"""
    normalized = copy.deepcopy(periods or [])
    normalize_revenue_sankey(normalized)
    selected = sorted(
        normalized,
        key=_sankey_period_sort_key,
        reverse=True,
    )[:recent_n]

    mismatches = [
        _sankey_period(item)
        for item in selected
        if item.get("reconciliation_status") == "mismatch"
    ]
    if mismatches:
        raise ValueError(
            "revenue sankey reconciliation failed: " + ", ".join(mismatches)
        )

    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow([
        "period",
        "node_key",
        "name",
        "level",
        "parent_key",
        "row_type",
        "value",
        "show_value",
        "gross_segment_mix_percent",
        "qoq",
        "yoy",
        "longbridge_yoy_raw",
        "segment_completeness_status",
        "missing_segment_revenue",
        "reconciliation_status",
    ])
    for item in selected:
        period = _sankey_period(item)
        links = [
            link
            for link in item.get("links", [])
            if isinstance(link, dict)
        ]
        for node in item.get("nodes", []):
            if not isinstance(node, dict):
                continue
            writer.writerow([
                period,
                node.get("key", ""),
                node.get("name", ""),
                node.get("level", ""),
                _sankey_parent_key(node, links),
                node.get("row_type", ""),
                node.get("value", ""),
                node.get("show_value", ""),
                node.get("gross_segment_mix_percent", ""),
                node.get("qoq", ""),
                node.get("yoy", ""),
                node.get("longbridge_yoy_raw", ""),
                item.get("segment_completeness_status", ""),
                item.get("missing_segment_revenue", ""),
                item.get("reconciliation_status", ""),
            ])
    return buf.getvalue()


def normalize_sankey_data(data: dict, ticker: str = None) -> dict:
    """迁移为单一 revenue_sankey 契约，不保留 business_historical。"""
    normalized = copy.deepcopy(data or {})
    periods = normalized.get("revenue_sankey", [])
    normalize_revenue_sankey(periods)
    return {
        "metadata": get_revenue_sankey_metadata(ticker),
        "revenue_sankey": periods,
    }


def gen_yaml_from_data(data: dict) -> dict:
    """从 revenue_sankey.json 推导 segments.yaml。"""
    if not data:
        return None
    periods = data.get("revenue_sankey", [])
    if not periods:
        return None
    return derive_segments_yaml(periods)


def main():
    parser = argparse.ArgumentParser(description="长桥桑基数据预处理")
    parser.add_argument("ticker", help="Ticker (e.g. 09988.HK, AAPL)")
    parser.add_argument("date", help="Analysis date YYYY-MM-DD")
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument(
        "--output-dir",
        default=None,
        help="Base output directory; appends TICKER/DATE",
    )
    output_group.add_argument(
        "--ticker-data-dir",
        default=None,
        help="Exact ticker-level data directory; appends DATE only",
    )
    parser.add_argument("--recent-n", type=int, default=8)
    parser.add_argument(
        "--gen-yaml",
        action="store_true",
        help="同时生成 ticker 级 segments.yaml",
    )
    args = parser.parse_args()

    ticker = args.ticker.upper()
    output_dir = args.output_dir or os.path.join(
        os.path.dirname(__file__),
        "..",
        "data",
    )
    ticker_root, day_dir = resolve_ticker_paths(
        ticker,
        args.date,
        base_output_dir=output_dir,
        ticker_data_dir=args.ticker_data_dir,
    )
    json_path = os.path.join(day_dir, "revenue_sankey.json")

    if not os.path.exists(json_path):
        print(f"Error: {json_path} not found", flush=True)
        return 1

    with open(json_path) as handle:
        data = json.load(handle)

    data = normalize_sankey_data(data, ticker=ticker)
    csv_text = to_sankey_csv(
        data.get("revenue_sankey", []),
        recent_n=args.recent_n,
    )

    with open(json_path, "w") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)

    csv_path = os.path.join(day_dir, "revenue_sankey.csv")
    with open(csv_path, "w") as handle:
        handle.write(csv_text)
    print(f"Revenue sankey CSV written to {csv_path}", flush=True)

    if args.gen_yaml:
        import yaml

        yaml_struct = gen_yaml_from_data(data)
        if yaml_struct is None:
            print("No segment data to derive yaml", flush=True)
            return 1
        yaml_path = os.path.join(ticker_root, "segments.yaml")
        with open(yaml_path, "w") as handle:
            yaml.dump(yaml_struct, handle, allow_unicode=True, sort_keys=False)
        print(f"segments.yaml written to {yaml_path}", flush=True)
        flag = os.path.join(day_dir, "segments_missing.flag")
        if os.path.exists(flag):
            os.remove(flag)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
