# 最终报告合成指引

This file serves as the template and quality checklist for Phase 6 final report synthesis. The main session (NOT a sub-agent) reads reference.md, phase4_synthesis.md, investment_analyst.md, and produces the final report.

## Key Principles

- **Do NOT paste full analyst reports** — they live in `analyst_reports/`. Summarize each in 1 paragraph + link.
- **DO embed investment_analyst.md in full** — this is the most actionable section.
- **Use tables, bullet grids, and inline charts for readability** — this is a professional report, not a text dump.

## Report Structure

```markdown
# {行业名称} 产业趋势调研报告

**日期**: {date} | **数据截止**: {data_as_of_date} | **版本**: chain.yaml v{version}

---

## 一、产业链全景

{从 chain.yaml 按 layer 排序，用 ASCII 流程图展示产业链结构}

```
上游原材料          制造/设计              硬件/基础设施          软件/模型             终端市场
                                                                                  
高纯石英砂 ──→ 硅晶圆 ──→ 晶圆代工(3nm) ──→ AI加速芯片 ──→ AI服务器 ──→ 数据中心 ──→ 大模型 ──→ Agent ──→ 应用 ──→ 企业/个人
                    ↑ 半导体设备/EUV        ↑ HBM              ↑ 光模块            ↑ 电力  ↑ 政策  ↑ 资本
                    ↑ EDA/IP核              ↑ CoWoS先进封装
```

## 二、关键发现摘要 (Executive Summary)

> 用 5 条以内的 bullet，每条附上支撑数据，凸显最重要的洞察。

| # | 发现 | 支撑数据 | 影响 |
|---|------|----------|------|
| 1 | ... | ... | ↑/↓/→ |
| 2 | ... | ... | ... |

## 三、产业链各环节景气度速览

{按 layer 排序的景气度热力图}

| 层级 | 节点 | 景气度 | 方向 | 一句话判断 |
|------|------|--------|------|-----------|
| -5 | 高纯石英砂 | 6/10 | → | ... |
| ... | ... | ... | ... | ... |

> 完整分析报告: [节点名称](analyst_reports/{node_id}.md)

{为每个节点写 1-2 句摘要，然后链接到完整报告}

## 四、跨环节传导与综合研判

{从 phase4_synthesis.md 提取并优化格式}

### 传导热力图

{用简单的表格展示各边的传导强度}

| 传导路径 | 方向 | 强度 | 时滞 | 关键发现 |
|----------|------|------|------|----------|
| HBM → AI芯片 | 供给约束 | ████ 高 | 0-3月 | ... |
| CoWoS → AI芯片 | 供给约束 | ████ 高 | 0-6月 | ... |
| 大模型 → AI应用 | 成本推动 | ███ 中 | 1-6月 | ... |
| ... | ... | ... | ... | ... |

### 关键传导链

{提取 phase4_synthesis.md 中的传导链分析，用路径图 + 情景表格展示}

### 矛盾信号与研判

| 矛盾 | 信号A | 信号B | 研判 |
|------|-------|-------|------|
| ... | ... | ... | ... |

### 核心变量

| 排名 | 变量 | 当前值 | 关键阈值 | 突破后影响 |
|------|------|--------|----------|-----------|
| 1 | ... | ... | ... | ... |
| 2 | ... | ... | ... | ... |
| 3 | ... | ... | ... | ... |

## 五、投资与商业研判

**{完整粘贴 investment_analyst.md 的内容，不加修改}**

## 六、历史趋势对比

{Phase 5 内容。首次分析标注"首次分析，暂无历史对比"}

## 七、附录

### A. 数据质量
- 数据来源: {来源}
- 总数据量: {数量}
- 覆盖率: {百分比}

### B. 分析师报告索引
{从 reference.md 提取所有标题+链接}

### C. 执行统计
- Phase 3: {N} 个代理并行执行
- Phase 4: 1 个 Cross-Impact Analyst
- Phase 4.5: 1 个 Investment Analyst
- 总耗时: {时间}
```

## Quality Checklist

- [ ] Executive summary is a TABLE with supporting data (not just bullet points)
- [ ] Each node has ≤2 sentences + link to full report (no verbatim paste)
- [ ] Conduction heatmap shows ALL critical edges with intensity bars
- [ ] Investment analysis is pasted IN FULL from investment_analyst.md
- [ ] Core variables have SPECIFIC numeric thresholds and impact estimates
- [ ] Reference index in appendix links to ALL individual analyst reports
- [ ] No large text walls — use tables, grids, short paragraphs
