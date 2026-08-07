---
name: stock-analysis-debate
description: Use when the user wants to analyze a stock (US/CN/HK markets), explain recent price behavior, or get a Buy/Hold/Sell recommendation backed by deterministic tool-layer data validation, currency-normalized valuation, official-disclosure fallbacks, evidence-graded attribution, and multi-agent debate.
---

# Stock Analysis with Multi-Agent Debate

## Overview

Conduct a professional stock analysis by orchestrating multiple AI agents in a structured debate. Agents play specialized roles — Market Analyst, News Analyst, Social Media Analyst, Fundamentals Analyst, Options Flow Analyst (US current research only), Price Action Attribution Analyst, Bull/Bear Researchers, Trader, Aggressive/Conservative/Neutral Risk Analysts, and Portfolio Manager — to explain recent price behavior and produce a data-backed investment recommendation (Buy/Overweight/Hold/Underweight/Sell).

Data is fetched primarily from **yfinance** (OHLCV, benchmark/sector comparators, dedicated analyst-estimate tables, news, fundamentals, financial statements), with **Longbridge daily K-lines** filling missing latest OHLCV dates for US/HK/SH/SZ stocks using market-aware, fail-closed volume normalization, and **stockstats** computing technical indicators. Provider calls use classified exponential retries. Official disclosures are discovered through HKEXnews, SEC EDGAR/XBRL, or CNINFO as market-appropriate fallbacks; `official_financials.toon` normalizes supported official facts without allowing commercial or document-only data to overwrite them. Unstructured filing PDFs remain evidence-only and are never numerically extracted by an LLM.

Use `current_research` by default. Use `historical_replay` only with an explicit historical cutoff; the tool then excludes every retrieval-time source that lacks verified point-in-time availability instead of backfilling it with today's snapshot.

## Critical Execution Rules

**These rules override all other instructions during analysis execution:**

1. **NEVER ask the user for permission to proceed between phases.** After each phase completes, immediately continue to the next phase. The user asked for a complete analysis — deliver it in one continuous run.
2. **Phase 2 has TWO steps. Start every applicable base analyst concurrently, wait for all scheduled roles, and verify their files. Then start exactly one Price Action Attribution Analyst, which reads the base reports and attribution data and writes `price_action_attribution_analyst.md`. Only after both steps are verified may Phase 3 start. Every analyst writes directly to its own file and returns only a short write confirmation; the main session never aggregates analyst responses.**
3. **Phases 3-6 run role tasks sequentially because each depends on the previous task's persisted artifact. After each artifact is verified, immediately start the next task. Do NOT pause for user confirmation.**
4. **Phase 7 is the final phase and runs in the main session. In the same assistant turn, persist and verify `analysis_report.md` first, then return the user-visible decision summary. If the report is not verified, do not return a success summary.**
5. **The workflow is complete ONLY when the report file has been written to `skills/stock-analysis-debate/reposrts/{TICKER}/reports/{DATE}/analysis_report.md` AND confirmed to the user.**

6. **CN market skips Phase 1 Step 3 (Segment Setup) and Segment Analyst entirely.** No `segments.yaml`, no segment data. Run 4 Step 1 analysts (options flow is US-only), then the mandatory Price Action Attribution Analyst in Step 2.
7. **If `segments_fetch_failed.flag` exists**, skip Segment Analyst, run every other applicable Step 1 analyst (including Options Flow for US current research), then the mandatory Price Action Attribution Analyst in Step 2. Note the missing segment view in the final report.
8. **Options Flow Analyst runs ONLY for US-listed equities in `current_research`.** For HK/CN markets and every `historical_replay`, `options.txt` contains a Not Rated placeholder and the analyst must not run. For eligible US current research, the yfinance aggregate snapshot authorizes only activity concentration and approximate implied-pricing observations: volume/OI cannot establish opening/closing status, buyer/seller direction, strategy, or participant identity. Options evidence must not directly determine the rating, target price, position sizing, or risk limits. Read `reference/options-volume-open-interest-and-sentiment.en.md` only when interpreting or changing these boundaries.

9. **REPORT DATE AND TIME MODE:** `{DATE}` is always the actual local execution date and is the ONLY date allowed in the report title and output directory. `current_research` requires `{DATE}` to be today. `historical_replay` additionally requires `--as-of-date`; disclose its market-timezone `analysis_timestamp` and label the report as a replay, never as if it was authored then. Treat `data_as_of_date` only as the latest market observation. Even when `data_fresh: false`, write exactly one report to `reposrts/{TICKER}/reports/{DATE}/analysis_report.md`. If `warning_no_200_sma: true`, 200 SMA must be N/A.
10. **DATA DIRECTORY EVIDENCE CONTRACT AND TEMPORAL GUARDRAIL:** The current run's non-empty artifacts listed in Phase 1 under `skills/stock-analysis-debate/reposrts/{TICKER}/data/{DATE}/` are candidate evidence. First apply `temporal_context.source_statuses` from `data_quality` and `validated_metrics`; a source not marked `allowed` is Not Rated even if a value is present. Then cite the source file, field/row or indicator, and period/as-of date for every material number. `validated_metrics.toon` (or `.json` in JSON mode) is authoritative only for the metrics it contains and for all `gates`: its unavailable, stale, conflicting, translated-only, temporally blocked, or otherwise blocked status cannot be bypassed. Prefer tool-derived values; do not recompute returns, growth, TTM, margins, valuation multiples, or technical indicators with an LLM. Apart from presentation-only rounding/unit scaling and workflow-required target-price or position formulas with displayed inputs, missing derived values are N/A or Not Rated. Never infer, interpolate, backfill a historical snapshot with later data, treat placeholders/flags as evidence, or extract a number from an unstructured filing with an LLM.
11. **NEWS/SENTIMENT EVIDENCE:** Treat `news.txt` evidence IDs and content levels as hard boundaries. If `Social Data Available: false`, social sentiment is Not Rated and must not affect the rating, target price, position sizing, or risk limits. If `options.txt` marks options flow Not Rated, the same restriction applies to options evidence.

12. **PRICE ATTRIBUTION EVIDENCE:** The Price Action Attribution Analyst ranks competing hypotheses; it does not prove a unique cause or issue a rating, target price, position size, or trade. No pre-event expectation means the surprise/priced-in claim is Not Rated. No comparator means abnormal return is Not Rated. No stock-specific leverage/short/flow evidence means forced liquidation, short squeeze, or investor identity is not established. Oversold/overbought is a state, not a catalyst.

**PORTFOLIO APPLICABILITY:** Resolve `portfolio_mode` before Phase 4 by applying `prompts/portfolio_policy.md`. Default to `research_only`; incomplete context always downgrades to that mode. In `research_only`, keep security-level entry/invalidation conditions but output `Position Size: Not Rated — complete portfolio context was not supplied.` and no allocation percentages, capital, or shares. Agent consensus never substitutes for portfolio context or risk-budget arithmetic.

13. **CONTEXT HYGIENE (main session):** The main session's context is reserved for orchestration, decision synthesis, and deliverables:
    - Every Phase 2 analyst writes its own report file and returns only a short confirmation — never the full report.
    - The Price Action Attribution Analyst is the only Phase 2 role required to read all available Step 1 reports; it reads raw files only to verify material attribution claims.
    - Debate/risk agents write their own files (File I/O protocol) and return only short confirmations/summaries — never their full arguments.
    - Downstream agents read only the reports and raw data needed for their current role. Give them the report/data directory paths and mandatory prior-phase artifacts; never paste file contents into agent prompts.
    - Never Read a file whose content is already in the main context (own Write output).
    - At Phase 7, read only the unseen reports and current-run data artifacts required for final claims and debate adjudication. Read the configured `validated_metrics` artifact and `validation_report.md` for their covered metrics and gates; other listed data artifacts remain valid domain evidence but cannot bypass a blocked covered metric. Files already in the main context are not re-read.

14. **ONE-RETRY POLICY — SINGLE FAILURE SOURCE OF TRUTH:** Resolve role applicability before scheduling work. An unavailable optional source degrades to Not Rated and may make its conditional role inapplicable; this is not a scheduled-role failure. Every scheduled unit has at most two total attempts: the initial attempt plus exactly one retry of that unit. A successful return is insufficient without its required non-empty artifact. After a second failure, enter terminal `FAILED`, report the failed unit, and do not execute any later state. Never re-run a completed unit. This policy also covers final report persistence.

## Output Directory Contract

Keep fetched data and generated reports in separate directory trees for every analysis:

Structured artifacts use `tools/structured_io.py::STRUCTURED_OUTPUT_FORMAT`. The default is `toon`, so the paths below use `.toon`; if the variable is changed to `json`, use the same basenames with `.json`. Never mix extensions within one run.

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
| `REPORT_WRITTEN` | `RISK_READY` | Apply the deterministic gates and persist the final report | `analysis_report.md` exists, is non-empty, and contains the required final-decision sections |
| `COMPLETE` | `REPORT_WRITTEN` | Return the concise user-visible decision summary in the same assistant turn | Report path and decision summary are both delivered |

Apply rule 14 to the current unit whenever its completion evidence is absent. `FAILED` is terminal and has no outgoing transition.

## Workflow

1. **Phase 1: Data Collection & Validation** — Run `fetch_data.py` synchronously, inspect the configured `data_quality` artifact (`.toon` by default), then perform segment setup when applicable. Wait for each required artifact before proceeding. Details are in the Phase 1 section below.

2. **Phase 2: Analyst Reports** — two steps
   - Step 1: start 4 to 6 applicable base roles concurrently, then wait for every scheduled role.
   - Options Flow Analyst runs ONLY for US-listed equities in `current_research`.
   - Segment Analyst runs ONLY in `current_research` for HK/US with `multi_segment: true` in `segments.yaml`.
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
   - Do not delegate the final synthesis to another role.
   - Persist and verify `analysis_report.md`, then return the decision summary in the same assistant turn.
   - Workflow is complete only when both deliverables succeed.

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

On missing completion evidence, apply rule 14 to this data-fetch unit.

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
| `news.txt` | Company-specific news with evidence IDs, content levels, available summaries, processing audit, and explicit social-data availability (30 days) | yfinance + fetch_data.py |
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
| `official_financials.toon` | Unified official filing/fact contract with source, period, unit, currency, raw tag, source URL and fail-closed numeric status | SEC EDGAR XBRL / HKEXnews / CNINFO (SSE/SZSE) |
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
- Keep the requested execution `date` as the report date and output-directory date. Use `data_as_of_date` only for statements about how current the market data is. If the dates differ, disclose both explicitly and do not generate a second report.
- Read `temporal_context`: record `analysis_mode`, `execution_date`, `analysis_timestamp`, and every `source_statuses` entry. Do not dispatch an analyst with a blocked source as usable evidence.
- Check `trading_days`: note how many trading days are available for indicators.
- Check `warning_no_200_sma`: if true, 200 SMA is NOT computable.
- Check `indicator_sufficiency`: each indicator has a `sufficient` boolean and `min_days` threshold.
- Record any `notes` warnings for inclusion in the final report.
- Read the configured `validated_metrics` artifact (`validated_metrics.toon` by default) and `validation_report.md`. Stop before Phase 2 if either is missing, invalid structured data, or empty.
- Treat `validation_gates` as hard controls and read the matching `gate_details`. A false `allow_exact_valuation`, `allow_target_price`, `allow_strong_rating`, or `allow_segment_growth` gate prohibits that output; it is not an invitation for an agent to reconstruct the missing data. A true `allow_strong_rating` confirms numeric prerequisites only: Buy/Sell additionally requires Phase 7 to verify valid relative-return evidence, a traceable catalyst, and a traceable thesis-invalidation condition. Otherwise cap the final rating at Overweight/Underweight/Hold.
- Inspect `provider_retry_events` for exhausted or non-retryable provider failures and disclose the affected domain as degraded.

**Step 3: Segment Setup (HK/US only)**

**Skip conditions**: CN market, `historical_replay`, OR `segments_fetch_failed.flag` exists in the date dir.

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
3. On missing completion evidence, apply rule 14 to this segment-preparation unit.
4. Proceed immediately to Phase 2.

See `prompts/segment_analyst.md` for data interpretation rules and `prepare_segments.py` plus `longbridge_fetcher.py` for tool-level processing logic.
- `reconciliation_status=mismatch` → the tool raises an exception, Phase 1 Step 3 fails, and no CSV is generated.
- A non-empty `segment_completeness_status` → the analyst must disclose the incomplete data in the report.

## Phase 2: Analyst Reports (Two Steps, Direct File Output)

**CRITICAL**: Start the applicable base analysts concurrently (4 base analysts, plus the conditional Options Flow Analyst [US current research only] and Segment Analyst [HK/US current research + multi_segment only]). Wait for all scheduled roles and verify their artifacts before starting Step 2. Step 2 is one sequential Price Action Attribution Analyst task and must never overlap Step 1.

**IMPORTANT — Main session must NOT preload prompt or data-file contents before dispatching analysts.** Each delegated role reads its own assigned files using the Read tool. The main session provides only:
- Full absolute file paths to: its prompt file + all required data files
- One unique absolute output path under `reposrts/{TICKER}/reports/{DATE}/`
- Instrument context: ticker, market, analysis mode, execution date, analysis timestamp, quote currency, financial currency, verified FX status, and as-of price
- Phase 1 quality-check findings: data_as_of_date, trading_days, warning_no_200_sma flag, indicator_sufficiency summary
- For Segment Analyst: also mention the segment list from `segments.yaml`

Every analyst task must end with this file protocol:

Before the role-specific prompt, every analyst must read `prompts/data_policy.md`, the configured `{DATA_DIR}/validated_metrics` artifact (`.toon` by default), and `{DATA_DIR}/validation_report.md`. These three paths are mandatory in every analyst task. The role-specific current-run data artifacts listed below are authorized domain evidence; they cannot bypass a status, allowed use, or gate for a metric covered by `validated_metrics`.

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

**Fundamentals Analyst** — Prompt: `skills/stock-analysis-debate/prompts/fundamentals_analyst.md` — Data: configured `validated_metrics` artifact (`.toon` by default), `validation_report.md`, `fundamentals.txt`, `balance_sheet.csv`, `cashflow.csv`, `income_stmt.csv` — Output: `fundamentals_analyst.md`

**Options Flow Analyst** (Conditional 5th Analyst: US `current_research` only) — Prompt: `skills/stock-analysis-debate/prompts/options_flow_analyst.md` — Data: `options.txt` — Output: `options_flow_analyst.md`

Launch Options Flow Analyst IN PARALLEL with the other 4 only when the market is **US** and `analysis_mode=current_research`. For HK/CN markets and historical replay, `options.txt` contains a Not Rated placeholder — do NOT launch the Options Flow Analyst.

**Segment Analyst** (Conditional 6th Analyst: HK/US `current_research` + multi_segment only) — Prompt: `skills/stock-analysis-debate/prompts/segment_analyst.md` — Data: `revenue_sankey.csv`, `income_stmt.csv` — Output: `segment_analyst.md`.

Launch Segment Analyst IN PARALLEL with the other analysts only in `current_research` when `segments.yaml` has `multi_segment: true`. Otherwise run the applicable analysts (current US: 5 including Options Flow; current HK: 4; historical replay: 4; CN: 4) as above.

**After all Step 1 roles settle**: Verify that every scheduled output exists and is non-empty. Do not read or combine successful reports in the main session. On missing completion evidence, apply rule 14 to only that role; never create a synthetic analyst report.

### Step 2 — Price Action Attribution Analyst (mandatory, sequential)

Run only after every Step 1 output has been verified.

**Price Action Attribution Analyst** — Prompt: `skills/stock-analysis-debate/prompts/price_action_attribution_analyst.md` — Reports: every available Step 1 `*_analyst.md` in the report directory — Required data (pass as full absolute paths in the data directory): `{DATA_DIR}/price_context.toon`, `{DATA_DIR}/expectations.txt`, `{DATA_DIR}/ohlcv.csv`, `{DATA_DIR}/indicators.txt`, `{DATA_DIR}/news.txt` — Conditional evidence (pass every file as a FULL absolute path under the data directory, never as a bare filename): `{DATA_DIR}/global_news.txt`, `{DATA_DIR}/macro_indicators.txt`, `{DATA_DIR}/prediction_markets.txt`, `{DATA_DIR}/fundamentals.txt`, `{DATA_DIR}/balance_sheet.csv`, `{DATA_DIR}/cashflow.csv`, `{DATA_DIR}/income_stmt.csv`, `{DATA_DIR}/options.txt` — Output: `price_action_attribution_analyst.md`. In JSON mode, pass `{DATA_DIR}/price_context.json` instead.

Provide the absolute prompt path, report directory, data directory, output path, instrument context, Phase 1 quality findings, and the list of failed/missing Step 1 roles. The analyst must read all available Step 1 reports, verify only its material claims against raw artifacts, rank competing hypotheses, and produce conditional outlooks without issuing a rating, target price, position size, or transaction recommendation.

After it returns, verify `price_action_attribution_analyst.md` exists and is non-empty. On missing completion evidence, apply rule 14 to the attribution unit.

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

For each agent, provide: role, round N of total, debate history file path, report directory, data directory, `prompts/data_policy.md`, the configured `validated_metrics` artifact, `validation_report.md`, and instrument context. Require the agent to read `price_action_attribution_analyst.md` when available, challenge at least its primary attribution or its main alternative, and verify decisive counterclaims without bypassing the deterministic contract. The attribution report is a hypothesis ranking, not an authority. Identify any analyst role that failed so the agent does not assume that evidence exists.

**Return protocol**: Each debate agent appends its full argument to the debate history file and returns ONLY a one-line status confirmation (role, round, file write succeeded) per the Step 4 protocol in its prompt. The main session must NOT read `debate_history.md` during Phase 3 — it is shared memory between debate agents and read later by the Research Manager (which reads it itself) and at Phase 7 (when the main session reads it to write the report summaries).

Debate history file: `skills/stock-analysis-debate/reposrts/{TICKER}/reports/{DATE}/debate_history.md`
Supporting evidence: read individual reports and raw data from the report/data directories only as needed

On missing completion evidence for a role/round entry, apply rule 14 to only that debate unit.

After Phase 3, proceed immediately to Phase 4.

## Phase 4: Research Manager

- **Before**: Do NOT preload debate, analyst, or data files in the main session — the sub-agent reads what it needs itself (see rule 13).
- **Prompt**: `skills/stock-analysis-debate/prompts/research_manager.md`
- **Context in prompt**: Full absolute paths to `debate_history.md`, the report directory, the data directory, `prompts/data_policy.md`, `prompts/portfolio_policy.md`, the configured `validated_metrics` artifact, and `validation_report.md`; plus the resolved `portfolio_mode` and only the user-supplied portfolio fields needed by the policy. The agent must read both policies before `debate_history.md` and `price_action_attribution_analyst.md`, adjudicate the debate's challenges to the primary attribution/priced-in assessment, then read only the additional reports/data needed to judge specific claims. Identify any missing analyst role. Include instrument context (market type, quote currency, financial currency, ticker, e.g. "601988.SH is a CN stock on Shanghai Stock Exchange, quote/financial currency: CNY, ±10% price limit, T+1 settlement").
- **Task**: Judge the debate. Make definitive Buy/Sell/Hold decision. Produce investment plan with rationale + strategic actions.
- **After it returns**: The agent writes its complete plan directly to `skills/stock-analysis-debate/reposrts/{TICKER}/reports/{DATE}/research_plan.md`, and returns only a short confirmation/summary — never the full plan.
- On missing completion evidence, apply rule 14 to the Research Manager unit.
- Immediately go to Phase 5.

## Phase 5: Trader

- **Before**: Do NOT preload `research_plan.md`, analyst reports, or data files in the main session — the sub-agent reads what it needs itself (see rule 13).
- **Prompt**: `skills/stock-analysis-debate/prompts/trader.md`
- **Context in prompt**: Full absolute paths to `research_plan.md`, the report directory, the data directory, `prompts/data_policy.md`, `prompts/portfolio_policy.md`, the configured `validated_metrics` artifact, and `validation_report.md`; plus the resolved `portfolio_mode` and applicable user-supplied portfolio fields. The agent must apply both policies and the deterministic gates before reading `research_plan.md`, then read only the individual reports/data needed to produce and verify the trade plan. Include instrument context.
- Must end output with: `FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL**`
- In `research_only`, require the exact Position Size: Not Rated statement and prohibit weights, capital, and shares. In an allowed numeric mode, require the Trader to derive every applicable cap from `portfolio_policy.md`, identify the binding minimum, and verify staged incremental/cumulative weights against it.
- **After it returns**: The agent writes its complete proposal directly to `skills/stock-analysis-debate/reposrts/{TICKER}/reports/{DATE}/trader_plan.md`, and returns only a short confirmation/summary — never the full proposal. The proposal must still end with `FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL**`.
- On missing completion evidence, apply rule 14 to the Trader unit.
- Immediately go to Phase 6.

---

## Phase 6: Risk Assessment Debate

Run **`risk_discuss_rounds`** rounds (default 2). Each round: Aggressive → Conservative → Neutral, sequential. Sub-agents handle risk debate history file I/O via the protocol in their prompts.

For each agent, provide: role, round N of total, risk debate history file path, trader plan file path, report directory, data directory, `prompts/data_policy.md`, `prompts/portfolio_policy.md`, the configured `validated_metrics` artifact, `validation_report.md`, resolved `portfolio_mode`, applicable user-supplied portfolio fields, and instrument context. The agent applies both policies and the deterministic gates, then reads `trader_plan.md` plus only the reports/data needed for its risk argument. Identify any analyst role that failed.

**Return protocol**: Each risk debator appends its full assessment to the risk debate history file and returns ONLY a short summary (final stance, portfolio result permitted by the resolved mode, 3-5 core argument bullets) per the Step 4 protocol in its prompt. In `research_only`, that result contains no allocation number. The main session uses these returns during Phase 3-6 and at Phase 7 Reads `risk_debate_history.md` itself to write the report summaries.

Risk debate history file: `skills/stock-analysis-debate/reposrts/{TICKER}/reports/{DATE}/risk_debate_history.md`
Trader plan: `skills/stock-analysis-debate/reposrts/{TICKER}/reports/{DATE}/trader_plan.md`
Supporting evidence: read individual reports and raw data from the report/data directories only as needed

On missing completion evidence for a role/round entry, apply rule 14 to only that risk-debate unit.

After Phase 6, proceed immediately to Phase 7.

## Phase 7: Portfolio Manager — Final Decision + Report File (main session)

**This phase runs in the main session, not as a delegated role.** Numeric validation has already completed deterministically in Phase 1; do not launch an LLM verifier.

**This phase produces two deliverables in the same assistant turn: first the persisted, verified report; then the user-visible summary.**

---

### Step 1: Gather

Apply the on-demand read protocol from rule 13:

- Read `portfolio_manager.md` for the required output structure.
- Read `prompts/portfolio_policy.md`, resolve `portfolio_mode` independently, and downgrade incomplete context to `research_only` even if an upstream report contains percentages.
- Read `debate_history.md` when adjudicating Bull/Bear arguments and `risk_debate_history.md` when deriving the final position plan.
- Read `research_plan.md` and `trader_plan.md` when writing the Investment Plan and Trading Proposal report summaries.
- Read `price_action_attribution_analyst.md` when explaining the recent move, adjudicating priced-in claims, or deriving continuation/reversal conditions.
- Read only the `*_analyst.md` files needed to support or challenge claims used in the final decision.
- Read `prompts/data_policy.md`, the configured `validated_metrics` artifact, and `validation_report.md` before selecting numeric evidence. Use the relevant listed current-run data artifacts for domain numbers, while treating the validated contract as authoritative for metrics it covers and for all gates.
- Do not re-read the configured `data_quality` artifact when its content is already present in the main context.
- Do not create any intermediate combined or summary file while gathering evidence.

### Step 2: Deterministic Data Gate (MANDATORY — do NOT skip)

1. Read `validation_report.md` and the configured `validated_metrics` artifact; do not launch an agent.
2. Confirm every numeric claim planned for the final report is traceable either to an allowed `metric_id` or to a listed current-run data artifact with its field/row or indicator and period/as-of date. When `validated_metrics` covers the claim, its status and `allowed_uses` are mandatory.
3. Obey all `gates` and disclose relevant `gate_details.blocking_reasons`. If a gate is false, remove the exact valuation, target price, strong rating, or segment-growth claim and replace it with N/A or Not Rated. Buy/Sell are strong ratings: even when `allow_strong_rating` is true, use them only after verifying every `phase_7_requirements` item; otherwise cap the rating at Overweight/Underweight/Hold.
4. Do not recalculate tool-derived returns, growth, TTM, margins, valuation multiples, or indicators. For a target price, use the `gate_details.allow_target_price.forecast_period`, state the `valuation_method`, show all traceable current-run inputs in one currency, and include a multiple-sensitivity table. Apply `portfolio_policy.md` separately: `research_only` prohibits all allocation numbers; an allowed numeric mode requires every risk-budget cap, source, formula, and binding minimum. Missing required portfolio context produces Position Size: Not Rated rather than an assumed value.

### Step 3: Synthesize

Produce the Portfolio Manager's final decision in the main session. The Final Decision is the single most important deliverable — it must be a **fully-argued conclusion**, not a summary. A Final Decision that merely restates the rating, entry points, and a one-paragraph thesis is INCOMPLETE and must be expanded. Every claim must be anchored to specific evidence: numeric values, evidence IDs (e.g., [N005]), analyst verdicts, or debate-file passages.

Before synthesizing, apply the deterministic contract and gates from Step 2. Never use an analyst report as the sole numeric source: trace the number back to its current-run data artifact. A number unavailable or disallowed in `validated_metrics` cannot be restored from another artifact or report when the contract covers that metric.

The Final Decision MUST contain, in order:

1. **Rating** — one of Buy / Overweight / Hold / Underweight / Sell, a one-line verdict, AND one line on the key reason for choosing this rating over its nearest alternatives (e.g., why Overweight rather than Buy, or why Buy rather than Hold).
2. **Executive Summary** — one coherent paragraph (not bullets-only): the business case in one or two sentences with figures, the best-supported recent price attribution and its confidence, entry strategy, portfolio applicability/position-sizing status, key risk levels including the thesis-level invalidation condition, a tactical reference band if computable (e.g., Bollinger/structure levels), and the time horizon.
3. **Decision Logic Chain** — explicit reasoning for the rating vs EVERY other plausible choice: why not Sell/Underweight (hard-bottom evidence with figures), why not Hold (asymmetric payoff already priced), why not a one-shot full position (evidence-grade discount). Each justification cites data.
4. **Core Thesis with Evidence Anchors** — 3-6 numbered arguments; each = claim + concrete evidence (figure, [Nxxx] ID, analyst report, or debate passage) + explicit rebuttal of the opposing view on that point. May be organized as grouped anchors (e.g., "facts anchoring the bullish direction" vs "facts anchoring the caution") when the debate's residual disagreement splits that way.
5. **Debate Adjudication** — what the bull side won on (with evidence), what the bear side won on (with evidence), which arguments were dismissed and why, AND the facts neither side disputed (uncontested consensus — often the strongest basis for the rating direction), and the net ruling that leads to this rating.
6. **Scenarios & Target Price Derivation** — base/optimistic/pessimistic scenarios with their conditions; reconcile them with the attribution report's continuation/reversal conditions. When `allow_target_price` is true, use its gate-detail forecast period and valuation method, show every input and the arithmetic chain, and include a multiple-sensitivity table. When false, set the numeric target to Not Rated and disclose the blocking reasons. Technical measured moves and debate targets are cross-checks, never substitutes for a blocked valuation gate.
7. **Risk Levels & Verification Nodes** — two layers: (a) thesis-level invalidation (the sustained condition that would overturn the entire thesis, with its evidence threshold); (b) tactical stop/reference levels with structural derivation (ATR-calibrated, structure-based). Plus the upcoming verification event (e.g., earnings) that would confirm or invalidate the thesis.
8. **Portfolio Applicability & Final Position Plan** — state the resolved mode. In `research_only`, use the exact Position Size: Not Rated statement and no allocation numbers. In an allowed numeric mode, show every applicable risk-budget cap, the binding minimum constraint, the complete staged schedule, arithmetic verification, and any initial → final change driven by a constraint rather than agent voting.
9. **Data Caveats** — Not Rated items (social, options, macro, expectation baseline, comparators, leverage/short/flow evidence), TTM/forward valuation conflicts and which anchor was used, missing statements.

Sections 2-8 must carry the specific numbers and evidence they derive from — summary prose without data is not acceptable. Prioritize readability: lead with conclusions, use tables for comparisons and evidence, keep paragraphs short (one point each), and bold key figures — avoid wall-of-text prose.

### Step 4: Write Report + Output Decision

**This is the mandatory deliverable. The analysis is incomplete until the file is on disk.**

In one assistant turn, perform this ordered sequence:

**Output A — persisted report**: Use the Write tool to create `skills/stock-analysis-debate/reposrts/{TICKER}/reports/{DATE}/analysis_report.md` with ALL sections populated, then verify it exists and is non-empty. The main session writes the report summaries itself (based on Step 1's Gather) — natural-language summaries, one short paragraph or bullet list per section. **Final Decision is FIRST.** Structure (fixed):

```
# Stock Analysis Report: {TICKER} ({DATE})

**Report Date**: {DATE} | **Analysis Mode**: {analysis_mode} | **Analysis Cutoff**: {analysis_timestamp} | **Market Data As Of**: {data_as_of_date}

## Final Decision
{portfolio manager's full decision — first, structured per Step 3's 9 mandatory sections: Rating (+ key reason) / Executive Summary / Decision Logic Chain / Core Thesis with Evidence Anchors / Debate Adjudication (incl. uncontested consensus) / Scenarios & Target Price Derivation / Risk Levels & Verification Nodes (thesis-level invalidation + tactical stops) / Portfolio Applicability & Final Position Plan / Data Caveats. In research_only, the position section is Not Rated with no allocation numbers; in an allowed numeric mode it includes binding-constraint derivation and any initial → final schedule evolution. A 1-2 paragraph verdict is NOT a complete Final Decision.}

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

**Output B — user-visible text**: Only after Output A is verified, return a concise summary of the rating, price target, and key rationale.

After both outputs complete, confirm: "The analysis report has been saved to skills/stock-analysis-debate/reposrts/{TICKER}/reports/{DATE}/analysis_report.md"

**Date guardrail**: `{DATE}` above is always the actual execution date. Do not replace it with `analysis_as_of_date` or `data_as_of_date`, and do not write or copy `analysis_report.md` to any second date directory. In `historical_replay`, keep the historical cutoff in the metadata line and label conclusions as replay results.

---

**Guardrail**: If `analysis_report.md` has not been persisted and verified, do not send the success summary. Apply rule 14 to the report-persistence unit; a second failure enters terminal `FAILED`.

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
| `date` | today | Actual local execution date in YYYY-MM-DD; also the data/report directory date |
| `analysis_mode` | `current_research` | `current_research` or explicit `historical_replay` |
| `as_of_date` | current execution date | Required historical cutoff for `historical_replay`; interpreted as end of day in the instrument market timezone |
| `portfolio_mode` | `research_only` | `research_only`, explicit `model_portfolio`, or `portfolio_context_complete`; incomplete required fields always downgrade to `research_only` |

## Reference Material

- `reference/options-volume-open-interest-and-sentiment.en.md` — Read on demand when interpreting options volume, open interest, volume/OI activity flags, directional-flow requirements, or approximate IV skew. It summarizes the relevant OIC, OCC, and Cboe source material and defines the Skill's allowed/prohibited claims.

## Common Mistakes

- **Modifying prompts**: Prompt files contain the exact prompts. Do NOT paraphrase or improve them. Pass verbatim.
- **Defaulting to Hold**: If both sides have valid points, pick the stronger argument. Hold only for genuinely neutral situations.
- **Forgetting instrument context**: Every debate/judgment agent needs market (US/CN/HK), quote currency, financial currency, FX status, ticker format, and trading rules.
- **Context bloat**: Do NOT paste file contents into agent prompts or require each phase to read every report/data file. The Price Action Attribution Analyst reads all Step 1 reports by design; every other downstream role reads only the evidence needed for its claims. Do not re-read content already in the main context. See rule 13 and the On-Demand Read Protocol.
- **Post-hoc attribution**: Do not convert a nearby headline, an oversold reading, or a large rebound into a proven cause. Require expectation, timing, abnormal-return, and mechanism evidence; preserve competing hypotheses and Not Rated gaps.
- **Historical look-ahead**: Do not pass a past date as the execution date or reuse retrieval-time fundamentals, statements, estimates, ratings, options, macro snapshots, or segment data in a replay. Use the explicit historical mode and obey `temporal_context.source_statuses`.
- **Anemic Final Decision**: A Final Decision that only restates the rating, entry points, and a one-paragraph thesis is incomplete (see Phase 7 Step 3). It must contain all 9 sections — Rating with key reason, Executive Summary, Decision Logic Chain (why not the other ratings), evidence-anchored thesis, Debate Adjudication (including uncontested consensus), scenario/target-price derivation, layered risk levels (thesis-level invalidation + tactical stops), portfolio applicability/position result permitted by `portfolio_policy.md`, and Data Caveats — each carrying the specific evidence it derives from.
