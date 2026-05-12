# ABOUTME: Assumption confidence tracking for WorkloadProfile inputs.
# ABOUTME: Tags each calculator input with its measurement confidence level.

from __future__ import annotations

from dataclasses import fields

from calculator.lcpr import WorkloadProfile

VALID_STATUSES: set[str] = {
    "assumed",
    "measured_in_logs",
    "load_tested",
    "invoice_reconciled",
    "contract_confirmed",
    "stale",
}

# Fields that represent tunable assumptions (not structural like token counts)
_TRACKABLE_FIELDS: set[str] = {
    "avg_input_tokens",
    "avg_output_tokens",
    "monthly_requests",
    "retry_rate",
    "quality_gate_pass_rate",
    "repair_cost_per_failure",
    "engineering_hours_per_month",
    "engineer_hourly_cost",
}


class AssumptionConfidence:
    """Tracks confidence status for each WorkloadProfile input."""

    def __init__(self, statuses: dict[str, str]) -> None:
        self.statuses = dict(statuses)

    def set(self, field: str, status: str) -> None:
        """Set the confidence status for a field."""
        if field not in self.statuses:
            raise ValueError(f"Unknown field: {field}")
        if status not in VALID_STATUSES:
            raise ValueError(
                f"Invalid status: {status!r}. "
                f"Valid: {sorted(VALID_STATUSES)}"
            )
        self.statuses[field] = status

    @property
    def measured_count(self) -> int:
        """Count of fields with status beyond 'assumed'."""
        return sum(
            1 for s in self.statuses.values()
            if s not in ("assumed", "stale")
        )


def default_confidence() -> AssumptionConfidence:
    """Create a confidence tracker with all trackable fields set to 'assumed'."""
    return AssumptionConfidence(
        {field: "assumed" for field in _TRACKABLE_FIELDS}
    )
