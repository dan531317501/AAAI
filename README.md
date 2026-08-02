# aaai

个人 AI/自动化实验仓库。

## 调研报告

- [AI 知识库全链路智能根因分析架构方案](../GolandProjects/afra-agent/AI知识库全链路智能根因分析架构方案.md)：面向线上告警驱动 RCA，覆盖代码/QA/API 知识加工、混合检索、实时证据验证、Agent 编排、安全治理、评测与渐进式落地路线。

## skills/translate-webpage-to-chinese

网页中文化 skill。输入公开网页 URL 或已保存的 HTML，抽取可翻译文本并生成简体中文 HTML；保留原始 DOM、CSS、图片、链接和响应式布局，代码与专业术语可保持原文。

核心流程：

1. `prepare` 抓取或读取网页，生成带稳定占位符的 HTML 与 `segments.json`。
2. Agent 按语义翻译文本段，输出 `translations.json`。
3. `apply` 只替换文本占位符，不重建页面。
4. `validate` 检查翻译覆盖、DOM 结构、样式引用与来源元数据。

生成结果会保留原页面脚本节点，但通过内容安全策略禁止执行脚本，避免客户端 hydration 将中文译文重新覆盖为原文。
默认以翻译效率为先，不执行浏览器截图对比或多视口验收；仅在直抓失败或发现明确问题时使用浏览器排查。

用法与故障降级策略参考 `skills/translate-webpage-to-chinese/SKILL.md`。

## skills/stock-analysis-debate

多智能体辩论式股票分析 skill。编排 Market/News/Social/Fundamentals 分析师 + Bull/Bear 辩论 + 风险辩论 + 组合经理，产出 Buy/Hold/Sell 建议。

报告日期固定使用本次执行日期，行情截止日期单独披露；每次执行只在对应日期目录生成一份 `analysis_report.md`，不会因行情数据滞后而在 `data_as_of_date` 目录重复输出。

分阶段交易计划统一输出新增仓位和累计仓位；任何风险辩论调整都必须重算后续阶段，最终累计仓位不得超过上限。未提供组合本金时不虚构资金和股数。

**数据源**：yfinance（OHLCV/基本面/财报/港股新闻）、长桥证券 API（A/H/美股最新日 K 兜底、HK/US 分部收入）、stockstats（技术指标）、新浪财经（CN 新闻 + HK 降级备用，翻页抓全）、东方财富（CN 公告）。

### 新闻处理流水（数据层去噪 + 分析层打分）

- **数据源路由**：港股优先 yfinance（质量高、噪声少），不足时降级到新浪翻页；A 股使用新浪翻页 + 东方财富公告。
- **分层保留**：近 7 天全量保留；8-30 天仅保留命中高信号词（财报/评级/价格战/并购/监管等）的新闻。
- **去重**：数据层做标题归一化后完全相同去重；近似重复（媒体洗稿）交由 News Analyst LLM 识别。
- **去噪**：关键词 + 来源黑名单过滤明显噪声（地缘无关/鸡汤/国旗等）。
- **打分标注**：News Analyst 对每条新闻打影响力分(0-3) + 标注业务线，输出高分事件表与业务线命中表。
- **证据可审计**：`news.txt` 为最终新闻分配稳定的 `[Nxxx]` 编号，标明 `title_only`/`summary` 内容层级并保留可用摘要；分析师只能在对应证据边界内陈述事实。
- **社交数据降级**：当前抓取链路不采集社交帖子或平台情绪指标，`news.txt` 显式记录 `social_data_available: false`；Social Media Analyst 必须输出 `Not Rated`，不得生成提及量、情绪分数或社区趋势。必要时最多抓取 3 篇高价值新闻正文辅助新闻叙事分析，但不得将其视为社交情绪数据。
- **单文件审计**：抓取、去重、去噪、内容层级和社交数据可用性统计直接追加到 `news.txt`；不再单独生成 `news_meta.txt`，重新抓取同一日期时会清理旧版审计文件。

### 股价数据兜底

- OHLCV 优先使用 yfinance；若数据未覆盖分析日当天或此前最近一个交易日，则调用长桥日 K API 补齐缺失交易日。
- 支持沪深 A 股、港股和美股代码；同一交易日已有 yfinance 数据时不会被覆盖。
- 长桥请求仅发送必需的 `x-app-id` Header，不携带浏览器指纹、设备 ID 或账户渠道信息。

### 多业务分部视角（仅 HK/US）

- **Phase 1.5**：`prepare_segments.py --gen-yaml` 以长桥 `revenue-sankey?report=qf` 为唯一分部数据源，生成 `revenue_sankey.json`、`revenue_sankey.csv` 和 ticker 级 `segments.yaml`。CSV 完整保留桑基节点，并按 `node_key` 本地计算 QoQ/YoY，补充节点分类、抵销前分部构成、合并勾稽和 Level-1 分部缺失检测；不再抓取或保存 `business_historical`。
- **Segment Analyst**：条件触发（`multi_segment: true`），与其他 Phase 2 分析师独立并行，读取增强后的 `revenue_sankey.csv` 和 `income_stmt.csv`，识别业务线增长/衰退拐点及长桥桑基口径下的利润结构变化，判断对集团股价综合方向；不依赖 News Analyst 的中间结果。
- **Phase 2 产物**：所有适用分析师返回后，由主会话将 4 或 5 份完整响应统一写入并校验 `phase2_analyst_reports.md`，再进入辩论阶段。
- **CN 市场不走业务线分析**（长桥无 A 股分部数据），退化为 4 分析师流程。
- **降级**：长桥抓取失败时生成 `segments_fetch_failed.flag`，跳过分部视角，不阻断分析。

### 工具模块

| 文件 | 职责 |
|------|------|
| `tools/fetch_data.py` | 主抓取流程（新浪翻页+去噪流水+长桥分部+flag），并把同口径估值、TTM EPS/P/E 对账和 GAAP 营业利润审计追加到 `fundamentals.txt` |
| `tools/financial_audit.py` | 使用最新有效收盘价与季度报表复算市值、P/B、简化 EV/EBITDA 和 TTM EPS/P/E；对比 provider 快照并输出冲突状态，同时区分 GAAP 报告营业利润与派生营业利润 |
| `tools/news_filter.py` | 新闻去重/去噪/分层保留及证据编号、内容层级序列化纯函数 |
| `tools/longbridge_fetcher.py` | 长桥日 K 兜底、counter_id、分部 API 抓取解析及清单推导 |
| `tools/prepare_segments.py` | 长桥桑基 JSON→增强 CSV + `--gen-yaml` 生成清单 |

### 测试

```bash
PYTHONPATH=skills/stock-analysis-debate/tools python -m pytest skills/stock-analysis-debate/tools/tests/ -v
```

### 用法

参考 `skills/stock-analysis-debate/SKILL.md`。
