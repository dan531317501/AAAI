#!/usr/bin/env python3
"""Assemble the final analysis report from the phase files' fixed-format summary blocks.

Two subcommands:

- `extract` — pull every `<!-- SUMMARY:BEGIN -->...<!-- SUMMARY:END -->` block out of
  each phase file and write it to `{DATE}/summaries/{file}.summary.md`. The orchestrator
  Reads these small files for Phase 7 decision synthesis. Stdout only reports counts
  (the block contents never enter the tool result unless printed).

- `build`   — write `analysis_report.md` by concatenating: header, Final Decision
  (from `final_decision.md`, which must exist), each section's summary blocks (re-extracted
  from the phase files), and per-section links to the full phase files. Final Decision
  is FIRST by construction.

The summary-block markers are the only thing this tool depends on; the content inside
the markers is free-form and role-specific (see Summary Block Protocol in SKILL.md).

Usage:
    python assemble_report.py {TICKER} {DATE} --output-dir <dir> extract
    python assemble_report.py {TICKER} {DATE} --output-dir <dir> build
"""

import argparse
import json
import re
import sys
from pathlib import Path

SUMMARY_RE = re.compile(r"<!-- SUMMARY:BEGIN -->(.*?)<!-- SUMMARY:END -->", re.S)

# (section title, source phase file, link target relative to the date dir)
SECTIONS = [
    ("1. Analyst Research", "phase2_analyst_reports.md", "phase2_analyst_reports.md"),
    ("2. Bull vs Bear Debate", "debate_history.md", "debate_history.md"),
    ("3. Investment Plan", "research_plan.md", "research_plan.md"),
    ("4. Trading Proposal", "trader_plan.md", "trader_plan.md"),
    ("5. Risk Assessment Debate", "risk_debate_history.md", "risk_debate_history.md"),
]


def extract_blocks(path: Path):
    """Return the list of summary-block contents (stripped) in file order."""
    text = path.read_text(encoding="utf-8")
    return [m.group(1).strip() for m in SUMMARY_RE.finditer(text)]


def read_data_as_of(date_dir: Path) -> str:
    dq = date_dir / "data_quality.json"
    if dq.exists():
        try:
            meta = json.loads(dq.read_text(encoding="utf-8"))
            return str(meta.get("data_as_of_date", "N/A"))
        except (json.JSONDecodeError, OSError):
            pass
    return "N/A"


def cmd_extract(args) -> int:
    date_dir = Path(args.output_dir) / args.ticker / args.date
    if not date_dir.is_dir():
        print(f"ERROR: date directory not found: {date_dir}", file=sys.stderr)
        return 1

    out_dir = date_dir / "summaries"
    out_dir.mkdir(exist_ok=True)
    missing = []
    for _, fname, _ in SECTIONS:
        path = date_dir / fname
        if not path.exists():
            print(f"WARN: {fname} not found", file=sys.stderr)
            missing.append(fname)
            continue
        blocks = extract_blocks(path)
        if not blocks:
            print(f"WARN: no summary block in {fname}", file=sys.stderr)
        out = out_dir / (fname.replace(".md", ".summary.md"))
        out.write_text("\n\n".join(blocks) + ("\n" if blocks else ""), encoding="utf-8")
        lines = len(blocks)
        print(f"{fname}: {lines} block(s) -> {out.name}")

    print(f"extract done: {len(SECTIONS) - len(missing)}/{len(SECTIONS)} files processed")
    return 0


def cmd_build(args) -> int:
    date_dir = Path(args.output_dir) / args.ticker / args.date
    if not date_dir.is_dir():
        print(f"ERROR: date directory not found: {date_dir}", file=sys.stderr)
        return 1

    final = date_dir / "final_decision.md"
    if not final.exists():
        print(f"ERROR: {final} not found — write final_decision.md first", file=sys.stderr)
        return 1

    parts = []
    parts.append(f"# Stock Analysis Report: {args.ticker} ({args.date})")
    parts.append("")
    parts.append(f"**Report Date**: {args.date} | **Market Data As Of**: {read_data_as_of(date_dir)}")
    parts.append("")
    parts.append("## Final Decision")
    parts.append("")
    parts.append(final.read_text(encoding="utf-8").strip())

    for title, fname, link in SECTIONS:
        parts.append("")
        parts.append(f"## {title}")
        path = date_dir / fname
        if not path.exists():
            print(f"WARN: {fname} not found — section placeholder only", file=sys.stderr)
            parts.append("")
            parts.append(f"完整报告: [{link}](./{link})")
            continue
        blocks = extract_blocks(path)
        if not blocks:
            print(f"WARN: no summary block in {fname}", file=sys.stderr)
            parts.append("")
            parts.append("*（该阶段文件无 summary 块，请参见完整报告）*")
        else:
            parts.append("")
            parts.append("\n\n".join(blocks))
        parts.append("")
        parts.append(f"完整报告: [{link}](./{link})")

    report = date_dir / "analysis_report.md"
    report.write_text("\n".join(parts) + "\n", encoding="utf-8")
    size = report.stat().st_size
    print(f"analysis_report.md written: {report} ({size} bytes, {len(parts)} lines)")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ticker", help="Stock ticker, e.g. QQQ")
    parser.add_argument("date", help="Analysis date in YYYY-MM-DD (the report date)")
    parser.add_argument("--output-dir", required=True, help="Data root, e.g. skills/stock-analysis-debate/tools/data")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("extract", help="Extract summary blocks into {DATE}/summaries/ for decision synthesis")
    sub.add_parser("build", help="Assemble analysis_report.md (Final Decision first)")

    args = parser.parse_args(argv)
    if args.command == "extract":
        return cmd_extract(args)
    return cmd_build(args)


if __name__ == "__main__":
    sys.exit(main())
