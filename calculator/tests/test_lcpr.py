# ABOUTME: Unit tests for the LCPR (Loaded Cost Per Result) calculation engine.
# ABOUTME: Tests core formula, break-even analysis, sensitivity, edge cases, and pricing loading.

import math
from pathlib import Path

import pytest

from calculator.lcpr import (
    LCPRCalculator,
    LCPRResult,
    ProviderPricing,
    WorkloadProfile,
    compute_break_even,
    compute_lcpr,
    load_provider_pricing,
)

# --- Fixtures ---


@pytest.fixture
def simple_profile():
    """Minimal workload profile for testing."""
    return WorkloadProfile(
        avg_input_tokens=500,
        avg_output_tokens=200,
        monthly_requests=100_000,
        retry_rate=0.05,
        quality_gate_pass_rate=0.95,
        repair_cost_per_failure=0.002,
        engineering_hours_per_month=10,
        engineer_hourly_cost=100,
    )


@pytest.fixture
def zero_failure_profile():
    """Profile with no retries, no failures — ideal case."""
    return WorkloadProfile(
        avg_input_tokens=500,
        avg_output_tokens=200,
        monthly_requests=100_000,
        retry_rate=0.0,
        quality_gate_pass_rate=1.0,
        repair_cost_per_failure=0.0,
        engineering_hours_per_month=0,
        engineer_hourly_cost=0,
    )


@pytest.fixture
def openai_pricing():
    """GPT-5.5 pricing."""
    return ProviderPricing(
        name="OpenAI GPT-5.5",
        input_rate_per_m=5.00,
        output_rate_per_m=30.00,
        deployment_mode="closed_api",
    )


@pytest.fixture
def together_pricing():
    """Together AI DeepSeek V3 serverless pricing.
    [PUBLIC_PRICING] together.ai/pricing — verified 2026-05-12."""
    return ProviderPricing(
        name="Together DeepSeek V3",
        input_rate_per_m=0.60,
        output_rate_per_m=1.70,
        deployment_mode="serverless_open",
    )


@pytest.fixture
def dedicated_pricing():
    """Dedicated H100 pricing (Lambda).
    [PUBLIC_PRICING] lambda.ai/pricing — verified 2026-05-12."""
    return ProviderPricing(
        name="Lambda H100 Dedicated",
        input_rate_per_m=0.0,
        output_rate_per_m=0.0,
        deployment_mode="dedicated",
        gpu_hourly_rate=3.99,
        throughput_tps=1500,
        utilization=0.40,
    )


# --- Core LCPR Formula Tests ---


class TestComputeLCPR:
    """Tests for the core LCPR formula."""

    def test_basic_lcpr_closed_api(self, simple_profile, openai_pricing):
        """LCPR for closed API should account for token cost + overhead."""
        result = compute_lcpr(simple_profile, openai_pricing)

        assert isinstance(result, LCPRResult)
        assert result.lcpr > 0
        assert result.monthly_cost > 0
        assert result.cost_per_1k_requests > 0

    def test_lcpr_reflects_token_pricing(self, simple_profile, openai_pricing, together_pricing):
        """Cheaper per-token pricing should produce lower base LCPR."""
        openai_result = compute_lcpr(simple_profile, openai_pricing)
        together_result = compute_lcpr(simple_profile, together_pricing)

        # Together at $0.60/$1.70 should be much cheaper than OpenAI at $5/$30
        assert together_result.lcpr < openai_result.lcpr

    def test_zero_failure_lcpr_equals_raw_token_cost(self, zero_failure_profile, openai_pricing):
        """With no retries, no failures, no engineering cost, LCPR = raw token cost."""
        result = compute_lcpr(zero_failure_profile, openai_pricing)

        # Expected: (500 * 5.00/1M + 200 * 30.00/1M) / 1.0
        expected_raw = (500 * 5.00 / 1_000_000) + (200 * 30.00 / 1_000_000)
        assert math.isclose(result.lcpr, expected_raw, rel_tol=1e-6)

    def test_retry_rate_increases_lcpr(self, simple_profile, openai_pricing):
        """Higher retry rate should increase LCPR."""
        low_retry = simple_profile
        high_retry = WorkloadProfile(
            avg_input_tokens=500,
            avg_output_tokens=200,
            monthly_requests=100_000,
            retry_rate=0.20,  # 20% vs 5%
            quality_gate_pass_rate=0.95,
            repair_cost_per_failure=0.002,
            engineering_hours_per_month=10,
            engineer_hourly_cost=100,
        )

        low_result = compute_lcpr(low_retry, openai_pricing)
        high_result = compute_lcpr(high_retry, openai_pricing)

        assert high_result.lcpr > low_result.lcpr

    def test_quality_gate_affects_lcpr(self, simple_profile, openai_pricing):
        """Lower quality gate pass rate should increase LCPR (fewer successful requests)."""
        high_quality = simple_profile  # 95% pass rate
        low_quality = WorkloadProfile(
            avg_input_tokens=500,
            avg_output_tokens=200,
            monthly_requests=100_000,
            retry_rate=0.05,
            quality_gate_pass_rate=0.70,  # 70% vs 95%
            repair_cost_per_failure=0.002,
            engineering_hours_per_month=10,
            engineer_hourly_cost=100,
        )

        high_result = compute_lcpr(high_quality, openai_pricing)
        low_result = compute_lcpr(low_quality, openai_pricing)

        assert low_result.lcpr > high_result.lcpr

    def test_engineering_cost_increases_lcpr(self, zero_failure_profile, openai_pricing):
        """Adding engineering time should increase LCPR."""
        with_eng = WorkloadProfile(
            avg_input_tokens=500,
            avg_output_tokens=200,
            monthly_requests=100_000,
            retry_rate=0.0,
            quality_gate_pass_rate=1.0,
            repair_cost_per_failure=0.0,
            engineering_hours_per_month=40,
            engineer_hourly_cost=150,
        )

        no_eng_result = compute_lcpr(zero_failure_profile, openai_pricing)
        with_eng_result = compute_lcpr(with_eng, openai_pricing)

        assert with_eng_result.lcpr > no_eng_result.lcpr

    def test_monthly_cost_is_lcpr_times_accepted_work_units(self, simple_profile, openai_pricing):
        """Monthly cost should be consistent with LCPR × accepted work units."""
        result = compute_lcpr(simple_profile, openai_pricing)

        # Monthly cost = total cost of all requests (including retries, failures, engineering)
        # LCPR = monthly_cost / accepted_work_units
        accepted_units = simple_profile.monthly_requests * simple_profile.quality_gate_pass_rate
        expected_monthly = result.lcpr * accepted_units
        assert math.isclose(result.monthly_cost, expected_monthly, rel_tol=1e-6)


# --- Dedicated GPU LCPR Tests ---


class TestDedicatedLCPR:
    """Tests for dedicated GPU LCPR calculation."""

    def test_dedicated_lcpr_uses_gpu_cost(self, simple_profile, dedicated_pricing):
        """Dedicated LCPR should derive from GPU hourly cost, not per-token rates."""
        result = compute_lcpr(simple_profile, dedicated_pricing)
        assert result.lcpr > 0
        assert result.deployment_mode == "dedicated"

    def test_dedicated_cheaper_at_high_volume(self, dedicated_pricing, together_pricing):
        """At high enough volume, dedicated should be cheaper than serverless."""
        high_volume = WorkloadProfile(
            avg_input_tokens=500,
            avg_output_tokens=200,
            monthly_requests=50_000_000,  # 50M requests/month
            retry_rate=0.02,
            quality_gate_pass_rate=0.98,
            repair_cost_per_failure=0.001,
            engineering_hours_per_month=40,
            engineer_hourly_cost=100,
        )

        dedicated_result = compute_lcpr(high_volume, dedicated_pricing)
        serverless_result = compute_lcpr(high_volume, together_pricing)

        # At 50M requests × 200 output tokens = 10B output tokens/month
        # Dedicated should win at this scale
        assert dedicated_result.lcpr < serverless_result.lcpr

    def test_dedicated_more_expensive_at_low_volume(self, dedicated_pricing, together_pricing):
        """At low volume, dedicated GPU utilization is wasted — serverless wins."""
        low_volume = WorkloadProfile(
            avg_input_tokens=500,
            avg_output_tokens=200,
            monthly_requests=10_000,  # 10K requests/month — very low
            retry_rate=0.02,
            quality_gate_pass_rate=0.98,
            repair_cost_per_failure=0.001,
            engineering_hours_per_month=10,
            engineer_hourly_cost=100,
        )

        dedicated_result = compute_lcpr(low_volume, dedicated_pricing)
        serverless_result = compute_lcpr(low_volume, together_pricing)

        assert serverless_result.lcpr < dedicated_result.lcpr


# --- Break-Even Analysis Tests ---


class TestBreakEven:
    """Tests for crossover/break-even analysis between deployment modes."""

    def test_break_even_infeasible_at_low_utilization(self, together_pricing, dedicated_pricing):
        """At $3.99/hr, 40% util vs $1.70/M serverless — effective dedicated rate
        ($1.848/M) exceeds serverless, so break-even is not feasible."""
        result = compute_break_even(together_pricing, dedicated_pricing)

        assert not result.break_even_feasible
        assert result.break_even_daily_output_tokens == float("inf")
        assert result.effective_cost_per_m > together_pricing.output_rate_per_m

    def test_break_even_feasible_at_higher_utilization(self, together_pricing):
        """At $3.99/hr, 60% util vs $1.70/M — effective rate ($1.23/M) is below
        serverless, so break-even IS feasible."""
        high_util_gpu = ProviderPricing(
            name="Lambda H100 (60% util)",
            input_rate_per_m=0.0,
            output_rate_per_m=0.0,
            deployment_mode="dedicated",
            gpu_hourly_rate=3.99,
            throughput_tps=1500,
            utilization=0.60,
        )
        result = compute_break_even(together_pricing, high_util_gpu)

        assert result.break_even_feasible
        assert result.break_even_daily_output_tokens > 0
        assert result.break_even_daily_output_tokens < 1e12

    def test_break_even_higher_with_lower_utilization(self, together_pricing):
        """Lower GPU utilization should push break-even higher."""
        high_util = ProviderPricing(
            name="H100 High Util",
            input_rate_per_m=0.0,
            output_rate_per_m=0.0,
            deployment_mode="dedicated",
            gpu_hourly_rate=2.99,
            throughput_tps=1500,
            utilization=0.60,
        )
        low_util = ProviderPricing(
            name="H100 Low Util",
            input_rate_per_m=0.0,
            output_rate_per_m=0.0,
            deployment_mode="dedicated",
            gpu_hourly_rate=2.99,
            throughput_tps=1500,
            utilization=0.30,
        )

        high_result = compute_break_even(together_pricing, high_util)
        low_result = compute_break_even(together_pricing, low_util)

        # Lower utilization → need more volume to break even
        assert (
            low_result.break_even_daily_output_tokens > high_result.break_even_daily_output_tokens
        )

    def test_break_even_lower_with_cheaper_gpu(self, together_pricing):
        """Cheaper GPUs should lower the break-even point."""
        expensive_gpu = ProviderPricing(
            name="CoreWeave H100",
            input_rate_per_m=0.0,
            output_rate_per_m=0.0,
            deployment_mode="dedicated",
            gpu_hourly_rate=6.16,
            throughput_tps=1500,
            utilization=0.40,
        )
        cheap_gpu = ProviderPricing(
            name="Lambda H100",
            input_rate_per_m=0.0,
            output_rate_per_m=0.0,
            deployment_mode="dedicated",
            gpu_hourly_rate=2.99,
            throughput_tps=1500,
            utilization=0.40,
        )

        expensive_result = compute_break_even(together_pricing, expensive_gpu)
        cheap_result = compute_break_even(together_pricing, cheap_gpu)

        assert (
            cheap_result.break_even_daily_output_tokens
            < expensive_result.break_even_daily_output_tokens
        )


# --- Provider Pricing Loading Tests ---


class TestLoadPricing:
    """Tests for loading provider pricing from YAML."""

    def test_load_pricing_returns_providers(self):
        """Should load provider pricing from the YAML file."""
        pricing_path = Path(__file__).parent.parent / "provider_pricing.yaml"
        providers = load_provider_pricing(pricing_path)

        assert len(providers) > 0
        assert all(isinstance(p, ProviderPricing) for p in providers)

    def test_loaded_pricing_has_expected_providers(self):
        """Should include key providers from the YAML."""
        pricing_path = Path(__file__).parent.parent / "provider_pricing.yaml"
        providers = load_provider_pricing(pricing_path)

        provider_names = [p.name for p in providers]
        # Check a few key providers exist
        assert any("OpenAI" in n or "GPT" in n for n in provider_names)
        assert any("Together" in n for n in provider_names)
        assert any("Lambda" in n for n in provider_names)

    def test_loaded_pricing_has_positive_rates(self):
        """All per-token providers should have positive rates."""
        pricing_path = Path(__file__).parent.parent / "provider_pricing.yaml"
        providers = load_provider_pricing(pricing_path)

        for p in providers:
            if p.deployment_mode in ("closed_api", "serverless_open"):
                assert p.input_rate_per_m > 0, f"{p.name} has zero input rate"
                assert p.output_rate_per_m > 0, f"{p.name} has zero output rate"

    def test_loaded_dedicated_has_gpu_rates(self):
        """Dedicated providers should have GPU hourly rates."""
        pricing_path = Path(__file__).parent.parent / "provider_pricing.yaml"
        providers = load_provider_pricing(pricing_path)

        dedicated = [p for p in providers if p.deployment_mode == "dedicated"]
        assert len(dedicated) > 0
        for p in dedicated:
            assert p.gpu_hourly_rate > 0, f"{p.name} missing GPU hourly rate"


# --- LCPRCalculator Integration Tests ---


class TestLCPRCalculator:
    """Tests for the high-level calculator that compares across providers."""

    def test_calculator_compares_all_modes(self, simple_profile):
        """Calculator should produce results across all deployment modes."""
        pricing_path = Path(__file__).parent.parent / "provider_pricing.yaml"
        calc = LCPRCalculator(pricing_path)

        results = calc.compare(simple_profile)

        assert len(results) > 0
        assert all(isinstance(r, LCPRResult) for r in results)
        # Should have results from multiple deployment modes
        modes = {r.deployment_mode for r in results}
        assert len(modes) >= 2

    def test_calculator_results_sorted_by_lcpr(self, simple_profile):
        """Results should be sorted by LCPR ascending (cheapest first)."""
        pricing_path = Path(__file__).parent.parent / "provider_pricing.yaml"
        calc = LCPRCalculator(pricing_path)

        results = calc.compare(simple_profile)

        lcprs = [r.lcpr for r in results]
        assert lcprs == sorted(lcprs)

    def test_calculator_sensitivity(self, simple_profile):
        """Sensitivity analysis should show LCPR at different retry rates."""
        pricing_path = Path(__file__).parent.parent / "provider_pricing.yaml"
        calc = LCPRCalculator(pricing_path)

        sensitivity = calc.sensitivity(
            simple_profile,
            vary="retry_rate",
            values=[0.0, 0.05, 0.10, 0.20],
        )

        assert len(sensitivity) == 4
        # LCPR should increase with retry rate
        lcprs = [s["lcpr"] for s in sensitivity]
        assert lcprs == sorted(lcprs)


# --- Edge Cases ---


class TestEdgeCases:
    """Tests for boundary conditions and edge cases."""

    def test_zero_output_tokens(self, openai_pricing):
        """Profile with zero output tokens (input-only classification)."""
        profile = WorkloadProfile(
            avg_input_tokens=1000,
            avg_output_tokens=0,
            monthly_requests=100_000,
            retry_rate=0.05,
            quality_gate_pass_rate=0.95,
            repair_cost_per_failure=0.0,
            engineering_hours_per_month=0,
            engineer_hourly_cost=0,
        )
        result = compute_lcpr(profile, openai_pricing)
        assert result.lcpr > 0

    def test_very_high_retry_rate(self, openai_pricing):
        """50% retry rate — cost should roughly double."""
        base = WorkloadProfile(
            avg_input_tokens=500,
            avg_output_tokens=200,
            monthly_requests=100_000,
            retry_rate=0.0,
            quality_gate_pass_rate=1.0,
            repair_cost_per_failure=0.0,
            engineering_hours_per_month=0,
            engineer_hourly_cost=0,
        )
        high_retry = WorkloadProfile(
            avg_input_tokens=500,
            avg_output_tokens=200,
            monthly_requests=100_000,
            retry_rate=0.50,
            quality_gate_pass_rate=1.0,
            repair_cost_per_failure=0.0,
            engineering_hours_per_month=0,
            engineer_hourly_cost=0,
        )

        base_result = compute_lcpr(base, openai_pricing)
        retry_result = compute_lcpr(high_retry, openai_pricing)

        # 50% retries means ~1.5x the token cost
        ratio = retry_result.lcpr / base_result.lcpr
        assert 1.4 < ratio < 1.6

    def test_single_request(self, openai_pricing):
        """Single request should still produce valid LCPR."""
        profile = WorkloadProfile(
            avg_input_tokens=500,
            avg_output_tokens=200,
            monthly_requests=1,
            retry_rate=0.0,
            quality_gate_pass_rate=1.0,
            repair_cost_per_failure=0.0,
            engineering_hours_per_month=0,
            engineer_hourly_cost=0,
        )
        result = compute_lcpr(profile, openai_pricing)
        assert result.lcpr > 0
        assert math.isfinite(result.lcpr)


# --- Division-by-Zero / Validation Tests ---


class TestDivisionByZeroValidation:
    """Tests that zero denominators raise ValueError instead of silently clamping."""

    def test_zero_quality_gate_raises_error(self, openai_pricing):
        """quality_gate_pass_rate=0.0 should raise ValueError, not silently clamp."""
        profile = WorkloadProfile(
            avg_input_tokens=500,
            avg_output_tokens=200,
            monthly_requests=100_000,
            retry_rate=0.05,
            quality_gate_pass_rate=0.0,
            repair_cost_per_failure=0.002,
            engineering_hours_per_month=10,
            engineer_hourly_cost=100,
        )
        with pytest.raises(ValueError, match="quality_gate_pass_rate must be > 0"):
            compute_lcpr(profile, openai_pricing)

    def test_zero_quality_gate_raises_error_dedicated(self):
        """quality_gate_pass_rate=0.0 raises ValueError in dedicated mode too."""
        profile = WorkloadProfile(
            avg_input_tokens=500,
            avg_output_tokens=200,
            monthly_requests=100_000,
            retry_rate=0.05,
            quality_gate_pass_rate=0.0,
            repair_cost_per_failure=0.002,
            engineering_hours_per_month=10,
            engineer_hourly_cost=100,
        )
        pricing = ProviderPricing(
            name="Test Dedicated",
            input_rate_per_m=0.0,
            output_rate_per_m=0.0,
            deployment_mode="dedicated",
            gpu_hourly_rate=2.99,
            throughput_tps=1500,
            utilization=0.40,
        )
        with pytest.raises(ValueError, match="quality_gate_pass_rate must be > 0"):
            compute_lcpr(profile, pricing)

    def test_zero_utilization_raises_error(self):
        """Dedicated with throughput_tps=0 or utilization=0 should raise ValueError."""
        profile = WorkloadProfile(
            avg_input_tokens=500,
            avg_output_tokens=200,
            monthly_requests=100_000,
            retry_rate=0.05,
            quality_gate_pass_rate=0.95,
            repair_cost_per_failure=0.002,
            engineering_hours_per_month=10,
            engineer_hourly_cost=100,
        )
        pricing_zero_util = ProviderPricing(
            name="Zero Util GPU",
            input_rate_per_m=0.0,
            output_rate_per_m=0.0,
            deployment_mode="dedicated",
            gpu_hourly_rate=2.99,
            throughput_tps=1500,
            utilization=0.0,
        )
        with pytest.raises(ValueError, match="effective throughput must be > 0"):
            compute_lcpr(profile, pricing_zero_util)

    def test_zero_throughput_raises_error(self):
        """Dedicated with throughput_tps=0 should raise ValueError."""
        profile = WorkloadProfile(
            avg_input_tokens=500,
            avg_output_tokens=200,
            monthly_requests=100_000,
            retry_rate=0.05,
            quality_gate_pass_rate=0.95,
            repair_cost_per_failure=0.002,
            engineering_hours_per_month=10,
            engineer_hourly_cost=100,
        )
        pricing_zero_tps = ProviderPricing(
            name="Zero TPS GPU",
            input_rate_per_m=0.0,
            output_rate_per_m=0.0,
            deployment_mode="dedicated",
            gpu_hourly_rate=2.99,
            throughput_tps=0,
            utilization=0.40,
        )
        with pytest.raises(ValueError, match="effective throughput must be > 0"):
            compute_lcpr(profile, pricing_zero_tps)


# --- Cache Hit Rate Tests ---


class TestCacheHitRate:
    """Tests for cache_hit_rate support in LCPR calculation."""

    def test_cache_hit_rate_reduces_lcpr(self):
        """With cache_hit_rate=0.8 and a cheap cached rate, LCPR should drop."""
        profile_no_cache = WorkloadProfile(
            avg_input_tokens=2000,
            avg_output_tokens=200,
            monthly_requests=100_000,
            retry_rate=0.0,
            quality_gate_pass_rate=1.0,
            repair_cost_per_failure=0.0,
            engineering_hours_per_month=0,
            engineer_hourly_cost=0,
        )
        profile_cached = WorkloadProfile(
            avg_input_tokens=2000,
            avg_output_tokens=200,
            monthly_requests=100_000,
            retry_rate=0.0,
            quality_gate_pass_rate=1.0,
            repair_cost_per_failure=0.0,
            engineering_hours_per_month=0,
            engineer_hourly_cost=0,
            cache_hit_rate=0.8,
        )
        pricing = ProviderPricing(
            name="Test Provider",
            input_rate_per_m=5.00,
            output_rate_per_m=25.00,
            deployment_mode="closed_api",
            cached_input_rate_per_m=0.50,
        )

        result_no_cache = compute_lcpr(profile_no_cache, pricing)
        result_cached = compute_lcpr(profile_cached, pricing)

        assert result_cached.lcpr < result_no_cache.lcpr

    def test_cache_hit_rate_no_effect_without_cached_rate(self):
        """If provider has no cached rate, cache_hit_rate has no effect on LCPR."""
        profile_no_cache = WorkloadProfile(
            avg_input_tokens=2000,
            avg_output_tokens=200,
            monthly_requests=100_000,
            retry_rate=0.0,
            quality_gate_pass_rate=1.0,
            repair_cost_per_failure=0.0,
            engineering_hours_per_month=0,
            engineer_hourly_cost=0,
        )
        profile_cached = WorkloadProfile(
            avg_input_tokens=2000,
            avg_output_tokens=200,
            monthly_requests=100_000,
            retry_rate=0.0,
            quality_gate_pass_rate=1.0,
            repair_cost_per_failure=0.0,
            engineering_hours_per_month=0,
            engineer_hourly_cost=0,
            cache_hit_rate=0.8,
        )
        pricing = ProviderPricing(
            name="No Cache Provider",
            input_rate_per_m=5.00,
            output_rate_per_m=25.00,
            deployment_mode="closed_api",
            # no cached_input_rate_per_m — defaults to 0.0
        )

        result_no_cache = compute_lcpr(profile_no_cache, pricing)
        result_cached = compute_lcpr(profile_cached, pricing)

        assert math.isclose(result_cached.lcpr, result_no_cache.lcpr, rel_tol=1e-9)

    def test_cache_hit_rate_zero_is_default(self):
        """Default cache_hit_rate=0.0 should produce the same result as before."""
        profile = WorkloadProfile(
            avg_input_tokens=2000,
            avg_output_tokens=200,
            monthly_requests=100_000,
            retry_rate=0.0,
            quality_gate_pass_rate=1.0,
            repair_cost_per_failure=0.0,
            engineering_hours_per_month=0,
            engineer_hourly_cost=0,
        )
        pricing_with_cache_rate = ProviderPricing(
            name="Has Cache Rate",
            input_rate_per_m=5.00,
            output_rate_per_m=25.00,
            deployment_mode="closed_api",
            cached_input_rate_per_m=0.50,
        )
        pricing_without = ProviderPricing(
            name="No Cache Rate",
            input_rate_per_m=5.00,
            output_rate_per_m=25.00,
            deployment_mode="closed_api",
        )

        # Default cache_hit_rate is 0.0, so both should be the same
        result_with = compute_lcpr(profile, pricing_with_cache_rate)
        result_without = compute_lcpr(profile, pricing_without)

        assert math.isclose(result_with.lcpr, result_without.lcpr, rel_tol=1e-9)


# --- Batch Eligible Fraction Tests ---


class TestBatchFraction:
    """Tests for batch_eligible_fraction support in LCPR calculation."""

    def test_batch_fraction_reduces_lcpr(self):
        """batch_eligible_fraction=0.5 with batch rates should produce lower LCPR."""
        profile_no_batch = WorkloadProfile(
            avg_input_tokens=2000,
            avg_output_tokens=500,
            monthly_requests=100_000,
            retry_rate=0.0,
            quality_gate_pass_rate=1.0,
            repair_cost_per_failure=0.0,
            engineering_hours_per_month=0,
            engineer_hourly_cost=0,
        )
        profile_batch = WorkloadProfile(
            avg_input_tokens=2000,
            avg_output_tokens=500,
            monthly_requests=100_000,
            retry_rate=0.0,
            quality_gate_pass_rate=1.0,
            repair_cost_per_failure=0.0,
            engineering_hours_per_month=0,
            engineer_hourly_cost=0,
            batch_eligible_fraction=0.5,
        )
        pricing = ProviderPricing(
            name="Batch Provider",
            input_rate_per_m=5.00,
            output_rate_per_m=30.00,
            deployment_mode="closed_api",
            batch_input_rate_per_m=2.50,
            batch_output_rate_per_m=15.00,
        )

        result_no_batch = compute_lcpr(profile_no_batch, pricing)
        result_batch = compute_lcpr(profile_batch, pricing)

        assert result_batch.lcpr < result_no_batch.lcpr

    def test_batch_fraction_zero_is_default(self):
        """Default batch_eligible_fraction=0.0 produces same result as before."""
        profile = WorkloadProfile(
            avg_input_tokens=2000,
            avg_output_tokens=500,
            monthly_requests=100_000,
            retry_rate=0.0,
            quality_gate_pass_rate=1.0,
            repair_cost_per_failure=0.0,
            engineering_hours_per_month=0,
            engineer_hourly_cost=0,
        )
        pricing_with_batch = ProviderPricing(
            name="Has Batch Rate",
            input_rate_per_m=5.00,
            output_rate_per_m=30.00,
            deployment_mode="closed_api",
            batch_input_rate_per_m=2.50,
            batch_output_rate_per_m=15.00,
        )
        pricing_without = ProviderPricing(
            name="No Batch Rate",
            input_rate_per_m=5.00,
            output_rate_per_m=30.00,
            deployment_mode="closed_api",
        )

        result_with = compute_lcpr(profile, pricing_with_batch)
        result_without = compute_lcpr(profile, pricing_without)

        assert math.isclose(result_with.lcpr, result_without.lcpr, rel_tol=1e-9)


# --- Prefill Efficiency Tests ---


class TestPrefillEfficiency:
    """Tests for prefill_efficiency support in dedicated GPU LCPR."""

    def test_prefill_efficiency_increases_dedicated_cost(self):
        """prefill_efficiency=0.1 should make dedicated LCPR higher for input-heavy workloads.

        We use a high volume so the prefill overhead pushes past the GPU capacity
        boundary (1 GPU capacity ~1.55B tokens/month at 600 effective tps).
        Without prefill: 200 * 10M = 2B output tokens (needs 2 GPUs).
        With prefill 0.1: 2B + 5000 * 10M * 0.1 = 2B + 5B = 7B (needs 5 GPUs).
        """
        profile_no_prefill = WorkloadProfile(
            avg_input_tokens=5000,
            avg_output_tokens=200,
            monthly_requests=10_000_000,
            retry_rate=0.0,
            quality_gate_pass_rate=1.0,
            repair_cost_per_failure=0.0,
            engineering_hours_per_month=0,
            engineer_hourly_cost=0,
        )
        profile_prefill = WorkloadProfile(
            avg_input_tokens=5000,
            avg_output_tokens=200,
            monthly_requests=10_000_000,
            retry_rate=0.0,
            quality_gate_pass_rate=1.0,
            repair_cost_per_failure=0.0,
            engineering_hours_per_month=0,
            engineer_hourly_cost=0,
            prefill_efficiency=0.1,
        )
        pricing = ProviderPricing(
            name="Dedicated GPU",
            input_rate_per_m=0.0,
            output_rate_per_m=0.0,
            deployment_mode="dedicated",
            gpu_hourly_rate=2.99,
            throughput_tps=1500,
            utilization=0.40,
        )

        result_no_prefill = compute_lcpr(profile_no_prefill, pricing)
        result_prefill = compute_lcpr(profile_prefill, pricing)

        # With prefill_efficiency > 0, effective output tokens increase
        # so more GPUs are needed, making LCPR higher
        assert result_prefill.lcpr > result_no_prefill.lcpr

    def test_prefill_efficiency_zero_is_default(self):
        """Default prefill_efficiency=0.0 produces same result as before."""
        profile = WorkloadProfile(
            avg_input_tokens=5000,
            avg_output_tokens=200,
            monthly_requests=1_000_000,
            retry_rate=0.0,
            quality_gate_pass_rate=1.0,
            repair_cost_per_failure=0.0,
            engineering_hours_per_month=0,
            engineer_hourly_cost=0,
        )
        pricing = ProviderPricing(
            name="Dedicated GPU",
            input_rate_per_m=0.0,
            output_rate_per_m=0.0,
            deployment_mode="dedicated",
            gpu_hourly_rate=2.99,
            throughput_tps=1500,
            utilization=0.40,
        )

        result = compute_lcpr(profile, pricing)

        # Should be exactly the same as before (no prefill contribution)
        # Just verify it produces a finite, positive result
        assert result.lcpr > 0
        assert math.isfinite(result.lcpr)


# --- YAML Data Integrity Tests ---


class TestYAMLDataIntegrity:
    """Tests for specific pricing data corrections in provider_pricing.yaml."""

    def test_deepinfra_asymmetric_pricing(self):
        """DeepInfra GPT-OSS-120B should have asymmetric pricing (input != output)."""
        pricing_path = Path(__file__).parent.parent / "provider_pricing.yaml"
        providers = load_provider_pricing(pricing_path)

        deepinfra = [p for p in providers if "DeepInfra" in p.name]
        assert len(deepinfra) > 0, "DeepInfra provider not found in YAML"

        di = deepinfra[0]
        # [PUBLIC_PRICING] deepinfra.com/openai/gpt-oss-120b — verified 2026-05-12
        assert di.input_rate_per_m == pytest.approx(0.039), (
            f"DeepInfra input rate should be $0.039/M, got {di.input_rate_per_m}"
        )
        assert di.output_rate_per_m == pytest.approx(0.19), (
            f"DeepInfra output rate should be $0.19/M, got {di.output_rate_per_m}"
        )
        # Asymmetric: output should be ~4.87x input
        assert di.output_rate_per_m > di.input_rate_per_m

    def test_workload_profile_repair_costs(self):
        """saas_chat and code_completion repair_cost_per_failure should be 0.002."""
        from calculator.workload_profiles import PROFILES

        assert PROFILES["saas_chat"].repair_cost_per_failure == 0.002
        assert PROFILES["code_completion"].repair_cost_per_failure == 0.002


# --- WorkloadProfile Validation Tests ---


class TestWorkloadProfileValidation:
    """Tests that WorkloadProfile rejects invalid inputs at construction time."""

    def _base_kwargs(self):
        """Valid kwargs to override in individual tests."""
        return dict(
            avg_input_tokens=500,
            avg_output_tokens=200,
            monthly_requests=100_000,
            retry_rate=0.05,
            quality_gate_pass_rate=0.95,
            repair_cost_per_failure=0.002,
            engineering_hours_per_month=10,
            engineer_hourly_cost=100,
        )

    def test_negative_input_tokens_rejected(self):
        kwargs = self._base_kwargs()
        kwargs["avg_input_tokens"] = -1
        with pytest.raises(ValueError, match="avg_input_tokens"):
            WorkloadProfile(**kwargs)

    def test_negative_output_tokens_rejected(self):
        kwargs = self._base_kwargs()
        kwargs["avg_output_tokens"] = -1
        with pytest.raises(ValueError, match="avg_output_tokens"):
            WorkloadProfile(**kwargs)

    def test_negative_monthly_requests_rejected(self):
        kwargs = self._base_kwargs()
        kwargs["monthly_requests"] = -1
        with pytest.raises(ValueError, match="monthly_requests"):
            WorkloadProfile(**kwargs)

    def test_retry_rate_above_one_rejected(self):
        kwargs = self._base_kwargs()
        kwargs["retry_rate"] = 1.5
        with pytest.raises(ValueError, match="retry_rate"):
            WorkloadProfile(**kwargs)

    def test_retry_rate_negative_rejected(self):
        kwargs = self._base_kwargs()
        kwargs["retry_rate"] = -0.1
        with pytest.raises(ValueError, match="retry_rate"):
            WorkloadProfile(**kwargs)

    def test_quality_gate_above_one_rejected(self):
        kwargs = self._base_kwargs()
        kwargs["quality_gate_pass_rate"] = 1.1
        with pytest.raises(ValueError, match="quality_gate_pass_rate"):
            WorkloadProfile(**kwargs)

    def test_quality_gate_negative_rejected(self):
        kwargs = self._base_kwargs()
        kwargs["quality_gate_pass_rate"] = -0.1
        with pytest.raises(ValueError, match="quality_gate_pass_rate"):
            WorkloadProfile(**kwargs)

    def test_cache_hit_rate_above_one_rejected(self):
        kwargs = self._base_kwargs()
        kwargs["cache_hit_rate"] = 1.5
        with pytest.raises(ValueError, match="cache_hit_rate"):
            WorkloadProfile(**kwargs)

    def test_batch_fraction_above_one_rejected(self):
        kwargs = self._base_kwargs()
        kwargs["batch_eligible_fraction"] = 2.0
        with pytest.raises(ValueError, match="batch_eligible_fraction"):
            WorkloadProfile(**kwargs)

    def test_prefill_efficiency_above_one_rejected(self):
        kwargs = self._base_kwargs()
        kwargs["prefill_efficiency"] = 1.5
        with pytest.raises(ValueError, match="prefill_efficiency"):
            WorkloadProfile(**kwargs)

    def test_negative_repair_cost_rejected(self):
        kwargs = self._base_kwargs()
        kwargs["repair_cost_per_failure"] = -0.01
        with pytest.raises(ValueError, match="repair_cost_per_failure"):
            WorkloadProfile(**kwargs)

    def test_negative_engineering_hours_rejected(self):
        kwargs = self._base_kwargs()
        kwargs["engineering_hours_per_month"] = -5
        with pytest.raises(ValueError, match="engineering_hours_per_month"):
            WorkloadProfile(**kwargs)

    def test_negative_engineer_hourly_cost_rejected(self):
        kwargs = self._base_kwargs()
        kwargs["engineer_hourly_cost"] = -100
        with pytest.raises(ValueError, match="engineer_hourly_cost"):
            WorkloadProfile(**kwargs)

    def test_valid_profile_accepted(self):
        """A valid profile should construct without error."""
        profile = WorkloadProfile(**self._base_kwargs())
        assert profile.avg_input_tokens == 500

    def test_zero_values_accepted(self):
        """Zero tokens, zero requests, zero rates should all be valid."""
        profile = WorkloadProfile(
            avg_input_tokens=0,
            avg_output_tokens=0,
            monthly_requests=0,
            retry_rate=0.0,
            quality_gate_pass_rate=0.01,  # must be > 0 for division
            repair_cost_per_failure=0.0,
            engineering_hours_per_month=0,
            engineer_hourly_cost=0,
        )
        assert profile.monthly_requests == 0

    def test_boundary_rate_one_accepted(self):
        """Rate values at exactly 1.0 should be valid."""
        kwargs = self._base_kwargs()
        kwargs["retry_rate"] = 1.0
        kwargs["quality_gate_pass_rate"] = 1.0
        kwargs["cache_hit_rate"] = 1.0
        kwargs["batch_eligible_fraction"] = 1.0
        kwargs["prefill_efficiency"] = 1.0
        profile = WorkloadProfile(**kwargs)
        assert profile.retry_rate == 1.0


# --- YAML Schema Validation Tests ---


class TestYAMLSchemaValidation:
    """Tests that load_provider_pricing rejects malformed YAML data."""

    def test_empty_yaml_returns_empty_list(self, tmp_path):
        """An empty YAML file should return an empty provider list, not crash."""
        yaml_file = tmp_path / "empty.yaml"
        yaml_file.write_text("")
        providers = load_provider_pricing(yaml_file)
        assert providers == []

    def test_negative_input_rate_rejected(self, tmp_path):
        """Negative input rates should raise ValueError."""
        yaml_file = tmp_path / "bad.yaml"
        yaml_file.write_text("""
closed_apis:
  bad_provider:
    name: "Bad"
    models:
      bad_model:
        name: "Bad Model"
        input_rate: -1.0
        output_rate: 5.0
""")
        with pytest.raises(ValueError, match="negative.*rate"):
            load_provider_pricing(yaml_file)

    def test_negative_output_rate_rejected(self, tmp_path):
        """Negative output rates should raise ValueError."""
        yaml_file = tmp_path / "bad.yaml"
        yaml_file.write_text("""
serverless_open:
  bad_provider:
    name: "Bad"
    models:
      bad_model:
        name: "Bad Model"
        input_rate: 1.0
        output_rate: -5.0
""")
        with pytest.raises(ValueError, match="negative.*rate"):
            load_provider_pricing(yaml_file)

    def test_negative_gpu_hourly_rate_rejected(self, tmp_path):
        """Negative GPU hourly rates should raise ValueError."""
        yaml_file = tmp_path / "bad.yaml"
        yaml_file.write_text("""
dedicated_gpu:
  bad_provider:
    name: "Bad"
    gpus:
      bad_gpu:
        name: "Bad GPU"
        hourly_rate: -2.99
""")
        with pytest.raises(ValueError, match="negative.*rate"):
            load_provider_pricing(yaml_file)

    def test_missing_model_name_rejected(self, tmp_path):
        """Models without a name field should raise ValueError."""
        yaml_file = tmp_path / "bad.yaml"
        yaml_file.write_text("""
closed_apis:
  provider:
    name: "Provider"
    models:
      model1:
        input_rate: 5.0
        output_rate: 30.0
""")
        with pytest.raises(ValueError, match="missing.*name"):
            load_provider_pricing(yaml_file)

    def test_null_rate_treated_as_zero(self, tmp_path):
        """Null/missing rates in optional fields should default to 0, not crash."""
        yaml_file = tmp_path / "ok.yaml"
        yaml_file.write_text("""
serverless_open:
  provider:
    name: "Provider"
    models:
      model1:
        name: "Model"
        input_rate: 1.0
        output_rate: 2.0
        cached_input_rate:
""")
        providers = load_provider_pricing(yaml_file)
        assert len(providers) == 1
        assert providers[0].cached_input_rate_per_m == 0.0


# --- Pricing Freshness Tests ---
# These tests pin YAML values to verified public pricing pages.
# If a test fails, the YAML is stale and needs a re-check.


class TestPricingFreshness:
    """Pin provider_pricing.yaml to verified public prices.

    Every assertion here corresponds to a specific vendor pricing page
    checked on 2026-05-12. When prices change upstream, update BOTH
    the YAML and the expected values here with the new source date.
    """

    @pytest.fixture
    def providers(self):
        pricing_path = Path(__file__).parent.parent / "provider_pricing.yaml"
        return load_provider_pricing(pricing_path)

    def _find(self, providers, substring):
        matches = [p for p in providers if substring in p.name]
        assert len(matches) > 0, f"No provider matching '{substring}' found in YAML"
        return matches[0]

    def test_openai_gpt55_rates(self, providers):
        """[PUBLIC_PRICING] openai.com/api/pricing — verified 2026-05-12."""
        gpt55 = self._find(providers, "GPT-5.5")
        assert gpt55.input_rate_per_m == pytest.approx(5.00)
        assert gpt55.output_rate_per_m == pytest.approx(30.00)

    def test_openai_gpt55_cached_input(self, providers):
        """[PUBLIC_PRICING] openai.com/api/pricing — verified 2026-05-12.
        Cached input is $0.50/M (90% discount), not $2.50/M (50% discount)."""
        gpt55 = self._find(providers, "GPT-5.5")
        assert gpt55.cached_input_rate_per_m == pytest.approx(0.50), (
            f"GPT-5.5 cached input should be $0.50/M, got ${gpt55.cached_input_rate_per_m}"
        )

    def test_together_deepseek_v3_rates(self, providers):
        """[PUBLIC_PRICING] together.ai/pricing — verified 2026-05-12.
        DeepSeek V3.1 is $0.60/M input, $1.70/M output (asymmetric)."""
        dsv3 = self._find(providers, "DeepSeek")
        assert dsv3.input_rate_per_m == pytest.approx(0.60), (
            f"Together DeepSeek V3 input should be $0.60/M, got ${dsv3.input_rate_per_m}"
        )
        assert dsv3.output_rate_per_m == pytest.approx(1.70), (
            f"Together DeepSeek V3 output should be $1.70/M, got ${dsv3.output_rate_per_m}"
        )

    def test_deepinfra_gpt_oss_120b_rates(self, providers):
        """[PUBLIC_PRICING] deepinfra.com/openai/gpt-oss-120b — verified 2026-05-12."""
        di = self._find(providers, "DeepInfra")
        assert di.input_rate_per_m == pytest.approx(0.039), (
            f"DeepInfra input should be $0.039/M, got ${di.input_rate_per_m}"
        )
        assert di.output_rate_per_m == pytest.approx(0.19), (
            f"DeepInfra output should be $0.19/M, got ${di.output_rate_per_m}"
        )

    def test_lambda_h100_hourly_rate(self, providers):
        """[PUBLIC] lambda.ai/pricing — verified 2026-05-13.
        H100 SXM 80GB on-demand is $4.29/hr (1x GPU)."""
        lambda_gpu = self._find(providers, "Lambda")
        assert lambda_gpu.gpu_hourly_rate == pytest.approx(4.29), (
            f"Lambda H100 should be $4.29/hr, got ${lambda_gpu.gpu_hourly_rate}"
        )


# --- Break-Even Capacity-Aware Tests ---


class TestBreakEvenCapacityAware:
    """Tests for the capacity-aware break-even model.

    The old model had a bug: it divided break-even by utilization when
    one GPU couldn't reach the theoretical volume, but still returned
    one-GPU daily cost. The correct model reports whether break-even
    is feasible at the given utilization and computes effective $/M.
    """

    def test_no_break_even_when_dedicated_rate_exceeds_serverless(self):
        """At $3.99/hr, 40% util, 1500 tok/s vs $1.70/M serverless:
        effective dedicated rate = $3.99*24 / (1500*0.4*86400/1M) = $1.848/M.
        Since $1.848 > $1.70, dedicated is always more expensive — no break-even."""
        serverless = ProviderPricing(
            name="Together DeepSeek V3",
            input_rate_per_m=0.60,
            output_rate_per_m=1.70,
            deployment_mode="serverless_open",
        )
        dedicated = ProviderPricing(
            name="Lambda H100",
            input_rate_per_m=0.0,
            output_rate_per_m=0.0,
            deployment_mode="dedicated",
            gpu_hourly_rate=3.99,
            throughput_tps=1500,
            utilization=0.40,
        )
        result = compute_break_even(serverless, dedicated)
        # Break-even should NOT be feasible at this utilization
        assert not result.break_even_feasible, (
            f"Expected no break-even: effective dedicated $/M ({result.effective_cost_per_m:.3f}) "
            f"> serverless $/M ($1.70)"
        )
        # Effective cost per M should be reported
        assert result.effective_cost_per_m > 1.70
        # Required utilization should be above the stated utilization
        assert result.required_utilization > 0.40

    def test_break_even_feasible_at_high_utilization(self):
        """At $3.99/hr and 60% utilization, effective rate = $3.99*24 / (1500*0.6*86400/1M)
        = $95.76 / 77.76 = $1.231/M. Since $1.231 < $1.70, break-even IS feasible."""
        serverless = ProviderPricing(
            name="Together DeepSeek V3",
            input_rate_per_m=0.60,
            output_rate_per_m=1.70,
            deployment_mode="serverless_open",
        )
        dedicated = ProviderPricing(
            name="Lambda H100",
            input_rate_per_m=0.0,
            output_rate_per_m=0.0,
            deployment_mode="dedicated",
            gpu_hourly_rate=3.99,
            throughput_tps=1500,
            utilization=0.60,
        )
        result = compute_break_even(serverless, dedicated)
        assert result.break_even_feasible, (
            f"Expected break-even feasible: effective $/M ({result.effective_cost_per_m:.3f}) "
            f"< serverless $1.70/M"
        )
        assert result.effective_cost_per_m < 1.70

    def test_required_utilization_reported(self):
        """Required utilization to break even at $3.99/hr vs $1.70/M should be ~43.5%."""
        serverless = ProviderPricing(
            name="Together DeepSeek V3",
            input_rate_per_m=0.60,
            output_rate_per_m=1.70,
            deployment_mode="serverless_open",
        )
        dedicated = ProviderPricing(
            name="Lambda H100",
            input_rate_per_m=0.0,
            output_rate_per_m=0.0,
            deployment_mode="dedicated",
            gpu_hourly_rate=3.99,
            throughput_tps=1500,
            utilization=0.40,
        )
        result = compute_break_even(serverless, dedicated)
        # required_utilization = (gpu_cost_per_day / serverless_rate) / (tps * 86400)
        # = (95.76 / 0.0000017) / (1500 * 86400) = 56_329_412 / 129_600_000 = 0.4347
        assert 0.42 < result.required_utilization < 0.46, (
            f"Expected required utilization ~0.435, got {result.required_utilization:.3f}"
        )

    def test_effective_capacity_tokens_per_day(self):
        """At 1500 tok/s and 40% utilization: 1500 * 0.4 * 86400 = 51.84M tokens/day."""
        serverless = ProviderPricing(
            name="Together DeepSeek V3",
            input_rate_per_m=0.60,
            output_rate_per_m=1.70,
            deployment_mode="serverless_open",
        )
        dedicated = ProviderPricing(
            name="Lambda H100",
            input_rate_per_m=0.0,
            output_rate_per_m=0.0,
            deployment_mode="dedicated",
            gpu_hourly_rate=3.99,
            throughput_tps=1500,
            utilization=0.40,
        )
        result = compute_break_even(serverless, dedicated)
        expected_capacity = 1500 * 0.40 * 86400
        assert math.isclose(
            result.effective_capacity_tokens_per_day,
            expected_capacity,
            rel_tol=0.001,
        )


class TestQualityAdjustedLCPR:
    """Test that quality_score on ProviderPricing adjusts effective quality gate."""

    def test_quality_score_one_has_no_effect(self, simple_profile, openai_pricing):
        """quality_score=1.0 should produce identical LCPR to no quality_score."""
        baseline = compute_lcpr(simple_profile, openai_pricing)
        scored = compute_lcpr(simple_profile, ProviderPricing(
            name="OpenAI GPT-5.5",
            input_rate_per_m=5.00,
            output_rate_per_m=30.00,
            deployment_mode="closed_api",
            quality_score=1.0,
        ))
        assert math.isclose(baseline.lcpr, scored.lcpr, rel_tol=0.001)

    def test_quality_score_below_one_increases_lcpr(self, simple_profile):
        """Lower quality_score means more quality gate failures, higher LCPR."""
        high_quality = ProviderPricing(
            name="High Quality",
            input_rate_per_m=0.60,
            output_rate_per_m=1.70,
            deployment_mode="serverless_open",
            quality_score=1.0,
        )
        low_quality = ProviderPricing(
            name="Low Quality",
            input_rate_per_m=0.60,
            output_rate_per_m=1.70,
            deployment_mode="serverless_open",
            quality_score=0.8,
        )
        r_high = compute_lcpr(simple_profile, high_quality)
        r_low = compute_lcpr(simple_profile, low_quality)
        assert r_low.lcpr > r_high.lcpr

    def test_quality_score_zero_raises(self, simple_profile):
        """quality_score=0.0 would zero out quality gate; should raise."""
        zero_quality = ProviderPricing(
            name="Zero Quality",
            input_rate_per_m=0.60,
            output_rate_per_m=1.70,
            deployment_mode="serverless_open",
            quality_score=0.0,
        )
        with pytest.raises(ValueError):
            compute_lcpr(simple_profile, zero_quality)

    def test_quality_score_affects_dedicated_mode(self):
        """quality_score should also affect dedicated LCPR calculations."""
        profile = WorkloadProfile(
            avg_input_tokens=500,
            avg_output_tokens=200,
            monthly_requests=5_000_000,
            retry_rate=0.05,
            quality_gate_pass_rate=0.95,
            repair_cost_per_failure=0.002,
            engineering_hours_per_month=40,
            engineer_hourly_cost=100,
        )
        good_gpu = ProviderPricing(
            name="Good GPU",
            input_rate_per_m=0.0,
            output_rate_per_m=0.0,
            deployment_mode="dedicated",
            gpu_hourly_rate=3.99,
            throughput_tps=1500,
            utilization=0.40,
            quality_score=1.0,
        )
        weak_gpu = ProviderPricing(
            name="Weak GPU",
            input_rate_per_m=0.0,
            output_rate_per_m=0.0,
            deployment_mode="dedicated",
            gpu_hourly_rate=3.99,
            throughput_tps=1500,
            utilization=0.40,
            quality_score=0.85,
        )
        r_good = compute_lcpr(profile, good_gpu)
        r_weak = compute_lcpr(profile, weak_gpu)
        assert r_weak.lcpr > r_good.lcpr
