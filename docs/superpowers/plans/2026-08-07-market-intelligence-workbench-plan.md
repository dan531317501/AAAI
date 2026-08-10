# 多市场市场情报工作台实施路线图

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在本地构建一个覆盖 A 股、港股和美股的市场情报 Web 工作台，提供实时/历史资金观察、四类可视化、热点新闻和五套视觉皮肤。

**Architecture:** 采用本地单体架构：Python 后端负责供应商适配、数据规范化、DuckDB 存储、任务调度和 HTTP API；React/TypeScript 前端负责图表、网络图、消息中心、筛选联动和皮肤系统。实现拆成三个独立子计划，均使用 fixture 数据完成可重复验证，再接入真实供应商。

**Tech Stack:** Python >=3.10、FastAPI、Uvicorn、Pydantic、DuckDB、pandas、yfinance、现有 Longbridge REST client；Node >=20、React、TypeScript、Vite、Apache ECharts、echarts-wordcloud、Cytoscape.js、Vitest。

## Global Constraints

- 市场范围固定为 A 股、港股、美股；时间必须同时保存 UTC 和市场本地时间。
- 实时采集粒度为可配置的 1、3 或 5 分钟；不实现 Level-2、逐笔盘口和自动下单。
- 原始指标、统一指标和派生指标分层保存，派生值必须可以重新计算。
- `standardized_flow_score` 默认使用日线最近 60 个有效交易日、日内最近 20 个同交易时段有效交易日的百分位窗口，计算 `round(200 * (p - 0.5))` 并限制在 `-100..100`；样本不足时不可用。
- 不同市场的原始资金字段不强行比较；只有标准化评分用于跨市场相对比较，价格/成交量估算必须标记为 `flow_proxy`。
- 离线回放必须使用显式 `as_of` 截止时间，禁止读取未来数据或用未来数据补缺。
- 凭据只从环境变量或操作系统安全存储读取，不进入普通日志、持久化消息和数据表。
- 现有未提交工作属于用户，实施时只修改任务列出的文件。
- 修改代码后必须同步更新根目录 `README.md`。
- 遵循用户约束：不采用“先写失败测试”的 TDD 流程；先完成最小实现，再用按真实语义编写的测试和验证命令检查漏洞。
- 所有测试从 `/Users/zhangqi.huang/aaai` 执行；命令按仓库约定使用 `rtk` 前缀。

## 子计划与依赖

### 子计划 A：数据底座

文件：`docs/superpowers/plans/2026-08-07-market-data-foundation-plan.md`

交付：独立的 Python 应用包、统一领域模型、DuckDB schema/repository、供应商能力接口、fixture provider、资金评分、交易日历、调度/恢复、离线回放和基础 API。

依赖：现有 Longbridge client 的可复用接口；真实 provider 能力必须通过适配器能力矩阵和有凭据的 smoke test 验证。没有凭据时仍必须支持 fixture provider 和离线模式。

### 子计划 B：可视化工作台

文件：`docs/superpowers/plans/2026-08-07-market-workbench-ui-plan.md`

交付：React/TypeScript 本地前端、统一筛选状态、每日扫描页、折线图、柱状图、Top 10 词云、关系网络图、历史回放入口和五套皮肤。

依赖：子计划 A 的 API 契约和 fixture 数据；先通过静态 fixture 验证交互，再接入真实 API。

### 子计划 C：新闻事件中心

文件：`docs/superpowers/plans/2026-08-07-news-event-center-plan.md`

交付：新闻 provider 接口、来源优先级、标准化、完全/近似去重、市场/行业/股票实体关联、相关性/影响力/可信度评分、事件聚类、新闻 API 和前端消息中心。

依赖：子计划 A 的 instrument/taxonomy/relation 数据契约和子计划 B 的前端 shell；新闻处理纯函数可在无网络 fixture 下独立验收。

## 执行顺序

1. 执行子计划 A，确保 `market_workbench` 能在无凭据、无网络情况下启动、写入 fixture 数据并提供 API。
2. 执行子计划 B 的前端 shell、筛选状态和基础图表；使用子计划 A 的 OpenAPI/fixture 响应。
3. 执行子计划 C 的新闻数据处理和 API，并在子计划 B 中接入消息中心与事件时间线。
4. 回到子计划 B 完成真实关系数据、网络图性能、五套皮肤和历史回放联动。
5. 按子计划 C 和 B 的最终任务同步根目录 README，完成跨层 smoke test 和完整验证。

## 集成验收

- 本地命令可以启动后端和前端，默认监听本机，不需要云端账号。
- 使用 fixture provider 可以看到 A/H/美股概览、资金折线、成交量柱状图、Top 10 词云和网络图。
- 选择历史 `as_of` 后，API 和所有图表不会读取截止时间之后的数据。
- 同一采集任务重复运行不会生成重复快照；重启后能补采最近缺口。
- 新闻可以关联市场、行业、主题和股票，并在新闻、图表和网络图之间联动。
- 五套皮肤只改变视觉 token，不改变数值、正负方向、单位和关系类型。
- provider 缺失、超时、限流、空数据和部分市场失败都在数据状态页可见。
- `rtk python -m pytest apps/market_workbench/tests -q`、`rtk npm --prefix frontend run test` 和前端生产构建均通过。
