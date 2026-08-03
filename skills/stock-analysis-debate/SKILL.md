---
name: stock-analysis-debate
description: Use when the user wants to analyze a stock (US/CN/HK markets) and get a Buy/Hold/Sell recommendation backed by a multi-agent debate among market analysts, researchers, risk assessors, and portfolio managers using real market data.
---

# Stock Analysis with Multi-Agent Debate

## Overview

Conduct a professional stock analysis by orchestrating multiple AI agents in a structured debate. Agents play specialized roles — Market Analyst, News Analyst, Social Media Analyst, Fundamentals Analyst, Bull/Bear Researchers, Trader, Aggressive/Conservative/Neutral Risk Analysts, and Portfolio Manager — to produce a data-backed investment recommendation (Buy/Overweight/Hold/Underweight/Sell).

Data is fetched primarily from **yfinance** (OHLCV, news, fundamentals, financial statements), with **Longbridge daily K-lines** filling missing latest OHLCV dates for US/HK/SH/SZ stocks, and **stockstats** computing technical indicators.

## Critical Execution Rules

**These rules override all other instructions during analysis execution:**

1. **NEVER ask the user for permission to proceed between phases.** After each phase completes, immediately continue to the next phase. The user asked for a complete analysis — deliver it in one continuous run.
2. **After all Phase 2 agents return, collect their complete responses, write all available reports to `phase2_analyst_reports.md`, verify that the file exists and is non-empty, then CONTINUE to Phase 3 without stopping.**
3. **Phases 3-6 run agents sequentially — each depends on the previous one's output. After each agent returns, immediately launch the next one. Do NOT pause for user confirmation.**
4. **Phase 7 is the final phase (NOT a sub-agent). It MUST produce TWO outputs in ONE message batch: (A) Write `analysis_report.md` via the Write tool, and (B) the final decision text. If either is missing, the analysis is incomplete. Do NOT output the decision text without also calling Write.**
5. **The workflow is complete ONLY when the report file has been written to `skills/stock-analysis-debate/tools/data/{TICKER}/{DATE}/analysis_report.md` AND confirmed to the user.**

6. **CN market skips Phase 1.5 and Segment Analyst entirely.** No `segments.yaml`, no segment data. Run 4 analysts.
7. **If `segments_fetch_failed.flag` exists**, treat as CN: skip Phase 1.5 and Segment Analyst, run 4 analysts. Note the missing segment view in the final report.

8. **REPORT DATE:** `{DATE}` is the execution/analysis date and is the ONLY date allowed in the report title and output directory. Treat `data_as_of_date` only as the market-data cutoff and disclose it separately. Even when `data_fresh: false`, write exactly one report to `data/{TICKER}/{DATE}/analysis_report.md`; never create or copy another report under `data_as_of_date`. If `warning_no_200_sma: true`, 200 SMA must be reported as N/A.
9. **ARITHMETIC VERIFICATION (Phase 7):** Before writing the final report, verify TTM EPS/P/E reconciliation, target_price = (profit × PE) / total_shares, forward_PE = current_price / forward_EPS, and market_cap = current_price × total_shares. If values conflict beyond the stated tolerance, disclose and correct them before producing the rating.
10. **NEWS/SENTIMENT EVIDENCE:** Treat `news.txt` evidence IDs and content levels as hard boundaries. If `Social Data Available: false`, social sentiment is Not Rated and must not affect the rating, target price, position sizing, or risk limits.

11. **CONTEXT HYGIENE (main session):** The main session's context is reserved for orchestration, decision synthesis, and deliverables:
    - Debate/risk agents write their own files (File I/O protocol) and return only short confirmations/summaries — never their full arguments.
    - Downstream agents (Research Manager, Trader) read files themselves via the paths given in their prompts — never paste file contents into agent prompts.
    - Never Read a file whose content is already in the main context (own Write output, agent-returned content saved to disk).
    - At Phase 7, the main session Reads only the files whose content it has NOT seen (debate history, risk debate history) — it writes the report summaries itself. Files it wrote itself (`phase2_analyst_reports.md`, `research_plan.md`, `trader_plan.md`) are NOT re-read; their content is already in context.

## Workflow

1. **Phase 1: Data Collection** — Bash: `fetch_data.py`
   - Foreground, synchronous; wait for it to return before proceeding.

1.1. **Phase 1.1: Data Quality Check** — Read `data_quality.json` from the output directory
   - Keep the requested execution `date` as the report date and output-directory date. Use `data_as_of_date` only for statements about how current the market data is. If the dates differ, disclose both explicitly and do not generate a second report.
   - Check `trading_days`: note how many trading days are available for indicators.
   - Check `warning_no_200_sma`: if true, 200 SMA is NOT computable.
   - Check `indicator_sufficiency`: each indicator has a `sufficient` boolean and `min_days` threshold.
   - Record any `notes` warnings for inclusion in the final report.

1.5. **Phase 1.5: Segment Setup** (HK/US only) — Bash: `prepare_segments.py --gen-yaml`
   - Skipped for CN market. Skipped if `segments_fetch_failed.flag` exists.
   - Foreground, synchronous.

2. **Phase 2: Analyst Reports** — 4 or 5 Agent calls
   - Parallel: launch all in a SINGLE message, foreground (no `run_in_background`).
   - 5th agent (Segment Analyst) runs ONLY for HK/US with `multi_segment: true` in `segments.yaml`.

3. **Phase 3: Bull vs Bear Debate** — 4 Agent calls
   - Sequential: one at a time (2 rounds × Bull/Bear).

4. **Phase 4: Research Manager** — 1 Agent call
   - Sequential; depends on Phase 3 output.

5. **Phase 5: Trader** — 1 Agent call
   - Sequential; depends on Phase 4 output.

6. **Phase 6: Risk Debate** — 6 Agent calls
   - Sequential: one at a time (3 roles × 2 rounds).

7. **Phase 7: Portfolio Manager + Final Report** — Main session synthesis + MANDATORY Write
   - NOT an Agent call; synthesized directly in the main session.
   - **MUST produce TWO outputs in ONE batch: Write tool (analysis_report.md) + decision text.**
   - Workflow is complete ONLY when both are done.

## Phase 1: Data Collection

Run synchronously via Bash:

```bash
python skills/stock-analysis-debate/tools/fetch_data.py <TICKER> <DATE> --output-dir skills/stock-analysis-debate/tools/data
```

**First-time setup** (install dependencies if not present):
```bash
pip install -r skills/stock-analysis-debate/tools/requirements.txt
```

Output is saved to `skills/stock-analysis-debate/tools/data/{TICKER}/{DATE}/` containing:

| File | Content | Source |
|------|---------|--------|
| `ohlcv.csv` | OHLCV price data (60 days) | yfinance + Longbridge latest-date fallback |
| `indicators.txt` | 13 technical indicators | stockstats via yfinance/Longbridge OHLCV |
| `news.txt` | Company-specific news with evidence IDs, content levels, available summaries, processing audit, and explicit social-data availability (30 days) | yfinance + fetch_data.py |
| `global_news.txt` | Macro/global news | yfinance Search |
| `fundamentals.txt` | Provider fundamentals plus point-in-time valuation, TTM EPS/P/E reconciliation, and GAAP operating-profit audit | yfinance + financial_audit.py |
| `balance_sheet.csv` | Quarterly balance sheet | yfinance |
| `cashflow.csv` | Quarterly cash flow | yfinance |
| `income_stmt.csv` | Quarterly income statement | yfinance |
| `insider.txt` | Insider transactions | yfinance |
| `summary.json` | Metadata summary | — |

**Additional outputs (HK/US only):**

| File | Content | Source |
|------|---------|--------|
| `revenue_sankey.json` | Longbridge quarterly Sankey data; preserves all original nodes and links and adds classification, QoQ/YoY, segment mix, consolidated reconciliation, and segment completeness checks | Longbridge revenue-sankey API (fetched in Phase 1) |
| `revenue_sankey.csv` | Enhanced Sankey nodes for recent periods, used for business-segment and profit-structure analysis | prepare_segments.py (Phase 1.5) |
| `segments_missing.flag` | Missing segment-manifest marker that triggers Phase 1.5 generation | fetch_data.py |
| `segments_fetch_failed.flag` | Longbridge fetch-failure marker used for graceful degradation | fetch_data.py |

**Ticker-level (no date, reused across runs):**

| File | Content | Source |
|------|---------|--------|
| `data/{TICKER}/segments.yaml` | Reusable cross-run business-segment manifest | prepare_segments.py --gen-yaml |

**After data is fetched**, immediately proceed to Phase 1.5 if applicable, otherwise go to Phase 2. Do not stop.

## Phase 1.5: Segment Setup (HK/US only)

**Skip conditions**: CN market, OR `segments_fetch_failed.flag` exists in the date dir.

1. Check `skills/stock-analysis-debate/tools/data/{TICKER}/segments.yaml` (ticker-level, no date).
   - If exists: read it, then run prepare_segments.py WITHOUT `--gen-yaml` to produce the day's `revenue_sankey.csv`:
     ```bash
     python skills/stock-analysis-debate/tools/prepare_segments.py {TICKER} {DATE} --output-dir skills/stock-analysis-debate/tools/data
     ```
   - If missing: run with `--gen-yaml` (generates `segments.yaml` and `revenue_sankey.csv`):
     ```bash
     python skills/stock-analysis-debate/tools/prepare_segments.py {TICKER} {DATE} --output-dir skills/stock-analysis-debate/tools/data --gen-yaml
     ```
2. Read `segments.yaml`. Record `multi_segment` for Phase 2 branching.
3. Proceed immediately to Phase 2.

See `prompts/segment_analyst.md` for data interpretation rules and `prepare_segments.py` plus `longbridge_fetcher.py` for tool-level processing logic.
- `reconciliation_status=mismatch` → the tool raises an exception, Phase 1.5 fails, and no CSV is generated.
- A non-empty `segment_completeness_status` → the analyst must disclose the incomplete data in the report.

## Phase 2: Analyst Reports (Parallel, Single Message)

**CRITICAL**: Launch all applicable analyst agents (4 base analysts, plus the conditional Segment Analyst) in a SINGLE message as parallel Agent tool calls. Do NOT use `run_in_background` — use foreground calls so results return to the main conversation. The system will execute them in parallel and wait for all to complete.

**IMPORTANT — Main session must NOT read prompt files or data files before dispatching analysts.** Each sub-agent reads its own prompt file and data files via the Read tool — the main session reading them too is pure context waste. The main session only tells each agent:
- Full absolute file paths to: its prompt file + all required data files
- Instrument context: ticker, market, currency, current price
- Phase 1.1 findings: data_as_of_date, trading_days, warning_no_200_sma flag, indicator_sufficiency summary
- For Segment Analyst: also mention the segment list from `segments.yaml`

The sub-agent discovers everything else by reading the files itself.

### The 4 Analysts (launch simultaneously in one message):

**Market Analyst** — Prompt: `skills/stock-analysis-debate/prompts/market_analyst.md` — Data: `ohlcv.csv`, `indicators.txt`

**News Analyst** — Prompt: `skills/stock-analysis-debate/prompts/news_analyst.md` — Data: `news.txt`, `global_news.txt`

**Social Media Analyst** — Prompt: `skills/stock-analysis-debate/prompts/social_media_analyst.md` — Data: `news.txt`

**Fundamentals Analyst** — Prompt: `skills/stock-analysis-debate/prompts/fundamentals_analyst.md` — Data: `fundamentals.txt`, `balance_sheet.csv`, `cashflow.csv`, `income_stmt.csv`

### Conditional 5th Analyst (HK/US + multi_segment only):

**Segment Analyst** — Prompt: `skills/stock-analysis-debate/prompts/segment_analyst.md` — Data: `revenue_sankey.csv`, `income_stmt.csv`.

Launch Segment Analyst IN PARALLEL with the other 4 only when `segments.yaml` has `multi_segment: true`. Otherwise run 4 analysts as before.

**After all launched agents return**: Extract every complete report from the agent responses. Save the 4 or 5 role results to `skills/stock-analysis-debate/tools/data/{TICKER}/{DATE}/phase2_analyst_reports.md` using the Write tool, under role-specific headings. If an agent failed or returned no content, write an explicit failure marker for that role instead. Verify that the file exists, is non-empty, and contains a report or failure marker for every launched analyst. Then IMMEDIATELY proceed to Phase 3. Do NOT ask the user.

## Debate History File Protocol

Multi-round debates use **files as shared memory**. Each sub-agent reads/writes the debate history file autonomously — the main session never touches these files. The File I/O protocol is defined in each debate agent's prompt file (`bull_researcher.md`, `bear_researcher.md`, `aggressive_debator.md`, `conservative_debator.md`, `neutral_debator.md`).

| Debate | File Path |
|--------|-----------|
| Bull vs Bear | `skills/stock-analysis-debate/tools/data/{TICKER}/{DATE}/debate_history.md` |
| Risk Assessment | `skills/stock-analysis-debate/tools/data/{TICKER}/{DATE}/risk_debate_history.md` |

The main session only tells each agent: the file path, its role, the round number, and paths to the data files it needs.

---

## Phase 3: Bull vs Bear Debate

Run **`debate_rounds`** rounds (default 2). Each round: Bull → Bear, sequential. Sub-agents handle debate history file I/O via the protocol in their prompts.

For each agent, tell it: role, round N of total, debate history file path, and analyst reports file path. Include instrument context.

**Return protocol**: Each debate agent appends its full argument to the debate history file and returns ONLY a one-line status confirmation (role, round, file write succeeded) per the Step 4 protocol in its prompt. The main session must NOT read `debate_history.md` during Phase 3 — it is shared memory between debate agents and read later by the Research Manager (which reads it itself) and at Phase 7 (when the main session reads it to write the report summaries).

Debate history file: `skills/stock-analysis-debate/tools/data/{TICKER}/{DATE}/debate_history.md`
Data file: `skills/stock-analysis-debate/tools/data/{TICKER}/{DATE}/phase2_analyst_reports.md`

After Phase 3, proceed immediately to Phase 4.

## Phase 4: Research Manager

- **Before**: Do NOT read the debate history or analyst report files in the main session — the sub-agent reads them itself (see rule 11).
- **Prompt**: `skills/stock-analysis-debate/prompts/research_manager.md`
- **Context in prompt**: Full absolute file paths to `debate_history.md` and `phase2_analyst_reports.md` (the agent Reads both itself — do NOT paste their contents). Include instrument context (market type, currency, ticker, e.g. "601988.SH is a CN stock on Shanghai Stock Exchange, currency: CNY, ±10% price limit, T+1 settlement").
- **Task**: Judge the debate. Make definitive Buy/Sell/Hold decision. Produce investment plan with rationale + strategic actions.
- **After it returns**: The full plan comes back in the agent's response — save it to `skills/stock-analysis-debate/tools/data/{TICKER}/{DATE}/research_plan.md` (its content is already in context; Phase 7 must NOT re-read it). Immediately go to Phase 5.

## Phase 5: Trader

- **Before**: Do NOT read `research_plan.md` or analyst reports in the main session — the sub-agent reads them itself (see rule 11).
- **Prompt**: `skills/stock-analysis-debate/prompts/trader.md`
- **Context in prompt**: Full absolute file paths to `research_plan.md` and `phase2_analyst_reports.md` (the agent Reads them itself — do NOT paste their contents). Include instrument context.
- Must end output with: `FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL**`
- For staged entries, require the Trader to output incremental and cumulative weights and verify that their sum does not exceed the maximum position. Include portfolio capital in context only when known; otherwise dollar amounts and share counts must be N/A.
- **After it returns**: The full proposal comes back in the agent's response — save it to `skills/stock-analysis-debate/tools/data/{TICKER}/{DATE}/trader_plan.md` (its content is already in context; Phase 7 must NOT re-read it). The proposal must still end with `FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL**`. Immediately go to Phase 6.

---

## Phase 6: Risk Assessment Debate

Run **`risk_discuss_rounds`** rounds (default 2). Each round: Aggressive → Conservative → Neutral, sequential. Sub-agents handle risk debate history file I/O via the protocol in their prompts.

For each agent, tell it: role, round N of total, risk debate history file path, trader plan file path, and analyst reports file path. Include instrument context.

**Return protocol**: Each risk debator appends its full assessment to the risk debate history file and returns ONLY a short summary (final stance, revised position plan with incremental/cumulative weights, 3-5 core argument bullets) per the Step 4 protocol in its prompt. The main session uses these returns during Phase 3-6 and at Phase 7 Reads `risk_debate_history.md` itself to write the report summaries.

Risk debate history file: `skills/stock-analysis-debate/tools/data/{TICKER}/{DATE}/risk_debate_history.md`
Trader plan: `skills/stock-analysis-debate/tools/data/{TICKER}/{DATE}/trader_plan.md`
Analyst reports: `skills/stock-analysis-debate/tools/data/{TICKER}/{DATE}/phase2_analyst_reports.md`

After Phase 6, proceed immediately to Phase 7.

## Phase 7: Portfolio Manager — Final Decision + Report File (main session)

**This phase runs in the main session, NOT as a sub-agent.** The main session has orchestrated every phase and holds the most complete context.

**The phase produces TWO outputs. They MUST be called in the SAME tool call batch. Never split them across messages.**

---

### Step 1: Gather

Read only the files whose content the main session has NOT seen yet (rule 11). The main session writes the report summaries itself — it does NOT need agents to pre-generate summaries:

**Must Read (never seen by the main session):**
- `skills/stock-analysis-debate/tools/data/{TICKER}/{DATE}/debate_history.md` — full Bull vs Bear debate (Phase 3 agents only returned status confirmations)
- `skills/stock-analysis-debate/tools/data/{TICKER}/{DATE}/risk_debate_history.md` — full risk debate (Phase 6 agents only returned short summaries)
- `skills/stock-analysis-debate/prompts/portfolio_manager.md` — output structure template (Rating scale, Executive Summary, Investment Thesis)

**Must NOT Read (already in the main context):**
- `phase2_analyst_reports.md` — written by the main session from the analysts' returned reports (Phase 2)
- `research_plan.md` — written from the Research Manager's returned plan (Phase 4)
- `trader_plan.md` — written from the Trader's returned proposal (Phase 5)
- `data_quality.json` — read in Phase 1.1

### Step 1.5: Arithmetic Sanity Check (MANDATORY — do NOT skip)

Before synthesizing, verify these numbers with actual computation:

1. **Market Cap**: current_price × total_shares. Does it match the fundamentals.txt market cap? If discrepancy >10%, flag it.
2. **P/B**: use current_price ÷ (latest-quarter common stock equity ÷ ordinary shares from that same quarter). Do not use a stale provider Book Value or attribute the mismatch to share count.
3. **EV/EBITDA**: use point-in-time market cap + latest total debt - latest cash and short-term investments, divided by TTM EBITDA in the same base currency. Preserve the numerator/denominator units and label simplified EV explicitly.
4. **GAAP operating profit**: use `Total Operating Income As Reported`; reconcile `Operating Income`, restructuring/merger charges, and other operating adjustments. Longbridge `oper_inc` is a provider-defined Sankey subtotal and must not be relabeled as GAAP without reconciliation.
5. **TTM EPS/P/E**: Use the audit section's `Preferred TTM EPS` and `Preferred TTM P/E`. When reconciliation status is `mismatch`, disclose provider and statement-derived values, use the statement-derived values, and remove downstream claims based on the conflicting provider values. When status is `provider_only` or `unavailable`, report audited TTM EPS/P/E as N/A and do not use provider values as a valuation anchor.
6. **Forward PE**: Compute current_price / provider_forward_EPS and compare it with provider Forward PE. Label both as provider consensus snapshot metrics; arithmetic agreement does not independently validate the forecast.
7. **Target Price**: For every target price in the debate, compute `(profit × PE) / total_shares` and verify it matches. If a debater claims "CNY 55 billion × 20x = CNY 88 per share" but the formula produces a different value, this is a HARD ERROR. Flag and correct it in the final report.
8. **Revenue/Net Income period labels**: If the Fundamentals Analyst cites a figure as "full-year 2025," verify that it is at least the sum of the visible quarters. If a column labeled "2025-12-31" is a single quarter, correct the label to "Q4 2025" in the final report.
9. **200 SMA**: If data_quality.json says `warning_no_200_sma: true`, any mention of "200 SMA" in analyst reports that uses a value other than N/A is invalid.
10. **News evidence**: Every material company-news claim must cite `[Nxxx]`. A `title_only` item supports only the literal headline; do not upgrade secondary reporting to an official confirmation or treat media rewrites as independent corroboration.
11. **Social sentiment**: If `news.txt` says `Social Data Available: false`, report social sentiment as Not Rated. Remove unsupported mention counts, sentiment scores, community trends, user positioning, and ticker comparisons from downstream outputs. These claims must not influence the rating, target price, position sizing, or risk limits.
12. **Position sizing**: For every staged entry plan, verify that cumulative weight equals the sum of incremental entry weights and does not exceed the stated maximum position. If any risk-debate proposal changes a stage, recompute all later stages, capital, and shares. Remove entry stages that occur after the maximum is reached. If portfolio capital or entry price is unavailable, report capital and shares as N/A.

### Step 2: Synthesize

Produce the Portfolio Manager's final decision in the main session:

- **Rating**: Buy / Overweight / Hold / Underweight / Sell
- **Executive Summary**: Entry strategy, position sizing, risk levels, time horizon
- **Investment Thesis**: Reasoning anchored in specific evidence from the files above

### Step 3: Write Report + Output Decision

**This is the mandatory deliverable. The analysis is incomplete until the file is on disk.**

In ONE continuous sequence (Write, then text — same turn), do:

**Output A — Write tool**: Call Write to create `skills/stock-analysis-debate/tools/data/{TICKER}/{DATE}/analysis_report.md` with ALL sections populated. The main session writes the report summaries ITSELF (based on Step 1's Gather) — natural-language summaries, one short paragraph or bullet list per section. **Final Decision is FIRST.** Structure (fixed):

```
# Stock Analysis Report: {TICKER} ({DATE})

**Report Date**: {DATE} | **Market Data As Of**: {data_as_of_date}

## Final Decision
{portfolio manager's full decision — first}

## 1. Analyst Research
{summary of the analyst reports — key verdict, levels, signals}

完整报告: [phase2_analyst_reports.md](./phase2_analyst_reports.md)

## 2. Bull vs Bear Debate
{summary of the debate — each side's stance, key arguments, convergence points}

完整辩论: [debate_history.md](./debate_history.md)

## 3. Investment Plan
{summary of the research manager's plan}

完整计划: [research_plan.md](./research_plan.md)

## 4. Trading Proposal
{summary of the trader's proposal}

完整提案: [trader_plan.md](./trader_plan.md)

## 5. Risk Assessment Debate
{summary of the risk debate — each role's stance, position plans, convergence}

完整辩论: [risk_debate_history.md](./risk_debate_history.md)
```

**Output B — Text**: A concise summary of the rating, price target, and key rationale so the user sees the result immediately.

After both outputs complete, confirm: "The analysis report has been saved to skills/stock-analysis-debate/tools/data/{TICKER}/{DATE}/analysis_report.md"

**Date guardrail**: `{DATE}` above is always the execution/analysis date. Do not replace it with `data_as_of_date`, and do not write or copy `analysis_report.md` to any second date directory.

---

**Guardrail**: If you catch yourself about to output the decision text without also calling Write on `analysis_report.md`, STOP. You are about to make the #1 deliverable mistake. Add the Write call, then send both together. A text-only output is not a deliverable — it disappears when context scrolls. The file is the permanent record.

**If any analyst agent failed or returned no content**, note it in the report but do NOT stop.

## Market-Specific Handling

| Market | Ticker Format | Currency | Special Rules |
|--------|--------------|----------|---------------|
| US | `AAPL`, `MSFT` | USD | None |
| CN | `600519.SH`, `000858.SZ` | CNY | ±10% price limit, T+1, 100 shares/lot |
| HK | `00700.HK`, `09988.HK` | HKD | Variable lot sizes, T+2, no price limit |

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `debate_rounds` | 2 | Bull vs Bear debate rounds |
| `risk_discuss_rounds` | 2 | Risk assessment debate rounds |
| `analysts` | all 4 | Which analysts to run (market, social, news, fundamentals) |
| `date` | today | Analysis date in YYYY-MM-DD |

## Common Mistakes

- **Modifying prompts**: Prompt files contain the exact prompts. Do NOT paraphrase or improve them. Pass verbatim.
- **Defaulting to Hold**: If both sides have valid points, pick the stronger argument. Hold only for genuinely neutral situations.
- **Forgetting instrument context**: Every debate/judgment agent needs market (US/CN/HK), currency, ticker format, and trading rules.
- **Context bloat**: Do NOT paste file contents into agent prompts, do NOT re-read files already in the main context (own Write output, agent-returned content). At Phase 7, Read only `debate_history.md` and `risk_debate_history.md` (the only files the main session has not seen). See rule 11.
