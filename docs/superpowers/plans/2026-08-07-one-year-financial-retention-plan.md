# 最近一年财务数据保留 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让官方披露、官方结构化事实和免费 API 财报数据统一只保留相对于 `analysis_as_of_date` 最近 365 天的数据。

**Architecture:** 在官方披露层计算滚动窗口并过滤披露记录；在官方财务统一层按报告期过滤 SEC、文档解析和 API fallback 事实；在 yfinance statement 序列化前过滤列，保证落盘原始财报也遵守同一窗口。

**Tech Stack:** Python、pandas、pytest、TOON/JSON structured output。

## Global Constraints

- 窗口为 `analysis_as_of_date - 365 days` 至 `analysis_as_of_date`，首尾包含。
- 官方数据优先，免费 API 只能补齐缺失指标/期间，不能覆盖官方事实。
- 行情、新闻、宏观和其他已有更短窗口保持不变。
- 代码修改后同步更新 README。
- 不使用 LLM 从 PDF/HTML 提取数值。

---

### Task 1: 统一窗口工具与官方披露过滤

**Files:**
- Modify: `skills/stock-analysis-debate/tools/official_filings.py`
- Test: `skills/stock-analysis-debate/tools/tests/test_official_filings.py`

- [ ] 增加窗口起点计算，并让 HKEX、SEC submissions、CNINFO 发现结果按 `filed_at` 保留窗口内记录。
- [ ] 让 SEC Company Facts 同时按 `filed` 和 `period_end` 过滤。
- [ ] 增加窗口边界、未来期间和窗口外记录测试。

### Task 2: 统一财务事实与 API statement 过滤

**Files:**
- Modify: `skills/stock-analysis-debate/tools/official_financials.py`
- Test: `skills/stock-analysis-debate/tools/tests/test_official_financials.py`

- [ ] 过滤文档解析事实和 SEC normalized facts 的 `period_end`。
- [ ] 过滤 yfinance statement CSV 的列后再进入官方/API 合并。
- [ ] 验证官方事实覆盖窗口内同键 fallback，窗口外 fallback 不进入结果。

### Task 3: 原始财报落盘、文档和回归验证

**Files:**
- Modify: `skills/stock-analysis-debate/tools/fetch_data.py`
- Modify: `README.md`
- Test: `skills/stock-analysis-debate/tools/tests/`

- [ ] 在 yfinance statement 输出前应用同一滚动一年过滤。
- [ ] README 补充窗口和边界语义。
- [ ] 运行完整测试、差异检查，并用一个真实标的刷新数据验证落盘范围。
