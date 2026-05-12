# Inference Field Guide

TCO frameworks, vendor evaluation, and architecture patterns for teams adopting open-model inference.

Companion to [The Honest Field Guide to Production Inference](https://sohailmo.ai/inference-field-guide/).

## LCPR Calculator

The Loaded Cost Per Request (LCPR) calculator computes true cost per successful request across deployment modes, accounting for retries, quality gate failures, repair costs, and engineering overhead.

### Interactive App

[inference-field-guide.streamlit.app](https://inference-field-guide.streamlit.app)

### CLI

```bash
pip install -e .
lcpr compare --profile saas_chat
lcpr crossover
lcpr sensitivity --vary retry_rate
```

## Provider Pricing

All pricing data in `calculator/provider_pricing.yaml` uses May 2026 public rates. Update via PR with evidence tags.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

114 tests verifying every claim in the essay.
