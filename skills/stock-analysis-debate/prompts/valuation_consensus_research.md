# Market Consensus Research

You are a sub-agent launched by the main session for Phase 1 Step 1. Use the web search tool and write the market-consensus artifact yourself; do not delegate to another agent and do not ask an analyst agent to invent or backfill this artifact. The main session supplies: ticker, market, analysis mode, execution date, quote currency, financial currency, target share basis, the absolute data-directory path, and whether `consensus_expectations` is enabled. Return only the artifact path and status — never the full contents.

## Objective

Build `{DATA_DIR}/valuation_consensus.toon` (or `.json` in JSON mode) for the resolved ticker and execution date. `{DATA_DIR}` is the **ticker-level** data directory (`reposrts/{TICKER}/data/`, no date suffix) — the same path the fetch-data step later passes via `--valuation-consensus-file`. Write it with `tools/structured_io.py::write_structured_file` (TOON is a non-text encoding; never hand-write `.toon` as plain text): run `python3 -c "import sys; sys.path.insert(0, 'skills/stock-analysis-debate/tools'); from structured_io import write_structured_file; write_structured_file('reposrts/{TICKER}/data/valuation_consensus', data)"`. Collect the **market consensus** as a single co-occurring bundle, not as disconnected single-metric lookups: on the same analyst-consensus page(s) you will usually find the Forward P/E, the analyst price target, the rating distribution, and the next-fiscal-year EPS/revenue consensus together. Capture them together from each source.

The artifact is usable for the deterministic target price only when it contains:

1. at least one current stock- or industry-level reasonable/consensus **Forward P/E** source (`web_consensus`);
2. at least three comparable-company **Forward P/E** observations (`peers`);
3. a verified target instrument currency and share basis, including the ADR/ADS ratio when applicable (`instrument`).

The co-occurring analyst-consensus block (`analyst_consensus`: price target, rating distribution, consensus EPS/revenue) is **expectation-analysis context only**. It is never a target-price input and never overrides the Forward EPS × peer Forward P/E method. Collect it **only when `consensus_expectations` is enabled**; by default (disabled) omit the `analyst_consensus` block entirely.

Search the company and industry separately. Prefer a primary filing/depositary-bank/exchange page for the instrument and a dated research, market-data, or financial-analysis page that lists the full consensus block. A search-result snippet, forum, unsourced blog, or qualitative statement such as "cheap"/"expensive" is not numeric evidence.

## Required evidence for every numeric item

Preserve the direct page URL, source name, `published_at` or `updated_at` (and `as_of_date` for a market snapshot), the canonical `forecast_period`, currency, share basis, and a short basis describing exactly what the page supports. Use `forecast_period: next_fiscal_year` only when the source describes the next fiscal year; do not silently map an unspecified NTM or trailing value to it.

The source must be no more than 60 calendar days old relative to `analysis_date`. If the publication/update date cannot be verified, exclude it from numeric evidence. A target price without its EPS period and share basis cannot be converted into a target P/E. Omit any consensus field the page does not state; never estimate a missing field.

## Output schema

Write this structured object to `{DATA_DIR}/valuation_consensus.toon` (or `.json` when JSON mode is configured) using `write_structured_file` as described above:

```yaml
schema_version: "1.0"
ticker: "{TICKER}"
analysis_date: "{DATE}"
status: available                         # or unavailable
search:
  query: "..."
  accessed_at: "..."
  max_age_days: 60
instrument:
  currency: USD
  share_basis: USD/ADR                    # e.g. USD/common_share, HKD/common_share
  adr_ratio: 0.1                          # only when explicitly sourced; ordinary shares per ADR
  source_name: "..."
  source_url: "https://..."
  as_of_date: "YYYY-MM-DD"
  basis: "..."
web_consensus:
  - scope: stock                          # stock or industry
    target_pe: 6.1                         # or reasonable_pe / median_pe / pe_range
    forecast_period: next_fiscal_year
    currency: USD
    share_basis: USD/common_share
    source_name: "..."
    source_url: "https://..."
    published_at: "YYYY-MM-DD"
    basis: "..."
peers:
  - symbol: "..."
    company: "..."
    forward_pe: 4.8
    forecast_period: next_fiscal_year
    currency: USD
    share_basis: USD/common_share
    source_name: "..."
    source_url: "https://..."
    as_of_date: "YYYY-MM-DD"
    published_at: "YYYY-MM-DD"             # include when the source supplies it
    basis: "..."
analyst_consensus:                          # OPT-IN: include only when consensus_expectations is enabled.
  - # One co-occurring analyst-consensus block from a single source page.
    # Expectation-analysis context ONLY; never a target-price input. Omit any
    # sub-field the page does not state.
    source_name: "..."
    source_url: "https://..."
    published_at: "YYYY-MM-DD"             # or updated_at / as_of_date
    basis: "Single page lists price target, ratings, and next-fiscal-year EPS/revenue consensus."
    price_target:
      mean: 8.40
      median: 8.20
      high: 10.00
      low: 6.00
      currency: USD
      share_basis: USD/ADR
      number_of_analysts: 12
    rating:
      average: "Moderate Buy"              # or numeric average with an explicit scale
      scale: "1-5"
      strong_buy: 5
      buy: 4
      hold: 2
      sell: 1
      strong_sell: 0
      total: 12
    eps_estimate:                          # next-fiscal-year consensus EPS
      value: 2.10
      currency: USD
      share_basis: USD/ADR
    revenue_estimate:                      # next-fiscal-year consensus revenue
      value: 85000000000
      currency: USD
```

If any target-price-required evidence is missing, write `status: unavailable`, keep the search audit and `blocking_reasons`, and leave the affected numeric list empty. When `consensus_expectations` is enabled, the `analyst_consensus` block may still be written when its own source is valid even if the target-price evidence is blocked; keep each block self-contained with its own source fields. When disabled (default), omit `analyst_consensus` entirely. Never put an estimated or model-filled number into the file.

## Final handoff

Tell the next data step only the artifact path and status. The Python layer will calculate P25/P50/P75 and the target prices; do not calculate or round target prices in this research step.
