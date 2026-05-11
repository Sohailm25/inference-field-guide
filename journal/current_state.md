# Inference Field Guide — Current State

## Phase Status

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1: Research + Scaffold | COMPLETE | All verification done, repo scaffolded |
| Phase 2: Calculator (TDD) | 2a COMPLETE | Core engine + profiles done (46 tests). CLI + Streamlit remain. |
| Phase 3: Essay | NOT STARTED | Essay stub at site/src/pages/index.md |
| Phase 4: Site + Templates | NOT STARTED | Evaluation templates created |
| Phase 5: Polish + Publish | NOT STARTED | |

## Research Verification Results (2026-05-11)

### Pricing Corrections Applied
- **Fireworks DeepSeek V4 Pro**: Corrected from $2.10/$4.40 to $1.74/$3.48
- **Lambda H100 SXM**: Corrected from $3.78/hr to $2.99/hr (price dropped)
- **OpenAI GPT-5.5**: Confirmed $5/$30, added Priority ($12.50/$75) and long-context tiers
- **Together DeepSeek V3**: $1.25/$1.25 confirmed (may be V3.1 blended rate)
- **CoreWeave H100 HGX**: $6.16/hr confirmed

### Framework Names: All Clear
- LCPR: No collision in ML/inference
- Migration Gate: No collision
- Seven-Gate Scorecard: No collision (footnote re: IBM's 7-step stage gating recommended)
- Inference Sourcing Patterns: No collision

### Technical Claims: Confirmed
- Anthropic prompt caching 90% reduction: Confirmed
- OpenAI 1,024-token auto-caching at 50% discount: Confirmed
- NVIDIA Dynamo 1.0 GA March 16, 2026: Confirmed
- All 17 named adopters: Confirmed (list is actually incomplete — more exist)

## Repo Location
`/Users/sohailmo/inference-field-guide/` (standalone repo, separate from togetherai)

## Completed This Session
1. Phase 1: Full research verification (pricing, namespace, caching, Dynamo)
2. Phase 1: Repo scaffold (28 files, initial commit)
3. Phase 2a: LCPR core engine (TDD — 23 tests)
4. Phase 2a: Workload profiles (TDD — 23 additional tests, 46 total)

## Next Actions
1. Phase 2b: CLI interface (click-based, `lcpr` command)
2. Phase 2b: Crossover analysis + sensitivity analysis CLI commands
3. Phase 2b: Run worked examples from essay — verify numbers match
4. Phase 2c: Streamlit app (interactive web UI)
5. Phase 3: Begin essay writing (Part 0: The Cost Illusion)
