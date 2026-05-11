# Build vs Buy Per Layer

The inference stack has 7 layers. Each is an independent build-vs-buy decision.

```mermaid
flowchart LR
    subgraph STACK["Inference Stack (top to bottom)"]
        L1["Layer 1: AI Gateway"]
        L2["Layer 2: Inference Runtime"]
        L3["Layer 3: Kernels"]
        L4["Layer 4: Hardware"]
        L5["Layer 5: Orchestration"]
        L6["Layer 6: Observability"]
        L7["Layer 7: Routing Intelligence"]
    end

    L1 --> V1["BUY: LiteLLM, Helicone,<br/>Portkey, Kong, Bifrost"]
    L2 --> V2["BUY: vLLM (default),<br/>SGLang (shared-prefix),<br/>TRT-LLM (peak perf)"]
    L3 --> V3["BUY: FlashAttention-4,<br/>TKC, cuBLAS/CUTLASS"]
    L4 --> V4["BUY: Neo-cloud<br/>40-85% cheaper than AWS/GCP"]
    L5 --> V5["BUY: NVIDIA Dynamo 1.0<br/>(if multi-node)"]
    L6 --> V6["BUY: Helicone, Arize,<br/>Grafana (watch Datadog costs)"]
    L7 --> V7["HOLD: Not mature enough<br/>Martian, RouteLLM, Not Diamond"]

    style V1 fill:#e8f5e9
    style V2 fill:#e8f5e9
    style V3 fill:#e8f5e9
    style V4 fill:#e8f5e9
    style V5 fill:#e8f5e9
    style V6 fill:#fff3e0
    style V7 fill:#fce4ec
```

## Layer Verdicts

| Layer | Verdict | Build When | Buy Options |
|-------|---------|-----------|-------------|
| 1. AI Gateway | **Buy** | Almost never | LiteLLM, Helicone (~50ms, Apache 2.0), Portkey (enterprise), Kong, Bifrost (11μs) |
| 2. Inference Runtime | **Buy** | Character.AI-level scale | vLLM (default), SGLang (shared-prefix), TRT-LLM (peak perf), ~~TGI~~ (maintenance mode) |
| 3. Kernels | **Buy** | Never (outside foundation labs) | FlashAttention-4, TKC, cuBLAS/CUTLASS |
| 4. Hardware | **Buy** | Hyperscaler-level | Neo-cloud: CoreWeave, Nebius, Lambda, RunPod (40-85% cheaper) |
| 5. Orchestration | **Buy Dynamo** | Single-node (just use vLLM) | NVIDIA Dynamo 1.0 — 17+ production adopters |
| 6. Observability | **Buy** | Never | Helicone, Arize, Grafana. Datadog works but watch for 40-200% bill increase |
| 7. Routing Intelligence | **Hold** | Not yet | Martian, RouteLLM, Not Diamond — category immature |

## The Vanity Infrastructure Test

If the only reason to self-host is "we want control," and the team doesn't have
a named owner who will maintain the stack through model updates, quantization
changes, and runtime upgrades — it's vanity infrastructure. It will rot.

## The Observability Warning

LLM observability costs are growing 30-50% YoY. AI workloads generate 10-50x
more telemetry than traditional services. The median Datadog bill for mid-market
companies is $123K/year and growing.

Budget 2-4x your Year-1 observability estimate. If your observability bill
exceeds 5% of your inference compute bill, you have a configuration problem.
