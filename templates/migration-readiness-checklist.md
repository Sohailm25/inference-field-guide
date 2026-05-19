# Migration Readiness Checklist

Framework from [The Honest Field Guide to Production Inference](https://sohailmo.ai/inference-field-guide/).

Fill in each gate. All three gates must pass before proceeding to execution phases.

---

## Gate 1: Volume

> Monthly closed-API spend below $10K makes migration economics marginal.
> Between $10K–$50K, execution risk matters. Above $50K, savings absorb friction.

- [ ] Current monthly inference spend: $________
- [ ] Current provider and model: ________________
- [ ] LCPR on current provider: $________ per request
- [ ] LCPR on target provider: $________ per request
- [ ] Monthly savings: $________
- [ ] Estimated migration cost (engineer-weeks × rate): $________
- [ ] Payback period (migration cost / monthly savings): ________ months
- [ ] **Gate 1 verdict**: PASS / FAIL

Run exact numbers at: https://sohailmo.ai/book/calculator/

---

## Gate 2: Specialization

> Pass this gate if any of the following are true, regardless of volume.

- [ ] Fine-tuned model matches frontier quality for your task
- [ ] Hard P99 latency SLO under 500ms on chained calls
- [ ] Need model-level modifications (constrained decoding, custom sampling, activation steering)
- [ ] Multi-LoRA serving required
- [ ] **Gate 2 verdict**: PASS / FAIL / N/A

---

## Gate 3: Ownership

> Pass this gate if regulatory or risk requirements force the move, regardless of volume.

- [ ] EU PII requiring data residency (Schrems II)
- [ ] Zero data retention required by default
- [ ] Vendor concentration risk exceeds tolerance (single-provider outage > 1% monthly revenue)
- [ ] Contractual or regulatory requirement for open-weights
- [ ] **Gate 3 verdict**: PASS / FAIL / N/A

---

## Migration Decision

- Gates passed: ________
- **Proceed with migration**: YES / NO

If NO, revisit when volume, specialization, or ownership requirements change.

---

## Execution Phases

### Phase 1: Foundation (Weeks 1–2)

- [ ] Select target provider(s) using [Vendor Evaluation Scorecard](./vendor-evaluation-scorecard.yaml)
- [ ] Deploy AI gateway (LiteLLM dev / Helicone or Portkey prod)
- [ ] Set up observability baseline (current latency, error rate, cost)
- [ ] Configure fallback provider for primary model
- [ ] Establish quality evaluation harness (automated, not manual)
- [ ] Document current prompt templates and expected outputs

### Phase 2: Validation (Weeks 3–6)

- [ ] Run target model against evaluation harness — record quality gate pass rate
- [ ] Adapt prompts for target model if needed
- [ ] Benchmark latency at production concurrency for 7+ days
- [ ] Calculate actual LCPR on target provider with real workload data
- [ ] Compare LCPR against pre-migration baseline
- [ ] Shadow-traffic test: route 5–10% of production to target, compare outputs
- [ ] Validate structured output compatibility
- [ ] Verify data handling matches requirements (retention, residency)

### Phase 3: Cutover (Weeks 7–10)

- [ ] Gradual traffic shift: 10% → 25% → 50% → 100%
- [ ] Monitor quality gate pass rate at each increment
- [ ] Monitor latency P50/P95/P99 at each increment
- [ ] Track LCPR daily during ramp
- [ ] Define rollback triggers (quality drop > X%, latency spike > Yms)
- [ ] Execute rollback drill before 50% cutover
- [ ] Complete cutover or hold at partial split based on data

### Phase 4: Operational Readiness

- [ ] Update runbooks for new provider
- [ ] Configure alerting on new provider metrics
- [ ] Document monthly maintenance tasks (API changes, pricing updates)
- [ ] Set up revert signal monitoring:
  - Multi-source overhead < 20% of savings (Stage 1)
  - GPU utilization > 40% sustained (Stage 2)
- [ ] Schedule 30-day post-migration review
- [ ] Archive pre-migration configuration for rollback

---

*Generated from the Migration Gate Framework. See Part 1 of the essay for full methodology.*
