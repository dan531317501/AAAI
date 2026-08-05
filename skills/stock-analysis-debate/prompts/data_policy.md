# Deterministic Data Policy

This policy binds every analyst, debater, manager, trader, and final report writer.

1. Read the configured `validated_metrics` artifact (`validated_metrics.toon` by default; `.json` in JSON mode) and `validation_report.md` before using a numeric claim.
2. Use a metric only when its `status`, `allowed_uses`, currency, period, and relevant gate permit the claim.
3. Never invent, interpolate, silently convert, or copy a blocked/raw provider value. Missing or disallowed data is `N/A` or `Not Rated`.
4. Treat `info.revenueGrowth` and `info.earningsGrowth` as latest-quarter historical actual YoY, not analyst consensus.
5. Use dedicated analyst-estimate records for consensus claims and preserve their per-row currency and period.
6. Keep quote currency and financial currency separate. Cross-currency arithmetic requires the contract's dated FX rate.
7. Use Longbridge Sankey values only within their `translated_only` allowed uses. Do not call them official operating growth or use them for valuation.
8. Do not extract numeric facts from an unstructured official filing with an LLM. Only tool-normalized structured official facts may authorize a number.
9. Perform only simple arithmetic over authorized inputs and show the formula, inputs, currencies, and result. If any input is unavailable, the result is unavailable.
10. A false decision gate is final for that run. Narrative confidence cannot override it.
