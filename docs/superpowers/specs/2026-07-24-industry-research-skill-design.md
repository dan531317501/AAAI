# 产业趋势调研 Skill 设计方案

**日期**: 2026-07-24
**状态**: 设计中

---

## 一、目标

实现一个 `industry-research` Skill，用户指定任意行业（如"新能源汽车"、"AI"），Skill 自动：
1. 发现并建模该行业的完整产业链结构（递归向上到原料、向下到终端消费者）
2. 为每个产业链节点搜索并注册可靠的数据源
3. 采集量化指标 + 最新资讯
4. 多代理并行分析各环节 + 跨环节综合研判
5. 对比历史分析结果，识别趋势变化
6. 输出含信息汇总 + 投资/商业研判的深度报告

---

## 二、架构选择

选择 **Phase Pipeline（流水线式）**，理由：
- 深度调研场景可靠性优先，每阶段产出明确可验证
- 多代理分析阶段内部并行（N+2 个代理同时跑），整体耗时可控
- 产业链知识库（`chain.yaml`）作为副产品自然积累
- 复杂度适中，不引入不必要的抽象

---

## 三、整体工作流

```
Phase 1: 产业链发现与建模
  ├── 1.1 LLM 基于自身知识草拟 chain.yaml（递归向上/向下发现）
  ├── 1.2 网络搜索验证并补充产业环节、影响因子
  └── 产出: chain.yaml（持久化，下次可直接复用或更新）

Phase 2: 数据源注册与采集
  ├── 2.1 为每个影响因子搜索可靠数据源站点，注册到 sources.yaml
  ├── 2.2 执行数据采集，拉取近期历史数据 + 当前最新数据
  └── 产出: sources.yaml + data/{行业}/{日期}/ 下的结构化数据文件

Phase 3: 多代理并行分析（全部并行触发，单条消息）
  ├── N个 Node Analyst（每个产业链节点一个）
  ├── 1个 Policy Analyst（如支持层存在政策节点）
  ├── 1个 Competition Analyst（竞争格局）
  └── 产出: phase3_analyst_reports.md

Phase 4: 综合研判（1个代理，串行）
  ├── Cross-Impact Analyst 读取所有 Phase 3 报告
  ├── 沿边传导分析、矛盾信号检测、关键变量识别
  └── 产出: phase4_synthesis.md

Phase 5: 历史趋势对比（主 session 执行）
  ├── 查找该行业历史报告
  ├── diff: 因子权重变化、新增/消失因素、趋势拐点
  └── 产出: phase5_trend_diff.md

Phase 6: 最终报告（主 session 执行）
  ├── 汇总所有阶段产出 → 结构化报告
  └── 产出: reports/{DATE}/report.md + latest_report.md（双写）
```

**关键规则：**
- Phase 1 的 `chain.yaml` 持久化到行业目录，再次分析时直接用（可选更新）
- Phase 3 所有代理严格并行，各自只读自己需要的数据
- 历史数据仅用于对比，不依赖旧数据做当前研判

---

## 四、产业链数据模型（`chain.yaml`）

用有向图（DAG）建模产业链，而非固定层级结构。

```yaml
industry: AI
description: 人工智能产业
discovery_date: 2026-07-24

nodes:
  - id: silica
    name: 高纯石英砂
    description: 制造硅晶圆的核心原料
    key_factors: [高纯石英矿储量, 提纯技术壁垒]
    layer: -4  # 距中心节点的层数（负=上游, 仅用于排序展示）

  - id: wafer
    name: 硅晶圆
    key_factors: [12英寸产能, 全球前5大供应商集中度]
    layer: -3

  # ... 更多节点

  - id: consumer
    name: 个人消费者
    key_factors: [付费订阅率, 使用时长]
    layer: 3

edges:
  - from: silica
    to: wafer
    type: upstream  # upstream: A供给B | downstream: B依赖A
    mechanism: 石英砂纯度→晶圆质量→芯片良率

  # ... 更多边

# 外部支撑因素（不属于产业链本身，但施加影响）
supports:
  - id: energy
    name: 电力能源
    affects: [data_center, chip_fab]
    key_factors: [电价, 绿电比例, 电网容量]

  - id: ai_policy
    name: AI政策法规
    affects: [ai_chip, ai_model, ai_application]
    key_factors: [芯片出口管制, 数据安全法, AI监管, 算力补贴]

meta:
  version: 1
  last_updated: 2026-07-24
```

**设计要点：**
- `nodes` + `edges` 构成有向图，分析时沿 `edges` 传播影响
- `layer` 仅用于报告排序展示，不参与分析逻辑
- `supports` 独立于产业链，通过 `affects` 指向被影响的节点
- `key_factors` 是该节点分析时必须覆盖的核心议题
- 递归发现逻辑：向上问"需要什么原料/部件？"直到自然资源；向下问"为谁提供产品/服务？"直到终端消费者

---

## 五、数据源注册与采集（Phase 2）

### 数据源注册（`sources.yaml`）

```yaml
sources:
  battery_raw_material:
    - id: shanghai_lithium_price
      name: 碳酸锂现货价格
      url: https://www.smm.cn/quote/...
      fallback_url: https://.../lithium
      frequency: daily
      selector_type: api
      parser: lithium_price_parser
    - id: lme_cobalt_price
      name: LME钴期货价格
      url: https://www.lme.com/...
      fallback_url: https://...
      frequency: daily
      selector_type: api

  policy:
    - id: miit_ne_policy
      name: 工信部新能源汽车政策
      url: https://www.miit.gov.cn/...
      fallback_url: https://r.jina.ai/https://www.miit.gov.cn/...
      frequency: on_change
      selector_type: rss

meta:
  last_verified: 2026-07-24
  broken_sources: []
```

### 数据采集输出结构

```
data/{INDUSTRY}/reports/{DATE}/
├── chain.yaml              # 本轮使用的产业链模型（从行业目录复制）
├── sources.yaml            # 本轮使用的数据源配置
├── metrics.json            # 量化指标数据（价格、销量、产能等）
├── news.json               # 按节点分组的新闻/政策资讯
├── news_raw/               # 原始抓取缓存
├── metadata.json           # 采集审计信息
└── data_quality.json       # 数据质量报告
```

### 采集策略
- 已注册 API：直接用 Python requests
- 网页抓取：优先 `r.jina.ai` 代理，失败则直接 HTTP
- 新闻搜索：DuckDuckGo/SerpApi 按 `key_factors` 关键词搜索，`r.jina.ai` 读正文
- 每条数据标注置信度（官方来源/权威媒体/自媒体/未知）
- 采集失败不阻塞，记录到 `metadata.json`

---

## 六、多代理并行分析（Phase 3-4）

### Phase 3 代理生成规则

| 代理类型 | 数量 | 输入数据 | 职责 |
|----------|------|----------|------|
| Node Analyst | 每个 node 1个 | 该节点的 news + metrics | 分析该环节供需、价格、技术、竞争 |
| Policy Analyst | 1（如有政策 support） | 政策相关 news | 政策方向、力度、时间线、影响范围 |
| Competition Analyst | 1 | 全部 news | 跨环节竞争格局变化 |
| Cross-Impact Analyst | 1（Phase 4） | 全部 Phase 3 报告 | 沿边传导 + 综合研判 |

可配置 `--max-node-agents 10`，超出时合并相似节点。

### 统一输出格式

每个分析代理输出：
- **当前状态** — 关键指标现状 + 近3个月变化方向与幅度
- **驱动因素分析** — 主要驱动因素、新兴/弱化因素
- **传导效应**（仅 Node Analyst）— 对上游/下游的传导方向与成本影响
- **风险与不确定性** — 短期+中长期风险 + 监控信号
- **评分** — 景气度 1-10 + 置信度 高/中/低

### Phase 4 Cross-Impact Analyst

沿 `edges` 传导分析：外部冲击如何沿产业链传播（如"HBM涨价→AI芯片成本↑→服务器毛利压缩→CAPEX推迟"）。
输出：传导路径分析 + 矛盾信号标注 + TOP 2-3 关键变量 + 行业整体景气度评分。

---

## 七、历史趋势对比 + 最终报告（Phase 5-6）

### Phase 5 趋势对比

对比维度：各节点景气度变化、TOP关键变量变化、新增/弱化因素、趋势拐点信号。
历史数据仅用于对比，不依赖旧数据做当前研判。

### Phase 6 最终报告

双写：`reports/{DATE}/report.md`（归档） + `latest_report.md`（覆盖）。

报告结构：
1. 产业链全景
2. 关键发现摘要 (3-5条)
3. 各环节深度分析（按 layer 排序）
4. 跨环节传导与综合研判
5. 历史趋势对比
6. 投资与商业研判（景气度总评、机会区域、风险矩阵、监控清单）
7. 附录（数据质量、数据源清单、代理执行状态）

---

## 八、目录结构

```
skills/industry-research/
├── SKILL.md                       # Skill 编排流程
├── prompts/
│   ├── node_analyst.md            # 产业链节点分析师（通用模板）
│   ├── policy_analyst.md          # 政策分析师
│   ├── competition_analyst.md     # 竞争格局分析师
│   ├── cross_impact_analyst.md    # 跨环节传导与综合研判
│   └── report_synthesizer.md      # 最终报告合成指引
├── tools/
│   ├── fetch_chain.py             # Phase 1: 产业链发现
│   ├── fetch_sources.py           # Phase 2.1: 数据源搜索注册
│   ├── fetch_data.py              # Phase 2.2: 数据采集
│   ├── parsers/                   # 网站自定义解析器
│   │   ├── __init__.py
│   │   ├── smm_parser.py
│   │   └── ...
│   ├── requirements.txt
│   ├── tests/
│   │   ├── test_fetch_chain.py
│   │   ├── test_fetch_sources.py
│   │   ├── test_fetch_data.py
│   │   └── fixtures/
│   └── utils.py                   # 公共工具
└── data/                          # 运行时数据 (git ignored)
    └── {INDUSTRY}/
        ├── chain.yaml             # 产业链模型（持久化）
        ├── sources.yaml           # 数据源注册表（持久化）
        ├── latest_report.md       # 最新报告
        └── reports/
            └── {YYYY-MM-DD}/      # 按日期归档
                ├── chain.yaml
                ├── sources.yaml
                ├── metrics.json
                ├── news.json
                ├── news_raw/
                ├── metadata.json
                ├── data_quality.json
                ├── phase3_analyst_reports.md
                ├── phase4_synthesis.md
                ├── phase5_trend_diff.md
                └── report.md
```

---

## 九、架构约束

1. **Phase 1-2 可复用**：同一行业第二次分析时，`chain.yaml` + `sources.yaml` 直接使用，可选 `--refresh` 更新
2. **Phase 3 严格并行**：所有分析代理在同一消息中触发，各自读自己的数据文件
3. **历史数据仅对比**：Phase 5 的旧报告只用于 diff，不进入 Phase 3-4 的分析流程
4. **主 session 承担编排+合成**：Phase 5-6 在主 session 执行（非子代理），确保报告质量
5. **子代理自主文件 I/O**：Phase 3-4 的代理自己读取所需数据文件，主 session 不代读
