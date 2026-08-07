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
11. Use Longbridge Sankey values only within their `translated_only` allowed uses. Do not call them official operating growth or use them for valuation.
12. Do not extract numeric facts from an unstructured official filing with an LLM. Only tool-normalized structured official facts may authorize a number.
13. A false decision gate is final for that run. Read its `gate_details.blocking_reasons`; narrative confidence cannot override it. A true `allow_strong_rating` establishes numeric eligibility only, and Buy/Sell still requires every listed Phase 7 evidence requirement.
14. Keep `execution_date`, `analysis_as_of_date`, and `retrieved_at` distinct. The report title/output directory use `execution_date`; a historical report must be labeled as a replay as of `analysis_timestamp`, never as if it had been authored then.

## Phase 2 report handoff

15. Add an `Evidence Handoff` section to every Phase 2 report. For each material number or claim, preserve the source artifact and field/row or indicator, period/as-of date, covered metric status and allowed uses when applicable, relevant gate outcome and blocking reasons when applicable, and material Not Rated gaps.
16. Make the report self-contained for downstream decision work. If required provenance or a restriction is unavailable, mark the claim N/A or Not Rated instead of omitting the limitation.

## Phases 3-7 report-only rules

17. Do not receive, open, search, or cite `{DATA_DIR}` or any file beneath the run's data directory. Use only persisted Phase 2 reports and required report artifacts from preceding phases.
18. Treat Phase 2 `Evidence Handoff` entries as the only evidence bridge from raw data. Preserve their source citations, statuses, allowed uses, gates, and blocking reasons in downstream reasoning.
19. Do not restore a blocked or unavailable claim through another report, debate consensus, or recalculation. If a Phase 2 report omits required provenance, status, allowed-use, or gate details, output N/A or Not Rated; never reopen raw data.
