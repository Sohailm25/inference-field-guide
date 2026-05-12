# ABOUTME: Streamlit web interface for the LCPR calculator.
# ABOUTME: Interactive UI for workload profiling, provider comparison, and crossover analysis.

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

# Ensure project root is on sys.path (needed when not pip-installed)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from calculator.lcpr import (
    LCPRCalculator,
    WorkloadProfile,
    compute_break_even,
    compute_lcpr,
    load_provider_pricing,
)
from calculator.workload_profiles import PROFILES, get_profile, list_profiles

PRICING_PATH = Path(__file__).parent / "provider_pricing.yaml"

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
        eng_hours = st.sidebar.slider("Engineering hours/month", 0, 80, 8)
        eng_rate = st.sidebar.slider("Engineer hourly cost ($)", 50, 250, 100, step=10)

        profile = WorkloadProfile(
            avg_input_tokens=input_tokens,
            avg_output_tokens=output_tokens,
            monthly_requests=monthly_requests,
            retry_rate=retry_rate,
            quality_gate_pass_rate=quality_gate,
            repair_cost_per_failure=0.002,
            engineering_hours_per_month=eng_hours,
            engineer_hourly_cost=eng_rate,
            cache_hit_rate=cache_hit_rate,
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

        profile = replace(
            profile,
            monthly_requests=monthly_requests,
            retry_rate=retry_rate,
            quality_gate_pass_rate=quality_gate,
        )

    return profile, profile_name


def _tab_comparison(calc: LCPRCalculator, profile: WorkloadProfile) -> None:
    """Tab 1: LCPR comparison table and bar chart."""
    st.subheader("LCPR Comparison")
    st.markdown(
        "Loaded Cost Per Request across all providers, ranked lowest to highest. "
        "LCPR includes token cost, retries, repair, and engineering overhead."
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
            "Raw $/req": f"${raw_cost:.4f}",
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
                monthly_gpu = p.gpu_hourly_rate * 24 * 30
                eff_tps = p.throughput_tps * (p.utilization or 0.4)
                if eff_tps > 0:
                    monthly_capacity = eff_tps * 3600 * 24 * 30
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
        "Find the daily output token volume where dedicated GPU becomes "
        "cheaper than serverless. Based on the formula in Part 1 of the essay."
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

    # Volume input
    st.markdown("---")
    your_volume = st.number_input(
        "Your daily output tokens",
        min_value=0, max_value=1_000_000_000,
        value=10_000_000, step=1_000_000,
    )

    # Cost vs volume chart
    import numpy as np
    volumes = np.linspace(0, result.break_even_daily_output_tokens * 2, 100)
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

    # Crossover annotation
    be_m = result.break_even_daily_output_tokens / 1_000_000
    fig.add_vline(x=be_m, line_dash="dot", line_color="#e74c3c", opacity=0.5)
    fig.add_annotation(
        x=be_m, y=ded_daily,
        text=f"Break-even: {be_m:.1f}M tokens/day",
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
        ("Healthcare / HIPAA", "Baseten (zero-retention default), Together or Fireworks with BAA", ""),
        ("Finance + audit", "Baseten Writer reference or hyperscaler", ""),
    ],
    "Latency": [
        ("Raw decode speed", "Groq / Cerebras", "Custom silicon"),
        ("p95 TTFT <200ms", "Fireworks", "FireAttention + speculation"),
        ("Agentic multi-hop <500ms", "Together ATLAS or Fireworks FireOptimizer", ""),
    ],
    "Cost": [
        ("Minimize per-token", "DeepInfra", "10-30% below Together/Fireworks"),
        ("Minimize LCPR", "Run the LCPR calculator (Tab 1) with your actual workload", ""),
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
        "Decision trees from the essay. Click any heading below to expand. "
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


def main() -> None:
    st.set_page_config(
        page_title="Inference Field Guide Calculator",
        page_icon="$",
        layout="wide",
    )

    st.title("Inference Field Guide Calculator")
    st.markdown(
        "Interactive LCPR calculator from "
        "[The Honest Field Guide to Production Inference]"
        "(https://sohailmo.ai/inference-field-guide/). "
        "All numbers use May 2026 public pricing."
    )

    calc = LCPRCalculator(PRICING_PATH)
    profile, profile_name = _build_profile_from_sidebar()

    tab1, tab2, tab3, tab4 = st.tabs([
        "LCPR Comparison",
        "Sensitivity Analysis",
        "Break-Even Analysis",
        "Decision Trees",
    ])

    with tab1:
        _tab_comparison(calc, profile)
    with tab2:
        _tab_sensitivity(calc, profile)
    with tab3:
        _tab_breakeven(calc)
    with tab4:
        _tab_decision_trees()


if __name__ == "__main__":
    main()
