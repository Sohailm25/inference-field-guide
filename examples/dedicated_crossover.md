# Worked Example: Serverless → Dedicated Crossover

When does it make sense to move a workload from serverless to dedicated?
This example walks through the break-even math.

## Scenario

A company running Llama 3.3 70B on Fireworks serverless at $0.90/M output tokens.
Daily volume: 30M output tokens, growing 15% month-over-month. Traffic is steady
(not bursty) with a 10-hour peak window.

## Break-Even Calculation

### Serverless Cost (current)
```
30M tokens/day × $0.90/M = $27.00/day
$27.00 × 30 = $810/month
```

### Dedicated Cost Options

**Option A: Lambda H100 SXM ($2.99/hr — verified May 2026)**
```
Theoretical max: 1,500 tok/s × 3,600 = 5.4M tokens/hr at saturation
Real utilization at 40%: 2.16M tokens/hr effective
Hours needed: 30M / 2.16M = 13.9 hours/day at 40% utilization

Cost: 13.9 hr × $2.99 = $41.56/day
But: GPU must be provisioned 24/7 = $2.99 × 24 = $71.76/day
Monthly: $71.76 × 30 = $2,153/month
```
**Verdict: Serverless wins at 30M tokens/day on Lambda.**

**Option B: Lambda H100, scale-to-zero possible**
```
If traffic compresses to 14 hours: $2.99 × 14 = $41.86/day = $1,256/month
Still more expensive than $810/month serverless.
```

**Option C: RunPod H100 SXM5 ($4.41/hr), 24/7**
```
$4.41 × 24 × 30 = $3,175/month
Even worse.
```

### Where Dedicated Wins

```
Break-even (Lambda, 24/7 provisioned at $2.99/hr):
$71.76/day ÷ ($0.90/M) = 79.7M tokens/day

Break-even (Lambda, scale-to-zero at 14 hours):
$41.86/day ÷ ($0.90/M) = 46.5M tokens/day

Break-even (with realistic 40% utilization correction):
Effective throughput: 1,500 × 0.40 = 600 tok/s
Max daily at 14 hours: 600 × 3,600 × 14 = 30.2M tokens
Need 2 GPUs for 46.5M: $83.72/day = $2,512/month
Serverless at 46.5M: 46.5 × $0.90 = $41.85/day = $1,256/month
Still serverless wins!

True break-even requires higher utilization OR cheaper GPUs:
At 60% utilization: 900 tok/s × 3,600 × 24 = 77.8M tokens/day
$71.76/day vs serverless at 77.8M: $70.02/day
Almost break-even at 60% utilization — but 60% sustained is rare.

At Lambda reserved rate ($1.89/hr):
$1.89 × 24 = $45.36/day
Break-even: $45.36 ÷ $0.90/M = 50.4M tokens/day at full utilization
With 40% utilization factor: ~3x → need ~150M tokens/day effective
```

## Key Insight

**The folk wisdom "dedicated is cheaper at scale" requires:**
1. Sustained utilization above 40% (most teams don't achieve this)
2. Very high daily volume (>50M output tokens/day minimum, often >100M)
3. Cheap GPU rates (neo-cloud, not hyperscaler)
4. Steady traffic (bursty traffic kills utilization)

**The 3x rule**: Whatever the naive break-even calculation shows, multiply
by ~3x to account for real-world utilization. This is the single most
common mistake in dedicated inference ROI calculations.

## When This Company Should Switch

At 15% month-over-month growth:
- Month 0: 30M tokens/day → $810/month serverless ✓
- Month 6: 69M tokens/day → $1,863/month serverless
- Month 9: 105M tokens/day → $2,835/month serverless
- Lambda dedicated (24/7 at $2.99/hr): $2,153/month

**Crossover at ~Month 7-8** assuming steady traffic and 40%+ utilization.
But: only if traffic is steady enough to sustain utilization. If growth
is bursty, the crossover point moves further out.

**Recommendation**: Re-evaluate at Month 6. If traffic is steady and
approaching 80M tokens/day, start the 6-10 week migration planning.
