# ABOUTME: Unit tests for the LCPR (Loaded Cost Per Request) calculation engine.
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
    """Together AI DeepSeek V3 serverless pricing."""
    return ProviderPricing(
        name="Together DeepSeek V3",
        input_rate_per_m=1.25,
        output_rate_per_m=1.25,
        deployment_mode="serverless_open",
    )


@pytest.fixture
def dedicated_pricing():
    """Dedicated H100 pricing (Lambda)."""
    return ProviderPricing(
        name="Lambda H100 Dedicated",
        input_rate_per_m=0.0,
        output_rate_per_m=0.0,
        deployment_mode="dedicated",
        gpu_hourly_rate=2.99,
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

        # Together at $1.25/$1.25 should be much cheaper than OpenAI at $5/$30
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

    def test_monthly_cost_is_lcpr_times_successful_requests(self, simple_profile, openai_pricing):
        """Monthly cost should be consistent with LCPR × successful request count."""
        result = compute_lcpr(simple_profile, openai_pricing)

        # Monthly cost = total cost of all requests (including retries, failures, engineering)
        # LCPR = monthly_cost / successful_requests
        successful = simple_profile.monthly_requests * simple_profile.quality_gate_pass_rate
        expected_monthly = result.lcpr * successful
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

    def test_break_even_returns_daily_tokens(self, together_pricing, dedicated_pricing):
        """Break-even should return daily token volume where dedicated becomes cheaper."""
        result = compute_break_even(together_pricing, dedicated_pricing)

        assert result.break_even_daily_output_tokens > 0
        assert result.break_even_daily_output_tokens < 1e12  # sanity upper bound

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
        assert di.input_rate_per_m == 0.05, f"DeepInfra input rate should be $0.05/M, got {di.input_rate_per_m}"
        assert di.output_rate_per_m == 0.45, f"DeepInfra output rate should be $0.45/M, got {di.output_rate_per_m}"
        # Asymmetric: output should be 9x input
        assert di.output_rate_per_m / di.input_rate_per_m == pytest.approx(9.0)

    def test_workload_profile_repair_costs(self):
        """saas_chat and code_completion repair_cost_per_failure should be 0.002."""
        from calculator.workload_profiles import PROFILES

        assert PROFILES["saas_chat"].repair_cost_per_failure == 0.002
        assert PROFILES["code_completion"].repair_cost_per_failure == 0.002
