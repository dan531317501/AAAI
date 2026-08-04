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
    assert "must never run in parallel with Step 1" in skill


def test_skill_allows_exactly_one_retry_then_stops():
    skill = _read("SKILL.md")

    assert "ONE-RETRY POLICY" in skill
    assert "retry only that analyst once" in skill
    assert "retry only that agent (same role and round) once" in skill
    assert "If the retry also fails, STOP the entire workflow immediately" in skill


def test_skill_passes_conditional_evidence_as_full_paths():
    skill = _read("SKILL.md")

    step_2_section = skill[skill.index("### Step 2 — Price Action Attribution Analyst"):skill.index("## Phase 3: Bull vs Bear Debate")]
    assert "Conditional evidence" in step_2_section
    assert "FULL absolute path" in step_2_section
    assert "{DATA_DIR}/global_news.txt" in step_2_section
    assert "{DATA_DIR}/options.txt" in step_2_section


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

    assert "`price_context.json`" in skill
    assert "`expectations.txt`" in skill
    assert "price_attribution_data.py" in skill
