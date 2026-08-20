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


def test_phase_7_applies_phase_2_report_gate_without_reopening_data():
    skill = _read("SKILL.md")

    step_2_section = skill[skill.index("### Step 2: Phase 2 Report Gate"):skill.index("### Step 3: Synthesize")]
    assert "`Evidence Handoff` requirements in rule 9" in step_2_section
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


def test_phase_2_is_the_only_raw_data_reader_and_hands_off_evidence():
    skill = _read("SKILL.md")
    policy = _read("prompts/data_policy.md")

    assert "EVIDENCE, GATE, AND DATA ACCESS CONTRACT — GLOBAL" in skill
    assert "Phase 2 is the only analysis phase allowed to read" in skill
    assert "Phases 3-7 use only persisted reports and required prior-phase artifacts" in skill
    assert "must never receive, open, search, or cite the data directory" in skill
    assert "gate outcome/blocking reasons" in skill
    assert "another artifact" in policy
    assert "Do not use an LLM to recompute returns, growth, TTM, margins" in policy
    assert "Only Phase 2 roles may use numeric evidence" in policy
    assert "Do not receive, open, search, or cite `{DATA_DIR}`" in policy


def test_phases_3_to_7_receive_reports_but_no_data_directory_paths():
    skill = _read("SKILL.md")
    downstream = skill[skill.index("## Phase 3: Bull vs Bear Debate"):]

    for forbidden_text in (
        "configured `validated_metrics` artifact",
        "Read `validation_report.md`",
        "report/data directories",
        "individual reports and raw data",
    ):
        assert forbidden_text not in downstream
    assert "Do not provide the data directory or any raw-data path" not in downstream
    assert "do not open any path beneath the data directory" not in downstream

    for relative_path in (
        "prompts/bull_researcher.md",
        "prompts/bear_researcher.md",
        "prompts/aggressive_debator.md",
        "prompts/conservative_debator.md",
        "prompts/neutral_debator.md",
    ):
        prompt = _read(relative_path)
        assert "Read only the report files and prior-phase artifacts specified in your prompt." in prompt, relative_path

    portfolio_manager = _read("prompts/portfolio_manager.md")
    assert "Use only persisted Phase 2 reports and required Phase 3-6 report artifacts" in portfolio_manager


def test_global_contracts_are_not_repeated_in_phase_specific_sections():
    skill = _read("SKILL.md")
    phase_sections = skill[skill.index("## Output Directory Contract"):]

    for heading in (
        "FINAL DELIVERABLE CONTRACT",
        "REPORT DATE AND TIME MODE — GLOBAL",
        "EVIDENCE, GATE, AND DATA ACCESS CONTRACT — GLOBAL",
        "PORTFOLIO APPLICABILITY — GLOBAL",
        "CONTEXT HYGIENE (main session)",
        "ONE-RETRY POLICY — SINGLE FAILURE SOURCE OF TRUTH",
        "LANGUAGE CONTRACT — GLOBAL",
    ):
        assert skill.count(heading) == 1, heading

    for repeated_instruction in (
        "Apply rule 14",
        "apply rule 14",
        "Do not provide the data directory or any raw-data path",
        "Date guardrail",
        "Proceed immediately",
        "Context bloat",
        "SIMPLIFIED_CHINESE",
        "returns only a short confirmation/summary",
        "returns ONLY a one-line status confirmation",
    ):
        assert repeated_instruction not in phase_sections

    assert skill.count("Position Size: Not Rated — complete portfolio context was not supplied.") == 1


def test_runtime_language_contract_is_global_and_not_repeated_per_phase():
    skill = _read("SKILL.md")
    contract = skill[skill.index("15. **LANGUAGE CONTRACT — GLOBAL:"):skill.index("## Output Directory Contract")]
    phase_specific_instructions = skill[skill.index("## Output Directory Contract"):]

    assert "Use English for every machine-generated data key, label, note, summary" in contract
    assert "Preserve provider-supplied source text verbatim" in contract
    assert "Write only the final `analysis_report.md` in Simplified Chinese" in contract
    assert "do not repeat it in phase-specific instructions" in contract
    for artifact in (
        "Evidence Handoff",
        "debate_history.md",
        "research_plan.md",
        "trader_plan.md",
        "risk_debate_history.md",
    ):
        assert artifact in contract

    assert "Simplified Chinese" not in phase_specific_instructions
    assert " in English" not in phase_specific_instructions
    assert "English-authored" not in phase_specific_instructions
    assert "SIMPLIFIED_CHINESE" not in phase_specific_instructions


def test_target_price_and_strong_rating_have_two_stage_controls():
    skill = _read("SKILL.md")
    manager = _read("prompts/portfolio_manager.md")
    contract_tool = _read("tools/data_validation.py")

    assert "gate outcome/blocking reasons" in skill
    assert "Buy/Sell are strong ratings" in skill
    assert "valid_relative_return_evidence" in contract_tool
    assert "traceable_catalyst_evidence" in contract_tool
    assert "traceable_thesis_invalidation_condition" in contract_tool
    assert "multiple-sensitivity table" in skill
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


def test_attribution_prompt_aligns_the_six_steps_with_one_appendix():
    prompt = _read("prompts/price_action_attribution_analyst.md")

    assert "The six analytical steps are the only numbered body sections." in prompt
    for step in range(1, 7):
        assert f"**Step {step} —" in prompt
    assert "**Appendix A — Evidence Handoff**" in prompt
    assert "Do not turn every analytical concept into a separate numbered chapter" in prompt
    assert "one and only one provenance table" in prompt
    assert "never append a second report or a second handoff" in prompt


def test_attribution_prompt_enforces_causal_time_exposure_and_priced_in_gates():
    prompt = _read("prompts/price_action_attribution_analyst.md")

    for required_text in (
        "event_time",
        "published_at",
        "Source-independence gate",
        "Company-exposure gate",
        "Priced-in gate",
        "If the catalyst-specific baseline is unavailable, use `Not Rated`",
        "Do not reproduce a full market, news, social, or fundamentals report",
    ):
        assert required_text in prompt


def test_phase_2_output_contract_is_idempotent_and_structurally_verified():
    skill = _read("SKILL.md")
    policy = _read("prompts/data_policy.md")

    assert "single idempotent artifact" in skill
    assert "never appends to an existing report" in skill
    assert "one each of `Step 1` through `Step 6`" in skill
    assert "one and only one `Evidence Handoff`" in policy
    assert "event_time` and `published_at`" in policy
    assert "never append a second report" in policy


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
