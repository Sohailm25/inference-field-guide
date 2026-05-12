# ABOUTME: Unit tests for migration readiness scoring module.
# ABOUTME: Tests complexity scoring, tier classification, gap detection, engineering hours, and payback.

import pytest

from calculator.readiness import (
    MigrationFactor,
    ReadinessResult,
    compute_payback,
    compute_readiness,
    get_engineering_hours,
)


# --- Fixtures ---


@pytest.fixture
def simple_factors():
    """All-low factors → Simple tier."""
    return [
        MigrationFactor(name="workload_count", score=1),
        MigrationFactor(name="prompt_portability", score=1),
        MigrationFactor(name="quality_infrastructure", score=1),
        MigrationFactor(name="latency_sensitivity", score=1),
        MigrationFactor(name="team_maturity", score=1),
        MigrationFactor(name="integration_depth", score=1),
    ]


@pytest.fixture
def standard_factors():
    """Mixed factors → Standard tier (score 12)."""
    return [
        MigrationFactor(name="workload_count", score=2),
        MigrationFactor(name="prompt_portability", score=2),
        MigrationFactor(name="quality_infrastructure", score=2),
        MigrationFactor(name="latency_sensitivity", score=2),
        MigrationFactor(name="team_maturity", score=2),
        MigrationFactor(name="integration_depth", score=2),
    ]


@pytest.fixture
def complex_factors():
    """All-high factors → Complex tier."""
    return [
        MigrationFactor(name="workload_count", score=3),
        MigrationFactor(name="prompt_portability", score=3),
        MigrationFactor(name="quality_infrastructure", score=3),
        MigrationFactor(name="latency_sensitivity", score=3),
        MigrationFactor(name="team_maturity", score=3),
        MigrationFactor(name="integration_depth", score=3),
    ]


# --- Scoring tests ---


class TestComputeReadiness:
    def test_simple_tier(self, simple_factors):
        result = compute_readiness(simple_factors)
        assert result.total_score == 6
        assert result.tier == "Simple"

    def test_standard_tier(self, standard_factors):
        result = compute_readiness(standard_factors)
        assert result.total_score == 12
        assert result.tier == "Standard"

    def test_complex_tier(self, complex_factors):
        result = compute_readiness(complex_factors)
        assert result.total_score == 18
        assert result.tier == "Complex"

    def test_simple_timeline(self, simple_factors):
        result = compute_readiness(simple_factors)
        assert result.timeline_weeks_min == 4
        assert result.timeline_weeks_max == 6

    def test_standard_timeline(self, standard_factors):
        result = compute_readiness(standard_factors)
        assert result.timeline_weeks_min == 8
        assert result.timeline_weeks_max == 12

    def test_complex_timeline(self, complex_factors):
        result = compute_readiness(complex_factors)
        assert result.timeline_weeks_min == 12
        assert result.timeline_weeks_max == 20

    def test_boundary_simple_standard(self):
        """Score of 9 is Simple, score of 10 is Standard."""
        factors_9 = [
            MigrationFactor(name="workload_count", score=2),
            MigrationFactor(name="prompt_portability", score=2),
            MigrationFactor(name="quality_infrastructure", score=1),
            MigrationFactor(name="latency_sensitivity", score=2),
            MigrationFactor(name="team_maturity", score=1),
            MigrationFactor(name="integration_depth", score=1),
        ]
        assert compute_readiness(factors_9).tier == "Simple"

        factors_10 = [
            MigrationFactor(name="workload_count", score=2),
            MigrationFactor(name="prompt_portability", score=2),
            MigrationFactor(name="quality_infrastructure", score=2),
            MigrationFactor(name="latency_sensitivity", score=2),
            MigrationFactor(name="team_maturity", score=1),
            MigrationFactor(name="integration_depth", score=1),
        ]
        assert compute_readiness(factors_10).tier == "Standard"

    def test_boundary_standard_complex(self):
        """Score of 14 is Standard, score of 15 is Complex."""
        factors_14 = [
            MigrationFactor(name="workload_count", score=2),
            MigrationFactor(name="prompt_portability", score=3),
            MigrationFactor(name="quality_infrastructure", score=2),
            MigrationFactor(name="latency_sensitivity", score=3),
            MigrationFactor(name="team_maturity", score=2),
            MigrationFactor(name="integration_depth", score=2),
        ]
        assert compute_readiness(factors_14).tier == "Standard"

        factors_15 = [
            MigrationFactor(name="workload_count", score=3),
            MigrationFactor(name="prompt_portability", score=3),
            MigrationFactor(name="quality_infrastructure", score=2),
            MigrationFactor(name="latency_sensitivity", score=3),
            MigrationFactor(name="team_maturity", score=2),
            MigrationFactor(name="integration_depth", score=2),
        ]
        assert compute_readiness(factors_15).tier == "Complex"

    def test_recommendation_simple(self, simple_factors):
        result = compute_readiness(simple_factors)
        assert "Self-service" in result.recommendation

    def test_recommendation_standard(self, standard_factors):
        result = compute_readiness(standard_factors)
        assert "managed dedicated" in result.recommendation.lower()

    def test_recommendation_complex(self, complex_factors):
        result = compute_readiness(complex_factors)
        assert "Field Deployment Engineer" in result.recommendation


# --- Gap detection tests ---


class TestGapDetection:
    def test_no_evals_gap(self):
        """Low quality_infrastructure should produce an eval gap."""
        factors = [
            MigrationFactor(name="workload_count", score=1),
            MigrationFactor(name="prompt_portability", score=1),
            MigrationFactor(name="quality_infrastructure", score=1),
            MigrationFactor(name="latency_sensitivity", score=1),
            MigrationFactor(name="team_maturity", score=2),
            MigrationFactor(name="integration_depth", score=1),
        ]
        result = compute_readiness(factors)
        gap_texts = [g.lower() for g in result.gaps]
        assert any("eval" in g for g in gap_texts)

    def test_no_team_high_latency_gap(self):
        """Low team_maturity + High latency_sensitivity should flag gap."""
        factors = [
            MigrationFactor(name="workload_count", score=1),
            MigrationFactor(name="prompt_portability", score=1),
            MigrationFactor(name="quality_infrastructure", score=2),
            MigrationFactor(name="latency_sensitivity", score=3),
            MigrationFactor(name="team_maturity", score=1),
            MigrationFactor(name="integration_depth", score=1),
        ]
        result = compute_readiness(factors)
        gap_texts = [g.lower() for g in result.gaps]
        assert any("inference expertise" in g or "latency" in g for g in gap_texts)

    def test_high_integration_high_workload_gap(self):
        """High integration_depth + High workload_count should flag phased approach."""
        factors = [
            MigrationFactor(name="workload_count", score=3),
            MigrationFactor(name="prompt_portability", score=1),
            MigrationFactor(name="quality_infrastructure", score=2),
            MigrationFactor(name="latency_sensitivity", score=1),
            MigrationFactor(name="team_maturity", score=2),
            MigrationFactor(name="integration_depth", score=3),
        ]
        result = compute_readiness(factors)
        gap_texts = [g.lower() for g in result.gaps]
        assert any("phased" in g for g in gap_texts)

    def test_no_gaps_when_all_medium_or_high(self):
        """Medium+ scores across the board should not trigger the 'no evals' gap."""
        factors = [
            MigrationFactor(name="workload_count", score=2),
            MigrationFactor(name="prompt_portability", score=2),
            MigrationFactor(name="quality_infrastructure", score=2),
            MigrationFactor(name="latency_sensitivity", score=2),
            MigrationFactor(name="team_maturity", score=2),
            MigrationFactor(name="integration_depth", score=2),
        ]
        result = compute_readiness(factors)
        gap_texts = [g.lower() for g in result.gaps]
        assert not any("no evaluation framework" in g for g in gap_texts)


# --- Engineering hours tests ---


class TestEngineeringHours:
    def test_serverless_hours(self):
        hours = get_engineering_hours("serverless")
        assert hours["setup_min"] == 2
        assert hours["setup_max"] == 8
        assert hours["monthly_min"] == 2
        assert hours["monthly_max"] == 5

    def test_managed_dedicated_hours(self):
        hours = get_engineering_hours("managed_dedicated")
        assert hours["setup_min"] == 8
        assert hours["setup_max"] == 20
        assert hours["monthly_min"] == 5
        assert hours["monthly_max"] == 10

    def test_self_managed_hours(self):
        hours = get_engineering_hours("self_managed")
        assert hours["setup_min"] == 40
        assert hours["setup_max"] == 80
        assert hours["monthly_min"] == 30
        assert hours["monthly_max"] == 60

    def test_unknown_mode_raises(self):
        with pytest.raises(KeyError):
            get_engineering_hours("nonexistent")


# --- Payback calculation tests ---


class TestPayback:
    def test_positive_savings(self):
        """If migration saves money, payback is positive and finite."""
        months = compute_payback(
            current_monthly_cost=10_000,
            projected_monthly_cost=7_000,
            engineering_investment=9_000,
        )
        assert months == pytest.approx(3.0)

    def test_no_savings(self):
        """If costs are the same, payback is infinite."""
        months = compute_payback(
            current_monthly_cost=10_000,
            projected_monthly_cost=10_000,
            engineering_investment=9_000,
        )
        assert months == float("inf")

    def test_negative_savings(self):
        """If migration costs more, payback is infinite (never pays back)."""
        months = compute_payback(
            current_monthly_cost=7_000,
            projected_monthly_cost=10_000,
            engineering_investment=9_000,
        )
        assert months == float("inf")

    def test_zero_investment(self):
        """Zero investment → immediate payback (0 months)."""
        months = compute_payback(
            current_monthly_cost=10_000,
            projected_monthly_cost=7_000,
            engineering_investment=0,
        )
        assert months == pytest.approx(0.0)


# --- Validation tests ---


class TestValidation:
    def test_score_out_of_range_raises(self):
        """Scores must be 1, 2, or 3."""
        with pytest.raises(ValueError):
            MigrationFactor(name="workload_count", score=0)

    def test_score_above_range_raises(self):
        with pytest.raises(ValueError):
            MigrationFactor(name="workload_count", score=4)

    def test_wrong_factor_count_raises(self):
        """Must provide exactly 6 factors."""
        factors = [MigrationFactor(name="workload_count", score=1)]
        with pytest.raises(ValueError):
            compute_readiness(factors)

    def test_invalid_factor_name_raises(self):
        """Factor names must match expected set."""
        factors = [
            MigrationFactor(name="garbage", score=1),
            MigrationFactor(name="prompt_portability", score=1),
            MigrationFactor(name="quality_infrastructure", score=1),
            MigrationFactor(name="latency_sensitivity", score=1),
            MigrationFactor(name="team_maturity", score=1),
            MigrationFactor(name="integration_depth", score=1),
        ]
        with pytest.raises(ValueError, match="unexpected"):
            compute_readiness(factors)

    def test_duplicate_factor_name_raises(self):
        """Duplicate factor names should fail (set shrinks below 6)."""
        factors = [
            MigrationFactor(name="workload_count", score=1),
            MigrationFactor(name="workload_count", score=2),
            MigrationFactor(name="quality_infrastructure", score=1),
            MigrationFactor(name="latency_sensitivity", score=1),
            MigrationFactor(name="team_maturity", score=1),
            MigrationFactor(name="integration_depth", score=1),
        ]
        with pytest.raises(ValueError):
            compute_readiness(factors)
