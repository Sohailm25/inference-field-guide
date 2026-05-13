# ABOUTME: Canonical registry for calculator views and their implementation status.
# ABOUTME: Keeps app tabs, examples, and documentation aligned around one view inventory.

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CalculatorView:
    """Metadata for one calculator view or appendix-promised template."""

    public_name: str
    internal_name: str
    status: str
    evidence_mode: str
    reference: str
    exercised_by_examples: tuple[str, ...] = ()


IMPLEMENTED_APP_TABS = (
    "LCPR Comparison",
    "Sensitivity Analysis",
    "Break-Even Analysis",
    "Migration Readiness",
    "Decision Trees",
    "Goodput Frontier",
    "Trace-to-Margin",
    "Cache Policy Gate",
    "KV Capacity Envelope",
    "RouteFit Matrix",
    "Trace Event Schema",
    "Source Snapshot Browser",
    "Operating Views",
)


APPENDIX_VIEW_NAMES = (
    "Workload Profile",
    "Trace Event Schema",
    "Latency Decomposition",
    "SLO-to-Route Mapping",
    "Cost Per Accepted Work",
    "Spend Movement Waterfall",
    "Commitment Utilization",
    "Variance Analysis",
    "Account Margin Model",
    "Usage Signals",
    "Security and Compliance Filter",
    "Cache Policy Gate",
    "KV Capacity Envelope",
    "Dedicated Break-Even",
)


VIEW_REGISTRY = (
    CalculatorView(
        public_name="LCPR Comparison",
        internal_name="LCPR-2026",
        status="implemented_ui",
        evidence_mode="modeled",
        reference="Part 1 / Appendix View 5",
        exercised_by_examples=("support-answer", "coding-agent", "benchmark-audit"),
    ),
    CalculatorView(
        public_name="Sensitivity Analysis",
        internal_name="Sensitivity Analysis v1",
        status="implemented_ui",
        evidence_mode="modeled",
        reference="Calculator utility view",
    ),
    CalculatorView(
        public_name="Break-Even Analysis",
        internal_name="Break-Even Analysis v1",
        status="implemented_ui",
        evidence_mode="modeled",
        reference="Part 4 / Appendix View 14",
    ),
    CalculatorView(
        public_name="Dedicated Break-Even",
        internal_name="Dedicated Break-Even v1",
        status="implemented_ui",
        evidence_mode="modeled",
        reference="Part 4 / Appendix View 14",
    ),
    CalculatorView(
        public_name="Migration Readiness",
        internal_name="Migration Readiness v1",
        status="implemented_ui",
        evidence_mode="modeled",
        reference="Part 4 migration gates",
    ),
    CalculatorView(
        public_name="Decision Trees",
        internal_name="Decision Frameworks v1",
        status="implemented_ui",
        evidence_mode="template",
        reference="Part 4 decision frameworks",
    ),
    CalculatorView(
        public_name="Goodput Frontier",
        internal_name="Goodput Frontier Test v1",
        status="implemented_ui",
        evidence_mode="synthetic_or_measured",
        reference="Part 2 / Derivation 5",
        exercised_by_examples=("coding-agent", "benchmark-audit"),
    ),
    CalculatorView(
        public_name="Trace-to-Margin",
        internal_name="Trace-to-Margin Review v1",
        status="implemented_ui",
        evidence_mode="synthetic_or_measured",
        reference="Part 5 / Derivation 6",
        exercised_by_examples=("support-answer",),
    ),
    CalculatorView(
        public_name="Cache Policy Gate",
        internal_name="Cache Policy Gate v1",
        status="implemented_ui",
        evidence_mode="modeled",
        reference="Part 2 / Derivation 3 / Appendix View 12",
        exercised_by_examples=("support-answer", "coding-agent"),
    ),
    CalculatorView(
        public_name="KV Capacity Envelope",
        internal_name="KV Capacity Envelope v1",
        status="implemented_ui",
        evidence_mode="derived",
        reference="Part 2 / Derivation 2 / Appendix View 13",
    ),
    CalculatorView(
        public_name="RouteFit Matrix",
        internal_name="RouteFit Matrix v1",
        status="template_ui",
        evidence_mode="user_input",
        reference="Part 4 / Appendix View 4",
        exercised_by_examples=("benchmark-audit",),
    ),
    CalculatorView(
        public_name="Trace Event Schema",
        internal_name="Trace Event Schema v1",
        status="template_ui",
        evidence_mode="user_input",
        reference="Part 1 / Appendix View 2",
    ),
    CalculatorView(
        public_name="Source Snapshot Browser",
        internal_name="Source Snapshot Browser v1",
        status="template_ui",
        evidence_mode="public_snapshot",
        reference="Appendix A.4",
    ),
    CalculatorView(
        public_name="Operating Views",
        internal_name="Operating Views v1",
        status="template_ui",
        evidence_mode="user_input",
        reference="Appendix Views 3, 6-11",
    ),
    CalculatorView(
        public_name="Workload Profile",
        internal_name="Workload Profile v1",
        status="implemented_ui",
        evidence_mode="user_input",
        reference="Sidebar / Appendix View 1",
    ),
    CalculatorView(
        public_name="Latency Decomposition",
        internal_name="Latency Decomposition v1",
        status="template_ui",
        evidence_mode="user_input",
        reference="Operating Views / Appendix View 3",
    ),
    CalculatorView(
        public_name="SLO-to-Route Mapping",
        internal_name="SLO-to-Route Mapping v1",
        status="template_ui",
        evidence_mode="user_input",
        reference="RouteFit Matrix / Appendix View 4",
    ),
    CalculatorView(
        public_name="Cost Per Accepted Work",
        internal_name="Cost Per Accepted Work v1",
        status="implemented_ui",
        evidence_mode="synthetic_or_measured",
        reference="LCPR Comparison / Trace-to-Margin / Appendix View 5",
    ),
    CalculatorView(
        public_name="Spend Movement Waterfall",
        internal_name="Spend Movement Waterfall v1",
        status="template_ui",
        evidence_mode="user_input",
        reference="Operating Views / Appendix View 6",
    ),
    CalculatorView(
        public_name="Commitment Utilization",
        internal_name="Commitment Utilization v1",
        status="template_ui",
        evidence_mode="user_input",
        reference="Operating Views / Appendix View 7",
    ),
    CalculatorView(
        public_name="Variance Analysis",
        internal_name="Variance Drilldown v1",
        status="template_ui",
        evidence_mode="user_input",
        reference="Operating Views / Appendix View 8",
    ),
    CalculatorView(
        public_name="Account Margin Model",
        internal_name="Account Margin Model v1",
        status="template_ui",
        evidence_mode="user_input",
        reference="Operating Views / Appendix View 9",
    ),
    CalculatorView(
        public_name="Usage Signals",
        internal_name="Usage Signals v1",
        status="template_ui",
        evidence_mode="user_input",
        reference="Operating Views / Appendix View 10",
    ),
    CalculatorView(
        public_name="Security and Compliance Filter",
        internal_name="Security and Compliance Filter v1",
        status="template_ui",
        evidence_mode="user_input",
        reference="Operating Views / Appendix View 11",
    ),
)


def view_by_public_name(public_name: str) -> CalculatorView:
    """Return metadata for a view by its visible name."""
    for view in VIEW_REGISTRY:
        if view.public_name == public_name:
            return view
    raise KeyError(public_name)


def view_by_internal_name(internal_name: str) -> CalculatorView:
    """Return metadata for a view by its seed/internal name."""
    for view in VIEW_REGISTRY:
        if view.internal_name == internal_name:
            return view
    raise KeyError(internal_name)


def registry_rows() -> list[dict[str, str]]:
    """Return registry rows suitable for docs and Streamlit tables."""
    return [
        {
            "View": view.public_name,
            "Internal name": view.internal_name,
            "Status": view.status,
            "Evidence mode": view.evidence_mode,
            "Reference": view.reference,
        }
        for view in VIEW_REGISTRY
    ]
