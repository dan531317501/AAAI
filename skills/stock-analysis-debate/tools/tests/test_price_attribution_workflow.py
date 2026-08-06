from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path):
    return (SKILL_ROOT / relative_path).read_text()


def test_skill_runs_attribution_only_after_step_1_and_before_debate():
    skill = _read("SKILL.md")

    step_1 = skill.index("### Step 1 — The Base Analysts")
    step_2 = skill.index("### Step 2 — Price Action Attribution Analyst")
    phase_3 = skill.index("## Phase 3: Bull vs Bear Debate")

    assert step_1 < step_2 < phase_3
    assert "price_action_attribution_analyst.md` exists and is non-empty" in skill
    assert "must never overlap Step 1" in skill


def test_skill_allows_exactly_one_retry_then_stops():
    skill = _read("SKILL.md")

    assert "ONE-RETRY POLICY — SINGLE FAILURE SOURCE OF TRUTH" in skill
    assert "at most two total attempts" in skill
    assert "the initial attempt plus exactly one retry of that unit" in skill
    assert "A successful return is insufficient without its required non-empty artifact" in skill
    assert "enter terminal `FAILED`" in skill
    assert "This policy also covers final report persistence" in skill
    assert "note it in the report but do NOT stop" not in skill


def test_base_analyst_prompts_use_persisted_inputs_without_provider_calls():
    fundamentals = _read("prompts/fundamentals_analyst.md")
    market = _read("prompts/market_analyst.md")

    for forbidden_name in (
        "get_fundamentals",
        "get_balance_sheet",
        "get_cashflow",
        "get_income_statement",
    ):
        assert forbidden_name not in fundamentals
    for forbidden_name in ("get_stock_data", "get_indicators"):
        assert forbidden_name not in market
    assert "Run independently from the Segment Analyst" in fundamentals
    assert "do not call provider-data tools or refetch these inputs" in fundamentals
    assert "do not call market-data or indicator tools" in market


def test_workflow_contract_avoids_batch_syntax_and_uses_explicit_file_tools():
    skill = _read("SKILL.md")
    prompts = "\n".join(
        _read(relative_path)
        for relative_path in (
            "prompts/bull_researcher.md",
            "prompts/bear_researcher.md",
            "prompts/aggressive_debator.md",
            "prompts/conservative_debator.md",
            "prompts/neutral_debator.md",
        )
    )

    for runtime_specific_text in (
        "SINGLE message",
        "SAME batch",
        "run_in_background",
        "Agent tool",
        "Bash tool",
    ):
        assert runtime_specific_text not in skill
        assert runtime_specific_text not in prompts
    assert "using the Read tool" in skill
    assert "Use the Write tool" in skill
    assert "using the Read tool" in prompts
    assert "using the Write tool" in prompts


def test_skill_passes_conditional_evidence_as_full_paths():
    skill = _read("SKILL.md")

    step_2_section = skill[skill.index("### Step 2 — Price Action Attribution Analyst"):skill.index("## Phase 3: Bull vs Bear Debate")]
    assert "Conditional evidence" in step_2_section
    assert "FULL absolute path" in step_2_section
    assert "{DATA_DIR}/global_news.txt" in step_2_section
    assert "{DATA_DIR}/options.txt" in step_2_section


def test_skill_runs_deterministic_data_gate_without_llm_verifier():
    skill = _read("SKILL.md")

    step_2_section = skill[skill.index("### Step 2: Deterministic Data Gate"):skill.index("### Step 3: Synthesize")]
    assert "configured `validated_metrics` artifact" in step_2_section
    assert "validation_report.md" in step_2_section
    assert "do not launch an agent" in step_2_section
    assert "N/A or Not Rated" in step_2_section
    assert "arithmetic_verifier.md" not in skill


def test_numeric_validation_is_implemented_in_tools():
    contract_tool = _read("tools/data_validation.py")
    audit_tool = _read("tools/financial_audit.py")

    for required_text in (
        "quote_currency",
        "financial_currency",
        "allow_exact_valuation",
        "allow_target_price",
        "translated_only",
        "raw_provider_values_allowed",
    ):
        assert required_text in contract_tool, required_text
    assert "_periods_are_contiguous_quarters" in audit_tool


def test_current_run_data_directory_is_the_numeric_evidence_set():
    skill = _read("SKILL.md")
    policy = _read("prompts/data_policy.md")

    assert "DATA DIRECTORY EVIDENCE CONTRACT" in skill
    assert "current run's non-empty artifacts listed in Phase 1" in skill
    assert "source file, field/row or indicator, and period/as-of date" in skill
    assert "authoritative only for the metrics it contains and for all `gates`" in skill
    assert "another artifact" in policy
    assert "Do not use an LLM to recompute returns, growth, TTM, margins" in policy
    assert "An analyst report is not a substitute for the underlying data artifact" in policy


def test_target_price_and_strong_rating_have_two_stage_controls():
    skill = _read("SKILL.md")
    manager = _read("prompts/portfolio_manager.md")
    contract_tool = _read("tools/data_validation.py")

    assert "gate_details.blocking_reasons" in skill
    assert "Buy/Sell are strong ratings" in skill
    assert "valid_relative_return_evidence" in contract_tool
    assert "traceable_catalyst_evidence" in contract_tool
    assert "traceable_thesis_invalidation_condition" in contract_tool
    assert "include a multiple-sensitivity table" in skill
    assert "Buy and Sell are strong ratings" in manager
    assert "If any requirement is missing" in manager


def test_attribution_prompt_has_evidence_and_role_boundaries():
    prompt = _read("prompts/price_action_attribution_analyst.md")

    for required_text in (
        "Expectation Baseline",
        "Trigger / Surprise",
        "Transmission / Amplifier",
        "Observed Price Move",
        "Fundamental Anchor",
        "Conditional Outlook",
        "No short squeeze without short evidence",
        "No rating, target price, position size, or transaction recommendation issued",
    ):
        assert required_text in prompt


def test_all_decision_layers_consume_or_challenge_attribution_report():
    for relative_path in (
        "prompts/bull_researcher.md",
        "prompts/bear_researcher.md",
        "prompts/research_manager.md",
        "prompts/trader.md",
        "prompts/aggressive_debator.md",
        "prompts/conservative_debator.md",
        "prompts/neutral_debator.md",
        "prompts/portfolio_manager.md",
    ):
        assert "price_action_attribution_analyst.md" in _read(relative_path), relative_path


def test_skill_declares_both_attribution_data_artifacts():
    skill = _read("SKILL.md")

    assert "`price_context.toon`" in skill
    assert "`expectations.txt`" in skill
    assert "price_attribution_data.py" in skill
