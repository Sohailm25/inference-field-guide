# ABOUTME: Canonical registry for calculator views and their implementation status.
# ABOUTME: Keeps app tabs, examples, and documentation aligned around one view inventory.

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import NamedTuple


# ABOUTME: 7-view enumeration for the new Marimo app — replaces the 13-tab
# ABOUTME: Streamlit split. See spec §9.1 and Appendix B decision 16.


class MarimoView(str, Enum):
    LANDING = "landing"
    COMPARE = "compare"
    SENSITIVITY = "sensitivity"
    BREAK_EVEN = "break-even"
    GOODPUT = "goodput"
    TRACE_TO_MARGIN = "trace-to-margin"
    ADVANCED = "advanced"


class ViewMeta(NamedTuple):
    label: str
    description: str
    replaces: tuple[str, ...]  # which Streamlit tab(s) this replaces


MARIMO_VIEW_META: dict[MarimoView, ViewMeta] = {
    MarimoView.LANDING: ViewMeta(
        label="Landing",
        description="Mad-libs sentence wired to a default workload; verdict paragraph below.",
        replaces=("Start Here",),
    ),
    MarimoView.COMPARE: ViewMeta(
        label="Compare",
        description="LCPR comparison across providers for the current workload.",
        replaces=("Compare",),
    ),
    MarimoView.SENSITIVITY: ViewMeta(
        label="Sensitivity",
        description="How LCPR moves as one parameter sweeps a range.",
        replaces=("Sensitivity",),
    ),
    MarimoView.BREAK_EVEN: ViewMeta(
        label="Break-Even",
        description="Daily output volume where dedicated capacity beats serverless.",
        replaces=("Break-Even",),
    ),
    MarimoView.GOODPUT: ViewMeta(
        label="Goodput",
        description="Accepted requests per second under latency + quality SLOs (Derivation 5).",
        replaces=("Goodput",),
    ),
    MarimoView.TRACE_TO_MARGIN: ViewMeta(
        label="Trace-to-Margin",
        description="Reconcile raw traces to invoice + revenue (Derivation 6).",
        replaces=("Trace-to-Margin",),
    ),
    MarimoView.ADVANCED: ViewMeta(
        label="Advanced",
        description="Cache Gate · KV Capacity · Migration · RouteFit · Trace Schema · Snapshots · Operations.",
        replaces=("Migration", "Cache Gate", "KV Capacity", "RouteFit", "Trace Schema", "Snapshots", "Operations"),
    ),
}


@dataclass(frozen=True)
class CalculatorView:
    """Metadata for one calculator view or appendix-promised template."""

    public_name: str
    internal_name: str
    status: str
    evidence_mode: str
    reference: str
    exercised_by_examples: tuple[str, ...] = ()


CORE_APP_TABS = (
    "Start Here",
    "Compare",
    "Sensitivity",
    "Break-Even",
    "Migration",
)

ADVANCED_APP_TABS = (
    "Goodput",
    "Trace-to-Margin",
    "Cache Gate",
    "KV Capacity",
    "RouteFit",
    "Trace Schema",
    "Snapshots",
    "Operations",
)

IMPLEMENTED_APP_TABS = CORE_APP_TABS[1:] + ADVANCED_APP_TABS


APPENDIX_VIEW_NAMES = (
    "Workload Profile",
    "Trace Schema",
    "Latency Decomposition",
    "SLO-to-Route Mapping",
    "Cost Per Accepted Work",
    "Spend Movement Waterfall",
    "Commitment Utilization",
    "Variance Analysis",
    "Account Margin Model",
    "Usage Signals",
    "Security and Compliance Filter",
    "Cache Gate",
    "KV Capacity",
    "Dedicated Break-Even",
)


VIEW_REGISTRY = (
    CalculatorView(
        public_name="Start Here",
        internal_name="Start Here v1",
        status="implemented_ui",
        evidence_mode="user_input",
        reference="Landing page / glossary",
    ),
    CalculatorView(
        public_name="Compare",
        internal_name="LCPR-2026",
        status="implemented_ui",
        evidence_mode="modeled",
        reference="Part 1 / Appendix View 5",
        exercised_by_examples=("support-answer", "coding-agent", "benchmark-audit"),
    ),
    CalculatorView(
        public_name="Sensitivity",
        internal_name="Sensitivity Analysis v1",
        status="implemented_ui",
        evidence_mode="modeled",
        reference="Calculator utility view",
    ),
    CalculatorView(
        public_name="Break-Even",
        internal_name="Break-Even Analysis v1",
        status="implemented_ui",
        evidence_mode="modeled",
        reference="Part 4 / Appendix View 14",
    ),
    CalculatorView(
        public_name="Dedicated Break-Even",
        internal_name="Dedicated Utilization Gate v1",
        status="implemented_ui",
        evidence_mode="modeled",
        reference="Part 4 / Appendix View 14",
    ),
    CalculatorView(
        public_name="Migration",
        internal_name="Migration Readiness v1",
        status="implemented_ui",
        evidence_mode="modeled",
        reference="Part 4 migration gates",
    ),
    CalculatorView(
        public_name="Goodput",
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
        public_name="Cache Gate",
        internal_name="Cache Policy Gate v1",
        status="implemented_ui",
        evidence_mode="modeled",
        reference="Part 2 / Derivation 3 / Appendix View 12",
        exercised_by_examples=("support-answer", "coding-agent"),
    ),
    CalculatorView(
        public_name="KV Capacity",
        internal_name="KV Capacity Envelope v1",
        status="implemented_ui",
        evidence_mode="derived",
        reference="Part 2 / Derivation 2 / Appendix View 13",
    ),
    CalculatorView(
        public_name="RouteFit",
        internal_name="RouteFit Matrix v1",
        status="template_ui",
        evidence_mode="user_input",
        reference="Part 4 / Appendix View 4",
        exercised_by_examples=("benchmark-audit",),
    ),
    CalculatorView(
        public_name="Trace Schema",
        internal_name="Trace Event Schema v1",
        status="template_ui",
        evidence_mode="user_input",
        reference="Part 1 / Appendix View 2",
    ),
    CalculatorView(
        public_name="Snapshots",
        internal_name="Source Snapshot Browser v1",
        status="template_ui",
        evidence_mode="public_snapshot",
        reference="Appendix A.4",
    ),
    CalculatorView(
        public_name="Operations",
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


# ABOUTME: Human-readable labels for snake_case parameter names. Used by
# ABOUTME: the Sensitivity view to label its parameter selectbox. See spec §9.1 step 6.

PARAM_LABELS: dict[str, str] = {
    "retry_rate": "Retry rate",
    "quality_gate_pass_rate": "Quality gate pass rate",
    "cache_hit_rate": "Cache hit rate",
    "batch_fraction": "Batch fraction",
    "monthly_requests": "Monthly requests",
    "avg_input_tokens": "Avg input tokens",
    "avg_output_tokens": "Avg output tokens",
    "schema_failure_rate": "Schema-failure rate",
    "escalation_rate": "Escalation rate",
    "ops_cost_per_request": "Ops cost per request",
}
