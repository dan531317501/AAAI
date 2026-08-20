# Deterministic Data Policy

This policy binds every analyst, debater, manager, trader, and final report writer. Apply the Phase 2 raw-data rules only in Phase 2 and the report-handoff rules in Phases 3-7.

## Phase 2 raw-data rules

1. Only Phase 2 roles may use numeric evidence from the current run's non-empty artifacts listed in `SKILL.md` under `{DATA_DIR}`. Do not use another date directory, a `.flag`, or a Not Rated/placeholder value as numeric evidence.
2. Read `temporal_context` in both `data_quality` and `validated_metrics` before using any artifact. A source whose `source_statuses.<source>.status` is not `allowed` is `Not Rated` even if its file contains a value.
3. In `historical_replay`, use only observations dated on/before `analysis_timestamp`, news with a parseable `published_at` on/before it, and official facts with `filed_at` on/before it. Retrieval-time fundamentals/statements, estimates/revisions/ratings/targets, insider, options, macro without vintage data, prediction markets, global-news search results, FX based on current metadata, and segment snapshots cannot support any claim.
4. Cite the source artifact, field/row or indicator, and period/as-of date for every material number. While preparing a Phase 2 report, do not use another analyst report as a substitute for checking the assigned underlying data artifact.
5. Read the configured `validated_metrics` artifact (`validated_metrics.toon` by default; `.json` in JSON mode) and `validation_report.md` before selecting numeric evidence. For every metric they cover, use it only when its `status`, `allowed_uses`, currency, period, temporal status, and relevant gate permit the claim; another artifact cannot restore a blocked covered metric.
6. Prefer values already fetched or derived by tools. Do not use an LLM to recompute returns, growth, TTM, margins, valuation multiples, or technical indicators. Presentation-only rounding/unit scaling is allowed. Workflow-required target-price or position formulas must show every input, source, currency, and result; an unavailable input makes the result unavailable.
7. Never invent, interpolate, silently convert, or backfill a historical snapshot with a value retrieved later. Missing or disallowed data is `N/A` or `Not Rated`.
8. Treat `info.revenueGrowth` and `info.earningsGrowth` as latest-quarter historical actual YoY, not analyst consensus.
9. Use dedicated analyst-estimate records for consensus claims and preserve their per-row currency and period; these records are unavailable in `historical_replay` unless a future provider supplies a verified publication timestamp and archival snapshot.
10. Keep quote currency and financial currency separate. Cross-currency arithmetic requires the contract's dated FX rate.
10.1. The authorized target-price method is next-fiscal-year Forward EPS multiplied by comparable-company Forward P/E P25/P50/P75. Read `forward_pe_valuation.toon` and `valuation_consensus.toon` before citing it. Require `allow_target_price: true`, `forecast_period: next_fiscal_year`, positive EPS, at least three valid peers, source URL/name, source date, source basis, and confirmed target share basis. The tool's Bear/Base/Bull outputs are authoritative; do not recompute a missing scenario or derive P/E from an article target price.
10.2. A target EPS shown as `USD/ADR`, `HKD/common_share`, or another share basis must retain that exact unit in the report. Do not infer an ADR/ADS ratio from ordinary-share and diluted-average-share counts. If the provider's EPS basis or the instrument source is unclear, mark the full target price `Not Rated`.
10.3. Web consensus P/E evidence must state whether it is a stock or industry view, its `next_fiscal_year` period, direct URL, publication/update/as-of date, and the basis for the numeric P/E. Evidence older than 60 calendar days or without a verifiable date is not current consensus.
10.3.1. The `analyst_consensus` block in `valuation_consensus.toon` (price target, rating distribution, consensus EPS/revenue) is expectation-analysis context only: cite it for sentiment and expectation claims, but never as a target-price input or to override the deterministic Forward P/E scenarios. It is collected only when `consensus_expectations` is enabled (disabled by default); treat a missing block as `Not Rated`, not as zero.
10.4. News evidence is limited to the inclusive 60-calendar-day window in `news.txt`. A missing or unparseable publication date cannot support a current catalyst; do not use older news to fill the gap.
11. Use Longbridge Sankey values only within their `translated_only` allowed uses. Do not call them official operating growth or use them for valuation.
12. Do not extract numeric facts from an unstructured official filing with an LLM. Only tool-normalized structured official facts may authorize a number.
13. A false decision gate is final for that run. Read its `gate_details.blocking_reasons`; narrative confidence cannot override it. A true `allow_strong_rating` establishes numeric eligibility only, and Buy/Sell still requires every listed Phase 7 evidence requirement.
14. Keep `execution_date`, `analysis_as_of_date`, and `retrieved_at` distinct. The report title/output directory use `execution_date`; a historical report must be labeled as a replay as of `analysis_timestamp`, never as if it had been authored then.

## Phase 2 report handoff

15. Add one and only one `Evidence Handoff` section to every Phase 2 report. For each material number or claim, preserve the source artifact and field/row or indicator, period/as-of date, `event_time` and `published_at` when event causality is discussed, covered metric status and allowed uses when applicable, relevant gate outcome and blocking reasons when applicable, independent evidence-cluster identity when repeated reports describe the same event, company-exposure status when applicable, and material Not Rated gaps.
16. Make the report self-contained for downstream decision work. If required provenance or a restriction is unavailable, mark the claim N/A or Not Rated instead of omitting the limitation. When the target gate is allowed, show exactly: `Forward EPS: value unit`, `Target P/E: bear x / base x / bull x`, and `Price Target: bear / base / bull unit`, where `unit` is the artifact's complete currency/share basis such as `USD/ADR` or `KRW/common_share`.

### Phase 2 output idempotency

- A role-specific report path is a single artifact, not an append-only log. An initial attempt or retry must replace the complete file atomically; never append a second report, duplicate a title, or add a second `Evidence Handoff`.
- Before returning success, verify the report has one title, one role boundary, one `Evidence Handoff`, and the exact section structure required by its role prompt. A non-empty file that fails these checks is not a successful artifact.

## Phases 3-7 report-only rules

17. Do not receive, open, search, or cite `{DATA_DIR}` or any file beneath the run's data directory. Use only persisted Phase 2 reports and required report artifacts from preceding phases.
18. Treat Phase 2 `Evidence Handoff` entries as the only evidence bridge from raw data. Preserve their source citations, statuses, allowed uses, gates, and blocking reasons in downstream reasoning.
19. Do not restore a blocked or unavailable claim through another report, debate consensus, or recalculation. If a Phase 2 report omits required provenance, status, allowed-use, or gate details, output N/A or Not Rated; never reopen raw data.
