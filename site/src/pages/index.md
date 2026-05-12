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

Not "doesn't work well." 0.92x. *Slower.* I implemented it at Wendy's. We were running open-source models behind 100K+ daily drive-thru interactions, 400-600ms inference budget, and under production concurrency, we were paying 8% more compute with it enabled than without. The papers promise 2-3x decode speedup. The papers are measuring single-request latency on clean benchmarks. At batch 12-16, different sequences accept different numbers of draft tokens, creating batch-level inefficiency: some sequences are still verifying while others have moved on to generation. The memory bandwidth cost of maintaining KV caches for both draft and target models, plus the verification overhead, eats the theoretical single-request speedup. Add a draft model that's never seen "Baconator" in its training data, and you're underwater.

(This problem is solvable. Together's ATLAS uses a three-component architecture — a heavyweight static speculator for baseline throughput, a lightweight adaptive speculator that learns from live traffic patterns, and a confidence-aware controller that routes each request to the right strategy. By selecting draft strategies per-request rather than per-batch, ATLAS achieves 2.65x speedup even at production concurrency where static spec decode is net negative [REPORTED]. The per-request routing is why it works at batch 12: instead of forcing all sequences in a batch to use the same draft model, the controller adapts to each sequence's acceptance rate characteristics.)

I spent two weeks on this before I killed it. Tried three draft model configurations. Fine-tuned a 1B speculator on 10K drive-thru transcripts — acceptance rate went from 48% to 58%, still below breakeven. The math is unforgiving: at α=0.55, γ=5, you get 1.94 expected tokens per step for 1.15x the cost. Net negative.

The reason this matters isn't speculative decoding. It's the gap it represents.

There's a concept from Elon Musk's early SpaceX days. He couldn't afford rockets, so he calculated the raw material cost — carbon fiber, metal, fuel — and compared it to what the aerospace industry charged for a finished product. The ratio was 50x. He called it the "idiot index": the cost of the finished product divided by the cost of its component materials. If the ratio is high, somewhere in the chain, a massive amount of unnecessary complexity has been layered on top.

AI deployment has its own idiot index. Not in hardware — GPU pricing is competitive and transparent. The idiot index in inference is the gap between the *advertised cost* of running a model and the *true cost* of getting a correct answer out of it in production. Pricing pages quote token rates. Production systems pay for retries, schema failures, quality gate rejections, engineering time, and an observability bill that grows 30-50% year over year.

This essay is about closing that gap. Not with benchmarks — those lie in predictable ways. With math.

### The April 2026 price signal

On April 23, 2026, OpenAI launched GPT-5.5 at $5.00/$30.00 per million input/output tokens — double the rates of its predecessor GPT-5.4 [PUBLIC]. Anthropic held Claude Opus 4.7 and Sonnet 4.6 at $5/$25 and $3/$15 respectively. Gemini 2.5 Pro at $1.25/$10 (≤200K context) remains the cheapest frontier option.

The signal is clear: expect price *increases* at the frontier, not decreases. Meanwhile, serverless open-weights inference is 5-10x cheaper at the total-cost level for non-reasoning workloads and within 5-15% quality on most benchmarks. The price gap between frontier closed APIs and serverless open-weights is widening — a signal that the open-weights cost advantage is structural, not temporary.

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

This formula is deliberately simplified. It omits cold start costs (relevant for scale-to-zero serverless), KV cache memory overhead (implicit in token cost for serverless; explicit for dedicated), and observability costs (covered separately in "The Observability Tax" below). A full-stack TCO model would include those — but even this simplified version produces materially different rankings than raw token pricing, which is the point.

Almost nobody calculates LCPR, which means almost nobody has accurate cost comparisons across providers.

### Worked example: the numbers change

Consider a mid-scale SaaS workload: 500,000 requests per month, 800 input tokens and 400 output tokens per request, 3% retry rate, 95% quality gate pass rate, and 8 engineering hours per month at $100/hour to keep things running.

Here's what the LCPR looks like across deployment modes, using May 2026 public pricing:

| Provider | Raw $/request | LCPR | Monthly cost | Overhead ratio |
|----------|------------:|-----:|-----------:|------:|
| OpenAI GPT-5.5 | $0.0160 | $0.0191 | $9,090 | 1.20x |
| Lambda H100 (dedicated, 40% util) | $0.0060 | $0.0063 | $3,003 | 1.05x |
| Together AI DeepSeek V3 (serverless) | $0.0015 | $0.0034 | $1,622 | 2.28x |
| Fireworks AI Llama 70B (serverless) | $0.0011 | $0.0030 | $1,406 | 2.74x |
| DeepInfra GPT-OSS-120B (serverless) | $0.0002 | $0.0020 | $963 | 9.22x |

Three things to notice.

**First, the ranking doesn't change — but the magnitude does.** GPT-5.5's raw token cost is $0.016 per request. Its LCPR is $0.019 — only 20% higher. For a managed API with near-zero engineering burden, that's a small overhead. But DeepInfra at $0.0002 per request (note: DeepInfra prices asymmetrically at $0.05/$0.45 per million input/output tokens [PUBLIC]) has an LCPR of $0.0020 — a 9.2x overhead ratio. This doesn't mean DeepInfra is inefficient — it's still the cheapest total cost in the table. The high ratio means tokens are cheap enough that fixed costs (engineering, retries, repair) dominate the per-request LCPR. Cheap providers need volume to amortize those fixed costs.

**Second, the cost ratios compress.** GPT-5.5 is 10.7x more expensive than Together on raw token cost. At LCPR level, it's 5.6x. Engineering overhead, retries, and repair costs are roughly fixed regardless of provider — they compress the ratio. Any comparison that doesn't include these costs is overstating the savings from switching.

**Third, dedicated GPU is not the cheapest option at this volume.** A Lambda H100 at $2.99/hr with 40% realistic utilization produces an LCPR of $0.0063 — more expensive than both serverless open-weights options. The GPU costs $2,153/month whether you use it or not. At 500K requests generating 200M output tokens per month, you're paying for capacity you don't fill. Dedicated wins at scale, but the crossover is higher than most teams expect.

### The numbers change when reliability changes

The worked example above assumes a 3% retry rate and 95% quality gate. What happens when those shift?

At 20% retry rate (not uncommon during model migrations or prompt changes), GPT-5.5's LCPR rises to $0.0220. Together's rises to $0.0037. The ratio *increases* from 5.6x to 6.0x — retries hurt expensive providers more because each retry costs more tokens.

At 70% quality gate pass rate (a model that frequently fails structured output validation), GPT-5.5's LCPR jumps to $0.0267. Together's jumps to $0.0053. The ratio *compresses* to 5.0x — because repair and engineering costs are provider-independent and start to dominate.

**The I/O ratio matters more than most teams realize.** The GPT-5.5 vs Together cost advantage depends heavily on the output-to-input ratio because GPT-5.5 prices output at 6x its input rate ($30 vs $5 per million), while Together charges $1.25 symmetrically. At 800 input tokens with varying output:

| Output tokens | Raw ratio | LCPR ratio |
|-------------:|----------:|-----------:|
| 100 (classification) | 6.2x | 3.1x |
| 400 (essay default) | 10.7x | 5.6x |
| 1,000 (long-form) | 15.1x | 9.1x |
| 1,500 (code gen) | 17.0x | 11.2x |

Output-heavy workloads (code generation, long-form content) see the largest savings from migration. Input-heavy workloads (classification, embedding prep) see the smallest — and may not justify migration at all if the volume is low [MODELED].

This is the cost illusion. The pricing page shows you the token rate. The LCPR shows you the bill. They're different numbers, and the gap between them depends on factors — retry rate, quality gate, engineering time, I/O ratio, observability cost — that no vendor has any incentive to help you measure.

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

## Part 1: When to Leave the API

The question is not *whether* open-weights inference is cheaper. Part 0 showed the LCPR math — 5-6x at the loaded level, 10-100x on raw tokens. The question is whether the savings justify the migration cost, and for which workloads.

Most teams get this wrong in one of two directions. They either stay on closed APIs past the point where they're hemorrhaging money, or they migrate too early, spend 10 engineer-weeks rebuilding prompt pipelines, and discover the savings don't cover the engineering bill for two years.

This section provides three gates. Pass all three and migration is nearly always worth it. Fail any one and you should stay put — or at least stay put for that workload.

### Gate 1: The Volume Gate

Migration has a fixed cost. The range varies by complexity: a straightforward API swap (same model family, OpenAI-compatible endpoints) can be done in 2-4 engineer-weeks. A standard migration requiring prompt adaptation and quality gate validation takes **6-10 engineer-weeks**, plus another 4-8 weeks of optimization to reach cost parity. Complex migrations involving fine-tuning, custom structured output validation, or domain-specific evaluation harnesses can extend to 12-20 weeks [ESTIMATED from limited public data: Braincuber's anonymized fintech client (6 weeks, $38K for scaling from 2M to 15M daily tokens) and Introl's vLLM hardening estimate ("one to two weeks" for production hardening alone, which understates the upstream evaluation work)].

At a blended rate of $150/hour for a senior ML engineer, 8 engineer-weeks costs $48,000. Does your monthly savings exceed the amortized migration cost over a reasonable payback period?

Here's the worked example. A B2B SaaS company running 800,000 requests per month on GPT-5.5, with 1,000 input tokens and 500 output tokens per request, a 5% retry rate, 92% quality gate pass rate, and 12 engineering hours per month to maintain the stack.

| Provider | LCPR | Monthly cost |
|----------|-----:|-----------:|
| OpenAI GPT-5.5 | $0.0246 | $18,128 |
| Lambda H100 (dedicated, 40% util) | $0.0047 | $3,481 |
| Together AI DeepSeek V3 (serverless) | $0.0039 | $2,903 |
| Fireworks AI Llama 70B (serverless) | $0.0033 | $2,462 |

Switching from GPT-5.5 to Together DeepSeek V3 saves $15,225 per month — $182,700 per year [MODELED]. Against a $48,000 migration cost, the payback period is 3.2 months. That's a clear pass.

But notice what happens at lower volume. In the Part 0 worked example (500K requests/month, simpler workload profile), GPT-5.5's monthly cost was $9,090. Against Together at $1,622, the savings are $7,468/month. Still a 6.4-month payback — acceptable, but you're now sensitive to migration overruns. If the migration takes 12 weeks instead of 8, or if the quality gate drops from 95% to 88% during the transition and you spend two months tuning prompts, the payback stretches past a year.

**The Volume Gate threshold**: if your monthly closed-API spend is below $10,000, the migration economics are marginal. Between $10,000 and $50,000, the economics work but execution risk matters — you need a team that's done this before. Above $50,000, the savings are large enough to absorb migration friction. These boundaries are rough; run the [LCPR calculator](https://github.com/sohailm/inference-field-guide) against your actual workload to get precise numbers.

### Gate 2: The Specialization Gate

Volume isn't the only reason to migrate. Sometimes the workload requires something closed APIs can't provide.

**Fine-tuned models.** If your quality evaluation shows that a fine-tuned 8B or 70B model matches frontier quality for your specific domain, the cost advantage is enormous. Cresta runs thousands of LoRA adapters for per-domain contact center agents on Fireworks Multi-LoRA at $0.20/M tokens — a 27x LCPR advantage over GPT-5.5 at 3M requests/month [MODELED]. Even accounting for the engineering cost of training and maintaining the fine-tune pipeline, the payback is measured in weeks, not months.

**Latency SLOs.** Shared APIs under load produce P99 latency spikes from ~300ms to 2-4 seconds on 70B-class models. For agent pipelines with 5+ chained calls, that compounds: a 2-second P99 across 5 calls is a 10-second worst case. Dedicated inference lets you control batch size and KV cache budget.

Decagon is the clearest illustration. They build voice AI agents for enterprise customer support — tens of millions of interactions, 80%+ deflection rate — running a multi-model voice stack (STT → LLM → TTS). Voice AI requires sub-100ms model latency to feel conversational, which shared APIs cannot guarantee under load. After migrating to Together AI on NVIDIA HGX B200 infrastructure with custom-trained speculators per application (not a static draft model — each application gets a speculator trained on its conversation patterns), Decagon achieved P95 model latency under 400ms, a 6x cost reduction per turn versus GPT-5 Mini, and 11x faster inference [REPORTED]. The custom-per-application speculator approach is key: generic speculators have low acceptance rates on domain-specific vocabulary, the same problem I hit at Wendy's with "Baconator."

**Custom architectures.** Some workloads require model modifications that closed APIs don't support: constrained decoding, custom sampling strategies, domain-specific tokenizers, or inference-time interventions like activation steering. If you need to modify the model's forward pass, you need dedicated inference.

**The Specialization Gate threshold**: if any of the following are true, migration passes this gate regardless of volume: (a) a fine-tuned model matches frontier quality for your task, (b) you have a hard P99 latency SLO under 500ms on chained calls, or (c) you need model-level modifications.

### Gate 3: The Ownership Gate

The third gate is non-economic: compliance, data residency, and vendor dependency.

**Data residency.** If your workload processes EU PII, Schrems II makes US-hosted inference legally fraught. The viable EU-resident options are Nebius (Finland, France), Scaleway, Mistral La Plateforme, and OVH. None of the major closed APIs (OpenAI, Anthropic) offer guaranteed EU-only inference. Anthropic's `inference_geo=US` parameter confirms that their default routing *isn't* geo-constrained — it's the exception, not the rule.

**Zero data retention.** For healthcare and financial workloads, the default storage behavior matters more than the compliance certification. Baseten stores nothing by default. Fireworks retains for 30 days on the Response API unless `store=false`. Together stores by default unless you disable it. OpenAI's fine-tuning retains training data. If your legal team requires contractual zero-retention by default, this narrows your vendor set.

**Vendor concentration risk.** Anthropic outages in 2024-2025 produced real revenue loss for single-sourced teams. If a single provider outage costs more than 1% of monthly revenue, you are underinvested in multi-sourcing — and multi-sourcing across closed APIs still leaves you dependent on two or three vendors' pricing decisions. Open-weights on serverless gives you model portability: if Together has an outage, the same DeepSeek V3 weights are available on Fireworks, DeepInfra, and others.

**The Ownership Gate threshold**: if regulatory requirements force specific data handling, or if vendor concentration risk exceeds your tolerance, migration passes this gate regardless of volume.

### When NOT to migrate

Not every workload should move. Three patterns where closed APIs remain the right answer:

**Small-token, high-volume workloads where Mini-class models win.** GPT-5.5 Mini at $0.30/$1.50 per million tokens is cheaper than Together DeepSeek V3 at $1.25/$1.25 for workloads with short outputs. A voice classification task at 300 input tokens and 150 output tokens at 3M requests/month costs $0.00073 LCPR on Mini versus $0.00100 on Together [MODELED]. Open-weights isn't always cheaper — the math depends on the input/output ratio and which model tier you're comparing against.

**Reasoning-heavy workloads where frontier quality matters.** If your task requires chain-of-thought reasoning, mathematical proof, or complex code generation where GPT-5.5 or Claude Opus 4.7 measurably outperform open-weights alternatives, the quality delta means more failed requests, more retries, and a higher LCPR on the open-weights side. Quality gate pass rate is the most powerful variable in the LCPR formula — a 10-point drop from 95% to 85% increases LCPR by 13% on expensive providers and up to 19% on cheap ones where fixed costs dominate [MODELED].

**Prototyping and early product.** At less than $10,000 per month, the engineering overhead of managing even a serverless open-weights deployment — prompt migration, model evaluation, gateway configuration — exceeds the savings. Use a closed API, ship the product, and revisit when you hit the Volume Gate.

### The Gemini question

Gemini 2.5 Pro at $1.25/$10 looks like frontier quality at near-open-weights pricing. Why migrate to open-weights when Gemini exists?

The answer depends on the workload shape.

**Output pricing is still asymmetric.** Gemini's output rate is $10/M — 8x Together's $1.25/M. For a RAG pipeline at 4,000 input / 600 output tokens and 800K requests/month, Gemini's LCPR is $0.0138 versus Together's $0.0079 — a 1.7x gap [MODELED]. For output-heavy workloads (code generation at 800/2,000 tokens), Gemini's LCPR rises to $0.0250 versus Together's $0.0054 — a 4.6x gap. Gemini is near-open-weights on *input* but not on *output*.

**No customization.** You cannot fine-tune Gemini, run custom speculators, control quantization, or modify the inference pipeline. Cursor and Decagon need these capabilities — it's why they use dedicated open-weights infrastructure.

**Data sovereignty.** Gemini runs on Google infrastructure with no self-hosting option and no zero-retention guarantee. For regulated workloads, this narrows the viable use cases.

**Vendor lock-in.** If Google changes pricing — as OpenAI did with GPT-5.5 — there's no portability. Open weights move between Together, Fireworks, DeepInfra, and self-hosted deployments.

**Where Gemini wins:** input-heavy classification and analysis workloads where output is short, customization is unnecessary, and Google's data handling is acceptable. At 2,000 input / 100 output tokens, the Gemini-to-Together LCPR ratio compresses to 1.2x — barely worth migrating [MODELED]. The Migration Gate framework still applies: if the savings don't cover migration cost, stay on Gemini.

### The break-even math for dedicated GPU

The three gates above address *whether* to migrate from closed APIs. A separate question is *when* to move from serverless open-weights to dedicated GPU. This is a volume calculation with a specific crossover point.

A Lambda H100 at $2.99/hr costs $2,153/month whether you use it or not. Running a 70B FP8 model with vLLM continuous batching, it sustains approximately 1,500 output tokens/sec at high batch utilization [REPORTED]. At full utilization, that's 129.6M output tokens per day. (This break-even is calculated on output tokens because, for typical chat workloads with moderate input and streaming output, throughput is bottlenecked by autoregressive decode. For long-context workloads with >8K input tokens or short-output tasks like classification, prefill dominates and the economics shift — dedicated becomes relatively more attractive because you're paying for compute you'd pay for anyway.)

Against Together's serverless rate of $1.25/M output tokens, break-even is **57.4M tokens/day at full utilization** [MODELED]. Against Fireworks at $0.90/M, it's 79.7M tokens/day.

But production workloads don't saturate. Real utilization on dedicated inference runs 30-50%, with 40% as the midpoint. The gap comes from decode-phase memory bandwidth limits, variable batch sizes across time-of-day, cold start periods after deployments, and the fact that real traffic doesn't produce constant request rates. Cast AI's finding that 49% GPU utilization on a 136-H200 cluster represents "the ceiling, not the floor" is consistent with what we see in practice [REPORTED]. At 40% real utilization, break-even against Together rises to **143.5M tokens/day**. Against Fireworks, it's 199.3M tokens/day [MODELED].

For context: 143.5M output tokens per day is approximately 4.8 million requests at 30 tokens per response, or 480,000 requests at 300 tokens per response. Most teams don't reach this volume on a single model endpoint. If your utilization consistently stays below 40%, the correct move is back to serverless — or consolidating workloads onto the GPU via Multi-LoRA serving.

### The decision flowchart

In practice, the three gates reduce to a sequence:

1. **Check the Volume Gate.** Is your monthly closed-API spend above $10K? If no, stay on closed APIs.
2. **Check the Specialization Gate.** Do you need fine-tuned models, hard latency SLOs, or model-level modifications? If yes, migrate regardless of volume.
3. **Check the Ownership Gate.** Do compliance, data residency, or vendor risk requirements force the move? If yes, migrate regardless of volume.
4. **If you pass Gates 1+2 or 1+3**, migrate to serverless open-weights first. Only move to dedicated when a single workload exceeds ~50M output tokens/day at theoretical max utilization (realistically ~140-200M at production utilization).

The most common mistake is skipping straight to dedicated GPU. Serverless open-weights is the right default for the vast majority of workloads that have passed the migration gates. Dedicated is for the outliers — and you'll know when you're an outlier because the serverless bill will tell you.

---

## Part 2: The Multi-Source Architecture

In 2024, most teams ran single-provider: OpenAI for everything. By mid-2025, the pattern shifted to "OpenAI + Anthropic + one fallback." In 2026, multi-sourcing is universal among serious AI-native companies. The question is no longer *whether* to multi-source but *how*.

This isn't a theoretical recommendation. Every company I've listed below runs multiple inference providers in production, and each has a specific architectural reason for doing so.

### The four patterns

Multi-source inference architectures fall into four patterns. Most production deployments use two or three of these simultaneously.

**Pattern 1: Workload-Segmented.** Different workloads go to different providers based on the workload's requirements. This is the most common pattern and the simplest to implement.

Cursor is the canonical example. Fast Apply (their deterministic code-edit feature) runs on a fine-tuned Llama-3-70B at ~1,000 tokens/sec through Fireworks speculative decoding. Sualeh Asif, Cursor co-founder: "We leverage speculative decoding for our custom models deployed on Fireworks.ai, which power the Fast Apply and Cursor Tab features. Thanks to speculative decoding, we saw up to a 2x reduction in generation latency" [REPORTED]. Note: Cursor's 2x speedup is for deterministic code-edit operations with predictable output structure — a different workload shape than the high-concurrency, variable-output scenario described in Part 0 where naive spec decode is net negative. Adaptive speculative decoding (FireOptimizer, ATLAS) addresses the batch-size problem by selecting draft strategies per-request. Composer 2 (their agentic coding model) trains and serves through Fireworks with weight syncs every training step via delta-compressed S3 uploads. Chat features use Claude Sonnet and Opus directly.

Cursor's production deployment spans multiple providers: Fireworks for speculative decoding on Fast Apply, Anthropic for frontier chat, and Together AI for Blackwell GPU inference with a quantization pipeline that moves new model weights from candidate to test endpoint within days [REPORTED].

Why multiple providers? Because each workload has a different constraint. Fast Apply needs throughput and deterministic diffs — a fine-tuned open model with speculative decoding. Chat needs frontier reasoning — Claude. Agentic coding needs training-inference integration — Fireworks RL infrastructure. And the quantization pipeline needs next-gen hardware — Together's Blackwell cluster.

Notion follows the same pattern: Fireworks for latency-critical features using fine-tuned models ("we reduced latency from about 2 seconds to 350 milliseconds," Sarah Sachs, Head of AI Engineering [REPORTED]), Baseten for other workloads, and Anthropic with prompt caching for features that benefit from frontier reasoning. Zomato's AI chatbot Zia, handling 1,000+ messages per minute on optimized Llama models through Together, achieved 2x CSAT improvement and 75% reduction in response time [REPORTED].

**Pattern 2: Capability-Arbitrage.** The same logical workload routes to different providers based on the *specific capability* needed for each request. This requires more sophisticated routing but captures large cost savings.

The Multi-LoRA pattern is the clearest example. Cresta runs thousands of LoRA adapters for per-domain contact center fine-tunes on Fireworks Multi-LoRA, with "a documented 100x cost reduction versus GPT-4" [REPORTED]. At $0.20/M tokens for a Llama 8B base with domain-specific adapters versus GPT-5.5 at $5/$30, the LCPR advantage is 27x at 3M requests/month [MODELED]. But Cresta doesn't route *everything* through Multi-LoRA — complex queries that exceed the fine-tune's capability escalate to a frontier model.

This is capability-arbitrage: use the cheapest model that can handle each request, and escalate only when necessary. The difficulty is building the routing logic to decide when to escalate. Most teams start with simple heuristics (input length, task type, confidence score) and add complexity only when the data justifies it.

**Pattern 3: Primary-Fallback.** A primary provider handles all traffic, with automatic failover to a secondary provider during outages or degradation. This is the minimum viable multi-source architecture.

The implementation is straightforward: an AI gateway (LiteLLM, Helicone, Portkey, or Bifrost) that routes to Provider A by default, detects failures (5xx responses, latency spikes above threshold, rate limit errors), and reroutes to Provider B. The same model family is available on both sides — DeepSeek V3 on Together with Fireworks as fallback, or Claude Sonnet via Anthropic with Bedrock as fallback.

This pattern doesn't save money. It costs slightly more because the fallback provider may have different pricing. Its value is availability: Anthropic outages in 2024-2025 demonstrated that single-source dependency on any provider — even a reliable one — is a business risk. If a single-provider outage costs more than 1% of monthly revenue, Primary-Fallback is table stakes.

**Pattern 4: Geo-Segmented.** Traffic routes to different providers based on geographic or regulatory requirements. This is compliance-driven, not cost-driven.

EU PII workloads route to Nebius (Finland, France) or Scaleway. US workloads route to any US-hosted provider. Federal workloads route to AWS Bedrock Government or Azure Government — the only FedRAMP-authorized paths as of May 2026. None of the neo-clouds (CoreWeave, Together, Baseten, Fireworks, Modal) have FedRAMP authorization yet.

Anthropic's `inference_geo=US` parameter with its 1.1x pricing multiplier is an honest acknowledgment of the cost of geographic constraints. If data residency matters, expect to pay for it.

### The complexity tax

Multi-source isn't free. Every additional provider adds operational surface area.

**Engineering overhead scales with providers, not linearly but noticeably.** Each provider has different API semantics, different error codes, different rate-limiting behavior, and different structured output support. Prompt portability between models is imperfect — a prompt tuned for Claude may perform differently on DeepSeek V3. My experience: budget 2-4 engineering days per provider for initial integration and 1-2 hours per month per provider for ongoing maintenance (API changes, deprecation notices, pricing updates).

**Observability multiplies.** Each provider produces telemetry in a different format. Standardizing on OpenTelemetry semantic conventions for GenAI helps, but the custom-metrics cost in Datadog or Grafana scales with the number of distinct provider×model combinations you're monitoring. Two providers with three models each is six metric series per telemetry dimension — that adds up fast against the observability tax described in Part 0.

**Testing multiplies.** Quality gates need to run against each provider×model combination. If you have three providers and two models each, that's six evaluation runs per prompt change. Automated evaluation pipelines (using frameworks like Braintrust, Arize, or custom harnesses) are mandatory at this point — manual evaluation doesn't scale.

The honest math: for a team running two providers with two models each, expect 8-16 engineering hours per month of multi-source overhead. At $100/hour, that's $800-$1,600/month — a meaningful fraction of the savings at lower volumes. This is why the Volume Gate matters: if you're saving $5,000/month by multi-sourcing, and spending $1,200/month managing the complexity, your net benefit is $3,800. Still positive, but not the 5-7x improvement the raw numbers suggest.

### The routing layer

Every multi-source deployment needs a routing layer. The question is how sophisticated to make it.

**Level 0: Model-keyed routing.** Model X goes to Provider A, Model Y goes to Provider B. No dynamic decisions. This is what most teams actually run, and it works. Implementation: a config file in your AI gateway.

**Level 1: Failover routing.** Level 0 plus automatic failover on provider errors. Implementation: your AI gateway's built-in retry/fallback logic (LiteLLM, Helicone, and Portkey all support this out of the box).

**Level 2: Cost-aware routing.** Route based on real-time pricing, rate limits, and capacity. Send overflow traffic to the cheapest available provider. Implementation: custom logic in your gateway, or a routing service like Martian ($18M raised, Accenture Ventures integration) or Not Diamond.

**Level 3: Quality-aware routing.** Route based on predicted model quality for the specific request. Estimate whether the cheap model can handle this request or if it needs the frontier model. Implementation: RouteLLM (open-source, out of UC Berkeley's LMSys group), or custom classifiers.

My recommendation for most teams: **Level 1, with plans for Level 2.** Level 0 is too fragile — you need failover. Level 1 is straightforward and covers 90% of the value. Level 2 is worth building when your monthly inference spend exceeds $100K and you have distinct traffic patterns with different cost sensitivities. Level 3 is research-grade — watch RouteLLM and RouterArena (arXiv:2510.00202, the first independent benchmark of routing quality), but don't bet production on it yet.

### The build-side end-state

Character.AI represents the far end of the multi-source spectrum: full vertical integration. Custom Kaiju-family models (13B/34B/110B) running on DigitalOcean AMD Instinct MI300X/MI325X GPUs, handling 1B+ queries per day at ~20,000 inference QPS [REPORTED]. Custom int8 attention kernels, KV cache on host memory between turns with LRU tree structure, quantization-aware training. They've achieved a 33x cost reduction since late 2022 and claim to be "13.5x cheaper than leading commercial APIs."

This is the build-side end-state. It works at Character.AI's scale. It does not work at yours. The engineering investment is measured in dozens of specialized inference engineers over multiple years. Don't attempt this until you have evidence — not a forecast, evidence — that your daily query volume justifies it. For everyone else, the serverless open-weights tier plus a routing layer gets you 80% of the economics at 5% of the engineering cost.

### What to implement first

If you're moving from single-source to multi-source, the implementation order matters:

1. **Add an AI gateway.** LiteLLM for development, Helicone or Portkey for production. This takes a day and costs nothing (LiteLLM and Helicone are open-source and self-hostable).
2. **Add a fallback provider** for your primary model. Same model family, different provider. Configure automatic failover in your gateway. This takes an afternoon.
3. **Move one workload** to a cheaper provider. Pick the workload with the highest token volume and lowest quality sensitivity — usually batch processing, summarization, or classification. Measure the LCPR before and after for 30 days before extending.
4. **Evaluate fine-tuning** for your highest-volume workload. If a fine-tuned 8B or 70B model matches frontier quality on your specific domain evaluation, the cost advantage justifies the training pipeline investment.
5. **Add geographic routing** only if compliance requires it.

Each step is independently valuable. You don't need to reach step 5 to benefit from step 1. The minimum viable multi-source architecture is steps 1 and 2 — a gateway with failover — and it can be implemented in a day.

---

## Part 3: What to Build vs. What to Buy

Inference is not one decision. It's a stack of seven decisions, and most teams make the wrong call at least twice because they treat the stack as monolithic.

The mistake is building at a layer where a commodity solution exists, or buying at a layer where the vendor's opinion doesn't match your workload. This section maps each layer and gives a recommendation.

### The Inference Stack Map

**Layer 1: AI Gateway.** *Recommendation: Buy.*

The gateway sits between your application and your inference providers. It handles routing, retries, rate limiting, and basic observability. The build case is almost never compelling because the open-source options are mature and free.

- **LiteLLM** (Python): broadest provider support, 100+ providers. Struggles past ~2,000 RPS per instance. Right for development and moderate production workloads.
- **Helicone** (Rust, Apache 2.0): ~50ms overhead, strongest combined observability + routing. Production users handling 5,000+ RPS [REPORTED].
- **Portkey**: enterprise control plane. Processes 2.5T+ tokens across 650+ organizations per their self-reporting. HIPAA BAA available.
- **Bifrost**: 11-microsecond overhead. Right for hyperscale where gateway latency matters.

For most teams: LiteLLM in development, Helicone or Portkey in production. Build your own only if you have a specific technical requirement none of these meet.

**Layer 2: Inference Runtime.** *Recommendation: Buy (use vLLM, SGLang, or TensorRT-LLM).*

The runtime turns model weights into token predictions. The build case exists for fewer than 10 teams globally.

- **vLLM**: the production default. 12,500 tok/s for Llama 3.1 8B BF16 on H100 [REPORTED]. Hardware support: NVIDIA, AMD, TPUs, Trainium, Gaudi. Continuous batching, PagedAttention, tensor parallelism. The right default unless you have a specific reason otherwise.
- **SGLang**: ~29% higher throughput than vLLM on shared-prefix workloads via RadixAttention [REPORTED]. Pick this for chat with long shared context, agent workloads, or evaluation harnesses.
- **TensorRT-LLM**: 15-30% higher peak throughput after a 10-30 minute compilation step. More mature multi-node support than vLLM as of May 2026. Pick this for stable models and latency-sensitive workloads (real-time voice, synchronous chat) where peak throughput and tail latency matter. Mature FP4 support on Blackwell (V0.17). The compilation overhead makes it unsuitable for frequent model updates, but for production deployments with infrequent model changes, it's the throughput leader.
- **TGI**: maintenance mode as of December 2025. Hugging Face now recommends vLLM or SGLang.

Build a custom runtime only if you have Character.AI-level scale (1B+ queries/day) and specific architectural requirements that justify custom attention kernels and KV cache management.

**Layer 3: Kernels.** *Recommendation: Buy.*

FlashAttention-4 (Tri Dao, Together AI co-founder and Chief Scientist, Hot Chips 2025): up to 22% faster than cuDNN attention on Blackwell [REPORTED]. Together Kernel Collection (TKC), built on Tri Dao's ThunderKittens framework developed with Stanford collaborators: reduces 1,000+ lines of CUDA to 100-200 lines while delivering 1.8x faster attention than FlashAttention-3, powering up to 75% faster FP8 inference on Blackwell [VENDOR CLAIM]. The research-to-production pipeline — FlashAttention → ThunderKittens → TKC → ATLAS — is a structural cost advantage: improvements come from fundamental research at the attention kernel level, not GPU arbitrage. Speculative decoding kernels are now a vendor differentiator: Together's ATLAS achieves 500 TPS on DeepSeek-V3.1 (2.65x standard decoding) by adapting draft model selection per-request rather than using a static draft model [REPORTED]. Fireworks' FireOptimizer delivers ~2x latency reduction at Cursor [REPORTED]. NVIDIA cuBLAS + CUTLASS for everything else. The build case is essentially zero outside of foundation model labs and the handful of teams doing custom attention work.

**Layer 4: Hardware.** *Recommendation: Buy from neo-clouds.*

This is where the money is. Neo-cloud providers (Lambda, RunPod, CoreWeave) offer 40-54% savings versus AWS for comparable on-demand GPU hours [PUBLIC]:

| Provider | GPU | $/hr | $/month |
|----------|-----|-----:|--------:|
| Lambda | H100 SXM | $2.99 | $2,153 |
| RunPod | H100 SXM5 | $4.41 | $3,175 |
| AWS | H200 (per GPU) | $4.975 | $3,582 |
| CoreWeave | H100 SXM | $6.16 | $4,435 |
| Baseten | H100 | $6.50 | $4,680 |

All prices are on-demand, per-GPU rates as of May 2026 [PUBLIC]. Lambda H100 SXM pricing requires 8-GPU minimum configs. Prices exclude persistent storage ($0.10-$0.25/GB/month), though InfiniBand/NVLink networking is included at most neo-clouds. Egress is zero at Lambda, RunPod, and CoreWeave; $0.05-$0.09/GB at AWS. Reserved pricing adds 15-40% discount for 1-12 month commits. Together AI also offers dedicated GPU clusters on 36,000 NVIDIA GB200 NVL72 GPUs co-built with Hypertec — one of the largest Blackwell deployments at launch, relevant for teams that need FP4 quantization and FlashAttention-4 on next-generation hardware [PUBLIC].

Lambda at $2.99/hr is 40% cheaper than AWS and 54% cheaper than Baseten. AWS hiked H200 prices ~15% in January 2026, widening the gap further [PUBLIC].

Two caveats. First, hyperscalers offer services neo-clouds don't — FedRAMP authorization, managed Kubernetes at scale, integrated data pipelines, and enterprise support contracts with meaningful remedies. If you need FedRAMP, AWS Bedrock Government or Azure Government are your only options. Second, if your application runs on AWS but inference runs on a neo-cloud, egress costs apply in both directions. For high-throughput workloads generating large outputs (code generation, long-form content), egress can add 20-40% to total cost. Factor this into your TCO calculation before committing.

**Layer 5: Orchestration.** *Recommendation: Buy NVIDIA Dynamo if multi-node.*

NVIDIA Dynamo 1.0 (GA March 2026) is the de facto disaggregation layer for multi-node NVIDIA GPU inference. Named production adopters include AstraZeneca, Baseten, ByteDance, CoreWeave, Crusoe, DigitalOcean, Meituan, Pinterest, Together AI, and Vultr [PUBLIC]. It sits above vLLM, SGLang, and TensorRT-LLM and provides KV-aware routing, SLA planning, and the NIXL low-latency transfer library.

For non-NVIDIA hardware (AMD MI300X, AWS Trainium, Google TPUs), orchestration options are runtime-specific: vLLM supports AMD and Trainium natively but lacks Dynamo's disaggregation features. For single-node deployments (1-8 GPUs), plain vLLM or SGLang with Kubernetes HPA is sufficient. You need Dynamo when you're running multi-node inference with disaggregated prefill and decode — typically 16+ GPUs across multiple nodes.

**Layer 6: Observability.** *Recommendation: Buy, but budget carefully.*

This is where teams get burned. LLM observability costs are growing 30-50% year over year, and AI workloads generate 10-50x more telemetry than traditional services [REPORTED].

- **Helicone** (bundled with gateway): free self-hosted, $20/seat/month Pro.
- **Arize AX**: free tier (1M traces / 14 days), Pro at $50/month.
- **Datadog GPU Monitoring**: $15-$23/host/month for infrastructure plus $31-$40/host for APM. The hidden cost is custom metrics — GenAI semantic-convention spans get billed as custom metrics, producing 40-200% bill increases [REPORTED].
- **Grafana Cloud Pro**: $19/month base plus usage-based pricing.

Start with Helicone for LLM-specific observability (traces, prompts, completions, token cost tracking). If you need production ML monitoring — drift detection, model quality regression over time, A/B test analysis — evaluate Arize, which covers a different dimension than Helicone. If you need general APM + infrastructure monitoring, Datadog is comprehensive but expensive: the median mid-market Datadog bill is $123K/year (byteiota.com, 2026) and growing 30-50% YoY. Budget 2-4x your Year-1 observability estimate.

**Layer 7: Routing Intelligence.** *Recommendation: Hold.*

The routing-startup category (Martian, Not Diamond, RouteLLM, Unify, TensorZero) is maturing but not yet production-proven at scale. RouteLLM (UC Berkeley LMSys, open-source) is the strongest option for teams comfortable running experimental infrastructure. RouterArena (arXiv:2510.00202) is the first independent benchmark.

For most teams: use your gateway's manual model-keyed routing. If you have a clear cost/quality routing problem — e.g., 70% of traffic can use a cheaper model without quality degradation — evaluate RouteLLM. Revisit the commercial routing category in 12 months when it has consolidated.

### The build-vs-buy summary

| Layer | Recommendation | Build only if... |
|-------|---------------|-----------------|
| Gateway | Buy (LiteLLM/Helicone) | Never, unless hyper-specific caching needs |
| Runtime | Buy (vLLM/SGLang) | 1B+ queries/day with custom arch needs |
| Kernels | Buy | You are Tri Dao |
| Hardware | Buy neo-cloud | You need FedRAMP → hyperscaler |
| Orchestration | Buy Dynamo if multi-node | Single-node → skip entirely |
| Observability | Buy (Helicone/Arize) | Don't build; budget carefully |
| Routing | Hold (evaluate RouteLLM if clear routing win) | Don't build, don't buy commercial yet |

---

## Part 4: The Seven-Gate Scorecard

Vendor evaluation in inference has a specific problem: the features that matter most are the hardest to evaluate from public information. Pricing is transparent. Latency under load is not. Compliance certifications are public. Zero data retention defaults are buried in terms of service.

The Seven-Gate Scorecard provides a structured evaluation framework. Each gate has a pass/fail criterion and a method for verification. A vendor that fails any gate should be eliminated for that workload, regardless of how well they score on the others.

### Gate 1: Model Availability

*Does the vendor serve the specific model(s) you need, at the precision you need?*

This seems obvious, but model availability is more nuanced than checking a catalog page. Key questions:
- Is your model available in FP8? FP4? The precision affects both quality and throughput.
- For fine-tuned models: can you deploy custom weights, or only use the vendor's hosted versions?
- For LoRA: does the vendor support runtime LoRA loading, or do you need a separate deployment per adapter?
- How quickly do new models become available after release? Some vendors lag by weeks.

**Verification method**: check the model catalog page, then verify the specific precision and configuration via API. Don't trust the catalog alone — models listed as "available" may be in preview or limited access.

### Gate 2: Latency Under Load

*What is the P50/P95/P99 latency at your expected concurrency, not on an empty endpoint?*

Vendor-published latency numbers are measured on unloaded endpoints with optimal batch sizes. Production latency under shared infrastructure is 2-5x worse at P99. The only reliable latency data is either (a) your own benchmark on the vendor's infrastructure, or (b) independent benchmarks like Artificial Analysis or SemiAnalysis InferenceMAX.

**Verification method**: run your actual prompts at your expected concurrency for at least 7 days to capture weekly traffic patterns (weekend dips, Monday spikes, diurnal variance). 24 hours is insufficient for P99 SLO validation. Measure TTFT and inter-token latency at P50, P95, and P99. If the vendor won't give you a trial endpoint with sufficient duration, that's information.

### Gate 3: Throughput Economics

*At your volume, what is the LCPR — not the token rate?*

This is the LCPR calculation from Part 0. Input the vendor's published rates, your workload profile (tokens, retry rate, quality gate, engineering hours), and compute the loaded cost. Compare across vendors at the LCPR level, not the token level.

**Verification method**: use the [LCPR calculator](https://github.com/sohailm/inference-field-guide) with your actual workload numbers. The vendor's pricing page is an input to the calculation, not the answer.

### Gate 4: Reliability and Failover

*What is the vendor's published uptime SLA, and what are the actual remedies?*

Most vendors offer 99.9% uptime with credit-based remedies. Read the credit math: most are capped at the monthly fee for the affected period, which doesn't cover your revenue loss during an outage.

Key questions:
- What's the historical uptime over the last 12 months? (Check status pages and incident histories.)
- Does the vendor support multi-region deployment for failover?
- What's the rate-limiting behavior under load? (Some vendors degrade gracefully; others return 429s aggressively.)

**Verification method**: check the vendor's status page history. Ask for uptime data covering the last 6 months. If they can't provide it, assume 99.5% or lower.

### Gate 5: Compliance and Data Handling

*Does the vendor's default data handling match your requirements — not just their certifications?*

SOC 2 Type II and HIPAA are table stakes — Fireworks, Baseten, Together, Modal, Nebius, and FriendliAI all have them. The differentiator is the *default* data handling behavior:

- **Baseten**: zero data retention by default (verified May 2026) [PUBLIC].
- **Fireworks**: zero retention on standard inference; Response API retains 30 days unless `store=false` (verified May 2026) [PUBLIC].
- **Together**: data stored by default unless disabled in settings (verified May 2026) [PUBLIC].
- **OpenAI**: fine-tuning data retained; API data retention varies by endpoint [PUBLIC].

Vendor data retention policies change. Verify current policy at contract time and get written confirmation — verbal assurances are insufficient for regulated workloads.

For EU data residency: Nebius (Finland, France), Scaleway, Mistral La Plateforme, OVH. For US federal: AWS Bedrock Government or Azure Government only.

**Verification method**: read the terms of service and data processing agreement. Ask specifically: "If I send a request to your API and do nothing else, is the prompt or completion stored? For how long? Where?" The answer should be in writing, not verbal.

### Gate 6: Integration Complexity

*How many engineering hours does it take to go from zero to production with this vendor?*

This covers API compatibility (OpenAI-compatible vs. custom), SDK quality, documentation completeness, structured output support, and streaming behavior. Vendors with OpenAI-compatible APIs (Together, Fireworks, DeepInfra) have lower integration cost because your existing code works with a URL change. Vendors with custom APIs (some Baseten configurations, custom runtimes) require more integration work.

**Verification method**: build a proof-of-concept integration. Measure time from API key to first successful production-format request. If it takes more than a day, factor that into your migration cost estimate.

### Gate 7: Pricing Trajectory

*Is this vendor's pricing going up or down, and why?*

This is the most forward-looking gate and the hardest to verify. The signal from April 2026 is clear: frontier closed APIs are increasing prices. Serverless open-weights providers are competing on price and have room to decrease. Dedicated GPU pricing follows hardware cycles — B200 availability in late 2026 should bring H100 prices down further.

Key questions:
- Has the vendor raised prices in the last 12 months? (OpenAI doubled GPT-5.5 rates on April 23, 2026.)
- What's the vendor's gross margin? (Fireworks estimated ~50% per Sacra research, targeting 60% [THIRD-PARTY ESTIMATE — Sacra reports are paywalled analyst estimates, not audited financials].)
- Does the vendor have structural cost advantages (custom kernels, speculative decoding, cache pooling) that protect margins without raising prices?

**Verification method**: check pricing page history via Wayback Machine. Read earnings calls or funding announcements for margin signals. Vendors with structural cost advantages — custom speculative decoding (Together ATLAS, Fireworks FireOptimizer), KV cache pooling (LMCache integration), custom kernels (TKC, FireAttention) — can maintain pricing as GPU commodity markets tighten. Vendors relying on GPU arbitrage alone will face margin pressure and may raise prices or reduce service quality.

### Using the scorecard

For each vendor under consideration, score each gate as Pass, Conditional Pass (acceptable with mitigation), or Fail. A Fail should eliminate the vendor unless you have a clear compensating control — failing Gate 4 (reliability) can be mitigated with multi-vendor failover; failing Gate 5 (compliance) for regulated workloads generally cannot. Two or more Conditional Passes should trigger deeper evaluation before committing.

The scorecard is deliberately binary — pass/fail, not scored 1-10 — because weighted scoring encourages teams to rationalize a preferred vendor by assigning high weights to gates where it excels. "Fail" means "fail for this workload without mitigation," not "never use this vendor."

---

## Part 5: The Staged Playbook

This final section synthesizes Parts 1-4 into concrete, staged guidance. Each stage has an entry threshold, a set of actions, and an exit threshold that tells you when to graduate to the next stage.

### Stage 0: Prototype (under $10,000/month)

**Entry**: you're building an AI-powered product and spending less than $10,000 per month on inference.

**Architecture**: single closed API (OpenAI, Anthropic, or Gemini). No gateway. No fallback. No dedicated GPU.

**Actions**:
1. Pick one provider. Anthropic if you need reasoning quality and prompt caching (90% reduction on cached input tokens [PUBLIC]). OpenAI if you need the broadest ecosystem. Gemini if you need the cheapest frontier option ($1.25/$10 for ≤200K context [PUBLIC]).
2. Use prompt caching aggressively. Anthropic's caching reduces cached input cost to 10% of base. OpenAI's automatic caching triggers on prompts ≥1,024 tokens at 50% discount [PUBLIC].
3. Don't optimize for inference cost. At $4,116/month on GPT-5.5 for 200K requests [MODELED], the savings from switching to open-weights ($2,987/month) don't justify the engineering distraction of migration. Ship the product.
4. Use prompt caching to stretch your closed-API budget further. A Sonnet workload with 4,800 input tokens (4,000-token system prompt + 800 user input) and 600 output tokens at 500K requests/month costs $12,901/month without caching. With Anthropic's 83% cache hit rate (the system prompt is cacheable), LCPR drops 43% to $7,361/month — a $5,540 savings with zero migration effort [MODELED]. Even cached Sonnet at $0.0155 LCPR is still 1.7x Together's uncached $0.0091, but the gap narrows enough that migration ROI becomes marginal at this volume.

**Exit threshold**: monthly inference spend exceeds $10,000 (approximately 500K requests/month on GPT-5.5 at 800/400 tokens — the point where multi-source migration ROI exceeds $7.5K/month per the Part 1 worked example), OR you experience a provider outage that costs revenue, OR a customer asks about data residency. The $10K figure is a guideline; teams with tight margins or latency-sensitive workloads may justify Stage 1 earlier.

### Stage 1: Scale ($10,000-$100,000/month)

**Entry**: you've passed the Volume Gate from Part 1.

**Architecture**: primary closed API + AI gateway + one or two serverless open-weights providers for specific workloads.

**Actions**:
1. Add an AI gateway (LiteLLM in dev, Helicone or Portkey in prod).
2. Add a fallback provider for your primary closed-API model (Anthropic via Bedrock, Gemini via Vertex).
3. Move long-tail, quality-insensitive workloads to serverless open-weights: batch processing, summarization, classification, embeddings. Together, Fireworks, or DeepInfra on Llama 3.3 70B, DeepSeek V3, or Qwen 3. For offline batch workloads (embeddings, evaluation harnesses, bulk summarization), consider spot-priced dedicated GPUs (RunPod spot, Lambda spot) at 40-70% discount — batch workloads tolerate interruption and higher latency.
4. Implement prompt caching everywhere it helps.
5. Start measuring LCPR, not just token cost. The difference matters at this scale.

**Worked example**: a team at 2M requests/month on GPT-5.5 spends $33,960/month [MODELED]. Splitting 70/30 — keeping 1.4M quality-sensitive requests on GPT-5.5 and moving 600K long-tail requests to Together — brings the combined bill to $25,799. That's $8,161/month in savings, or $97,932/year, with minimal engineering effort [MODELED].

**Exit threshold**: any single workload exceeds ~50M output tokens/day with steady traffic, OR you need a fine-tuned model, OR you have a hard latency SLO under 500ms that shared APIs can't meet.

### Stage 2: Production at Scale ($100,000-$1,000,000/month)

**Entry**: you've passed the Specialization Gate or hit the dedicated GPU crossover.

**Architecture**: multi-source with one or two dedicated GPU deployments for highest-volume workloads, serverless for everything else.

**Actions**:
1. Move your 1-2 highest-volume workloads to dedicated inference. Pick the vendor by workload fit: Baseten if you need TensorRT-LLM + observability tooling (Abridge, OpenEvidence, Writer references). Fireworks if you have agentic coding or RL post-training workloads (Cursor, Vercel v0 references). Together if you need production speculative decoding (ATLAS, 500 TPS on DeepSeek-V3.1), fine-tuning and inference on a unified platform, or next-gen hardware access via their 36,000 GB200 GPU deployment (Decagon reference: 90ms latency, 11x faster).
2. Run vLLM or SGLang. Use FP8 quantization for 70B-class models — quality holds within 1% of BF16 on most benchmarks [REPORTED].
3. Run NVIDIA Dynamo if multi-node.
4. Buy compliance certifications (SOC 2, HIPAA BAA) from your dedicated vendor.
5. Monitor GPU utilization weekly. The 40% threshold approximates the break-even between dedicated and serverless for 70B-class models: at Lambda's $2.99/hr and serverless rates of $0.90-$1.25/M tokens, you need roughly 10 hours/day of saturated throughput (42% daily utilization) to justify dedicated [MODELED]. Below that, serverless is cheaper. Consolidate via Multi-LoRA if you have multiple low-volume workloads that can share a GPU.

**Worked example**: at 10M requests/month, GPT-5.5 costs $166,600/month. Together serverless costs $17,250. A Lambda H100 at 40% utilization costs $8,258 for that same workload [MODELED] — but this excludes egress costs. Lambda charges zero egress, but if you're routing outputs through a hyperscaler's load balancer or CDN, add $0.05-$0.09/GB. At higher utilization, the dedicated cost drops further. The dedicated option wins at this volume if (a) utilization stays above 40%, and (b) egress costs don't negate the savings. Serverless remains the safer default.

**Exit threshold**: total monthly spend exceeds $1M, OR you have a strategic reason to control kernels and models end-to-end.

### Stage 3: Build-Side ($1,000,000+/month)

**Entry**: you've hit a scale where the operational investment in custom infrastructure is justified by the savings.

**Architecture**: dedicated inference on neo-cloud (Lambda, CoreWeave, Nebius) with vLLM/SGLang + custom optimizations. Serverless overflow path for traffic spikes.

**Actions**:
1. Hire 2-4 dedicated inference engineers, plus SRE support for on-call, alerting, and capacity planning. This is not optional — you cannot run dedicated inference at $1M+/month without specialized expertise. The inference team owns runtime optimization, quantization, KV cache tuning, and failure recovery. SREs own runbooks and operational tooling.
2. Adopt LMCache or Mooncake for KV cache pooling if your traffic has high prefix overlap (shared system prompts, RAG context, multi-turn chat). KV cache pooling deduplicates shared prefixes across requests — workloads with >70% prefix overlap see the largest gains. LMCache reports 1.9-8.1x smaller TTFT and 2.3-14x higher throughput versus baseline vLLM [REPORTED]. Mooncake powers Kimi K2 at 224K tokens/sec prefill on 128 H200 GPUs, processing 100B+ tokens daily [REPORTED].
3. Evaluate FP4 quantization on Blackwell with proper calibration. NVIDIA's analysis shows 1% or less accuracy degradation on key tasks [REPORTED]. FP4 on B200 doubles throughput versus FP8.
4. Maintain a serverless overflow path. Every dedicated deployment needs this. Traffic spikes happen, GPUs fail (Meta's Llama 3 training saw 466 job interruptions over 54 days, 78% hardware-related [REPORTED]), and autoscaling dedicated GPU is measured in minutes, not milliseconds.
5. Don't try to be Character.AI. They run custom Kaiju models on DigitalOcean AMD GPUs at 1B+ queries/day with custom int8 kernels and quantization-aware training. That's the build-side end-state. It works at their scale and represents a 33x cost reduction since 2022 [REPORTED]. Your scale is probably not their scale.

### The revert signals

Every stage transition should be monitored for revert signals — indicators that you've graduated too early.

- **Stage 1 → Stage 0**: If your multi-source overhead (gateway maintenance, prompt migration testing, vendor management) exceeds 20% of your inference savings, simplify back to a single provider.
- **Stage 2 → Stage 1**: If your dedicated GPU utilization stays below 40% for two consecutive months, move that workload back to serverless. At 40% utilization on a Lambda H100 ($2.99/hr), your effective cost per output token exceeds serverless rates ($0.90-$1.25/M) — you're paying $2,153/month in fixed GPU cost for throughput you could get cheaper on-demand [MODELED].
- **Stage 3 → Stage 2**: If your inference engineering team spends more than 50% of their time on operational issues (GPU failures, OOM errors, kernel debugging) rather than optimization, you don't have the operational maturity for build-side infrastructure yet.

These revert signals are as important as the exit thresholds. The right architecture is the simplest one that meets your cost and performance requirements. Over-engineering inference is as wasteful as over-paying for it.

---

## Closing

The frameworks in this guide — LCPR, Migration Gates, Inference Sourcing Patterns, the Stack Map, the Seven-Gate Scorecard, and the Staged Playbook — are tools for making decisions with math instead of vibes. They're opinionated, because frameworks that try to accommodate every edge case end up accommodating none.

The companion [LCPR calculator](https://github.com/sohailm/inference-field-guide) lets you run these calculations against your actual workload. Every number in this essay was generated by that calculator and verified against May 2026 public pricing. When prices change — and they will — update the YAML and re-run.

I work at Together AI. I've tried to write this guide as if I didn't. Where I've failed at that, the evidence tags are there so you can check my work.

The best time to calculate your LCPR was six months ago. The second best time is now.

---

*Sohail Mohammad — May 2026*
*[GitHub](https://github.com/sohailm/inference-field-guide) · [LCPR Calculator](https://github.com/sohailm/inference-field-guide)*
