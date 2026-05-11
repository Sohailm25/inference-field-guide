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

## Part 1: When to Leave the API

The question is not *whether* open-weights inference is cheaper. Part 0 showed the LCPR math — 5-7x at the loaded level, 10-100x on raw tokens. The question is whether the savings justify the migration cost, and for which workloads.

Most teams get this wrong in one of two directions. They either stay on closed APIs past the point where they're hemorrhaging money, or they migrate too early, spend 10 engineer-weeks rebuilding prompt pipelines, and discover the savings don't cover the engineering bill for two years.

This section provides three gates. Pass all three and migration is nearly always worth it. Fail any one and you should stay put — or at least stay put for that workload.

### Gate 1: The Volume Gate

Migration has a fixed cost. Based on published case studies and industry norms, moving one production workload from a closed API to serverless open-weights inference takes **6-10 engineer-weeks** for a competent ML platform team, plus another 4-8 weeks of optimization to reach cost parity [REPORTED]. That's the Braincuber estimate (6 weeks, $38K for a fintech client scaling from 2M to 15M daily tokens) and the Introl vLLM hardening estimate ("one to two weeks" for production hardening alone, which understates the upstream evaluation work).

At a blended rate of $150/hour for a senior ML engineer, 8 engineer-weeks costs $48,000. The question is simple: does your monthly savings exceed the amortized migration cost over a reasonable payback period?

Here's the worked example. A B2B SaaS company running 800,000 requests per month on GPT-5.5, with 1,000 input tokens and 500 output tokens per request, a 5% retry rate, 92% quality gate pass rate, and 12 engineering hours per month to maintain the stack.

| Provider | LCPR | Monthly cost |
|----------|-----:|-----------:|
| OpenAI GPT-5.5 | $0.0246 | $18,128 |
| Lambda H100 (dedicated, 40% util) | $0.0047 | $3,481 |
| Together AI DeepSeek V3 (serverless) | $0.0039 | $2,903 |
| Fireworks AI Llama 70B (serverless) | $0.0033 | $2,462 |

Switching from GPT-5.5 to Together DeepSeek V3 saves $15,225 per month — $182,700 per year [MODELED]. Against a $48,000 migration cost, the payback period is 3.2 months. That's a clear pass.

But notice what happens at lower volume. In the Part 0 worked example (500K requests/month, simpler workload profile), GPT-5.5's monthly cost was $9,065. Against Together at $1,598, the savings are $7,467/month. Still a 6.4-month payback — acceptable, but you're now sensitive to migration overruns. If the migration takes 12 weeks instead of 8, or if the quality gate drops from 95% to 88% during the transition and you spend two months tuning prompts, the payback stretches past a year.

**The Volume Gate threshold**: if your monthly closed-API spend is below $10,000, the migration economics are marginal. Between $10,000 and $50,000, the economics work but execution risk matters — you need a team that's done this before. Above $50,000, the savings are large enough to absorb migration friction. These boundaries are rough; run the [LCPR calculator](https://github.com/sohailm/inference-field-guide) against your actual workload to get precise numbers.

### Gate 2: The Specialization Gate

Volume isn't the only reason to migrate. Sometimes the workload requires something closed APIs can't provide.

**Fine-tuned models.** If your quality evaluation shows that a fine-tuned 8B or 70B model matches frontier quality for your specific domain, the cost advantage is enormous. Cresta runs thousands of LoRA adapters for per-domain contact center agents on Fireworks Multi-LoRA at $0.20/M tokens — a 26.6x LCPR advantage over GPT-5.5 at scale [MODELED]. Even accounting for the engineering cost of training and maintaining the fine-tune pipeline, the payback is measured in weeks, not months.

**Latency SLOs.** Shared APIs under load produce P99 latency spikes from ~300ms to 2-4 seconds on 70B-class models. For agent pipelines with 5+ chained calls, that compounds: a 2-second P99 across 5 calls is a 10-second worst case. Dedicated inference lets you control batch size and KV cache budget. Decagon achieved 90ms model latency and P90 of 342ms for voice AI agents using Together AI with custom-trained speculators per application — "6x cost reduction per turn vs. gpt-5 mini, 11x faster inference" [REPORTED].

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

**Small-token, high-volume workloads where Mini-class models win.** GPT-5.5 Mini at $0.30/$1.50 per million tokens is cheaper than Together DeepSeek V3 at $1.25/$1.25 for workloads with short outputs. A voice classification task at 300 input tokens and 150 output tokens costs $0.00076 LCPR on Mini versus $0.00101 on Together [MODELED]. Open-weights isn't always cheaper — the math depends on the input/output ratio and which model tier you're comparing against.

**Reasoning-heavy workloads where frontier quality matters.** If your task requires chain-of-thought reasoning, mathematical proof, or complex code generation where GPT-5.5 or Claude Opus 4.7 measurably outperform open-weights alternatives, the quality delta means more failed requests, more retries, and a higher LCPR on the open-weights side. Quality gate pass rate is the most powerful variable in the LCPR formula — a 10-point drop from 95% to 85% increases LCPR by 12%.

**Prototyping and early product.** At less than $10,000 per month, the engineering overhead of managing even a serverless open-weights deployment — prompt migration, model evaluation, gateway configuration — exceeds the savings. Use a closed API, ship the product, and revisit when you hit the Volume Gate.

### The break-even math for dedicated GPU

The three gates above address *whether* to migrate from closed APIs. A separate question is *when* to move from serverless open-weights to dedicated GPU. This is a volume calculation with a specific crossover point.

A Lambda H100 at $2.99/hr costs $2,153/month whether you use it or not. Running a 70B FP8 model with vLLM continuous batching, it sustains approximately 1,500 tokens/sec at high batch utilization [REPORTED]. At full utilization, that's 129.6M output tokens per day.

Against Together's serverless rate of $1.25/M output tokens, break-even is **57.4M tokens/day at full utilization** [MODELED]. Against Fireworks at $0.90/M, it's 79.7M tokens/day.

But production workloads don't saturate. Real utilization on dedicated inference runs 30-50%, with 40% as the midpoint — consistent with Cast AI's finding that 49% GPU utilization on a 136-H200 cluster represents "the ceiling, not the floor" [REPORTED]. At 40% real utilization, break-even against Together rises to **143.5M tokens/day**. Against Fireworks, it's 199.3M tokens/day [MODELED].

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

Cursor is the canonical example. Fast Apply (their deterministic code-edit feature) runs on a fine-tuned Llama-3-70B at ~1,000 tokens/sec through Fireworks speculative decoding. Sualeh Asif, Cursor co-founder: "We leverage speculative decoding for our custom models deployed on Fireworks.ai, which power the Fast Apply and Cursor Tab features. Thanks to speculative decoding, we saw up to a 2x reduction in generation latency" [REPORTED]. Composer 2 (their agentic coding model) trains and serves through Fireworks with weight syncs every training step via delta-compressed S3 uploads. Chat features use Claude Sonnet and Opus directly.

Why three providers? Because each workload has a different constraint. Fast Apply needs throughput and deterministic diffs — a fine-tuned open model with speculative decoding. Chat needs frontier reasoning — Claude. Composer needs training-inference integration with fast iteration cycles — Fireworks RL infrastructure.

Notion follows the same pattern: Fireworks for latency-critical features using fine-tuned models ("we reduced latency from about 2 seconds to 350 milliseconds," Sarah Sachs, Head of AI Engineering [REPORTED]), Baseten for other workloads, and Anthropic with prompt caching for features that benefit from frontier reasoning.

**Pattern 2: Capability-Arbitrage.** The same logical workload routes to different providers based on the *specific capability* needed for each request. This requires more sophisticated routing but captures large cost savings.

The Multi-LoRA pattern is the clearest example. Cresta runs thousands of LoRA adapters for per-domain contact center fine-tunes on Fireworks Multi-LoRA, with "a documented 100x cost reduction versus GPT-4" [REPORTED]. At $0.20/M tokens for a Llama 8B base with domain-specific adapters versus GPT-5.5 at $5/$30, the LCPR advantage is 26.6x at scale [MODELED]. But Cresta doesn't route *everything* through Multi-LoRA — complex queries that exceed the fine-tune's capability escalate to a frontier model.

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

*Part 3: What to Build vs. What to Buy →*
