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
def _compare(mo, MarimoView):
    """LCPR comparison — to be implemented in Task 6."""
    mo.md(f"# {MarimoView.COMPARE.value} — TODO")
    return


# ── Sensitivity view (Task 7) ──
@app.cell
def _sensitivity(mo, MarimoView, PARAM_LABELS):
    """Parameter sweep — to be implemented in Task 7."""
    mo.md(f"# {MarimoView.SENSITIVITY.value} — TODO")
    _ = PARAM_LABELS  # silence unused-import — wired in Task 7
    return


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
