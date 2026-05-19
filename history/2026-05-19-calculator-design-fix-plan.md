# Calculator Design Fix — Implementation Plan (Scope C)

**Date:** 2026-05-19
**Branch (to create):** `wip/calculator-design-fix` in `inference-field-guide/`
**Companion repo:** `Sohailm25.github.io/` (the deployed WASM bundle lands at `content/extra/book/calculator/`)
**Status:** Plan-reviewer pass complete; revisions applied; awaiting Sohail approval to execute Phase 2

## Plan-reviewer findings (incorporated)

A `plan-reviewer` agent reviewed the first draft. Verdict: **needs revision**. Corrections applied below:

| Issue | Severity | Resolution |
|---|---|---|
| Branch creation was at Task 3.2 (after Phase 2 commits land on whatever branch is checked out) | **Critical** | Added Task 2.0 "Create branch from master" as the first step of Phase 2. |
| Task 2.1 snippet used wrong attribute names (`loaded_to_naive_ratio`, `naive_trace_cost_per_attempt`) | **Critical** | Verified against source — real names are `lcpr_to_naive_ratio` and `naive_cost_per_unit`. Snippet corrected. |
| Task 2.1 only flagged 3 sites; the actual `**$...**` pattern occurs in **25 sites** across Landing / Sensitivity / Break-Even / Goodput / Trace-to-Margin / Cache-Gate verdicts AND their detail-accordion bodies | **Critical** | Task 2.1 reworked as a global sweep (grep + targeted Edits) instead of three hand-written replacements. |
| Task 2.4 CSS missing: `mo.ui.switch` (`[role="switch"]`), `:focus-visible` rings, plotly modebar, `marimo-accordion button` trigger, text input fallback | **Important** | Added rules for each. |
| Task 2.3 rationale understated the issue | **Important** | Re-phrased: a bare `mo.Html(...)` expression call produces no cell output because Marimo cells render the *last expression value* or the explicit return — discarded calls vanish. Returning `mo.Html(...)` makes it the cell's output. |
| `bargap=0.25` on small-N (2–3 results) charts produces awkwardly wide bars | Minor | Added clamp: `bargap=min(0.25, 0.5 / max(2, len(_sorted_results)))`. |
| Decision 6 called it "preload" but pseudocode injects a stylesheet `<link>` | Minor | Renamed to "Inject Google Fonts stylesheet" in decision + task. |
| C10 Lighthouse target ≥85 unrealistic for cold WASM bundle | Minor | Re-scoped to warm-load only; cold-load excluded. |
| Task 3.3 merge skipped any review checkpoint on the book repo | Minor | Added a "review the diff in `output/book/calculator/` before merge" sub-step. |
| Plan did not reference the **previously-specified Phase 3 widget embedding** from `2026-05-18-book-calculator-uiux-design.md §10` | **Important (from Sohail)** | Added Phase 5 — Heavy Widget Embedding (follow-up; depends on Phase 4 sign-off). |

---

## Why

The deployed calculator at `sohailmo.ai/book/calculator/` doesn't visually match the rest of the v2 site + book. Three distinct problems:

1. **Mangled text** — `**$0.0019** vs. **...** at LCPR **$0.0020**` patterns get pulled into KaTeX math mode (because `$` opens inline math), rendering `vs.` as italic math `vs.` and `**` as `∗∗` operators.
2. **Bar chart unreadable** — Compare view has ~30 provider/config labels rotated 90° at the X-axis, overlapping each other.
3. **Theme CSS misses** — `calculator/static/marimo-theme.css` exists with moss + oxblood styling, but its selectors target Streamlit / Marimo 0.10 DOM, not Marimo 0.23.6. Form controls render with default Radix styling. "made with marimo" badge visible.

---

## Discovery — done

Two scout agents ran in parallel during planning. Their outputs ground this plan.

### Agent A — Selector truth-table (excerpt)

Full table in agent output; key findings:

- `marimo-slider`, `marimo-tabs`, `marimo-dropdown`, `marimo-number`, `marimo-accordion` are **plain custom elements** (no Shadow DOM) — externally styleable.
- Durable selectors are ARIA roles + Radix data attributes + custom element tag names.
- Watermark badge: `[data-testid="watermark"]` (hide with `display: none`).
- "Run or Edit" banner: `[data-testid="static-notebook-banner"]` + `[data-testid="static-notebook-dialog-trigger"]`.
- Cell width: `.marimo-cell { max-width: 88ch }` (uses inherit; constraint propagates).
- The medium-width column wrapper uses Tailwind utility `max-w-(--content-width-medium)` — no stable class; override by setting the CSS var on `#App`.

### Agent B — Build pipeline

- Source: `calculator/marimo_app.py` + `calculator/*.py` + `provider_pricing.yaml` + `calculator/static/marimo-theme.css`
- Bundler: `scripts/bundle_marimo_for_wasm.py` inlines everything (including the theme CSS as a string) into `calculator/marimo_app_wasm.py`.
- WASM export: `marimo export html-wasm calculator/marimo_app_wasm.py -o marimo-build/`
- Deploy: `scripts/build_marimo_to_book.py` runs the full pipeline and copies `marimo-build/` → `Sohailm25.github.io/content/extra/book/calculator/`.
- One-shot end-to-end rebuild command:
  ```bash
  cd /Users/sohailmo/inference-field-guide && .venv/bin/python scripts/build_marimo_to_book.py
  ```
- No incremental WASM build. Fast preview path (native Python, no WASM): `.venv/bin/marimo run calculator/marimo_app.py`.

---

## Decisions

| # | Axis | Decision | Rationale |
|---|---|---|---|
| 1 | Currency escape | Wrap dollar amounts in backticks (`` `$0.0019` ``) | Site already uses monospace for numerics; backticks are exempt from KaTeX; cleanest fix. |
| 2 | Bar chart | Switch to horizontal bars (provider on y-axis, LCPR on x-axis); auto-height by N rows | 30+ providers don't fit on a vertical axis; horizontal is the standard pattern for many-categories ranking. |
| 3 | Theme selector strategy | Custom element tag + ARIA role + Radix data attributes; class-substring as fallback | Survives Marimo version bumps; hashed class names like `.marimo-Button-CuKU-ENz` would break on every release. |
| 4 | Marimo branding | Hide watermark + Run-or-Edit banner via CSS `display: none` | Calculator is embedded in a published book; the branding is noise. |
| 5 | `_theme_css` cell | Refactor to return `mo.Html(...)` instead of bare expression + `return None` | Defensive — guarantees the CSS reaches the rendered DOM through Marimo's normal output pipeline. |
| 6 | Inject Google Fonts stylesheet into bundle | Add Newsreader + Instrument Serif + JetBrains Mono `<link rel="stylesheet">` to the bundle's `index.html` via a post-export patch step (NOT `rel="preload"` — the pseudocode injects a stylesheet load) | Eliminates the Lora → Newsreader flash. Marimo bundles Lora by default and we can't stop that, but we can ship our fonts as a stylesheet alongside. |
| 7 | Iteration loop | Fast preview via `marimo run` during development; full WASM rebuild + deploy only when ready to ship | The full pipeline takes >30s; fast loop is essential for the iterative theme work in Phase 4. |
| 8 | Scope of preserved Marimo defaults | Keep Marimo's cell layout, scroll behavior, accordion expand/collapse interactivity untouched | Don't fight Marimo's UX; only restyle. |

---

## Out of Scope

- Adding new calculator views / changing the seven-view structure.
- Changing the LCPR math or the `provider_pricing.yaml` data.
- Touching the `inference-econ.streamlit.app` legacy redirect.
- Restyling the iframe widgets that book chapters embed (separate follow-up).
- Removing the Marimo dependency. (Far too disruptive; theme overrides are sufficient.)

---

## File Map

| File | Operation | Phase |
|---|---|---|
| `calculator/marimo_app.py` | Modify — 3 verdict strings, Compare-view chart, `_theme_css` cell | 2 |
| `calculator/static/marimo-theme.css` | Replace — full rewrite using Agent A selector truth-table | 2 |
| `scripts/build_marimo_to_book.py` | Modify — add post-export font-preload injection step | 2 |
| `calculator/marimo_app_wasm.py` | Auto-regenerated by bundler — never edited by hand | 3 |
| `<book-repo>/content/extra/book/calculator/*` | Auto-copied by deploy script | 3 |

---

## Phase 2 — Code fixes (one branch, multiple commits)

### Task 2.0 — Create branch (FIRST, before any code edits)

- [ ] **Run:**

```bash
cd /Users/sohailmo/inference-field-guide
git checkout master 2>/dev/null || git checkout main
git pull
git checkout -b wip/calculator-design-fix
```
Expected: clean working tree, branch created. If `inference-field-guide` is currently on a feature branch with uncommitted work, ask Sohail before switching.

### Task 2.1 — Convert all `**$VALUE**` patterns to `` `$VALUE` `` (25 sites)

Bug: KaTeX (Marimo's math renderer) treats `$...$` as inline-math delimiters. When `mo.md(...)` content contains two or more `$` signs with `**` between them, the whole region becomes math, rendering bold markers as `∗∗` operators.

Fix: wrap dollar-prefixed values in backticks. Inline code is exempt from KaTeX parsing, AND backticks already match the site convention of monospace for numerics.

- [ ] **File:** `calculator/marimo_app.py`
- [ ] **Sites (verified by grep):** lines 114, 115, 120, 185, 273, 347, 348, 360, 368, 434, 435, 437, 549, 565, 665, 666, 669, 674, 675, 676, 677, 678, 679, 682, 839, 840, 841 — across Landing / Compare / Sensitivity / Break-Even (verdict + accordion body) / Goodput (verdict + accordion body) / Trace-to-Margin (verdict + cost-breakdown accordion body) / Cache-Gate verdict.

- [ ] **Verification before:**
```bash
grep -c '\*\*\$' calculator/marimo_app.py
```
Expected: 25+ (depends on current commit; record the number).

- [ ] **Approach:** because 25 sites span ~12 separate f-string blocks, edit each block targetedly via Read + Edit. Pattern to apply within every `mo.md(...)` body: `**${expr:fmt}**` → `` `${expr:fmt}` ``. Bold-but-non-`$` markers (e.g., `**{provider_name}**`, `**{count:,}**`) stay as bold.

Corrected snippets for the three sites previously called out (note variable name fixes):

```python
# Landing verdict (lines 113-121)
if cheapest and _second:
    _verdict = mo.md(
        f"At your volume, **{cheapest.provider_name}** is cheapest at LCPR "
        f"`${cheapest.lcpr:.4f}` vs. **{_second.provider_name}** at LCPR "
        f"`${_second.lcpr:.4f}`. See the **Compare** view for the full table."
    )
elif cheapest:
    _verdict = mo.md(
        f"At your volume, **{cheapest.provider_name}** is the only matching config "
        f"at LCPR `${cheapest.lcpr:.4f}`."
    )
```

```python
# Trace-to-Margin verdict (lines 664-670) — variable names verified against source
_verdict = mo.md(
    f"LCPR is `${_result.lcpr:.4f}` per accepted unit. Gross margin "
    f"is `${_result.gross_margin:,.2f}` "
    f"(**{_result.gross_margin_pct:.1%}** of revenue). The loaded-to-naive "
    f"ratio is **{_result.lcpr_to_naive_ratio:.2f}×** — naive trace cost "
    f"per attempt was `${_result.naive_cost_per_unit:.4f}`."
)
```

```python
# Trace-to-Margin cost breakdown accordion (lines 673-684)
_details = mo.accordion({
    "Cost breakdown": mo.md(
        f"- Raw trace cost: `${_result.trace_cost:,.2f}`\n"
        f"- Invoice amount: `${_result.invoice_amount:,.2f}` "
        f"(invoice − trace delta: `${_result.delta:,.2f}`)\n"
        f"- Eval cost: `${_result.eval_cost:,.2f}`\n"
        f"- Human escalation: `${_result.human_cost:,.2f}`\n"
        f"- Ops cost: `${_result.ops_cost:,.2f}`\n"
        f"- **Total loaded cost: `${_result.total_loaded_cost:,.2f}`**\n"
        f"- Accepted units: **{_result.accepted_units:,}**\n"
        f"- Revenue: `${_result.revenue:,.2f}` "
        f"(@ `${ttm_revenue_per_unit.value:.4f}/unit`)"
    ),
})
```

```python
# Cache-Gate verdict (lines 839-841)
_verdict = mo.md(
    f"Cache pays off at **{_break_even:.2f}** reuses of the cached prefix. "
    f"Storage cost over retention: `${_cache_result.storage_cost:.4f}`. "
    f"Projected savings at 10 reuses: `${_savings_10:.4f}`; "
    f"at 100 reuses: `${_savings_100:.4f}`."
)
```

Other sites (Sensitivity line 273, Break-Even lines 347-368 + accordion 434-437, Goodput line 549 + accordion 565): apply the same `**$X**` → `` `$X` `` rewrite. Read the actual lines before editing to preserve surrounding format strings.

- [ ] **Verification after:**
```bash
grep -c '\*\*\$' calculator/marimo_app.py
```
Expected: `0`.

- [ ] **Sanity check:** `.venv/bin/marimo run calculator/marimo_app.py` — open in browser, cycle through all seven views, confirm no rendered text contains `∗∗` characters and every dollar amount appears in monospace.
- [ ] **Commit:** `fix(calc): wrap dollar amounts in backticks to bypass KaTeX math mode`

### Task 2.2 — Compare-view: horizontal bars + auto-height

- [ ] **File:** `calculator/marimo_app.py` lines 160–178
- [ ] **Replace** the `_fig` construction block with:

```python
_fig = go.Figure()
# Reverse so lowest LCPR is at the top of the chart (visual hierarchy: cheapest first).
for r in reversed(_sorted_results):
    _fig.add_bar(
        x=[r.lcpr],
        y=[f"{r.provider_name} · {r.deployment_mode}"],
        orientation="h",
        marker_color=_deploy_color.get(r.deployment_mode, "#3A4F2A"),
        showlegend=False,
        hovertemplate=f"<b>{r.provider_name}</b><br>LCPR: $%{{x:.4f}}<extra>{r.deployment_mode}</extra>",
    )
_fig.update_layout(
    plot_bgcolor="#faf5e9",
    paper_bgcolor="#faf5e9",
    font_family="Newsreader, Iowan Old Style, Georgia, serif",
    font_color="#1a1a1a",
    xaxis=dict(title="LCPR ($)", gridcolor="#e0d8c0", tickfont=dict(family="JetBrains Mono", size=11)),
    yaxis=dict(gridcolor="#e0d8c0", tickfont=dict(family="JetBrains Mono", size=11), automargin=True),
    margin=dict(t=10, b=40, l=20, r=20),  # left margin shrinks (no y-axis title); yaxis tick uses automargin
    height=max(360, 22 * len(_sorted_results)),  # ~22px per row, min 360px
    bargap=min(0.25, 0.5 / max(2, len(_sorted_results))),  # clamp so 2-3 result charts don't get ultra-wide bars
)
```

- [ ] **Verification:** local preview with `.venv/bin/marimo run calculator/marimo_app.py`. Switch through workloads — at any workload the chart should render readable provider names on the y-axis.
- [ ] **Commit:** `fix(calc): switch Compare-view bar chart to horizontal for readability`

### Task 2.3 — Fix the `_theme_css` cell return value

Bug (more accurate than the first draft): a Marimo cell renders the *last expression value* or the explicit `return` value. The current cell at lines 50–64 calls `mo.Html(...)` as a bare expression statement (its value is discarded) and then `return`s `None`. Result: the CSS may not reach the rendered DOM at all, or may only reach it through whatever incidental side effects Marimo applies to expression statements (unreliable across Marimo versions).

The moss tokens DO appear in the deployed HTML (I verified earlier), but it's via the bundled notebook code being parsed into Marimo's static export — not through the cell's runtime output. The fix below makes the injection deterministic.

- [ ] **File:** `calculator/marimo_app.py` lines 50–64
- [ ] **Replace** with:

```python
@app.cell
def _theme_css(mo, Path):
    """Inject palette + typography (moss/oxblood + Newsreader/JBMono).
    Loads marimo-theme.css from the static/ directory so the Marimo chrome
    inherits the book design.
    """
    _css_path = Path(__file__).parent / "static" / "marimo-theme.css"
    _css_text = _css_path.read_text() if _css_path.exists() else ""
    return mo.Html(f"""
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href='https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Newsreader:opsz,wght@6..72,400;6..72,500;6..72,700&family=JetBrains+Mono:wght@400;500;600;700&display=swap' rel='stylesheet'>
    <style>{_css_text}</style>
    """)
```

- [ ] **Commit:** `fix(calc): return mo.Html() from theme cell so CSS reliably injects`

### Task 2.4 — Rewrite `marimo-theme.css` against the real DOM

- [ ] **File:** `calculator/static/marimo-theme.css` (replace contents)
- [ ] **Coverage:** plan-reviewer flagged missing rules for `mo.ui.switch`, `:focus-visible`, plotly modebar, `marimo-accordion` button trigger, text input fallback. All added below.
- [ ] **New file body:**

```css
/* ABOUTME: Marimo 0.23 theme override — moss + oxblood, Newsreader body.
   ABOUTME: Selectors target Marimo's actual custom-element + Radix DOM. */

:root {
  --paper:      #faf5e9;
  --paper-tint: #f7f1e2;
  --ink:        #3A4F2A;
  --ink-soft:   #a3ad8a;
  --brown:      #5C2A1E;
  --brown-soft: #b39a90;
  --text:       #1a1a1a;
  --text-deck:  #4a4a4a;
  --text-mute:  #8a8a8a;
  /* Override Marimo's medium-width column to the book's reading measure */
  --content-width-medium: 88ch;
}

/* ── Page background + body type ─────────────── */
html, body { background: var(--paper) !important; }
body {
  color: var(--text) !important;
  font-family: 'Newsreader', 'Iowan Old Style', Georgia, serif !important;
  font-feature-settings: "tnum" 1, "lnum" 1;
}

/* ── Hide Marimo branding + run-or-edit banner ─ */
[data-testid="watermark"],
[data-testid="static-notebook-banner"],
[data-testid="static-notebook-dialog-trigger"] {
  display: none !important;
}

/* ── Headings — moss ───────────────────────────── */
h1, h2, h3, h4, h5, h6 {
  color: var(--ink) !important;
  font-family: 'Newsreader', 'Iowan Old Style', Georgia, serif !important;
  letter-spacing: -0.01em;
}

/* ── Inline code / monospace data ──────────────── */
code, pre, kbd, samp {
  font-family: 'JetBrains Mono', 'SF Mono', monospace !important;
  font-variant-numeric: tabular-nums slashed-zero;
}
code {
  background: var(--paper-tint);
  padding: 0.1em 0.35em;
  border-radius: 2px;
  font-size: 0.92em;
}

/* ── Links — body color, moss-soft underline ────── */
a {
  color: var(--text) !important;
  text-decoration: underline;
  text-decoration-color: var(--ink-soft);
  text-underline-offset: 0.18em;
}
a:hover { color: var(--brown) !important; text-decoration-color: var(--brown); }

/* ── Dropdown (Radix Select via custom element) ── */
marimo-dropdown [role="combobox"] {
  background: var(--paper) !important;
  border: 1px solid var(--ink) !important;
  color: var(--text) !important;
  font-family: 'JetBrains Mono', monospace !important;
  font-size: 0.85rem !important;
  padding: 0.35em 0.7em !important;
  border-radius: 2px !important;
}
marimo-dropdown [role="combobox"][data-state="open"] {
  outline: 2px solid var(--ink-soft);
  outline-offset: 1px;
}
[role="listbox"] {
  background: var(--paper) !important;
  border: 1px solid var(--ink) !important;
  font-family: 'JetBrains Mono', monospace !important;
  font-size: 0.85rem !important;
  border-radius: 2px !important;
}
[role="option"][data-highlighted] { background: var(--paper-tint) !important; color: var(--ink) !important; }
[role="option"][data-state="checked"] { color: var(--ink) !important; font-weight: 700; }

/* ── Slider (custom element wrapping Radix Slider) ── */
marimo-slider [data-testid="track"] {
  background: var(--ink-soft) !important;
  height: 4px !important;
  border-radius: 2px !important;
}
marimo-slider [data-testid="range"] {
  background: var(--ink) !important;
}
marimo-slider [role="slider"] {
  background: var(--ink) !important;
  border: 2px solid var(--paper) !important;
  width: 14px !important;
  height: 14px !important;
  box-shadow: 0 0 0 1px var(--ink) !important;
}

/* ── Number input (React-Aria spinbutton) ─────── */
marimo-number [role="group"] {
  border: 1px solid var(--ink) !important;
  border-radius: 2px !important;
  background: var(--paper) !important;
}
marimo-number [role="spinbutton"] {
  font-family: 'JetBrains Mono', monospace !important;
  font-size: 0.85rem !important;
  background: transparent !important;
  border: none !important;
  color: var(--text) !important;
  padding: 0.3em 0.6em !important;
}
marimo-number [slot="increment"],
marimo-number [slot="decrement"] {
  background: var(--paper-tint) !important;
  color: var(--ink) !important;
  border-left: 1px solid var(--ink) !important;
}

/* ── Tabs (Radix Tabs via custom element) ─────── */
marimo-tabs [role="tablist"] {
  border-bottom: 1px solid var(--ink-soft) !important;
  gap: 0 !important;
}
marimo-tabs [role="tab"] {
  font-family: 'JetBrains Mono', monospace !important;
  font-size: 0.78rem !important;
  text-transform: uppercase !important;
  letter-spacing: 0.08em !important;
  color: var(--text-deck) !important;
  background: transparent !important;
  border: none !important;
  border-bottom: 2px solid transparent !important;
  padding: 0.5em 1em !important;
  margin-bottom: -1px !important;
}
marimo-tabs [role="tab"]:hover { color: var(--ink) !important; }
marimo-tabs [role="tab"][data-state="active"] {
  color: var(--ink) !important;
  border-bottom-color: var(--ink) !important;
  font-weight: 700 !important;
}

/* ── Accordion (Radix Accordion via custom element) ── */
marimo-accordion {
  border-top: 1px solid var(--ink-soft) !important;
  border-bottom: 1px solid var(--ink-soft) !important;
  margin: 0.5em 0 !important;
  background: transparent !important;
}
marimo-accordion h3,
marimo-accordion button {
  font-family: 'JetBrains Mono', monospace !important;
  font-size: 0.85rem !important;
  text-transform: uppercase !important;
  letter-spacing: 0.06em !important;
  color: var(--ink) !important;
  background: transparent !important;
  border: none !important;
  padding: 0.5em 0 !important;
  cursor: pointer !important;
  text-align: left !important;
}
marimo-accordion [role="region"] {
  padding: 0.5em 0 !important;
}

/* ── Switch (mo.ui.switch via Radix Switch) ───── */
marimo-switch [role="switch"] {
  background: var(--ink-soft) !important;
  border: 1px solid var(--ink) !important;
}
marimo-switch [role="switch"][data-state="checked"] {
  background: var(--ink) !important;
}
marimo-switch [role="switch"] [data-state] {
  background: var(--paper) !important;
}

/* ── Text input fallback (mo.ui.text, generic <input type="text">) ── */
marimo-text input,
input[type="text"]:not([role="spinbutton"]):not([role="combobox"]) {
  font-family: 'JetBrains Mono', monospace !important;
  font-size: 0.85rem !important;
  background: var(--paper) !important;
  border: 1px solid var(--ink) !important;
  color: var(--text) !important;
  border-radius: 2px !important;
  padding: 0.3em 0.6em !important;
}

/* ── Focus rings (keyboard nav) — moss-soft outline ── */
:focus-visible {
  outline: 2px solid var(--ink-soft) !important;
  outline-offset: 2px !important;
  border-radius: 2px;
}
[role="tab"]:focus-visible,
[role="option"]:focus-visible {
  outline-offset: -2px !important;
}

/* ── Plotly chart modebar (the toolbar that appears on hover) ── */
.modebar {
  background: var(--paper-tint) !important;
  border: 1px solid var(--ink-soft) !important;
  border-radius: 2px !important;
}
.modebar-btn path { fill: var(--text-deck) !important; }
.modebar-btn:hover path { fill: var(--ink) !important; }
.modebar-btn.active path { fill: var(--brown) !important; }

/* ── Tables (data) ─────────────────────────────── */
table { border-collapse: collapse; width: 100%; font-family: 'Newsreader', Georgia, serif; font-size: 0.92rem; }
th, td { padding: 0.4rem 0.6rem; text-align: left; border-bottom: 1px solid var(--ink-soft); }
th {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--ink);
  background: var(--paper-tint);
}

/* ── Cell column width — match book reading measure ── */
.marimo-cell { max-width: inherit; }
```

- [ ] **Commit:** `feat(calc): rewrite marimo-theme.css against Marimo 0.23 DOM`

### Task 2.5 — Font preload patch in `build_marimo_to_book.py`

- [ ] **File:** `scripts/build_marimo_to_book.py`
- [ ] After the copy step, add a tiny post-process step that opens the copied `content/extra/book/calculator/index.html` and inserts three `<link rel="preload" as="font">` lines for Newsreader, Instrument Serif, and JetBrains Mono before the `</head>` tag. Use Google Fonts woff2 URLs.

Pseudocode (drop in to the right place in the script):
```python
import re
idx = book_calc_dir / "index.html"
html = idx.read_text()
preloads = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Newsreader:opsz,wght@6..72,400;6..72,500;6..72,700&family=JetBrains+Mono:wght@400;500;600;700&display=swap">
"""
if "fonts.googleapis.com" not in html:
    html = html.replace("</head>", preloads + "</head>", 1)
    idx.write_text(html)
    print("[build_marimo_to_book] injected Google Fonts preload into index.html")
```

- [ ] **Commit:** `chore(build): inject site fonts into deployed calculator index.html`

---

## Phase 3 — Build + deploy

### Task 3.1 — Rebuild the WASM bundle

```bash
cd /Users/sohailmo/inference-field-guide
.venv/bin/python scripts/build_marimo_to_book.py 2>&1 | tail -20
```
Expected: pipeline runs all three stages, copies into `<book-repo>/content/extra/book/calculator/`.

### Task 3.2 — Push the source repo branch

Branch already created at Task 2.0. Per-task commits already exist. Just push:

```bash
cd /Users/sohailmo/inference-field-guide
git status  # sanity check — should show clean tree, branch wip/calculator-design-fix, 4 commits ahead of master
git push -u origin wip/calculator-design-fix
```

### Task 3.3 — Commit + push the book repo

```bash
cd /Users/sohailmo/Documents/Sohailm25.github.io
git checkout master && git pull
git checkout -b wip/calc-redeploy-design-fix

# Review the diff in output before staging — confirm no unexpected files moved
git status
git diff --stat content/extra/book/calculator/ | head

git add content/extra/book/calculator/
git commit -m "feat(book): redeploy calculator with v2 design fixes"
git push -u origin wip/calc-redeploy-design-fix

# If master is branch-protected, fall back to a PR:
#   gh pr create --base master --title "Redeploy calculator with v2 design fixes" --body "..."
# Otherwise direct merge:
git checkout master
git merge --no-ff wip/calc-redeploy-design-fix -m "Merge calc-redeploy-design-fix"
git push origin master
```

### Task 3.4 — Watch the deploy

```bash
gh run watch
```

---

## Phase 4 — Verify + iterate (Sohail-driven)

After deploy:

- [ ] **Visual check on desktop** at `https://sohailmo.ai/book/calculator/`. Cycle through the seven views.
- [ ] **Visual check on mobile** — at iPhone width, the chart should be horizontally scrollable if needed; form controls should be moss-bordered.
- [ ] **Specific things to verify** (mapped to acceptance criteria):
  - The Landing-view verdict reads "**DeepInfra GPT-OSS-120B** is cheapest at LCPR `$0.0019` vs. **Together AI Qwen3 8B** at LCPR `$0.0020`" — bold provider names, monospace dollar amounts. No `∗∗vs.∗∗` math glitch.
  - The Compare-view bar chart renders horizontally with provider names left-aligned on the y-axis.
  - The "made with marimo" badge is gone.
  - Tabs in Advanced section (Cache Gate / KV Capacity / Migration / etc.) render as mono-uppercase moss text with active tab underlined.
  - Dropdowns and sliders show moss borders / moss accent, not Radix default.

- [ ] **If something looks wrong**, Sohail opens browser devtools, inspects the offending element, captures the actual selector hierarchy (right-click → Copy → Copy selector). Send to me; I update `marimo-theme.css` and re-run Phase 3.

Realistic iteration budget: 2-3 rounds of devtools → CSS update → rebuild before everything looks correct. Each round is ~5 min.

---

## Acceptance criteria

| # | Criterion | Verification |
|---|---|---|
| C1 | No `∗∗text∗∗` math-mode artifacts anywhere on the calculator | Visual scan of all 7 views |
| C2 | Compare-view bar chart readable (provider names not overlapping) | Visual |
| C3 | `[data-testid="watermark"]` not visible | Devtools or `display: none` confirmed |
| C4 | Dropdowns render with moss border + parchment background | Visual |
| C5 | Sliders show moss accent + thumb | Visual |
| C6 | Tabs in Advanced section show mono-uppercase + moss-underlined active state | Visual |
| C7 | Number input fields render with moss border + JBMono font | Visual |
| C8 | Calculator's body type renders in Newsreader (not Lora) after page load completes | Devtools `getComputedStyle` |
| C9 | No regressions in interactivity (sliders move, dropdowns open, tabs switch) | Manual test |
| C10 | Lighthouse Performance ≥85 on the calculator page (**warm load only — cold WASM load excluded** as it pulls ~5–8 MB Pyodide) | One-shot Lighthouse run after first navigation primes the cache |

---

## Risks

| Risk | Mitigation |
|---|---|
| Some Marimo selectors in the truth-table are wrong; theme misses a control | Phase 4 iteration; ARIA roles are stable so worst case is per-component touch-up. |
| The `build_marimo_to_book.py` script breaks because of a marimo CLI version change | Pin the marimo version in `requirements.txt`; if it does break, fast-fix in script. |
| The font preload injection conflicts with Marimo's own preloads | Both can coexist; CSS cascade picks ours since theme CSS uses `!important`. |
| `marimo run` (fast preview) renders differently than `marimo export html-wasm` (deploy) | Always do at least one full WASM rebuild + local preview via `python -m http.server` before pushing. |
| 30+ horizontal bars become a very tall chart (~700px) | Acceptable; user scrolls. If users complain, add a "top N" filter later. |
| Backticks around `$X.XX` might look out of place if surrounding text is in serif | The site convention is monospace for numerics; consistency win. Visual sample in Phase 4 confirms. |
| CSS selectors in Task 2.4 cover most but not all controls — `mo.ui.checkbox`, `mo.ui.radio`, `mo.ui.date`, file-pickers untested | Phase 4 iteration; ARIA roles are durable so missing controls are quick to patch (one rule per type). |
| Book repo `master` may have branch protection (no direct push) | If `git push origin master` fails, fall back to `gh pr create` for the merge step. Plan documents the merge command path; PR is a one-flag swap. |
| Font stylesheet injection in `build_marimo_to_book.py` runs every deploy — could double-inject if the index.html is regenerated mid-pipeline | Pseudocode guards with `if "fonts.googleapis.com" not in html`. Safe. |
| The `mo.accordion` accordion button selector covers the new Radix DOM but might miss a legacy structure for an older accordion variant | Phase 4 catches it; CSS fallback adds `marimo-accordion > details > summary` as a backup selector. |

---

## Rollback

Per-PR revert if anything looks wrong on production:

```bash
# In Sohailm25.github.io:
git revert <merge-commit-hash>
git push origin master
```

This restores the previous calculator bundle. The source-repo changes can stay or be reverted independently:

```bash
# In inference-field-guide:
git revert <commit-hash>
```

---

## Phase 5 — Heavy Widget Embedding (follow-up, conditional on Phase 4 sign-off)

This was specified in the previous design doc at `Sohailm25.github.io/history/2026-05-18-book-calculator-uiux-design.md §10 (Phase 3 — Heavy Widget Embedding)` but never executed. Reviving here because the design-system work in Phase 2 is a structural prerequisite — without a clean theme CSS, embedded widgets would inherit the broken styling.

### Scope: six inline chapter widgets

One Marimo notebook per page, embedded as iframe at the point the derivation is introduced:

| Chapter | Widget | Inputs (var-active slots) | Output | `lcpr.py` function |
|---|---|---|---|---|
| Part 1, Ch 2 | LCPR live formula | retry rate · quality gate · cache hit · batch fraction · monthly requests | Loaded $/result · naive $/result · ratio | `compute_lcpr` |
| Part 2, Ch 3 | Sensitivity sparkline | parameter selector · sweep range (min, max, steps) | LCPR-vs-parameter mini line chart | `compute_lcpr` (iterated) |
| Part 2, Ch 4 | Break-even crossover | daily output tokens · dedicated GPU cost/hr | Crossover volume verdict + crossover chart | `compute_break_even` |
| Part 3, Ch 5 | Cache gate | TTL · reuse rate · prefix tokens · per-call savings | Min reuses within TTL to break even | `compute_cache_break_even` |
| Part 3, Ch 6 | KV capacity envelope | context length · HBM budget · model size · KV bytes/tok | Max concurrent sequences | `compute_kv_sizing` |
| Part 4, Ch 7 | Goodput frontier | latency SLO · quality SLO · request mix · provider | Accepted req/s under SLO + cost per accepted | `compute_goodput` |

### Architecture (per the prior spec)

Build one Marimo notebook at `calculator/widgets/inline_widgets.py` with a router cell that reads `mo.cli_args().get("widget")` and renders only the requested cell. One WASM build → six iframes, one shared Pyodide bootstrap cached across all chapters.

Each chapter embeds:

```html
<iframe src="/book/calculator/widgets/?widget=lcpr"
        class="book-widget-frame" loading="lazy"
        style="width:100%; aspect-ratio: 4/3; border: 1px solid var(--ink-soft);">
</iframe>
```

### Files (Phase 5)

| File | Operation |
|---|---|
| `calculator/widgets/inline_widgets.py` | **New** — single-notebook six-cell router |
| `calculator/widgets/router.py` (helper) | **New** — small dispatch helper if needed |
| `scripts/build_widgets_to_book.py` | **New** — analogous to `build_marimo_to_book.py` but emits to `content/extra/book/calculator/widgets/` |
| `<book-repo>/content/extra/book/part-1/index.html` | **Modify** — insert `<iframe>` at the right paragraph in Ch 2 |
| `<book-repo>/content/extra/book/part-2/index.html` | **Modify** — insert 2 iframes (sensitivity, break-even) |
| `<book-repo>/content/extra/book/part-3/index.html` | **Modify** — insert 2 iframes (cache gate, KV capacity) |
| `<book-repo>/content/extra/book/part-4/index.html` | **Modify** — insert 1 iframe (goodput) |
| `<book-repo>/theme/static/css/book.css` | **Modify** — add `.book-widget-frame` styles (1px moss border, aspect-ratio 4/3, no-JS table fallback) |

### Acceptance (Phase 5)

| # | Criterion |
|---|---|
| W1 | Each chapter renders its iframe in flow, sized via `aspect-ratio`, no layout shift on load |
| W2 | Iframe content inherits the same moss/oxblood theme via the Phase 2-updated `marimo-theme.css` |
| W3 | All six widgets call `compute_*` from `lcpr.py` — no numerics drift from standalone calculator |
| W4 | First widget encounter incurs ~5–8 MB Pyodide cold-load; subsequent widgets ≤ 200 KB (browser-cached) |
| W5 | No-JS fallback: each iframe is preceded by a `<noscript>` block with a static data table or "open standalone calculator" link |

### Open question for Phase 5

The prior spec mentioned a `Mad-libs panel` UI inside each widget (fill-in-the-blank sentence with editable slots). Worth confirming whether the Mad-libs UI shipped in Phase 2 of the original spec or whether it's still aspirational — that affects whether Phase 5 widgets reuse a component or build it fresh.

### Why Phase 5 is OUT OF SCOPE of this plan execution

Phase 5 is a separate workstream:
- It depends on Phase 4 sign-off (design fixes confirmed clean).
- It touches two repos in coordinated commits (calculator + book).
- It needs editorial review of where in the prose each widget should embed.
- The chapter HTML files currently bypass Pelican templates (`EXTRA_PATH_METADATA`); inserting iframes is markup work, not template work.

When ready, a new plan doc (`history/2026-05-XX-calculator-widget-embedding-plan.md`) should be drafted to execute Phase 5 specifically.

---

## Why these agents, why these phases

- **Phase 1 (discovery) used two scout agents in parallel** because the two unknowns (Marimo selectors + build pipeline) are independent — no shared state. Each returned in <1 minute. Reading Marimo's own bundled CSS gave better ground-truth than guessing or reading their docs.
- **Phase 2 (code fixes) is sequential and orchestrator-driven** because each change is small and reading the file once + editing is faster than spawning agents per task.
- **Phase 3 (build + deploy) is one-shot scripting** — no agents needed.
- **Phase 4 (verify) needs Sohail at devtools** — the iteration loop is "look → identify miss → relay selector → update CSS → rebuild". Browser-bound; no agent can do it remotely.

If selector-miss iteration is annoyingly slow, an option for round 2 is to dispatch a **critic/judge agent** to review the deployed HTML against the design spec and surface visible discrepancies. But that's only useful if Sohail wants to outsource the visual diffing.
