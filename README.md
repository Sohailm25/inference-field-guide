# Inference Field Guide

TCO frameworks, vendor evaluation, and architecture patterns for teams running inference in production.

Companion to [The Honest Field Guide to Production Inference](https://sohailmo.ai/inference-field-guide/) and the [LCPR-2026 framework](https://sohailmo.ai/lcpr-calculator-v2/) from *Production Inference Economics*.

## LCPR Calculator v2

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

[inference-field-guide.streamlit.app](https://inference-field-guide.streamlit.app)

Visible app tabs:

1. LCPR Comparison
2. Sensitivity Analysis
3. Break-Even Analysis
4. Migration Readiness
5. Decision Trees
6. Goodput Frontier
7. Trace-to-Margin
8. Cache Policy Gate
9. KV Capacity Envelope
10. RouteFit Matrix
11. Trace Event Schema
12. Source Snapshot Browser
13. Operating Views

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
