# 最终报告合成指引

This file serves as the template and quality checklist for Phase 6 final report synthesis. The main session (NOT a sub-agent) reads all Phase 3-5 outputs and produces the final report.

## Report Structure

```markdown
# {行业名称} 产业趋势调研报告
**日期**: {date}
**数据截止**: {data_as_of_date}
**产业链版本**: chain.yaml v{version}

---

## 一、产业链全景
{从 chain.yaml 渲染的递归结构概览，含各节点一句话描述和关系图}

## 二、关键发现摘要 (Executive Summary)
{3-5 条最重要的发现，每条不超过 3 句话}
1. ...
2. ...

## 三、产业链各环节深度分析
{按 layer 排序，从上游到下游}

### 3.1 {节点A} (layer -3)
{paste Node Analyst A 的完整报告}

### 3.2 {节点B} (layer -2)
...

### 3.N 政策与监管环境
{paste Policy Analyst 报告}

### 3.N+1 竞争格局
{paste Competition Analyst 报告}

## 四、跨环节传导与综合研判
{paste Phase 4 Cross-Impact Analyst 完整报告}

## 五、历史趋势对比
{paste Phase 5 对比结果，如为首次分析则标注"首次分析，暂无历史对比"}

## 六、投资与商业研判

### 6.1 行业景气度总评
- 当前评分: X/10
- 12个月展望: 评分 + 方向
- 关键假设: 列举支撑评分的前提条件

### 6.2 机会区域
- 短期 (3-6月): {最确定性机会}
- 中期 (6-18月): {需要持续验证的机会}
- 长期 (2年+): {结构性机会}

### 6.3 风险矩阵
| 风险 | 概率 | 影响 | 预警信号 | 应对策略 |
|------|------|------|----------|----------|
| ...  | 高/中/低 | 高/中/低 | ... | ... |

### 6.4 监控清单
{未来3个月需重点跟踪的指标列表 + 每个指标的阈值/触发条件}

## 七、附录
- A. 数据质量报告
- B. 数据源清单
- C. 代理执行状态
```

## Quality Checklist

- [ ] All Phase 3 analyst reports included verbatim (no summarization)
- [ ] Phase 5 trend diff included (or "首次分析" marker)
- [ ] Risk matrix has at least 5 entries
- [ ] Each opportunity in 6.2 has a verifiable trigger condition
- [ ] Monitoring checklist in 6.4 has specific numeric thresholds
- [ ] All sources cited with dates
