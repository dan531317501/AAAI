---
name: stock-analysis-debate
description: Use when the user wants to analyze a stock (US/CN/HK markets) and get a Buy/Hold/Sell recommendation backed by a multi-agent debate among market analysts, researchers, risk assessors, and portfolio managers using real market data.
---

# Stock Analysis with Multi-Agent Debate

## Overview

Conduct a professional stock analysis by orchestrating multiple AI agents in a structured debate. Agents play specialized roles — Market Analyst, News Analyst, Social Media Analyst, Fundamentals Analyst, Bull/Bear Researchers, Trader, Aggressive/Conservative/Neutral Risk Analysts, and Portfolio Manager — to produce a data-backed investment recommendation (Buy/Overweight/Hold/Underweight/Sell).

Data is fetched from **yfinance** (OHLCV, news, fundamentals, financial statements) and **stockstats** (technical indicators), exactly matching the original TradingAgents data sources.

## Critical Execution Rules

**These rules override all other instructions during analysis execution:**

1. **NEVER ask the user for permission to proceed between phases.** After each phase completes, immediately continue to the next phase. The user asked for a complete analysis — deliver it in one continuous run.
2. **After Phase 2 agents complete, extract their results by reading the output files, then CONTINUE to Phase 3 without stopping.**
3. **Phases 3-6 run agents sequentially — each depends on the previous one's output. After each agent returns, immediately launch the next one. Do NOT pause for user confirmation.**
4. **Phase 7 is the final phase (NOT a sub-agent). It MUST produce TWO outputs in ONE message batch: (A) Write `analysis_report.md` via the Write tool, and (B) the final decision text. If either is missing, the analysis is incomplete. Do NOT output the decision text without also calling Write.**
5. **The workflow is complete ONLY when the report file has been written to `skills/stock-analysis-debate/tools/data/{TICKER}/{DATE}/analysis_report.md` AND confirmed to the user.**

6. **CN market skips Phase 1.5 and Segment Analyst entirely.** No `segments.yaml`, no segment data. Run 4 analysts.
7. **If `segments_fetch_failed.flag` exists**, treat as CN: skip Phase 1.5 and Segment Analyst, run 4 analysts. Note the missing segment view in the final report.

8. **DATA QUALITY CHECK (Phase 1.1):** After data is fetched, read `data_quality.json`. If `data_fresh: false`, use `data_as_of_date` as the report's effective date throughout. If `warning_no_200_sma: true`, 200 SMA must be reported as N/A.
9. **ARITHMETIC VERIFICATION (Phase 7):** Before writing the final report, verify: target_price = (profit × PE) / total_shares. If the numbers don't reconcile within 5%, flag and correct them. Also verify: forward_PE = current_price / forward_EPS. Cross-check market_cap = current_price × total_shares against the fundamentals.txt value.

## Workflow

1. **Phase 1: Data Collection** — Bash: `fetch_data.py`
   - Foreground, synchronous; wait for it to return before proceeding.

1.1. **Phase 1.1: Data Quality Check** — Read `data_quality.json` from the output directory
   - Check `data_as_of_date`: this is the effective date for all analysis. If different from the requested `date`, use `data_as_of_date` as the report timestamp.
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
| `ohlcv.csv` | OHLCV price data (60 days) | yfinance |
| `indicators.txt` | 13 technical indicators | stockstats via yfinance |
| `news.txt` | Company-specific news (30 days) | yfinance |
| `global_news.txt` | Macro/global news | yfinance Search |
| `fundamentals.txt` | 28 fundamental metrics | yfinance |
| `balance_sheet.csv` | Quarterly balance sheet | yfinance |
| `cashflow.csv` | Quarterly cash flow | yfinance |
| `income_stmt.csv` | Quarterly income statement | yfinance |
| `insider.txt` | Insider transactions | yfinance |
| `summary.json` | Metadata summary | — |

**Additional outputs (HK/US only):**

| File | Content | Source |
|------|---------|--------|
| `segments_financials.json` | 长桥原始分部数据（季度+财年） | 长桥 API1+API2（Phase 1 抓取） |
| `segments_financials.csv` | 预处理紧凑分部CSV | prepare_segments.py (Phase 1.5) |
| `news_meta.txt` | 新闻抓取/去重/去噪审计 | fetch_data.py |
| `segments_missing.flag` | 清单缺失标记（触发Phase 1.5生成） | fetch_data.py |
| `segments_fetch_failed.flag` | 长桥抓取失败标记（降级） | fetch_data.py |

**Ticker-level (no date, reused across runs):**

| File | Content | Source |
|------|---------|--------|
| `data/{TICKER}/segments.yaml` | 业务线清单（跨次复用） | prepare_segments.py --gen-yaml |

**After data is fetched**, immediately proceed to Phase 1.5 if applicable, otherwise go to Phase 2. Do not stop.

## Phase 1.5: Segment Setup (HK/US only)

**Skip conditions**: CN market, OR `segments_fetch_failed.flag` exists in the date dir.

1. Check `skills/stock-analysis-debate/tools/data/{TICKER}/segments.yaml` (ticker-level, no date).
   - If exists: read it, then run prepare_segments.py WITHOUT `--gen-yaml` to produce the day's `segments_financials.csv`:
     ```bash
     python skills/stock-analysis-debate/tools/prepare_segments.py {TICKER} {DATE} --output-dir skills/stock-analysis-debate/tools/data
     ```
   - If missing: run with `--gen-yaml` (generates both `segments.yaml` and the day's CSV):
     ```bash
     python skills/stock-analysis-debate/tools/prepare_segments.py {TICKER} {DATE} --output-dir skills/stock-analysis-debate/tools/data --gen-yaml
     ```
2. Read `segments.yaml`. Record `multi_segment` for Phase 2 branching.
3. Proceed immediately to Phase 2.

## Phase 2: Analyst Reports (Parallel, Single Message)

**CRITICAL**: Launch ALL 4 analyst agents in a SINGLE message as parallel Agent tool calls. Do NOT use `run_in_background` — use foreground calls so results return to the main conversation. The system will execute them in parallel and wait for all to complete.

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

**Segment Analyst** — Prompt: `skills/stock-analysis-debate/prompts/segment_analyst.md` — Data: `segments_financials.csv`, News Analyst's segment-hit summary (from `phase2_analyst_reports.md`).

Launch Segment Analyst IN PARALLEL with the other 4 only when `segments.yaml` has `multi_segment: true`. Otherwise run 4 analysts as before.

**After all 4 agents return**: Extract their full report texts from the agent responses (not the data files). Save each analyst's complete output to `skills/stock-analysis-debate/tools/data/{TICKER}/{DATE}/phase2_analyst_reports.md` using the Write tool. Then IMMEDIATELY proceed to Phase 3. Do NOT ask the user.

## Debate History File Protocol

**This protocol applies to ALL multi-round debates (Phase 3 Bull vs Bear, Phase 6 Risk Assessment). It is the only acceptable way to pass context between debate rounds.**

When running multi-round debates, use a **file as shared memory** to preserve complete, verbatim arguments across rounds.

**The sub-agent handles all file I/O itself.** The main session does NOT read or write the debate history file. It only tells each sub-agent:
- The file path to read/write
- Which round this is
- Which role it is playing (e.g., "Bull Round 1")
- The data files it needs (analyst reports, trader plan, etc.)

### File Paths

| Debate | File Path |
|--------|-----------|
| Bull vs Bear | `skills/stock-analysis-debate/tools/data/{TICKER}/{DATE}/debate_history.md` |
| Risk Assessment | `skills/stock-analysis-debate/tools/data/{TICKER}/{DATE}/risk_debate_history.md` |

### What each sub-agent MUST do (in order)

**1. Read the debate history file** using the Read tool.
   - If the file doesn't exist yet (Round 1), the history is empty — note this and proceed.
   - The agent must read the **FULL VERBATIM content**. Do NOT skip or skim.

**2. Read the data files** specified in its prompt (analyst reports, trader plan, etc.).

**3. Generate its debate argument**, directly engaging with every previous speaker's exact words.

**4. Append its complete output to the debate history file** using the Write tool (or create the file if Round 1). Use this format:
   ```
   ### [Agent Role] — Round N
   {paste the agent's ENTIRE response here verbatim}
   
   ---
   ```
   If the file exists, read old content + write old content + new entry. Do NOT edit, truncate, or summarize previous entries.

**Why this protocol exists**: Passing summarized/paraphrased context between agents causes information loss — key data points, nuanced arguments, and specific rebuttals are dropped. Having each sub-agent read the raw file directly ensures every debater sees the exact words of previous speakers, enabling precise counter-arguments. Delegating file I/O to sub-agents also keeps the main session context clean.

---

## Phase 3: Bull vs Bear Debate

Run **`debate_rounds`** rounds (default 2). Each round = 1 Bull call + 1 Bear call, sequential. **Sub-agents handle debate history file I/O themselves.** The main session only launches agents sequentially.

Debate history file: `skills/stock-analysis-debate/tools/data/{TICKER}/{DATE}/debate_history.md`

For each round, the main session tells the sub-agent: the file path, its role (Bull/Bear), the round number, total rounds, and where to find the data files. The sub-agent reads the debate history, reads data files, generates its argument, and appends to the file — all autonomously.

### Loop: For each round R = 1 to `debate_rounds`

**Bull Researcher (Round R)**
- **Tell the agent**: Role = Bull Researcher, Round = R of `debate_rounds`{is_final_marker}. Debate history file = `skills/stock-analysis-debate/tools/data/{TICKER}/{DATE}/debate_history.md`. Data file = `skills/stock-analysis-debate/tools/data/{TICKER}/{DATE}/phase2_analyst_reports.md`. If R == 1, the file may not exist yet (create it) and there is no Bear argument to counter. If R > 1, the file contains all prior rounds — respond to the Bear's latest argument. Include instrument context (market, ticker, currency, current price, trading rules).
- **After agent completes**: Immediately launch the Bear for this round.

**Bear Researcher (Round R)**
- **Tell the agent**: Role = Bear Researcher, Round = R of `debate_rounds`{is_final_marker}. Debate history file = `skills/stock-analysis-debate/tools/data/{TICKER}/{DATE}/debate_history.md`. Data file = `skills/stock-analysis-debate/tools/data/{TICKER}/{DATE}/phase2_analyst_reports.md`. The Bull has already written its Round R argument — read the file and respond. Include instrument context.
- **After agent completes**: If R < `debate_rounds`, go to next round (Bull). If R == `debate_rounds`, immediately go to Phase 4.

Where `{is_final_marker}` = " (final round)" if R == `debate_rounds`, otherwise empty string.

After Phase 3, the debate history file contains all rounds' complete, verbatim arguments (written by the sub-agents).

## Phase 4: Research Manager

- **Before**: Read the debate history file to get the complete Phase 3 debate verbatim. Read `phase2_analyst_reports.md` to get the 4 analyst reports verbatim.
- **Prompt**: `skills/stock-analysis-debate/prompts/research_manager.md`
- **Context in prompt**: Paste the FULL debate history file content verbatim. Paste ALL 4 analyst reports verbatim. Include instrument context (market type, currency, ticker, e.g. "601988.SH is a CN stock on Shanghai Stock Exchange, currency: CNY, ±10% price limit, T+1 settlement").
- **Task**: Judge the debate. Make definitive Buy/Sell/Hold decision. Produce investment plan with rationale + strategic actions.
- **After it returns**: Save the Research Manager's output to `skills/stock-analysis-debate/tools/data/{TICKER}/{DATE}/research_plan.md`. Immediately go to Phase 5.

## Phase 5: Trader

- **Before**: Read `research_plan.md` to get the Research Manager's plan verbatim. Read `phase2_analyst_reports.md` if needed.
- **Prompt**: `skills/stock-analysis-debate/prompts/trader.md`
- **Context in prompt**: Paste the Research Manager's full investment plan verbatim. Include instrument context. Paste the 4 analyst report summaries if helpful.
- Must end output with: `FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL**`
- **After it returns**: Save the Trader's output to `skills/stock-analysis-debate/tools/data/{TICKER}/{DATE}/trader_plan.md`. Immediately go to Phase 6.

---

## Phase 6: Risk Assessment Debate

Run **`risk_discuss_rounds`** rounds (default 2). Each round = 3 calls (Aggressive → Conservative → Neutral), sequential. **Sub-agents handle risk debate history file I/O themselves.**

Risk debate history file: `skills/stock-analysis-debate/tools/data/{TICKER}/{DATE}/risk_debate_history.md`

For every agent, the main session tells it: the file path, its role, the round number, total rounds, the trader plan file path (`trader_plan.md`), the analyst reports file path (`phase2_analyst_reports.md`), and instrument context.

### Loop: For each round R = 1 to `risk_discuss_rounds`

**Aggressive Risk Analyst (Round R)**
- **Tell the agent**: Role = Aggressive Risk Analyst, Round = R of `risk_discuss_rounds`{is_final_marker}. Risk debate history file = `skills/stock-analysis-debate/tools/data/{TICKER}/{DATE}/risk_debate_history.md`. Read trader plan from `trader_plan.md`, analyst reports from `phase2_analyst_reports.md`. If R == 1: file may not exist yet (create it), no other arguments to counter. If R > 1: file contains all prior rounds — respond to Conservative and Neutral from the previous round.
- **After agent completes**: Immediately launch Conservative for this round.

**Conservative Risk Analyst (Round R)**
- **Tell the agent**: Role = Conservative Risk Analyst, Round = R of `risk_discuss_rounds`{is_final_marker}. Risk debate history file = `skills/stock-analysis-debate/tools/data/{TICKER}/{DATE}/risk_debate_history.md`. Read trader plan and analyst reports. The Aggressive analyst has already written Round R — read the file and respond.
- **After agent completes**: Immediately launch Neutral for this round.

**Neutral Risk Analyst (Round R)**
- **Tell the agent**: Role = Neutral Risk Analyst, Round = R of `risk_discuss_rounds`{is_final_marker}. Risk debate history file = `skills/stock-analysis-debate/tools/data/{TICKER}/{DATE}/risk_debate_history.md`. Read trader plan and analyst reports. The file now contains Aggressive + Conservative for Round R (plus all prior rounds). Challenge both and deliver your assessment.
- **After agent completes**: If R < `risk_discuss_rounds`, go to next round (Aggressive). If R == `risk_discuss_rounds`, immediately go to Phase 7.

Where `{is_final_marker}` = " (final round)" if R == `risk_discuss_rounds`, otherwise empty string.

After Phase 6, the risk debate history file contains all rounds' complete, verbatim arguments (written by the sub-agents).

## Phase 7: Portfolio Manager — Final Decision + Report File (main session)

**This phase runs in the main session, NOT as a sub-agent.** The main session has orchestrated every phase and holds the most complete context.

**The phase produces TWO outputs. They MUST be called in the SAME tool call batch. Never split them across messages.**

---

### Step 1: Gather

Read these files to refresh the complete analysis record:

1. `skills/stock-analysis-debate/prompts/portfolio_manager.md` — output structure template (Rating scale, Executive Summary, Investment Thesis)
2. `phase2_analyst_reports.md` — 4 analyst reports
3. `debate_history.md` — Bull vs Bear debate (Phase 3)
4. `research_plan.md` — Research Manager's plan (Phase 4)
5. `trader_plan.md` — Trader's proposal (Phase 5)
6. `risk_debate_history.md` — Risk assessment debate (Phase 6)
7. `data_quality.json` — Data quality metadata (Phase 1.1)

### Step 1.5: Arithmetic Sanity Check (MANDATORY — do NOT skip)

Before synthesizing, verify these numbers with actual computation:

1. **Market Cap**: current_price × total_shares. Does it match the fundamentals.txt market cap? If discrepancy >10%, flag it.
2. **Forward PE**: current_price / forward_EPS. Does it match the reported Forward PE? Report both computed and stated values.
3. **Target Price**: For every target price in the debate, compute `(profit × PE) / total_shares` and verify it matches. If a debater claims "550亿 × 20x = 88元" but (550e8 × 20) / shares ≠ 88, this is a HARD ERROR. Flag and correct in the final report.
4. **Revenue/Net Income period labels**: If fundamentals analyst cited "2025全年" figures, verify they are >= the sum of visible quarters. If a column labeled "2025-12-31" is a single quarter, correct the label to "Q4 2025" in the final report.
5. **200 SMA**: If data_quality.json says `warning_no_200_sma: true`, any mention of "200 SMA" in analyst reports that uses a value other than N/A is invalid.

### Step 2: Synthesize

Produce the Portfolio Manager's final decision in the main session:

- **Rating**: Buy / Overweight / Hold / Underweight / Sell
- **Executive Summary**: Entry strategy, position sizing, risk levels, time horizon
- **Investment Thesis**: Reasoning anchored in specific evidence from the files above

### Step 3: Write Report + Output Decision

**This is the mandatory deliverable. The analysis is incomplete until the file is on disk.**

In a SINGLE tool call batch, do:

**Output A — Write tool**: Call Write to create `skills/stock-analysis-debate/tools/data/{TICKER}/{DATE}/analysis_report.md` with ALL sections populated:

```
# Stock Analysis Report: {TICKER} ({DATE})

## 1. Analyst Research
### Market Analysis
{paste the market analyst's full report}
### News Analysis
{paste the news analyst's full report}
### Sentiment Analysis
{paste the social media analyst's full report}
### Fundamentals Analysis
{paste the fundamentals analyst's full report}

## 2. Bull vs Bear Debate
{paste the full debate history}

## 3. Investment Plan
{paste the research manager's output}

## 4. Trading Proposal
{paste the trader's output}

## 5. Risk Assessment Debate
{paste the full risk debate history}

## 6. Final Decision
{paste the portfolio manager's output (Step 2 above)}
```

**Output B — Text**: A concise summary of the rating, price target, and key rationale so the user sees the result immediately.

After both outputs complete, confirm: "分析报告已保存至 skills/stock-analysis-debate/tools/data/{TICKER}/{DATE}/analysis_report.md"

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

- **Stopping between phases to ask the user**: This is the #1 failure mode. The user asked for a complete analysis. Run all phases back-to-back. If the user says "继续", you have ALREADY made this mistake — immediately proceed to the next unfinished phase.
- **Outputting Phase 7 text without calling Write on `analysis_report.md` in the SAME batch**: This is the #1 deliverable mistake. The Write call and the decision text MUST be part of the same tool call batch. If you output the decision text alone, the analysis is incomplete — it disappears when context scrolls. The `.md` file is the permanent record. If you catch yourself about to do this, STOP, add the Write call, send both together.
- **Modifying prompts**: The prompt files contain the EXACT prompts from the original code. Do NOT paraphrase or improve them. Read the file and pass its content verbatim.
- **Defaulting to Hold**: If both sides have valid points, pick the stronger argument. Hold is only for genuinely neutral situations.
- **Forgetting to include instrument context**: Every debate/judgment agent needs to know the market (US/CN/HK), currency, and ticker format.
- **Summarizing debate arguments instead of passing verbatim text**: This is the #1 information-loss bug. When launching a Phase 3 or Phase 6 debate agent, do NOT paste debate history into the agent prompt — the sub-agent reads the file itself. The main session only tells the agent WHERE the file is and WHAT its role/round is. See "Debate History File Protocol" above for the mandatory file-I/O-by-sub-agent approach.
