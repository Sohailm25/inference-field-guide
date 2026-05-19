# Production Inference Economics Calculator

TCO frameworks, vendor evaluation, and architecture patterns for teams running inference in production.

Companion calculator for [Production Inference Economics: A Field Guide](https://sohailmo.ai/inference-field-guide/) and the [LCPR-2026 framework](https://sohailmo.ai/lcpr-calculator-v2/).

## LCPR Calculator

The Loaded Cost Per Result (LCPR) calculator computes true cost per accepted work unit across deployment modes. It accounts for retries, quality gate failures, eval grader cost, human escalation, operational overhead, and the invoice reconciliation delta.

### Current Computations

- **LCPR comparison**: loaded cost per result across providers and deployment modes.
- **Sensitivity analysis**: how LCPR changes when retry rate, quality gate, cache hit rate, token volume, or request volume shifts.
- **Break-even analysis**: daily output token volume where dedicated capacity beats serverless.
- **Goodput frontier**: accepted requests per second under latency and quality SLOs (Derivation 5).
- **Trace-to-margin reconciliation**: raw traces, invoice delta, eval cost, human cost, ops cost, revenue, and margin (Derivation 6).
- **Cache policy gate**: minimum reuse count within TTL for caching to save money (Derivation 3).
- **KV capacity envelope**: maximum concurrent sequences at a given context length and hardware memory budget (Derivation 2).
- **Template views**: RouteFit Matrix, Trace Event Schema, Source Snapshot Browser, and grouped operating views for spend, commitments, variance, account margin, usage signals, security, and latency.

### Interactive App

**Live (Marimo, recommended):** [sohailmo.ai/book/calculator/](https://sohailmo.ai/book/calculator/) — companion calculator for the book, deployed under the unified-publication URL.

**Local dev:**
```bash
.venv/bin/marimo run calculator/marimo_app.py    # edit mode
.venv/bin/python scripts/build_marimo_to_book.py  # WASM build + copy to book repo
```

**Legacy note:** The previous Streamlit app at `inference-econ.streamlit.app` has been retired. The calculator is Marimo-only now, served from `sohailmo.ai`.

**7 views** (collapsed from the legacy 13-tab Streamlit app):

1. **Landing** — Mad-libs sentence wired to a default workload; one-paragraph verdict
2. **Compare** — LCPR comparison across providers + deployments
3. **Sensitivity** — parameter sweep to find dominant cost lever
4. **Break-Even** — dedicated vs serverless crossover daily-volume
5. **Goodput** — accepted req/s under latency + quality SLOs (Derivation 5)
6. **Trace-to-Margin** — reconcile raw traces to invoice + revenue (Derivation 6)
7. **Advanced** — collapsible group: Cache Gate · KV Capacity · Migration · RouteFit · Trace Schema · Snapshots · Operations

The new visual design (moss + oxblood on parchment, Newsreader serif + JetBrains Mono) matches the book's broadsheet aesthetic — see `history/2026-05-18-phase2-calculator-marimo-migration.md` for the migration plan and `/Users/sohailmo/Documents/Sohailm25.github.io/history/2026-05-18-book-calculator-uiux-design.md` for the unified-publication design spec.

### CLI

```bash
pip install -e .
lcpr compare --profile saas_chat
lcpr crossover
lcpr sensitivity --vary retry_rate
```

### Worked Examples

Three seed files in `examples/` exercise the calculator views:

- **support-answer.trace-margin.v1**: monthly trace-to-margin seed with 100,000 attempts, 82,000 accepted units, LCPR `$0.234`, naive trace cost `$0.142`, and a `1.65x` loaded-to-naive ratio.
- **coding-agent.lifecycle.v1**: coding-agent lifecycle seed with 178,000 input tokens, 18,000 output tokens, 90% acceptance, and cache savings.
- **support-rag-answer-drafting.audit.v1**: benchmark audit where the naive throughput winner loses on goodput cost per accepted result.

The manuscript also uses a smaller daily teaching fixture for the opener: 1,000 attempts, 820 accepted units, `$140.65` loaded cost, LCPR `$0.172`, naive trace cost `$0.0142`, and a `12.1x` loaded-to-naive ratio. That fixture is intentionally separate from the monthly support seed above.

```bash
python -m examples.run_seeds
```

## Provider Pricing

All pricing data in `calculator/provider_pricing.yaml` uses May 2026 public rates. Update via PR with evidence tags.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

The test suite verifies formulas, worked examples, documentation alignment, and edge cases.
