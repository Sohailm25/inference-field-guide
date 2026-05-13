# ABOUTME: Streamlit web interface for the LCPR calculator.
# ABOUTME: Interactive UI for workload profiling, provider comparison, and crossover analysis.

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import yaml

# Ensure project root is on sys.path (needed when not pip-installed)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from calculator.confidence import VALID_STATUSES, default_confidence
from calculator.lcpr import (
    HOURS_PER_MONTH,
    SECONDS_PER_MONTH,
    GoodputRequest,
    LCPRCalculator,
    WorkloadProfile,
    compute_break_even,
    compute_cache_break_even,
    compute_goodput,
    compute_kv_sizing,
    compute_lcpr,
    compute_trace_to_margin,
)
from calculator.permalink import decode_profile, encode_profile
from calculator.readiness import (
    MigrationFactor,
    compute_payback,
    compute_readiness,
    get_engineering_hours,
)
from calculator.view_registry import IMPLEMENTED_APP_TABS, registry_rows
from calculator.workload_profiles import get_profile, list_profiles

PRICING_PATH = Path(__file__).parent / "provider_pricing.yaml"
SNAPSHOT_DIR = Path(__file__).parent.parent / "source-snapshots" / "2026-05-12"

DEPLOYMENT_COLORS = {
    "closed_api": "#e74c3c",
    "serverless_open": "#A7C080",
    "dedicated": "#7FBBB3",
}

DEPLOYMENT_LABELS = {
    "closed_api": "Closed API",
    "serverless_open": "Serverless Open",
    "dedicated": "Dedicated GPU",
}


def _build_profile_from_sidebar() -> tuple[WorkloadProfile, str]:
    """Build a WorkloadProfile from sidebar controls. Returns (profile, name)."""
    st.sidebar.header("Workload Profile")

    profile_names = list_profiles()
    labels = [n.replace("_", " ").title() for n in profile_names]
    labels.append("Custom")
    choice = st.sidebar.selectbox("Preset", labels, index=0)

    if choice == "Custom":
        profile_name = "custom"
        input_tokens = st.sidebar.slider("Avg input tokens", 50, 10000, 800, step=50)
        output_tokens = st.sidebar.slider("Avg output tokens", 10, 5000, 400, step=50)
        monthly_requests = st.sidebar.number_input(
            "Monthly requests", min_value=10_000, max_value=100_000_000,
            value=500_000, step=100_000,
        )
        retry_rate = st.sidebar.slider("Retry rate", 0.0, 0.50, 0.03, step=0.01)
        quality_gate = st.sidebar.slider("Quality gate pass rate", 0.50, 1.0, 0.95, step=0.01)
        cache_hit_rate = st.sidebar.slider("Cache hit rate", 0.0, 1.0, 0.0, step=0.05)
        batch_fraction = st.sidebar.slider(
            "Batch eligible fraction", 0.0, 1.0, 0.0, step=0.05,
            help="Fraction of requests eligible for batch API pricing",
        )
        prefill_eff = st.sidebar.slider(
            "Prefill efficiency", 0.0, 0.50, 0.0, step=0.05,
            help="Fraction of prefill compute displacing decode throughput (>8K input)",
        )
        repair_cost = st.sidebar.number_input(
            "Repair cost per failure ($)", min_value=0.0, max_value=1.0,
            value=0.002, step=0.001, format="%.3f",
            help="Cost to re-prompt a request that fails quality/schema gates",
        )
        eng_hours = st.sidebar.slider("Engineering hours/month", 0, 80, 8)
        eng_rate = st.sidebar.slider("Engineer hourly cost ($)", 50, 250, 100, step=10)

        profile = WorkloadProfile(
            avg_input_tokens=input_tokens,
            avg_output_tokens=output_tokens,
            monthly_requests=monthly_requests,
            retry_rate=retry_rate,
            quality_gate_pass_rate=quality_gate,
            repair_cost_per_failure=repair_cost,
            engineering_hours_per_month=eng_hours,
            engineer_hourly_cost=eng_rate,
            cache_hit_rate=cache_hit_rate,
            batch_eligible_fraction=batch_fraction,
            prefill_efficiency=prefill_eff,
        )
    else:
        idx = labels.index(choice)
        profile_name = profile_names[idx]
        profile = get_profile(profile_name)

        st.sidebar.markdown("---")
        st.sidebar.markdown(f"**{choice} defaults:**")
        st.sidebar.markdown(
            f"- Input: {profile.avg_input_tokens} tokens\n"
            f"- Output: {profile.avg_output_tokens} tokens\n"
            f"- Volume: {profile.monthly_requests:,}/mo\n"
            f"- Retry: {profile.retry_rate:.0%}\n"
            f"- Quality gate: {profile.quality_gate_pass_rate:.0%}\n"
            f"- Eng hours: {profile.engineering_hours_per_month}h/mo"
        )

        # Allow overrides
        st.sidebar.markdown("---")
        st.sidebar.markdown("**Override parameters:**")
        monthly_requests = st.sidebar.number_input(
            "Monthly requests", min_value=10_000, max_value=100_000_000,
            value=profile.monthly_requests, step=100_000,
        )
        retry_rate = st.sidebar.slider(
            "Retry rate", 0.0, 0.50, profile.retry_rate, step=0.01,
        )
        quality_gate = st.sidebar.slider(
            "Quality gate pass rate", 0.50, 1.0,
            profile.quality_gate_pass_rate, step=0.01,
        )
        cache_hit_rate = st.sidebar.slider(
            "Cache hit rate", 0.0, 1.0, profile.cache_hit_rate, step=0.05,
        )
        batch_fraction = st.sidebar.slider(
            "Batch eligible fraction", 0.0, 1.0,
            profile.batch_eligible_fraction, step=0.05,
            help="Fraction of requests eligible for batch API pricing",
        )
        prefill_eff = st.sidebar.slider(
            "Prefill efficiency", 0.0, 0.50,
            profile.prefill_efficiency, step=0.05,
            help="Fraction of prefill compute displacing decode throughput (>8K input)",
        )
        repair_cost = st.sidebar.number_input(
            "Repair cost per failure ($)", min_value=0.0, max_value=1.0,
            value=profile.repair_cost_per_failure, step=0.001, format="%.3f",
            help="Cost to re-prompt a request that fails quality/schema gates",
        )

        profile = replace(
            profile,
            monthly_requests=monthly_requests,
            retry_rate=retry_rate,
            quality_gate_pass_rate=quality_gate,
            cache_hit_rate=cache_hit_rate,
            batch_eligible_fraction=batch_fraction,
            prefill_efficiency=prefill_eff,
            repair_cost_per_failure=repair_cost,
        )

    return profile, profile_name


def _tab_comparison(calc: LCPRCalculator, profile: WorkloadProfile) -> None:
    """Tab 1: LCPR comparison table and bar chart."""
    st.subheader("LCPR Comparison")
    st.markdown(
        "Profile-estimated Loaded Cost Per Result across providers, ranked "
        "lowest to highest. This view uses sidebar workload assumptions, pricing "
        "rows, retry rate, quality gate pass rate, repair cost, and engineering "
        "overhead. Use Trace-to-Margin when you have traces and invoices and need "
        "the full book formula with invoice delta, eval, human, and ops costs."
    )

    results = calc.compare(profile)

    # Build table data
    rows = []
    for r in results:
        raw_cost = _raw_cost_per_request(profile, r.provider_name, calc)
        overhead = r.lcpr / raw_cost if raw_cost > 0 else 0
        rows.append({
            "Provider": r.provider_name,
            "Mode": DEPLOYMENT_LABELS.get(r.deployment_mode, r.deployment_mode),
            "Raw $/attempt": f"${raw_cost:.4f}",
            "LCPR": f"${r.lcpr:.4f}",
            "Monthly": f"${r.monthly_cost:,.0f}",
            "Overhead": f"{overhead:.1f}x",
        })

    st.dataframe(rows, use_container_width=True, hide_index=True)

    # Bar chart
    chart_data = []
    for r in results:
        chart_data.append({
            "Provider": r.provider_name,
            "LCPR ($)": r.lcpr,
            "Mode": DEPLOYMENT_LABELS.get(r.deployment_mode, r.deployment_mode),
        })

    fig = px.bar(
        chart_data,
        x="Provider",
        y="LCPR ($)",
        color="Mode",
        color_discrete_map={v: DEPLOYMENT_COLORS[k] for k, v in DEPLOYMENT_LABELS.items()},
        title="LCPR by Provider",
    )
    fig.update_layout(
        xaxis_tickangle=-45,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font_color="#e8e8e8",
        height=500,
    )
    st.plotly_chart(fig, use_container_width=True)


def _raw_cost_per_request(
    profile: WorkloadProfile, provider_name: str, calc: LCPRCalculator,
) -> float:
    """Compute raw token cost per request (no overhead) for a provider."""
    for p in calc.providers:
        if p.name == provider_name:
            if p.deployment_mode == "dedicated":
                monthly_gpu = p.gpu_hourly_rate * HOURS_PER_MONTH
                eff_tps = p.throughput_tps * (p.utilization or 0.4)
                if eff_tps > 0:
                    monthly_capacity = eff_tps * SECONDS_PER_MONTH
                    tokens_needed = profile.avg_output_tokens * profile.monthly_requests
                    import math
                    gpus = max(1, math.ceil(tokens_needed / monthly_capacity))
                    return (monthly_gpu * gpus) / profile.monthly_requests
                return 0
            input_cost = profile.avg_input_tokens * p.input_rate_per_m / 1_000_000
            output_cost = profile.avg_output_tokens * p.output_rate_per_m / 1_000_000
            return input_cost + output_cost
    return 0


def _tab_sensitivity(calc: LCPRCalculator, profile: WorkloadProfile) -> None:
    """Tab 2: Sensitivity analysis — vary one parameter, see LCPR impact."""
    st.subheader("Sensitivity Analysis")
    st.markdown(
        "Select a parameter to vary and see how LCPR changes across providers."
    )

    param = st.selectbox("Parameter to vary", [
        "retry_rate",
        "quality_gate_pass_rate",
        "avg_output_tokens",
        "avg_input_tokens",
        "monthly_requests",
    ])

    param_ranges = {
        "retry_rate": (0.0, 0.30, 0.01),
        "quality_gate_pass_rate": (0.60, 1.0, 0.02),
        "avg_output_tokens": (100, 3000, 100),
        "avg_input_tokens": (100, 8000, 200),
        "monthly_requests": (100_000, 10_000_000, 200_000),
    }

    lo, hi, step = param_ranges[param]
    if isinstance(lo, float):
        val_range = st.slider(
            f"Range for {param}", lo, hi,
            (lo, hi), step=step,
        )
    else:
        val_range = st.slider(
            f"Range for {param}", int(lo), int(hi),
            (int(lo), int(hi)), step=int(step),
        )

    # Build values list
    import numpy as np
    if isinstance(lo, float):
        values = list(np.arange(val_range[0], val_range[1] + step / 2, step))
    else:
        values = list(range(int(val_range[0]), int(val_range[1]) + 1, int(step)))

    # Select providers
    all_names = [p.name for p in calc.providers]
    # Default to a mix: one closed, one serverless, one dedicated
    defaults = []
    for mode in ["closed_api", "serverless_open", "dedicated"]:
        for p in calc.providers:
            if p.deployment_mode == mode:
                defaults.append(p.name)
                break

    selected = st.multiselect(
        "Providers to compare", all_names,
        default=defaults[:3],
    )

    if not selected or not values:
        st.info("Select providers and a range to see results.")
        return

    # Compute sensitivity for each provider
    chart_rows = []
    for pname in selected:
        for val in values:
            try:
                mod_profile = replace(profile, **{param: val})
                provider = next(p for p in calc.providers if p.name == pname)
                result = compute_lcpr(mod_profile, provider)
                chart_rows.append({
                    param: val,
                    "LCPR ($)": result.lcpr,
                    "Provider": pname,
                })
            except (ValueError, StopIteration):
                pass

    if not chart_rows:
        st.warning("No valid results for this configuration.")
        return

    fig = px.line(
        chart_rows,
        x=param,
        y="LCPR ($)",
        color="Provider",
        title=f"LCPR Sensitivity to {param}",
        markers=True,
    )
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font_color="#e8e8e8",
        height=500,
    )
    st.plotly_chart(fig, use_container_width=True)


def _tab_breakeven(calc: LCPRCalculator) -> None:
    """Tab 3: Break-even analysis between serverless and dedicated."""
    st.subheader("Break-Even Analysis")
    st.markdown(
        "Screen the daily output token volume where a dedicated GPU becomes "
        "cheaper than serverless at the stated utilization. This is the "
        "token-volume version of the dedicated break-even gate from Part 4, not "
        "a full migration payback model."
    )

    providers = calc.providers
    serverless = [p for p in providers if p.deployment_mode == "serverless_open"]
    dedicated = [p for p in providers if p.deployment_mode == "dedicated"]

    if not serverless or not dedicated:
        st.error("Need both serverless and dedicated providers in pricing data.")
        return

    col1, col2 = st.columns(2)
    with col1:
        sl_name = st.selectbox(
            "Serverless provider",
            [p.name for p in serverless],
        )
    with col2:
        ded_name = st.selectbox(
            "Dedicated provider",
            [p.name for p in dedicated],
        )

    sl = next(p for p in serverless if p.name == sl_name)
    ded = next(p for p in dedicated if p.name == ded_name)

    result = compute_break_even(sl, ded)

    st.markdown("---")

    if result.break_even_feasible:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(
                "Break-even",
                f"{result.break_even_daily_output_tokens / 1_000_000:.1f}M tokens/day",
            )
        with col2:
            st.metric("Daily GPU cost", f"${result.dedicated_daily_cost:.2f}")
        with col3:
            st.metric(
                "Serverless cost at break-even",
                f"${result.serverless_daily_cost_at_break_even:.2f}",
            )
    else:
        st.warning(
            f"**No break-even at {ded.utilization:.0%} utilization.** "
            f"Effective dedicated cost is ${result.effective_cost_per_m:.2f}/M tokens, "
            f"which exceeds the serverless rate of ${sl.output_rate_per_m:.2f}/M. "
            f"Required utilization for break-even: {result.required_utilization:.0%}."
        )
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Effective $/M (dedicated)", f"${result.effective_cost_per_m:.2f}")
        with col2:
            st.metric("Daily GPU cost", f"${result.dedicated_daily_cost:.2f}")
        with col3:
            st.metric("Required utilization", f"{result.required_utilization:.0%}")

    # Volume input
    st.markdown("---")
    your_volume = st.number_input(
        "Your daily output tokens",
        min_value=0, max_value=1_000_000_000,
        value=10_000_000, step=1_000_000,
    )

    # Cost vs volume chart
    import numpy as np
    if result.break_even_feasible:
        chart_max = result.break_even_daily_output_tokens * 2
    else:
        # Show chart up to GPU capacity to illustrate the gap
        chart_max = result.effective_capacity_tokens_per_day * 2
    volumes = np.linspace(0, chart_max, 100)
    sl_rate = sl.output_rate_per_m / 1_000_000
    ded_daily = result.dedicated_daily_cost

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=volumes / 1_000_000, y=volumes * sl_rate,
        name=sl_name, mode="lines",
        line=dict(color=DEPLOYMENT_COLORS["serverless_open"]),
    ))
    fig.add_trace(go.Scatter(
        x=volumes / 1_000_000,
        y=[ded_daily] * len(volumes),
        name=ded_name, mode="lines",
        line=dict(color=DEPLOYMENT_COLORS["dedicated"], dash="dash"),
    ))

    if result.break_even_feasible:
        # Crossover annotation
        be_m = result.break_even_daily_output_tokens / 1_000_000
        fig.add_vline(x=be_m, line_dash="dot", line_color="#e74c3c", opacity=0.5)
        fig.add_annotation(
            x=be_m, y=ded_daily,
            text=f"Break-even: {be_m:.1f}M tokens/day",
            showarrow=True, arrowhead=2,
            font=dict(color="#e8e8e8"),
        )
    else:
        # Capacity limit annotation
        cap_m = result.effective_capacity_tokens_per_day / 1_000_000
        fig.add_vline(x=cap_m, line_dash="dot", line_color="#f39c12", opacity=0.5)
        fig.add_annotation(
            x=cap_m, y=ded_daily,
            text=f"GPU capacity: {cap_m:.1f}M tokens/day",
            showarrow=True, arrowhead=2,
            font=dict(color="#e8e8e8"),
        )

    # Your volume marker
    your_m = your_volume / 1_000_000
    your_sl_cost = your_volume * sl_rate
    fig.add_trace(go.Scatter(
        x=[your_m], y=[min(your_sl_cost, ded_daily)],
        name="Your volume", mode="markers",
        marker=dict(size=12, color="#e74c3c", symbol="diamond"),
    ))

    fig.update_layout(
        title="Daily Cost vs Output Token Volume",
        xaxis_title="Daily Output Tokens (millions)",
        yaxis_title="Daily Cost ($)",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font_color="#e8e8e8",
        height=500,
    )
    st.plotly_chart(fig, use_container_width=True)

    # Verdict
    if your_volume > result.break_even_daily_output_tokens:
        st.success(
            f"At {your_m:.1f}M tokens/day, **dedicated is cheaper**. "
            f"Serverless would cost ${your_sl_cost:.2f}/day vs "
            f"${ded_daily:.2f}/day for dedicated."
        )
    else:
        st.info(
            f"At {your_m:.1f}M tokens/day, **serverless is cheaper**. "
            f"Serverless costs ${your_sl_cost:.2f}/day vs "
            f"${ded_daily:.2f}/day for dedicated."
        )


VENDOR_RECOMMENDATIONS = {
    "Compliance / Regulation": [
        ("US Federal / FedRAMP", "AWS Bedrock Gov or Azure Gov", "Only viable options"),
        ("EU data residency", "Nebius Finland/France, Scaleway, Mistral", ""),
        (
            "Healthcare / HIPAA",
            "Baseten (zero-retention default), Together or Fireworks with BAA",
            "",
        ),
        ("Finance + audit", "Baseten Writer reference or hyperscaler", ""),
    ],
    "Latency": [
        ("Raw decode speed", "Groq / Cerebras", "Custom silicon"),
        ("p95 TTFT <200ms", "Fireworks", "FireAttention + speculation"),
        ("Agentic multi-hop <500ms", "Together ATLAS or Fireworks FireOptimizer", ""),
    ],
    "Cost": [
        ("Minimize per-token", "DeepInfra", "10-30% below Together/Fireworks"),
        ("Minimize LCPR", "Run the LCPR Comparison tab with your actual workload", ""),
        ("Need Multi-LoRA", "Fireworks Multi-LoRA", "$0.20/M for 8B base"),
    ],
    "Model flexibility": [
        ("Broad model catalog", "Together AI", "Widest serverless catalog"),
        ("Custom Docker / TRT-LLM", "Baseten Truss", "Full runtime control"),
        ("Fine-tune + serve", "Together or Fireworks", "Customer owns weights"),
    ],
    "Operational simplicity": [
        ("No ML infra team", "Managed: Together, Fireworks, or Baseten dedicated", ""),
        ("Have infra engineers", "Neo-cloud + vLLM/SGLang (Lambda, CoreWeave, RunPod)", ""),
    ],
}

CONSTRAINT_COLORS = {
    "Compliance / Regulation": "#e8eaf6",
    "Latency": "#fff3e0",
    "Cost": "#e3f2fd",
    "Model flexibility": "#f3e5f5",
    "Operational simplicity": "#fce4ec",
}


def _vendor_selection_widget() -> None:
    """Interactive vendor selection based on primary constraint."""
    constraint = st.radio(
        "What's your primary constraint?",
        list(VENDOR_RECOMMENDATIONS.keys()),
        horizontal=True,
    )

    recommendations = VENDOR_RECOMMENDATIONS[constraint]
    bg = CONSTRAINT_COLORS[constraint]

    for sub_need, providers, note in recommendations:
        note_text = f" — *{note}*" if note else ""
        st.markdown(
            f'<div style="background:{bg}; color:#333; padding:12px 16px; '
            f'border-radius:8px; margin-bottom:8px;">'
            f"<strong>{sub_need}</strong><br/>"
            f"{providers}{note_text}</div>",
            unsafe_allow_html=True,
        )


def _tab_decision_trees() -> None:
    """Tab 4: Decision tree diagrams."""
    st.subheader("Decision Frameworks")
    st.markdown(
        "Decision trees from the book. Click any heading below to expand. "
        "Use the **expand icon** (top-right of each diagram) to view full-size."
    )

    svg_dir = Path(__file__).parent.parent / "decision-trees" / "svg"

    trees = [
        ("Migration Gate Framework", "migration_gate",
         "Three gates to determine whether to migrate from closed APIs "
         "to open-model inference: Volume (>$10K/mo spend), "
         "Specialization (fine-tuning, latency SLOs, custom arch), "
         "and Ownership (compliance, data residency, vendor risk)."),
        ("Inference Sourcing Patterns", "sourcing_patterns",
         "Four multi-source patterns: Workload-Segmented (different providers "
         "per workload), Capability-Arbitrage (best provider per capability), "
         "Primary-Fallback (same model, multiple providers), and "
         "Geo-Segmented (provider per region/regulation)."),
        ("Build vs Buy Spectrum", "build_buy_spectrum",
         "The inference stack has 7 layers. Each is an independent "
         "build-vs-buy decision. Most layers: buy. Routing Intelligence: hold."),
    ]

    for title, slug, description in trees:
        with st.expander(title, expanded=False):
            st.markdown(description)
            svg_path = svg_dir / f"{slug}.svg"
            if svg_path.exists():
                st.image(str(svg_path), use_container_width=True)
            else:
                st.warning(f"Diagram not found: {svg_path}")

    # Vendor Selection — interactive widget instead of static SVG
    with st.expander("Vendor Selection", expanded=False):
        st.markdown(
            "Which provider fits your workload? "
            "Select your primary constraint to see recommendations."
        )
        _vendor_selection_widget()


FACTOR_OPTIONS = {
    "workload_count": {
        "label": "How many model endpoints?",
        "choices": [
            "1-2 models, single use case",
            "3-5 models, 2-3 use cases",
            "6+ models, mixed requirements",
        ],
    },
    "prompt_portability": {
        "label": "Prompt complexity?",
        "choices": [
            "Simple prompts, no structured output",
            "JSON mode, moderate engineering",
            "Tool use, function calling, custom schemas",
        ],
    },
    "quality_infrastructure": {
        "label": "Evaluation infrastructure?",
        "choices": [
            "No formal evals",
            "Basic suite (<50 test cases)",
            "Comprehensive (500+ cases, regression, HITL)",
        ],
    },
    "latency_sensitivity": {
        "label": "Latency requirement?",
        "choices": [
            "Batch/async (>5s OK)",
            "Interactive (<2s P95)",
            "Real-time (<500ms P95, voice/streaming)",
        ],
    },
    "team_maturity": {
        "label": "Inference team maturity?",
        "choices": [
            "No ML infra expertise",
            "1-2 engineers with serving experience",
            "Dedicated inference team (3+)",
        ],
    },
    "integration_depth": {
        "label": "Integration complexity?",
        "choices": [
            "Single API call, stateless",
            "SDK + session state + caching",
            "Multi-system (gateway, observability, billing, compliance)",
        ],
    },
}

TIER_COLORS = {
    "Simple": "#A7C080",
    "Standard": "#D4A843",
    "Complex": "#e74c3c",
}


def _tab_readiness(calc: LCPRCalculator, profile: WorkloadProfile) -> None:
    """Tab 5: Migration readiness assessment."""
    st.subheader("Migration Readiness Assessment")
    st.markdown(
        "Score 6 factors to estimate migration complexity, timeline, "
        "and engineering investment. This is a readiness screen for the "
        "migration gates in Part 4; it does not replace measured candidate LCPR."
    )

    # Section 1: Complexity Assessment
    st.markdown("#### Complexity Factors")
    factors = []
    for name, opts in FACTOR_OPTIONS.items():
        choice = st.radio(
            opts["label"],
            opts["choices"],
            key=f"readiness_{name}",
            horizontal=True,
        )
        score = opts["choices"].index(choice) + 1
        factors.append(MigrationFactor(name=name, score=score))

    result = compute_readiness(factors)
    color = TIER_COLORS[result.tier]

    # Section 2: Score Output
    st.markdown("---")
    st.markdown("#### Assessment Result")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            f'<div style="text-align:center; padding:16px; '
            f'border:2px solid {color}; border-radius:8px;">'
            f'<div style="font-size:2em; font-weight:bold; color:{color};">'
            f'{result.total_score}/18</div>'
            f'<div style="color:#ccc;">Complexity Score</div>'
            f'<div style="color:{color}; font-weight:bold;">{result.tier}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with col2:
        st.metric(
            "Estimated Timeline",
            f"{result.timeline_weeks_min}-{result.timeline_weeks_max} weeks",
        )
    with col3:
        team_size = {
            "Simple": "1-2 engineers",
            "Standard": "2-3 engineers",
            "Complex": "Dedicated team or vendor partnership",
        }
        st.metric("Team Requirement", team_size[result.tier])

    st.info(f"**Recommended approach:** {result.recommendation}")

    # Section 3: Engineering Hours
    st.markdown("---")
    st.markdown("#### Engineering Investment by Deployment Mode")

    eng_rate = profile.engineer_hourly_cost
    rows = []
    for mode, label in [
        ("serverless", "Serverless Open-Weights"),
        ("managed_dedicated", "Managed Dedicated"),
        ("self_managed", "Self-Managed Dedicated"),
    ]:
        hours = get_engineering_hours(mode)
        setup_cost_lo = hours["setup_min"] * eng_rate
        setup_cost_hi = hours["setup_max"] * eng_rate
        monthly_cost_lo = hours["monthly_min"] * eng_rate
        monthly_cost_hi = hours["monthly_max"] * eng_rate
        rows.append({
            "Deployment Mode": label,
            "Setup (hours)": f"{hours['setup_min']}-{hours['setup_max']}",
            "Setup (cost)": f"${setup_cost_lo:,.0f}-${setup_cost_hi:,.0f}",
            "Monthly (hours)": f"{hours['monthly_min']}-{hours['monthly_max']}",
            "Monthly (cost)": f"${monthly_cost_lo:,.0f}-${monthly_cost_hi:,.0f}",
        })

    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.caption(
        f"Cost estimates use ${eng_rate:.0f}/hr engineer rate from sidebar profile. "
        "Setup hours: [MODELED] from provider onboarding documentation. "
        "Self-managed ongoing: [REPORTED] from community benchmarks."
    )

    # Section 4: Cost Impact
    st.markdown("---")
    st.markdown("#### Cost Impact")
    st.markdown(
        "Enter your current monthly inference spend to see projected savings "
        "and payback period. The target cost comes from the LCPR comparison "
        "(Tab 1) using your sidebar workload profile."
    )

    results = calc.compare(profile)
    if results:
        current_monthly = st.number_input(
            "Your current monthly inference spend ($)",
            min_value=0,
            max_value=10_000_000,
            value=0,
            step=1_000,
            key="readiness_current_spend",
        )

        if current_monthly > 0:
            # Suggest target based on tier
            serverless = [
                r for r in results if r.deployment_mode == "serverless_open"
            ]
            dedicated = [
                r for r in results if r.deployment_mode == "dedicated"
            ]

            if result.tier == "Simple" and serverless:
                target = serverless[0]
                target_label = "Serverless open-weights"
                target_mode = "serverless"
            elif result.tier != "Simple" and dedicated:
                target = dedicated[0]
                target_label = "Managed dedicated"
                target_mode = "managed_dedicated"
            elif serverless:
                target = serverless[0]
                target_label = "Serverless open-weights"
                target_mode = "serverless"
            else:
                target = results[0]
                target_label = "Best available"
                target_mode = "serverless"

            target_hours = get_engineering_hours(target_mode)
            setup_investment = (
                (target_hours["setup_min"] + target_hours["setup_max"])
                / 2 * eng_rate
            )
            monthly_eng_cost = (
                (target_hours["monthly_min"] + target_hours["monthly_max"])
                / 2 * eng_rate
            )
            # Total projected = inference cost + engineering overhead
            projected_total = target.monthly_cost + monthly_eng_cost
            net_monthly_savings = current_monthly - projected_total

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Current Spend", f"${current_monthly:,.0f}/mo")
            with col2:
                st.metric(
                    f"{target_label} (total)",
                    f"${projected_total:,.0f}/mo",
                    delta=(
                        f"-${net_monthly_savings:,.0f}/mo"
                        if net_monthly_savings > 0 else
                        f"+${-net_monthly_savings:,.0f}/mo"
                    ),
                    delta_color="normal" if net_monthly_savings > 0 else "inverse",
                    help=(
                        f"{target.provider_name}: "
                        f"${target.monthly_cost:,.0f} inference + "
                        f"${monthly_eng_cost:,.0f} engineering"
                    ),
                )
            with col3:
                payback = compute_payback(
                    current_monthly, projected_total, setup_investment,
                )
                if payback == float("inf"):
                    st.metric("Payback Period", "N/A",
                              help="Migration does not save money at this spend level")
                else:
                    st.metric("Payback Period", f"{payback:.1f} months",
                              help=f"One-time setup: ${setup_investment:,.0f}")
        else:
            st.info(
                "Enter your current monthly spend above to see projected "
                "savings. You can also compare providers directly in the "
                "LCPR Comparison tab."
            )

    # Section 5: Readiness Gaps
    if result.gaps:
        st.markdown("---")
        st.markdown("#### Readiness Gaps")
        for gap in result.gaps:
            st.warning(f"**{gap}**")


def _tab_goodput() -> None:
    """Tab 6: Goodput Frontier Test — compare routes by accepted work under SLO."""
    st.subheader("Goodput Frontier Test")
    st.markdown(
        "Compare two routes by cost per accepted result under SLO. "
        "A route with higher total cost can still win if it produces more "
        "accepted work. Goodput means requests that pass both latency and "
        "quality gates per second. Based on Derivation 5."
    )
    st.caption(
        "The sliders synthesize request rows from summary rates for quick "
        "screening. For publication or migration decisions, replace them with "
        "route-specific load test traces."
    )

    st.markdown("#### SLO Thresholds")
    col1, col2, col3 = st.columns(3)
    with col1:
        ttft_slo = st.number_input("TTFT SLO (ms)", 100, 5000, 800, step=100)
    with col2:
        tpot_slo = st.number_input("TPOT SLO (ms/tok)", 10, 200, 50, step=5)
    with col3:
        duration = st.number_input("Test duration (seconds)", 1, 600, 10, step=1)

    st.markdown("---")

    routes = {}
    for label, col in zip(["Route A", "Route B"], st.columns(2)):
        with col:
            st.markdown(f"#### {label}")
            n = st.number_input(
                "Total requests", 10, 10000, 100, step=10, key=f"{label}_n",
            )
            quality_rate = st.slider(
                "Quality pass rate", 0.0, 1.0, 0.85, 0.01, key=f"{label}_qr",
            )
            latency_rate = st.slider(
                "Latency pass rate (meet TTFT+TPOT SLO)", 0.0, 1.0, 0.90, 0.01,
                key=f"{label}_lr",
            )
            cost_per_req = st.number_input(
                "Cost per request ($)", 0.001, 1.0, 0.011, 0.001,
                format="%.3f", key=f"{label}_cpr",
            )
            ttft_pass = st.number_input(
                "TTFT when passing (ms)", 50, 5000, 500, step=50,
                key=f"{label}_ttft_pass",
            )
            ttft_fail = st.number_input(
                "TTFT when failing (ms)", 50, 5000, 1400, step=50,
                key=f"{label}_ttft_fail",
            )

            # Build synthetic requests from the summary stats
            n_quality_pass = int(n * quality_rate)
            n_latency_pass = int(n * latency_rate)
            # Accepted = pass both. Approximate intersection:
            n_both = int(n * quality_rate * latency_rate)
            requests = []
            for i in range(n):
                if i < n_both:
                    qp, ttft = True, float(ttft_pass)
                elif i < n_quality_pass:
                    qp, ttft = True, float(ttft_fail)
                elif i < n_quality_pass + (n_latency_pass - n_both):
                    qp, ttft = False, float(ttft_pass)
                else:
                    qp, ttft = False, float(ttft_fail)
                requests.append(GoodputRequest(
                    ttft_ms=ttft,
                    tpot_ms=float(tpot_slo - 10) if ttft == ttft_pass else float(tpot_slo + 20),
                    output_tokens=200,
                    quality_pass=qp,
                    cost=cost_per_req,
                ))
            routes[label] = requests

    st.markdown("---")
    st.markdown("#### Results")

    results = {}
    for label, reqs in routes.items():
        results[label] = compute_goodput(reqs, float(duration), float(ttft_slo), float(tpot_slo))

    cols = st.columns(2)
    for (label, r), col in zip(results.items(), cols):
        with col:
            st.markdown(f"**{label}**")
            st.metric("Accepted requests", r.accepted_requests)
            st.metric("Goodput (accepted/sec)", f"{r.goodput_rate:.1f}")
            st.metric("Cost per accepted", f"${r.cost_per_accepted:.4f}")
            st.metric("Total cost", f"${r.total_cost:.2f}")
            st.metric("Quality pass rate", f"{r.quality_pass_rate:.0%}")
            st.metric("Latency pass rate", f"{r.latency_pass_rate:.0%}")

    # Comparison chart
    chart_data = []
    for label, r in results.items():
        chart_data.append({
            "Route": label,
            "Metric": "Cost/accepted ($)",
            "Value": r.cost_per_accepted,
        })
    for label, r in results.items():
        chart_data.append({"Route": label, "Metric": "Goodput (req/s)", "Value": r.goodput_rate})

    winner = min(results, key=lambda k: results[k].cost_per_accepted)
    loser = max(results, key=lambda k: results[k].cost_per_accepted)
    if results[winner].cost_per_accepted < results[loser].cost_per_accepted:
        winner_cost = results[winner].cost_per_accepted
        loser_cost = results[loser].cost_per_accepted
        savings_pct = (1 - winner_cost / loser_cost) * 100
        st.success(
            f"**{winner}** wins on cost per accepted result "
            f"(${results[winner].cost_per_accepted:.4f} vs "
            f"${results[loser].cost_per_accepted:.4f}, "
            f"{savings_pct:.0f}% cheaper per accepted unit)."
        )


def _tab_trace_to_margin() -> None:
    """Tab 7: Trace-to-Margin reconciliation — Derivation 6."""
    st.subheader("Trace-to-Margin Review")
    st.markdown(
        "Reconcile trace-derived inference cost with the provider invoice, "
        "add non-inference cost layers, compute LCPR, and calculate gross margin. "
        "Based on Derivation 6."
    )
    st.caption(
        "This is the reconciled LCPR path from the book. It is the right view "
        "when you have trace cost, invoice amount, eval spend, human escalation "
        "cost, ops allocation, and accepted work count for the same period."
    )

    st.markdown("#### Cost Components")
    col1, col2 = st.columns(2)
    with col1:
        trace_cost = st.number_input(
            "Trace-derived inference cost ($)", 0.0, 100000.0, 14.20,
            format="%.2f",
        )
        invoice_amount = st.number_input(
            "Provider invoice amount ($)", 0.0, 100000.0, 14.85,
            format="%.2f",
        )
        eval_cost = st.number_input(
            "Eval grader cost ($)", 0.0, 100000.0, 0.80,
            format="%.2f",
        )
    with col2:
        human_cost = st.number_input(
            "Human escalation cost ($)", 0.0, 1000000.0, 100.00,
            format="%.2f",
        )
        ops_cost = st.number_input(
            "Ops overhead ($)", 0.0, 100000.0, 25.00,
            format="%.2f",
        )

    st.markdown("#### Volume")
    col1, col2, col3 = st.columns(3)
    with col1:
        total_attempts = st.number_input(
            "Total attempts", 1, 10000000, 1000, step=100,
        )
    with col2:
        accepted_units = st.number_input(
            "Accepted units", 1, 10000000, 820, step=10,
        )
    with col3:
        revenue_per_unit = st.number_input(
            "Revenue per accepted unit ($)", 0.0, 10000.0, 0.25,
            format="%.2f",
        )

    st.markdown("---")

    result = compute_trace_to_margin(
        trace_cost=trace_cost,
        invoice_amount=invoice_amount,
        eval_cost=eval_cost,
        human_cost=human_cost,
        ops_cost=ops_cost,
        total_attempts=total_attempts,
        accepted_units=accepted_units,
        revenue_per_unit=revenue_per_unit,
    )

    # Summary metrics
    st.markdown("#### Results")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("LCPR", f"${result.lcpr:.4f}")
    with col2:
        st.metric("Naive cost/unit", f"${result.naive_cost_per_unit:.4f}")
    with col3:
        st.metric("LCPR / Naive", f"{result.lcpr_to_naive_ratio:.1f}x")
    with col4:
        delta_color = "normal" if result.gross_margin >= 0 else "inverse"
        st.metric("Gross margin", f"${result.gross_margin:.2f}", delta_color=delta_color)

    # Cost waterfall
    st.markdown("#### Cost Waterfall")
    waterfall_data = [
        ("Trace inference", result.trace_cost),
        ("Invoice delta", result.delta),
        ("Eval grader", result.eval_cost),
        ("Human escalation", result.human_cost),
        ("Ops overhead", result.ops_cost),
    ]

    fig = go.Figure(go.Waterfall(
        name="Cost",
        orientation="v",
        x=[w[0] for w in waterfall_data],
        y=[w[1] for w in waterfall_data],
        connector={"line": {"color": "rgb(63, 63, 63)"}},
        increasing={"marker": {"color": "#e74c3c"}},
        totals={"marker": {"color": "#7FBBB3"}},
        text=[f"${w[1]:.2f}" for w in waterfall_data],
        textposition="outside",
    ))
    fig.update_layout(
        title=f"Loaded Cost Buildup: ${result.total_loaded_cost:.2f}",
        showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font_color="#e8e8e8",
        height=400,
    )
    st.plotly_chart(fig, use_container_width=True)

    # Component breakdown table
    st.markdown("#### Component Breakdown")
    total = result.total_loaded_cost
    rows = [
        {"Component": "Inference (trace)", "Amount": f"${result.trace_cost:.2f}",
         "% of LCPR": f"{result.trace_cost / total * 100:.1f}%"},
        {"Component": "Invoice delta", "Amount": f"${result.delta:.2f}",
         "% of LCPR": f"{result.delta / total * 100:.1f}%"},
        {"Component": "Eval grader", "Amount": f"${result.eval_cost:.2f}",
         "% of LCPR": f"{result.eval_cost / total * 100:.1f}%"},
        {"Component": "Human escalation", "Amount": f"${result.human_cost:.2f}",
         "% of LCPR": f"{result.human_cost / total * 100:.1f}%"},
        {"Component": "Ops overhead", "Amount": f"${result.ops_cost:.2f}",
         "% of LCPR": f"{result.ops_cost / total * 100:.1f}%"},
        {"Component": "**Total**", "Amount": f"**${total:.2f}**",
         "% of LCPR": "**100%**"},
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    # Margin summary
    st.markdown("#### Margin Analysis")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Revenue", f"${result.revenue:.2f}")
    with col2:
        st.metric("Total loaded cost", f"${result.total_loaded_cost:.2f}")
    with col3:
        st.metric("Margin %", f"{result.gross_margin_pct:.1%}")


def _tab_cache_policy_gate() -> None:
    """Cache break-even and savings view."""
    st.subheader("Cache Policy Gate")
    st.caption(
        "Modeled cache economics. Replace defaults with measured prefix size, TTL, "
        "and provider cache prices before using this for a production decision. "
        "Break-even reuse is the number of reads needed for one cache write plus "
        "storage to beat sending the prefix uncached each time."
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        prefix_tokens = st.number_input(
            "Cacheable prefix tokens", 0, 1_000_000, 50_000, step=1_000,
        )
        uncached_price = st.number_input(
            "Uncached input price ($/M)", 0.0, 100.0, 3.00, step=0.10,
            format="%.2f",
        )
    with col2:
        write_price = st.number_input(
            "Cache write price ($/M)", 0.0, 100.0, 3.75, step=0.10,
            format="%.2f",
        )
        read_price = st.number_input(
            "Cache read price ($/M)", 0.0, 100.0, 0.30, step=0.05,
            format="%.2f",
        )
    with col3:
        storage_price = st.number_input(
            "Storage price ($/M-hour)", 0.0, 100.0, 0.0, step=0.01,
            format="%.2f",
        )
        storage_hours = st.number_input(
            "Retention hours", 0.0, 720.0, 0.0, step=0.25,
            format="%.2f",
        )

    result = compute_cache_break_even(
        prefix_tokens=int(prefix_tokens),
        uncached_input_price_per_m=float(uncached_price),
        cache_write_price_per_m=float(write_price),
        cache_read_price_per_m=float(read_price),
        storage_price_per_m_hour=float(storage_price),
        storage_hours=float(storage_hours),
    )

    st.markdown("#### Result")
    col1, col2, col3 = st.columns(3)
    with col1:
        if result.break_even_requests == float("inf"):
            st.metric("Break-even reuse", "Never")
        else:
            st.metric("Break-even reuse", f"{result.break_even_requests:.2f} requests")
    with col2:
        st.metric("Storage cost", f"${result.storage_cost:.4f}")
    with col3:
        st.metric("Savings at 10 uses", f"${result.savings_at_n[10]:.4f}")

    rows = [
        {"Reuse count": n, "Savings vs uncached": f"${savings:.4f}"}
        for n, savings in result.savings_at_n.items()
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)


def _tab_kv_capacity() -> None:
    """KV cache memory sizing view."""
    st.subheader("KV Capacity Envelope")
    st.caption(
        "Derived architecture math. It estimates KV memory capacity, not provider "
        "queueing, scheduler behavior, or guaranteed concurrency."
    )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        n_layers = st.number_input("Layers", 1, 256, 80, step=1)
        n_kv_heads = st.number_input("KV heads", 1, 256, 8, step=1)
    with col2:
        head_dim = st.number_input("Head dimension", 1, 1024, 128, step=8)
        element_bytes = st.selectbox("KV dtype bytes", [1, 2, 4], index=1)
    with col3:
        kv_pool_gb = st.number_input("KV pool (GB)", 0.1, 1024.0, 40.0, step=1.0)
        resident_tokens = st.number_input(
            "Resident tokens / sequence", 1, 1_000_000, 4096, step=1024,
        )
    with col4:
        headroom = st.slider("Headroom", 0.0, 0.50, 0.10, step=0.05)
        weight_gb = st.number_input("Weight memory (GB, optional)", 0.0, 2048.0, 140.0, step=1.0)

    result = compute_kv_sizing(
        n_layers=int(n_layers),
        n_kv_heads=int(n_kv_heads),
        head_dim=int(head_dim),
        element_bytes=int(element_bytes),
        kv_pool_bytes=float(kv_pool_gb) * 1_000_000_000,
        resident_tokens=int(resident_tokens),
        headroom_fraction=float(headroom),
        weight_bytes=float(weight_gb) * 1_000_000_000,
    )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("KV bytes/token", f"{result.kv_bytes_per_token:,.0f}")
    with col2:
        st.metric("KV per sequence", f"{result.total_kv_memory_per_seq / 1e9:.2f} GB")
    with col3:
        st.metric("Max live sequences", f"{result.max_live_sequences:,}")
    with col4:
        if result.context_length_at_weight_parity:
            st.metric("Weight parity context", f"{result.context_length_at_weight_parity:,}")
        else:
            st.metric("Weight parity context", "N/A")


def _tab_routefit_matrix() -> None:
    """Template view for workload-route feasibility decisions."""
    st.subheader("RouteFit Matrix")
    st.caption(
        "Template view. It records route feasibility and evidence quality; it does "
        "not claim a route is production-ready without measured or modeled inputs."
    )
    st.markdown(
        "**Evidence labels:** measured = trace/eval data from the route, "
        "modeled = formula-backed estimate from explicit inputs, estimated = "
        "placeholder assumption that still needs validation."
    )

    default_rows = [
        {
            "Workload": "support-chat",
            "Route": "closed-api",
            "Feasibility": "pass",
            "Evidence": "measured",
            "LCPR": 0.234,
            "Blocker": "",
        },
        {
            "Workload": "support-chat",
            "Route": "serverless-open",
            "Feasibility": "measure",
            "Evidence": "estimated",
            "LCPR": 0.168,
            "Blocker": "quality gate not measured",
        },
        {
            "Workload": "coding-agent",
            "Route": "batch-api",
            "Feasibility": "pass",
            "Evidence": "modeled",
            "LCPR": 0.047,
            "Blocker": "",
        },
    ]
    rows = st.data_editor(default_rows, use_container_width=True, num_rows="dynamic")

    candidates = [
        row for row in rows
        if row.get("Feasibility") == "pass"
        and row.get("Evidence") in {"measured", "modeled"}
        and row.get("LCPR") is not None
    ]
    if not candidates:
        st.warning("No passable route has measured or modeled LCPR evidence.")
        return

    winner = min(candidates, key=lambda row: float(row["LCPR"]))
    st.success(
        "Current lowest-evidence-qualified route: "
        f"{winner['Workload']} -> {winner['Route']} at ${float(winner['LCPR']):.4f} LCPR."
    )


REQUIRED_TRACE_FIELDS = (
    "request_id",
    "workload_id",
    "route",
    "input_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
    "output_tokens",
    "trace_cost",
    "quality_pass",
    "latency_pass",
    "accepted_work_unit",
)


def _tab_trace_event_schema() -> None:
    """Trace schema template and local validator."""
    st.subheader("Trace Event Schema")
    st.caption(
        "Template view. Paste a representative event to check whether it carries "
        "the fields needed for LCPR and trace-to-margin reconciliation."
    )

    sample = {
        "request_id": "req_001",
        "workload_id": "support-chat-v2",
        "route": "anthropic/sonnet",
        "input_tokens": 2800,
        "cache_creation_input_tokens": 1800,
        "cache_read_input_tokens": 0,
        "output_tokens": 350,
        "trace_cost": 0.142,
        "quality_pass": True,
        "latency_pass": True,
        "accepted_work_unit": "accepted_resolution",
    }
    raw = st.text_area("Trace event JSON", value=json.dumps(sample, indent=2), height=300)

    try:
        event = json.loads(raw)
    except json.JSONDecodeError as exc:
        st.error(f"Invalid JSON: {exc}")
        return

    missing = [field for field in REQUIRED_TRACE_FIELDS if field not in event]
    rows = [
        {
            "Field": field,
            "Present": field in event,
            "Value": event.get(field, ""),
        }
        for field in REQUIRED_TRACE_FIELDS
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)
    if missing:
        st.warning(f"Missing fields: {', '.join(missing)}")
    else:
        st.success("Trace event has the required LCPR fields.")


def _flatten_pricing_rows(pricing_data: dict) -> list[dict[str, object]]:
    """Flatten provider pricing YAML into display rows."""
    rows: list[dict[str, object]] = []
    for group_name in ("closed_apis", "serverless_open"):
        for provider_data in pricing_data.get(group_name, {}).values():
            provider = provider_data.get("name", "unknown")
            for model_data in provider_data.get("models", {}).values():
                rows.append({
                    "Provider": provider,
                    "Model": model_data.get("name", "unknown"),
                    "Mode": group_name,
                    "Input $/M": model_data.get("input_rate"),
                    "Output $/M": model_data.get("output_rate"),
                    "Cached $/M": model_data.get("cached_input_rate"),
                    "Evidence": model_data.get("evidence", "comment_only"),
                })
    for provider_data in pricing_data.get("dedicated_gpu", {}).values():
        provider = provider_data.get("name", "unknown")
        for gpu_data in provider_data.get("gpus", {}).values():
            rows.append({
                "Provider": provider,
                "Model": gpu_data.get("name", "unknown"),
                "Mode": "dedicated_gpu",
                "Input $/M": None,
                "Output $/M": None,
                "Cached $/M": None,
                "Evidence": gpu_data.get("evidence", "comment_only"),
            })
    return rows


def _tab_source_snapshot_browser() -> None:
    """Pricing/source snapshot browser."""
    st.subheader("Source Snapshot Browser")
    st.caption(
        "Displays the local pricing snapshot and flags rows with missing required "
        "pricing fields. Use it as an audit surface, not a live price refresh. "
        "Provider-pricing evidence is currently stored in YAML comments, so the "
        "table marks those rows as comment_only until evidence metadata is "
        "promoted to machine-readable fields."
    )

    pricing_data = yaml.safe_load(PRICING_PATH.read_text()) or {}
    rows = _flatten_pricing_rows(pricing_data)
    for row in rows:
        needs_token_prices = row["Mode"] != "dedicated_gpu"
        missing = needs_token_prices and (
            row["Input $/M"] is None or row["Output $/M"] is None
        )
        row["Status"] = "incomplete" if missing else "usable"

    st.markdown(f"**Pricing file:** `{PRICING_PATH.name}`")
    st.dataframe(rows, use_container_width=True, hide_index=True)

    snapshot_files = (
        sorted(p.name for p in SNAPSHOT_DIR.glob("*.yaml"))
        if SNAPSHOT_DIR.exists()
        else []
    )
    st.markdown("#### Source snapshot files")
    if snapshot_files:
        st.write(", ".join(snapshot_files))
    else:
        st.warning(f"No source snapshot directory found at {SNAPSHOT_DIR}.")

    st.markdown("#### View registry")
    st.dataframe(registry_rows(), use_container_width=True, hide_index=True)


def _tab_operating_views() -> None:
    """Grouped finance, ops, latency, usage, and compliance templates."""
    st.subheader("Operating Views")
    st.caption(
        "Template views for operating review. These are user-input calculators, "
        "not automated billing, telemetry, or compliance integrations."
    )

    tabs = st.tabs([
        "Spend Movement",
        "Commitment",
        "Variance",
        "Account Margin",
        "Usage Signals",
        "Security",
        "Latency",
    ])

    with tabs[0]:
        baseline = st.number_input("Baseline monthly spend ($)", 0.0, 10_000_000.0, 100_000.0)
        volume_delta = st.slider("Volume delta", -1.0, 2.0, 0.05, step=0.01)
        price_delta = st.slider("Unit price delta", -1.0, 2.0, -0.18, step=0.01)
        mix_delta = st.slider("Mix/cache/quality delta", -1.0, 2.0, 0.10, step=0.01)
        forecast = baseline * (1 + volume_delta) * (1 + price_delta) * (1 + mix_delta)
        st.metric("Forecast spend", f"${forecast:,.0f}", delta=f"${forecast - baseline:,.0f}")

    with tabs[1]:
        committed_hours = st.number_input("Committed GPU hours/month", 0.0, 100_000.0, 720.0)
        used_hours = st.number_input("Used GPU hours/month", 0.0, 100_000.0, 430.0)
        hourly_rate = st.number_input("Committed hourly rate ($)", 0.0, 1000.0, 4.00)
        utilization = used_hours / committed_hours if committed_hours else 0.0
        idle_cost = max(committed_hours - used_hours, 0.0) * hourly_rate
        st.metric("Commitment utilization", f"{utilization:.1%}")
        st.metric("Idle committed cost", f"${idle_cost:,.0f}")

    with tabs[2]:
        expected = st.number_input("Expected monthly loaded cost ($)", 0.0, 10_000_000.0, 100_000.0)
        actual = st.number_input("Actual monthly loaded cost ($)", 0.0, 10_000_000.0, 118_000.0)
        threshold = st.slider("Investigation threshold", 0.0, 1.0, 0.05, step=0.01)
        variance = (actual - expected) / expected if expected else 0.0
        st.metric("Variance", f"{variance:.1%}", delta=f"${actual - expected:,.0f}")
        if abs(variance) >= threshold:
            st.warning("Variance exceeds the investigation threshold.")
        else:
            st.success("Variance is within threshold.")

    with tabs[3]:
        revenue = st.number_input("Account revenue ($)", 0.0, 100_000_000.0, 45_000.0)
        loaded_cost = st.number_input("Loaded inference cost ($)", 0.0, 100_000_000.0, 19_150.0)
        margin = revenue - loaded_cost
        margin_pct = margin / revenue if revenue else 0.0
        st.metric("Gross margin", f"${margin:,.0f}")
        st.metric("Gross margin %", f"{margin_pct:.1%}")

    with tabs[4]:
        requests = st.number_input("Requests", 0, 100_000_000, 100_000)
        accepted = st.number_input("Accepted work units", 0, 100_000_000, 82_000)
        cache_hit = st.slider("Cache hit rate", 0.0, 1.0, 0.35, step=0.01)
        retry = st.slider("Retry rate", 0.0, 1.0, 0.03, step=0.01)
        acceptance = accepted / requests if requests else 0.0
        st.dataframe(
            [
                {"Signal": "Acceptance rate", "Value": f"{acceptance:.1%}"},
                {"Signal": "Cache hit rate", "Value": f"{cache_hit:.1%}"},
                {"Signal": "Retry rate", "Value": f"{retry:.1%}"},
            ],
            use_container_width=True,
            hide_index=True,
        )

    with tabs[5]:
        data_residency = st.checkbox("Data residency required", value=True)
        zero_retention = st.checkbox("Zero data retention required", value=True)
        baa_required = st.checkbox("BAA or regulated-data agreement required", value=False)
        public_batch_ok = st.checkbox("Public batch endpoint allowed", value=False)
        blockers = []
        if data_residency:
            blockers.append("verify region and routing controls")
        if zero_retention:
            blockers.append("verify retention setting in contract/API")
        if baa_required:
            blockers.append("verify BAA or equivalent agreement")
        if not public_batch_ok:
            blockers.append("exclude public batch routes for restricted data")
        st.dataframe(
            [{"Constraint": blocker, "Status": "must verify"} for blocker in blockers],
            use_container_width=True,
            hide_index=True,
        )

    with tabs[6]:
        network_ms = st.number_input("Network + app overhead (ms)", 0, 10_000, 250)
        ttft_ms = st.number_input("TTFT (ms)", 0, 10_000, 500)
        decode_ms = st.number_input("Decode time (ms)", 0, 60_000, 1200)
        tool_ms = st.number_input("Tool/retrieval time (ms)", 0, 60_000, 600)
        slo_ms = st.number_input("End-to-end SLO (ms)", 1, 120_000, 5000)
        total_ms = network_ms + ttft_ms + decode_ms + tool_ms
        st.metric("End-to-end latency", f"{total_ms:,} ms")
        if total_ms <= slo_ms:
            st.success("Latency model is within SLO.")
        else:
            st.warning("Latency model exceeds SLO.")


def main() -> None:
    st.set_page_config(
        page_title="Production Inference Economics Calculator",
        page_icon="$",
        layout="wide",
    )

    st.title("Production Inference Economics Calculator")
    st.markdown(
        "Companion calculator for "
        "[Production Inference Economics: A Field Guide]"
        "(https://sohailmo.ai/inference-field-guide/). "
        "Bundled pricing rows are snapshots last verified in May 2026."
    )

    with st.expander("What is LCPR?", expanded=False):
        st.latex(
            r"\text{LCPR} = \frac{C_{\text{trace}} + \Delta_{\text{invoice}}"
            r" + C_{\text{eval}} + C_{\text{human}} + C_{\text{ops}}}"
            r"{A_{\text{accepted work}}}"
        )
        st.markdown(
            "**Loaded Cost Per Result** is loaded cost divided by accepted work "
            "units. The denominator is not raw requests: a unit only counts when "
            "it passes the workload's quality, latency, reliability, and policy "
            "gates.\n\n"
            "- **LCPR Comparison** is a profile estimator for screening providers. "
            "It models token spend, retries, quality failures, repair cost, and "
            "engineering overhead from sidebar assumptions.\n"
            "- **Trace-to-Margin** is the reconciled book formula. Use it when "
            "you have trace cost, invoice delta, eval cost, human escalation, ops "
            "allocation, and accepted work count for the same period.\n\n"
            "Full methodology: "
            "[Part 1 of the book]"
            "(https://sohailmo.ai/inference-field-guide/"
            "#part-1-the-economic-unit)."
        )

    calc = LCPRCalculator(PRICING_PATH)

    # Load profile from permalink query param if present
    _config_param = st.query_params.get("config")
    _permalink_profile = None
    if _config_param:
        try:
            _permalink_profile = decode_profile(_config_param)
            st.info("Loaded profile from shared link. Adjust in sidebar to override.")
        except (ValueError, Exception):
            st.warning("Invalid shared link — using default profile.")

    profile, profile_name = _build_profile_from_sidebar()

    # If permalink loaded, override sidebar profile (sidebar defaults win on next interaction)
    if _permalink_profile is not None and "config" in st.query_params:
        profile = _permalink_profile

    # Share button
    st.sidebar.markdown("---")
    _encoded = encode_profile(profile)
    _share_url = f"https://inference-field-guide.streamlit.app/?config={_encoded}"
    st.sidebar.text_input(
        "Share this config",
        value=_share_url,
        help="Copy this URL to share your current workload profile.",
    )

    # Assumption confidence tracker
    _confidence = default_confidence()
    _status_options = sorted(VALID_STATUSES)
    with st.sidebar.expander("Assumption Confidence", expanded=False):
        st.markdown(
            "Tag each input with how it was measured. "
            "An LCPR built on assumptions is a hypothesis; "
            "one built on measurements is a budget."
        )
        for field in _confidence.statuses:
            label = field.replace("_", " ").title()
            new_status = st.selectbox(
                label, options=_status_options,
                index=_status_options.index("assumed"),
                key=f"conf_{field}",
            )
            _confidence.set(field, new_status)
        measured = _confidence.measured_count
        total = len(_confidence.statuses)
        st.progress(measured / total if total else 0)
        st.caption(f"{measured}/{total} inputs measured")

    # Pricing snapshot panel
    with st.expander("Pricing Data (click to verify)", expanded=False):
        _pricing_data = yaml.safe_load(PRICING_PATH.read_text()) or {}
        _verified = _pricing_data.get("_meta", {}).get("last_verified", "unknown")
        # Extract verification date from YAML comment (line 4)
        _yaml_lines = PRICING_PATH.read_text().splitlines()
        for _line in _yaml_lines[:10]:
            if "Last verified:" in _line:
                _verified = _line.split("Last verified:")[-1].strip()
                break
        st.markdown(f"**Data last verified: {_verified}**")
        st.markdown("All prices from public vendor pricing pages. "
                     "[Report stale pricing →]"
                     "(https://github.com/sohailm25/inference-field-guide/issues)")
        providers = calc.providers
        rows = []
        for p in providers:
            if p.deployment_mode == "dedicated":
                price_str = f"${p.gpu_hourly_rate:.2f}/hr GPU"
            else:
                price_str = f"${p.input_rate_per_m:.2f} / ${p.output_rate_per_m:.2f}"
            rows.append({
                "Provider": p.name,
                "Mode": p.deployment_mode.replace("_", " ").title(),
                "Pricing (input/output per M tokens)": price_str,
            })
        st.table(rows)

    tabs = st.tabs(IMPLEMENTED_APP_TABS)

    with tabs[0]:
        _tab_comparison(calc, profile)
    with tabs[1]:
        _tab_sensitivity(calc, profile)
    with tabs[2]:
        _tab_breakeven(calc)
    with tabs[3]:
        _tab_readiness(calc, profile)
    with tabs[4]:
        _tab_decision_trees()
    with tabs[5]:
        _tab_goodput()
    with tabs[6]:
        _tab_trace_to_margin()
    with tabs[7]:
        _tab_cache_policy_gate()
    with tabs[8]:
        _tab_kv_capacity()
    with tabs[9]:
        _tab_routefit_matrix()
    with tabs[10]:
        _tab_trace_event_schema()
    with tabs[11]:
        _tab_source_snapshot_browser()
    with tabs[12]:
        _tab_operating_views()


if __name__ == "__main__":
    main()
