"""Tests for assemble_report.py — final-report assembly from summary blocks.

Semantics under test:
- build 必须把 Final Decision 放在报告最前（header 之后第一个章节）。
- 各章节只含 summary 块内容 + 指向完整阶段文件的链接，不含阶段文件正文。
- extract 按固定标记提取全部块（多块、顺序），stdout 只报告数量。
- final_decision.md 缺失时 build 必须失败（退出码 1），避免产出无决策的报告。
- 无 summary 块 / 阶段文件缺失时降级为占位文案但流程不中断。
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from assemble_report import SECTIONS, extract_blocks, main

BULL_BLOCK = """<!-- SUMMARY:BEGIN -->
立场：看多，3-6 个月，目标 $714-719
核心：200 SMA 未破；MSFT 盈利兑现
<!-- SUMMARY:END -->"""

BEAR_BLOCK = """<!-- SUMMARY:BEGIN -->
立场：看空，目标 $643-650
核心：利率 4.7%+；AAPL 利润侵蚀
<!-- SUMMARY:END -->"""

ANALYST_BODY = (
    "<!-- SUMMARY:BEGIN -->\n趋势结论：长期多、中期回调\n关键价位：$680 / $701\n"
    "<!-- SUMMARY:END -->\n\n# 完整报告正文\n这里是不应进入最终报告的细节内容……"
)


def _phase_file(date_dir: Path, fname: str, content: str) -> Path:
    p = date_dir / fname
    p.write_text(content, encoding="utf-8")
    return p


@pytest.fixture
def date_dir(tmp_path: Path) -> Path:
    d = tmp_path / "data" / "QQQ" / "2026-08-03"
    d.mkdir(parents=True)
    (tmp_path / "data" / "QQQ" / "2026-08-03" / "data_quality.json").write_text(
        json.dumps({"data_as_of_date": "2026-07-31"}), encoding="utf-8"
    )
    return d


def test_build_puts_final_decision_first_and_uses_summaries_only(date_dir: Path, capsys):
    _phase_file(date_dir, "phase2_analyst_reports.md", ANALYST_BODY)
    _phase_file(date_dir, "debate_history.md", f"### Bull — Round 1\n\n{BULL_BLOCK}\n\n正文……")
    _phase_file(date_dir, "research_plan.md", "<!-- SUMMARY:BEGIN -->\n评级：SELL\n目标：$643-650\n<!-- SUMMARY:END -->\n\n计划正文……")
    _phase_file(date_dir, "trader_plan.md", "<!-- SUMMARY:BEGIN -->\n方向：SELL\n触发：$680\n<!-- SUMMARY:END -->\n\n提案正文……")
    _phase_file(date_dir, "risk_debate_history.md", f"### Aggressive — Round 1\n\n{BEAR_BLOCK}\n\n评估正文……")
    _phase_file(date_dir, "final_decision.md", "# Final Decision\n\n**评级**：Hold\n\n决策理由……")

    rc = main(["QQQ", "2026-08-03", "--output-dir", str(date_dir.parent.parent), "build"])
    assert rc == 0

    report = (date_dir / "analysis_report.md").read_text(encoding="utf-8")
    # Final Decision 是第一个章节（header 之后）
    assert report.index("## Final Decision") < report.index("## 1. Analyst Research")
    assert "# Final Decision" in report or "**评级**：Hold" in report
    # 各章节含 summary 内容与链接
    assert "趋势结论：长期多、中期回调" in report
    assert "立场：看多，3-6 个月，目标 $714-719" in report
    assert "评级：SELL" in report
    assert "方向：SELL" in report
    assert "立场：看空，目标 $643-650" in report
    for _, _, link in SECTIONS:
        assert f"[{link}](./{link})" in report
    # 阶段文件正文不进最终报告
    assert "不应进入最终报告的细节" not in report
    assert "正文……" not in report
    # 报告日期与数据截止日
    assert "**Report Date**: 2026-08-03" in report
    assert "**Market Data As Of**: 2026-07-31" in report
    out = capsys.readouterr().out
    assert "analysis_report.md written" in out


def test_build_fails_without_final_decision(date_dir: Path):
    _phase_file(date_dir, "research_plan.md", "x")
    rc = main(["QQQ", "2026-08-03", "--output-dir", str(date_dir.parent.parent), "build"])
    assert rc == 1
    assert not (date_dir / "analysis_report.md").exists()


def test_build_degrades_when_no_summary_block(date_dir: Path, capsys):
    _phase_file(date_dir, "phase2_analyst_reports.md", "全篇无 summary 标记的正文")
    _phase_file(date_dir, "final_decision.md", "决策")
    rc = main(["QQQ", "2026-08-03", "--output-dir", str(date_dir.parent.parent), "build"])
    assert rc == 0
    report = (date_dir / "analysis_report.md").read_text(encoding="utf-8")
    assert "无 summary 块" in report  # 占位文案
    assert "WARN: no summary block in phase2_analyst_reports.md" in capsys.readouterr().err


def test_extract_writes_blocks_and_only_counts_on_stdout(date_dir: Path, capsys):
    multi = (
        f"### Bull — Round 1\n\n{BULL_BLOCK}\n\n### Bull — Round 2\n\n"
        f"<!-- SUMMARY:BEGIN -->\n立场：维持看多\n<!-- SUMMARY:END -->\n"
    )
    _phase_file(date_dir, "debate_history.md", multi)
    _phase_file(date_dir, "phase2_analyst_reports.md", ANALYST_BODY)

    rc = main(["QQQ", "2026-08-03", "--output-dir", str(date_dir.parent.parent), "extract"])
    assert rc == 0

    out_dir = date_dir / "summaries"
    debate = (out_dir / "debate_history.summary.md").read_text(encoding="utf-8")
    # 多块按文件顺序拼接
    assert "立场：看多" in debate and "立场：维持看多" in debate
    assert debate.index("立场：看多") < debate.index("立场：维持看多")
    assert (out_dir / "phase2_analyst_reports.summary.md").exists()
    # stdout 只报告数量，不打印块内容
    out = capsys.readouterr().out
    assert "debate_history.md: 2 block(s)" in out
    assert "维持看多" not in out


def test_extract_reports_missing_file(date_dir: Path, capsys):
    rc = main(["QQQ", "2026-08-03", "--output-dir", str(date_dir.parent.parent), "extract"])
    assert rc == 0
    assert "not found" in capsys.readouterr().err


def test_extract_blocks_returns_stripped_contents_in_order(tmp_path: Path):
    p = tmp_path / "f.md"
    p.write_text(
        f"前文\n\n{BULL_BLOCK}\n\n中间\n\n<!-- SUMMARY:BEGIN -->\n  立场：X\n<!-- SUMMARY:END -->",
        encoding="utf-8",
    )
    blocks = extract_blocks(p)
    assert len(blocks) == 2
    assert blocks[0].startswith("立场：看多")
    assert blocks[1] == "立场：X"


def test_cli_invocation_build(date_dir: Path):
    """通过命令行入口验证（与主会话实际调用方式一致）。"""
    _phase_file(date_dir, "final_decision.md", "决策")
    _phase_file(date_dir, "research_plan.md", "<!-- SUMMARY:BEGIN -->\n评级：SELL\n<!-- SUMMARY:END -->\n正文")
    proc = subprocess.run(
        [sys.executable, str(Path(__file__).parent.parent / "assemble_report.py"),
         "QQQ", "2026-08-03", "--output-dir", str(date_dir.parent.parent), "build"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "analysis_report.md written" in proc.stdout
    assert (date_dir / "analysis_report.md").exists()
