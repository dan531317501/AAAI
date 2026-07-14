"""把长桥分部数据（解析后的季度列表）转成紧凑CSV，喂LLM省token。"""
import csv
import io
import json
import os
import argparse


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


def main():
    import sys
    parser = argparse.ArgumentParser(description="长桥分部JSON转CSV")
    parser.add_argument("ticker", help="Ticker (e.g. 09988.HK, AAPL)")
    parser.add_argument("date", help="Analysis date YYYY-MM-DD")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--recent-n", type=int, default=8)
    args = parser.parse_args()

    output_dir = args.output_dir or os.path.join(os.path.dirname(__file__), "..", "data")
    day_dir = os.path.join(output_dir, args.ticker.upper().replace(".", "_"), args.date)
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
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
