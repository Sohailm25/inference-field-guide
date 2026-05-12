# ABOUTME: Tests for assumption confidence tracking alongside WorkloadProfile.
# ABOUTME: Verifies confidence status lifecycle and display helpers.

import pytest

from calculator.confidence import (
    VALID_STATUSES,
    AssumptionConfidence,
    default_confidence,
)
from calculator.lcpr import WorkloadProfile


class TestAssumptionConfidence:
    """Test the confidence tracking data structure."""

    def test_default_confidence_has_all_profile_fields(self):
        conf = default_confidence()
        profile_fields = {
            "avg_input_tokens",
            "avg_output_tokens",
            "monthly_requests",
            "retry_rate",
            "quality_gate_pass_rate",
            "repair_cost_per_failure",
            "engineering_hours_per_month",
            "engineer_hourly_cost",
        }
        for field in profile_fields:
            assert field in conf.statuses, f"Missing field: {field}"

    def test_default_status_is_assumed(self):
        conf = default_confidence()
        for field, status in conf.statuses.items():
            assert status == "assumed", f"{field} should default to 'assumed'"

    def test_set_valid_status(self):
        conf = default_confidence()
        conf.set("retry_rate", "measured_in_logs")
        assert conf.statuses["retry_rate"] == "measured_in_logs"

    def test_set_invalid_status_raises(self):
        conf = default_confidence()
        with pytest.raises(ValueError, match="Invalid status"):
            conf.set("retry_rate", "guessed")

    def test_set_unknown_field_raises(self):
        conf = default_confidence()
        with pytest.raises(ValueError, match="Unknown field"):
            conf.set("nonexistent_field", "assumed")

    def test_valid_statuses_are_defined(self):
        expected = {
            "assumed",
            "measured_in_logs",
            "load_tested",
            "invoice_reconciled",
            "contract_confirmed",
            "stale",
        }
        assert VALID_STATUSES == expected

    def test_measured_count(self):
        conf = default_confidence()
        assert conf.measured_count == 0
        conf.set("retry_rate", "measured_in_logs")
        conf.set("quality_gate_pass_rate", "load_tested")
        assert conf.measured_count == 2
