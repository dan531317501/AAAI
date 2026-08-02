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
4. Dispatching analyst sub-agents by a **dependency DAG**: no-dependency topics launched in parallel in ONE message; dependent topics dispatched separately AFTER their dependencies complete
5. Each sub-agent writes its full report to its **own standalone file** (no truncation, no main-session rewriting)
6. Synthesizing cross-node impact propagation (a dependent topic)
7. Comparing against historical analyses to detect trend shifts
8. Producing a final report = **overall trend summary (written by main session) + sub-agent reports concatenated VERBATIM as topic chapters**

## Critical Execution Rules

1. **NEVER ask the user for permission between phases.** Run all phases continuously.
2. **Independent topics (no dependencies) are ALL launched in a SINGLE message as parallel Agent calls.** Do not use `run_in_background`.
3. **Dependent topics are dispatched AFTER their dependencies complete** — never in the same batch as their dependencies.
4. **Each sub-agent writes its full report to its own file.** The main session does not summarize, trim, or rewrite sub-agent output.
5. **Phase 5-6 run in the main session**, not as sub-agents.
6. **Phase 6 produces TWO Write outputs in ONE batch: Write (report.md) + Write (latest_report.md), plus a text summary.**
7. **Phase 6 final report = overall trend summary (main session) + sub-agent reports concatenated VERBATIM as topic chapters.** Never trim or rewrite sub-agent content.
8. **Historical data is for COMPARISON only — never for current analysis.**

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

### Sub-agent report heading convention

Each sub-agent report MUST follow these heading rules so it can be concatenated **verbatim** into the final report as one chapter:
1. Open with a **single `##` heading** for its topic title (e.g. `## AI算力芯片 分析报告`, `## 投资与商业研判`). This heading becomes the final report's chapter title.
2. All internal sections use **`###`** — never `#` (reserved for the final report title only).
3. Do NOT include a date/industry metadata block in the report body (the final report header already covers it).

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

### Phase 3: Parallel Multi-Agent Analysis (Batch 1 — no dependencies)

**Dependency note**: Every topic in this phase depends ONLY on data already collected in Phases 1-2 (chain.yaml, news.json, metrics.json). They have NO upstream/downstream dependencies on each other, so ALL are launched in one batch.

**CRITICAL**: Launch ALL of them in a SINGLE message as parallel Agent tool calls. Do NOT use `run_in_background`.

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

### Phase 4: Cross-Impact Synthesis (dependent topic)

**Dependency note**: This topic DEPENDS on all Phase 3 reports (node analysts + policy + competition). Dispatch it ONLY after every Batch 1 agent has returned — never in the same batch as its dependencies.

Launch 1 agent (serial, after Phase 3):

- **Tell the agent**: Role = Cross-Impact Analyst.
  1. Read prompt: `skills/industry-research/prompts/cross_impact_analyst.md`
  2. Read reference index: `skills/industry-research/data/{INDUSTRY}/reports/{DATE}/reference.md` (to discover available reports)
  3. Read chain: `skills/industry-research/data/{INDUSTRY}/reports/{DATE}/chain.yaml`
  4. Selectively read analyst reports: open `analyst_reports/` files you need (you do NOT need to read all — pick the ones most relevant to cross-node propagation)
- **Context**: industry={INDUSTRY}, data_date={DATE}, reference_file={path_to_reference.md}
- **After analysis**: Write your full report to `skills/industry-research/data/{INDUSTRY}/reports/{DATE}/phase4_synthesis.md`. Then append `- [跨环节传导与综合研判](../phase4_synthesis.md)` to reference.md under a new section `## Phase 4: Synthesis`.

After it returns, immediately go to Phase 4.5.

### Phase 4.5: Investment & Business Assessment (dependent topic)

**Dependency note**: This topic DEPENDS on the Phase 4 synthesis (and selectively on Phase 3 reports). Dispatch it ONLY after Phase 4 completes.

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

> **Timing tip**: The READ part (steps 1-3: list earlier reports, read, extract scores/variables) has NO dependency on any sub-agent — do it right after dispatching Batch 1 while the agents run. Only the comparison + write (step 4) must wait for Phase 3-4.5 results.

1. List `skills/industry-research/data/{INDUSTRY}/reports/` for earlier dated directories.
2. If earlier reports exist, read the most recent one's `report.md`.
3. Extract from the old report:
   - Per-node prosperity scores
   - Top key variables
   - Overall direction
4. Compare with current Phase 3-4.5 results and write `phase5_trend_diff.md` to the report directory (heading must be `## 历史趋势对比` so it becomes a proper chapter when concatenated):
   ```markdown
   ## 历史趋势对比
   
   ### 趋势变化对比
   
   | 维度 | 上次 (date) | 本次 (date) | 变化 |
   |------|------------|------------|------|
   ...
   
   ### 新增因素
   ### 弱化/消失因素
   ### 趋势拐点信号
   ```
5. If this is the first analysis, write `## 历史趋势对比\n\n首次分析，暂无历史对比` and proceed.

After writing phase5_trend_diff.md, immediately go to Phase 6.

### Phase 6: Final Report

**This phase runs in the MAIN SESSION.**

**Report format**: final report = **overall trend summary** (written by the main session) + **sub-agent reports concatenated VERBATIM as topic chapters** (no trimming, no rewriting).

**Dependency note**: This phase DEPENDS on every sub-agent report (Phase 3-4.5) and `phase5_trend_diff.md`.

1. Read `reference.md` to discover all sub-agent report files. Follow the structure in `skills/industry-research/prompts/report_synthesizer.md`.
2. Read enough of each sub-agent report to write the overall summary — its topic heading + key sections (scores, top findings, risks). You do NOT need every line: the reports are embedded verbatim below the summary anyway.
3. **Write the chain overview** to `chain_overview.md` — a `## 产业链全景` chapter rendered as a **mermaid flowchart** (diagram, NOT text), generated from chain.yaml:
   - Group nodes by `layer` ascending; one `subgraph` per layer, titled `Layer {N}: {上游/中游/下游}` (layer<0=上游, layer==0=中游, layer>0=下游)
   - One mermaid node per chain node: `{node_id}["{node_name}"]`
   - One mermaid edge per chain edge: `{from} --> {to}`
   - Below the diagram: one line of stats (node count, edge count) + a short bullet list of `supports`
4. **Write the overall summary** to `analyst_reports/00_overall_summary.md`, opening with `## 行业趋势调研总结`. It MUST contain:
   - **关键发现 TOP 5** — table (`# | 发现 | 支撑数据 | 影响`), each row citing "per {话题} 报告"
   - **综合景气度** — score X/10 + direction + confidence, with anchoring rationale
   - **投资要点与风险速览** — 3-5 key takeaways + TOP 3 risks (with triggers)
   - **章节导读** — one-sentence guide per chapter, in final report order
5. **Write the appendix** to `appendix.md` (数据质量 from data_quality.json, 分析师报告索引 from reference.md, 执行统计).
6. **Concatenate VERBATIM in fixed chapter order** with Bash (never re-type sub-agent content by hand — manual copying risks truncation and hallucinated edits):
   Chapter order: `chain overview → overall summary → nodes (by layer, upstream → downstream) → policy → competition → cross-impact → investment → historical comparison → appendix`
   ```bash
   cd skills/industry-research/data/{INDUSTRY}/reports/{DATE} && {
     {
       printf '# %s 产业趋势调研报告\n\n**日期**: %s | **数据截止**: %s | **版本**: chain.yaml v%s\n\n---\n\n' '{INDUSTRY}' '{DATE}' '{DATA_AS_OF}' '{CHAIN_VERSION}'
       cat chain_overview.md
       printf '\n---\n\n'
       cat analyst_reports/00_overall_summary.md
       for f in <sub-agent report files in topic order>; do
         printf '\n---\n\n'
         cat "$f"
       done
       printf '\n---\n\n'
       cat phase5_trend_diff.md
       printf '\n---\n\n'
       cat appendix.md
     } > report.md
     cp report.md ../../latest_report.md
   }
   ```
   (If this is the first analysis, `phase5_trend_diff.md` contains "首次分析，暂无历史对比" — include it as-is.)

**Output A** — `report.md` (produced by the Bash step above).
**Output B** — `latest_report.md` (same content, copied by `cp`).
**Output C** — Text: brief summary of key findings and the overall prosperity score.

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
| `data/{INDUSTRY}/reports/{DATE}/chain_overview.md` | Chain overview chapter with mermaid diagram (Phase 6, written by main session) |
| `data/{INDUSTRY}/reports/{DATE}/analyst_reports/` | **Individual analyst reports** (Phase 3 + Phase 4.5) |
| `data/{INDUSTRY}/reports/{DATE}/analyst_reports/00_overall_summary.md` | Overall trend summary (Phase 6, written by main session) |
| `data/{INDUSTRY}/reports/{DATE}/appendix.md` | Appendix: data quality + report index + execution stats (Phase 6) |
| `data/{INDUSTRY}/reports/{DATE}/phase4_synthesis.md` | Cross-impact synthesis (Phase 4) |
| `data/{INDUSTRY}/reports/{DATE}/phase5_trend_diff.md` | Historical comparison (Phase 5) |
| `data/{INDUSTRY}/reports/{DATE}/report.md` | Final report (Phase 6) |

## Common Mistakes

- **Stopping between phases to ask the user**: The user asked for a complete analysis. Run all phases continuously.
- **Forgetting to parallelize independent topics**: ALL no-dependency agents (Phase 3 batch) must be launched in ONE message.
- **Dispatching dependent topics in the same batch as their dependencies**: Cross-impact (Phase 4) MUST wait for ALL Phase 3 reports; Investment (Phase 4.5) MUST wait for Phase 4. Dispatch each only after its dependencies complete.
- **Sub-agents not writing to `analyst_reports/` + `reference.md`**: Each agent MUST write its output to a standalone file AND register in the reference index. This is the #1 data loss prevention mechanism.
- **Phase 6 trimming or rewriting sub-agent reports**: Concatenate VERBATIM — never summarize, trim, or rephrase sub-agent content in the final report.
- **Phase 6 re-typing sub-agent content by hand**: Use Bash `cat` to concatenate — manual re-typing risks truncation and hallucinated edits.
- **Phase 6 text-only output without Write call**: The report MUST be written to disk. Text output alone is not deliverable.
- **Using historical data for current analysis**: Historical reports are ONLY for Phase 5 comparison.
