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

多智能体辩论式股票分析 skill。编排 Market/News/Social/Fundamentals 基础分析师、Price Action Attribution（价格行为归因）分析师、Bull/Bear 辩论、风险辩论和组合经理，解释近期涨跌并产出 Buy/Hold/Sell 建议。

每次分析严格分离数据与报告：原始/派生数据写入 `skills/stock-analysis-debate/reposrts/{TICKER}/data/{DATE}/`，分析报告和流程产物写入 `skills/stock-analysis-debate/reposrts/{TICKER}/reports/{DATE}/`。报告日期固定使用本次执行日期，行情截止日期单独披露；每次执行只在报告目录生成一份 `analysis_report.md`，不会因行情数据滞后而在 `data_as_of_date` 目录重复输出。

分阶段交易计划统一输出新增仓位和累计仓位；任何风险辩论调整都必须重算后续阶段，最终累计仓位不得超过上限。未提供组合本金时不虚构资金和股数。

编排采用 context 卫生原则：辩论/风险 Agent 按文件 I/O 协议自写历史文件并仅返回状态确认或精简摘要；主会话只传递文件路径、不向 Agent prompt 粘贴文件内容；主会话 context 仅保留编排与决策所需内容，避免全文重复驻留。

最终 `analysis_report.md` 以 **Final Decision 置顶**，并单列价格行为归因章节；Phase 7 的算术复核由独立 Arithmetic Verifier 子代理完成（不占用主会话上下文，输出 `arithmetic_verification.md`），主会话按最终主张读取必要的独立分析师报告、辩论历史和验证结论后撰写摘要，并附带各完整报告链接。

**数据源**：yfinance（OHLCV、大盘/行业代理、历史财报预期差、评级行动、基本面/财报/港股新闻）、长桥证券 API（A/H/美股最新日 K 兜底、HK/US 分部收入）、stockstats（技术指标）、新浪财经（CN 新闻 + HK 降级备用，翻页抓全）、东方财富（CN 公告）。

### 价格行为归因

- **两步编排**：Phase 2 Step 1 并行运行基础分析师并分别落盘；所有可用报告完成后，Step 2 顺序运行 Price Action Attribution Analyst，输出 `price_action_attribution_analyst.md`，然后才进入 Bull/Bear 辩论。
- **归因链路**：按 `Expectation Baseline → Trigger/Surprise → Transmission/Amplifier → Observed Price Move → Fundamental Anchor → Conditional Outlook` 分析，区分事前预期、新信息、资金/市场结构放大和基本面持续性。
- **相对表现**：`price_context.json` 提供目标股票与大盘/行业代理的 1/5/20 个交易时段绝对收益、超额收益和最近 60 个交易时段对齐序列；主要同行仅在能够说明可比关系并取得同窗口行情时补充，否则标为 `Not Rated`；单个代理获取失败时独立降级。
- **预期证据**：`expectations.txt` 保存 yfinance 财报预期差记录、近 90 日评级行动和抓取时点一致预期快照；抓取时点快照不得反向充当历史事件前预期，缺少事前一致预期时“超预期/已计价”结论必须 `Not Rated`。
- **证据分级**：候选原因按 Strongly Supported / Supported / Plausible / Rejected / Not Rated 排序，必须同时列支持证据、反证、缺失证据和至少一个竞争解释。
- **因果边界**：超买/超卖只是状态；RSI、价格和成交量不能识别买卖方；强平、逼空、外资/机构流向必须有对应杠杆、借券或资金流证据。该角色不输出评级、目标价、仓位或交易建议。
- **前瞻输出**：分别给出未来 1 周、1—2 个月、3—12 个月的延续/反转条件、验证节点、失效条件与置信等级，由后续 Bull/Bear、Research Manager 和 Portfolio Manager 挑战和裁决。

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
- **Phase 2 产物**：每个适用分析师子代理将完整结果直接写入 `reposrts/{TICKER}/reports/{DATE}/` 下的独立 `*_analyst.md` 文件，并只向主会话返回写入确认；不再生成聚合或总结文件。Step 2 归因分析师读取所有可用 Step 1 报告，Phase 3-7 再根据当前职责按需读取独立报告和原始数据。
- **CN 市场不走业务线分析**（长桥无 A 股分部数据），Step 1 为 4 个基础分析师，随后仍运行 Price Action Attribution Analyst。
- **降级**：长桥抓取失败时生成 `segments_fetch_failed.flag`，跳过分部视角，不阻断分析。

### 工具模块

| 文件 | 职责 |
|------|------|
| `tools/fetch_data.py` | 主抓取流程（相对表现/预期上下文+新浪翻页+去噪流水+长桥分部+flag），并把同口径估值、TTM EPS/P/E 对账和 GAAP 营业利润审计追加到 `fundamentals.txt` |
| `tools/price_attribution_data.py` | 选择可解释的大盘/行业代理，计算 1/5/20 时段绝对与超额收益，序列化最近 60 时段对齐行情，并输出带点时使用边界的财报预期差和评级行动 |
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
