# Inference Field Guide — Current State

## Phase Status

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1: Research + Scaffold | COMPLETE | All verification done, repo scaffolded |
| Phase 2a: Calculator Core | COMPLETE | Core engine + profiles (46 tests) |
| Phase 2b: CLI + Verification | COMPLETE | CLI (5 commands), essay number verification, sweep output (80 tests) |
| Phase 2c: Streamlit App | NOT STARTED | Interactive web UI |
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

## Phase 2b: Essay Number Verification

Key verified numbers for the essay:
- **GPT-5.5 LCPR** (SaaS chat profile): ~$0.019/request ($9,065/month at 500K req)
- **Together DeepSeek V3 LCPR**: ~$0.003/request ($1,598/month) — ~5.7x cheaper
- **Break-even** (Together $1.25/M vs Lambda $2.99/hr): ~143.5M output tokens/day
- **Break-even** (Fireworks $0.90/M vs H100 $2.01/hr, theoretical): ~53.6M tokens/day
- **Neo-cloud savings**: Lambda ($2.99/hr) vs AWS ($4.975/hr) = ~40% savings
- **Multi-LoRA advantage**: Fireworks $0.20/M vs GPT-5.5 = ~8x LCPR advantage
- **Monthly GPU costs**: Lambda ~$2,153, AWS ~$3,582, CoreWeave ~$4,435

## CLI Commands

```
lcpr profiles              # List workload profiles
lcpr compare --profile X   # Compare all providers (table or JSON)
lcpr crossover             # Break-even serverless vs dedicated
lcpr sensitivity           # Vary one parameter, see LCPR impact
lcpr sweep                 # Volume-vs-cost sweep (JSON for Streamlit)
```

## Repo Location
`/Users/sohailmo/inference-field-guide/` (standalone repo, separate from togetherai)

## Test Coverage
- 80 tests total (46 core + 22 CLI + 12 essay verification)
- All passing, ruff clean

## Next Actions
1. Phase 2c: Streamlit app (interactive web UI, charts from sweep data)
2. Phase 3: Begin essay writing (Part 0: The Cost Illusion)
