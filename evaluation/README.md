# Evaluation Framework

Templates for evaluating inference providers and migration readiness.

## Files

- `seven_gate_scorecard.yaml` — Score vendors across 7 critical dimensions
- `vendor_comparison.yaml` — Pre-filled comparison data for major providers
- `migration_gate.yaml` — Checklist for "should we leave the API?" decision

## Usage

1. Copy the scorecard YAML
2. Fill in scores from your own bake-off testing
3. The scoring system is 1-5 per gate, weighted by your workload priorities
4. Compare total weighted scores across providers

The scorecard is intentionally opinionated about *what* to measure.
Your weights reflect *how much* each dimension matters for your workload.
