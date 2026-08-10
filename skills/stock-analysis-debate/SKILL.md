---
name: stock-analysis-debate
description: Use when the user wants to analyze a stock (US/CN/HK markets), explain recent price behavior, or get a Buy/Hold/Sell recommendation backed by deterministic tool-layer data validation, currency-normalized valuation, official-disclosure fallbacks, evidence-graded attribution, and multi-agent debate.
---

# Stock Analysis with Multi-Agent Debate

## Overview

Conduct a professional stock analysis by orchestrating multiple AI agents in a structured debate. Agents play specialized roles — Market Analyst, News Analyst, Social Media Analyst, Fundamentals Analyst, Options Flow Analyst (US current research only), Price Action Attribution Analyst, Bull/Bear Researchers, Trader, Aggressive/Conservative/Neutral Risk Analysts, and Portfolio Manager — to explain recent price behavior and produce a data-backed investment recommendation (Buy/Overweight/Hold/Underweight/Sell).

Data is fetched primarily from **yfinance** (OHLCV, benchmark/sector comparators, dedicated analyst-estimate tables, news, fundamentals, financial statements), with **Longbridge daily K-lines** filling missing latest OHLCV dates for US/HK/SH/SZ stocks using market-aware, fail-closed volume normalization, and **stockstats** computing technical indicators. Provider calls use classified exponential retries. Official disclosures are discovered through HKEXnews, SEC EDGAR/XBRL, or CNINFO as market-appropriate fallbacks; `official_document_parser.py` deterministically converts text-based PDF/HTML disclosures into canonical facts, and free API facts only fill missing metric-period keys. No LLM extracts numbers from filings, and official facts are never overwritten by API fallback values.

## Critical Execution Rules

**These rules override all other instructions during analysis execution:**

1. **NEVER ask the user for permission to proceed between phases.** After each phase completes, immediately continue to the next phase. The user asked for a complete analysis — deliver it in one continuous run.
2. **Phase 2 has TWO steps. Start every applicable base analyst concurrently, wait for all scheduled roles, and verify their files. Then start exactly one Price Action Attribution Analyst, which reads the base reports and attribution data and writes `price_action_attribution_analyst.md`. Only after both steps are verified may Phase 3 start.**
3. **Phases 3-6 run role tasks sequentially because each depends on the previous task's persisted artifact.**
4. **FINAL DELIVERABLE CONTRACT:** Phase 7 runs in the main session. In the same assistant turn, write and verify `skills/stock-analysis-debate/reposrts/{TICKER}/reports/{DATE}/analysis_report.md`, then return the user-visible decision summary and confirm the path. The workflow is incomplete if either deliverable fails; never report success before file verification.

5. **CN market skips Phase 1 Step 3 (Segment Setup) and Segment Analyst entirely.** No `segments.yaml`, no segment data. Run 4 Step 1 analysts (options flow is US-only), then the mandatory Price Action Attribution Analyst in Step 2.
6. **If `segments_fetch_failed.flag` exists**, skip Segment Analyst, run every other applicable Step 1 analyst (including Options Flow for US current research), then the mandatory Price Action Attribution Analyst in Step 2. Note the missing segment view in the final report.
7. **Options Flow Analyst runs ONLY for US-listed equities in `current_research`.** For HK/CN markets and every `historical_replay`, `options.txt` contains a Not Rated placeholder and the analyst must not run. For eligible US current research, the yfinance aggregate snapshot authorizes only activity concentration and approximate implied-pricing observations: volume/OI cannot establish opening/closing status, buyer/seller direction, strategy, or participant identity. Options evidence must not directly determine the rating, target price, position sizing, or risk limits. Read `reference/options-volume-open-interest-and-sentiment.en.md` only when interpreting or changing these boundaries.

8. **REPORT DATE AND TIME MODE — GLOBAL:** Use `current_research` by default. `{DATE}` is always the actual local execution date and the only date allowed in the report title and output directory. `historical_replay` requires `--as-of-date`; disclose its market-timezone `analysis_timestamp` and label the report as a replay. Treat `data_as_of_date` only as the latest market observation, never as the report date. If `warning_no_200_sma: true`, 200 SMA is N/A.
9. **EVIDENCE, GATE, AND DATA ACCESS CONTRACT — GLOBAL:** Phase 1 collects and validates data. Phase 2 is the only analysis phase allowed to read the current run's data directory; every Phase 2 report must carry forward each material claim's source file and field/row, period/as-of date, metric status/allowed uses, relevant gate outcome/blocking reasons, and material Not Rated gaps. Phases 3-7 use only persisted reports and required prior-phase artifacts and must never receive, open, search, or cite the data directory. Apply `temporal_context.source_statuses`, `validated_metrics`, and all gates fail-closed: unavailable, stale, conflicting, translated-only, temporally blocked, or otherwise blocked evidence remains N/A or Not Rated. Prefer tool-derived values; do not use an LLM to recompute returns, growth, TTM, margins, valuation multiples, or technical indicators, infer missing values, backfill historical snapshots, treat placeholders/flags as evidence, or numerically extract unstructured filings.
10. **NEWS/SENTIMENT EVIDENCE:** Treat `news.txt` evidence IDs and content levels as hard boundaries. If `stocktwits.txt` or `reddit.txt` contains a Not Rated placeholder, the corresponding social source is Not Rated and must not affect the rating, target price, position sizing, or risk limits. If `options.txt` marks options flow Not Rated, the same restriction applies to options evidence.

11. **PRICE ATTRIBUTION EVIDENCE:** The Price Action Attribution Analyst ranks competing hypotheses; it does not prove a unique cause or issue a rating, target price, position size, or trade. No pre-event expectation means the surprise/priced-in claim is Not Rated. No comparator means abnormal return is Not Rated. No stock-specific leverage/short/flow evidence means forced liquidation, short squeeze, or investor identity is not established. Oversold/overbought is a state, not a catalyst.

12. **PORTFOLIO APPLICABILITY — GLOBAL:** Apply `prompts/portfolio_policy.md` before Phase 4. Default to `research_only`; incomplete context always downgrades to that mode. In `research_only`, keep security-level entry/invalidation conditions but output `Position Size: Not Rated — complete portfolio context was not supplied.` and no allocation percentages, capital, or shares. Agent consensus never substitutes for portfolio context or risk-budget arithmetic.

13. **CONTEXT HYGIENE (main session):** The main session's context is reserved for orchestration, decision synthesis, and deliverables:
    - Give every role the resolved instrument context: ticker, market, analysis mode, execution date, analysis timestamp, quote currency, financial currency, FX status, as-of price, and market trading rules.
    - Every Phase 2 analyst writes its own report file and returns only a short confirmation — never the full report.
    - The Price Action Attribution Analyst is the only Phase 2 role required to read all available Step 1 reports; it reads raw files only to verify material attribution claims.
    - Debate/risk agents own their history files and return only short confirmations/summaries — never their full arguments. The main session does not read those histories during Phases 3 or 6; designated downstream roles read them directly, and the main session reads them only for Phase 7 synthesis.
    - Never Read a file whose content is already in the main context (own Write output).
    - At Phase 7, read only unseen reports required for final synthesis. Files already in the main context are not re-read.

14. **ONE-RETRY POLICY — SINGLE FAILURE SOURCE OF TRUTH:** Resolve role applicability before scheduling work. An unavailable optional source degrades to Not Rated and may make its conditional role inapplicable; this is not a scheduled-role failure. Every scheduled unit has at most two total attempts: the initial attempt plus exactly one retry of that unit. A successful return is insufficient without its required non-empty artifact. After a second failure, enter terminal `FAILED`, report the failed unit, and do not execute any later state. Never re-run a completed unit. This policy also covers final report persistence.

15. **LANGUAGE CONTRACT — GLOBAL:** Use English for every machine-generated data key, label, note, summary, and narrative under the run's data directory, and for every persisted Phase 2-6 report or workflow artifact, including `Evidence Handoff`, `debate_history.md`, `research_plan.md`, `trader_plan.md`, and `risk_debate_history.md`. Preserve provider-supplied source text verbatim when it is a non-English news/filing title, proper noun, quotation, company name, or segment name; keep its evidence ID and link, and add an English explanation only when needed. Do not rewrite or silently translate raw source evidence. Write only the final `analysis_report.md` in Simplified Chinese: translate all narrative, headings, labels, table headers, caveats, and conclusions while preserving tickers, identifiers, formulas, filenames, source paths, evidence IDs, and rating tokens when exact tokens are required. No other persisted report may use Chinese-authored prose. This global rule overrides the language of every prompt, example, section name, and template below; do not repeat it in phase-specific instructions.

## Output Directory Contract

Keep fetched data and generated reports in separate directory trees for every analysis:

Structured artifacts use `tools/structured_io.py::STRUCTURED_OUTPUT_FORMAT`. The default is `toon`, so the paths below use `.toon`; if the variable is changed to `json`, use the same basenames with `.json`. Never mix extensions within one run.

| Output | Directory |
|--------|-----------|
| Raw and derived data | `skills/stock-analysis-debate/reposrts/{TICKER}/data/{DATE}/` |
| Reports and workflow artifacts | `skills/stock-analysis-debate/reposrts/{TICKER}/reports/{DATE}/` |
| Individual analyst reports | `skills/stock-analysis-debate/reposrts/{TICKER}/reports/{DATE}/{ROLE}_analyst.md` |

Set these paths once at the start of the run. Never write report artifacts into the data directory, and never write fetched or derived datasets into the report directory. Create the report directory before Phase 2.

## Report Artifact Handoff Protocol

Do not create a combined Phase 2 report, summary file, manifest, or concatenated analyst output. Keep each analyst result only in its role-specific file.

Preserve every existing report-to-report dependency. Give each downstream role the report directory and mandatory artifact from the immediately preceding phase, then let it select only the persisted reports needed for its claims. Treat missing optional evidence as Not Rated; do not fabricate a replacement summary.

## Workflow State Machine

This table is the only phase-transition contract. State is inferred from verified artifacts; do not create a workflow manifest or separate state file.

| State | Required prior evidence | Work | Completion evidence |
|---|---|---|---|
| `START` | Resolved ticker, execution date, analysis mode, data directory, and report directory | Create the two output directories and resolve applicable roles | Paths and applicability are fixed for the run |
| `DATA_READY` | `START` | Run data collection and validation; run segment preparation only when applicable | Non-empty decodable `data_quality`, `validated_metrics`, and `validation_report.md`; segment outputs or an allowed pre-scheduling degradation |
| `BASE_ANALYSTS_READY` | `DATA_READY` | Start all applicable base analyst roles concurrently | Every scheduled base role file exists and is non-empty |
| `ATTRIBUTION_READY` | `BASE_ANALYSTS_READY` | Run Price Action Attribution Analyst | `price_action_attribution_analyst.md` exists and is non-empty |
| `DEBATE_READY` | `ATTRIBUTION_READY` | Run Bull then Bear for every configured round | `debate_history.md` contains every scheduled role/round entry |
| `RESEARCH_READY` | `DEBATE_READY` | Run Research Manager | `research_plan.md` exists and is non-empty |
| `TRADER_READY` | `RESEARCH_READY` | Run Trader | `trader_plan.md` exists, is non-empty, and ends with the required proposal marker |
| `RISK_READY` | `TRADER_READY` | Run Aggressive, Conservative, then Neutral for every configured round | `risk_debate_history.md` contains every scheduled role/round entry |
| `REPORT_WRITTEN` | `RISK_READY` | Apply the gate outcomes propagated through Phase 2 reports and persist the final report | `analysis_report.md` exists, is non-empty, and contains the required final-decision sections |
| `COMPLETE` | `REPORT_WRITTEN` | Return the concise user-visible decision summary in the same assistant turn | Report path and decision summary are both delivered |

## Workflow

1. **Phase 1: Data Collection & Validation** — Run `fetch_data.py` synchronously, inspect the configured `data_quality` artifact (`.toon` by default), then perform segment setup when applicable. Wait for each required artifact before proceeding. Details are in the Phase 1 section below.

2. **Phase 2: Analyst Reports** — two steps
   - Step 1: start all applicable base roles concurrently according to rules 5-7, then wait for every scheduled role.
   - Step 2: after all Step 1 files are verified, run one Price Action Attribution Analyst sequentially.
   - Each analyst writes directly to its assigned file under `reposrts/{TICKER}/reports/{DATE}/`; the main session only verifies the files.

3. **Phase 3: Bull vs Bear Debate**
   - Sequential: one at a time (2 rounds × Bull/Bear).

4. **Phase 4: Research Manager**
   - Sequential; depends on Phase 3 output.

5. **Phase 5: Trader**
   - Sequential; depends on Phase 4 output.

6. **Phase 6: Risk Debate**
   - Sequential: one at a time (3 roles × 2 rounds).

7. **Phase 7: Portfolio Manager + Final Report** — Main-session synthesis and report persistence

## Phase 1: Data Collection & Validation

Three sequential steps, all foreground and synchronous (wait for each to return before proceeding):

**Step 1: Fetch data.** Run synchronously using the runtime's command-execution capability:

```bash
python skills/stock-analysis-debate/tools/fetch_data.py <TICKER> <DATE> --ticker-data-dir skills/stock-analysis-debate/reposrts/<TICKER>/data
```

For a historical replay, keep `<DATE>` as today's execution date and pass the separate cutoff:

```bash
python skills/stock-analysis-debate/tools/fetch_data.py <TICKER> <DATE> --analysis-mode historical_replay --as-of-date <HISTORICAL_DATE> --ticker-data-dir skills/stock-analysis-debate/reposrts/<TICKER>/data
```

**First-time setup** (install dependencies if not present):
```bash
pip install -r skills/stock-analysis-debate/tools/requirements.txt
```

Output is saved to `skills/stock-analysis-debate/reposrts/{TICKER}/data/{DATE}/` containing:

| File | Content | Source |
|------|---------|--------|
| `ohlcv.csv` | OHLCV price data (up to the configured 350-calendar-day lookback) | yfinance + Longbridge latest-date fallback |
| `price_context.toon` | Broad-market/sector comparator metadata, 1/5/20-session absolute and excess returns, and 60-session aligned daily context; each unavailable comparator degrades independently to Not Rated | yfinance + price_attribution_data.py |
| `expectations.txt` | Current mode: retrieval-time consensus/event context; historical replay: explicit Not Rated placeholder | yfinance + price_attribution_data.py |
| `instrument_metadata.toon` | API-reported quote currency, financial currency, estimate-currency evidence, and retrieval timestamp | yfinance explicit metadata fields |
| `analyst_estimates.toon` | Dedicated earnings/revenue estimates, EPS trend/revisions, currency, periods, and analyst counts | yfinance estimate endpoints |
| `indicators.txt` | 13 technical indicators | stockstats via yfinance/Longbridge OHLCV |
| `news.txt` | Company-specific news with evidence IDs, content levels, available summaries, and processing audit (30 days); social data is NOT in this file (see `stocktwits.txt` / `reddit.txt`) | yfinance + fetch_data.py |
| `stocktwits.txt` | Retail-trader cashtag posts with user-labeled Bullish/Bearish tags and a Bullish/Bearish ratio; degrades to Not Rated placeholder | StockTwits public stream (no key) |
| `reddit.txt` | Finance-subreddit discussion (r/wallstreetbets, r/stocks, r/investing, past 7 days) via RSS; degrades to Not Rated placeholder | Reddit public RSS |
| `global_news.txt` | Macro/global news | yfinance Search |
| `macro_indicators.txt` | FRED macro series: fed funds rate, 10y Treasury, yield curve, CPI, core CPI, unemployment (degrades to Not Rated placeholder without `FRED_API_KEY`) | FRED API | 
| `prediction_markets.txt` | Polymarket event probabilities: Fed rate cut, recession, US election (per-topic graceful degradation) | Polymarket Gamma API |
| `fundamentals.txt` | Provider fundamentals plus point-in-time valuation, TTM EPS/P/E reconciliation, and GAAP operating-profit audit | yfinance + financial_audit.py |
| `balance_sheet.csv` | Quarterly balance sheet | yfinance |
| `cashflow.csv` | Quarterly cash flow | yfinance |
| `income_stmt.csv` | Quarterly income statement | yfinance |
| `insider.txt` | Insider transactions | yfinance |
| `official_filings.toon` | Official filing discovery evidence and structured/unstructured ingestion boundary | HKEXnews / SEC EDGAR / CNINFO |
| `official_companyfacts.toon` | SEC structured XBRL facts when available (US only) | SEC EDGAR Company Facts API |
| `official_financials.toon` | Unified official filing/fact contract with document parsing audit, source, period, unit, currency, raw tag, source URL/page, extraction method, API fallback provenance and fail-closed numeric status | SEC EDGAR XBRL / HKEXnews / CNINFO (SSE/SZSE) / free API fallback |
| `validated_metrics.toon` | Typed, fail-closed numeric contract with temporal context, source fields, currencies, periods, statuses, allowed uses, and decision gates | data_validation.py |
| `validation_report.md` | Deterministic summary of currency, TTM continuity, unavailable metrics, and decision gates | data_validation.py |
| `options.txt` | Options activity and implied pricing: put/call volume and prior-settlement OI mix, approximate ±5% moneyness IV difference, most-active contracts, and high-volume/prior-OI activity flags; no directional-flow inference (US only; Not Rated placeholder for HK/CN) | yfinance option chain |
| `data_quality.toon` | Execution/as-of/retrieval time context, per-source temporal status, data freshness, trading-day counts, indicator sufficiency, validation gates, and retry events | fetch_data.py + temporal_policy.py |
| `summary.toon` | Metadata summary | — |

In `historical_replay`, the tool writes explicit Not Rated placeholders instead of retrieval-time fundamentals, statements, estimates, global/macro/prediction context, insider, options, and segment snapshots. Only date-bounded price artifacts, timestamp-filtered company news, and cutoff-filtered official disclosures remain allowed; read `temporal_context.source_statuses` for the authoritative per-source result.

**Additional outputs (HK/US only):**

| File | Content | Source |
|------|---------|--------|
| `revenue_sankey.toon` | Longbridge quarterly Sankey data; preserves all original nodes and links and adds classification, QoQ/YoY, segment mix, consolidated reconciliation, and segment completeness checks | Longbridge revenue-sankey API (fetched in Phase 1) |
| `revenue_sankey.csv` | Enhanced Sankey nodes for recent periods, used for business-segment and profit-structure analysis | prepare_segments.py (Phase 1 Step 3) |
| `segments_missing.flag` | Missing segment-manifest marker that triggers Phase 1 Step 3 generation | fetch_data.py |
| `segments_fetch_failed.flag` | Longbridge fetch-failure marker used for graceful degradation | fetch_data.py |

**Ticker-level (no date, reused across runs):**

| File | Content | Source |
|------|---------|--------|
| `reposrts/{TICKER}/data/segments.yaml` | Reusable cross-run business-segment manifest | prepare_segments.py --gen-yaml |

**Step 2: Data quality check.** Read the configured `data_quality` artifact (`data_quality.toon` by default) from the output directory:
- Read `temporal_context`: record `analysis_mode`, `execution_date`, `analysis_timestamp`, and every `source_statuses` entry. Do not dispatch an analyst with a blocked source as usable evidence.
- Check `trading_days`: note how many trading days are available for indicators.
- Check `warning_no_200_sma`: if true, 200 SMA is NOT computable.
- Check `indicator_sufficiency`: each indicator has a `sufficient` boolean and `min_days` threshold.
- Record any `notes` warnings for inclusion in the final report.
- Read the configured `validated_metrics` artifact (`validated_metrics.toon` by default) and `validation_report.md`. Stop before Phase 2 if either is missing, invalid structured data, or empty.
- Treat `validation_gates` as hard controls and read the matching `gate_details`. A false `allow_exact_valuation`, `allow_target_price`, `allow_strong_rating`, or `allow_segment_growth` gate prohibits that output; it is not an invitation for an agent to reconstruct the missing data. A true `allow_strong_rating` confirms numeric prerequisites only: Buy/Sell additionally requires Phase 7 to verify valid relative-return evidence, a traceable catalyst, and a traceable thesis-invalidation condition. Otherwise cap the final rating at Overweight/Underweight/Hold.
- Inspect `provider_retry_events` for exhausted or non-retryable provider failures and disclose the affected domain as degraded.

**Step 3: Segment Setup (HK/US only)**

Apply the segment-setup applicability and degradation rules in rules 5-6 before running this step.

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
3. Verify the required segment-preparation artifacts.

See `prompts/segment_analyst.md` for data interpretation rules and `prepare_segments.py` plus `longbridge_fetcher.py` for tool-level processing logic.
- `reconciliation_status=mismatch` → the tool raises an exception, Phase 1 Step 3 fails, and no CSV is generated.
- A non-empty `segment_completeness_status` → the analyst must disclose the incomplete data in the report.

## Phase 2: Analyst Reports (Two Steps, Direct File Output)

**CRITICAL**: Start all roles applicable under rules 5-7 concurrently. Wait for all scheduled roles and verify their artifacts before starting Step 2. Step 2 is one sequential Price Action Attribution Analyst task and must never overlap Step 1.

Each delegated role reads its own assigned files using the Read tool. The main session provides:
- Full absolute file paths to: its prompt file + all required data files
- One unique absolute output path under `reposrts/{TICKER}/reports/{DATE}/`
- Instrument context
- Phase 1 quality-check findings: data_as_of_date, trading_days, warning_no_200_sma flag, indicator_sufficiency summary
- For Segment Analyst: also mention the segment list from `segments.yaml`

Every analyst task must end with this file protocol:

Before the role-specific prompt, every analyst must read `prompts/data_policy.md`, the configured `{DATA_DIR}/validated_metrics` artifact (`.toon` by default), and `{DATA_DIR}/validation_report.md`. These three paths are mandatory in every analyst task. The role-specific current-run data artifacts listed below are authorized domain evidence; they cannot bypass a status, allowed use, or gate for a metric covered by `validated_metrics`.

1. Read the assigned prompt and data files.
2. Write the complete analysis directly to the assigned output file, including the `Evidence Handoff` required by rule 9.
3. Verify that the output file exists and is non-empty.
4. Follow the return contract in rule 13.

The sub-agent discovers everything else by reading the files itself.

### Step 1 — The Base Analysts (launch simultaneously in one message)

All analysts listed below launch IN THE SAME parallel batch: the 4 base analysts always run; the conditional Options Flow and Segment analysts join the batch only when their conditions are met. There are no sub-steps within Step 1.

**Market Analyst** — Prompt: `skills/stock-analysis-debate/prompts/market_analyst.md` — Data: `ohlcv.csv`, `indicators.txt` — Output: `market_analyst.md`

**News Analyst** — Prompt: `skills/stock-analysis-debate/prompts/news_analyst.md` — Data: `news.txt`, `global_news.txt`, `macro_indicators.txt`, `prediction_markets.txt` — Output: `news_analyst.md`

**Social Media Analyst** — Prompt: `skills/stock-analysis-debate/prompts/social_media_analyst.md` — Data: `news.txt`, `stocktwits.txt`, `reddit.txt` — Output: `social_media_analyst.md`

**Fundamentals Analyst** — Prompt: `skills/stock-analysis-debate/prompts/fundamentals_analyst.md` — Data: configured `validated_metrics` artifact (`.toon` by default), `validation_report.md`, `fundamentals.txt`, `balance_sheet.csv`, `cashflow.csv`, `income_stmt.csv` — Output: `fundamentals_analyst.md`

**Options Flow Analyst** (conditional 5th analyst; apply rule 7) — Prompt: `skills/stock-analysis-debate/prompts/options_flow_analyst.md` — Data: `options.txt` — Output: `options_flow_analyst.md`

**Segment Analyst** (conditional 6th analyst; apply rules 5-6) — Prompt: `skills/stock-analysis-debate/prompts/segment_analyst.md` — Data: `revenue_sankey.csv`, `income_stmt.csv` — Output: `segment_analyst.md`.

**After all Step 1 roles settle**: Verify that every scheduled output exists and is non-empty. Do not read or combine successful reports in the main session; never create a synthetic analyst report.

### Step 2 — Price Action Attribution Analyst (mandatory, sequential)

Run only after every Step 1 output has been verified.

**Price Action Attribution Analyst** — Prompt: `skills/stock-analysis-debate/prompts/price_action_attribution_analyst.md` — Reports: every available Step 1 `*_analyst.md` in the report directory — Required data (pass as full absolute paths in the data directory): `{DATA_DIR}/price_context.toon`, `{DATA_DIR}/expectations.txt`, `{DATA_DIR}/ohlcv.csv`, `{DATA_DIR}/indicators.txt`, `{DATA_DIR}/news.txt` — Conditional evidence (pass every file as a FULL absolute path under the data directory, never as a bare filename): `{DATA_DIR}/global_news.txt`, `{DATA_DIR}/macro_indicators.txt`, `{DATA_DIR}/prediction_markets.txt`, `{DATA_DIR}/fundamentals.txt`, `{DATA_DIR}/balance_sheet.csv`, `{DATA_DIR}/cashflow.csv`, `{DATA_DIR}/income_stmt.csv`, `{DATA_DIR}/options.txt` — Output: `price_action_attribution_analyst.md`. In JSON mode, pass `{DATA_DIR}/price_context.json` instead.

Provide the absolute prompt path, report directory, data directory, output path, instrument context, Phase 1 quality findings, and the list of failed/missing Step 1 roles. The analyst must read all available Step 1 reports, verify only its material claims against raw artifacts, preserve the required `Evidence Handoff`, rank competing hypotheses, and produce conditional outlooks without issuing a rating, target price, position size, or transaction recommendation.

After it returns, verify `price_action_attribution_analyst.md` exists and is non-empty.

## Debate History File Protocol

Multi-round debates use **files as shared memory**. The File I/O protocol is defined in each debate agent's prompt file (`bull_researcher.md`, `bear_researcher.md`, `aggressive_debator.md`, `conservative_debator.md`, `neutral_debator.md`); apply the ownership and return rules in rule 13.

| Debate | File Path |
|--------|-----------|
| Bull vs Bear | `skills/stock-analysis-debate/reposrts/{TICKER}/reports/{DATE}/debate_history.md` |
| Risk Assessment | `skills/stock-analysis-debate/reposrts/{TICKER}/reports/{DATE}/risk_debate_history.md` |

The main session only tells each agent: the file path, its role, the round number, the report directory, and paths to required prior report artifacts.

---

## Phase 3: Bull vs Bear Debate

Run **`debate_rounds`** rounds (default 2). Each round: Bull → Bear, sequential. Sub-agents handle debate history file I/O via the protocol in their prompts.

For each agent, provide: role, round N of total, debate history file path, report directory, `prompts/data_policy.md`, and instrument context. Require the agent to read `price_action_attribution_analyst.md` when available, challenge at least its primary attribution or its main alternative, and verify decisive counterclaims against the relevant Phase 2 reports without bypassing the statuses, allowed uses, or gates carried in their `Evidence Handoff` sections. The attribution report is a hypothesis ranking, not an authority. Identify any analyst role that failed so the agent does not assume that evidence exists.

Debate history file: `skills/stock-analysis-debate/reposrts/{TICKER}/reports/{DATE}/debate_history.md`
Supporting evidence: read only the relevant Phase 2 reports and debate history from the report directory

## Phase 4: Research Manager

- **Prompt**: `skills/stock-analysis-debate/prompts/research_manager.md`
- **Context in prompt**: Full absolute paths to `debate_history.md`, the report directory, `prompts/data_policy.md`, and `prompts/portfolio_policy.md`; plus the resolved `portfolio_mode`, applicable user-supplied portfolio fields, and instrument context. The agent must read both policies before `debate_history.md` and `price_action_attribution_analyst.md`, adjudicate the debate's challenges to the primary attribution/priced-in assessment, then read only the additional Phase 2 reports needed to judge specific claims. Identify any missing analyst role.
- **Task**: Judge the debate. Make definitive Buy/Sell/Hold decision. Produce investment plan with rationale + strategic actions.
- **Output**: `skills/stock-analysis-debate/reposrts/{TICKER}/reports/{DATE}/research_plan.md`

## Phase 5: Trader

- **Prompt**: `skills/stock-analysis-debate/prompts/trader.md`
- **Context in prompt**: Full absolute paths to `research_plan.md`, the report directory, `prompts/data_policy.md`, and `prompts/portfolio_policy.md`; plus the resolved `portfolio_mode` and applicable user-supplied portfolio fields. The agent must apply both policies and the gate outcomes carried by Phase 2 reports before reading `research_plan.md`, then read only the individual reports needed to produce and verify the trade plan. Include instrument context.
- **Output**: `skills/stock-analysis-debate/reposrts/{TICKER}/reports/{DATE}/trader_plan.md`, ending with `FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL**`.

---

## Phase 6: Risk Assessment Debate

Run **`risk_discuss_rounds`** rounds (default 2). Each round: Aggressive → Conservative → Neutral, sequential. Sub-agents handle risk debate history file I/O via the protocol in their prompts.

For each agent, provide: role, round N of total, risk debate history file path, trader plan file path, report directory, `prompts/data_policy.md`, `prompts/portfolio_policy.md`, resolved `portfolio_mode`, applicable user-supplied portfolio fields, and instrument context. The agent applies both policies and the gate outcomes carried by Phase 2 reports, then reads `trader_plan.md` plus only the reports needed for its risk argument. Identify any analyst role that failed.

Each risk debator appends its full assessment to the risk debate history file and follows the return contract in its prompt and rule 13. The main session reads `risk_debate_history.md` only during Phase 7 synthesis.

Risk debate history file: `skills/stock-analysis-debate/reposrts/{TICKER}/reports/{DATE}/risk_debate_history.md`
Trader plan: `skills/stock-analysis-debate/reposrts/{TICKER}/reports/{DATE}/trader_plan.md`
Supporting evidence: read only `trader_plan.md`, relevant Phase 2 reports, and prior risk-debate entries from the report directory

## Phase 7: Portfolio Manager — Final Decision + Report File (main session)

Numeric validation completed deterministically in Phase 1 and its allowed results and restrictions were transferred through Phase 2 reports; do not launch an LLM verifier.

---

### Step 1: Gather

Apply the report artifact handoff protocol:

- Read `portfolio_manager.md` for the required output structure.
- Read `prompts/portfolio_policy.md`.
- Read `debate_history.md` when adjudicating Bull/Bear arguments and `risk_debate_history.md` when deriving the final position plan.
- Read `research_plan.md` and `trader_plan.md` when writing the Investment Plan and Trading Proposal report summaries.
- Read `price_action_attribution_analyst.md` when explaining the recent move, adjudicating priced-in claims, or deriving continuation/reversal conditions.
- Read only the `*_analyst.md` files needed to support or challenge claims used in the final decision.
- Read `prompts/data_policy.md`.
- Do not create any intermediate combined or summary file while gathering evidence.

### Step 2: Phase 2 Report Gate (MANDATORY — do NOT skip)

1. Read the relevant Phase 2 analyst reports; do not launch an agent.
2. Confirm every numeric claim planned for the final report satisfies the `Evidence Handoff` requirements in rule 9.
3. Obey every gate outcome and blocking reason propagated through Phase 2 reports. If a gate is false or its outcome is absent, remove the exact valuation, target price, strong rating, or segment-growth claim and replace it with N/A or Not Rated. Buy/Sell are strong ratings: even when a Phase 2 report carries `allow_strong_rating: true`, use them only after verifying every carried Phase 7 evidence requirement; otherwise cap the rating at Overweight/Underweight/Hold.
4. For a target price, use only a Phase 2 report's authorized forecast period and valuation method, show all handed-off inputs in one currency, and include the arithmetic chain and multiple-sensitivity table inside `Investment Thesis`. The `Price Target` field contains only the final authorized value or `Not Rated`. Apply `portfolio_policy.md` separately.

### Step 3: Synthesize

Produce the Portfolio Manager's final decision in the main session. The Final Decision is the single most important deliverable — use the compact field-based format illustrated by the reference final-trade-decision report, but keep it a **fully-argued conclusion**, not an unsupported summary. Every claim must be anchored to specific evidence: numeric values, evidence IDs (e.g., [N005]), analyst verdicts, or debate-file passages.

Before synthesizing, apply the report gate from Step 2.

The Final Decision MUST contain exactly these fields, in this order, using the field labels verbatim:

1. **Rating** — one of Buy / Overweight / Hold / Underweight / Sell, followed by a one-line verdict and the key reason for choosing this rating over its nearest alternatives.
2. **Executive Summary** — one coherent paragraph: the business case with figures, the best-supported recent price attribution and confidence, entry strategy, portfolio applicability/position-sizing status, key risk levels including thesis-level invalidation, any computable tactical reference band, and the time horizon.
3. **Investment Thesis** — the fully argued body of the decision. Consolidate the decision logic against the other ratings, 3-6 evidence-anchored arguments with rebuttals, Bull/Bear adjudication and uncontested facts, base/optimistic/pessimistic scenarios, authorized target-price derivation and sensitivity when permitted, risk/verification nodes, portfolio applicability and position plan, and material Not Rated/data caveats. Keep the content readable with short paragraphs or numbered arguments; do not reduce it to a generic one-paragraph thesis.
4. **Price Target** — the final value authorized by the Phase 2 gates and `portfolio_policy.md`, or `Not Rated` when any required gate is false, missing, conflicting, or otherwise blocked. Do not invent a numeric target from technical levels or debate estimates.
5. **Time Horizon** — the expected holding/review horizon and the next verification cadence; keep the supporting conditions in `Executive Summary` or `Investment Thesis`.

All five fields must carry the specific numbers and evidence they derive from. Prioritize readability: lead with conclusions, keep paragraphs short, and bold key figures — avoid wall-of-text prose.

### Step 4: Write Report + Output Decision

**Output A — persisted report**: Use the Write tool to create `skills/stock-analysis-debate/reposrts/{TICKER}/reports/{DATE}/analysis_report.md`(Reader-friendly) with ALL sections populated, then verify it exists and is non-empty. The main session writes the report summaries itself (based on Step 1's Gather) — natural-language summaries, one short paragraph or bullet list per section. **Final Decision is FIRST.** Structure (fixed):

```
# Stock Analysis Report: {TICKER} ({DATE})

**Report Date**: {DATE} | **Analysis Mode**: {analysis_mode} | **Analysis Cutoff**: {analysis_timestamp} | **Market Data As Of**: {data_as_of_date}

## Final Decision
**Rating**: {Buy / Overweight / Hold / Underweight / Sell}

**Executive Summary**: {one coherent paragraph}

**Investment Thesis**: {fully argued evidence-backed conclusion, including the required decision logic, scenarios, risks, portfolio applicability, and material caveats}

**Price Target**: {authorized target price or Not Rated}

**Time Horizon**: {expected horizon and review cadence}

## 1. Analyst Research
{key evidence used from the individual analyst reports — include only reports relevant to the final decision, }

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

**Output B — user-visible text**: Only after Output A is verified, return a concise summary of the rating, price target, and key rationale.

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
| `analysts` | all applicable Step 1 roles; attribution always runs | Base roles resolved by rules 5-7; Price Action Attribution remains mandatory after Step 1 |
| `date` | today | Actual local execution date in YYYY-MM-DD; also the data/report directory date |
| `analysis_mode` | `current_research` | `current_research` or explicit `historical_replay` |
| `as_of_date` | current execution date | Required historical cutoff for `historical_replay`; interpreted as end of day in the instrument market timezone |
| `portfolio_mode` | `research_only` | `research_only`, explicit `model_portfolio`, or `portfolio_context_complete`; incomplete required fields always downgrade to `research_only` |

## Reference Material

- `reference/options-volume-open-interest-and-sentiment.en.md` — Read on demand when interpreting options volume, open interest, volume/OI activity flags, directional-flow requirements, or approximate IV skew. It summarizes the relevant OIC, OCC, and Cboe source material and defines the Skill's allowed/prohibited claims.

## Common Mistakes

- **Modifying prompts**: Prompt files contain the exact prompts. Do NOT paraphrase or improve them. Pass verbatim.
- **Defaulting to Hold**: If both sides have valid points, pick the stronger argument. Hold only for genuinely neutral situations.
- **Anemic Final Decision**: Use the five required fields in Phase 7 Step 3, but do not omit the evidence-backed decision logic, scenarios, risks, portfolio applicability, or material caveats from `Investment Thesis`.
