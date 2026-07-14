# 股票分析 Skill 优化设计：新闻去噪 + 多业务分部视角

**日期**: 2026-07-14
**Skill**: `skills/stock-analysis-debate`
**状态**: 待实施

## 背景与问题

当前 stock-analysis-debate skill 在分析多业务公司（如阿里巴巴 09988.HK）时存在两个核心问题：

### 问题1：新闻噪声大且覆盖不足（数据层根因）

- `fetch_data.py` 的 `fetch_cn_news` / `fetch_hk_news` 抓取新浪 `vCB_AllNewsStock` 接口时**没有翻页**，默认只返回最新一页（约40条），导致 30 天窗口实际只覆盖最近 1-2 天。
- 没有任何去噪/相关性过滤：马云鸡汤文、霍尔木兹海峡港口、国旗、工商联研修等无关内容混入，真正的信号（菜鸟供应链拆分独立、券商维持"优于大市"点名"云业务增长引擎"、北水连续6日买入、爱诗科技领投）被淹没。
- 重复严重：同一条事件的媒体洗稿重复出现（如爱诗科技4条、菜鸟5条）。
- 关键事件（如"与美团打价格战"）要么在更早日期被翻页缺失吃掉，要么被噪声挤出。

### 问题2：多业务公司缺乏分部视角（分析架构缺失）

- 当前 4 个 analyst 中，`fundamentals_analyst` 只看 yfinance 合并报表，没有业务线拆分。
- 多业务公司（阿里：云/电商/本地生活/菜鸟/国际/大文娱）中，不同业务线对股价是相反方向的力量（如"云增长+30%"vs"本地生活亏损扩大"），合并看会互相抵消、看不出驱动因素。
- yfinance 本身不提供 segment reporting，需要新数据源。

## 设计决策（六轮澄清收敛）

| 维度 | 决定 |
|------|------|
| 新闻窗口 | 近7天全量翻页抓取 + 8-30天仅保留高信号事件（关键词粗筛） |
| 多业务处理 | 自动判别是否多业务；多业务才走业务线分析；**仅 HK/US 市场，CN 不走** |
| 去噪策略 | 数据层保守去重去噪（标题完全相同去重 + 黑名单过滤）+ 分析层 LLM 打分标注，全量保留可追溯 |
| 去重策略 | 数据层只做标题归一化后完全相同去重；近似重复（媒体洗稿）交给分析层 LLM 识别 |
| 嵌入方式 | 新闻打分并入 News Analyst（改 prompt）；业务线分析新增为 Phase 2 第5个并行 analyst（条件触发） |
| 业务线清单 | 按 ticker 缓存 `segments.yaml`；运行时扫描，缺失则生成分部硬数据来源：长桥 API（HK/US） |
| 分部数据 | 长桥 API1（business-historical）+ API2（revenue-sankey）直连抓取，预处理成 CSV 省 token |

## 第一块：数据层改造（`tools/fetch_data.py`）

### 1.1 新浪新闻翻页抓全

- `fetch_cn_news` / `fetch_hk_news` 增加 `Page=1..N` 翻页循环。
- 终止条件：抓到的新闻日期早于 `news_start`，或连续两页无新增条目。
- 解决"40条只覆盖1天"问题。

### 1.2 新闻窗口分层保留

- **近7天**：全量翻页抓取，全量保留（不漏近期催化，如价格战、领投、评级变动）。
- **8-30天**：用关键词粗筛，只保留标题命中高信号词的新闻。高信号词集合包括：财报/业绩/并购/评级/价格战/补贴/合作/监管/处罚/回购/增减持/分部/同比增长/下滑/亏损/盈利/拆分/独立。
- 窗口边界基于 `NEWS_LOOKBACK_DAYS=30`，7天为 `RECENT_NEWS_DAYS=7`。

### 1.3 去重（数据层仅完全相同去重）

- 标题归一化（去媒体前缀、去标点、去空白）后，**完全相同**的去重，只保留最早一条。
- **不做 SimHash 近似去重**。近似重复（媒体洗稿、同一事件不同表述）交给分析层 LLM 在打分阶段识别处理。

### 1.4 去噪（黑名单过滤）

- **来源黑名单**：明显非财经来源（社会类、情感类自媒体号）整条剔除。
- **关键词黑名单**：整条剔除标题命中无关关键词的新闻（地缘冲突无关项如"霍尔木兹/葬礼"、纯励志鸡汤、与公司无关的地名新闻）。
- 标题长度 < 8 的剔除（已有逻辑，保留）。

### 1.5 输出与审计

- 去重去噪后的全量保留条目仍写入 `news.txt`（C：数据层不打分，全量留给分析层）。
- 新增 `news_meta.txt` 记录：原始抓取数 / 去重数 / 去噪数 / 7天保留数 / 8-30天保留数 / 最终保留数，便于审计。

### 1.6 业务线清单与分部数据扫描（仅 HK/US）

- `fetch_data.py` 检查 `data/{TICKER}/segments.yaml`（**ticker 级、不带日期**，跨次复用）。
- HK/US 市场：调用长桥 API 抓取分部硬数据，存 `segments_financials.json`（当日目录）。
- CN 市场：不执行此线路，不抓取分部数据。
- 若 `segments.yaml` 不存在，写 `segments_missing.flag` 到当日目录，触发 Phase 1.5 生成。

### 1.7 长桥 API 抓取

两个 API，参数语义不同，分别处理：

**API1 — business-historical（季度分部收入历史）**
```
GET https://mr.lbkrs.com/api/forward/v2/stock-info/business-historical
    ?counter_id=ST/HK/{code去前导零}&report=qf&cate=business
```
返回 `data.historical[]`，每条含：`date`（报告期）、`report_txt`（如"2025.Q4"）、`total`（总收入）、`currency`、`business[]`（分部：`name`/`value`/`percent`/`yoy`）。

**API2 — revenue-sankey（财年收入→成本→利润桑基分解）**
```
GET https://mr.lbkrs.com/api/forward/v3/stock-info/revenue-sankey
    ?counter_id=ST/HK/{code去前导零}&report=annual
```
返回 `data.list[]`，按财年，含分部节点（`nodes[]`：`name`/`value`/`yoy`/`level`）。

**counter_id 规则**（已验证）：
- HK：`ST/HK/{code去前导零}` → `ST/HK/89988`（注意去前导零，与 yfinance/Sina 保留前导零相反）。
- US：`ST/US/{ticker}` → `ST/US/AAPL`。
- 请求头需带 `User-Agent: Mozilla/5.0`，否则可能被拒。

**已验证覆盖**：
- HK（89988）：✅ 两个 API 均返回完整分部数据。
- US（AAPL）：✅ 两个 API 均返回完整分部数据。
- CN A股（600519/000858）：❌ 返回 `historical:[]`，长桥无 A 股分部数据（符合方案：CN 不走此线路）。

**抓取失败兜底**：若长桥 API 连接失败或返回空（`historical:[]`），`fetch_data.py` 写 `segments_fetch_failed.flag`，Phase 1.5 据此降级——不生成 `segments.yaml`，Phase 2 不启动 Segment Analyst（退化为原有4-analyst流程）。

## 第二块：分部数据预处理脚本（`tools/prepare_segments.py`，新建）

**职责**：把 `segments_financials.json` 转成紧凑 CSV，喂 LLM 省 token。

**调用时机**：在 Phase 1.5 内调用（Phase 1 仅抓取原始 JSON，Phase 1.5 生成清单时同步跑预处理出 CSV）。不在 Phase 1 调用。

**输入**：`data/{TICKER}/{DATE}/segments_financials.json`

**输出**：`data/{TICKER}/{DATE}/segments_financials.csv`

**CSV 格式**（一行一个分部×季度）：
```
segment,report_period,total_revenue,revenue,percent,yoy
云智能集团,2025.Q4,32154000000,1243000000,3.87,20.11
商业,2025.Q4,32154000000,27241000000,84.72,
...
```

- 仅取最近 4-8 个季度（足够看拐点，避免历史过长）。
- 数值保留原始精度但去掉多余小数。
- 脚本独立可单测，参数：`prepare_segments.py <TICKER> <DATE> [--output-dir ...]`，与 `fetch_data.py` 风格一致。

## 第三块：Phase 1.5 业务线清单生成（仅 HK/US，串行）

**位置**：Phase 1（数据抓取）之后、Phase 2（analyst 并行）之前。串行执行。

**触发条件**：
- 市场为 HK 或 US，**且**当日目录存在 `segments_missing.flag`。
- CN 市场：跳过整个 Phase 1.5。
- 若存在 `segments_fetch_failed.flag`：跳过，不生成清单，Phase 2 不启动 Segment Analyst。

**步骤**（主会话直接执行，不起 agent）：
1. 读取 `segments_financials.csv`（预处理后）。
2. 从长桥返回的分部名直接生成 `segments.yaml`：
   - `multi_segment`：分部数 > 1，且非"所有其他/其他"单一分部占绝对主导（如 >90%）。
   - 每条 segment 含 `name`（规范名，取长桥分部名）、`aliases`（关键词别名，由 LLM 从常见简称补充）、`brief`（一句话说明）。
3. Write 到 `data/{TICKER}/segments.yaml`（ticker 级，跨次复用）。
4. 清理 `segments_missing.flag`。

**`segments.yaml` 结构**：
```yaml
multi_segment: true
judgment_basis: "长桥分部数据：商业/云智能/大文娱/本地生活/菜鸟 5个分部"
data_source: longbridge
segments:
  - name: 云智能集团
    aliases: [阿里云, 云计算, 通义, 飞天, AI]
    brief: 阿里旗下云计算与AI业务
  - name: 商业
    aliases: [淘宝, 天猫, 电商, 88VIP]
    brief: 中国商业+国际商业电商平台
```

**已有清单**：`data/{TICKER}/segments.yaml` 存在时，Phase 1.5 直接跳过（清单跨次复用，不重复生成长桥数据若已存在当日 CSV）。

## 第四块：分析层改造

### 4.1 News Analyst 改造（`prompts/news_analyst.md`）

prompt 改为两段式：
1. **打分标注**：对 `news.txt` 每条新闻打影响力分(0-3) + 标注涉及业务线（用 `segments.yaml` 的 `name`/`aliases` 匹配，若清单存在）。
   - 0 = 噪声（国旗/鸡汤/地缘无关）。
   - 1 = 边缘相关。
   - 2 = 相关但常规。
   - 3 = 高信号催化（价格战/评级变动/分部重大变化/并购/监管处罚/资金动向）。
2. **近似去重**：LLM 在打分时识别媒体洗稿/同一事件不同表述，同类只保留最高分一条进报告（全量仍留在 `news.txt`）。
3. **报告**：末尾附"高分事件表"（分≥2）+ "业务线命中表"（每条业务线命中的高分新闻数与方向）。

### 4.2 新增 Segment Analyst（`prompts/segment_analyst.md`，新建）

- **触发**：HK/US 且 `segments.yaml` 的 `multi_segment: true`。CN 或单业务公司跳过。
- **数据**：`segments_financials.csv`（分部硬数据）+ News Analyst 的业务线命中表。
- **任务**：
  1. 识别哪个业务线产生增长/衰退拐点（基于分部同比增速变化）。
  2. 判断该拐点对集团股价综合方向（正/负/中性）。
  3. 给出分部增速对比 + 拐点证据（引用具体季度数据 + 对应新闻）。
  4. 输出末尾附 Markdown 表格：业务线 / 最新增速 / 上期增速 / 拐点方向 / 股价影响。

## 第五块：工作流改动（`SKILL.md`）

### Phase 编号不变，Phase 2 条件扩展

- **Phase 1.5**（新增，串行，仅 HK/US）：业务线清单生成。
- **Phase 2**（并行）：原 4 个 analyst + Segment Analyst（条件触发）。
  - HK/US 且 `multi_segment: true`：5 个并行。
  - CN 或单业务公司：4 个并行（原样）。
- **Phase 3-7**：不变，但 Bull/Bear/Fundamentals 的 context 里**若存在** Segment Analyst 报告则一并粘贴。
- **instrument context 增补**：debate/judgment agent 需知道"该公司是 N 业务线集团，主驱动业务是 X"。

### Phase 1 数据抓取新增输出

`fetch_data.py` 输出文件表新增（仅 HK/US）：
| 文件 | 内容 | 来源 |
|------|------|------|
| `segments_financials.json` | 长桥原始分部数据 | 长桥 API1+API2（Phase 1 抓取） |
| `segments_financials.csv` | 预处理后的紧凑分部数据 | prepare_segments.py（Phase 1.5 调用） |
| `news_meta.txt` | 新闻抓取/去重/去噪审计统计 | fetch_data.py |
| `segments_missing.flag` | 清单缺失标记（触发 Phase 1.5） | fetch_data.py |
| `segments_fetch_failed.flag` | 长桥抓取失败标记（降级） | fetch_data.py |

ticker 级（不带日期）：
| 文件 | 内容 |
|------|------|
| `data/{TICKER}/segments.yaml` | 业务线清单（跨次复用） |

## 改动文件汇总

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `tools/fetch_data.py` | 修改 | 新浪翻页+7天全量/8-30天粗筛+标题去重+黑名单去噪+`news_meta.txt`；新增长桥API1/API2抓取（HK/US）；`segments.yaml`扫描 |
| `tools/prepare_segments.py` | 新建 | 长桥JSON→紧凑CSV，省token |
| `prompts/news_analyst.md` | 修改 | 加打分(0-3)+业务线标注+近似去重+高分事件表 |
| `prompts/segment_analyst.md` | 新建 | 分部拐点分析+股价综合方向 |
| `prompts/fundamentals_analyst.md` | 微调 | 引用Segment Analyst结论（若存在） |
| `SKILL.md` | 修改 | 增Phase 1.5；Phase 2条件触发第5 analyst；Phase 3-7 context增segment报告；CN标注不走业务线 |

## 失败降级

- 长桥 API 不可用（连接失败/返回空）：`segments_fetch_failed.flag` → 不生成清单 → Phase 2 退化为4-analyst流程，分析正常进行（只是缺分部视角）。
- `prepare_segments.py` 失败：同上降级。
- 新闻翻页失败：退化为现有单页抓取（不阻断），`news_meta.txt` 记录翻页失败。

## 不在本次范围

- CN 市场的业务线分析（明确排除，仅处理 HK/US）。
- 长桥 API 之外的财报分部附注抓取（如巨潮资讯年报HTML解析）——作为后续增强。
- WebSearch 兜底生成清单（HK/US 长桥已够，不需要）。
