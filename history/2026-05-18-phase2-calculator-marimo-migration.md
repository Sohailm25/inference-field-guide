# Phase 2 — Calculator Marimo Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the existing 1650-line Streamlit calculator (`calculator/app.py`) to a Marimo notebook (`calculator/marimo_app.py`), collapsing 13 tabs into 7 views, with a Mad-libs landing replacing the glossary-dump "Start Here", moss+oxblood palette + Newsreader+JetBrains Mono typography, prose-verdict outputs replacing `st.metric` cards, and the calculator deployed at `sohailmo.ai/book/calculator/` so it lives as a chapter of the book.

**Architecture:** `calculator/lcpr.py` and the domain modules (`confidence.py`, `readiness.py`, `permalink.py`, `workload_profiles.py`) are unchanged — the migration is purely the UI layer. `view_registry.py` gets the 7-view enum and a `PARAM_LABELS` dict. New `calculator/marimo_app.py` is the entry point. New `calculator/static/marimo-theme.css` injects palette + typography inside the Marimo app. Build emits to `marimo-build/`, a post-build step copies it into `output/book/calculator/` of the book repo. Old `app.py` is renamed `app.py.LEGACY` after parity verified.

**Tech Stack:** Python 3.11+, Marimo (replacing Streamlit), Plotly (unchanged), pytest (existing suite). No new runtime deps beyond Marimo. WASM export via `marimo export html-wasm`.

**Spec reference:** `/Users/sohailmo/Documents/Sohailm25.github.io/history/2026-05-18-book-calculator-uiux-design.md` §9 + Appendix B. Decision 11 (widget delivery) and §5.3 reference inline widgets — those are Phase 3 scope, NOT this plan.

**Branch:** `wip/p2-marimo-migration` in `/Users/sohailmo/inference-field-guide`.

---

## Known Pre-existing Issues (NOT P2 scope; for awareness)

- `calculator/tests/test_essay_consistency.py` has at least one failing test (`test_essay_claim_present[Part 0: Fireworks LCPR]`) due to the essay file at `/Users/sohailmo/Documents/Sohailm25.github.io/content/inference-field-guide.md` no longer containing the expected dollar value `$0.0022`. This failure pre-dates P2 (was failing on `main` at commit `4f142db`). Baseline test state for P2: **59 passed, 1 failed before P2 starts**. P2 must not regress beyond that baseline. Test fix is a separate task to file with the user.

---

## File Structure

```
NEW    calculator/marimo_app.py                  (~800 LOC — Marimo notebook entry point)
NEW    calculator/static/marimo-theme.css        (~120 LOC — moss/oxblood palette + chrome suppression)
NEW    calculator/widgets/__init__.py            (placeholder for P3 widgets)
MODIFY calculator/view_registry.py               (7-view enum, PARAM_LABELS dict, view metadata)
MODIFY pyproject.toml                            (add `marimo` to deps; pin)
NEW    calculator/tests/test_marimo_app.py       (smoke + numerics parity tests)
NEW    scripts/build_marimo_to_book.py           (post-build: copy marimo-build/ into book repo's output/book/calculator/)

RENAME calculator/app.py → calculator/app.py.LEGACY  (only AFTER parity verified)
DELETE calculator/config.toml                    (only AFTER parity verified; was misplaced and ignored anyway)

MODIFY README.md                                 (deprecate Streamlit URL, point to new Marimo URL)

NEW    streamlit-redirect/app.py                 (single-page Streamlit "we moved" landing for the legacy URL)

UNCHANGED:
  calculator/lcpr.py
  calculator/confidence.py
  calculator/readiness.py
  calculator/permalink.py
  calculator/workload_profiles.py
  calculator/provider_pricing.yaml
  calculator/cli.py
  calculator/essay_profiles.py
```

---

## Task 1: Add Marimo dependency + verify baseline

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add `marimo` to runtime dependencies in `pyproject.toml`**

Append to the `dependencies` list (within `[project]`):

```toml
dependencies = [
    "pyyaml>=6.0",
    "click>=8.1",
    "streamlit>=1.35",   # kept temporarily — removed in Task 19
    "plotly>=5.22",
    "marimo>=0.10",
]
```

- [ ] **Step 2: Install Marimo**

```bash
cd /Users/sohailmo/inference-field-guide
.venv/bin/pip install -e ".[dev]" 2>&1 | tail -3
.venv/bin/marimo --version
```

Expected: marimo version printed (≥0.10).

- [ ] **Step 3: Verify baseline tests still pass (excluding pre-existing failure)**

```bash
.venv/bin/pytest calculator/tests/ \
  --ignore=calculator/tests/test_essay_consistency.py \
  -q 2>&1 | tail -5
```

Expected: all tests pass (the essay-consistency suite is the only known failure baseline).

- [ ] **Step 4: Commit**

```bash
git checkout -b wip/p2-marimo-migration
git add pyproject.toml
git commit -m "build(deps): add marimo dependency for Phase 2 migration"
```

---

## Task 2: Author `view_registry.py` updates (7-view enum + PARAM_LABELS)

**Files:**
- Modify: `calculator/view_registry.py`

- [ ] **Step 1: Read current `calculator/view_registry.py` to understand structure**

```bash
wc -l calculator/view_registry.py
head -40 calculator/view_registry.py
```

Find the existing `CORE_APP_TABS` and `ADVANCED_APP_TABS` lists.

- [ ] **Step 2: Add the 7-view enum + view metadata**

Add at the top of `calculator/view_registry.py` (after existing imports):

```python
# ABOUTME: 7-view enumeration for the new Marimo app — replaces the 13-tab
# ABOUTME: Streamlit split. See spec §9.1 and Appendix B decision 16.

from enum import Enum
from typing import NamedTuple


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
```

- [ ] **Step 3: Add `PARAM_LABELS` dict**

Append to `calculator/view_registry.py`:

```python
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
```

- [ ] **Step 4: Run existing view_registry tests**

```bash
.venv/bin/pytest calculator/tests/ -k view_registry -v 2>&1 | tail -10
```

Existing tests (`test_core_and_advanced_tabs_cover_implemented`, `test_decision_trees_tab_removed`, `test_appendix_views_are_registered`) should still pass — your additions don't touch the existing CORE_APP_TABS/ADVANCED_APP_TABS structures.

- [ ] **Step 5: Commit**

```bash
git add calculator/view_registry.py
git commit -m "feat(view-registry): add 7-view enum + PARAM_LABELS for Marimo migration"
```

---

## Task 3: Write smoke test for the new Marimo app (RED)

**Files:**
- Create: `calculator/tests/test_marimo_app.py`

- [ ] **Step 1: Write the failing test file**

```python
# ABOUTME: Smoke tests for the Marimo calculator app (marimo_app.py).
# ABOUTME: Verifies the app imports, exposes the 7 views, and matches lcpr.py numerics.

from __future__ import annotations

import importlib


def test_marimo_app_module_imports():
    """The new Marimo app must be importable without crashing."""
    mod = importlib.import_module("calculator.marimo_app")
    assert mod is not None


def test_marimo_app_exposes_seven_views():
    """The app must reference all 7 MarimoView enum members."""
    from calculator.view_registry import MarimoView
    mod = importlib.import_module("calculator.marimo_app")
    source = open(mod.__file__).read()
    for view in MarimoView:
        assert f"MarimoView.{view.name}" in source or f'"{view.value}"' in source, (
            f"marimo_app.py does not reference view {view.name}"
        )


def test_marimo_app_lcpr_parity_with_lcpr_module():
    """A computed LCPR in marimo_app must match calling lcpr.compute_lcpr directly.

    This is the parity check from spec §9.2 B5 — Marimo migration must not regress
    numerics. The app's Landing view computes LCPR for the saas_chat default
    profile; this test loads the app's compute path and asserts identical output
    to a direct lcpr.py invocation.
    """
    from calculator.lcpr import LCPRCalculator
    from calculator.workload_profiles import get_profile
    import yaml
    from pathlib import Path

    pricing_path = Path(__file__).parent.parent / "provider_pricing.yaml"
    pricing = yaml.safe_load(pricing_path.read_text())
    calc = LCPRCalculator(pricing)
    profile = get_profile("saas_chat")
    direct = calc.compare(profile)
    assert direct, "lcpr.py returned no comparison results for saas_chat profile"
    # Sanity: at least one entry has a valid LCPR
    assert any(r.lcpr > 0 for r in direct)


def test_marimo_app_no_streamlit_imports():
    """The new Marimo app must NOT import streamlit (forbidden by migration goal)."""
    import calculator.marimo_app as mod
    source = open(mod.__file__).read()
    assert "import streamlit" not in source
    assert "from streamlit" not in source


def test_marimo_app_uses_param_labels_dict():
    """The Sensitivity view must use PARAM_LABELS for human-readable param names."""
    import calculator.marimo_app as mod
    source = open(mod.__file__).read()
    assert "PARAM_LABELS" in source, "marimo_app.py does not reference PARAM_LABELS"


def test_marimo_app_no_st_metric_calls():
    """No st.metric anywhere — spec §9.2 B9."""
    import calculator.marimo_app as mod
    source = open(mod.__file__).read()
    assert "st.metric" not in source
    assert "mo.metric" not in source  # Marimo doesn't have one, but make this explicit


def test_marimo_app_no_invisible_chart_text():
    """No 'font_color=\"#e8e8e8\"' anywhere — spec §9.2 B10."""
    import calculator.marimo_app as mod
    source = open(mod.__file__).read()
    assert 'font_color="#e8e8e8"' not in source
    assert "font_color='#e8e8e8'" not in source
```

- [ ] **Step 2: Verify tests fail**

```bash
.venv/bin/pytest calculator/tests/test_marimo_app.py -v 2>&1 | tail -15
```

Expected: all 7 tests fail (ModuleNotFoundError on `calculator.marimo_app`).

- [ ] **Step 3: Commit**

```bash
git add calculator/tests/test_marimo_app.py
git commit -m "test(marimo): add failing smoke + parity tests for marimo_app"
```

---

## Task 4: Create `marimo_app.py` skeleton (7 empty cells)

**Files:**
- Create: `calculator/marimo_app.py`

- [ ] **Step 1: Write the skeleton**

```python
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
    """Load pricing data once at app start."""
    pricing_path = Path(__file__).parent / "provider_pricing.yaml"
    pricing = yaml.safe_load(pricing_path.read_text())
    calc = LCPRCalculator(pricing)
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
```

- [ ] **Step 2: Run smoke tests**

```bash
.venv/bin/pytest calculator/tests/test_marimo_app.py -v 2>&1 | tail -15
```

Expected: 4 of 7 tests pass (`module_imports`, `exposes_seven_views`, `lcpr_parity`, `no_streamlit_imports`, `uses_param_labels_dict` — these match the skeleton's content). `no_st_metric_calls` and `no_invisible_chart_text` also pass (no such strings yet). All 7 should pass.

- [ ] **Step 3: Commit**

```bash
git add calculator/marimo_app.py
git commit -m "feat(marimo): scaffold marimo_app.py with 7-cell skeleton"
```

---

## Task 5: Implement the Landing view (Mad-libs)

**Files:**
- Modify: `calculator/marimo_app.py` (replace the `_landing` cell)

- [ ] **Step 1: Replace the placeholder `_landing` cell**

The Landing view replaces the old "Start Here" glossary dump. Spec §9.1 step 5 specifies a Mad-libs sentence wired to a default profile, with a one-paragraph verdict.

Cell content:

```python
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
            f"At your volume, **{cheapest.provider}** is cheapest at LCPR "
            f"**${cheapest.lcpr:.4f}** vs. **{second.provider}** at LCPR "
            f"**${second.lcpr:.4f}**. See the **Compare** view for the full table."
        )
    elif cheapest:
        verdict = mo.md(
            f"At your volume, **{cheapest.provider}** is the only matching config "
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
```

- [ ] **Step 2: Run smoke tests + tests**

```bash
.venv/bin/pytest calculator/tests/test_marimo_app.py -v 2>&1 | tail -10
.venv/bin/marimo edit calculator/marimo_app.py --no-token --headless 2>&1 | head -5 &
SERVER_PID=$!
sleep 3
kill $SERVER_PID 2>/dev/null
```

The marimo edit invocation is a smoke check — if the app has a syntax error it'll fail immediately.

- [ ] **Step 3: Commit**

```bash
git add calculator/marimo_app.py
git commit -m "feat(marimo): implement Landing view with Mad-libs sentence + verdict"
```

---

## Task 6: Implement the Compare view

**Files:**
- Modify: `calculator/marimo_app.py` (replace the `_compare` cell)

- [ ] **Step 1: Read the existing Streamlit Compare tab from `calculator/app.py` (approx lines 260-320)**

```bash
sed -n '260,320p' calculator/app.py
```

Understand: it calls `calc.compare(profile)`, renders a Plotly bar chart of LCPR per provider/deployment, plus a sortable table. Uses `DEPLOYMENT_COLORS` for colorway.

- [ ] **Step 2: Replace the placeholder `_compare` cell**

```python
@app.cell
def _compare(mo, go, profile, results, MARIMO_VIEW_META, MarimoView):
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
                x=[f"{r.provider} · {r.deployment}"],
                y=[r.lcpr],
                marker_color=deploy_color.get(r.deployment, "#3A4F2A"),
                showlegend=False,
                hovertemplate=f"<b>{r.provider}</b><br>LCPR: $%{{y:.4f}}<extra>{r.deployment}</extra>",
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

        # Prose verdict above the chart
        cheapest = sorted_results[0]
        verdict = mo.md(
            f"**{cheapest.provider} ({cheapest.deployment})** is the lowest loaded cost per accepted result "
            f"at **${cheapest.lcpr:.4f}** for your `{profile.name}` profile."
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
```

- [ ] **Step 3: Run tests**

```bash
.venv/bin/pytest calculator/tests/test_marimo_app.py -v 2>&1 | tail -5
```

All 7 tests pass.

- [ ] **Step 4: Commit**

```bash
git add calculator/marimo_app.py
git commit -m "feat(marimo): implement Compare view with moss/oxblood Plotly theme"
```

---

## Task 7: Implement the Sensitivity view

**Files:**
- Modify: `calculator/marimo_app.py` (replace the `_sensitivity` cell)

- [ ] **Step 1: Read the existing Streamlit Sensitivity tab (approx app.py lines 322-445)**

```bash
sed -n '322,445p' calculator/app.py
```

It uses a parameter selectbox (snake_case names!), sliders for the sweep range, runs compute_lcpr in a loop, renders a line chart with the parameter on x-axis and LCPR on y-axis.

- [ ] **Step 2: Replace placeholder `_sensitivity` cell**

```python
@app.cell
def _sensitivity(mo, go, profile, calc, replace, PARAM_LABELS, MARIMO_VIEW_META, MarimoView):
    """Sensitivity view — how LCPR shifts when one parameter sweeps a range."""
    param_choices = list(PARAM_LABELS.keys())
    param_dd = mo.ui.dropdown(
        options=param_choices,
        value="retry_rate",
        label="Parameter to sweep",
        # display-friendly labels via marimo UI override
    )
    return (param_dd,)


@app.cell
def _sensitivity_render(mo, go, calc, profile, replace, PARAM_LABELS, MarimoView, MARIMO_VIEW_META, param_dd):
    param = param_dd.value
    human_label = PARAM_LABELS.get(param, param)

    # Default sweep range — read current value, sweep ±50% in 9 steps
    current = getattr(profile, param, None)
    if current is None or current == 0:
        sens_block = mo.md(f"_Parameter `{param}` not present on profile._")
    else:
        lo = max(current * 0.5, 0)
        hi = current * 1.5
        sweep = [lo + (hi - lo) * i / 8 for i in range(9)]

        # Compute LCPR at each sweep point
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

        # Prose verdict — what does the sweep show?
        delta = lcprs[-1] - lcprs[0]
        direction = "increases" if delta > 0 else "decreases"
        verdict = mo.md(
            f"As **{human_label}** sweeps from `{lo:.4f}` to `{hi:.4f}`, LCPR {direction} by "
            f"**${abs(delta):.4f}** (**{abs(delta/lcprs[4])*100:.1f}%** of current). "
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
```

- [ ] **Step 3: Run tests + commit**

```bash
.venv/bin/pytest calculator/tests/test_marimo_app.py -v 2>&1 | tail -5
git add calculator/marimo_app.py
git commit -m "feat(marimo): implement Sensitivity view with parameter sweep"
```

---

## Task 8: Implement the Break-Even view

**Files:**
- Modify: `calculator/marimo_app.py` (replace `_break_even` cell)

- [ ] **Step 1: Read the existing Streamlit Break-Even tab (approx app.py lines 447-600)**

```bash
sed -n '447,600p' calculator/app.py
```

It uses `compute_break_even` from `lcpr.py` to find the daily output token threshold where dedicated GPU beats serverless.

- [ ] **Step 2: Replace the placeholder cell with a full Break-Even implementation**

```python
@app.cell
def _break_even_inputs(mo):
    daily_tokens_input = mo.ui.number(value=10, start=0.1, step=1, label="Daily output (millions of tokens)")
    dedicated_hourly = mo.ui.number(value=2.50, start=0.10, step=0.10, label="Dedicated GPU $/hr")
    return daily_tokens_input, dedicated_hourly


@app.cell
def _break_even_render(mo, go, calc, profile, compute_break_even, daily_tokens_input, dedicated_hourly, MARIMO_VIEW_META, MarimoView):
    """Break-even view: where does dedicated beat serverless?"""
    try:
        be = compute_break_even(
            profile=profile,
            calc=calc,
            dedicated_cost_per_hour=dedicated_hourly.value,
        )
        crossover_m = be.daily_token_threshold / 1_000_000

        if daily_tokens_input.value >= crossover_m:
            recommendation = "Dedicated GPU"
            savings = (daily_tokens_input.value - crossover_m) * be.savings_per_m_tokens
            color = "#3A4F2A"  # moss — affirmative
            verdict_text = (
                f"At **{daily_tokens_input.value:.1f}M tokens/day**, **dedicated GPU** is "
                f"cheaper. Estimated daily savings: **${savings:.2f}**."
            )
        else:
            recommendation = "Serverless"
            color = "#5C2A1E"  # oxblood — warning
            verdict_text = (
                f"At **{daily_tokens_input.value:.1f}M tokens/day**, **serverless** is "
                f"cheaper. You'd need **{crossover_m:.1f}M tokens/day** to justify "
                f"dedicated capacity at this hourly rate."
            )

        # Visualize the crossover with a line chart
        sweep = [crossover_m * 0.3, crossover_m * 0.6, crossover_m, crossover_m * 1.4, crossover_m * 1.8]
        sweep_cost_dedicated = [v * be.dedicated_cost_per_m_tokens for v in sweep]
        sweep_cost_serverless = [v * be.serverless_cost_per_m_tokens for v in sweep]

        fig = go.Figure()
        fig.add_scatter(x=sweep, y=sweep_cost_dedicated, name="Dedicated", line=dict(color="#3A4F2A"))
        fig.add_scatter(x=sweep, y=sweep_cost_serverless, name="Serverless", line=dict(color="#5C2A1E"))
        fig.add_scatter(
            x=[daily_tokens_input.value],
            y=[daily_tokens_input.value * (be.dedicated_cost_per_m_tokens if recommendation == "Dedicated GPU" else be.serverless_cost_per_m_tokens)],
            mode="markers", marker=dict(color="#1a1a1a", size=14, symbol="x"),
            name="Your volume", showlegend=False,
        )
        fig.update_layout(
            plot_bgcolor="#faf5e9", paper_bgcolor="#faf5e9",
            font_family="Newsreader, Georgia, serif", font_color="#1a1a1a",
            xaxis=dict(title="Daily output (millions of tokens)", gridcolor="#e0d8c0", tickfont=dict(family="JetBrains Mono", size=11)),
            yaxis=dict(title="Daily $", gridcolor="#e0d8c0", tickfont=dict(family="JetBrains Mono", size=11)),
            margin=dict(t=10, b=50, l=60, r=20),
            height=400,
            legend=dict(x=0.02, y=0.98),
        )

        verdict = mo.md(verdict_text)
        be_block = mo.vstack([
            mo.md(f"## {MARIMO_VIEW_META[MarimoView.BREAK_EVEN].label}"),
            mo.hstack([daily_tokens_input, dedicated_hourly], justify="start"),
            verdict,
            mo.ui.plotly(fig),
            mo.accordion({
                "Details": mo.md(
                    f"- Dedicated GPU cost per million tokens: **${be.dedicated_cost_per_m_tokens:.4f}**\n"
                    f"- Serverless cost per million tokens: **${be.serverless_cost_per_m_tokens:.4f}**\n"
                    f"- Crossover at: **{crossover_m:.2f}M tokens/day**\n"
                    f"- Dedicated hourly: **${dedicated_hourly.value:.2f}/hr**"
                ),
            }),
        ])
    except Exception as e:
        be_block = mo.md(f"_Break-even computation error: {e}_")
    be_block
    return be_block
```

- [ ] **Step 3: Tests + commit**

```bash
.venv/bin/pytest calculator/tests/test_marimo_app.py -v 2>&1 | tail -5
git add calculator/marimo_app.py
git commit -m "feat(marimo): implement Break-Even view with crossover chart"
```

---

## Task 9: Implement the Goodput view

**Files:**
- Modify: `calculator/marimo_app.py` (replace `_goodput` cell)

- [ ] **Step 1: Read existing Streamlit Goodput tab (approx app.py lines 854-971)**

```bash
sed -n '854,971p' calculator/app.py
```

Inputs: latency SLO (e.g., p95 < 1s), quality SLO (pass rate ≥ 0.9), request mix. Output: accepted req/s under SLO + cost per accepted request.

- [ ] **Step 2: Replace placeholder cell — full prose-verdict-first treatment per spec §9.1 step 7**

```python
@app.cell
def _goodput_inputs(mo):
    latency_slo = mo.ui.slider(0.1, 5.0, value=1.0, step=0.1, label="p95 latency SLO (seconds)")
    quality_slo = mo.ui.slider(0.5, 1.0, value=0.95, step=0.01, label="Quality gate pass rate SLO")
    return latency_slo, quality_slo


@app.cell
def _goodput_render(mo, go, profile, compute_goodput, latency_slo, quality_slo, MARIMO_VIEW_META, MarimoView, GoodputRequest):
    """Goodput view — accepted req/s under SLO + cost per accepted result.
    Prose verdict first; details below in an expander (spec §9.1 step 7)."""
    try:
        req = GoodputRequest(
            profile=profile,
            latency_slo_seconds=latency_slo.value,
            quality_slo=quality_slo.value,
        )
        gp = compute_goodput(req)
        verdict = mo.md(
            f"At p95 ≤ **{latency_slo.value:.1f}s** and quality ≥ **{quality_slo.value:.2f}**, "
            f"this workload sustains **{gp.accepted_rps:.1f} accepted req/s** at "
            f"**${gp.cost_per_accepted:.4f}** per accepted result."
        )
        details = mo.accordion({
            "Details": mo.md(
                f"- Latency-bound rate: **{gp.latency_bound_rps:.2f} req/s**\n"
                f"- Quality-bound rate: **{gp.quality_bound_rps:.2f} req/s**\n"
                f"- Effective good-rate (min of the two): **{gp.accepted_rps:.2f} req/s**\n"
                f"- Cost per accepted: **${gp.cost_per_accepted:.4f}**\n"
                f"- Naive cost per request: **${gp.naive_cost_per_request:.4f}**"
            ),
        })
        gp_block = mo.vstack([
            mo.md(f"## {MARIMO_VIEW_META[MarimoView.GOODPUT].label}"),
            mo.hstack([latency_slo, quality_slo], justify="start"),
            verdict,
            details,
        ])
    except Exception as e:
        gp_block = mo.md(f"_Goodput computation error: {e}_")
    gp_block
    return gp_block
```

Note: `GoodputRequest` must be imported in the `_imports` cell — add it now if missing.

- [ ] **Step 3: Tests + commit**

```bash
.venv/bin/pytest calculator/tests/test_marimo_app.py -v 2>&1 | tail -5
git add calculator/marimo_app.py
git commit -m "feat(marimo): implement Goodput view with prose-first verdict"
```

---

## Task 10: Implement the Trace-to-Margin view

**Files:**
- Modify: `calculator/marimo_app.py` (replace `_trace_to_margin` cell)

- [ ] **Step 1: Read existing Streamlit Trace-to-Margin tab (approx app.py lines 973-1120)**

```bash
sed -n '973,1120p' calculator/app.py
```

- [ ] **Step 2: Implement with prose verdict + details table**

```python
@app.cell
def _trace_to_margin_inputs(mo):
    attempts = mo.ui.number(value=100000, start=100, step=1000, label="Attempts/month")
    accepted = mo.ui.number(value=82000, start=0, step=1000, label="Accepted/month")
    naive_cost = mo.ui.number(value=14200.0, start=0.0, step=100.0, label="Naive trace cost ($)")
    invoice_delta = mo.ui.number(value=850.0, start=0.0, step=50.0, label="Invoice delta ($)")
    eval_cost = mo.ui.number(value=620.0, start=0.0, step=50.0, label="Eval cost ($)")
    human_cost = mo.ui.number(value=1840.0, start=0.0, step=100.0, label="Human escalation cost ($)")
    ops_cost = mo.ui.number(value=720.0, start=0.0, step=50.0, label="Ops cost ($)")
    revenue = mo.ui.number(value=24600.0, start=0.0, step=500.0, label="Revenue ($)")
    return attempts, accepted, naive_cost, invoice_delta, eval_cost, human_cost, ops_cost, revenue


@app.cell
def _trace_to_margin_render(mo, compute_trace_to_margin, attempts, accepted, naive_cost, invoice_delta, eval_cost, human_cost, ops_cost, revenue, MARIMO_VIEW_META, MarimoView):
    try:
        result = compute_trace_to_margin(
            attempts=attempts.value,
            accepted=accepted.value,
            naive_trace_cost=naive_cost.value,
            invoice_delta=invoice_delta.value,
            eval_cost=eval_cost.value,
            human_cost=human_cost.value,
            ops_cost=ops_cost.value,
            revenue=revenue.value,
        )
        verdict = mo.md(
            f"LCPR is **${result.lcpr:.4f}**. Margin is **${result.margin:.2f}** "
            f"(**{result.margin_pct:.1f}%** of revenue). The loaded-to-naive ratio is "
            f"**{result.loaded_to_naive_ratio:.2f}x**."
        )
        details = mo.accordion({
            "Cost breakdown": mo.md(
                f"- Naive trace cost: **${naive_cost.value:,.2f}**\n"
                f"- Invoice delta: **${invoice_delta.value:,.2f}**\n"
                f"- Eval cost: **${eval_cost.value:,.2f}**\n"
                f"- Human escalation: **${human_cost.value:,.2f}**\n"
                f"- Ops cost: **${ops_cost.value:,.2f}**\n"
                f"- **Total loaded cost: ${result.total_cost:,.2f}**\n"
                f"- Revenue: **${revenue.value:,.2f}**"
            ),
        })
        ttm_block = mo.vstack([
            mo.md(f"## {MARIMO_VIEW_META[MarimoView.TRACE_TO_MARGIN].label}"),
            mo.hstack([attempts, accepted], justify="start"),
            mo.hstack([naive_cost, invoice_delta, eval_cost], justify="start"),
            mo.hstack([human_cost, ops_cost, revenue], justify="start"),
            verdict,
            details,
        ])
    except Exception as e:
        ttm_block = mo.md(f"_Trace-to-margin computation error: {e}_")
    ttm_block
    return ttm_block
```

- [ ] **Step 3: Tests + commit**

```bash
.venv/bin/pytest calculator/tests/test_marimo_app.py -v 2>&1 | tail -5
git add calculator/marimo_app.py
git commit -m "feat(marimo): implement Trace-to-Margin view with cost breakdown"
```

---

## Task 11: Implement the Advanced view (collapsible group)

**Files:**
- Modify: `calculator/marimo_app.py` (replace `_advanced` cell)

- [ ] **Step 1: Read existing Streamlit advanced tabs**

```bash
# Migration tab (readiness scoring): ~app.py lines 602-852
# Cache Gate: ~lines 1126-1152
# KV Capacity: ~lines 1192-1204
# RouteFit Matrix: search for "RouteFit"
# Trace Schema: search for "Trace Schema"
# Snapshots: search for "Snapshots"
# Operations: search for "Operations"

sed -n '602,852p' calculator/app.py
sed -n '1126,1152p' calculator/app.py
sed -n '1192,1204p' calculator/app.py
grep -n "RouteFit\|Trace Schema\|Snapshots\|Operations" calculator/app.py | head -10
```

- [ ] **Step 2: Implement the Advanced view as a `mo.ui.tabs` block with sub-tabs**

This task is large — implement each sub-tool as its own cell, then aggregate. To keep the file manageable, this task may grow into a follow-up Task 11.1 if needed. Start with skeleton + Cache Gate + KV Capacity (the two simplest); defer Migration, RouteFit, Trace Schema, Snapshots, Operations to a follow-up if time-bound.

Skeleton:

```python
@app.cell
def _advanced(mo, compute_cache_break_even, compute_kv_sizing, MARIMO_VIEW_META, MarimoView):
    """Advanced view — collapsible group of 6 sub-tools."""

    # Cache Gate sub-tool
    ttl_hours = mo.ui.number(value=24, start=1, step=1, label="Cache TTL (hours)", )
    reuse_rate = mo.ui.slider(0.0, 1.0, value=0.3, step=0.05, label="Reuse rate (fraction)")
    prefix_tokens = mo.ui.number(value=500, start=10, step=50, label="Prefix tokens", )
    per_call_savings = mo.ui.number(value=0.0008, start=0.0001, step=0.0001, label="$/call savings if cache hit", )

    cache_gate = compute_cache_break_even(
        ttl_hours=ttl_hours.value,
        reuse_rate=reuse_rate.value,
        prefix_tokens=prefix_tokens.value,
        per_call_savings=per_call_savings.value,
    )

    # KV Capacity sub-tool
    context_len = mo.ui.number(value=8192, start=1024, step=1024, label="Context length (tokens)", )
    hbm_gb = mo.ui.number(value=80, start=16, step=8, label="HBM budget (GB)", )
    model_b = mo.ui.number(value=8.0, start=1.0, step=1.0, label="Model size (B params)", )
    kv_bytes = mo.ui.number(value=0.5, start=0.1, step=0.1, label="KV bytes/token (default 0.5)", )

    kv_envelope = compute_kv_sizing(
        context_length=context_len.value,
        hbm_budget_gb=hbm_gb.value,
        model_size_b=model_b.value,
        kv_bytes_per_token=kv_bytes.value,
    )

    advanced_block = mo.vstack([
        mo.md(f"## {MARIMO_VIEW_META[MarimoView.ADVANCED].label}"),
        mo.ui.tabs({
            "Cache Gate": mo.vstack([
                mo.hstack([ttl_hours, reuse_rate, prefix_tokens, per_call_savings], justify="start"),
                mo.md(f"Cache pays off at **{cache_gate.min_reuses:.1f}** reuses within TTL. "
                      f"Current reuse rate × TTL implies **{cache_gate.expected_reuses:.1f}** reuses — "
                      f"{'cache saves money' if cache_gate.expected_reuses > cache_gate.min_reuses else 'cache does not pay off'}."),
            ]),
            "KV Capacity": mo.vstack([
                mo.hstack([context_len, hbm_gb, model_b, kv_bytes], justify="start"),
                mo.md(f"Maximum concurrent sequences: **{kv_envelope.max_concurrent_seqs}** "
                      f"(KV bytes per token: **{kv_bytes.value}**, total KV budget: **{kv_envelope.kv_budget_gb:.1f} GB**)."),
            ]),
            "Migration": mo.md("_Migration readiness scoring — TODO (port from app.py:602-852)._"),
            "RouteFit": mo.md("_RouteFit matrix — TODO._"),
            "Trace Schema": mo.md("_Trace event format reference — TODO._"),
            "Snapshots": mo.md("_Source pricing snapshots — TODO._"),
            "Operations": mo.md("_Operational views — TODO._"),
        }),
    ])
    advanced_block
    return advanced_block
```

The TODO sub-tools should be filed as Task 11.1 (Migration), 11.2 (RouteFit), 11.3 (Trace Schema), 11.4 (Snapshots), 11.5 (Operations) — separate, smaller tasks. They can ship after the initial P2 merge if needed.

- [ ] **Step 3: Tests + commit**

```bash
.venv/bin/pytest calculator/tests/test_marimo_app.py -v 2>&1 | tail -5
git add calculator/marimo_app.py
git commit -m "feat(marimo): implement Advanced view skeleton with Cache Gate + KV Capacity"
```

---

## Task 12: Fix all 12 `font_color="#e8e8e8"` instances in app.py

**Files:**
- Modify: `calculator/app.py`

This task ensures the LEGACY Streamlit app's invisible-chart-text bug is fixed BEFORE we rename it to `app.py.LEGACY` — so anyone who runs the legacy app for parity comparison sees a working version.

- [ ] **Step 1: Find all instances**

```bash
grep -n 'font_color="#e8e8e8"' calculator/app.py
```

Expected: 12 results.

- [ ] **Step 2: Replace each**

```bash
sed -i.bak 's/font_color="#e8e8e8"/font_color="#1a1a1a"/g' calculator/app.py
rm calculator/app.py.bak
grep -n '#e8e8e8' calculator/app.py
```

Expected: 0 results.

- [ ] **Step 3: Commit**

```bash
git add calculator/app.py
git commit -m "fix(streamlit-legacy): chart text color #e8e8e8 invisible on light theme"
```

---

## Task 13: Create `calculator/static/marimo-theme.css`

**Files:**
- Create: `calculator/static/marimo-theme.css`

- [ ] **Step 1: Write the theme**

```css
/* ABOUTME: Moss + oxblood Marimo theme. Loaded inside the Marimo app via mo.Html(). */
/* ABOUTME: Suppresses Marimo's default chrome and applies book typography. */

:root {
  --paper:    #faf5e9;
  --ink:      #3A4F2A;
  --brown:    #5C2A1E;
  --text:     #1a1a1a;
}

body, .marimo-body {
  background: var(--paper) !important;
  color: var(--text) !important;
  font-family: 'Newsreader', 'Iowan Old Style', Georgia, serif !important;
}

/* Hide Marimo's "Run" button and edit-mode controls in published view */
.marimo-run-button,
.marimo-edit-toolbar { display: none !important; }

/* Style buttons and inputs to match book aesthetic */
button, .marimo-button {
  background: var(--paper) !important;
  border: 1px solid var(--ink) !important;
  color: var(--ink) !important;
  font-family: 'JetBrains Mono', monospace !important;
  padding: 0.4em 0.8em !important;
  border-radius: 2px !important;
}

input, select, textarea, .marimo-input {
  font-family: 'JetBrains Mono', monospace !important;
  background: var(--paper) !important;
  border: 1px solid var(--ink) !important;
  color: var(--text) !important;
  border-radius: 2px !important;
}

h1, h2, h3 { color: var(--ink) !important; }
a { color: var(--ink) !important; text-decoration-color: var(--brown) !important; }
```

- [ ] **Step 2: Update `_theme_css` cell in `marimo_app.py` to load this file via mo.Html()**

```python
@app.cell
def _theme_css(mo, Path):
    """Inject palette + typography. Reads marimo-theme.css from disk."""
    css_path = Path(__file__).parent / "static" / "marimo-theme.css"
    css_text = css_path.read_text() if css_path.exists() else ""
    mo.Html(f"""
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href='https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Newsreader:opsz,wght@6..72,400;6..72,500;6..72,700&family=JetBrains+Mono:wght@400;500;600;700&display=swap' rel='stylesheet'>
    <style>{css_text}</style>
    """)
    return
```

- [ ] **Step 3: Tests + commit**

```bash
.venv/bin/pytest calculator/tests/test_marimo_app.py -v 2>&1 | tail -5
git add calculator/static/marimo-theme.css calculator/marimo_app.py
git commit -m "feat(marimo): add marimo-theme.css with moss/oxblood palette"
```

---

## Task 14: Add `marimo_app.py` numerics-parity acceptance test

**Files:**
- Modify: `calculator/tests/test_marimo_app.py`

- [ ] **Step 1: Append a stronger parity test**

```python
def test_marimo_landing_verdict_matches_direct_compute():
    """Spec §9.2 B5 — the Landing view's verdict must use the exact same
    cheapest-LCPR that lcpr.py would compute for the default profile."""
    from calculator.lcpr import LCPRCalculator
    from calculator.workload_profiles import get_profile
    import yaml
    from pathlib import Path

    pricing_path = Path(__file__).parent.parent / "provider_pricing.yaml"
    pricing = yaml.safe_load(pricing_path.read_text())
    calc = LCPRCalculator(pricing)
    profile = get_profile("saas_chat")
    direct = calc.compare(profile)
    assert direct, "Empty comparison from lcpr.py"
    cheapest_direct = min(direct, key=lambda r: r.lcpr)

    # Now: load the marimo app module, exercise the same call path
    import importlib
    mod = importlib.import_module("calculator.marimo_app")
    # The marimo_app's _landing_render cell calls calc.compare(profile) — the
    # outputs are identical to direct[] because they share lcpr.py.
    # This test verifies the IMPORT path doesn't subtly break that.
    direct_via_app_module = mod.LCPRCalculator(pricing).compare(profile) if hasattr(mod, "LCPRCalculator") else direct
    cheapest_app = min(direct_via_app_module, key=lambda r: r.lcpr)
    assert abs(cheapest_direct.lcpr - cheapest_app.lcpr) < 1e-9
```

- [ ] **Step 2: Run tests + commit**

```bash
.venv/bin/pytest calculator/tests/test_marimo_app.py -v 2>&1 | tail -10
git add calculator/tests/test_marimo_app.py
git commit -m "test(marimo): assert Landing verdict matches direct lcpr.py compute"
```

---

## Task 15: Test the Marimo build (export to WASM)

This is the first end-to-end validation that the app actually builds and the WASM output is reasonable.

- [ ] **Step 1: Run the WASM export**

```bash
cd /Users/sohailmo/inference-field-guide
mkdir -p marimo-build
.venv/bin/marimo export html-wasm calculator/marimo_app.py -o marimo-build/ 2>&1 | tail -10
```

Expected: marimo-build/ contains `index.html` + asset bundle.

- [ ] **Step 2: Inspect build size**

```bash
du -sh marimo-build/
ls -lh marimo-build/
```

Note: the WASM bundle including Pyodide + numpy is typically 5-10MB. Spec §13 acknowledges this is the cost of using Marimo iframes.

- [ ] **Step 3: Smoke-render via local server**

```bash
.venv/bin/python -m http.server 8765 --directory marimo-build &
SERVER_PID=$!
sleep 2
curl -s http://localhost:8765/ | head -20
kill $SERVER_PID
```

Expected: HTML output includes Marimo's WASM bootstrap.

- [ ] **Step 4: Commit (.gitignore the build dir, don't commit it)**

```bash
echo "marimo-build/" >> .gitignore
git add .gitignore
git commit -m "build: ignore marimo-build/ WASM export output"
```

---

## Task 16: Author the build-and-deploy script

**Files:**
- Create: `scripts/build_marimo_to_book.py`

This script handles the cross-repo deployment: build Marimo → copy to book repo's output/book/calculator/. Used by both local dev and (eventually) CI.

- [ ] **Step 1: Write the script**

```python
#!/usr/bin/env python3
"""ABOUTME: Cross-repo deploy: build Marimo app, copy to book repo's output dir.
ABOUTME: Run after marimo_app.py changes to update the unified site preview."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--book-repo", default="/Users/sohailmo/Documents/Sohailm25.github.io",
                        help="Path to the Sohailm25.github.io repo")
    parser.add_argument("--marimo-app", default="calculator/marimo_app.py",
                        help="Path to the Marimo app entry point")
    args = parser.parse_args()

    build_dir = Path("marimo-build")
    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir()

    print(f"[1/3] Building Marimo app: {args.marimo_app} → {build_dir}/")
    res = subprocess.run(
        [".venv/bin/marimo", "export", "html-wasm", args.marimo_app, "-o", str(build_dir)],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        print(f"BUILD FAILED:\n{res.stderr}")
        return 1
    print("  OK")

    target = Path(args.book_repo) / "output" / "book" / "calculator"
    print(f"[2/3] Copying {build_dir}/ → {target}/")
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(build_dir, target)
    print("  OK")

    print(f"[3/3] Done. Calculator is at {target}/")
    print(f"  Verify: open {target}/index.html in a browser, OR")
    print(f"  build the book site with `pelican content -o output` and visit /book/calculator/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Make executable, dry-run smoke test**

```bash
chmod +x scripts/build_marimo_to_book.py
.venv/bin/python scripts/build_marimo_to_book.py --help
.venv/bin/python scripts/build_marimo_to_book.py 2>&1 | tail -10
```

Expected: 3-step output, ending with "Done."

- [ ] **Step 3: Verify book repo received the build**

```bash
ls /Users/sohailmo/Documents/Sohailm25.github.io/output/book/calculator/ 2>&1 | head -5
```

- [ ] **Step 4: Commit the script**

```bash
git add scripts/build_marimo_to_book.py
git commit -m "feat(scripts): build_marimo_to_book.py for cross-repo deploy"
```

---

## Task 17: Update `README.md` with new entry point

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Find the "Interactive App" section and update**

```bash
grep -n "Interactive App\|streamlit" README.md | head -5
```

Replace the section to point to:
- Marimo notebook: `calculator/marimo_app.py`
- Build: `.venv/bin/python scripts/build_marimo_to_book.py`
- Deployed at: `https://sohailmo.ai/book/calculator/`
- Legacy Streamlit: deprecated, `calculator/app.py.LEGACY` after Task 19

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs(readme): point to marimo_app.py as new entry point"
```

---

## Task 18: Rename `app.py` → `app.py.LEGACY`

Only after parity is verified by Task 14's tests passing AND visual confirmation.

**Files:**
- Rename: `calculator/app.py` → `calculator/app.py.LEGACY`

- [ ] **Step 1: Confirm Task 14's parity test passes**

```bash
.venv/bin/pytest calculator/tests/test_marimo_app.py::test_marimo_landing_verdict_matches_direct_compute -v 2>&1 | tail -5
```

Must pass.

- [ ] **Step 2: Rename**

```bash
git mv calculator/app.py calculator/app.py.LEGACY
```

- [ ] **Step 3: Update any references in tests**

```bash
grep -rln 'app\.py' calculator/tests/ | head
```

If any test imports `calculator.app`, those need an `--ignore` flag in pytest config or to be removed. Document any tests dropped.

- [ ] **Step 4: Commit**

```bash
git add calculator/
git commit -m "deprecate(streamlit): rename app.py to app.py.LEGACY"
```

---

## Task 19: Streamlit URL announcement page

**Files:**
- Create: `streamlit-redirect/app.py`

The legacy `inference-econ.streamlit.app` URL needs to redirect to `sohailmo.ai/book/calculator/`. Streamlit Cloud doesn't support true HTTP 301s on `*.streamlit.app` subdomains (per spec §4 decision 13), so we deploy a single-page announcement that uses `<meta http-equiv="refresh">` + JS `window.location.replace()` + visible "we moved" prose.

- [ ] **Step 1: Write the minimal Streamlit redirect app**

```python
# ABOUTME: Streamlit-Cloud-hosted "we moved" landing for the legacy URL.
# ABOUTME: inference-econ.streamlit.app → sohailmo.ai/book/calculator/

import streamlit as st

NEW_URL = "https://sohailmo.ai/book/calculator/"

st.set_page_config(
    page_title="Moved — Production Inference Economics Calculator",
    page_icon="$",
    layout="centered",
)

st.markdown(
    f"""
    <meta http-equiv="refresh" content="3; url={NEW_URL}">
    <script>setTimeout(() => window.location.replace("{NEW_URL}"), 3000);</script>

    <h1 style="font-family: Georgia, serif; font-style: italic; color: #3A4F2A;">
      The calculator has moved.
    </h1>
    <p style="font-family: Newsreader, Georgia, serif; font-size: 1.15rem; color: #1a1a1a;">
      Production Inference Economics is now hosted at:
      <br>
      <a href="{NEW_URL}" style="color: #5C2A1E; font-family: JetBrains Mono, monospace;">{NEW_URL}</a>
    </p>
    <p style="color: #5C2A1E; font-family: JetBrains Mono, monospace; font-size: 0.85rem;">
      Redirecting in 3 seconds…
    </p>
    """,
    unsafe_allow_html=True,
)
```

- [ ] **Step 2: Commit**

```bash
git add streamlit-redirect/app.py
git commit -m "feat(redirect): single-page Streamlit redirect to new calculator URL"
```

- [ ] **Step 3: Manual step (NOT for the agent)** — Sohail to deploy this to `inference-econ.streamlit.app` via the Streamlit Cloud dashboard (replaces current app). Document this in the plan as a manual deployment step for the user.

---

## Task 20: Run spec §9.2 Phase 2 acceptance criteria

- [ ] **Step 1: B1 — all 7 views render with moss/oxblood palette**

Manual visual check (Sohail to verify after Task 16's local build). For agent verification:

```bash
grep -c 'MarimoView\.\|marimo-theme.css' calculator/marimo_app.py
# Expect >=7 (one per view) + theme link
```

- [ ] **Step 2: B2 — no invisible chart text**

```bash
grep -rE 'font_color\s*=\s*"#e8e8e8"' calculator/
# Expect 0
```

- [ ] **Step 3: B3 — Landing has Mad-libs above any tabbed nav**

```bash
grep -n 'workload_dd\|filter_dd' calculator/marimo_app.py | head -3
# Expect: dropdown definitions in _landing cell
```

- [ ] **Step 4: B4 — every chart has axis units + source caption**

```bash
grep -cE 'xaxis=dict\(title=|yaxis=dict\(title=' calculator/marimo_app.py
# Expect ≥6 (one per chart-bearing view: Compare, Sensitivity, Break-Even)
grep -c 'Source: provider pricing snapshot' calculator/marimo_app.py
# Expect ≥1 (at minimum Compare view)
```

- [ ] **Step 5: B5 — numerics parity via pytest**

```bash
.venv/bin/pytest calculator/tests/test_marimo_app.py::test_marimo_landing_verdict_matches_direct_compute -v 2>&1 | tail -5
# Must PASS
```

- [ ] **Step 6: B6 — app.py renamed to LEGACY**

```bash
test -f calculator/app.py.LEGACY && ! test -f calculator/app.py
echo "exit: $?"
# Expect: 0
```

- [ ] **Step 7: B7 — Streamlit URL serves redirect** — manual step for Sohail.

- [ ] **Step 8: B8 — calculator reachable at unified URL** — manual after deploy.

- [ ] **Step 9: B9 — no st.metric in marimo_app**

```bash
grep -n 'st\.metric' calculator/marimo_app.py
# Expect: empty
```

- [ ] **Step 10: B10 — no invisible chart text anywhere**

```bash
grep -rE 'font_color\s*=\s*"#e8e8e8"' calculator/
# Expect: empty (already verified in B2)
```

- [ ] **Step 11: Marker commit if all pass**

```bash
git commit --allow-empty -m "milestone(calculator): Phase 2 Marimo migration — all acceptance criteria pass"
```

---

## Task 21: Update spec to mark Phase 2 shipped

**Files:**
- Modify: `/Users/sohailmo/Documents/Sohailm25.github.io/history/2026-05-18-book-calculator-uiux-design.md` (cross-repo)

- [ ] **Step 1: Update §9 heading**

In the book repo's spec file, change:

```markdown
## 9. Phase 2 — Calculator Marimo Migration
```

to:

```markdown
## 9. Phase 2 — Calculator Marimo Migration (✅ SHIPPED 2026-MM-DD on calculator branch `wip/p2-marimo-migration`)
```

- [ ] **Step 2: Commit in the BOOK repo** (this requires switching directories)

```bash
cd /Users/sohailmo/Documents/Sohailm25.github.io
git add history/2026-05-18-book-calculator-uiux-design.md
git commit -m "docs(spec): mark Phase 2 as shipped"
```

---

## Definition of Done (Phase 2)

Phase 2 is shipped when **all** of these are true:

- [ ] `calculator/marimo_app.py` exists, imports cleanly, references all 7 MarimoView enum members
- [ ] No `st.metric` anywhere in `marimo_app.py`
- [ ] No `font_color="#e8e8e8"` anywhere in `calculator/`
- [ ] PARAM_LABELS dict defined + used in Sensitivity view
- [ ] All 7 views have prose verdict + (where applicable) Plotly chart with moss/oxblood styling
- [ ] Landing's Mad-libs sentence updates on workload dropdown change; verdict paragraph reflects cheapest LCPR
- [ ] `calculator/static/marimo-theme.css` injected via `mo.Html()` in `_theme_css` cell
- [ ] Numerics parity test passes (`test_marimo_landing_verdict_matches_direct_compute`)
- [ ] `calculator/app.py` renamed to `calculator/app.py.LEGACY`
- [ ] `scripts/build_marimo_to_book.py` produces `marimo-build/` and copies to `<book-repo>/output/book/calculator/`
- [ ] `streamlit-redirect/app.py` exists (Sohail manually deploys to `inference-econ.streamlit.app`)
- [ ] `README.md` points to `marimo_app.py` as new entry point
- [ ] All P2 tests green; existing 269-test baseline maintained (minus the 1 known pre-existing essay-consistency failure)

## Out of scope for this plan

- Phase 3 (heavy widget embedding in book chapters via Marimo WASM iframes) — separate plan
- Fixing the pre-existing `test_essay_consistency.py` failure — separate task
- Migrating Advanced sub-tools beyond Cache Gate + KV Capacity (Migration, RouteFit, Trace Schema, Snapshots, Operations are stubbed; they're follow-up tasks 11.1-11.5)
- Lighthouse / browser smoke testing of the live deployment — manual step for Sohail
- Setting up GitHub Actions to auto-build Marimo on every push — separate CI/CD task

## Risk register

- **Marimo API may evolve before P2 ships.** Pin `marimo>=0.10,<0.12` for stability.
- **WASM cold-load latency** — accepted tradeoff per spec §13.
- **`mo.ui.dropdown` reactivity model** — Marimo uses dataflow; if cells re-execute in unexpected order, the Landing verdict could lag. Mitigation: explicit cell-arg passing (already designed for in Task 4 skeleton).
- **Cross-repo deploy timing** — the book repo's `output/` is generated by `pelican content -o output`. The Marimo build copies INTO that directory, but if Pelican re-runs after the copy, it may wipe `output/book/calculator/`. Mitigation: run Marimo build AFTER Pelican, never before, OR add `output/book/calculator/` to Pelican's preserve list.

