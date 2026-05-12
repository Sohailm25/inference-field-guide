# Inference Field Guide — Current State

## Phase Status (as of 2026-05-12)

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 0: Trust Blockers | COMPLETE (except 0a — skipped per user) | Pricing updated, break-even math fixed, formula/gate logic corrected. |
| Phase 1: Calculator Hardening | COMPLETE | Constants extracted, input validation, YAML schema validation, prefill_efficiency docs, verifier rewritten |
| Phase 2: Calculator Features | COMPLETE | Quality sensitivity (2a), hidden controls (2e), pricing panel (2c), permalink/shareable state (2b), assumption confidence tracker (2d) |
| Phase 3: Calculator UI | DEFERRED | Loading spinners, accessibility — lower priority |
| Phase 4: Essay Structure | COMPLETE | Disclosure moved, spec decode softened, "stay on APIs" section, quality risk, absolute claims fixed, compliance caveats |
| Phase 5: Essay Analytics | COMPLETE | All items done: definition alignment, LCPR failure modes, assumption register, metering gap, math cards, fallback design, lead time, governance tiers, reconciliation, red-flag triggers, thresholds caveat, cost segmentation, attrition tax, systems delay, workload reference cards, diagnostic trees |
| Phase 6: Audit + Recompute | COMPLETE | All 21 verifier claims PASS. All stale numbers updated. Evidence tags re-classified to 8-level taxonomy. Full test suite 191 passed. |

## Deployment Status (2026-05-12)

### sohailmo.ai (Pelican / GitHub Pages)
- **URL**: sohailmo.ai/inference-field-guide/
- **Repo**: Sohailm25/Sohailm25.github.io (master branch)
- **Deploy**: GitHub Actions — completed successfully
- **Features**: Sticky sidebar TOC, mobile dropdown TOC, dark-themed tables, 4 pre-rendered decision tree SVGs

### Streamlit Calculator
- **Repo**: github.com/Sohailm25/inference-field-guide (main branch)
- **Main file**: calculator/app.py
- **Requirements**: requirements-streamlit.txt
- **Theme**: .streamlit/config.toml (dark theme matching sohailmo.ai)
- **Status**: Code pushed, Streamlit Cloud deployment has auth redirect issue (0a — skipped)
- **Target URL**: inference-field-guide.streamlit.app

### Streamlit App Tabs
1. **LCPR Comparison**: Sidebar profile selector (5 presets + custom), comparison table with overhead ratios, Plotly bar chart color-coded by deployment mode
2. **Sensitivity Analysis**: Parameter dropdown (retry_rate, quality_gate, I/O tokens, volume), range slider, multi-provider line chart
3. **Break-Even Analysis**: Serverless vs dedicated selector, break-even metrics, cost-vs-volume chart with crossover annotation
4. **Decision Trees**: 4 Mermaid diagrams in expanders with context text

### New Calculator Features (2026-05-12)
- **Quality sensitivity**: `quality_score` field on ProviderPricing adjusts effective quality gate
- **Exposed controls**: batch_eligible_fraction, prefill_efficiency, repair_cost in both custom and preset modes
- **Pricing snapshot panel**: Collapsible expander showing all provider prices with verification dates and source URLs
- **Permalink / shareable state**: base64-encoded WorkloadProfile in URL query params; share button in sidebar
- **Assumption confidence tracker**: 6-level status per trackable field (assumed → contract_confirmed); progress bar in sidebar

## Test Coverage
- **191 tests** total across calculator/tests/
- All passing (0.26s runtime)
- Test classes include: TestQualityAdjustedLCPR, TestYAMLSchemaValidation, TestWorkloadProfileValidation, TestFormatFunctions, TestVerifyClaims, TestPermalink, TestAssumptionConfidence

## Essay Verification
- **verify_essay.py**: Reads essay text, computes expected values from calculator, reports PASS/FAIL
- **21 claims verified**: All PASS as of 2026-05-12
- **Pricing sources**: All updated to May 2026 verified public prices

## Evidence Tag System (8-level taxonomy)
| Tag | Count | Description |
|-----|-------|-------------|
| PUBLIC_PRICING | 10 | Vendor pricing pages with verified date |
| PUBLIC_DOC | 9 | Vendor documentation or announcements |
| MEASURED_PRIVATE | 0 | Author's production measurements (in legend only) |
| CUSTOMER_STORY | 17 | Vendor-published case studies |
| INDEPENDENT_BENCHMARK | 7 | Third-party benchmarks with methodology |
| ANALYST_ESTIMATE | 6 | Third-party analysis or estimates |
| MODELED | 21 | LCPR calculator output, reproducible |
| UNVERIFIED | 0 | Claims needing primary source (in legend only) |

## Key Numbers (May 2026)
- OpenAI GPT-5.5: $5.00/$30.00/M input/output
- Together DeepSeek V3: $0.60/$1.70/M input/output
- Fireworks Llama 70B: $0.90/$0.90/M
- DeepInfra GPT-OSS-120B: $0.039/$0.19/M
- Lambda H100 SXM: $3.99/hr

## Remaining Work
- **0a**: Fix Streamlit deployment (auth redirects) — skipped per user decision
- **Phase 3**: Calculator UI improvements (loading spinners, accessibility) — deferred

## Repo Location
`/Users/sohailmo/inference-field-guide/` (standalone repo, separate from togetherai)
