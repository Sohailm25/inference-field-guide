# Inference Field Guide — Current State

## Phase Status

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1: Research + Scaffold | COMPLETE | All verification done, repo scaffolded |
| Phase 2a: Calculator Core | COMPLETE | Core engine + profiles (46 tests) |
| Phase 2b: CLI + Verification | COMPLETE | CLI (5 commands), essay number verification, sweep output (80 tests) |
| Phase 2c: Streamlit App | NOT STARTED | Interactive web UI |
| Phase 3: Essay | IN PROGRESS | Parts 0-2 written (~4,600 words), Parts 3-5 remaining |
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

## Second-Pass Audit (2026-05-11)

### Claims Corrected
- **Break-even threshold**: Was "~20M output tokens/day" — corrected to ~53.6M at
  full util, ~134-179M at 30-40% real utilization. Original number from earlier
  draft with different pricing assumptions.
- **Cost ratio**: Was "5-30x cheaper" — narrowed to "5-10x at LCPR level"
  (engineering overhead compresses raw token ratio). Raw token ratio is 10-150x.
- **Utilization multiplier**: Was "~3x" — documented as 2.5x at 40% util,
  3.3x at 30% util. "~3x" is midpoint of the range.

### Evidence Tags Fixed
- GPT-5.5 Mini ($0.30/$1.50): changed from [PUBLIC] to [MODELED]
- Baseten Model API ($0.88): changed from [PUBLIC] to [MODELED]
- Throughput notes: removed inaccurate "Clarifai validation" citation

### Research File Updated
- additional_research.md: Fireworks V4 corrected to $1.74/$3.48, Lambda to $2.99
- additional_research.md: "5-30x" claim narrowed to "5-10x at LCPR level"

### False Positives Dismissed
- "Dedicated GPU ignores input tokens" — correct behavior; GPU throughput is
  bottlenecked by decode phase (output), not prefill (input)
- "Break-even ignores input tokens" — conservative simplification, biased
  toward staying serverless (the safer recommendation)

## Repo Location
`/Users/sohailmo/inference-field-guide/` (standalone repo, separate from togetherai)

## Test Coverage
- 80 tests total (46 core + 22 CLI + 12 essay verification)
- All passing, ruff clean

## Phase 3: Essay Progress (2026-05-11)

### Parts Written
- **Part 0: The Cost Illusion** (~1,465 words) — LCPR formula, worked example table, sensitivity, observability tax
- **Part 1: When to Leave the API** (~1,700 words) — Migration Gate Framework (Volume/Specialization/Ownership), worked example (B2B SaaS at $18K/month), break-even math, when NOT to migrate
- **Part 2: The Multi-Source Architecture** (~1,430 words) — Four patterns (Workload-Segmented, Capability-Arbitrage, Primary-Fallback, Geo-Segmented), named examples, complexity tax, routing layer levels

### Numbers Verified Against Calculator
- Enterprise profile (800K req, 1000/500 tokens, 5% retry, 92% QG): GPT-5.5 LCPR=$0.0246 ($18,128/mo)
- Together DeepSeek V3: LCPR=$0.0039 ($2,903/mo) — 6.2x cheaper
- Migration savings: $15,225/month, payback 3.2 months at $48K migration cost
- Break-even Together vs Lambda (40% util): 143.5M tokens/day
- Break-even Together vs Lambda (100% util): 57.4M tokens/day
- Quality gate 95%→85% = 12.4% LCPR increase
- Multi-LoRA 26.6x LCPR advantage over GPT-5.5 at 10M req/month
- GPT-5.5 Mini cheaper than Together for short-output voice workloads

## Next Actions
1. Phase 3: Write Parts 3-5 (Build vs Buy, Seven-Gate Scorecard, Staged Playbook)
2. Phase 2c: Streamlit app (can be done in parallel or after essay)
