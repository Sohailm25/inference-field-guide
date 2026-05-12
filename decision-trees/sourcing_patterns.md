# Which Multi-Source Pattern?

Four inference sourcing patterns, each suited to different organizational needs.

```mermaid
flowchart TD
    START([How many distinct<br/>workload types?]) --> Q1

    Q1{Different latency/quality<br/>requirements per workload?}
    Q1 -->|Yes| WS[Workload-Segmented<br/>Different provider per workload type]
    Q1 -->|No| Q2

    Q2{Need best-in-class for<br/>specific capabilities?}
    Q2 -->|Multi-LoRA, spec decoding,<br/>custom Docker| CA[Capability-Arbitrage<br/>Best provider per capability]
    Q2 -->|No| Q3

    Q3{Primary concern is<br/>availability/reliability?}
    Q3 -->|Yes| PF[Primary-Fallback<br/>Same model, multiple providers]
    Q3 -->|No| Q4

    Q4{Compliance-driven<br/>geographic requirements?}
    Q4 -->|Yes| GS[Geo-Segmented<br/>Provider per region/regulation]
    Q4 -->|No| PF

    WS --> EXAMPLES_WS["Examples:<br/>Cursor: Fireworks (Fast Apply) + Together (Blackwell inference) + Anthropic (chat)<br/>Notion: Fireworks (latency) + Baseten (other)"]

    CA --> EXAMPLES_CA["Examples:<br/>Cresta: Fireworks Multi-LoRA<br/>Decagon: Together ATLAS speculation<br/>Writer: Baseten custom Docker"]

    PF --> EXAMPLES_PF["Examples:<br/>Sourcegraph: Fireworks + Anthropic/OpenAI<br/>Minimum: AI gateway with health-checked routing"]

    GS --> EXAMPLES_GS["Examples:<br/>EU: Nebius (Finland/France), Scaleway<br/>US Federal: AWS Bedrock Gov / Azure Gov<br/>Healthcare: Baseten (Abridge, OpenEvidence)"]

    style WS fill:#e3f2fd
    style CA fill:#f3e5f5
    style PF fill:#e8f5e9
    style GS fill:#fff3e0
```

## Pattern Details

### 1. Workload-Segmented
Different providers for different workload types based on latency/quality/cost tradeoffs.
- **When**: Multiple workloads with different SLOs
- **Complexity**: Medium (N provider relationships, simple routing)
- **Example**: Cursor — Fast Apply on Fireworks, Blackwell inference on Together, chat on Anthropic

### 2. Capability-Arbitrage
Best provider per specific technical capability.
- **When**: Need Multi-LoRA, speculative decoding, custom runtime, or RL inference
- **Complexity**: Medium-High (capability-specific integration per provider)
- **Example**: Cresta — thousands of LoRA adapters on Fireworks at 100x cost reduction vs GPT-4

### 3. Primary-Fallback
Same model family across multiple providers for availability.
- **When**: Single-provider outage would cost >1% monthly revenue
- **Complexity**: Low (AI gateway handles routing)
- **Minimum viable**: LiteLLM / Helicone / Portkey with health-checked failover

### 4. Geo-Segmented
Provider selection driven by compliance and data residency.
- **When**: EU data residency, US Federal, healthcare, China
- **Complexity**: High (separate contracts, monitoring, incident response per region)
- **Forced**: FedRAMP → hyperscaler only. EU PII → Nebius/Scaleway
