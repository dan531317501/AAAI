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

时间模式默认是 `current_research`，其中 `{DATE}` 必须等于本地当天。历史分析必须显式使用 `historical_replay` 并通过 `--as-of-date` 提供市场时区下的日终截止日；目录仍使用真实执行日期，报告明确标记为历史回放，不能伪装成当时生成的报告。

```bash
# 当前研究
python skills/stock-analysis-debate/tools/fetch_data.py AAPL "$(date +%F)" --ticker-data-dir skills/stock-analysis-debate/reposrts/AAPL/data

# 历史回放（执行目录仍是今天）
python skills/stock-analysis-debate/tools/fetch_data.py AAPL "$(date +%F)" --analysis-mode historical_replay --as-of-date 2024-05-01 --ticker-data-dir skills/stock-analysis-debate/reposrts/AAPL/data
```

默认采用 `research_only`：未提供完整组合画像时只输出证券研究结论、入场/失效条件，并将仓位标记为 Not Rated，不输出任何配置百分比、资金或股数。只有用户明确提供完整真实组合上下文，或明确要求并完整定义假设模型组合时，才按风险预算、压力损失、流动性及集中度约束的最小值计算仓位；Agent 一致或投票不能提高仓位。

编排采用 context 卫生原则：辩论/风险 Agent 按文件 I/O 协议自写历史文件并仅返回状态确认或精简摘要；主会话只传递文件路径、不向 Agent prompt 粘贴文件内容；主会话 context 仅保留编排与决策所需内容，避免全文重复驻留。

最终 `analysis_report.md` 以 **Final Decision 置顶**，并单列价格行为归因章节。所有币种识别、连续季度校验、TTM/估值运算、预测表语义、重试降级和数据门禁都在工具层完成，默认输出 `validated_metrics.toon` 与 `validation_report.md`；Phase 7 优先引用数据目录中已有的工具派生值，不用 LLM 重算收益率、增长率、TTM、利润率、估值倍数或技术指标，仅对目标价、仓位等工作流明确要求的决策公式展示可追溯输入和计算过程。

### 数据完整性、币种与官方披露降级

- **统一请求运行时**：yfinance、Longbridge 和官方披露接口对连接失败、超时、HTTP 408/429/5xx 做指数退避重试；400/401/403、结构错误等不可恢复问题立即失败。每次尝试写入 `data_quality.toon` 的 `provider_retry_events`。
- **目录级数值证据契约**：当前运行 `reposrts/{TICKER}/data/{DATE}/` 下由 `SKILL.md` 列出的有效产物共同构成数值依据，每个重要数字须追溯到文件、字段/行及期间。`validated_metrics.toon` 对其覆盖的指标及全部决策门禁具有优先约束；缺失、过期、冲突或被阻断的覆盖指标不能改从其他文件绕过，只能输出 N/A/Not Rated。
- **历史时点契约**：`data_quality.toon` 与 `validated_metrics.toon` 同时保存 `execution_date`、`analysis_as_of_date`、市场时区 `analysis_timestamp`、`retrieved_at` 和逐来源 `source_statuses`。历史回放只允许截止日前的行情/相对收益、具有可解析发布时间的新闻及已提交官方披露；当前财务快照、报表、一致预期/修订/评级/目标价、内部人、期权、无 vintage 宏观、预测市场、全局新闻搜索、FX 当前元数据和分部快照全部自动降级为 Not Rated。SEC Company Facts 在落盘前按 `filed_at <= analysis_as_of_date` 裁剪。
- **结构化输出**：`tools/structured_io.py` 统一负责 JSON 数据模型的 TOON/JSON 编解码、严格往返校验和原子落盘。`STRUCTURED_OUTPUT_FORMAT = "toon"` 为默认值；改成 `"json"` 后所有结构化文件统一输出 JSON。成功写入时会删除同名的另一格式，读取时可兼容历史 `.json`/`.toon` 文件。
- **双币种建模**：分别保存交易币种 `quote_currency` 和财报/预测币种 `financial_currency`。跨币种 P/E、P/B、EV/EBITDA 和目标价必须使用分析日附近的有效 FX；无有效汇率时禁止精确估值。
- **预测语义纠正**：`info.revenueGrowth` 和 `info.earningsGrowth` 仅表示最近季度历史同比；一致预期来自专门的 earnings/revenue estimate、EPS trend/revisions 接口，并保留每行币种和分析师数量。
- **连续季度门禁**：TTM 只接受四个连续财季。即使存在四个非空值，只要整季缺失形成时间断档，也不会用更老季度回填。
- **目标价与强评级门禁**：P/E 型目标价要求正的 TTM EPS/P/E、连续季度、有效币种/汇率，以及期间、币种、均值和分析师数量均有效的年度一致预期；`gate_details` 记录所有阻断原因和实际采用的预期期间。Buy/Sell 除数值门禁外，还必须在最终决策阶段具备相对收益、可追溯催化剂和投资逻辑失效条件，否则降级为 Overweight/Underweight/Hold。
- **期权活动解释边界**：US 期权快照只描述成交/OI 构成、成交集中位置和近似 ±5% moneyness IV 相对定价。`volume > 2× prior OI` 仅标记异常活动，不能证明新开仓、资金方向、策略或参与者身份；期权证据不直接决定评级、目标价、仓位或风险上限。方法依据见 `skills/stock-analysis-debate/reference/options-volume-open-interest-and-sentiment.en.md`。
- **组合适用性门禁**：`research_only`、`model_portfolio`、`portfolio_context_complete` 三种模式由 `prompts/portfolio_policy.md` 统一约束；任何必需字段缺失都会降级为 `research_only`。数值仓位必须展示所有约束、风险预算公式及最终绑定项，不能使用默认百分比或多 Agent 投票结果。
- **官方披露降级**：港股发现 HKEXnews 财报公告，美股接 SEC EDGAR submissions 与 Company Facts XBRL，A 股接 CNINFO 法定披露。只有结构化字段进入数值管线；未结构化 PDF 仅作为证据链接，禁止 LLM 从中抽数。调用 SEC 时建议按其自动访问规范设置 `SEC_USER_AGENT="组织名 contact@example.com"`；未配置或被拒绝时显式降级，不伪造联系信息。
- **长桥口径边界**：Longbridge 桑基币种标记为 `translated_only`。没有原始报告币种和换算汇率时，只能用于分部构成背景，不能作为官方经营增长或跨币种估值依据。

**数据源**：yfinance（OHLCV、大盘/行业代理、历史财报预期差、评级行动、基本面/财报/港股新闻）、长桥证券 API（A/H/美股最新日 K 兜底、HK/US 分部收入）、stockstats（技术指标）、新浪财经（CN 新闻 + HK 降级备用，翻页抓全）、东方财富（CN 公告）。

### 价格行为归因

- **两步编排**：Phase 2 Step 1 并行运行基础分析师并分别落盘；所有可用报告完成后，Step 2 顺序运行 Price Action Attribution Analyst，输出 `price_action_attribution_analyst.md`，然后才进入 Bull/Bear 辩论。
- **归因链路**：按 `Expectation Baseline → Trigger/Surprise → Transmission/Amplifier → Observed Price Move → Fundamental Anchor → Conditional Outlook` 分析，区分事前预期、新信息、资金/市场结构放大和基本面持续性。
- **相对表现**：`price_context.toon` 提供目标股票与大盘/行业代理的 1/5/20 个交易时段绝对收益、超额收益和最近 60 个交易时段对齐序列；主要同行仅在能够说明可比关系并取得同窗口行情时补充，否则标为 `Not Rated`；单个代理获取失败时独立降级。
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

- **Phase 1.5**：`prepare_segments.py --gen-yaml` 以长桥 `revenue-sankey?report=qf` 为唯一分部数据源，生成 `revenue_sankey.toon`、`revenue_sankey.csv` 和 ticker 级 `segments.yaml`。CSV 完整保留桑基节点，并按 `node_key` 本地计算 QoQ/YoY，补充节点分类、抵销前分部构成、合并勾稽和 Level-1 分部缺失检测；不再抓取或保存 `business_historical`。
- **Segment Analyst**：条件触发（`multi_segment: true`），与其他 Phase 2 分析师独立并行，读取增强后的 `revenue_sankey.csv` 和 `income_stmt.csv`，识别业务线增长/衰退拐点及长桥桑基口径下的利润结构变化，判断对集团股价综合方向；不依赖 News Analyst 的中间结果。
- **Phase 2 产物**：每个适用分析师子代理将完整结果直接写入 `reposrts/{TICKER}/reports/{DATE}/` 下的独立 `*_analyst.md` 文件，并只向主会话返回写入确认；不再生成聚合或总结文件。Step 2 归因分析师读取所有可用 Step 1 报告，Phase 3-7 再根据当前职责按需读取独立报告和原始数据。
- **CN 市场不走业务线分析**（长桥无 A 股分部数据），Step 1 为 4 个基础分析师，随后仍运行 Price Action Attribution Analyst。
- **降级**：长桥抓取失败时生成 `segments_fetch_failed.flag`，跳过分部视角，不阻断分析。

### 工具模块

| 文件 | 职责 |
|------|------|
| `tools/fetch_data.py` | 主抓取流程（相对表现/预期上下文+新浪翻页+去噪流水+长桥分部+flag），并把同口径估值、TTM EPS/P/E 对账和 GAAP 营业利润审计追加到 `fundamentals.txt` |
| `tools/provider_runtime.py` | 统一错误分类、指数退避重试、响应校验和请求审计轨迹 |
| `tools/official_filings.py` | HKEXnews、SEC EDGAR/XBRL、CNINFO 官方披露发现与结构化数据边界 |
| `tools/data_validation.py` | API 币种识别、分析日汇率、预测表标准化、数值契约和决策门禁 |
| `tools/temporal_policy.py` | 当前研究/历史回放日期校验、市场时区截止点、逐来源时点许可、历史快照降级与新闻时间过滤 |
| `tools/structured_io.py` | JSON→TOON 转换、TOON/JSON 格式开关、严格往返校验、原子写入与历史格式兼容读取 |
| `tools/price_attribution_data.py` | 选择可解释的大盘/行业代理，计算 1/5/20 时段绝对与超额收益，序列化最近 60 时段对齐行情，并输出带点时使用边界的财报预期差和评级行动 |
| `tools/financial_audit.py` | 校验四个连续财季，按分析日 FX 把交易币种转换为财报币种后复算市值、P/B、简化 EV/EBITDA 和 TTM EPS/P/E；币种或周期不完整时阻断精确值 |
| `tools/news_filter.py` | 新闻去重/去噪/分层保留及证据编号、内容层级序列化纯函数 |
| `tools/longbridge_fetcher.py` | 长桥日 K 兜底、counter_id、分部 API 抓取解析及清单推导 |
| `tools/prepare_segments.py` | 长桥桑基 TOON/JSON→增强 CSV + `--gen-yaml` 生成清单 |

### 测试

```bash
PYTHONPATH=skills/stock-analysis-debate/tools python -m pytest skills/stock-analysis-debate/tools/tests/ -v
```

### 用法

参考 `skills/stock-analysis-debate/SKILL.md`。
