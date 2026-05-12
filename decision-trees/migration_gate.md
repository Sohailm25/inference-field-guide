# When to Leave the API

The Migration Gate Framework: three gates, all must pass.

```mermaid
flowchart TD
    START([Current workload on<br/>closed API]) --> G1

    G1{Gate 1: Volume<br/>Monthly spend >$10K?}
    G1 -->|No| STAY_API[Stay on closed API<br/>Re-evaluate quarterly]
    G1 -->|Yes, $10K-$100K| SERVERLESS[Add serverless open-model<br/>for long-tail workloads]
    G1 -->|Yes, >$100K| G1B

    G1B{Single workload<br/>>50M output tokens/day<br/>with steady traffic?}
    G1B -->|No| SERVERLESS
    G1B -->|Yes| G2

    G2{Gate 2: Specialization<br/>Need capabilities unavailable<br/>on serverless?}
    G2 -->|No| SERVERLESS_DEDICATED[Evaluate dedicated for<br/>cost savings only]
    G2 -->|Fine-tuned model| G3
    G2 -->|Hard latency SLO <500ms p95| G3
    G2 -->|Compliance controls| G3
    G2 -->|Custom LoRA not served| G3

    SERVERLESS_DEDICATED --> BREAKEVEN{Break-even math:<br/>GPU utilization >40%?}
    BREAKEVEN -->|No| SERVERLESS
    BREAKEVEN -->|Yes| G3

    G3{Gate 3: Ownership<br/>Named owner + capacity<br/>for 6-10 eng-weeks?}
    G3 -->|No| MANAGED[Use managed dedicated<br/>Baseten / Fireworks / Together]
    G3 -->|Yes| DEDICATED[Self-managed dedicated<br/>Neo-cloud + vLLM/SGLang]

    style STAY_API fill:#e8f5e9
    style SERVERLESS fill:#e3f2fd
    style MANAGED fill:#fff3e0
    style DEDICATED fill:#fce4ec
```

## Gate Details

### Gate 1: Volume
- Under ~$10K/month: Stay on closed APIs
- $10K-$100K/month: Add serverless open-model (Together, Fireworks, DeepInfra)
- One workload >50M output tokens/day steady: Consider dedicated (realistically ~140-200M at production utilization)

### Gate 2: Specialization
- Fine-tuned models not available serverless
- Hard latency SLO (<500ms p95) — shared APIs spike to 2-4s p99 under load
- Compliance: data residency, zero retention, CMEK
- Custom quantization with controlled calibration

### Gate 3: Ownership
- 6-10 engineer-weeks for initial migration
- 4-8 weeks for optimization to cost crossover
- 2-4 weeks per model-update cycle ongoing
- If no owner exists, use managed dedicated (Baseten, Fireworks, Together)
