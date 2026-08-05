# Portfolio Applicability and Position-Sizing Policy

This policy binds the Research Manager, Trader, all Risk Analysts, Portfolio Manager, and final report writer.

## 1. Resolve the portfolio mode before discussing allocation

Use exactly one mode:

- `research_only` — default. Use when the user did not explicitly request a model portfolio and did not supply complete portfolio context.
- `model_portfolio` — use only when the user explicitly requests a hypothetical/model portfolio and supplies every required assumption. Label every allocation as hypothetical.
- `portfolio_context_complete` — use only when the user supplies every required item for their actual portfolio.

Required items are: total portfolio value or investable capital; current position and cost basis (an explicit zero position is valid); cash/liquidity requirement; single-security, sector, country, and currency limits; maximum-loss/risk budget or drawdown constraint; investment horizon; leverage and short-sale permissions; and relevant correlated holdings or factor exposures.

If any required item is missing, contradictory, or only inferred, downgrade to `research_only`. Do not invent a portfolio mode, assumption, limit, exposure, or risk tolerance.

## 2. `research_only` output boundary

- Output exactly `Position Size: Not Rated — complete portfolio context was not supplied.`
- Do not output a maximum weight, incremental/cumulative weight, allocation percentage, capital amount, or share count.
- Entry conditions, invalidation conditions, tactical reference levels, and verification events may still be provided as security-research observations.
- Agreement among agents, strength of conviction, or a favorable risk/reward view cannot substitute for portfolio context.

## 3. `model_portfolio` disclosure

- Start the allocation section with `Hypothetical model portfolio — not individualized advice.`
- List every user-supplied assumption used in sizing, including an explicit zero for assumed absent holdings/exposures.
- If an assumption required by this policy is absent, downgrade to `research_only`; do not create a conventional 5%, 10%, or other default weight.

## 4. `portfolio_context_complete` evidence

- Cite each sizing input to the user-provided portfolio context or a current-run data artifact.
- Do not expose unrelated personal financial details in the report; include only inputs needed to audit the sizing result.
- A security rating remains a research view. The calculated weight is a separate portfolio-applicability result.

## 5. Risk-budget sizing formula

For `model_portfolio` and `portfolio_context_complete`, calculate every applicable cap and use the smallest:

```text
risk_budget_weight = maximum_loss_budget_percent / stop_or_invalidation_distance_percent
stress_weight = stress_loss_budget_percent / stress_drawdown_percent
liquidity_weight = maximum_liquid_position_notional / portfolio_value
final_maximum_weight = min(
  single_security_limit,
  remaining_sector_capacity,
  remaining_country_capacity,
  remaining_currency_capacity,
  risk_budget_weight,
  stress_weight,
  liquidity_weight,
  correlation_or_factor_capacity
)
```

- Show every applicable formula, input, unit, source, intermediate cap, and the binding minimum constraint.
- A missing denominator, limit, exposure, stop/invalidation distance, stress loss, or liquidity input makes numeric sizing Not Rated.
- For staged entries, incremental weights must sum to the final cumulative weight and may not exceed `final_maximum_weight`.
- Calculate `capital = portfolio value × incremental weight` and `shares = floor(capital / entry price)` only after the weight is valid. Apply market lot-size rules where relevant.
- Risk-agent proposals are scenario critiques, not arithmetic inputs. Agent voting or consensus must never increase `final_maximum_weight`.

## 6. Required final disclosure

Always state the resolved portfolio mode. For a numeric plan, also state the binding constraint and verify the incremental-weight sum. For `research_only`, retain the Position Plan section but use the exact Not Rated statement from Section 2.
