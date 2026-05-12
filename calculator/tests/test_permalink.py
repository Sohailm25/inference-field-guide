# ABOUTME: Tests for permalink encode/decode — roundtrip WorkloadProfile through base64 JSON.
# ABOUTME: Ensures profiles can be shared via URL query parameters.

import pytest

from calculator.lcpr import WorkloadProfile
from calculator.permalink import decode_profile, encode_profile


class TestPermalinkRoundtrip:
    """Encoding then decoding should produce an identical profile."""

    def test_default_profile_roundtrip(self):
        profile = WorkloadProfile(
            avg_input_tokens=800,
            avg_output_tokens=400,
            monthly_requests=500_000,
            retry_rate=0.03,
            quality_gate_pass_rate=0.95,
            repair_cost_per_failure=0.002,
            engineering_hours_per_month=8,
            engineer_hourly_cost=100,
        )
        encoded = encode_profile(profile)
        decoded = decode_profile(encoded)
        assert decoded == profile

    def test_custom_profile_roundtrip(self):
        profile = WorkloadProfile(
            avg_input_tokens=4000,
            avg_output_tokens=2000,
            monthly_requests=10_000_000,
            retry_rate=0.15,
            quality_gate_pass_rate=0.80,
            repair_cost_per_failure=0.01,
            engineering_hours_per_month=40,
            engineer_hourly_cost=200,
            cache_hit_rate=0.3,
            batch_eligible_fraction=0.5,
            prefill_efficiency=0.1,
        )
        encoded = encode_profile(profile)
        decoded = decode_profile(encoded)
        assert decoded == profile

    def test_encoded_is_url_safe_string(self):
        profile = WorkloadProfile(
            avg_input_tokens=800,
            avg_output_tokens=400,
            monthly_requests=500_000,
            retry_rate=0.03,
            quality_gate_pass_rate=0.95,
            repair_cost_per_failure=0.002,
            engineering_hours_per_month=8,
            engineer_hourly_cost=100,
        )
        encoded = encode_profile(profile)
        assert isinstance(encoded, str)
        # URL-safe base64 uses only alphanumeric, -, _, =
        for char in encoded:
            assert char.isalnum() or char in ("-", "_", "="), f"Unexpected char: {char}"

    def test_decode_invalid_raises(self):
        with pytest.raises((ValueError, Exception)):
            decode_profile("not-valid-base64-json!!!")

    def test_decode_missing_field_uses_default(self):
        """If a field is missing from the JSON (e.g. old link), defaults fill in."""
        import base64
        import json

        partial = {"avg_input_tokens": 1000, "avg_output_tokens": 500,
                    "monthly_requests": 100_000}
        encoded = base64.urlsafe_b64encode(json.dumps(partial).encode()).decode()
        decoded = decode_profile(encoded)
        assert decoded.avg_input_tokens == 1000
        assert decoded.avg_output_tokens == 500
        assert decoded.monthly_requests == 100_000
        # Remaining fields should use WorkloadProfile defaults
        assert decoded.retry_rate == 0.0
        assert decoded.engineering_hours_per_month == 0
