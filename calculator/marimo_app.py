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
        serverless = next(p for p in calc.providers if p.name == serverless_dd.value)
        dedicated = next(p for p in calc.providers if p.name == dedicated_dd.value)
        be = compute_break_even(serverless, dedicated)

        user_daily_m = daily_tokens_input.value
        serverless_rate_per_m = serverless.output_rate_per_m  # $/M output tokens
        # Per-day dedicated cost is fixed (GPU $/hr × 24); per-token rate decreases with volume.
        dedicated_daily = be.dedicated_daily_cost
        user_serverless_cost = user_daily_m * serverless_rate_per_m

        if not be.break_even_feasible:
            verdict_text = (
                f"At any volume, **{serverless.name}** (serverless) is cheaper than "
                f"**{dedicated.name}** at the stated utilization "
                f"(`{dedicated.utilization * 100:.0f}%`). "
                f"Dedicated effective cost is **${be.effective_cost_per_m:.4f}/M** vs "
                f"serverless **${serverless_rate_per_m:.4f}/M**. "
                f"You'd need utilization ≥ **{be.required_utilization * 100:.1f}%** to break even."
            )
            recommendation = "Serverless"
        else:
            crossover_m = be.break_even_daily_output_tokens / 1_000_000
            if user_daily_m >= crossover_m:
                recommendation = "Dedicated GPU"
                # Daily $ saved by switching to dedicated at this volume.
                savings = user_serverless_cost - dedicated_daily
                verdict_text = (
                    f"At **{user_daily_m:.1f}M tokens/day**, **{dedicated.name}** is cheaper. "
                    f"Estimated daily savings vs **{serverless.name}**: **${savings:,.2f}**. "
                    f"Crossover at **{crossover_m:.2f}M tokens/day**."
                )
            else:
                recommendation = "Serverless"
                verdict_text = (
                    f"At **{user_daily_m:.1f}M tokens/day**, **{serverless.name}** is cheaper. "
                    f"You'd need **{crossover_m:.2f}M tokens/day** to justify "
                    f"**{dedicated.name}** at **${dedicated.gpu_hourly_rate:.2f}/hr** and "
                    f"`{dedicated.utilization * 100:.0f}%` utilization."
                )

        # Sweep daily-token range for the crossover plot. Anchor around the
        # crossover if feasible; otherwise anchor around the user's volume.
        if be.break_even_feasible:
            anchor = be.break_even_daily_output_tokens / 1_000_000
        else:
            anchor = max(user_daily_m, 1.0)
        sweep = [max(anchor * f, 0.01) for f in (0.1, 0.3, 0.6, 1.0, 1.4, 1.8, 2.5)]
        # Always include the user's volume in the sweep so the cost lines pass through it.
        sweep = sorted(set(sweep + [user_daily_m]))

        sweep_cost_serverless = [v * serverless_rate_per_m for v in sweep]
        sweep_cost_dedicated = [dedicated_daily for _ in sweep]  # flat: fixed daily GPU cost

        fig = go.Figure()
        fig.add_scatter(
            x=sweep, y=sweep_cost_dedicated,
            name=f"Dedicated ({dedicated.name})",
            line=dict(color="#3A4F2A", width=2),
            hovertemplate="%{x:.2f}M tok/day<br>$%{y:,.2f}/day<extra>Dedicated</extra>",
        )
        fig.add_scatter(
            x=sweep, y=sweep_cost_serverless,
            name=f"Serverless ({serverless.name})",
            line=dict(color="#5C2A1E", width=2),
            hovertemplate="%{x:.2f}M tok/day<br>$%{y:,.2f}/day<extra>Serverless</extra>",
        )
        # Mark the user's current volume.
        user_y = dedicated_daily if recommendation == "Dedicated GPU" else user_serverless_cost
        fig.add_scatter(
            x=[user_daily_m], y=[user_y],
            mode="markers",
            marker=dict(color="#1a1a1a", size=14, symbol="x"),
            name="Your volume",
            showlegend=False,
            hovertemplate=f"your volume: %{{x:.1f}}M tok/day<br>$%{{y:,.2f}}/day<extra></extra>",
        )
        fig.update_layout(
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

        verdict = mo.md(verdict_text)
        crossover_str = (
            f"**{be.break_even_daily_output_tokens / 1_000_000:.2f}M tokens/day**"
            if be.break_even_feasible else "**not reachable at this utilization**"
        )
        details = mo.accordion({
            "Details": mo.md(
                f"- Recommendation at your volume: **{recommendation}**\n"
                f"- Serverless rate: **${serverless_rate_per_m:.4f}/M output tokens**\n"
                f"- Dedicated effective rate: **${be.effective_cost_per_m:.4f}/M output tokens** "
                f"(at `{dedicated.utilization * 100:.0f}%` utilization)\n"
                f"- Dedicated daily cost: **${dedicated_daily:,.2f}/day** "
                f"(${dedicated.gpu_hourly_rate:.2f}/hr × 24)\n"
                f"- Effective dedicated capacity: "
                f"**{be.effective_capacity_tokens_per_day / 1_000_000:.2f}M tokens/day**\n"
                f"- Crossover volume: {crossover_str}\n"
                f"- Required utilization for break-even: "
                f"**{be.required_utilization * 100:.1f}%**"
            ),
        })
        be_block = mo.vstack([
            mo.md(f"## {MARIMO_VIEW_META[MarimoView.BREAK_EVEN].label}"),
            mo.hstack([serverless_dd, dedicated_dd, daily_tokens_input], justify="start"),
            verdict,
            mo.ui.plotly(fig),
            details,
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
        quality_rate = profile.quality_gate_pass_rate
        latency_rate = latency_pass_slider.value
        n = 200  # screening batch size — enough to stabilize p99
        n_quality_pass = int(n * quality_rate)
        n_latency_pass = int(n * latency_rate)
        # Approximate intersection assuming independence
        n_both = int(n * quality_rate * latency_rate)

        ttft_slo_ms = float(ttft_slo.value)
        tpot_slo_ms = float(tpot_slo.value)
        # Synthesize "passing" and "failing" archetypes around the SLO
        ttft_pass_val = max(50.0, ttft_slo_ms * 0.6)
        ttft_fail_val = ttft_slo_ms * 1.75
        tpot_pass_val = max(5.0, tpot_slo_ms * 0.8)
        tpot_fail_val = tpot_slo_ms * 1.4
        cpr = float(cost_per_req.value)

        requests = []
        for i in range(n):
            if i < n_both:
                qp, ttft, tpot = True, ttft_pass_val, tpot_pass_val
            elif i < n_quality_pass:
                qp, ttft, tpot = True, ttft_fail_val, tpot_fail_val
            elif i < n_quality_pass + max(0, n_latency_pass - n_both):
                qp, ttft, tpot = False, ttft_pass_val, tpot_pass_val
            else:
                qp, ttft, tpot = False, ttft_fail_val, tpot_fail_val
            requests.append(GoodputRequest(
                ttft_ms=ttft,
                tpot_ms=tpot,
                output_tokens=profile.avg_output_tokens,
                quality_pass=qp,
                cost=cpr,
            ))

        # Duration: assume 1 second of arrivals — goodput_rate then
        # reads as "accepted requests in this batch" per second.
        duration = 1.0
        gp = compute_goodput(requests, duration, ttft_slo_ms, tpot_slo_ms)

        # Cost per accepted may be +inf if zero accepted; render safely.
        if gp.accepted_requests == 0:
            cost_str = "**∞** (no requests passed both gates)"
            verdict = mo.md(
                f"At TTFT ≤ **{ttft_slo_ms:.0f} ms** and TPOT ≤ **{tpot_slo_ms:.0f} ms/tok**, "
                f"the `{workload_dd.value}` workload sustains **0 accepted req/s** — "
                f"every request fails at least one gate."
            )
        else:
            cost_str = f"**${gp.cost_per_accepted:.4f}**"
            verdict = mo.md(
                f"At TTFT ≤ **{ttft_slo_ms:.0f} ms**, TPOT ≤ **{tpot_slo_ms:.0f} ms/tok**, "
                f"and quality ≥ **{quality_rate:.0%}** (from `{workload_dd.value}` preset), "
                f"this workload sustains **{gp.goodput_rate:.1f} accepted req/s** at "
                f"{cost_str} per accepted result."
            )

        details = mo.accordion({
            "Details": mo.md(
                f"- Total requests in screening batch: **{gp.total_requests}**\n"
                f"- Accepted (passed all gates): **{gp.accepted_requests}** "
                f"({gp.accepted_requests / gp.total_requests:.0%})\n"
                f"- Goodput rate: **{gp.goodput_rate:.2f} accepted req/s**\n"
                f"- Cost per accepted: {cost_str}\n"
                f"- Total cost (all requests, paid even for failures): "
                f"**${gp.total_cost:.4f}**\n"
                f"- TTFT p99: **{gp.ttft_p99_ms:.0f} ms** "
                f"(SLO: {ttft_slo_ms:.0f} ms)\n"
                f"- TPOT p99: **{gp.tpot_p99_ms:.2f} ms/tok** "
                f"(SLO: {tpot_slo_ms:.0f} ms)\n"
                f"- Quality pass rate: **{gp.quality_pass_rate:.0%}** "
                f"(from profile)\n"
                f"- Latency pass rate: **{gp.latency_pass_rate:.0%}** "
                f"(from synthesis slider)"
            ),
        })

        caption = mo.md(
            f"<small style='color:#5C2A1E;font-family:JetBrains Mono,monospace'>"
            f"Source: synthesized {n}-request batch from `{workload_dd.value}` profile · "
            f"Derivation 5 (goodput = accepted/duration)</small>"
        )

        gp_block = mo.vstack([
            mo.md(f"## {MARIMO_VIEW_META[MarimoView.GOODPUT].label}"),
            mo.hstack(
                [ttft_slo, tpot_slo, latency_pass_slider, cost_per_req],
                justify="start",
            ),
            verdict,
            details,
            caption,
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
        result = compute_trace_to_margin(
            trace_cost=float(ttm_trace_cost.value),
            invoice_amount=float(ttm_invoice.value),
            eval_cost=float(ttm_eval_cost.value),
            human_cost=float(ttm_human_cost.value),
            ops_cost=float(ttm_ops_cost.value),
            total_attempts=int(ttm_attempts.value),
            accepted_units=int(ttm_accepted.value),
            revenue_per_unit=float(ttm_revenue_per_unit.value),
        )

        verdict = mo.md(
            f"LCPR is **${result.lcpr:.4f}** per accepted unit. Gross margin "
            f"is **${result.gross_margin:,.2f}** "
            f"(**{result.gross_margin_pct:.1%}** of revenue). The loaded-to-naive "
            f"ratio is **{result.lcpr_to_naive_ratio:.2f}×** — naive trace cost "
            f"per attempt was **${result.naive_cost_per_unit:.4f}**."
        )

        details = mo.accordion({
            "Cost breakdown": mo.md(
                f"- Raw trace cost: **${result.trace_cost:,.2f}**\n"
                f"- Invoice amount: **${result.invoice_amount:,.2f}** "
                f"(invoice − trace delta: **${result.delta:,.2f}**)\n"
                f"- Eval cost: **${result.eval_cost:,.2f}**\n"
                f"- Human escalation: **${result.human_cost:,.2f}**\n"
                f"- Ops cost: **${result.ops_cost:,.2f}**\n"
                f"- **Total loaded cost: ${result.total_loaded_cost:,.2f}**\n"
                f"- Accepted units: **{result.accepted_units:,}**\n"
                f"- Revenue: **${result.revenue:,.2f}** "
                f"(@ ${ttm_revenue_per_unit.value:.4f}/unit)"
            ),
        })

        caption = mo.md(
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
            verdict,
            details,
            caption,
        ])
    except Exception as e:
        ttm_block = mo.md(f"_Trace-to-margin computation error: {e}_")
    ttm_block
    return ttm_block


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
