# 官方披露文档结构化财务数据设计

## 背景与目标

当前官方财务层能够发现 SEC、HKEX 和 CNINFO 披露，但港股及 A 股披露主要以 PDF/HTML 文档存在，现有实现只保存链接并将 `facts` 置空，导致最新官方财务事实不能进入 `validated_metrics.toon`。

本次改造将官方披露文档作为可解析数据源：优先下载并确定性提取 PDF/HTML 中的财务事实；单个指标或文档无法解析时，按指标降级到现有免费 API；所有来源、期间、单位、币种和页码/URL 均保留，API 不得覆盖已经取得的官方事实。

## 设计

### 数据流

```text
SEC XBRL / HKEX / CNINFO discovery
        |
        +--> structured official payload (SEC Company Facts)
        |
        +--> PDF/HTML download and deterministic text extraction
        |       |
        |       +--> canonical official facts
        |
        +--> per-metric free API fallback (only missing metrics)
                |
                +--> fallback facts marked as non-official
```

PDF/HTML 解析使用文本层和规则映射，不使用 LLM。扫描型 PDF、无文本层、无法识别报告期/单位或无法形成可信指标时，解析结果只记录错误并进入 API 降级。

### 统一事实模型

每条事实至少包含：

- `metric`：统一指标名，如 `revenue`、`net_income_attributable_to_parent`、`diluted_eps`、`total_assets`；
- `value`、`unit`、`currency`；
- `period_start`、`period_end`、`period_type`；
- `filed_at`、`source`、`provider`、`source_url`；
- `source_page`、`source_excerpt`、`extraction_method`；
- `official` 和 `fallback_reason`，区分官方事实与免费 API 补充。

金额按披露单位转成基础单位，EPS 不应用报表的千/百万倍数。没有明确币种或期间的数字不进入 `facts`。

### 降级与覆盖规则

1. SEC XBRL 已有的结构化事实保持最高优先级。
2. HKEX/CNINFO PDF/HTML 解析事实使用 `HKEX_OFFICIAL_DOCUMENT_PARSER` 或 `CNINFO_OFFICIAL_DOCUMENT_PARSER`。
3. 解析失败或官方文档未提供某项指标时，使用免费 API 事实逐指标补缺，来源标记为 `YFINANCE_FREE_API`。
4. API 只能补充缺失的 `(metric, period_end, period_type)`，不能替换官方值。
5. 所有层均无值时保持缺失，`numeric_status` 继续为 `unavailable`。

### 产物与门禁

`official_financials.toon` 保存文档解析审计、API fallback 审计及最终事实；`validated_metrics.toon` 继续逐条暴露事实，不把 API fallback 伪装成官方事实。`data_quality.toon` 保留文档下载重试记录。

## 验收标准

- 中芯国际 HKEX 2025 年度业绩 PDF 能产出至少收入、归母净利润、经营现金流、总资产、归母权益和稀释 EPS 的官方事实，并保留页码和来源 URL；
- PDF 解析失败时能逐指标补充免费 API 数据，且不会覆盖官方事实；
- HTML 文档能走同一规范化管线；
- 解析失败且 API 失败时仍 fail-closed；
- 单元测试覆盖来源优先级、单位换算、期间识别、API 补缺和不覆盖规则；
- README 与 `SKILL.md` 同步说明新的官方文档解析边界。
