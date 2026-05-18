# ABOUTME: Marimo notebook app — production inference economics calculator.
# ABOUTME: Replaces the legacy Streamlit app.py. 7 views (Landing + 6 tools).

import marimo

__generated_with = "0.10.0"
app = marimo.App(width="medium", app_title="Production Inference Economics")


@app.cell
def _imports():
    import marimo as mo
    import plotly.express as px
    import plotly.graph_objects as go
    import yaml
    from dataclasses import replace
    from pathlib import Path

    from calculator.lcpr import (
        LCPRCalculator,
        WorkloadProfile,
        compute_break_even,
        compute_cache_break_even,
        compute_goodput,
        compute_kv_sizing,
        compute_lcpr,
        compute_trace_to_margin,
    )
    from calculator.workload_profiles import get_profile, list_profiles
    from calculator.view_registry import MarimoView, MARIMO_VIEW_META, PARAM_LABELS
    return (
        LCPRCalculator, WorkloadProfile, compute_break_even, compute_cache_break_even,
        compute_goodput, compute_kv_sizing, compute_lcpr, compute_trace_to_margin,
        MarimoView, MARIMO_VIEW_META, PARAM_LABELS,
        get_profile, list_profiles, mo, px, go, yaml, replace, Path,
    )


@app.cell
def _pricing(Path, yaml, LCPRCalculator):
    """Load pricing data once at app start. LCPRCalculator takes a Path,
    not a loaded dict (see lcpr.py:711). The raw pricing dict is also
    returned for views that need direct yaml access."""
    pricing_path = Path(__file__).parent / "provider_pricing.yaml"
    calc = LCPRCalculator(pricing_path)
    pricing = yaml.safe_load(pricing_path.read_text())
    return calc, pricing


@app.cell
def _theme_css(mo):
    """Inject palette + typography (moss/oxblood + Newsreader/JBMono).
    Loads marimo-theme.css from the static/ directory so the Marimo chrome
    inherits the book design.
    """
    mo.Html("""
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href='https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Newsreader:opsz,wght@6..72,400;6..72,500;6..72,700&family=JetBrains+Mono:wght@400;500;600;700&display=swap' rel='stylesheet'>
    <style>
      /* placeholder — full theme will move to calculator/static/marimo-theme.css in Task 17 */
      body { background: #faf5e9; color: #1a1a1a; font-family: 'Newsreader', Georgia, serif; }
    </style>
    """)
    return


# ── Landing view (Task 5) ──
@app.cell
def _landing(mo, calc, get_profile, list_profiles, MARIMO_VIEW_META):
    """Mad-libs Landing — replaces the legacy 'Start Here' glossary.
    Sentence with editable slots: model · workload · token mix · filter.
    Below the sentence, a one-paragraph verdict computed from defaults.
    """
    profile_names = list_profiles()
    workload_dd = mo.ui.dropdown(
        options=profile_names,
        value="saas_chat" if "saas_chat" in profile_names else profile_names[0],
        label="workload",
    )

    # Static "model" and "token mix" slots for now — the workload preset
    # carries those numbers. The Compare view (Task 6) lets users override.
    model_label = mo.md("**Llama 3.1 8B**")  # display-only; pricing is per-provider
    tokens_label = mo.md("**from preset**")
    filter_dd = mo.ui.dropdown(
        options=["every benchmarked configuration", "open-weight serverless only", "dedicated GPU only", "closed-API only"],
        value="every benchmarked configuration",
        label="filter",
    )

    return workload_dd, filter_dd, model_label, tokens_label


@app.cell
def _landing_render(mo, MARIMO_VIEW_META, MarimoView, workload_dd, filter_dd, calc, get_profile):
    """Render the Mad-libs sentence + verdict paragraph.
    Reactive on workload_dd / filter_dd changes.
    """
    profile = get_profile(workload_dd.value)
    results = calc.compare(profile)
    sorted_results = sorted(results, key=lambda r: r.lcpr)
    cheapest = sorted_results[0] if sorted_results else None
    second = sorted_results[1] if len(sorted_results) > 1 else None

    sentence = mo.md(
        f"I want to serve **Llama 3.1 8B** for **{workload_dd.value}**, "
        f"expecting **{profile.avg_input_tokens:,} in / {profile.avg_output_tokens:,} out** "
        f"tokens per call. Show me LCPR across **{filter_dd.value}**."
    )

    if cheapest and second:
        verdict = mo.md(
            f"At your volume, **{cheapest.provider_name}** is cheapest at LCPR "
            f"**${cheapest.lcpr:.4f}** vs. **{second.provider_name}** at LCPR "
            f"**${second.lcpr:.4f}**. See the **Compare** view for the full table."
        )
    elif cheapest:
        verdict = mo.md(
            f"At your volume, **{cheapest.provider_name}** is the only matching config "
            f"at LCPR **${cheapest.lcpr:.4f}**."
        )
    else:
        verdict = mo.md("_No matching configurations for this filter._")

    landing_block = mo.vstack([
        mo.md(f"# Production Inference Economics — {MARIMO_VIEW_META[MarimoView.LANDING].label}"),
        mo.hstack([workload_dd, filter_dd], justify="start"),
        sentence,
        verdict,
        mo.accordion({
            "Terminology": mo.md(
                "**LCPR** — Loaded Cost Per Result. The cost per *accepted* unit of work, "
                "after retries, quality-gate failures, eval cost, and escalation. "
                "Different from $/M-tokens because retries and gates can dominate.\n\n"
                "**Workload profile** — A named bundle of (avg input tokens, avg output tokens, "
                "monthly requests, retry rate, quality-gate rate, cache rate, batch fraction)."
            ),
        }),
    ])
    landing_block
    return landing_block, profile, results, cheapest


# ── Compare view (Task 6) ──
@app.cell
def _compare(mo, go, workload_dd, results, MARIMO_VIEW_META, MarimoView):
    """Compare view — LCPR across providers + deployments for current workload."""
    if not results:
        compare_block = mo.md(f"## {MARIMO_VIEW_META[MarimoView.COMPARE].label}\n\n_No matching results._")
    else:
        sorted_results = sorted(results, key=lambda r: r.lcpr)

        # Plotly bar chart, moss + oxblood palette per book.css
        deploy_color = {
            "closed_api": "#5C2A1E",       # oxblood — closed API
            "serverless_open": "#3A4F2A",  # moss — serverless open
            "dedicated": "#7a8a5a",        # moss-light — dedicated
        }

        fig = go.Figure()
        for r in sorted_results:
            fig.add_bar(
                x=[f"{r.provider_name} · {r.deployment_mode}"],
                y=[r.lcpr],
                marker_color=deploy_color.get(r.deployment_mode, "#3A4F2A"),
                showlegend=False,
                hovertemplate=f"<b>{r.provider_name}</b><br>LCPR: $%{{y:.4f}}<extra>{r.deployment_mode}</extra>",
            )
        fig.update_layout(
            plot_bgcolor="#faf5e9",
            paper_bgcolor="#faf5e9",
            font_family="Newsreader, Iowan Old Style, Georgia, serif",
            font_color="#1a1a1a",
            xaxis=dict(gridcolor="#e0d8c0", tickfont=dict(family="JetBrains Mono", size=11)),
            yaxis=dict(title="LCPR ($)", gridcolor="#e0d8c0", tickfont=dict(family="JetBrains Mono", size=11)),
            margin=dict(t=10, b=40, l=60, r=20),
            height=400,
        )

        # Prose verdict above the chart. WorkloadProfile has no .name attribute,
        # so we use workload_dd.value (the profile key string) for display.
        cheapest = sorted_results[0]
        verdict = mo.md(
            f"**{cheapest.provider_name} ({cheapest.deployment_mode})** is the lowest loaded cost per accepted result "
            f"at **${cheapest.lcpr:.4f}** for your `{workload_dd.value}` profile."
        )

        # Source caption
        caption = mo.md(
            f"<small style='color:#5C2A1E;font-family:JetBrains Mono,monospace'>"
            f"Source: provider pricing snapshot · Derivation 1</small>"
        )

        compare_block = mo.vstack([
            mo.md(f"## {MARIMO_VIEW_META[MarimoView.COMPARE].label}"),
            verdict,
            mo.ui.plotly(fig),
            caption,
        ])
    compare_block
    return compare_block


# ── Sensitivity view (Task 7) ──
@app.cell
def _sensitivity(mo, PARAM_LABELS):
    """Sensitivity view — input cell."""
    param_choices = list(PARAM_LABELS.keys())
    param_dd = mo.ui.dropdown(
        options=param_choices,
        value="retry_rate" if "retry_rate" in param_choices else param_choices[0],
        label="Parameter to sweep",
    )
    return (param_dd,)


@app.cell
def _sensitivity_render(mo, go, calc, profile, replace, PARAM_LABELS, MarimoView, MARIMO_VIEW_META, param_dd):
    """Render the sensitivity sparkline + verdict for the selected parameter."""
    param = param_dd.value
    human_label = PARAM_LABELS.get(param, param)

    current = getattr(profile, param, None)
    if current is None or current == 0:
        sens_block = mo.vstack([
            mo.md(f"## {MARIMO_VIEW_META[MarimoView.SENSITIVITY].label}"),
            param_dd,
            mo.md(f"_Parameter `{param}` not present on profile, or value is zero._"),
        ])
    else:
        # Sweep ±50% in 9 steps
        lo = max(current * 0.5, 0)
        hi = current * 1.5
        sweep = [lo + (hi - lo) * i / 8 for i in range(9)]

        lcprs = []
        for v in sweep:
            sweep_profile = replace(profile, **{param: v})
            results = calc.compare(sweep_profile)
            cheapest = min(results, key=lambda r: r.lcpr).lcpr if results else 0
            lcprs.append(cheapest)

        fig = go.Figure()
        fig.add_scatter(
            x=sweep, y=lcprs, mode="lines+markers",
            line=dict(color="#3A4F2A", width=2),
            marker=dict(color="#5C2A1E", size=8),
            hovertemplate=f"{human_label}: %{{x:.4f}}<br>LCPR: $%{{y:.4f}}<extra></extra>",
        )
        fig.add_scatter(
            x=[current], y=[lcprs[4]], mode="markers",
            marker=dict(color="#5C2A1E", size=14, symbol="x"),
            hovertemplate=f"current {human_label}: %{{x:.4f}}<extra></extra>",
            showlegend=False,
        )
        fig.update_layout(
            plot_bgcolor="#faf5e9",
            paper_bgcolor="#faf5e9",
            font_family="Newsreader, Georgia, serif",
            font_color="#1a1a1a",
            xaxis=dict(title=f"{human_label}", gridcolor="#e0d8c0", tickfont=dict(family="JetBrains Mono", size=11)),
            yaxis=dict(title="LCPR ($)", gridcolor="#e0d8c0", tickfont=dict(family="JetBrains Mono", size=11)),
            margin=dict(t=10, b=50, l=60, r=20),
            height=400,
            showlegend=False,
        )

        delta = lcprs[-1] - lcprs[0]
        direction = "increases" if delta > 0 else ("decreases" if delta < 0 else "is flat at")
        pct = abs(delta / lcprs[4]) * 100 if lcprs[4] else 0
        verdict = mo.md(
            f"As **{human_label}** sweeps from `{lo:.4f}` to `{hi:.4f}`, LCPR {direction} by "
            f"**${abs(delta):.4f}** (**{pct:.1f}%** of current). "
            f"The current value `{current:.4f}` is marked with an `×`."
        )

        sens_block = mo.vstack([
            mo.md(f"## {MARIMO_VIEW_META[MarimoView.SENSITIVITY].label}"),
            param_dd,
            verdict,
            mo.ui.plotly(fig),
        ])
    sens_block
    return sens_block


# ── Break-Even view (Task 8) ──
@app.cell
def _break_even(mo, MarimoView):
    """Crossover analysis — to be implemented in Task 8."""
    mo.md(f"# {MarimoView.BREAK_EVEN.value} — TODO")
    return


# ── Goodput view (Task 9) ──
@app.cell
def _goodput(mo, MarimoView):
    """Goodput frontier — to be implemented in Task 9."""
    mo.md(f"# {MarimoView.GOODPUT.value} — TODO")
    return


# ── Trace-to-Margin view (Task 10) ──
@app.cell
def _trace_to_margin(mo, MarimoView):
    """Reconcile traces to invoice — to be implemented in Task 10."""
    mo.md(f"# {MarimoView.TRACE_TO_MARGIN.value} — TODO")
    return


# ── Advanced view (Task 11) ──
@app.cell
def _advanced(mo, MarimoView):
    """Collapsible group: cache gate, KV capacity, RouteFit, trace schema, snapshots, operations.
    To be implemented in Task 11.
    """
    mo.md(f"# {MarimoView.ADVANCED.value} — TODO")
    return


if __name__ == "__main__":
    app.run()
