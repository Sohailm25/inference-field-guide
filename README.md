# Inference Field Guide

TCO frameworks, vendor evaluation, and architecture patterns for teams running inference in production.

Companion to [The Honest Field Guide to Production Inference](https://sohailmo.ai/inference-field-guide/) and the [LCPR-2026 framework](https://sohailmo.ai/lcpr-calculator-v2/) from *Production Inference Economics*.

## LCPR Calculator v2

The Loaded Cost Per Result (LCPR) calculator computes true cost per accepted work unit across deployment modes. It accounts for retries, quality gate failures, eval grader cost, human escalation, operational overhead, and the invoice reconciliation delta.

### Computations

- **LCPR comparison** — loaded cost per result across providers and deployment modes
- **Sensitivity analysis** — how LCPR changes when retry rate, quality gate, or cache hit rate shifts
- **Break-even analysis** — daily output token volume where dedicated capacity beats serverless
- **Goodput frontier** — accepted requests per second under latency and quality SLOs (Derivation 5)
- **Trace-to-margin reconciliation** — from raw traces to account margin via the four-source join (Derivation 6)
- **Cache break-even** — minimum reuse count within TTL for caching to save money (Derivation 3)
- **KV memory sizing** — maximum concurrent sequences at a given context length and hardware (Derivation 2)

### Interactive App

[inference-field-guide.streamlit.app](https://inference-field-guide.streamlit.app)

### CLI

```bash
pip install -e .
lcpr compare --profile saas_chat
lcpr crossover
lcpr sensitivity --vary retry_rate
```

### Worked Examples

Three seed files in `examples/` exercise the calculator views:

- **support-answer.trace-margin.v1** — 12-request trace, LCPR $0.172 vs naive $0.014 (12x gap)
- **coding-agent.lifecycle.v1** — 280 requests, 90% acceptance, cache hit differential
- **support-rag-answer-drafting.audit.v1** — benchmark audit where the naive winner loses on goodput

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

239 tests verifying formulas, worked examples, and edge cases.
