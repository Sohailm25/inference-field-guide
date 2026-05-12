# ABOUTME: Migration readiness scoring engine for polynomial complexity assessment.
# ABOUTME: Scores 6 migration factors to determine tier, timeline, gaps, and payback.

from __future__ import annotations

from dataclasses import dataclass


EXPECTED_FACTORS = {
    "workload_count",
    "prompt_portability",
    "quality_infrastructure",
    "latency_sensitivity",
    "team_maturity",
    "integration_depth",
}

TIER_THRESHOLDS = {
    "Simple": (6, 9),
    "Standard": (10, 14),
    "Complex": (15, 18),
}

TIMELINE_BY_TIER = {
    "Simple": (4, 6),
    "Standard": (8, 12),
    "Complex": (12, 20),
}

RECOMMENDATIONS = {
    "Simple": (
        "Self-service migration using this guide. "
        "Start with serverless open-weights."
    ),
    "Standard": (
        "Phased migration with quality gates. "
        "Consider managed dedicated for primary workload."
    ),
    "Complex": (
        "Expert-assisted migration recommended. "
        "Managed dedicated with vendor engineering support "
        "(Field Deployment Engineer model) reduces both timeline and risk."
    ),
}

ENGINEERING_HOURS = {
    "serverless": {
        "setup_min": 2,
        "setup_max": 8,
        "monthly_min": 2,
        "monthly_max": 5,
    },
    "managed_dedicated": {
        "setup_min": 8,
        "setup_max": 20,
        "monthly_min": 5,
        "monthly_max": 10,
    },
    "self_managed": {
        "setup_min": 40,
        "setup_max": 80,
        "monthly_min": 30,
        "monthly_max": 60,
    },
}


@dataclass(frozen=True)
class MigrationFactor:
    """A single migration complexity factor with a 1-3 score."""

    name: str
    score: int

    def __post_init__(self) -> None:
        if self.score < 1 or self.score > 3:
            raise ValueError(
                f"Score must be 1, 2, or 3, got {self.score} for {self.name}"
            )


@dataclass(frozen=True)
class ReadinessResult:
    """Output of a migration readiness assessment."""

    total_score: int
    tier: str  # "Simple", "Standard", or "Complex"
    timeline_weeks_min: int
    timeline_weeks_max: int
    recommendation: str
    gaps: list[str]


def compute_readiness(factors: list[MigrationFactor]) -> ReadinessResult:
    """Score 6 migration factors and return tier, timeline, and gaps."""
    if len(factors) != 6:
        raise ValueError(f"Expected 6 factors, got {len(factors)}")

    provided_names = {f.name for f in factors}
    if provided_names != EXPECTED_FACTORS:
        missing = EXPECTED_FACTORS - provided_names
        unexpected = provided_names - EXPECTED_FACTORS
        parts = []
        if missing:
            parts.append(f"missing: {sorted(missing)}")
        if unexpected:
            parts.append(f"unexpected: {sorted(unexpected)}")
        raise ValueError(f"Invalid factor names — {', '.join(parts)}")

    total = sum(f.score for f in factors)

    # Determine tier
    tier = "Complex"  # default for anything above 14
    for tier_name, (lo, hi) in TIER_THRESHOLDS.items():
        if lo <= total <= hi:
            tier = tier_name
            break

    timeline_min, timeline_max = TIMELINE_BY_TIER[tier]
    recommendation = RECOMMENDATIONS[tier]

    # Detect gaps — factor_map is safe because we validated names above
    factor_map = {f.name: f.score for f in factors}
    gaps = _detect_gaps(factor_map)

    return ReadinessResult(
        total_score=total,
        tier=tier,
        timeline_weeks_min=timeline_min,
        timeline_weeks_max=timeline_max,
        recommendation=recommendation,
        gaps=gaps,
    )


def _detect_gaps(factor_map: dict[str, int]) -> list[str]:
    """Identify readiness gaps based on factor scores.

    Assumes factor_map contains all EXPECTED_FACTORS keys (validated upstream).
    """
    gaps: list[str] = []

    if factor_map["quality_infrastructure"] == 1:
        gaps.append(
            "Gap: No evaluation framework. "
            "You cannot safely validate model quality after migration without evals. "
            "Build a minimum viable eval suite (20-50 representative inputs with "
            "expected outputs) before starting migration."
        )

    if factor_map["team_maturity"] == 1 and factor_map["latency_sensitivity"] == 3:
        gaps.append(
            "Gap: No inference expertise for latency-critical workload. "
            "Sub-500ms P95 requires runtime-level optimization. "
            "Options: (1) hire inference engineer, "
            "(2) use managed dedicated with vendor optimization."
        )

    if factor_map["integration_depth"] == 3 and factor_map["workload_count"] == 3:
        gaps.append(
            "Gap: Multi-system migration at scale. "
            "Phased approach mandatory. "
            "Migrate one workload at a time with 2-week parallel-run validation."
        )

    return gaps


def get_engineering_hours(deployment_mode: str) -> dict[str, int]:
    """Return setup and monthly engineering hours for a deployment mode."""
    return ENGINEERING_HOURS[deployment_mode]


def compute_payback(
    current_monthly_cost: float,
    projected_monthly_cost: float,
    engineering_investment: float,
) -> float:
    """Compute payback period in months.

    Returns float('inf') if migration doesn't save money.
    """
    monthly_savings = current_monthly_cost - projected_monthly_cost
    if monthly_savings <= 0:
        return float("inf")
    return engineering_investment / monthly_savings
