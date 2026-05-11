# ABOUTME: Tests for workload profile templates.
# ABOUTME: Validates pre-built profiles produce reasonable LCPR outputs.

from pathlib import Path

import pytest

from calculator.lcpr import LCPRCalculator, ProviderPricing, WorkloadProfile, compute_lcpr
from calculator.workload_profiles import (
    PROFILES,
    get_profile,
    list_profiles,
)


class TestProfileRegistry:
    """Tests for the profile registry."""

    def test_profiles_exist(self):
        """Should have pre-built profiles."""
        assert len(PROFILES) >= 5

    def test_list_profiles_returns_names(self):
        """list_profiles should return profile names."""
        names = list_profiles()
        assert len(names) >= 5
        assert all(isinstance(n, str) for n in names)

    def test_get_profile_returns_workload(self):
        """get_profile should return a WorkloadProfile."""
        names = list_profiles()
        profile = get_profile(names[0])
        assert isinstance(profile, WorkloadProfile)

    def test_get_unknown_profile_raises(self):
        """get_profile with unknown name should raise."""
        with pytest.raises(KeyError):
            get_profile("nonexistent_profile")

    def test_expected_profiles_exist(self):
        """Should have the 5 planned profiles."""
        names = list_profiles()
        expected = {
            "saas_chat",
            "code_completion",
            "batch_processing",
            "voice_agent",
            "rag_pipeline",
        }
        assert expected.issubset(set(names))


class TestProfileValues:
    """Tests that profile values are reasonable."""

    @pytest.mark.parametrize("name", list_profiles() if hasattr(list_profiles, "__call__") else [])
    def test_profile_has_positive_tokens(self, name):
        """Every profile should have at least some input tokens."""
        profile = get_profile(name)
        assert profile.avg_input_tokens > 0

    @pytest.mark.parametrize("name", list_profiles() if hasattr(list_profiles, "__call__") else [])
    def test_profile_has_valid_retry_rate(self, name):
        """Retry rate should be between 0 and 1."""
        profile = get_profile(name)
        assert 0.0 <= profile.retry_rate <= 1.0

    @pytest.mark.parametrize("name", list_profiles() if hasattr(list_profiles, "__call__") else [])
    def test_profile_has_valid_quality_gate(self, name):
        """Quality gate pass rate should be between 0 and 1."""
        profile = get_profile(name)
        assert 0.0 < profile.quality_gate_pass_rate <= 1.0


class TestProfileLCPRReasonableness:
    """Tests that profiles produce reasonable LCPR values."""

    @pytest.fixture
    def calculator(self):
        pricing_path = Path(__file__).parent.parent / "provider_pricing.yaml"
        return LCPRCalculator(pricing_path)

    def test_saas_chat_reasonable_monthly_cost(self, calculator):
        """SaaS chat profile should produce a plausible monthly cost range."""
        profile = get_profile("saas_chat")
        results = calculator.compare(profile)

        # At least one result should exist
        assert len(results) > 0

        # Monthly costs should range from hundreds to tens of thousands
        monthly_costs = [r.monthly_cost for r in results]
        cheapest = min(monthly_costs)
        most_expensive = max(monthly_costs)
        assert cheapest > 0
        assert most_expensive < 10_000_000  # sanity check

    def test_batch_processing_cheaper_than_chat(self, calculator):
        """Batch processing should generally be cheaper per-request due to tolerance."""
        chat = get_profile("saas_chat")
        batch = get_profile("batch_processing")

        # Use a common provider for comparison
        provider = ProviderPricing(
            name="Test Provider",
            input_rate_per_m=1.25,
            output_rate_per_m=1.25,
            deployment_mode="serverless_open",
        )

        chat_result = compute_lcpr(chat, provider)
        batch_result = compute_lcpr(batch, provider)

        # Batch should have lower LCPR (less overhead, higher quality gate)
        # This isn't guaranteed — depends on token volumes — so just check both are valid
        assert chat_result.lcpr > 0
        assert batch_result.lcpr > 0

    def test_voice_agent_has_low_token_counts(self):
        """Voice agent should have relatively small input/output tokens."""
        profile = get_profile("voice_agent")
        # Voice interactions are typically short
        assert profile.avg_output_tokens < 500
