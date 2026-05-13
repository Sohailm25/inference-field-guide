ABOUTME: Tracks current state for the Production Inference Economics calculator.
ABOUTME: Summarizes implementation status, verification, and remaining risks.

# Production Inference Economics Calculator — Current State

## Status As Of 2026-05-13

The companion calculator is aligned to the book-facing view inventory in
`calculator/view_registry.py`. The Streamlit app exposes 13 tabs directly and
maps the 14 appendix views either to a direct tab or to a grouped template
surface.

The current second pass tightened consistency between the app, README, code
comments, and appendix vocabulary:

- App and README now use the book title: **Production Inference Economics: A
  Field Guide**.
- The main app explainer now uses the full LCPR reconciliation formula:
  `C_trace + delta + C_eval + C_human + C_ops` over accepted work units.
- The LCPR Comparison tab is explicitly labeled as a profile-based screening
  estimator, not invoice-grade trace-to-margin reconciliation.
- Trace-to-Margin is labeled as the reconciled path when traces, invoice,
  eval, human, ops, and accepted work counts exist for the same period.
- Break-Even Analysis is described as the Part 4 dedicated-capacity screening
  gate, not a Part 1 formula.
- Source Snapshot Browser no longer pretends PyYAML can infer `[PUBLIC]`
  evidence tags from comments. Rows now show `comment_only` until source
  metadata is promoted into structured YAML fields.

## Streamlit App Tabs

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

## View Inventory Notes

- Book-facing **Dedicated Break-Even** maps to the app's **Break-Even
  Analysis** tab.
- Its internal schema name is **Dedicated Utilization Gate v1**, matching the
  appendix and Part 4 derivation language.
- Book-facing operating views such as Spend Movement, Commitment Utilization,
  Variance Analysis, Account Margin Model, Usage Signals, Security and
  Compliance Filter, and Latency Decomposition live inside the grouped
  **Operating Views** tab.

## Verification

- `ruff check calculator/app.py calculator/lcpr.py calculator/cli.py calculator/__init__.py calculator/tests/test_lcpr.py calculator/tests/test_view_registry.py`
  passed.
- `pytest -p no:cacheprovider calculator/tests/test_view_registry.py calculator/tests/test_lcpr.py`
  passed with 79 tests.
- `pytest -p no:cacheprovider calculator/tests examples/test_seeds.py` passed
  with 269 tests.
- Streamlit app booted successfully on `http://localhost:8502` and returned
  HTTP 200.

## Remaining Risks

- Provider prices are still snapshots, not live pricing. Do not imply current
  market accuracy without a new source refresh.
- Pricing evidence tags are still mostly human-readable YAML comments. The app
  now avoids false precision, but structured `evidence`, `source_url`, and
  `verified_at` fields should be added if the browser is meant to audit sources
  programmatically.
- Streamlit Cloud deployment previously had an auth redirect issue. This pass
  verified local boot only.
