---
title: "The Honest Field Guide to Production Inference"
description: "TCO frameworks, vendor evaluation, and architecture patterns for teams adopting open-model inference"
author: "Sohail Mohammad"
date: "2026-05"
---

# The Honest Field Guide to Production Inference

*Sohail Mohammad is an infrastructure engineer at Together AI, prior fractional CTO and contributor to Unsloth/MLX-LM/Blackwell kernel work. Opinions are his own.*

---

## Part 0: The Cost Illusion

Speculative decoding doesn't work at batch 12.

Not "doesn't work well." 0.92x. *Slower.* I implemented it at Wendy's. We were running open-source models behind 100K+ daily drive-thru interactions, 400-600ms inference budget, and under production concurrency, we were paying 8% more compute with it enabled than without. The papers promise 2-3x decode speedup. The papers are measuring single-request latency on clean benchmarks. At batch 12-16, different sequences accept different numbers of draft tokens. You get ragged tensors. The alignment overhead eats the theoretical gain. Add the KV cache management cost of a draft model that's never seen "Baconator" in its training data, and you're underwater.

I spent two weeks on this before I killed it. Tried three draft model configurations. Fine-tuned a 1B speculator on 10K drive-thru transcripts — acceptance rate went from 48% to 58%, still below breakeven. The math is unforgiving: at α=0.55, γ=5, you get 1.94 expected tokens per step for 1.15x the cost. Net negative.

The reason this matters isn't speculative decoding. It's the gap it represents.

There's a concept from Elon Musk's early SpaceX days. He couldn't afford rockets, so he calculated the raw material cost — carbon fiber, metal, fuel — and compared it to what the aerospace industry charged for a finished product. The ratio was 50x. He called it the "idiot index": the cost of the finished product divided by the cost of its component materials. If the ratio is high, somewhere in the chain, a massive amount of unnecessary complexity has been layered on top.

AI deployment has its own idiot index. Not in hardware — GPU pricing is competitive and transparent. The idiot index in inference is the gap between the *advertised cost* of running a model and the *true cost* of getting a correct answer out of it in production. Pricing pages quote token rates. Production systems pay for retries, schema failures, quality gate rejections, engineering time, and an observability bill that grows 30-50% year over year.

This essay is about closing that gap. Not with benchmarks — those lie in predictable ways. With math.

### The April 2026 price signal

On April 23, 2026, OpenAI doubled GPT-5.5's standard rates to $5.00/$30.00 per million input/output tokens [PUBLIC]. Anthropic held Claude Opus 4.7 and Sonnet 4.6 at $5/$25 and $3/$15 respectively. Gemini 2.5 Pro at $1.25/$10 (≤200K context) remains the cheapest frontier option.

The signal is clear: expect price *increases* at the frontier, not decreases. Meanwhile, serverless open-weights inference is 5-10x cheaper at the total-cost level for non-reasoning workloads and within 5-15% quality on most benchmarks. The gap is widening, not closing.

But "5-10x cheaper" is itself a simplification. It depends on what you're measuring.

### The number that actually matters

Token pricing is a component, not a cost. The number you should care about is what I call **Loaded Cost Per Request** (LCPR):

```
LCPR = (token_cost + retry_cost + repair_cost + engineering_cost)
       / successful_requests
```

Where:
- **Token cost** = input tokens × input rate + output tokens × output rate, multiplied by total attempts (original requests + retries)
- **Retry cost** = implicit in total attempts — every retry is a full re-request that burns tokens
- **Repair cost** = requests that fail quality or schema gates × cost to re-prompt
- **Engineering cost** = monthly hours maintaining the inference stack × hourly rate
- **Successful requests** = total requests × quality gate pass rate

This formula isn't novel. Any ops team that's been burned by a 15% retry rate already thinks in these terms. But almost nobody *calculates it*, which means almost nobody has accurate cost comparisons across providers.

### Worked example: the numbers change

Consider a mid-scale SaaS workload: 500,000 requests per month, 800 input tokens and 400 output tokens per request, 3% retry rate, 95% quality gate pass rate, and 8 engineering hours per month at $100/hour to keep things running.

Here's what the LCPR looks like across deployment modes, using May 2026 public pricing:

| Provider | Raw $/request | LCPR | Monthly cost | Overhead ratio |
|----------|------------:|-----:|-----------:|------:|
| OpenAI GPT-5.5 | $0.0160 | $0.0191 | $9,065 | 1.19x |
| Lambda H100 (dedicated, 40% util) | $0.0043 | $0.0063 | $2,978 | 1.46x |
| Together AI DeepSeek V3 (serverless) | $0.0015 | $0.0034 | $1,598 | 2.24x |
| Fireworks AI Llama 70B (serverless) | $0.0011 | $0.0029 | $1,381 | 2.69x |
| DeepInfra (serverless) | $0.0001 | $0.0018 | $874 | 19.18x |

Three things to notice.

**First, the ranking doesn't change — but the magnitude does.** GPT-5.5's raw token cost is $0.016 per request. Its LCPR is $0.019 — only 19% higher. For a managed API with near-zero engineering burden, that's a small overhead. But DeepInfra at $0.0001 per request has an LCPR of $0.0018 — a 19x overhead ratio. The $800/month engineering cost dominates when tokens are nearly free. Cheap providers need volume to amortize fixed costs.

**Second, the cost ratios compress.** GPT-5.5 is 10.7x more expensive than Together on raw token cost. At LCPR level, it's 5.7x. Engineering overhead, retries, and repair costs are roughly fixed regardless of provider — they compress the ratio. Any comparison that doesn't include these costs is overstating the savings from switching.

**Third, dedicated GPU is not the cheapest option at this volume.** A Lambda H100 at $2.99/hr with 40% realistic utilization produces an LCPR of $0.0063 — more expensive than both serverless open-weights options. The GPU costs $2,153/month whether you use it or not. At 500K requests generating 200M output tokens per month, you're paying for capacity you don't fill. Dedicated wins at scale, but the crossover point is higher than most teams expect.

### The numbers change when reliability changes

The worked example above assumes a 3% retry rate and 95% quality gate. What happens when those shift?

At 20% retry rate (not uncommon during model migrations or prompt changes), GPT-5.5's LCPR rises to $0.0219. Together's rises to $0.0036. The ratio *increases* from 5.7x to 6.0x — retries hurt expensive providers more because each retry costs more tokens.

At 70% quality gate pass rate (a model that frequently fails structured output validation), GPT-5.5's LCPR jumps to $0.0263. Together's jumps to $0.0049. The ratio *compresses* to 5.3x — because repair and engineering costs are provider-independent and start to dominate.

This is the cost illusion. The pricing page shows you the token rate. The LCPR shows you the bill. They're different numbers, and the gap between them depends on factors — retry rate, quality gate, engineering time, observability cost — that no vendor has any incentive to help you measure.

### The observability tax

One cost deserves special mention because it's the single largest hidden expense most teams discover too late: observability.

byteiota's 2026 analysis found a median Datadog bill of $123K/year for mid-market companies, growing 30-50% year over year [REPORTED]. Teams adding LLM monitoring report 40-200% bill increases because GenAI semantic-convention spans get billed as custom metrics. AI workloads generate 10-50x more telemetry than traditional services.

If you're modeling a migration from closed APIs to self-managed inference, budget 2-4x your Year-1 observability estimate. The Datadog bill is not a rounding error — it's a line item that rivals your GPU spend at small to medium scale.

### What this essay covers

The rest of this guide provides frameworks for the four decisions every team migrating to open-model inference has to make:

1. **When to leave the API** — the Migration Gate Framework (Part 1)
2. **How to architect multi-provider inference** — the Inference Sourcing Patterns (Part 2)
3. **What to build versus what to buy** — the Inference Stack Map (Part 3)
4. **How to evaluate vendors honestly** — the Seven-Gate Scorecard (Part 4)
5. **What to do at each scale** — the Staged Playbook (Part 5)

Each framework includes worked calculations, named real-world examples with direct quotes, and a companion [LCPR calculator](https://github.com/sohailm/inference-field-guide) you can run against your own workload. Every vendor claim is tagged with its evidence basis: [PUBLIC] for pricing pages, [MEASURED] for my own production experience, [REPORTED] for third-party sources, and [MODELED] for calculations with methodology shown.

I work at Together AI. Where Together wins, I'll say so and cite why. Where Together loses to a competitor, I'll say that too. A field guide that only recommends the author's employer isn't a field guide — it's a brochure.

---

*Part 1: When to Leave the API →*
