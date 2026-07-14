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

## Workflow

1. **Phase 1: Data Collection** — Bash: `fetch_data.py`
   - Foreground, synchronous; wait for it to return before proceeding.

2. **Phase 2: Analyst Reports** — 4 Agent calls
   - Parallel: launch ALL 4 in a SINGLE message, foreground (no `run_in_background`).

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

**After data is fetched**, immediately proceed to Phase 2. Do not stop.

## Phase 2: Analyst Reports (Parallel, Single Message)

**CRITICAL**: Launch ALL 4 analyst agents in a SINGLE message as parallel Agent tool calls. Do NOT use `run_in_background` — use foreground calls so results return to the main conversation. The system will execute them in parallel and wait for all to complete.

**IMPORTANT**: Tell each agent to read its prompt file AND the data files it needs. Include summaries of the key data directly in the agent prompt so the agent doesn't need to discover which files to read.

### The 4 Analysts (launch simultaneously in one message):

**Market Analyst** — Prompt: `skills/stock-analysis-debate/prompts/market_analyst.md` — Data: `ohlcv.csv`, `indicators.txt`

**News Analyst** — Prompt: `skills/stock-analysis-debate/prompts/news_analyst.md` — Data: `news.txt`, `global_news.txt`

**Social Media Analyst** — Prompt: `skills/stock-analysis-debate/prompts/social_media_analyst.md` — Data: `news.txt`

**Fundamentals Analyst** — Prompt: `skills/stock-analysis-debate/prompts/fundamentals_analyst.md` — Data: `fundamentals.txt`, `balance_sheet.csv`, `cashflow.csv`, `income_stmt.csv`

**After all 4 agents return**: Extract their full report texts from the agent responses (not the data files). Save each analyst's complete output to `skills/stock-analysis-debate/tools/data/{TICKER}/{DATE}/phase2_analyst_reports.md` using the Write tool. Then IMMEDIATELY proceed to Phase 3. Do NOT ask the user.

## Debate History File Protocol

**This protocol applies to ALL multi-round debates (Phase 3 Bull vs Bear, Phase 6 Risk Assessment). It is the only acceptable way to pass context between debate rounds.**

When running multi-round debates, use a **file as shared memory** to preserve complete, verbatim arguments across rounds.

### File Paths

| Debate | File Path |
|--------|-----------|
| Bull vs Bear | `skills/stock-analysis-debate/tools/data/{TICKER}/{DATE}/debate_history.md` |
| Risk Assessment | `skills/stock-analysis-debate/tools/data/{TICKER}/{DATE}/risk_debate_history.md` |

### Protocol (must follow exactly for EVERY debate step)

**Step A — BEFORE launching the debate agent:**

1. Read the debate history file using the Read tool.
2. If the file doesn't exist yet (first round), the history is empty — nothing to read.
3. In the agent's prompt, include the **FULL VERBATIM content of the debate history file** as the `history` context. Do NOT summarize, abbreviate, or paraphrase any previous arguments. The debater must see the complete, unaltered text of every previous speaker.

**Step B — AFTER the agent returns:**

1. Append the agent's complete output to the debate history file using the Write tool. Use this format:
   ```
   ### [Agent Role] — Round N
   {paste the agent's ENTIRE response here verbatim}
   
   ---
   ```
2. If the file doesn't exist yet, create it. If it exists, append to it (read old content + write old content + new entry).
3. Do NOT edit, truncate, or summarize the agent's response before writing it.

**Why this protocol exists**: Passing summarized/paraphrased context between agents causes information loss — key data points, nuanced arguments, and specific rebuttals are dropped. The file ensures every debater reads the exact words of previous speakers, enabling precise counter-arguments.

---

## Phase 3: Bull vs Bear Debate (4 Sequential Calls)

Run 4 sequential Agent calls, back-to-back. **Apply the Debate History File Protocol for every step.**

Debate history file: `skills/stock-analysis-debate/tools/data/{TICKER}/{DATE}/debate_history.md`

### Step 3a: Bull Researcher (Round 1)
- **Before**: Read `phase2_analyst_reports.md` to get the 4 analyst reports. Since this is Round 1, the debate history file is empty — no history to read yet.
- **Prompt**: `skills/stock-analysis-debate/prompts/bull_researcher.md`
- **Context in prompt**: Paste ALL 4 analyst reports verbatim. Set `history` to empty. Set `current_response` to empty (no bear argument yet).
- **After it returns**: Write the bull's full output to the debate history file. Immediately go to 3b.

### Step 3b: Bear Researcher (Round 1)
- **Before**: Read the debate history file to get the bull's Round 1 argument verbatim.
- **Prompt**: `skills/stock-analysis-debate/prompts/bear_researcher.md`
- **Context in prompt**: Paste ALL 4 analyst reports verbatim. Set `history` to the full debate history file content. Set `current_response` to the bull's Round 1 argument verbatim.
- **After it returns**: Append the bear's full output to the debate history file. Immediately go to 3c.

### Step 3c: Bull Researcher (Round 2)
- **Before**: Read the debate history file to get the complete bull R1 + bear R1 arguments verbatim.
- **Prompt**: `skills/stock-analysis-debate/prompts/bull_researcher.md`
- **Context in prompt**: Paste ALL 4 analyst reports verbatim. Set `history` to the full debate history file content. Set `current_response` to the bear's Round 1 argument verbatim.
- **After it returns**: Append the bull's R2 output to the debate history file. Immediately go to 3d.

### Step 3d: Bear Researcher (Round 2, final)
- **Before**: Read the debate history file to get the complete history (bull R1, bear R1, bull R2) verbatim.
- **Prompt**: `skills/stock-analysis-debate/prompts/bear_researcher.md`
- **Context in prompt**: Paste ALL 4 analyst reports verbatim. Set `history` to the full debate history file content. Set `current_response` to the bull's Round 2 argument verbatim.
- **After it returns**: Append the bear's R2 output to the debate history file. Immediately go to Phase 4.

After Phase 3, the debate history file contains all 4 complete, verbatim arguments.

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

## Phase 6: Risk Assessment Debate (6 Sequential Calls)

Run 2 rounds of 3 roles each. **Apply the Debate History File Protocol for every step.**

Risk debate history file: `skills/stock-analysis-debate/tools/data/{TICKER}/{DATE}/risk_debate_history.md`

**Context shared across all 6 calls**: Paste the Trader's full plan verbatim (from `trader_plan.md`). Paste ALL 4 analyst reports verbatim (from `phase2_analyst_reports.md`).

### Round 1

**Step 6a: Aggressive (Round 1)**
- **Before**: Read `trader_plan.md` and `phase2_analyst_reports.md`. Risk debate history is empty (first round).
- **Prompt**: `skills/stock-analysis-debate/prompts/aggressive_debator.md`
- **Context**: Trader's plan verbatim + all 4 reports verbatim + empty history. No conservative/neutral arguments yet.
- **After**: Write aggressive's output to the risk debate history file. Immediately go to 6b.

**Step 6b: Conservative (Round 1)**
- **Before**: Read the risk debate history file to get aggressive's argument verbatim.
- **Prompt**: `skills/stock-analysis-debate/prompts/conservative_debator.md`
- **Context**: Trader's plan verbatim + all 4 reports verbatim + full risk debate history (aggressive's R1 argument verbatim). No neutral argument yet.
- **After**: Append conservative's output to the risk debate history file. Immediately go to 6c.

**Step 6c: Neutral (Round 1)**
- **Before**: Read the risk debate history file to get aggressive + conservative arguments verbatim.
- **Prompt**: `skills/stock-analysis-debate/prompts/neutral_debator.md`
- **Context**: Trader's plan verbatim + all 4 reports verbatim + full risk debate history verbatim.
- **After**: Append neutral's output to the risk debate history file. Immediately go to 6d.

### Round 2

**Step 6d: Aggressive (Round 2)**
- **Before**: Read the risk debate history file to get all 3 Round 1 arguments verbatim.
- **Prompt**: `skills/stock-analysis-debate/prompts/aggressive_debator.md`
- **Context**: Trader's plan verbatim + all 4 reports verbatim + full risk debate history verbatim. Set `current_conservative_response` and `current_neutral_response` to their Round 1 arguments verbatim.
- **After**: Append aggressive's R2 output to the risk debate history file. Immediately go to 6e.

**Step 6e: Conservative (Round 2)**
- **Before**: Read the risk debate history file to get all previous arguments verbatim.
- **Prompt**: `skills/stock-analysis-debate/prompts/conservative_debator.md`
- **Context**: Trader's plan verbatim + all 4 reports verbatim + full risk debate history verbatim. Set `current_aggressive_response` to aggressive's R2 verbatim.
- **After**: Append conservative's R2 output to the risk debate history file. Immediately go to 6f.

**Step 6f: Neutral (Round 2, final)**
- **Before**: Read the risk debate history file to get all 5 previous arguments verbatim.
- **Prompt**: `skills/stock-analysis-debate/prompts/neutral_debator.md`
- **Context**: Trader's plan verbatim + all 4 reports verbatim + full risk debate history verbatim. Set `current_aggressive_response` and `current_conservative_response` to their Round 2 arguments verbatim.
- **After**: Append neutral's R2 output to the risk debate history file. Immediately go to Phase 7.

After Phase 6, the risk debate history file contains all 6 complete, verbatim arguments.

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
- **Summarizing debate arguments instead of passing verbatim text**: This is the #1 information-loss bug. When launching a Phase 3 or Phase 6 debate agent, you MUST read the debate history file and paste its FULL content into the agent prompt. Do NOT write a summary in your own words — the debater needs to see the EXACT words of previous speakers to make precise counter-arguments. See "Debate History File Protocol" above for the mandatory file-based approach.
