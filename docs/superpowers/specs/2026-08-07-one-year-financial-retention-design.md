# 最近一年财务数据保留设计

## 目标

以 `analysis_as_of_date` 为截止日，仅抓取和保留最近 365 天内的财务数据；财务事实的主要过滤口径是 `period_end`，官方披露记录同时按 `filed_at` 限制，官方来源优先级和失败关闭语义保持不变。

## 范围

- 官方披露发现：只保留最近 365 天内发布的财报/定期报告记录。
- 官方 PDF/HTML 与 SEC XBRL：只保留 `period_end` 在窗口内的事实。
- 免费 API 财报表：只保留窗口内的列。
- `official_financials.toon`、`validated_metrics.toon` 和相关原始结构化产物继承同一窗口。
- 行情、新闻、宏观和其他已有更短窗口不改变。

## 边界

- 窗口起点为 `analysis_as_of_date - 365 days`，起止日期均包含。
- 未来期间不保留。
- 披露日期与报告期不同：披露记录按 `filed_at` 过滤，财务事实按 `period_end` 过滤。
- 官方数据只在窗口内参与合并；窗口外的 API 数据不能补入。
- 过滤后没有数据时，继续输出结构化的不可用/部分状态，不推导旧数据。

## 验收标准

- HKEX、SEC、CNINFO 的官方发现结果不会包含窗口外披露记录。
- SEC Company Facts、官方文档解析事实和 yfinance statement fallback 不包含窗口外 `period_end`。
- 官方事实仍然优先于同一指标/期间的免费 API 回退事实。
- 现有测试和新增边界测试全部通过，README 说明该口径。
