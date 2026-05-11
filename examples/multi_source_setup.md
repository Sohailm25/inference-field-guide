# Worked Example: Workload-Segmented Architecture

An AI-native company with multiple inference workloads needing different
performance characteristics.

## Workload Profile

| Workload | Volume | Latency SLO | Quality Requirement |
|----------|--------|-------------|-------------------|
| Code completion | 25M output tokens/day | p95 < 500ms | Must match GPT-5.5 |
| Chat | 10M output tokens/day | p95 < 2s | Frontier quality |
| Batch analysis | 50M output tokens/day | None (async) | 90% of frontier |
| Voice agent | 2M output tokens/day | p95 < 200ms TTFT | Domain-specific |

## Sourcing Decision

### Code Completion → Fireworks (dedicated)
- **Why Fireworks**: Speculative decoding (2x latency reduction), Cursor reference
- **Model**: Fine-tuned Llama 70B with custom speculator
- **Deployment**: Dedicated GPUs via Fireworks
- **Fallback**: Together ATLAS on same model family

### Chat → Anthropic Claude (serverless)
- **Why Anthropic**: Frontier quality, prompt caching (90% input cost reduction)
- **Model**: Claude Sonnet 4.6
- **Deployment**: Direct API with prompt caching
- **Fallback**: OpenAI GPT-5.5 via Bedrock

### Batch Analysis → Together (serverless)
- **Why Together**: Broad catalog, batch pricing, no latency constraint
- **Model**: DeepSeek V3 serverless
- **Deployment**: Async batch API
- **Fallback**: DeepInfra (10-30% cheaper, same models)

### Voice Agent → Together ATLAS (dedicated)
- **Why Together**: ATLAS adaptive speculation, 90ms model latency (Decagon reference)
- **Model**: Custom fine-tune with per-application speculator
- **Deployment**: Dedicated with ATLAS
- **Fallback**: Fireworks dedicated

## Infrastructure

```
                    ┌─────────────────┐
                    │   AI Gateway    │
                    │ (Helicone/      │
                    │  LiteLLM)       │
                    └────────┬────────┘
                             │
            ┌────────────────┼────────────────┐
            │                │                │
     ┌──────┴──────┐  ┌─────┴─────┐  ┌──────┴──────┐
     │  Fireworks  │  │ Anthropic │  │  Together   │
     │  Dedicated  │  │ Serverless│  │ Serverless  │
     │ (code comp) │  │  (chat)   │  │(batch+voice)│
     └─────────────┘  └───────────┘  └─────────────┘
```

## Operational Cost

- 3 provider relationships (billing, monitoring, incident response each)
- AI gateway: ~$200/month (Helicone Team) or self-hosted (free)
- Monitoring: Helicone covers all 3 providers through single gateway
- Estimated engineering overhead: 8-12 hours/month for gateway + routing maintenance

## When This Becomes Stage 2

- Code completion exceeds 25M tokens/day sustained → already on dedicated
- Batch analysis grows past $50K/month → evaluate dedicated on neo-cloud
- Voice agent latency needs tighten → consider custom silicon (Groq) for decode
