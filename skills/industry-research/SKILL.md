---
name: industry-research
description: Use when the user wants to research industry trends, discover the full industry chain (upstream to downstream), analyze key influencing factors (policy, supply-demand, competition, technology), and produce a comprehensive report with investment/business recommendations.
---

# Industry Trend Research

## Overview

Conduct a deep industry chain analysis by:
1. Discovering the complete industry chain (recursive: upstream to raw materials, downstream to end consumers)
2. Registering reliable data sources for each chain node's key factors
3. Collecting quantitative metrics and news via search
4. Dispatching parallel analyst agents for each node + specialization
5. Synthesizing cross-node impact propagation
6. Comparing against historical analyses to detect trend shifts
7. Producing a final report with both information synthesis and actionable recommendations

## Critical Execution Rules

1. **NEVER ask the user for permission between phases.** Run all phases continuously.
2. **Phase 3 agents are ALL launched in a SINGLE message as parallel Agent calls.** Do not use `run_in_background`.
3. **Phase 5-6 run in the main session**, not as sub-agents.
4. **Phase 6 MUST produce TWO outputs in ONE batch: Write (report.md) + Write (latest_report.md) + text summary.**
5. **Historical data is for COMPARISON only — never for current analysis.**

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `industry` | (required) | Industry name in Chinese or English |
| `date` | today | Analysis date YYYY-MM-DD |
| `--refresh-chain` | false | Re-discover chain even if chain.yaml exists |
| `--refresh-sources` | false | Re-search data sources even if sources.yaml exists |
| `--max-node-agents` | 10 | Max parallel node analysts (merge similar nodes if exceeded) |

## Workflow

### Phase 1: Chain Discovery and Modeling

**Goal**: Produce `data/{INDUSTRY}/chain.yaml`

1. Check if `skills/industry-research/data/{INDUSTRY}/chain.yaml` exists.
   - If exists AND `--refresh-chain` is NOT set: Read it, validate with `validate_chain()`, proceed to Phase 2.
   - If missing OR `--refresh-chain` is set: Continue to step 2.

2. Run `fetch_chain.py --init` to create a skeleton:
   ```bash
   cd skills/industry-research/tools && python -c "
   from fetch_chain import init_chain
   from pathlib import Path
   init_chain('{INDUSTRY}', Path('..') / 'data' / '{INDUSTRY_SAFE}' / 'chain.yaml')
   "
   ```

3. **LLM drafts the chain** — Use the main session's knowledge + WebFetch:
   - Start from the input industry as center
   - **Recurse upstream**: For each node, ask "what raw materials/components does this need?" until reaching basic natural resources or commodities
   - **Recurse downstream**: For each node, ask "who consumes/uses this? what does it enable?" until reaching end consumers
   - Identify 2-5 `key_factors` per node (what drives this node?)
   - Draft `edges` between nodes (upstream = A supplies B, downstream = B depends on A)
   - Identify `supports` — external factors that affect nodes but aren't part of the chain itself

4. **Validate with web search** — For each node and key_factor, run 1-2 web searches to verify:
   - Does this node actually exist in the industry chain?
   - Are the key_factors the right ones?
   - Any missing nodes or factors?

5. Write the complete chain.yaml. Use `fetch_chain.validate_or_raise()` to validate.

6. **Skip to Phase 2 immediately.**

### Phase 2: Data Source Registration and Collection

#### Phase 2.1: Source Registration (→ sources.yaml)

**Goal**: For each node's `key_factors`, find reliable data sources and register them.

1. Check `skills/industry-research/data/{INDUSTRY}/sources.yaml`.
   - If exists AND `--refresh-sources` is NOT set: Use it, skip to Phase 2.2.
   - Otherwise: Continue.

2. Run init:
   ```bash
   cd skills/industry-research/tools && python -c "
   from fetch_sources import init_sources
   from pathlib import Path
   init_sources(Path('..') / 'data' / '{INDUSTRY_SAFE}' / 'sources.yaml')
   "
   ```

3. For each node in chain.yaml, for each key_factor:
   - Search DuckDuckGo/Bing for: `{industry} {node_name} {key_factor} 数据 source API`
   - Identify reliable sources (government, industry association, major financial data platforms)
   - For each source found, record: URL, frequency, selector type
   - Prioritize sources with APIs, then structured pages, then RSS
   - Fallback URL = Jina AI proxy of the same page

4. Register each source by appending to sources.yaml. After all sources are registered, run `validate_sources()` to check.

#### Phase 2.2: Data Collection

```bash
cd skills/industry-research/tools && python fetch_data.py "{INDUSTRY}" "{DATE}"
```

This produces under `data/{INDUSTRY}/reports/{DATE}/`:
- `news.json` — News grouped by node
- `metrics.json` — Quantitative indicators
- `metadata.json` — Collection audit
- `data_quality.json` — Quality report
- Copies of chain.yaml and sources.yaml

After data collection, immediately go to Phase 3.

---

## Reference Document Protocol

**This protocol applies to Phase 3, Phase 4, and Phase 4.5 sub-agents for output persistence and discoverability.**

Context compression will truncate long agent outputs. To prevent information loss, each sub-agent MUST write its output to a standalone file and register it in a shared reference index.

**Reference file**: `skills/industry-research/data/{INDUSTRY}/reports/{DATE}/reference.md`

### Reference file format

```markdown
# 分析报告索引 — {INDUSTRY} ({DATE})

## Phase 3: Node Analysts
- [{node_name} 分析报告](analyst_reports/{node_id}.md)
- ...

## Phase 3: Specialized Analysts
- [政策与监管分析报告](analyst_reports/policy_analyst.md)
- [竞争格局分析报告](analyst_reports/competition_analyst.md)

## Phase 4: Synthesis
- [跨环节传导与综合研判](phase4_synthesis.md)

## Phase 4.5: Investment Analysis
- [投资与商业研判](analyst_reports/investment_analyst.md)
```

### What each Phase 3 sub-agent MUST do

1. Read its prompt template and data files
2. Generate its analysis
3. **Write full report** to `skills/industry-research/data/{INDUSTRY}/reports/{DATE}/analyst_reports/{agent_name}.md` using the Write tool
4. **Append to reference.md**: Add one line `- [{title}]({relative_path})` under the appropriate section (creating the file + section header if first writer). The main session tells each agent its `agent_name`, `title`, and `section`.

### How downstream agents use reference.md

Phase 4 and Phase 4.5 agents read `reference.md` to discover available reports, then selectively read only the files they need via the Read tool — they do NOT load everything into context.

---

### Phase 3: Parallel Multi-Agent Analysis

**CRITICAL**: Launch ALL analyst agents in a SINGLE message as parallel Agent tool calls. Do NOT use `run_in_background`.

Read `chain.yaml` to get the full list of nodes and supports. Then launch:

**For EACH merged node group** in chain.yaml, launch a Node Analyst:
- **Tell the agent**: Role = Node Analyst.
  1. Read prompt from `skills/industry-research/prompts/node_analyst.md`
  2. Read chain model from `skills/industry-research/data/{INDUSTRY}/reports/{DATE}/chain.yaml`
  3. Read news from `skills/industry-research/data/{INDUSTRY}/reports/{DATE}/news.json` for your node(s)
  4. Read metrics from `skills/industry-research/data/{INDUSTRY}/reports/{DATE}/metrics.json`
  5. Generate analysis, then **MUST do TWO Write calls**: 
     - Write full report to `skills/industry-research/data/{INDUSTRY}/reports/{DATE}/analyst_reports/{agent_name}.md`
     - Write to `skills/industry-research/data/{INDUSTRY}/reports/{DATE}/reference.md`: read current content, then write back with `- [{title}](analyst_reports/{agent_name}.md)` appended under the correct section. If the file or section header doesn't exist yet, create them.
- **Context to provide**: agent_name={unique_id}, title={display_title}, section="## Phase 3: Node Analysts", node_id={id}, node_name={name}, node_description={desc}, key_factors={factors}, layer={layer}, industry={INDUSTRY}, data_date={DATE}
- **IMPORTANT**: If total nodes > `--max-node-agents`, merge adjacent nodes (same layer, similar focus) into one analyst. Each merged analyst covers 2-3 nodes.

**Policy Analyst** — IF chain.yaml has any support with policy-related key_factors:
- **Tell the agent**: Role = Policy Analyst. Prompt: `skills/industry-research/prompts/policy_analyst.md`. Read chain.yaml + news.json.
- agent_name="policy_analyst", title="政策与监管分析报告", section="## Phase 3: Specialized Analysts"
- If no policy-related supports exist, SKIP this agent.

**Competition Analyst** — Always launch:
- **Tell the agent**: Role = Competition Analyst. Prompt: `skills/industry-research/prompts/competition_analyst.md`. Read chain.yaml + news.json.
- agent_name="competition_analyst", title="竞争格局分析报告", section="## Phase 3: Specialized Analysts"

**After all agents return**: The reference.md file now contains links to all individual reports. Immediately go to Phase 4.

### Phase 4: Cross-Impact Synthesis

Launch 1 agent (serial, after Phase 3):

- **Tell the agent**: Role = Cross-Impact Analyst.
  1. Read prompt: `skills/industry-research/prompts/cross_impact_analyst.md`
  2. Read reference index: `skills/industry-research/data/{INDUSTRY}/reports/{DATE}/reference.md` (to discover available reports)
  3. Read chain: `skills/industry-research/data/{INDUSTRY}/reports/{DATE}/chain.yaml`
  4. Selectively read analyst reports: open `analyst_reports/` files you need (you do NOT need to read all — pick the ones most relevant to cross-node propagation)
- **Context**: industry={INDUSTRY}, data_date={DATE}, reference_file={path_to_reference.md}
- **After analysis**: Write your full report to `skills/industry-research/data/{INDUSTRY}/reports/{DATE}/phase4_synthesis.md`. Then append `- [跨环节传导与综合研判](../phase4_synthesis.md)` to reference.md under a new section `## Phase 4: Synthesis`.

After it returns, immediately go to Phase 4.5.

### Phase 4.5: Investment & Business Assessment (NEW — dedicated sub-agent)

Launch 1 agent (serial, after Phase 4):

- **Tell the agent**: Role = Investment Analyst.
  1. Read prompt: `skills/industry-research/prompts/investment_analyst.md`
  2. Read reference index: `skills/industry-research/data/{INDUSTRY}/reports/{DATE}/reference.md`
  3. Read chain.yaml to understand the industry structure
  4. Read phase4_synthesis.md for cross-impact analysis
  5. **Selectively** read individual analyst reports from `analyst_reports/` that are most relevant to investment decisions (e.g., supply-critical nodes, highest-growth applications, policy constraints). Do NOT read all reports — pick the ones with highest investment relevance.
- **Context**: industry={INDUSTRY}, data_date={DATE}, reference_file={path_to_reference.md}
- **CRITICAL**: This agent must produce professional analyst-grade output, NOT generic templates. It must:
  - Quantify revenue/margin impacts with specific numbers
  - Identify concrete investable themes with timelines and triggers
  - Name specific public companies and their positioning
  - Provide scenario-based valuation frameworks
  - Include a risk matrix with probability-weighted scenarios
- **After analysis**: Write full report to `skills/industry-research/data/{INDUSTRY}/reports/{DATE}/analyst_reports/investment_analyst.md`. Then append `- [投资与商业研判](analyst_reports/investment_analyst.md)` to reference.md under a new section `## Phase 4.5: Investment Analysis`.

After it returns, immediately go to Phase 5.

### Phase 5: Historical Trend Comparison

**This phase runs in the MAIN SESSION (not a sub-agent).**

1. List `skills/industry-research/data/{INDUSTRY}/reports/` for earlier dated directories.
2. If earlier reports exist, read the most recent one's `report.md`.
3. Extract from the old report:
   - Per-node prosperity scores
   - Top key variables
   - Overall direction
4. Compare with current Phase 3-4.5 results and write `phase5_trend_diff.md` to the report directory:
   ```markdown
   ## 趋势变化对比
   
   | 维度 | 上次 (date) | 本次 (date) | 变化 |
   |------|------------|------------|------|
   ...
   
   ### 新增因素
   ### 弱化/消失因素
   ### 趋势拐点信号
   ```
5. If this is the first analysis, write "首次分析，暂无历史对比" and proceed.

After writing phase5_trend_diff.md, immediately go to Phase 6.

### Phase 6: Final Report

**This phase runs in the MAIN SESSION.**

Read these files:
- `reference.md` — to discover all report files
- `phase4_synthesis.md` — cross-impact summary
- `analyst_reports/investment_analyst.md` — investment analysis
- `phase5_trend_diff.md` — historical comparison
- `chain.yaml` — industry structure
- `data_quality.json` — data quality
- Prompt template: `skills/industry-research/prompts/report_synthesizer.md`

**Produce THREE outputs in ONE Write batch:**

**Output A** — Write `skills/industry-research/data/{INDUSTRY}/reports/{DATE}/report.md`:
Follow the structure in `report_synthesizer.md`. Reference each analyst report by its title — do NOT paste full reports verbatim into the final report (they are already in `analyst_reports/`). Instead:
- For each node: give a concise 1-paragraph summary + reference link to the full report
- For cross-impact: embed the phase4_synthesis.md content
- For investment: embed the investment_analyst.md content IN FULL (this is the most valuable section)

**Output B** — Write `skills/industry-research/data/{INDUSTRY}/latest_report.md`:
Same content as Output A (the industry-level latest report).

**Output C** — Text: Brief summary of key findings and the overall prosperity score.

After all 3 outputs, confirm: "分析报告已保存至 skills/industry-research/data/{INDUSTRY}/reports/{DATE}/report.md"

---

## Data File Reference

### Per-Industry (persistent, reused across runs)
| File | Content |
|------|---------|
| `data/{INDUSTRY}/chain.yaml` | Chain model (phase 1 output, persistent) |
| `data/{INDUSTRY}/sources.yaml` | Data source registry (phase 2.1 output, persistent) |
| `data/{INDUSTRY}/latest_report.md` | Latest report (phase 6 output, overwritten) |

### Per-Date (archived)
| File | Content |
|------|---------|
| `data/{INDUSTRY}/reports/{DATE}/chain.yaml` | Chain snapshot |
| `data/{INDUSTRY}/reports/{DATE}/sources.yaml` | Sources snapshot |
| `data/{INDUSTRY}/reports/{DATE}/news.json` | Grouped news |
| `data/{INDUSTRY}/reports/{DATE}/metrics.json` | Quantitative indicators |
| `data/{INDUSTRY}/reports/{DATE}/metadata.json` | Collection audit |
| `data/{INDUSTRY}/reports/{DATE}/data_quality.json` | Quality report |
| `data/{INDUSTRY}/reports/{DATE}/reference.md` | **Report index** — maps agent_name → file path + title |
| `data/{INDUSTRY}/reports/{DATE}/analyst_reports/` | **Individual analyst reports** (Phase 3 + Phase 4.5) |
| `data/{INDUSTRY}/reports/{DATE}/phase4_synthesis.md` | Cross-impact synthesis (Phase 4) |
| `data/{INDUSTRY}/reports/{DATE}/phase5_trend_diff.md` | Historical comparison (Phase 5) |
| `data/{INDUSTRY}/reports/{DATE}/report.md` | Final report (Phase 6) |

## Common Mistakes

- **Stopping between phases to ask the user**: The user asked for a complete analysis. Run all phases continuously.
- **Forgetting to parallelize Phase 3 agents**: ALL agents must be launched in ONE message.
- **Phase 3 agents not writing to `analyst_reports/` + `reference.md`**: Each agent MUST write its output to a standalone file AND register in the reference index. This is the #1 data loss prevention mechanism.
- **Phase 6 summarizing investment analysis instead of pasting verbatim**: The investment_analyst.md report is the most valuable section. Paste it in full.
- **Phase 6 text-only output without Write call**: The report MUST be written to disk. Text output alone is not deliverable.
- **Using historical data for current analysis**: Historical reports are ONLY for Phase 5 comparison.
