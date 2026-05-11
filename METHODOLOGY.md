# Methodology

How numbers in this guide were calculated and sourced.

## Evidence Tags

Every vendor claim in the essay and calculator uses one of four evidence tags:

| Tag | Meaning | Reliability |
|-----|---------|-------------|
| `[PUBLIC]` | From vendor's public docs or pricing page | Verifiable by reader |
| `[MEASURED]` | From the author's own production experience | First-party but not reproducible |
| `[REPORTED]` | From third-party benchmarks or customer references | Independent but context-dependent |
| `[MODELED]` | Calculated/estimated with methodology shown | Transparent but assumption-dependent |

## Pricing Data

All pricing data is from public pricing pages as of May 2026. Negotiated rates
for committed spend are typically 20-40% below list prices.

Pricing sources:
- Together AI: https://together.ai/pricing
- Fireworks AI: https://fireworks.ai/pricing
- Baseten: https://baseten.co/pricing
- OpenAI: https://openai.com/api/pricing
- Anthropic: https://anthropic.com/pricing
- Lambda: https://lambdalabs.com/service/gpu-cloud
- CoreWeave: https://coreweave.com/pricing

## LCPR Calculation

The Loaded Cost Per Request (LCPR) formula:

```
LCPR = (input_tokens * input_rate
        + output_tokens * output_rate
        + retry_cost
        + invalid_output_repair_cost
        + amortized_engineering_cost)
       / requests_meeting_latency_quality_and_schema_gates
```

### Variables

- `input_tokens`, `output_tokens`: Average per request
- `input_rate`, `output_rate`: Per-token pricing (varies by provider and model)
- `retry_cost`: Cost of retried requests (retry_rate * base_cost_per_request)
- `invalid_output_repair_cost`: Cost of re-prompting for schema/quality failures
- `amortized_engineering_cost`: Monthly engineering hours * hourly rate / monthly requests
- `requests_meeting_*_gates`: Requests that pass latency, quality, and schema checks

### Break-Even Analysis

Dedicated vs. serverless break-even:

```
break_even_tokens_per_day = (gpu_hourly_rate * 24 * utilization_factor) /
                            (serverless_per_token_rate * 1_000_000)
```

Where `utilization_factor` accounts for real-world batch variance (typically 0.3-0.5
of theoretical maximum throughput).

## Benchmark Sources

Independent benchmarks cited:
- Artificial Analysis (April 2026): Provider throughput and pricing comparisons
- SemiAnalysis InferenceMAX v1: Blackwell benchmark suite
- Spheron benchmark report: vLLM/SGLang/TRT-LLM comparison on H100
- Clarifai benchmark: Runtime throughput comparison

## Limitations

- Pricing changes frequently. Verify against current public pages before making decisions.
- Vendor-published benchmarks use vendor-controlled harnesses. Independent benchmarks are preferred.
- Engineering time estimates are based on limited published data and consulting case studies.
- The "typical" workload profiles in the calculator are illustrative, not prescriptive.
