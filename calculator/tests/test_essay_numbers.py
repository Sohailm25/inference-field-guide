# ABOUTME: Verification tests for worked examples that will appear in the essay.
# ABOUTME: Ensures calculator output matches claims in the Inference Field Guide.

import math

import pytest

from calculator.lcpr import (
    ProviderPricing,
    WorkloadProfile,
    compute_break_even,
    compute_lcpr,
)

# --- Essay Part 0: The Cost Illusion ---
# Worked example using real May 2026 pricing.
# Profile: generic SaaS workload, 500K requests/month.


@pytest.fixture
def essay_workload():
    """The essay's primary worked example: a mid-scale SaaS workload."""
    return WorkloadProfile(
        avg_input_tokens=800,
        avg_output_tokens=400,
        monthly_requests=500_000,
        retry_rate=0.03,
        quality_gate_pass_rate=0.95,
        repair_cost_per_failure=0.001,
        engineering_hours_per_month=8,
        engineer_hourly_cost=100,
    )


@pytest.fixture
def gpt55():
    """GPT-5.5: $5.00/$30.00 per M input/output tokens [PUBLIC]."""
    return ProviderPricing(
        name="OpenAI GPT-5.5",
        input_rate_per_m=5.00,
        output_rate_per_m=30.00,
        deployment_mode="closed_api",
    )


@pytest.fixture
def together_dsv3():
    """Together DeepSeek V3 serverless: $0.60/$1.70 per M.
    [PUBLIC_PRICING] together.ai/pricing — verified 2026-05-12."""
    return ProviderPricing(
        name="Together DeepSeek V3",
        input_rate_per_m=0.60,
        output_rate_per_m=1.70,
        deployment_mode="serverless_open",
    )


@pytest.fixture
def lambda_h100():
    """Lambda H100 dedicated: $3.99/hr, 1500 tok/s theoretical, 40% util.
    [PUBLIC_PRICING] lambda.ai/pricing — verified 2026-05-12."""
    return ProviderPricing(
        name="Lambda H100",
        input_rate_per_m=0.0,
        output_rate_per_m=0.0,
        deployment_mode="dedicated",
        gpu_hourly_rate=3.99,
        throughput_tps=1500,
        utilization=0.40,
    )


class TestEssayPart0CostIllusion:
    """Verify the essay's Cost Illusion worked example."""

    def test_gpt55_lcpr_range(self, essay_workload, gpt55):
        """GPT-5.5 LCPR should be in the range cited in the essay."""
        result = compute_lcpr(essay_workload, gpt55)
        # At $5/$30 with 800 input, 400 output tokens:
        # Raw token cost per request = (800*5/1M) + (400*30/1M) = 0.004 + 0.012 = $0.016
        # With retries, quality gate, engineering overhead → ~$0.017-$0.020
        assert 0.015 < result.lcpr < 0.025

    def test_together_lcpr_range(self, essay_workload, together_dsv3):
        """Together DeepSeek V3 LCPR should be dramatically cheaper than GPT-5.5."""
        result = compute_lcpr(essay_workload, together_dsv3)
        # At $0.60/$1.70: raw = (800*0.60/1M) + (400*1.70/1M) = 0.00048 + 0.00068 = $0.00116
        # With overhead → ~$0.003-$0.005
        assert 0.002 < result.lcpr < 0.006

    def test_gpt55_vs_together_ratio(self, essay_workload, gpt55, together_dsv3):
        """Essay claims open-weights is 5-10x cheaper at LCPR level
        (10-150x on raw token cost). Verify this pair falls in range."""
        gpt_result = compute_lcpr(essay_workload, gpt55)
        together_result = compute_lcpr(essay_workload, together_dsv3)
        ratio = gpt_result.lcpr / together_result.lcpr
        # LCPR ratio: 5-10x (engineering overhead compresses the raw token ratio)
        assert ratio > 3.0, f"Expected >3x ratio, got {ratio:.1f}x"
        assert ratio < 15.0, f"Unexpectedly high ratio: {ratio:.1f}x"

    def test_dedicated_lcpr_range(self, essay_workload, lambda_h100):
        """Dedicated H100 at this volume — should be more expensive than serverless
        (500K req × 400 output tokens = 200M tokens/month, not enough to justify dedicated)."""
        result = compute_lcpr(essay_workload, lambda_h100)
        # GPU cost is fixed at $3.99*24*30 = $2,872.80/month regardless of volume
        # At 500K requests that's ~$0.006-$0.008 per successful request
        assert result.lcpr > 0
        assert result.monthly_cost > 2800  # At minimum the GPU cost


class TestEssayPart1MigrationGate:
    """Verify migration gate thresholds from the essay.

    Essay claims:
    - Under ~$10K/month: stay on closed APIs
    - $10K-$100K/month: add serverless open for long-tail
    - Break-even for dedicated: ~50M output tokens/day at full util,
      ~130-180M at 30-40% real utilization (provider-dependent)
    """

    def test_low_spend_stays_closed(self, gpt55, together_dsv3):
        """At <$10K/month spend on GPT-5.5, switching to Together still saves money
        but the absolute savings may not justify the migration effort."""
        low_volume = WorkloadProfile(
            avg_input_tokens=800,
            avg_output_tokens=400,
            monthly_requests=100_000,  # low volume
            retry_rate=0.03,
            quality_gate_pass_rate=0.95,
            repair_cost_per_failure=0.001,
            engineering_hours_per_month=4,
            engineer_hourly_cost=100,
        )
        gpt_result = compute_lcpr(low_volume, gpt55)
        together_result = compute_lcpr(low_volume, together_dsv3)
        # GPT-5.5 monthly cost should be under $10K at this volume
        assert gpt_result.monthly_cost < 10_000
        # Together is still cheaper
        assert together_result.monthly_cost < gpt_result.monthly_cost

    def test_break_even_infeasible_at_40pct_utilization(self, together_dsv3, lambda_h100):
        """At $3.99/hr, 40% util vs $1.70/M serverless — effective dedicated rate
        ($1.848/M) exceeds serverless, so break-even is not feasible on one GPU."""
        result = compute_break_even(together_dsv3, lambda_h100)
        assert not result.break_even_feasible, (
            f"Expected no break-even: effective $/M ({result.effective_cost_per_m:.3f}) "
            f"> serverless $1.70/M"
        )
        # Required utilization to break even should be ~43.5%
        assert result.required_utilization > 0.40

    def test_break_even_feasible_at_50pct_utilization(self, together_dsv3):
        """At $3.99/hr, 50% util vs $1.70/M — effective rate ($1.478/M) is below
        serverless, so break-even IS feasible. Volume ~56M tokens/day."""
        h100_50pct = ProviderPricing(
            name="Lambda H100 (50% util)",
            input_rate_per_m=0.0,
            output_rate_per_m=0.0,
            deployment_mode="dedicated",
            gpu_hourly_rate=3.99,
            throughput_tps=1500,
            utilization=0.50,
        )
        result = compute_break_even(together_dsv3, h100_50pct)
        assert result.break_even_feasible
        daily_tokens = result.break_even_daily_output_tokens
        assert daily_tokens > 10_000_000, f"Break-even too low: {daily_tokens:,.0f}"
        assert daily_tokens < 200_000_000, f"Break-even too high: {daily_tokens:,.0f}"

    def test_fireworks_break_even_at_full_util(self):
        """H100 at $2.01/hr vs Fireworks $0.90/M serverless: break-even is
        ~53.6M tokens/day at full utilization. At 30-40% real utilization,
        effective break-even is 2.5-3.3x higher (~134-179M tokens/day)."""
        fireworks_70b = ProviderPricing(
            name="Fireworks Llama 70B",
            input_rate_per_m=0.90,
            output_rate_per_m=0.90,
            deployment_mode="serverless_open",
        )
        cheap_h100 = ProviderPricing(
            name="Cheap H100",
            input_rate_per_m=0.0,
            output_rate_per_m=0.0,
            deployment_mode="dedicated",
            gpu_hourly_rate=2.01,
            throughput_tps=1500,
            utilization=1.0,  # theoretical max
        )
        result = compute_break_even(fireworks_70b, cheap_h100)
        # Theoretical: ($2.01 * 24) / ($0.90 / 1M) = $48.24 / $0.0000009 = 53.6M
        expected_theoretical = (2.01 * 24) / (0.90 / 1_000_000)
        assert math.isclose(
            result.break_even_daily_output_tokens, expected_theoretical, rel_tol=0.01
        ), (
            f"Expected ~{expected_theoretical / 1e6:.1f}M, "
            f"got {result.break_even_daily_output_tokens / 1e6:.1f}M"
        )


class TestEssayPart2MultiSource:
    """Verify multi-source cost comparisons cited in the essay.

    Essay cites:
    - Cresta: "thousands of LoRA adapters, 100x cost reduction vs GPT-4"
    - Decagon: "6x cost reduction per turn vs gpt-5 mini"
    """

    def test_multi_lora_cost_advantage(self):
        """Multi-LoRA at $0.20/M vs GPT-5.5 at $5/$30 — verify large gap exists."""
        multi_lora = ProviderPricing(
            name="Fireworks Multi-LoRA 8B",
            input_rate_per_m=0.20,
            output_rate_per_m=0.20,
            deployment_mode="serverless_open",
        )
        gpt55 = ProviderPricing(
            name="OpenAI GPT-5.5",
            input_rate_per_m=5.00,
            output_rate_per_m=30.00,
            deployment_mode="closed_api",
        )
        profile = WorkloadProfile(
            avg_input_tokens=500,
            avg_output_tokens=200,
            monthly_requests=1_000_000,
            retry_rate=0.02,
            quality_gate_pass_rate=0.95,
            repair_cost_per_failure=0.001,
            engineering_hours_per_month=10,
            engineer_hourly_cost=100,
        )
        lora_result = compute_lcpr(profile, multi_lora)
        gpt_result = compute_lcpr(profile, gpt55)
        ratio = gpt_result.lcpr / lora_result.lcpr
        # Token-level advantage is enormous but engineering overhead
        # dilutes the LCPR ratio. Essay's "100x" claim is pure token cost
        # vs GPT-4 — at LCPR level, expect 5-15x range.
        assert ratio > 5, f"Expected >5x, got {ratio:.1f}x"


class TestEssayPart3BuildBuy:
    """Verify build-buy economics from the essay.

    Essay's observability warning: median $123K/yr Datadog bill.
    Essay's GPU comparison: neo-cloud 40-85% cheaper than AWS/GCP.
    """

    def test_neo_cloud_vs_hyperscaler_savings(self):
        """Lambda at $3.99/hr vs AWS at $4.975/hr (per GPU) — verify savings %.
        Note: at corrected pricing, savings are ~20%, well below the essay's
        original "40-85%" claim. Essay needs correction in Phase 4/6."""
        lambda_rate = 3.99  # [PUBLIC_PRICING] lambda.ai/pricing — verified 2026-05-12
        aws_rate = 4.975  # p5e.48xlarge per-GPU
        savings_pct = (1 - lambda_rate / aws_rate) * 100
        # Corrected: Lambda is ~20% cheaper than AWS, not 40-85%
        assert savings_pct > 15, f"Savings only {savings_pct:.0f}%"
        assert savings_pct < 30, f"Savings {savings_pct:.0f}% seems too high"

    def test_dedicated_gpu_monthly_cost_range(self):
        """Verify monthly GPU costs are in the ranges cited."""
        # Lambda H100: $3.99/hr → ~$2,873/month
        # [PUBLIC_PRICING] lambda.ai/pricing — verified 2026-05-12
        lambda_monthly = 3.99 * 24 * 30
        assert 2800 < lambda_monthly < 2950

        # AWS per-GPU: $4.975/hr → ~$3,582/month
        aws_monthly = 4.975 * 24 * 30
        assert 3500 < aws_monthly < 3700

        # CoreWeave: $6.16/hr → ~$4,435/month
        cw_monthly = 6.16 * 24 * 30
        assert 4400 < cw_monthly < 4500


class TestEssayPart5StagedPlaybook:
    """Verify staged playbook thresholds.

    Stage 0: <$10K/month → single closed API
    Stage 1: $10K-$100K/month → add serverless open
    Stage 2: $100K-$1M/month → dedicated for high-volume workloads
    """

    def test_stage0_boundary(self, gpt55):
        """At $10K/month on GPT-5.5, verify the approximate request volume."""
        # Find request count that produces ~$10K monthly on GPT-5.5
        profile = WorkloadProfile(
            avg_input_tokens=800,
            avg_output_tokens=400,
            monthly_requests=500_000,
            retry_rate=0.03,
            quality_gate_pass_rate=0.95,
            repair_cost_per_failure=0.001,
            engineering_hours_per_month=8,
            engineer_hourly_cost=100,
        )
        result = compute_lcpr(profile, gpt55)
        # At 500K requests, GPT-5.5 monthly cost should be close to $10K
        # (gives readers a tangible sense of the boundary)
        assert 5_000 < result.monthly_cost < 15_000, (
            f"Expected ~$10K, got ${result.monthly_cost:,.0f}"
        )

    def test_utilization_revert_signal(self, together_dsv3, lambda_h100):
        """Essay: 'Dedicated GPU utilization consistently below 40% → move back to serverless.'
        Verify that at 20% utilization, dedicated is much worse."""
        low_util_gpu = ProviderPricing(
            name="Lambda H100 (underutilized)",
            input_rate_per_m=0.0,
            output_rate_per_m=0.0,
            deployment_mode="dedicated",
            gpu_hourly_rate=3.99,
            throughput_tps=1500,
            utilization=0.20,
        )
        # At moderate volume, low utilization means paying for idle GPU
        moderate_volume = WorkloadProfile(
            avg_input_tokens=500,
            avg_output_tokens=200,
            monthly_requests=1_000_000,
            retry_rate=0.02,
            quality_gate_pass_rate=0.98,
            repair_cost_per_failure=0.001,
            engineering_hours_per_month=20,
            engineer_hourly_cost=100,
        )
        serverless_result = compute_lcpr(moderate_volume, together_dsv3)
        dedicated_result = compute_lcpr(moderate_volume, low_util_gpu)
        # At 20% utilization and 1M requests, serverless should win
        assert serverless_result.lcpr < dedicated_result.lcpr


# --- Exact-match tests using canonical essay profiles ---
# These import from essay_profiles.py (single source of truth) and verify
# the calculator produces the exact numbers cited in the essay.

from calculator.essay_profiles import (
    PART0_SAAS,
    PART0_HIGH_RETRY,
    PART0_LOW_GATE,
    PART0_85_GATE,
    PART1_B2B,
    PART5_STAGE0,
    PART5_STAGE1,
    PART5_STAGE1_GPT,
    PART5_STAGE1_TOG,
    PART5_STAGE2,
)

# Provider pricing used across exact-match tests
_GPT55 = ProviderPricing(
    name="OpenAI GPT-5.5",
    input_rate_per_m=5.00,
    output_rate_per_m=30.00,
    deployment_mode="closed_api",
)
_TOGETHER = ProviderPricing(
    name="Together DeepSeek V3",
    input_rate_per_m=0.60,  # [PUBLIC_PRICING] together.ai/pricing — verified 2026-05-12
    output_rate_per_m=1.70,  # [PUBLIC_PRICING] together.ai/pricing — verified 2026-05-12
    deployment_mode="serverless_open",
)
_DEEPINFRA = ProviderPricing(
    name="DeepInfra GPT-OSS-120B",
    input_rate_per_m=0.039,  # [PUBLIC_PRICING] deepinfra.com/openai/gpt-oss-120b — verified 2026-05-12
    output_rate_per_m=0.19,  # [PUBLIC_PRICING] deepinfra.com/openai/gpt-oss-120b — verified 2026-05-12
    deployment_mode="serverless_open",
)


class TestEssayPart0ExactNumbers:
    """Exact-match tests for Part 0 table values using canonical profiles."""

    def test_gpt55_lcpr(self):
        """GPT-5.5 LCPR = $0.0191 per successful request."""
        result = compute_lcpr(PART0_SAAS, _GPT55)
        assert math.isclose(result.lcpr, 0.0191, rel_tol=0.005), (
            f"Expected LCPR ~$0.0191, got ${result.lcpr:.4f}"
        )

    def test_gpt55_monthly(self):
        """GPT-5.5 monthly cost = $9,090."""
        result = compute_lcpr(PART0_SAAS, _GPT55)
        assert math.isclose(result.monthly_cost, 9090.00, rel_tol=0.005), (
            f"Expected monthly ~$9,090, got ${result.monthly_cost:,.2f}"
        )

    def test_together_lcpr(self):
        """Together DeepSeek V3 LCPR = $0.003047 per successful request."""
        result = compute_lcpr(PART0_SAAS, _TOGETHER)
        assert math.isclose(result.lcpr, 0.003047, rel_tol=0.005), (
            f"Expected LCPR ~$0.003047, got ${result.lcpr:.6f}"
        )

    def test_together_monthly(self):
        """Together monthly cost = $1,447.40."""
        result = compute_lcpr(PART0_SAAS, _TOGETHER)
        assert math.isclose(result.monthly_cost, 1447.40, rel_tol=0.005), (
            f"Expected monthly ~$1,447.40, got ${result.monthly_cost:,.2f}"
        )

    def test_deepinfra_lcpr(self):
        """DeepInfra LCPR = ~$0.001906 per successful request."""
        result = compute_lcpr(PART0_SAAS, _DEEPINFRA)
        assert math.isclose(result.lcpr, 0.001906, rel_tol=0.005), (
            f"Expected LCPR ~$0.001906, got ${result.lcpr:.6f}"
        )

    def test_deepinfra_monthly(self):
        """DeepInfra monthly cost = $905.21."""
        result = compute_lcpr(PART0_SAAS, _DEEPINFRA)
        assert math.isclose(result.monthly_cost, 905.21, rel_tol=0.005), (
            f"Expected monthly ~$905.21, got ${result.monthly_cost:,.2f}"
        )

    def test_gpt55_vs_together_ratio(self):
        """GPT-5.5 / Together LCPR ratio = ~6.3x at baseline."""
        gpt_result = compute_lcpr(PART0_SAAS, _GPT55)
        tog_result = compute_lcpr(PART0_SAAS, _TOGETHER)
        ratio = gpt_result.lcpr / tog_result.lcpr
        assert math.isclose(ratio, 6.28, rel_tol=0.01), (
            f"Expected ~6.28x, got {ratio:.2f}x"
        )


class TestEssayPart1ExactNumbers:
    """Exact-match tests for Part 1 B2B migration example."""

    def test_b2b_gpt_monthly(self):
        """B2B workload on GPT-5.5 monthly cost = $18,128."""
        result = compute_lcpr(PART1_B2B, _GPT55)
        assert math.isclose(result.monthly_cost, 18128.00, rel_tol=0.005), (
            f"Expected monthly ~$18,128, got ${result.monthly_cost:,.2f}"
        )

    def test_b2b_together_monthly(self):
        """B2B workload on Together monthly cost = $2,546."""
        result = compute_lcpr(PART1_B2B, _TOGETHER)
        assert math.isclose(result.monthly_cost, 2546.00, rel_tol=0.005), (
            f"Expected monthly ~$2,546, got ${result.monthly_cost:,.2f}"
        )

    def test_b2b_savings(self):
        """Switching B2B from GPT-5.5 to Together saves $15,582/month."""
        gpt_result = compute_lcpr(PART1_B2B, _GPT55)
        tog_result = compute_lcpr(PART1_B2B, _TOGETHER)
        savings = gpt_result.monthly_cost - tog_result.monthly_cost
        assert math.isclose(savings, 15582.00, rel_tol=0.005), (
            f"Expected savings ~$15,582, got ${savings:,.2f}"
        )


class TestEssaySensitivity:
    """Exact-match tests for sensitivity analysis claims in the essay."""

    def test_high_retry_ratio(self):
        """At 20% retry rate, GPT/Together LCPR ratio = ~6.8x."""
        gpt_result = compute_lcpr(PART0_HIGH_RETRY, _GPT55)
        tog_result = compute_lcpr(PART0_HIGH_RETRY, _TOGETHER)
        ratio = gpt_result.lcpr / tog_result.lcpr
        assert math.isclose(ratio, 6.76, rel_tol=0.01), (
            f"Expected ~6.76x, got {ratio:.2f}x"
        )

    def test_low_gate_ratio(self):
        """At 70% quality gate, GPT/Together LCPR ratio = ~5.5x."""
        gpt_result = compute_lcpr(PART0_LOW_GATE, _GPT55)
        tog_result = compute_lcpr(PART0_LOW_GATE, _TOGETHER)
        ratio = gpt_result.lcpr / tog_result.lcpr
        assert math.isclose(ratio, 5.50, rel_tol=0.01), (
            f"Expected ~5.50x, got {ratio:.2f}x"
        )

    def test_quality_gate_10_point_drop_increases_lcpr_13_pct(self):
        """Dropping quality gate from 95% to 85% increases GPT-5.5 LCPR by ~13%."""
        base = compute_lcpr(PART0_SAAS, _GPT55)
        gate_85 = compute_lcpr(PART0_85_GATE, _GPT55)
        pct_increase = (gate_85.lcpr - base.lcpr) / base.lcpr * 100
        assert math.isclose(pct_increase, 13.0, rel_tol=0.02), (
            f"Expected ~13% increase, got {pct_increase:.1f}%"
        )


class TestEssayPart5Numbers:
    """Exact-match tests for Part 5 staged playbook costs."""

    def test_stage0_monthly(self):
        """Stage 0 (200K requests on GPT-5.5) monthly cost = $4,116."""
        result = compute_lcpr(PART5_STAGE0, _GPT55)
        assert math.isclose(result.monthly_cost, 4116.00, rel_tol=0.005), (
            f"Expected monthly ~$4,116, got ${result.monthly_cost:,.2f}"
        )

    def test_stage1_all_gpt_monthly(self):
        """Stage 1 before split (2M requests all on GPT-5.5) monthly cost = $33,960."""
        result = compute_lcpr(PART5_STAGE1, _GPT55)
        assert math.isclose(result.monthly_cost, 33960.00, rel_tol=0.005), (
            f"Expected monthly ~$33,960, got ${result.monthly_cost:,.2f}"
        )

    def test_stage2_monthly(self):
        """Stage 2 (10M requests on GPT-5.5) monthly cost = $166,600."""
        result = compute_lcpr(PART5_STAGE2, _GPT55)
        assert math.isclose(result.monthly_cost, 166600.00, rel_tol=0.005), (
            f"Expected monthly ~$166,600, got ${result.monthly_cost:,.2f}"
        )

    def test_stage1_split_savings(self):
        """Stage 1 70/30 split saves vs all-GPT."""
        all_gpt = compute_lcpr(PART5_STAGE1, _GPT55)
        split_gpt = compute_lcpr(PART5_STAGE1_GPT, _GPT55)
        split_tog = compute_lcpr(PART5_STAGE1_TOG, _TOGETHER)
        split_total = split_gpt.monthly_cost + split_tog.monthly_cost
        assert split_total < all_gpt.monthly_cost, (
            f"Split ${split_total:,.0f} should be cheaper than all-GPT ${all_gpt.monthly_cost:,.0f}"
        )
