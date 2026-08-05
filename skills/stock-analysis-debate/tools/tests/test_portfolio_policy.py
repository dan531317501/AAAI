from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[2]
POSITION_ROLES = (
    "prompts/research_manager.md",
    "prompts/trader.md",
    "prompts/aggressive_debator.md",
    "prompts/conservative_debator.md",
    "prompts/neutral_debator.md",
    "prompts/portfolio_manager.md",
)
NOT_RATED_POSITION = (
    "Position Size: Not Rated — complete portfolio context was not supplied."
)


def _read(relative_path: str) -> str:
    return (SKILL_ROOT / relative_path).read_text()


def test_portfolio_policy_defaults_incomplete_context_to_research_only():
    policy = _read("prompts/portfolio_policy.md")

    assert "`research_only` — default" in policy
    assert "`model_portfolio`" in policy
    assert "`portfolio_context_complete`" in policy
    assert "If any required item is missing, contradictory, or only inferred" in policy
    assert NOT_RATED_POSITION in policy
    assert "Do not output a maximum weight" in policy


def test_portfolio_policy_requires_real_context_before_numeric_sizing():
    policy = _read("prompts/portfolio_policy.md")

    for required_context in (
        "total portfolio value or investable capital",
        "current position and cost basis",
        "cash/liquidity requirement",
        "single-security, sector, country, and currency limits",
        "maximum-loss/risk budget or drawdown constraint",
        "investment horizon",
        "leverage and short-sale permissions",
        "correlated holdings or factor exposures",
    ):
        assert required_context in policy


def test_numeric_sizing_uses_minimum_constraint_not_agent_vote():
    policy = _read("prompts/portfolio_policy.md")

    assert "risk_budget_weight = maximum_loss_budget_percent" in policy
    assert "stress_weight = stress_loss_budget_percent" in policy
    assert "liquidity_weight = maximum_liquid_position_notional" in policy
    assert "final_maximum_weight = min(" in policy
    assert "binding minimum constraint" in policy
    assert "Agent voting or consensus must never increase" in policy


def test_every_position_role_reads_shared_policy_and_handles_research_only():
    for relative_path in POSITION_ROLES:
        prompt = _read(relative_path)
        assert "portfolio_policy.md" in prompt, relative_path
        assert "research_only" in prompt, relative_path
        assert "Position Size: Not Rated" in prompt, relative_path


def test_skill_passes_portfolio_policy_and_mode_through_decision_phases():
    skill = _read("SKILL.md")

    assert "**PORTFOLIO APPLICABILITY:**" in skill
    assert NOT_RATED_POSITION in skill
    assert "`prompts/portfolio_policy.md`" in skill
    assert "| `portfolio_mode` | `research_only` |" in skill
    assert "Agent consensus never substitutes" in skill
    assert "In `research_only`, that result contains no allocation number" in skill


def test_old_percentage_fallback_and_role_vote_examples_are_removed():
    combined = "\n".join(_read(path) for path in POSITION_ROLES)

    assert "use percentages only" not in combined
    assert "20% cap" not in combined
    assert "15% cap" not in combined
    assert "10% cap" not in combined
