# ABOUTME: Tests that calculator seed outputs match book prose numbers.
# ABOUTME: Validates all 3 example seeds produce expected LCPR, goodput, and margin values.

import pytest
import yaml
from pathlib import Path

from examples.run_seeds import (
    load_seed,
    run_support_answer,
    run_benchmark_audit,
    run_coding_agent,
)

EXAMPLES_DIR = Path(__file__).parent


class TestSupportAnswerSeed:
    """Example 1: numbers must match Part 5 Ch 24 worked example."""

    @pytest.fixture
    def output(self):
        seed = load_seed(EXAMPLES_DIR / "support-answer.trace-margin.v1/calculator-seed.yaml")
        return run_support_answer(seed)

    def test_total_loaded_cost(self, output):
        assert output["trace_to_margin"]["total_loaded_cost"] == pytest.approx(19150.0)

    def test_lcpr(self, output):
        assert output["trace_to_margin"]["lcpr"] == pytest.approx(0.234, abs=0.001)

    def test_delta(self, output):
        assert output["trace_to_margin"]["delta"] == pytest.approx(650.0)

    def test_naive_cost(self, output):
        assert output["trace_to_margin"]["naive_cost_per_unit"] == pytest.approx(0.142)

    def test_revenue(self, output):
        assert output["trace_to_margin"]["revenue"] == pytest.approx(45000.0, abs=1.0)

    def test_gross_margin(self, output):
        assert output["trace_to_margin"]["gross_margin"] == pytest.approx(25850.0, abs=1.0)

    def test_gross_margin_pct(self, output):
        assert output["trace_to_margin"]["gross_margin_pct"] == pytest.approx(0.574, abs=0.01)


class TestBenchmarkAuditSeed:
    """Example 3: Route A wins naive throughput, Route B wins goodput cost."""

    @pytest.fixture
    def output(self):
        seed = load_seed(EXAMPLES_DIR / "support-rag-answer-drafting.audit.v1/calculator-seed.yaml")
        return run_benchmark_audit(seed)

    def test_route_a_accepted(self, output):
        assert output["routes"]["route_a"]["goodput"]["accepted_requests"] == 58

    def test_route_b_accepted(self, output):
        assert output["routes"]["route_b"]["goodput"]["accepted_requests"] == 85

    def test_route_a_goodput_rate(self, output):
        assert output["routes"]["route_a"]["goodput"]["goodput_rate"] == pytest.approx(5.8)

    def test_route_b_goodput_rate(self, output):
        assert output["routes"]["route_b"]["goodput"]["goodput_rate"] == pytest.approx(8.5)

    def test_route_a_cost_per_accepted(self, output):
        assert output["routes"]["route_a"]["goodput"]["cost_per_accepted"] == pytest.approx(0.019, abs=0.001)

    def test_route_b_cost_per_accepted(self, output):
        assert output["routes"]["route_b"]["goodput"]["cost_per_accepted"] == pytest.approx(0.017, abs=0.001)

    def test_route_b_wins_on_goodput_cost(self, output):
        assert output["routes"]["analysis"]["winner_by_goodput_cost"] == "route_b"

    def test_route_a_wins_naive_throughput(self, output):
        assert output["routes"]["analysis"]["winner_by_naive_throughput"] == "route_a"

    def test_reversal_detected(self, output):
        assert output["routes"]["analysis"]["reversal"] is True

    def test_quality_gap(self, output):
        a_quality = output["routes"]["route_a"]["goodput"]["quality_pass_rate"]
        b_quality = output["routes"]["route_b"]["goodput"]["quality_pass_rate"]
        assert a_quality == pytest.approx(0.72)
        assert b_quality == pytest.approx(0.91)


class TestCodingAgentSeed:
    """Example 2: numbers must match Part 3 Ch 12 worked example."""

    @pytest.fixture
    def output(self):
        seed = load_seed(EXAMPLES_DIR / "coding-agent.lifecycle.v1/calculator-seed.yaml")
        return run_coding_agent(seed)

    def test_input_tokens(self, output):
        assert output["task_economics"]["input_tokens"] == 178000

    def test_output_tokens(self, output):
        assert output["task_economics"]["output_tokens"] == 18000

    def test_cache_hit_rate(self, output):
        assert output["task_economics"]["cache_hit_rate"] == pytest.approx(0.708, abs=0.01)

    def test_fanout_multiplier(self, output):
        assert output["task_economics"]["fanout_multiplier"] == 20

    def test_cache_saves_money(self, output):
        assert output["task_economics"]["cache_savings_ratio"] > 1.0

    def test_acceptance_rate(self, output):
        tasks = output["fleet_economics"]["tasks_per_month"]
        accepted = output["fleet_economics"]["accepted_per_month"]
        assert accepted / tasks == pytest.approx(0.90)
