# Deterministic Data Policy

This policy binds every analyst, debater, manager, trader, and final report writer.

1. Numeric evidence may come from the current run's non-empty artifacts listed in `SKILL.md` under `{DATA_DIR}`. Do not use another date directory, a report file, a `.flag`, or a Not Rated/placeholder value as numeric evidence.
2. Read `temporal_context` in both `data_quality` and `validated_metrics` before using any artifact. A source whose `source_statuses.<source>.status` is not `allowed` is `Not Rated` even if its file contains a value.
3. In `historical_replay`, use only observations dated on/before `analysis_timestamp`, news with a parseable `published_at` on/before it, and official facts with `filed_at` on/before it. Retrieval-time fundamentals/statements, estimates/revisions/ratings/targets, insider, options, macro without vintage data, prediction markets, global-news search results, FX based on current metadata, and segment snapshots cannot support any claim.
4. Cite the source artifact, field/row or indicator, and period/as-of date for every material number. An analyst report is not a substitute for the underlying data artifact.
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
