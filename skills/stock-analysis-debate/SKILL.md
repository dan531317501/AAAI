---
name: stock-analysis-debate
description: Use when the user wants to analyze a stock (US/CN/HK markets), explain recent price behavior, and get a Buy/Hold/Sell recommendation backed by evidence-graded price attribution and a multi-agent debate using real market data.
---

# Stock Analysis with Multi-Agent Debate

## Overview

Conduct a professional stock analysis by orchestrating multiple AI agents in a structured debate. Agents play specialized roles — Market Analyst, News Analyst, Social Media Analyst, Fundamentals Analyst, Options Flow Analyst (US-listed equities only), Price Action Attribution Analyst, Bull/Bear Researchers, Trader, Aggressive/Conservative/Neutral Risk Analysts, and Portfolio Manager — to explain recent price behavior and produce a data-backed investment recommendation (Buy/Overweight/Hold/Underweight/Sell).

Data is fetched primarily from **yfinance** (OHLCV, benchmark/sector comparators, expectation records, news, fundamentals, financial statements), with **Longbridge daily K-lines** filling missing latest OHLCV dates for US/HK/SH/SZ stocks, and **stockstats** computing technical indicators.

## Critical Execution Rules

**These rules override all other instructions during analysis execution:**

1. **NEVER ask the user for permission to proceed between phases.** After each phase completes, immediately continue to the next phase. The user asked for a complete analysis — deliver it in one continuous run.
2. **Phase 2 has TWO steps. Step 1 launches the applicable base analysts in parallel. After their files are verified, Step 2 launches exactly one Price Action Attribution Analyst, which reads the base reports and attribution data and writes `price_action_attribution_analyst.md`. Only after both steps are verified may Phase 3 start. Every analyst writes directly to its own file and returns only a short write confirmation; the main session never aggregates analyst responses.**
3. **Phases 3-6 run agents sequentially — each depends on the previous one's output. After each agent returns, immediately launch the next one. Do NOT pause for user confirmation.**
4. **Phase 7 is the final phase (NOT a sub-agent). It MUST produce TWO outputs in ONE message batch: (A) Write `analysis_report.md` via the Write tool, and (B) the final decision text. If either is missing, the analysis is incomplete. Do NOT output the decision text without also calling Write.**
5. **The workflow is complete ONLY when the report file has been written to `skills/stock-analysis-debate/reposrts/{TICKER}/reports/{DATE}/analysis_report.md` AND confirmed to the user.**

6. **CN market skips Phase 1 Step 3 (Segment Setup) and Segment Analyst entirely.** No `segments.yaml`, no segment data. Run 4 Step 1 analysts (options flow is US-only), then the mandatory Price Action Attribution Analyst in Step 2.
7. **If `segments_fetch_failed.flag` exists**, skip Segment Analyst, run every other applicable Step 1 analyst (including Options Flow for US equities), then the mandatory Price Action Attribution Analyst in Step 2. Note the missing segment view in the final report.
8. **Options Flow Analyst runs ONLY for US-listed equities.** For HK/CN markets `options.txt` contains a Not Rated placeholder; the Options Flow Analyst must not run and options evidence must not influence the rating, target price, position sizing, or risk limits.

9. **REPORT DATE:** `{DATE}` is the execution/analysis date and is the ONLY date allowed in the report title and output directory. Treat `data_as_of_date` only as the market-data cutoff and disclose it separately. Even when `data_fresh: false`, write exactly one report to `reposrts/{TICKER}/reports/{DATE}/analysis_report.md`; never create or copy another report under `data_as_of_date`. If `warning_no_200_sma: true`, 200 SMA must be reported as N/A.
10. **ARITHMETIC VERIFICATION (Phase 7):** Before writing the final report, verify TTM EPS/P/E reconciliation, target_price = (profit × PE) / total_shares, forward_PE = current_price / forward_EPS, and market_cap = current_price × total_shares. If values conflict beyond the stated tolerance, disclose and correct them before producing the rating.
11. **NEWS/SENTIMENT EVIDENCE:** Treat `news.txt` evidence IDs and content levels as hard boundaries. If `Social Data Available: false`, social sentiment is Not Rated and must not affect the rating, target price, position sizing, or risk limits. If `options.txt` marks options flow Not Rated, the same restriction applies to options evidence.

12. **PRICE ATTRIBUTION EVIDENCE:** The Price Action Attribution Analyst ranks competing hypotheses; it does not prove a unique cause or issue a rating, target price, position size, or trade. No pre-event expectation means the surprise/priced-in claim is Not Rated. No comparator means abnormal return is Not Rated. No stock-specific leverage/short/flow evidence means forced liquidation, short squeeze, or investor identity is not established. Oversold/overbought is a state, not a catalyst.

13. **CONTEXT HYGIENE (main session):** The main session's context is reserved for orchestration, decision synthesis, and deliverables:
    - Every Phase 2 analyst writes its own report file and returns only a short confirmation — never the full report.
    - The Price Action Attribution Analyst is the only Phase 2 role required to read all available Step 1 reports; it reads raw files only to verify material attribution claims.
    - Debate/risk agents write their own files (File I/O protocol) and return only short confirmations/summaries — never their full arguments.
    - Downstream agents read only the reports and raw data needed for their current role. Give them the report/data directory paths and mandatory prior-phase artifacts; never paste file contents into agent prompts.
    - Never Read a file whose content is already in the main context (own Write output).
    - At Phase 7, read only the unseen reports and raw data required for final claims and debate adjudication; arithmetic verification is delegated to the Step 2 sub-agent and is never re-run in the main session. Files already in the main context are not re-read.

14. **ONE-RETRY POLICY:** Every phase and every agent call allows exactly ONE retry at the smallest granularity. Retry only the failed step — a failed `fetch_data.py`/`prepare_segments.py` run (Phase 1), a single failed analyst (Phase 2), one debate round or one risk-debate role (Phases 3/6), or one failed downstream agent (Phases 4/5) — never re-run completed work. If the retry also fails, STOP the entire workflow immediately, report the failed step to the user, and do NOT continue to later phases.

## Output Directory Contract

Keep fetched data and generated reports in separate directory trees for every analysis:

| Output | Directory |
|--------|-----------|
| Raw and derived data | `skills/stock-analysis-debate/reposrts/{TICKER}/data/{DATE}/` |
| Reports and workflow artifacts | `skills/stock-analysis-debate/reposrts/{TICKER}/reports/{DATE}/` |
| Individual analyst reports | `skills/stock-analysis-debate/reposrts/{TICKER}/reports/{DATE}/{ROLE}_analyst.md` |

Set these paths once at the start of the run and pass absolute paths to every sub-agent. Never write report artifacts into the data directory, and never write fetched or derived datasets into the report directory. Create the report directory before Phase 2.

## On-Demand Read Protocol

Do not create a combined Phase 2 report, summary file, manifest, or concatenated analyst output. Keep each analyst result only in its role-specific file.

For Phase 2 Step 2 and Phases 3-7:

1. Provide the absolute report directory, data directory, and mandatory artifact from the immediately preceding phase.
2. Let the active agent select and read only the individual reports and raw data needed for its role and claims.
3. Except for the Price Action Attribution Analyst's required Step 1 report intake, do not require every phase to read every `*_analyst.md` or data file.
4. Treat missing optional evidence as Not Rated and disclose the gap when it affects the conclusion; do not fabricate a replacement summary.

## Workflow

1. **Phase 1: Data Collection & Validation** — Bash `fetch_data.py`, then read `data_quality.json`, then (HK/US only) segment setup via `prepare_segments.py`. All foreground, synchronous; wait for each to return before proceeding. Details in the Phase 1 section below (Steps 1-3).

2. **Phase 2: Analyst Reports** — 5 to 7 Agent calls in two steps
   - Step 1: launch 4 to 6 base analysts in a SINGLE message, foreground (no `run_in_background`).
   - Options Flow Analyst runs ONLY for US-listed equities.
   - Segment Analyst runs ONLY for HK/US with `multi_segment: true` in `segments.yaml`.
   - Step 2: after all Step 1 files are verified, run one Price Action Attribution Analyst sequentially.
   - Each analyst writes directly to its assigned file under `reposrts/{TICKER}/reports/{DATE}/`; the main session only verifies the files.

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

## Phase 1: Data Collection & Validation

Three sequential steps, all foreground and synchronous (wait for each to return before proceeding):

**Step 1: Fetch data.** Run synchronously via Bash:

```bash
python skills/stock-analysis-debate/tools/fetch_data.py <TICKER> <DATE> --ticker-data-dir skills/stock-analysis-debate/reposrts/<TICKER>/data
```

**Failure retry**: If the fetch fails, retry the exact command once. If the retry also fails, STOP the workflow and report the failure to the user (rule 14).

**First-time setup** (install dependencies if not present):
```bash
pip install -r skills/stock-analysis-debate/tools/requirements.txt
```

Output is saved to `skills/stock-analysis-debate/reposrts/{TICKER}/data/{DATE}/` containing:

| File | Content | Source |
|------|---------|--------|
| `ohlcv.csv` | OHLCV price data (up to the configured 350-calendar-day lookback) | yfinance + Longbridge latest-date fallback |
| `price_context.json` | Broad-market/sector comparator metadata, 1/5/20-session absolute and excess returns, and 60-session aligned daily context; each unavailable comparator degrades independently to Not Rated | yfinance + price_attribution_data.py |
| `expectations.txt` | Retrieval-time consensus snapshot, historical earnings-surprise records, recent rating actions, and strict point-in-time use rules | yfinance + price_attribution_data.py |
| `indicators.txt` | 13 technical indicators | stockstats via yfinance/Longbridge OHLCV |
| `news.txt` | Company-specific news with evidence IDs, content levels, available summaries, processing audit, and explicit social-data availability (30 days) | yfinance + fetch_data.py |
| `global_news.txt` | Macro/global news | yfinance Search |
| `macro_indicators.txt` | FRED macro series: fed funds rate, 10y Treasury, yield curve, CPI, core CPI, unemployment (degrades to Not Rated placeholder without `FRED_API_KEY`) | FRED API | 
| `prediction_markets.txt` | Polymarket event probabilities: Fed rate cut, recession, US election (per-topic graceful degradation) | Polymarket Gamma API |
| `fundamentals.txt` | Provider fundamentals plus point-in-time valuation, TTM EPS/P/E reconciliation, and GAAP operating-profit audit | yfinance + financial_audit.py |
| `balance_sheet.csv` | Quarterly balance sheet | yfinance |
| `cashflow.csv` | Quarterly cash flow | yfinance |
| `income_stmt.csv` | Quarterly income statement | yfinance |
| `insider.txt` | Insider transactions | yfinance |
| `options.txt` | Options flow: put/call volume & OI ratios, IV levels/skew, most-active contracts (US only; Not Rated placeholder for HK/CN) | yfinance option chain | 
| `summary.json` | Metadata summary | — |

**Additional outputs (HK/US only):**

| File | Content | Source |
|------|---------|--------|
| `revenue_sankey.json` | Longbridge quarterly Sankey data; preserves all original nodes and links and adds classification, QoQ/YoY, segment mix, consolidated reconciliation, and segment completeness checks | Longbridge revenue-sankey API (fetched in Phase 1) |
| `revenue_sankey.csv` | Enhanced Sankey nodes for recent periods, used for business-segment and profit-structure analysis | prepare_segments.py (Phase 1 Step 3) |
| `segments_missing.flag` | Missing segment-manifest marker that triggers Phase 1 Step 3 generation | fetch_data.py |
| `segments_fetch_failed.flag` | Longbridge fetch-failure marker used for graceful degradation | fetch_data.py |

**Ticker-level (no date, reused across runs):**

| File | Content | Source |
|------|---------|--------|
| `reposrts/{TICKER}/data/segments.yaml` | Reusable cross-run business-segment manifest | prepare_segments.py --gen-yaml |

**Step 2: Data quality check.** Read `data_quality.json` from the output directory:
- Keep the requested execution `date` as the report date and output-directory date. Use `data_as_of_date` only for statements about how current the market data is. If the dates differ, disclose both explicitly and do not generate a second report.
- Check `trading_days`: note how many trading days are available for indicators.
- Check `warning_no_200_sma`: if true, 200 SMA is NOT computable.
- Check `indicator_sufficiency`: each indicator has a `sufficient` boolean and `min_days` threshold.
- Record any `notes` warnings for inclusion in the final report.

**Step 3: Segment Setup (HK/US only)**

**Skip conditions**: CN market, OR `segments_fetch_failed.flag` exists in the date dir.

1. Check `skills/stock-analysis-debate/reposrts/{TICKER}/data/segments.yaml` (ticker-level, no date).
   - If exists: read it, then run prepare_segments.py WITHOUT `--gen-yaml` to produce the day's `revenue_sankey.csv`:
     ```bash
     python skills/stock-analysis-debate/tools/prepare_segments.py {TICKER} {DATE} --ticker-data-dir skills/stock-analysis-debate/reposrts/{TICKER}/data
     ```
   - If missing: run with `--gen-yaml` (generates `segments.yaml` and `revenue_sankey.csv`):
     ```bash
     python skills/stock-analysis-debate/tools/prepare_segments.py {TICKER} {DATE} --ticker-data-dir skills/stock-analysis-debate/reposrts/{TICKER}/data --gen-yaml
     ```
2. Read `segments.yaml`. Record `multi_segment` for Phase 2 branching.
3. **Failure retry**: If Step 3 fails, retry the failed `prepare_segments.py` command once. If the retry also fails, STOP the workflow and report the failure to the user (rule 14).
4. Proceed immediately to Phase 2.

See `prompts/segment_analyst.md` for data interpretation rules and `prepare_segments.py` plus `longbridge_fetcher.py` for tool-level processing logic.
- `reconciliation_status=mismatch` → the tool raises an exception, Phase 1 Step 3 fails, and no CSV is generated.
- A non-empty `segment_completeness_status` → the analyst must disclose the incomplete data in the report.

## Phase 2: Analyst Reports (Two Steps, Direct File Output)

**CRITICAL**: Step 1 launches the applicable base analysts (4 base analysts, plus the conditional Options Flow Analyst [US only] and Segment Analyst [HK/US + multi_segment only]) in a SINGLE message as parallel Agent tool calls. Do NOT use `run_in_background` — use foreground calls so results return to the main conversation. Wait for all Step 1 agents before starting Step 2. Step 2 is one sequential Price Action Attribution Analyst call and must never run in parallel with Step 1.

**IMPORTANT — Main session must NOT read prompt files or data files before dispatching analysts.** Each sub-agent reads its own prompt file and data files via the Read tool — the main session reading them too is pure context waste. The main session only tells each agent:
- Full absolute file paths to: its prompt file + all required data files
- One unique absolute output path under `reposrts/{TICKER}/reports/{DATE}/`
- Instrument context: ticker, market, currency, current price
- Phase 1 quality-check findings: data_as_of_date, trading_days, warning_no_200_sma flag, indicator_sufficiency summary
- For Segment Analyst: also mention the segment list from `segments.yaml`

Every analyst task must end with this file protocol:

1. Read the assigned prompt and data files.
2. Write the complete analysis directly to the assigned output file.
3. Verify that the output file exists and is non-empty.
4. Return only a one-line confirmation containing the role and output path; never return the report body to the main session.

The sub-agent discovers everything else by reading the files itself.

### Step 1 — The Base Analysts (launch simultaneously in one message)

All analysts listed below launch IN THE SAME parallel batch: the 4 base analysts always run; the conditional Options Flow and Segment analysts join the batch only when their conditions are met. There are no sub-steps within Step 1.

**Market Analyst** — Prompt: `skills/stock-analysis-debate/prompts/market_analyst.md` — Data: `ohlcv.csv`, `indicators.txt` — Output: `market_analyst.md`

**News Analyst** — Prompt: `skills/stock-analysis-debate/prompts/news_analyst.md` — Data: `news.txt`, `global_news.txt`, `macro_indicators.txt`, `prediction_markets.txt` — Output: `news_analyst.md`

**Social Media Analyst** — Prompt: `skills/stock-analysis-debate/prompts/social_media_analyst.md` — Data: `news.txt` — Output: `social_media_analyst.md`

**Fundamentals Analyst** — Prompt: `skills/stock-analysis-debate/prompts/fundamentals_analyst.md` — Data: `fundamentals.txt`, `balance_sheet.csv`, `cashflow.csv`, `income_stmt.csv` — Output: `fundamentals_analyst.md`

**Options Flow Analyst**(Conditional 5th Analyst (US market only)) — Prompt: `skills/stock-analysis-debate/prompts/options_flow_analyst.md` — Data: `options.txt` — Output: `options_flow_analyst.md`

Launch Options Flow Analyst IN PARALLEL with the other 4 only when the market is **US** (yfinance option chains are reliable only for US-listed equities). For HK/CN markets `options.txt` contains a Not Rated placeholder — do NOT launch the Options Flow Analyst.

**Segment Analyst**(Conditional 6th Analyst (HK/US + multi_segment only)) — Prompt: `skills/stock-analysis-debate/prompts/segment_analyst.md` — Data: `revenue_sankey.csv`, `income_stmt.csv` — Output: `segment_analyst.md`.

Launch Segment Analyst IN PARALLEL with the other analysts only when `segments.yaml` has `multi_segment: true`. Otherwise run the applicable analysts (US: 5 including Options Flow; HK: 4; CN: 4) as before.

**After all Step 1 agents return**: Verify that every expected Step 1 output exists and is non-empty. Do not read or combine successful reports in the main session. If an analyst failed or its output file is missing/empty, retry only that analyst once with the same output path. If the retry also fails, STOP the entire workflow immediately and report the failed analyst to the user (rule 14); do not create a synthetic analyst report and do not continue to Step 2.

### Step 2 — Price Action Attribution Analyst (mandatory, sequential)

Run only after every Step 1 output has been verified.

**Price Action Attribution Analyst** — Prompt: `skills/stock-analysis-debate/prompts/price_action_attribution_analyst.md` — Reports: every available Step 1 `*_analyst.md` in the report directory — Required data (pass as full absolute paths in the data directory): `{DATA_DIR}/price_context.json`, `{DATA_DIR}/expectations.txt`, `{DATA_DIR}/ohlcv.csv`, `{DATA_DIR}/indicators.txt`, `{DATA_DIR}/news.txt` — Conditional evidence (pass every file as a FULL absolute path under the data directory, never as a bare filename): `{DATA_DIR}/global_news.txt`, `{DATA_DIR}/macro_indicators.txt`, `{DATA_DIR}/prediction_markets.txt`, `{DATA_DIR}/fundamentals.txt`, `{DATA_DIR}/balance_sheet.csv`, `{DATA_DIR}/cashflow.csv`, `{DATA_DIR}/income_stmt.csv`, `{DATA_DIR}/options.txt` — Output: `price_action_attribution_analyst.md`.

Provide the absolute prompt path, report directory, data directory, output path, instrument context, Phase 1 quality findings, and the list of failed/missing Step 1 roles. The analyst must read all available Step 1 reports, verify only its material claims against raw artifacts, rank competing hypotheses, and produce conditional outlooks without issuing a rating, target price, position size, or transaction recommendation.

After it returns, verify `price_action_attribution_analyst.md` exists and is non-empty. Retry the attribution analyst once if the file is missing/empty. If the retry also fails, STOP the entire workflow immediately and report the failure to the user (rule 14); do NOT proceed to Phase 3 and do NOT ask the user.

## Debate History File Protocol

Multi-round debates use **files as shared memory**. Each sub-agent reads/writes the debate history file autonomously — the main session never touches these files. The File I/O protocol is defined in each debate agent's prompt file (`bull_researcher.md`, `bear_researcher.md`, `aggressive_debator.md`, `conservative_debator.md`, `neutral_debator.md`).

| Debate | File Path |
|--------|-----------|
| Bull vs Bear | `skills/stock-analysis-debate/reposrts/{TICKER}/reports/{DATE}/debate_history.md` |
| Risk Assessment | `skills/stock-analysis-debate/reposrts/{TICKER}/reports/{DATE}/risk_debate_history.md` |

The main session only tells each agent: the file path, its role, the round number, and paths to the data files it needs.

---

## Phase 3: Bull vs Bear Debate

Run **`debate_rounds`** rounds (default 2). Each round: Bull → Bear, sequential. Sub-agents handle debate history file I/O via the protocol in their prompts.

For each agent, provide: role, round N of total, debate history file path, report directory, data directory, and instrument context. Require the agent to read `price_action_attribution_analyst.md` when available, challenge at least its primary attribution or its main alternative, and verify decisive counterclaims against the underlying reports/data. The attribution report is a hypothesis ranking, not an authority. Identify any analyst role that failed so the agent does not assume that evidence exists.

**Return protocol**: Each debate agent appends its full argument to the debate history file and returns ONLY a one-line status confirmation (role, round, file write succeeded) per the Step 4 protocol in its prompt. The main session must NOT read `debate_history.md` during Phase 3 — it is shared memory between debate agents and read later by the Research Manager (which reads it itself) and at Phase 7 (when the main session reads it to write the report summaries).

Debate history file: `skills/stock-analysis-debate/reposrts/{TICKER}/reports/{DATE}/debate_history.md`
Supporting evidence: read individual reports and raw data from the report/data directories only as needed

**Failure retry**: If a debate agent fails or does not append its argument to the debate history file, retry only that agent (same role and round) once. If the retry also fails, STOP the entire workflow immediately and report the failed round to the user (rule 14).

After Phase 3, proceed immediately to Phase 4.

## Phase 4: Research Manager

- **Before**: Do NOT preload debate, analyst, or data files in the main session — the sub-agent reads what it needs itself (see rule 13).
- **Prompt**: `skills/stock-analysis-debate/prompts/research_manager.md`
- **Context in prompt**: Full absolute paths to `debate_history.md`, the report directory, and the data directory. The agent must read `debate_history.md` and `price_action_attribution_analyst.md` when available, adjudicate the debate's challenges to the primary attribution/priced-in assessment, then read only the additional reports/data needed to judge specific claims. Identify any missing analyst role. Include instrument context (market type, currency, ticker, e.g. "601988.SH is a CN stock on Shanghai Stock Exchange, currency: CNY, ±10% price limit, T+1 settlement").
- **Task**: Judge the debate. Make definitive Buy/Sell/Hold decision. Produce investment plan with rationale + strategic actions.
- **After it returns**: The agent writes its complete plan directly to `skills/stock-analysis-debate/reposrts/{TICKER}/reports/{DATE}/research_plan.md`, verifies the file exists and is non-empty, and returns only a short confirmation/summary — never the full plan.
- **Failure retry**: If the Research Manager fails or `research_plan.md` is missing/empty, retry the agent once. If the retry also fails, STOP the entire workflow immediately and report the failure to the user (rule 14).
- Immediately go to Phase 5.

## Phase 5: Trader

- **Before**: Do NOT preload `research_plan.md`, analyst reports, or data files in the main session — the sub-agent reads what it needs itself (see rule 13).
- **Prompt**: `skills/stock-analysis-debate/prompts/trader.md`
- **Context in prompt**: Full absolute paths to `research_plan.md`, the report directory, and the data directory. The agent must read `research_plan.md`, then read only the individual reports/data needed to produce and verify the trade plan. Include instrument context.
- Must end output with: `FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL**`
- For staged entries, require the Trader to output incremental and cumulative weights and verify that their sum does not exceed the maximum position. Include portfolio capital in context only when known; otherwise dollar amounts and share counts must be N/A.
- **After it returns**: The agent writes its complete proposal directly to `skills/stock-analysis-debate/reposrts/{TICKER}/reports/{DATE}/trader_plan.md`, verifies the file exists and is non-empty, and returns only a short confirmation/summary — never the full proposal. The proposal must still end with `FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL**`.
- **Failure retry**: If the Trader fails or `trader_plan.md` is missing/empty, retry the agent once. If the retry also fails, STOP the entire workflow immediately and report the failure to the user (rule 14).
- Immediately go to Phase 6.

---

## Phase 6: Risk Assessment Debate

Run **`risk_discuss_rounds`** rounds (default 2). Each round: Aggressive → Conservative → Neutral, sequential. Sub-agents handle risk debate history file I/O via the protocol in their prompts.

For each agent, provide: role, round N of total, risk debate history file path, trader plan file path, report directory, data directory, and instrument context. The agent reads `trader_plan.md` plus only the reports/data needed for its risk argument. Identify any analyst role that failed.

**Return protocol**: Each risk debator appends its full assessment to the risk debate history file and returns ONLY a short summary (final stance, revised position plan with incremental/cumulative weights, 3-5 core argument bullets) per the Step 4 protocol in its prompt. The main session uses these returns during Phase 3-6 and at Phase 7 Reads `risk_debate_history.md` itself to write the report summaries.

Risk debate history file: `skills/stock-analysis-debate/reposrts/{TICKER}/reports/{DATE}/risk_debate_history.md`
Trader plan: `skills/stock-analysis-debate/reposrts/{TICKER}/reports/{DATE}/trader_plan.md`
Supporting evidence: read individual reports and raw data from the report/data directories only as needed

**Failure retry**: If a risk debator fails or does not append its assessment to the risk debate history file, retry only that agent (same role and round) once. If the retry also fails, STOP the entire workflow immediately and report the failed round to the user (rule 14).

After Phase 6, proceed immediately to Phase 7.

## Phase 7: Portfolio Manager — Final Decision + Report File (main session)

**This phase runs in the main session, NOT as a sub-agent** — with ONE exception: Step 2 (Arithmetic Sanity Check) runs as a dedicated sub-agent so its raw-data reads and computations never pollute the main session context. The main session has orchestrated every phase and holds the most complete context.

**The phase produces TWO outputs. They MUST be called in the SAME tool call batch. Never split them across messages.**

---

### Step 1: Gather

Apply the on-demand read protocol from rule 13:

- Read `portfolio_manager.md` for the required output structure.
- Read `debate_history.md` when adjudicating Bull/Bear arguments and `risk_debate_history.md` when deriving the final position plan.
- Read `research_plan.md` and `trader_plan.md` when writing the Investment Plan and Trading Proposal report summaries.
- Read `price_action_attribution_analyst.md` when explaining the recent move, adjudicating priced-in claims, or deriving continuation/reversal conditions.
- Read only the `*_analyst.md` files needed to support or challenge claims used in the final decision.
- Do NOT read raw data for Step 2 verification — the Arithmetic Verifier sub-agent (Step 2) reads and recomputes every raw input itself. Read raw data in the main session only for claims the final decision itself must cite: `fundamentals.txt` and `indicators.txt` are required when valuation or technical claims are used; read `options.txt` only for US equities when options evidence is available and relevant.
- Do not re-read `data_quality.json` when its content is already present in the main context.
- Do not create any intermediate combined or summary file while gathering evidence.

### Step 2: Arithmetic Sanity Check (MANDATORY — do NOT skip) — sub-agent

Run the 18-point arithmetic and evidence-integrity check as a dedicated SUB-AGENT so its raw-data reads and computations stay out of the main session context:

1. Launch ONE foreground Agent call with prompt `skills/stock-analysis-debate/prompts/arithmetic_verifier.md` (contains the full 18 checks). Do NOT use `run_in_background`.
2. Pass: absolute report directory and data directory paths; the list of `*_analyst.md`, `debate_history.md`, `risk_debate_history.md`, `research_plan.md`, and `trader_plan.md` files whose numeric claims must be verified; and the output path `skills/stock-analysis-debate/reposrts/{TICKER}/reports/{DATE}/arithmetic_verification.md`. The sub-agent reads every raw file it needs (`fundamentals.txt`, `indicators.txt`, `ohlcv.csv`, `price_context.json`, `options.txt`, `news.txt`, `data_quality.json`) itself.
3. Output contract: the sub-agent writes its full findings (PASS/FLAG per check, recomputed vs claimed value, required correction) directly to `arithmetic_verification.md` and returns only a short confirmation. The main session must NOT read the raw verification inputs; if the Final Decision needs a verified number, read `arithmetic_verification.md` instead.
4. Failure retry (rule 14): if the sub-agent fails or `arithmetic_verification.md` is missing/empty, retry the sub-agent once. If the retry also fails, STOP the entire workflow immediately and report the failure to the user; do NOT proceed to Step 3.

### Step 3: Synthesize

Produce the Portfolio Manager's final decision in the main session. The Final Decision is the single most important deliverable — it must be a **fully-argued conclusion**, not a summary. A Final Decision that merely restates the rating, entry points, and a one-paragraph thesis is INCOMPLETE and must be expanded. Every claim must be anchored to specific evidence: numeric values, evidence IDs (e.g., [N005]), analyst verdicts, or debate-file passages.

Before synthesizing, read `arithmetic_verification.md` (Step 2's output). Its flags and corrections BIND the Final Decision: recompute, do not copy — apply every FLAG to the sections below before writing the report, and never restate a number the verifier flagged without the correction.

The Final Decision MUST contain, in order:

1. **Rating** — one of Buy / Overweight / Hold / Underweight / Sell, a one-line verdict, AND one line on the key reason for choosing this rating over its nearest alternatives (e.g., why Overweight rather than Buy, or why Buy rather than Hold).
2. **Executive Summary** — one coherent paragraph (not bullets-only): the business case in one or two sentences with figures, the best-supported recent price attribution and its confidence, entry strategy, position sizing, key risk levels including the thesis-level invalidation condition, a tactical reference band if computable (e.g., options-implied range; otherwise Bollinger/structure levels), and the time horizon.
3. **Decision Logic Chain** — explicit reasoning for the rating vs EVERY other plausible choice: why not Sell/Underweight (hard-bottom evidence with figures), why not Hold (asymmetric payoff already priced), why not a one-shot full position (evidence-grade discount). Each justification cites data.
4. **Core Thesis with Evidence Anchors** — 3-6 numbered arguments; each = claim + concrete evidence (figure, [Nxxx] ID, analyst report, or debate passage) + explicit rebuttal of the opposing view on that point. May be organized as grouped anchors (e.g., "facts anchoring the bullish direction" vs "facts anchoring the caution") when the debate's residual disagreement splits that way.
5. **Debate Adjudication** — what the bull side won on (with evidence), what the bear side won on (with evidence), which arguments were dismissed and why, AND the facts neither side disputed (uncontested consensus — often the strongest basis for the rating direction), and the net ruling that leads to this rating.
6. **Scenarios & Target Price Derivation** — base/optimistic/pessimistic scenarios with their conditions; reconcile them with the attribution report's continuation/reversal conditions; show the arithmetic chain behind the target price (e.g., multiple × TTM EBITDA → EV → equity value ÷ shares), cross-checked against technical measures (e.g., double-bottom measured move) and the debate's own targets. Recompute, do not copy.
7. **Risk Levels & Verification Nodes** — two layers: (a) thesis-level invalidation (the sustained condition that would overturn the entire thesis, with its evidence threshold); (b) tactical stop/reference levels with structural derivation (ATR-calibrated, structure-based). Plus the upcoming verification event (e.g., earnings) that would confirm or invalidate the thesis.
8. **Final Position Plan with Derivation** — the maximum position weight AND the reasoning that picked it among the risk-debate proposals (which proposal won and why, with the arithmetic); if the risk debate revised the trader's initial schedule, state the initial → final evolution and the evidence reason for each change; staged table with trigger / incremental / cumulative / entry price; arithmetic verification statement.
9. **Data Caveats** — Not Rated items (social, options, macro, expectation baseline, comparators, leverage/short/flow evidence), TTM/forward valuation conflicts and which anchor was used, missing statements.

Sections 2-8 must carry the specific numbers and evidence they derive from — summary prose without data is not acceptable. Prioritize readability: lead with conclusions, use tables for comparisons and evidence, keep paragraphs short (one point each), and bold key figures — avoid wall-of-text prose.

### Step 4: Write Report + Output Decision

**This is the mandatory deliverable. The analysis is incomplete until the file is on disk.**

In ONE continuous sequence (Write, then text — same turn), do:

**Output A — Write tool**: Call Write to create `skills/stock-analysis-debate/reposrts/{TICKER}/reports/{DATE}/analysis_report.md` with ALL sections populated. The main session writes the report summaries ITSELF (based on Step 1's Gather) — natural-language summaries, one short paragraph or bullet list per section. **Final Decision is FIRST.** Structure (fixed):

```
# Stock Analysis Report: {TICKER} ({DATE})

**Report Date**: {DATE} | **Market Data As Of**: {data_as_of_date}

## Final Decision
{portfolio manager's full decision — first, structured per Step 3's 9 mandatory sections: Rating (+ key reason) / Executive Summary / Decision Logic Chain / Core Thesis with Evidence Anchors / Debate Adjudication (incl. uncontested consensus) / Scenarios & Target Price Derivation / Risk Levels & Verification Nodes (thesis-level invalidation + tactical stops) / Final Position Plan with Derivation (incl. initial → final schedule evolution) / Data Caveats. A 1-2 paragraph verdict is NOT a complete Final Decision.}

## 1. Analyst Research
{key evidence used from the individual analyst reports — include only reports relevant to the final decision}

Individual reports (include only analysts that ran):
- [Market Analyst](./market_analyst.md)
- [News Analyst](./news_analyst.md)
- [Social Media Analyst](./social_media_analyst.md)
- [Fundamentals Analyst](./fundamentals_analyst.md)
- [Options Flow Analyst](./options_flow_analyst.md)
- [Segment Analyst](./segment_analyst.md)
- [Price Action Attribution Analyst](./price_action_attribution_analyst.md)

## 2. Price Action Attribution
{the primary Trigger/Surprise, principal Amplifier, abnormal-return evidence, Fundamental Anchor, competing explanation, priced-in classification, continuation/reversal conditions, confidence, and material Not Rated gaps}

Full attribution: [price_action_attribution_analyst.md](./price_action_attribution_analyst.md)

## 3. Bull vs Bear Debate
{summary of the debate — each side's stance, key arguments, convergence points}

Full debate: [debate_history.md](./debate_history.md)

## 4. Investment Plan
{summary of the research manager's plan}

Full plan: [research_plan.md](./research_plan.md)

## 5. Trading Proposal
{summary of the trader's proposal}

Full proposal: [trader_plan.md](./trader_plan.md)

## 6. Risk Assessment Debate
{summary of the risk debate — each role's stance, position plans, convergence}

Full debate: [risk_debate_history.md](./risk_debate_history.md)
```

**Output B — Text**: A concise summary of the rating, price target, and key rationale so the user sees the result immediately.

After both outputs complete, confirm: "The analysis report has been saved to skills/stock-analysis-debate/reposrts/{TICKER}/reports/{DATE}/analysis_report.md"

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
| `analysts` | all applicable Step 1 roles; attribution always runs | Which base analysts to run (market, social, news, fundamentals, options [US only], segment [conditional]); Price Action Attribution remains mandatory after Step 1 |
| `date` | today | Analysis date in YYYY-MM-DD |

## Common Mistakes

- **Modifying prompts**: Prompt files contain the exact prompts. Do NOT paraphrase or improve them. Pass verbatim.
- **Defaulting to Hold**: If both sides have valid points, pick the stronger argument. Hold only for genuinely neutral situations.
- **Forgetting instrument context**: Every debate/judgment agent needs market (US/CN/HK), currency, ticker format, and trading rules.
- **Context bloat**: Do NOT paste file contents into agent prompts or require each phase to read every report/data file. The Price Action Attribution Analyst reads all Step 1 reports by design; every other downstream role reads only the evidence needed for its claims. Do not re-read content already in the main context. See rule 13 and the On-Demand Read Protocol.
- **Post-hoc attribution**: Do not convert a nearby headline, an oversold reading, or a large rebound into a proven cause. Require expectation, timing, abnormal-return, and mechanism evidence; preserve competing hypotheses and Not Rated gaps.
- **Anemic Final Decision**: A Final Decision that only restates the rating, entry points, and a one-paragraph thesis is incomplete (see Phase 7 Step 3). It must contain all 9 sections — Rating with key reason, Executive Summary, Decision Logic Chain (why not the other ratings), evidence-anchored thesis, Debate Adjudication (including uncontested consensus), scenario/target-price derivation, layered risk levels (thesis-level invalidation + tactical stops), position-plan derivation (which risk-debate proposal won and why, initial → final evolution), and Data Caveats — each carrying the specific numbers and evidence it derives from.
