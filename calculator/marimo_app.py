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
def _theme_css(mo, Path):
    """Inject palette + typography (moss/oxblood + Newsreader/JBMono).
    Loads marimo-theme.css from the static/ directory so the Marimo chrome
    inherits the book design.
    """
    _css_path = Path(__file__).parent / "static" / "marimo-theme.css"
    _css_text = _css_path.read_text() if _css_path.exists() else ""
    mo.Html(f"""
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href='https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Newsreader:opsz,wght@6..72,400;6..72,500;6..72,700&family=JetBrains+Mono:wght@400;500;600;700&display=swap' rel='stylesheet'>
    <style>{_css_text}</style>
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
    _sorted_results = sorted(results, key=lambda r: r.lcpr)
    cheapest = _sorted_results[0] if _sorted_results else None
    _second = _sorted_results[1] if len(_sorted_results) > 1 else None

    _sentence = mo.md(
        f"I want to serve **Llama 3.1 8B** for **{workload_dd.value}**, "
        f"expecting **{profile.avg_input_tokens:,} in / {profile.avg_output_tokens:,} out** "
        f"tokens per call. Show me LCPR across **{filter_dd.value}**."
    )

    if cheapest and _second:
        _verdict = mo.md(
            f"At your volume, **{cheapest.provider_name}** is cheapest at LCPR "
            f"**${cheapest.lcpr:.4f}** vs. **{_second.provider_name}** at LCPR "
            f"**${_second.lcpr:.4f}**. See the **Compare** view for the full table."
        )
    elif cheapest:
        _verdict = mo.md(
            f"At your volume, **{cheapest.provider_name}** is the only matching config "
            f"at LCPR **${cheapest.lcpr:.4f}**."
        )
    else:
        _verdict = mo.md("_No matching configurations for this filter._")

    landing_block = mo.vstack([
        mo.md(f"# Production Inference Economics — {MARIMO_VIEW_META[MarimoView.LANDING].label}"),
        mo.hstack([workload_dd, filter_dd], justify="start"),
        _sentence,
        _verdict,
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
        _sorted_results = sorted(results, key=lambda r: r.lcpr)

        # Plotly bar chart, moss + oxblood palette per book.css
        _deploy_color = {
            "closed_api": "#5C2A1E",       # oxblood — closed API
            "serverless_open": "#3A4F2A",  # moss — serverless open
            "dedicated": "#7a8a5a",        # moss-light — dedicated
        }

        _fig = go.Figure()
        for r in _sorted_results:
            _fig.add_bar(
                x=[f"{r.provider_name} · {r.deployment_mode}"],
                y=[r.lcpr],
                marker_color=_deploy_color.get(r.deployment_mode, "#3A4F2A"),
                showlegend=False,
                hovertemplate=f"<b>{r.provider_name}</b><br>LCPR: $%{{y:.4f}}<extra>{r.deployment_mode}</extra>",
            )
        _fig.update_layout(
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
        _cheapest = _sorted_results[0]
        _verdict = mo.md(
            f"**{_cheapest.provider_name} ({_cheapest.deployment_mode})** is the lowest loaded cost per accepted result "
            f"at **${_cheapest.lcpr:.4f}** for your `{workload_dd.value}` profile."
        )

        # Source caption
        _caption = mo.md(
            f"<small style='color:#5C2A1E;font-family:JetBrains Mono,monospace'>"
            f"Source: provider pricing snapshot · Derivation 1</small>"
        )

        compare_block = mo.vstack([
            mo.md(f"## {MARIMO_VIEW_META[MarimoView.COMPARE].label}"),
            _verdict,
            mo.ui.plotly(_fig),
            _caption,
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
    _param = param_dd.value
    _human_label = PARAM_LABELS.get(_param, _param)

    _current = getattr(profile, _param, None)
    if _current is None or _current == 0:
        sens_block = mo.vstack([
            mo.md(f"## {MARIMO_VIEW_META[MarimoView.SENSITIVITY].label}"),
            param_dd,
            mo.md(f"_Parameter `{_param}` not present on profile, or value is zero._"),
        ])
    else:
        # Sweep ±50% in 9 steps
        _lo = max(_current * 0.5, 0)
        _hi = _current * 1.5
        _sweep = [_lo + (_hi - _lo) * i / 8 for i in range(9)]

        _lcprs = []
        for v in _sweep:
            _sweep_profile = replace(profile, **{_param: v})
            _results = calc.compare(_sweep_profile)
            _cheapest = min(_results, key=lambda r: r.lcpr).lcpr if _results else 0
            _lcprs.append(_cheapest)

        _fig = go.Figure()
        _fig.add_scatter(
            x=_sweep, y=_lcprs, mode="lines+markers",
            line=dict(color="#3A4F2A", width=2),
            marker=dict(color="#5C2A1E", size=8),
            hovertemplate=f"{_human_label}: %{{x:.4f}}<br>LCPR: $%{{y:.4f}}<extra></extra>",
        )
        _fig.add_scatter(
            x=[_current], y=[_lcprs[4]], mode="markers",
            marker=dict(color="#5C2A1E", size=14, symbol="x"),
            hovertemplate=f"current {_human_label}: %{{x:.4f}}<extra></extra>",
            showlegend=False,
        )
        _fig.update_layout(
            plot_bgcolor="#faf5e9",
            paper_bgcolor="#faf5e9",
            font_family="Newsreader, Georgia, serif",
            font_color="#1a1a1a",
            xaxis=dict(title=f"{_human_label}", gridcolor="#e0d8c0", tickfont=dict(family="JetBrains Mono", size=11)),
            yaxis=dict(title="LCPR ($)", gridcolor="#e0d8c0", tickfont=dict(family="JetBrains Mono", size=11)),
            margin=dict(t=10, b=50, l=60, r=20),
            height=400,
            showlegend=False,
        )

        _delta = _lcprs[-1] - _lcprs[0]
        _direction = "increases" if _delta > 0 else ("decreases" if _delta < 0 else "is flat at")
        _pct = abs(_delta / _lcprs[4]) * 100 if _lcprs[4] else 0
        _verdict = mo.md(
            f"As **{_human_label}** sweeps from `{_lo:.4f}` to `{_hi:.4f}`, LCPR {_direction} by "
            f"**${abs(_delta):.4f}** (**{_pct:.1f}%** of current). "
            f"The current value `{_current:.4f}` is marked with an `×`."
        )

        sens_block = mo.vstack([
            mo.md(f"## {MARIMO_VIEW_META[MarimoView.SENSITIVITY].label}"),
            param_dd,
            _verdict,
            mo.ui.plotly(_fig),
        ])
    sens_block
    return sens_block


# ── Break-Even view (Task 8) ──
@app.cell
def _break_even_inputs(mo, calc):
    """Break-Even input cell — choose serverless vs dedicated provider + daily volume."""
    serverless_providers = [
        p for p in calc.providers if p.deployment_mode in ("serverless_open", "closed_api")
    ]
    dedicated_providers = [p for p in calc.providers if p.deployment_mode == "dedicated"]

    serverless_names = [p.name for p in serverless_providers]
    dedicated_names = [p.name for p in dedicated_providers]

    serverless_dd = mo.ui.dropdown(
        options=serverless_names,
        value="Together AI Llama 3.3 70B" if "Together AI Llama 3.3 70B" in serverless_names else serverless_names[0],
        label="serverless option",
    )
    dedicated_dd = mo.ui.dropdown(
        options=dedicated_names,
        value="Together AI H100 80GB" if "Together AI H100 80GB" in dedicated_names else dedicated_names[0],
        label="dedicated option",
    )
    daily_tokens_input = mo.ui.number(
        value=10.0, start=0.1, stop=10000.0, step=1.0,
        label="your daily output (millions of tokens)",
    )
    return (
        serverless_dd, dedicated_dd, daily_tokens_input,
        serverless_providers, dedicated_providers,
    )


@app.cell
def _break_even_render(
    mo, go, calc, compute_break_even,
    serverless_dd, dedicated_dd, daily_tokens_input,
    MARIMO_VIEW_META, MarimoView,
):
    """Render the break-even crossover chart + verdict.

    Adapted from plan: real compute_break_even signature is
    (serverless: ProviderPricing, dedicated: ProviderPricing) -> BreakEvenResult.
    We pick providers from the catalog rather than a free-form $/hr input.
    """
    try:
        _serverless = next(p for p in calc.providers if p.name == serverless_dd.value)
        _dedicated = next(p for p in calc.providers if p.name == dedicated_dd.value)
        _be = compute_break_even(_serverless, _dedicated)

        _user_daily_m = daily_tokens_input.value
        _serverless_rate_per_m = _serverless.output_rate_per_m  # $/M output tokens
        # Per-day dedicated cost is fixed (GPU $/hr × 24); per-token rate decreases with volume.
        _dedicated_daily = _be.dedicated_daily_cost
        _user_serverless_cost = _user_daily_m * _serverless_rate_per_m

        if not _be.break_even_feasible:
            _verdict_text = (
                f"At any volume, **{_serverless.name}** (serverless) is cheaper than "
                f"**{_dedicated.name}** at the stated utilization "
                f"(`{_dedicated.utilization * 100:.0f}%`). "
                f"Dedicated effective cost is **${_be.effective_cost_per_m:.4f}/M** vs "
                f"serverless **${_serverless_rate_per_m:.4f}/M**. "
                f"You'd need utilization ≥ **{_be.required_utilization * 100:.1f}%** to break even."
            )
            _recommendation = "Serverless"
        else:
            _crossover_m = _be.break_even_daily_output_tokens / 1_000_000
            if _user_daily_m >= _crossover_m:
                _recommendation = "Dedicated GPU"
                # Daily $ saved by switching to dedicated at this volume.
                _savings = _user_serverless_cost - _dedicated_daily
                _verdict_text = (
                    f"At **{_user_daily_m:.1f}M tokens/day**, **{_dedicated.name}** is cheaper. "
                    f"Estimated daily savings vs **{_serverless.name}**: **${_savings:,.2f}**. "
                    f"Crossover at **{_crossover_m:.2f}M tokens/day**."
                )
            else:
                _recommendation = "Serverless"
                _verdict_text = (
                    f"At **{_user_daily_m:.1f}M tokens/day**, **{_serverless.name}** is cheaper. "
                    f"You'd need **{_crossover_m:.2f}M tokens/day** to justify "
                    f"**{_dedicated.name}** at **${_dedicated.gpu_hourly_rate:.2f}/hr** and "
                    f"`{_dedicated.utilization * 100:.0f}%` utilization."
                )

        # Sweep daily-token range for the crossover plot. Anchor around the
        # crossover if feasible; otherwise anchor around the user's volume.
        if _be.break_even_feasible:
            _anchor = _be.break_even_daily_output_tokens / 1_000_000
        else:
            _anchor = max(_user_daily_m, 1.0)
        _sweep = [max(_anchor * f, 0.01) for f in (0.1, 0.3, 0.6, 1.0, 1.4, 1.8, 2.5)]
        # Always include the user's volume in the sweep so the cost lines pass through it.
        _sweep = sorted(set(_sweep + [_user_daily_m]))

        _sweep_cost_serverless = [v * _serverless_rate_per_m for v in _sweep]
        _sweep_cost_dedicated = [_dedicated_daily for _ in _sweep]  # flat: fixed daily GPU cost

        _fig = go.Figure()
        _fig.add_scatter(
            x=_sweep, y=_sweep_cost_dedicated,
            name=f"Dedicated ({_dedicated.name})",
            line=dict(color="#3A4F2A", width=2),
            hovertemplate="%{x:.2f}M tok/day<br>$%{y:,.2f}/day<extra>Dedicated</extra>",
        )
        _fig.add_scatter(
            x=_sweep, y=_sweep_cost_serverless,
            name=f"Serverless ({_serverless.name})",
            line=dict(color="#5C2A1E", width=2),
            hovertemplate="%{x:.2f}M tok/day<br>$%{y:,.2f}/day<extra>Serverless</extra>",
        )
        # Mark the user's current volume.
        _user_y = _dedicated_daily if _recommendation == "Dedicated GPU" else _user_serverless_cost
        _fig.add_scatter(
            x=[_user_daily_m], y=[_user_y],
            mode="markers",
            marker=dict(color="#1a1a1a", size=14, symbol="x"),
            name="Your volume",
            showlegend=False,
            hovertemplate=f"your volume: %{{x:.1f}}M tok/day<br>$%{{y:,.2f}}/day<extra></extra>",
        )
        _fig.update_layout(
            plot_bgcolor="#faf5e9", paper_bgcolor="#faf5e9",
            font_family="Newsreader, Georgia, serif", font_color="#1a1a1a",
            xaxis=dict(
                title="Daily output (millions of tokens)",
                gridcolor="#e0d8c0",
                tickfont=dict(family="JetBrains Mono", size=11),
            ),
            yaxis=dict(
                title="Daily $",
                gridcolor="#e0d8c0",
                tickfont=dict(family="JetBrains Mono", size=11),
            ),
            margin=dict(t=10, b=50, l=70, r=20),
            height=400,
            legend=dict(x=0.02, y=0.98, bgcolor="rgba(250,245,233,0.8)"),
        )

        _verdict = mo.md(_verdict_text)
        _crossover_str = (
            f"**{_be.break_even_daily_output_tokens / 1_000_000:.2f}M tokens/day**"
            if _be.break_even_feasible else "**not reachable at this utilization**"
        )
        _details = mo.accordion({
            "Details": mo.md(
                f"- Recommendation at your volume: **{_recommendation}**\n"
                f"- Serverless rate: **${_serverless_rate_per_m:.4f}/M output tokens**\n"
                f"- Dedicated effective rate: **${_be.effective_cost_per_m:.4f}/M output tokens** "
                f"(at `{_dedicated.utilization * 100:.0f}%` utilization)\n"
                f"- Dedicated daily cost: **${_dedicated_daily:,.2f}/day** "
                f"(${_dedicated.gpu_hourly_rate:.2f}/hr × 24)\n"
                f"- Effective dedicated capacity: "
                f"**{_be.effective_capacity_tokens_per_day / 1_000_000:.2f}M tokens/day**\n"
                f"- Crossover volume: {_crossover_str}\n"
                f"- Required utilization for break-even: "
                f"**{_be.required_utilization * 100:.1f}%**"
            ),
        })
        be_block = mo.vstack([
            mo.md(f"## {MARIMO_VIEW_META[MarimoView.BREAK_EVEN].label}"),
            mo.hstack([serverless_dd, dedicated_dd, daily_tokens_input], justify="start"),
            _verdict,
            mo.ui.plotly(_fig),
            _details,
        ])
    except Exception as e:
        be_block = mo.md(f"_Break-even computation error: {e}_")
    be_block
    return be_block


# ── Goodput view (Task 9) ──
@app.cell
def _goodput_inputs(mo):
    """Goodput view — input cell.
    Real compute_goodput signature operates on per-request samples
    (list[GoodputRequest] + SLO thresholds), NOT a single SLO struct.
    We synthesize a representative request batch from summary rates,
    mirroring the legacy app's screening pattern (lcpr.py:compute_goodput).
    """
    ttft_slo = mo.ui.slider(100, 5000, value=800, step=100, label="TTFT SLO (ms)")
    tpot_slo = mo.ui.slider(10, 200, value=50, step=5, label="TPOT SLO (ms/tok)")
    latency_pass_slider = mo.ui.slider(
        0.0, 1.0, value=0.90, step=0.01,
        label="Latency pass rate (frac. meeting TTFT+TPOT SLO)",
    )
    cost_per_req = mo.ui.number(
        start=0.0001, stop=1.0, value=0.011, step=0.0005,
        label="Cost per request ($)",
    )
    return ttft_slo, tpot_slo, latency_pass_slider, cost_per_req


@app.cell
def _goodput_render(
    mo, profile, compute_goodput, workload_dd,
    ttft_slo, tpot_slo, latency_pass_slider, cost_per_req,
    MARIMO_VIEW_META, MarimoView,
):
    """Goodput view — accepted req/s under SLO + cost per accepted result.

    Adapted from plan: compute_goodput takes per-request samples, not a
    profile object. We synthesize 200 requests from (quality_pass_rate
    from profile) × (latency_pass_rate from slider), then route them
    through compute_goodput with the user's SLO thresholds.
    Prose verdict first; details below in an expander (spec §9.1 step 7).
    """
    try:
        from calculator.lcpr import GoodputRequest

        # Source quality pass rate from the workload profile so the
        # view is reactive to the Landing dropdown.
        _quality_rate = profile.quality_gate_pass_rate
        _latency_rate = latency_pass_slider.value
        _n = 200  # screening batch size — enough to stabilize p99
        _n_quality_pass = int(_n * _quality_rate)
        _n_latency_pass = int(_n * _latency_rate)
        # Approximate intersection assuming independence
        _n_both = int(_n * _quality_rate * _latency_rate)

        _ttft_slo_ms = float(ttft_slo.value)
        _tpot_slo_ms = float(tpot_slo.value)
        # Synthesize "passing" and "failing" archetypes around the SLO
        _ttft_pass_val = max(50.0, _ttft_slo_ms * 0.6)
        _ttft_fail_val = _ttft_slo_ms * 1.75
        _tpot_pass_val = max(5.0, _tpot_slo_ms * 0.8)
        _tpot_fail_val = _tpot_slo_ms * 1.4
        _cpr = float(cost_per_req.value)

        _requests = []
        for i in range(_n):
            if i < _n_both:
                _qp, _ttft, _tpot = True, _ttft_pass_val, _tpot_pass_val
            elif i < _n_quality_pass:
                _qp, _ttft, _tpot = True, _ttft_fail_val, _tpot_fail_val
            elif i < _n_quality_pass + max(0, _n_latency_pass - _n_both):
                _qp, _ttft, _tpot = False, _ttft_pass_val, _tpot_pass_val
            else:
                _qp, _ttft, _tpot = False, _ttft_fail_val, _tpot_fail_val
            _requests.append(GoodputRequest(
                ttft_ms=_ttft,
                tpot_ms=_tpot,
                output_tokens=profile.avg_output_tokens,
                quality_pass=_qp,
                cost=_cpr,
            ))

        # Duration: assume 1 second of arrivals — goodput_rate then
        # reads as "accepted requests in this batch" per second.
        _duration = 1.0
        _gp = compute_goodput(_requests, _duration, _ttft_slo_ms, _tpot_slo_ms)

        # Cost per accepted may be +inf if zero accepted; render safely.
        if _gp.accepted_requests == 0:
            _cost_str = "**∞** (no requests passed both gates)"
            _verdict = mo.md(
                f"At TTFT ≤ **{_ttft_slo_ms:.0f} ms** and TPOT ≤ **{_tpot_slo_ms:.0f} ms/tok**, "
                f"the `{workload_dd.value}` workload sustains **0 accepted req/s** — "
                f"every request fails at least one gate."
            )
        else:
            _cost_str = f"**${_gp.cost_per_accepted:.4f}**"
            _verdict = mo.md(
                f"At TTFT ≤ **{_ttft_slo_ms:.0f} ms**, TPOT ≤ **{_tpot_slo_ms:.0f} ms/tok**, "
                f"and quality ≥ **{_quality_rate:.0%}** (from `{workload_dd.value}` preset), "
                f"this workload sustains **{_gp.goodput_rate:.1f} accepted req/s** at "
                f"{_cost_str} per accepted result."
            )

        _details = mo.accordion({
            "Details": mo.md(
                f"- Total requests in screening batch: **{_gp.total_requests}**\n"
                f"- Accepted (passed all gates): **{_gp.accepted_requests}** "
                f"({_gp.accepted_requests / _gp.total_requests:.0%})\n"
                f"- Goodput rate: **{_gp.goodput_rate:.2f} accepted req/s**\n"
                f"- Cost per accepted: {_cost_str}\n"
                f"- Total cost (all requests, paid even for failures): "
                f"**${_gp.total_cost:.4f}**\n"
                f"- TTFT p99: **{_gp.ttft_p99_ms:.0f} ms** "
                f"(SLO: {_ttft_slo_ms:.0f} ms)\n"
                f"- TPOT p99: **{_gp.tpot_p99_ms:.2f} ms/tok** "
                f"(SLO: {_tpot_slo_ms:.0f} ms)\n"
                f"- Quality pass rate: **{_gp.quality_pass_rate:.0%}** "
                f"(from profile)\n"
                f"- Latency pass rate: **{_gp.latency_pass_rate:.0%}** "
                f"(from synthesis slider)"
            ),
        })

        _caption = mo.md(
            f"<small style='color:#5C2A1E;font-family:JetBrains Mono,monospace'>"
            f"Source: synthesized {_n}-request batch from `{workload_dd.value}` profile · "
            f"Derivation 5 (goodput = accepted/duration)</small>"
        )

        gp_block = mo.vstack([
            mo.md(f"## {MARIMO_VIEW_META[MarimoView.GOODPUT].label}"),
            mo.hstack(
                [ttft_slo, tpot_slo, latency_pass_slider, cost_per_req],
                justify="start",
            ),
            _verdict,
            _details,
            _caption,
        ])
    except Exception as e:
        gp_block = mo.md(f"_Goodput computation error: {e}_")
    gp_block
    return gp_block


# ── Trace-to-Margin view (Task 10) ──
@app.cell
def _trace_to_margin_inputs(mo):
    """Input controls for the Trace-to-Margin view.

    Field names match the real compute_trace_to_margin signature
    (trace_cost, invoice_amount, …, revenue_per_unit) — Derivation 6.
    """
    ttm_attempts = mo.ui.number(
        value=100000, start=1, step=1000, label="Total attempts/month",
    )
    ttm_accepted = mo.ui.number(
        value=82000, start=1, step=1000, label="Accepted units/month",
    )
    ttm_trace_cost = mo.ui.number(
        value=14200.0, start=0.0, step=100.0, label="Raw trace cost ($)",
    )
    ttm_invoice = mo.ui.number(
        value=15050.0, start=0.0, step=100.0, label="Invoice amount ($)",
    )
    ttm_eval_cost = mo.ui.number(
        value=620.0, start=0.0, step=50.0, label="Eval cost ($)",
    )
    ttm_human_cost = mo.ui.number(
        value=1840.0, start=0.0, step=100.0, label="Human escalation cost ($)",
    )
    ttm_ops_cost = mo.ui.number(
        value=720.0, start=0.0, step=50.0, label="Ops cost ($)",
    )
    ttm_revenue_per_unit = mo.ui.number(
        value=0.30, start=0.0, step=0.01, label="Revenue per accepted unit ($)",
    )
    return (
        ttm_attempts, ttm_accepted, ttm_trace_cost, ttm_invoice,
        ttm_eval_cost, ttm_human_cost, ttm_ops_cost, ttm_revenue_per_unit,
    )


@app.cell
def _trace_to_margin(
    mo, compute_trace_to_margin,
    ttm_attempts, ttm_accepted, ttm_trace_cost, ttm_invoice,
    ttm_eval_cost, ttm_human_cost, ttm_ops_cost, ttm_revenue_per_unit,
    MARIMO_VIEW_META, MarimoView,
):
    """Reconcile raw traces to loaded cost and gross margin (Derivation 6).

    Adapted from plan: real signature uses trace_cost + invoice_amount
    (delta is computed internally), and result exposes total_loaded_cost,
    gross_margin, gross_margin_pct, lcpr_to_naive_ratio (not the plan's
    speculative names). Prose verdict first; cost breakdown in expander
    (spec §9.1 step 7).
    """
    try:
        _result = compute_trace_to_margin(
            trace_cost=float(ttm_trace_cost.value),
            invoice_amount=float(ttm_invoice.value),
            eval_cost=float(ttm_eval_cost.value),
            human_cost=float(ttm_human_cost.value),
            ops_cost=float(ttm_ops_cost.value),
            total_attempts=int(ttm_attempts.value),
            accepted_units=int(ttm_accepted.value),
            revenue_per_unit=float(ttm_revenue_per_unit.value),
        )

        _verdict = mo.md(
            f"LCPR is **${_result.lcpr:.4f}** per accepted unit. Gross margin "
            f"is **${_result.gross_margin:,.2f}** "
            f"(**{_result.gross_margin_pct:.1%}** of revenue). The loaded-to-naive "
            f"ratio is **{_result.lcpr_to_naive_ratio:.2f}×** — naive trace cost "
            f"per attempt was **${_result.naive_cost_per_unit:.4f}**."
        )

        _details = mo.accordion({
            "Cost breakdown": mo.md(
                f"- Raw trace cost: **${_result.trace_cost:,.2f}**\n"
                f"- Invoice amount: **${_result.invoice_amount:,.2f}** "
                f"(invoice − trace delta: **${_result.delta:,.2f}**)\n"
                f"- Eval cost: **${_result.eval_cost:,.2f}**\n"
                f"- Human escalation: **${_result.human_cost:,.2f}**\n"
                f"- Ops cost: **${_result.ops_cost:,.2f}**\n"
                f"- **Total loaded cost: ${_result.total_loaded_cost:,.2f}**\n"
                f"- Accepted units: **{_result.accepted_units:,}**\n"
                f"- Revenue: **${_result.revenue:,.2f}** "
                f"(@ ${ttm_revenue_per_unit.value:.4f}/unit)"
            ),
        })

        _caption = mo.md(
            f"<small style='color:#5C2A1E;font-family:JetBrains Mono,monospace'>"
            f"Source: user inputs · Derivation 6 "
            f"(LCPR = loaded_cost / accepted_units)</small>"
        )

        ttm_block = mo.vstack([
            mo.md(f"## {MARIMO_VIEW_META[MarimoView.TRACE_TO_MARGIN].label}"),
            mo.hstack(
                [ttm_attempts, ttm_accepted, ttm_revenue_per_unit],
                justify="start",
            ),
            mo.hstack(
                [ttm_trace_cost, ttm_invoice, ttm_eval_cost],
                justify="start",
            ),
            mo.hstack(
                [ttm_human_cost, ttm_ops_cost],
                justify="start",
            ),
            _verdict,
            _details,
            _caption,
        ])
    except Exception as e:
        ttm_block = mo.md(f"_Trace-to-margin computation error: {e}_")
    ttm_block
    return ttm_block


# ── Advanced view (Task 11) ──
@app.cell
def _advanced_cache_inputs(mo):
    """Input controls for the Cache Gate sub-tool.

    Field names match the real compute_cache_break_even signature
    (prefix_tokens, uncached_input_price_per_m, cache_write_price_per_m,
    cache_read_price_per_m, storage_price_per_m_hour, storage_hours).
    The plan's ttl_hours / reuse_rate / per_call_savings kwargs do not
    exist on the function — adapted to the real Derivation 3 formula.
    """
    cache_prefix_tokens = mo.ui.number(
        value=50000, start=0, step=1000, label="Cacheable prefix tokens",
    )
    cache_uncached_price = mo.ui.number(
        value=3.00, start=0.0, step=0.10, label="Uncached input price ($/M)",
    )
    cache_write_price = mo.ui.number(
        value=3.75, start=0.0, step=0.10, label="Cache write price ($/M)",
    )
    cache_read_price = mo.ui.number(
        value=0.30, start=0.0, step=0.05, label="Cache read price ($/M)",
    )
    cache_storage_price = mo.ui.number(
        value=0.0, start=0.0, step=0.01, label="Storage price ($/M-hour)",
    )
    cache_storage_hours = mo.ui.number(
        value=0.0, start=0.0, step=0.25, label="Retention hours",
    )
    return (
        cache_prefix_tokens, cache_uncached_price, cache_write_price,
        cache_read_price, cache_storage_price, cache_storage_hours,
    )


@app.cell
def _advanced_kv_inputs(mo):
    """Input controls for the KV Capacity sub-tool.

    Field names match the real compute_kv_sizing signature (n_layers,
    n_kv_heads, head_dim, element_bytes, kv_pool_bytes, resident_tokens,
    headroom_fraction, weight_bytes). The plan's context_length /
    hbm_budget_gb / model_size_b / kv_bytes_per_token kwargs are not
    the real API — adapted to Derivation 2 formula.
    """
    kv_n_layers = mo.ui.number(
        value=80, start=1, step=1, label="Layers",
    )
    kv_n_heads = mo.ui.number(
        value=8, start=1, step=1, label="KV heads",
    )
    kv_head_dim = mo.ui.number(
        value=128, start=1, step=8, label="Head dimension",
    )
    kv_element_bytes = mo.ui.dropdown(
        options={"1 (int8)": 1, "2 (fp16/bf16)": 2, "4 (fp32)": 4},
        value="2 (fp16/bf16)",
        label="KV dtype bytes",
    )
    kv_pool_gb = mo.ui.number(
        value=40.0, start=0.1, step=1.0, label="KV pool (GB)",
    )
    kv_resident_tokens = mo.ui.number(
        value=4096, start=1, step=1024, label="Resident tokens / sequence",
    )
    kv_headroom = mo.ui.slider(
        0.0, 0.50, value=0.10, step=0.05, label="Headroom fraction",
    )
    kv_weight_gb = mo.ui.number(
        value=140.0, start=0.0, step=1.0, label="Weight memory (GB, optional)",
    )
    return (
        kv_n_layers, kv_n_heads, kv_head_dim, kv_element_bytes,
        kv_pool_gb, kv_resident_tokens, kv_headroom, kv_weight_gb,
    )


@app.cell
def _advanced(
    mo, compute_cache_break_even, compute_kv_sizing,
    cache_prefix_tokens, cache_uncached_price, cache_write_price,
    cache_read_price, cache_storage_price, cache_storage_hours,
    kv_n_layers, kv_n_heads, kv_head_dim, kv_element_bytes,
    kv_pool_gb, kv_resident_tokens, kv_headroom, kv_weight_gb,
    MARIMO_VIEW_META, MarimoView,
):
    """Advanced view — collapsible group of 7 sub-tools.

    Cache Gate (Derivation 3) and KV Capacity (Derivation 2) are live.
    Migration, RouteFit, Trace Schema, Snapshots, and Operations are
    stubbed as P2-T11.1-T11.5 follow-up tasks (see plan).

    Each compute call is wrapped in try/except so a single bad input
    does not blank the whole view.
    """
    # ── Cache Gate sub-panel ──
    try:
        _cache_result = compute_cache_break_even(
            prefix_tokens=int(cache_prefix_tokens.value),
            uncached_input_price_per_m=float(cache_uncached_price.value),
            cache_write_price_per_m=float(cache_write_price.value),
            cache_read_price_per_m=float(cache_read_price.value),
            storage_price_per_m_hour=float(cache_storage_price.value),
            storage_hours=float(cache_storage_hours.value),
        )
        if _cache_result.break_even_requests == float("inf"):
            _break_even_text = "**Never** (cache read price ≥ uncached price)"
        else:
            _break_even_text = f"**{_cache_result.break_even_requests:.2f}** reuses"
        _savings_10 = _cache_result.savings_at_n.get(10, 0.0)
        _savings_100 = _cache_result.savings_at_n.get(100, 0.0)
        _cache_panel = mo.vstack([
            mo.hstack(
                [cache_prefix_tokens, cache_uncached_price, cache_write_price],
                justify="start",
            ),
            mo.hstack(
                [cache_read_price, cache_storage_price, cache_storage_hours],
                justify="start",
            ),
            mo.md(
                f"Cache pays off at {_break_even_text} of the cached prefix. "
                f"Storage cost over retention: **${_cache_result.storage_cost:.4f}**. "
                f"Projected savings at 10 reuses: **${_savings_10:.4f}**; "
                f"at 100 reuses: **${_savings_100:.4f}**."
            ),
            mo.md(
                "<small style='color:#5C2A1E;font-family:JetBrains Mono,monospace'>"
                "Source: user inputs · Derivation 3 "
                "(N_break_even = (p_write − p_read + H·p_storage) / (p_in − p_read))"
                "</small>"
            ),
        ])
    except Exception as e:
        _cache_panel = mo.md(f"_Cache Gate computation error: {e}_")

    # ── KV Capacity sub-panel ──
    try:
        _kv_result = compute_kv_sizing(
            n_layers=int(kv_n_layers.value),
            n_kv_heads=int(kv_n_heads.value),
            head_dim=int(kv_head_dim.value),
            element_bytes=int(kv_element_bytes.value),
            kv_pool_bytes=float(kv_pool_gb.value) * 1_000_000_000,
            resident_tokens=int(kv_resident_tokens.value),
            headroom_fraction=float(kv_headroom.value),
            weight_bytes=float(kv_weight_gb.value) * 1_000_000_000,
        )
        if _kv_result.context_length_at_weight_parity:
            _parity_text = (
                f"weight-parity context length is "
                f"**{_kv_result.context_length_at_weight_parity:,}** tokens"
            )
        else:
            _parity_text = "weight-parity context length is **N/A**"
        _kv_panel = mo.vstack([
            mo.hstack(
                [kv_n_layers, kv_n_heads, kv_head_dim, kv_element_bytes],
                justify="start",
            ),
            mo.hstack(
                [kv_pool_gb, kv_resident_tokens, kv_headroom, kv_weight_gb],
                justify="start",
            ),
            mo.md(
                f"KV bytes/token: **{_kv_result.kv_bytes_per_token:,.0f}**. "
                f"Per-sequence KV memory: "
                f"**{_kv_result.total_kv_memory_per_seq / 1e9:.2f} GB**. "
                f"Maximum concurrent live sequences: "
                f"**{_kv_result.max_live_sequences:,}** "
                f"(after {kv_headroom.value:.0%} headroom). "
                f"The {_parity_text}."
            ),
            mo.md(
                "<small style='color:#5C2A1E;font-family:JetBrains Mono,monospace'>"
                "Source: user inputs · Derivation 2 "
                "(kv_bytes_per_token = 2·n_layers·n_kv_heads·head_dim·element_bytes)"
                "</small>"
            ),
        ])
    except Exception as e:
        _kv_panel = mo.md(f"_KV Capacity computation error: {e}_")

    # ── Compose tabs (5 stubs are P2-T11.1-T11.5 follow-ups) ──
    advanced_block = mo.vstack([
        mo.md(f"## {MARIMO_VIEW_META[MarimoView.ADVANCED].label}"),
        mo.md(
            "Collapsible group of advanced analyses. Cache Gate and KV Capacity "
            "are live; the remaining sub-tools are scheduled as P2-T11.1-T11.5 "
            "follow-ups and currently render placeholders."
        ),
        mo.ui.tabs({
            "Cache Gate": _cache_panel,
            "KV Capacity": _kv_panel,
            "Migration": mo.md(
                "_Migration readiness scoring — TODO (P2-T11.1, port from "
                "app.py:602-852)._"
            ),
            "RouteFit": mo.md(
                "_RouteFit matrix — TODO (P2-T11.2)._"
            ),
            "Trace Schema": mo.md(
                "_Trace event format reference — TODO (P2-T11.3)._"
            ),
            "Snapshots": mo.md(
                "_Source pricing snapshots — TODO (P2-T11.4)._"
            ),
            "Operations": mo.md(
                "_Operational views — TODO (P2-T11.5)._"
            ),
        }),
    ])
    advanced_block
    return advanced_block


if __name__ == "__main__":
    app.run()
