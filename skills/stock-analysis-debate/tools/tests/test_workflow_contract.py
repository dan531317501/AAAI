import re
from collections import Counter
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[2]


def _workflow_states():
    skill = (SKILL_ROOT / "SKILL.md").read_text()
    section = skill.split("## Workflow State Machine", 1)[1].split("## Workflow", 1)[0]
    return re.findall(r"^\| `([A-Z_]+)` \|", section, re.MULTILINE)


class FakeFileStore:
    def __init__(self):
        self.artifacts = set()

    def persist(self, state):
        self.artifacts.add(state)

    def has(self, state):
        return state in self.artifacts


class FakeAgent:
    def __init__(self, failures_before_success=None):
        self.failures_before_success = dict(failures_before_success or {})
        self.calls = []

    def run(self, unit, store):
        self.calls.append(unit)
        remaining_failures = self.failures_before_success.get(unit, 0)
        if remaining_failures:
            self.failures_before_success[unit] = remaining_failures - 1
            return False
        store.persist(unit)
        return True


def _run_trace(agent, store):
    states = _workflow_states()
    trace = [states[0]]
    store.persist(states[0])

    for state in states[1:-1]:
        for _attempt in range(2):
            if agent.run(state, store) and store.has(state):
                trace.append(state)
                break
        else:
            trace.append("FAILED")
            return trace

    if store.has("REPORT_WRITTEN"):
        trace.append(states[-1])
    return trace


def _run_conditional_role(applicable, agent, store, role):
    if not applicable:
        return "NOT_RATED"
    for _attempt in range(2):
        if agent.run(role, store) and store.has(role):
            return "READY"
    return "FAILED"


def test_state_table_declares_the_complete_ordered_workflow():
    assert _workflow_states() == [
        "START",
        "DATA_READY",
        "BASE_ANALYSTS_READY",
        "ATTRIBUTION_READY",
        "DEBATE_READY",
        "RESEARCH_READY",
        "TRADER_READY",
        "RISK_READY",
        "REPORT_WRITTEN",
        "COMPLETE",
    ]


def test_fake_agent_and_file_store_reach_complete_in_table_order():
    agent = FakeAgent()
    store = FakeFileStore()

    trace = _run_trace(agent, store)

    assert trace == _workflow_states()
    assert all(store.has(state) for state in _workflow_states()[:-1])


def test_one_failure_retries_only_the_current_unit_then_continues():
    agent = FakeAgent({"ATTRIBUTION_READY": 1})
    store = FakeFileStore()

    trace = _run_trace(agent, store)

    assert trace == _workflow_states()
    assert Counter(agent.calls)["ATTRIBUTION_READY"] == 2
    assert all(
        count == 1
        for state, count in Counter(agent.calls).items()
        if state != "ATTRIBUTION_READY"
    )


def test_second_failure_is_terminal_and_skips_later_states():
    agent = FakeAgent({"DEBATE_READY": 2})
    store = FakeFileStore()

    trace = _run_trace(agent, store)

    assert trace[-1] == "FAILED"
    assert Counter(agent.calls)["DEBATE_READY"] == 2
    assert "RESEARCH_READY" not in agent.calls
    assert "COMPLETE" not in trace


def test_inapplicable_optional_role_degrades_without_scheduling_or_failure():
    agent = FakeAgent()
    store = FakeFileStore()

    result = _run_conditional_role(False, agent, store, "SEGMENT_ANALYST")

    assert result == "NOT_RATED"
    assert agent.calls == []
    assert not store.has("SEGMENT_ANALYST")


def test_report_persistence_second_failure_prevents_success_summary():
    agent = FakeAgent({"REPORT_WRITTEN": 2})
    store = FakeFileStore()

    trace = _run_trace(agent, store)

    assert trace[-1] == "FAILED"
    assert Counter(agent.calls)["REPORT_WRITTEN"] == 2
    assert not store.has("REPORT_WRITTEN")
    assert "COMPLETE" not in trace
