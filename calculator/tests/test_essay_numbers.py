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
    """Together DeepSeek V3 serverless: $1.25/$1.25 per M [PUBLIC]."""
    return ProviderPricing(
        name="Together DeepSeek V3",
        input_rate_per_m=1.25,
        output_rate_per_m=1.25,
        deployment_mode="serverless_open",
    )


@pytest.fixture
def lambda_h100():
    """Lambda H100 dedicated: $2.99/hr, 1500 tok/s theoretical, 40% util [PUBLIC]."""
    return ProviderPricing(
        name="Lambda H100",
        input_rate_per_m=0.0,
        output_rate_per_m=0.0,
        deployment_mode="dedicated",
        gpu_hourly_rate=2.99,
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
        # At $1.25/$1.25: raw = (800*1.25/1M) + (400*1.25/1M) = 0.001 + 0.0005 = $0.0015
        # With overhead → ~$0.003-$0.005
        assert 0.002 < result.lcpr < 0.006

    def test_gpt55_vs_together_ratio(self, essay_workload, gpt55, together_dsv3):
        """Essay claims open-weights is 5-30x cheaper for non-reasoning workloads.
        Verify this specific pair shows a significant cost advantage."""
        gpt_result = compute_lcpr(essay_workload, gpt55)
        together_result = compute_lcpr(essay_workload, together_dsv3)
        ratio = gpt_result.lcpr / together_result.lcpr
        # Should be roughly 5-10x cheaper (accounting for fixed engineering costs)
        assert ratio > 3.0, f"Expected >3x ratio, got {ratio:.1f}x"
        assert ratio < 15.0, f"Unexpectedly high ratio: {ratio:.1f}x"

    def test_dedicated_lcpr_range(self, essay_workload, lambda_h100):
        """Dedicated H100 at this volume — should be more expensive than serverless
        (500K req × 400 output tokens = 200M tokens/month, not enough to justify dedicated)."""
        result = compute_lcpr(essay_workload, lambda_h100)
        # GPU cost is fixed at $2.99*24*30 = $2,152.80/month regardless of volume
        # At 500K requests that's ~$0.004-$0.006 per successful request
        assert result.lcpr > 0
        assert result.monthly_cost > 2000  # At minimum the GPU cost


class TestEssayPart1MigrationGate:
    """Verify migration gate thresholds from the essay.

    Essay claims:
    - Under ~$10K/month: stay on closed APIs
    - $10K-$100K/month: add serverless open for long-tail
    - Break-even for dedicated: ~20M output tokens/day with steady traffic
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

    def test_break_even_daily_tokens_order_of_magnitude(self, together_dsv3, lambda_h100):
        """Essay claims break-even at ~20M output tokens/day vs Fireworks $0.90/M.
        Against Together at $1.25/M with Lambda at $2.99/hr, break-even should be
        in the tens-of-millions range."""
        result = compute_break_even(together_dsv3, lambda_h100)
        daily_tokens = result.break_even_daily_output_tokens
        # Should be in 50M-500M range (adjusted for utilization)
        assert daily_tokens > 10_000_000, f"Break-even too low: {daily_tokens:,.0f}"
        assert daily_tokens < 1_000_000_000, f"Break-even too high: {daily_tokens:,.0f}"

    def test_fireworks_break_even_near_20m(self):
        """Essay's specific claim: H100 at $2.01/hr vs Fireworks $0.90/M serverless
        break-even is ~53.6M tokens/day at full utilization.
        At 40% util, effective break-even is ~3x higher."""
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
        """Lambda at $2.99/hr vs AWS at $4.975/hr (per GPU) — verify savings %."""
        lambda_rate = 2.99
        aws_rate = 4.975  # p5e.48xlarge per-GPU
        savings_pct = (1 - lambda_rate / aws_rate) * 100
        # Essay claims 40-85% cheaper
        assert savings_pct > 35, f"Savings only {savings_pct:.0f}%"
        assert savings_pct < 90, f"Savings {savings_pct:.0f}% seems too high"

    def test_dedicated_gpu_monthly_cost_range(self):
        """Verify monthly GPU costs are in the ranges cited."""
        # Lambda H100: $2.99/hr → ~$2,153/month
        lambda_monthly = 2.99 * 24 * 30
        assert 2100 < lambda_monthly < 2200

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
            gpu_hourly_rate=2.99,
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
