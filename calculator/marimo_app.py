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
def _landing(mo, MarimoView):
    """Mad-libs landing — to be implemented in Task 5."""
    mo.md(f"# {MarimoView.LANDING.value} — TODO")
    return


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
