"""把长桥分部数据（解析后的季度列表）转成紧凑CSV，喂LLM省token。"""
import csv
import io
import json
import os
import argparse

from longbridge_fetcher import derive_segments_yaml


def to_csv(quarters: list, recent_n: int = 8) -> str:
    """quarters: parse_business_historical 的输出。取最近 recent_n 个季度。

    输出 CSV：segment,report_period,total_revenue,revenue,percent,yoy
    （每行一个分部×季度）。quarters 按 date 降序后取前 recent_n。
    """
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["segment", "report_period", "total_revenue", "revenue", "percent", "yoy"])

    sorted_q = sorted(quarters, key=lambda q: q.get("date", ""), reverse=True)
    for q in sorted_q[:recent_n]:
        period = q.get("report_period", "")
        total = q.get("total_revenue", "")
        for seg in q.get("segments", []):
            writer.writerow([
                seg.get("segment", ""),
                period,
                total,
                seg.get("revenue", ""),
                seg.get("percent", ""),
                seg.get("yoy", ""),
            ])
    return buf.getvalue()


def gen_yaml_from_data(data: dict) -> dict:
    """从 segments_financials.json 内容推导 segments.yaml 结构。无数据返回 None。"""
    if not data:
        return None
    bh = data.get("business_historical", [])
    if not bh:
        return None
    return derive_segments_yaml(bh)


def main():
    import sys
    parser = argparse.ArgumentParser(description="长桥分部数据预处理")
    parser.add_argument("ticker", help="Ticker (e.g. 09988.HK, AAPL)")
    parser.add_argument("date", help="Analysis date YYYY-MM-DD")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--recent-n", type=int, default=8)
    parser.add_argument("--gen-yaml", action="store_true",
                        help="同时生成 ticker 级 segments.yaml")
    args = parser.parse_args()

    output_dir = args.output_dir or os.path.join(os.path.dirname(__file__), "..", "data")
    ticker = args.ticker.upper()
    day_dir = os.path.join(output_dir, ticker.replace(".", "_"), args.date)
    json_path = os.path.join(day_dir, "segments_financials.json")

    if not os.path.exists(json_path):
        print(f"Error: {json_path} not found", flush=True)
        return 1

    with open(json_path) as f:
        data = json.load(f)

    quarters = data.get("business_historical", [])
    csv_text = to_csv(quarters, recent_n=args.recent_n)
    csv_path = os.path.join(day_dir, "segments_financials.csv")
    with open(csv_path, "w") as f:
        f.write(csv_text)
    print(f"Segments CSV written to {csv_path}", flush=True)

    if args.gen_yaml:
        import yaml
        yaml_struct = gen_yaml_from_data(data)
        if yaml_struct is None:
            print("No segment data to derive yaml", flush=True)
            return 1
        ticker_root = os.path.join(output_dir, ticker.replace(".", "_"))
        yaml_path = os.path.join(ticker_root, "segments.yaml")
        with open(yaml_path, "w") as f:
            yaml.dump(yaml_struct, f, allow_unicode=True, sort_keys=False)
        print(f"segments.yaml written to {yaml_path}", flush=True)
        flag = os.path.join(day_dir, "segments_missing.flag")
        if os.path.exists(flag):
            os.remove(flag)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
