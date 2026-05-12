# ABOUTME: Canonical WorkloadProfiles for every worked example in the essay.
# ABOUTME: Single source of truth — essay numbers derive from these profiles.

from dataclasses import replace

from calculator.lcpr import WorkloadProfile

# ─── Part 0: The Cost Illusion ────────────────────────────────────────────────

# Main table (line 62-72): 500K requests, 800/400 tokens
PART0_SAAS = WorkloadProfile(
    avg_input_tokens=800,
    avg_output_tokens=400,
    monthly_requests=500_000,
    retry_rate=0.03,
    quality_gate_pass_rate=0.95,
    repair_cost_per_failure=0.002,
    engineering_hours_per_month=8,
    engineer_hourly_cost=100,
)

# Sensitivity: 20% retry rate (line 86)
PART0_HIGH_RETRY = replace(PART0_SAAS, retry_rate=0.20)

# Sensitivity: 70% quality gate (line 88)
PART0_LOW_GATE = replace(PART0_SAAS, quality_gate_pass_rate=0.70)

# Sensitivity: 85% quality gate — for "10-point drop" claim (line 175)
PART0_85_GATE = replace(PART0_SAAS, quality_gate_pass_rate=0.85)

# ─── Part 1: When to Leave the API ───────────────────────────────────────────

# B2B SaaS migration example (line 130-138)
PART1_B2B = WorkloadProfile(
    avg_input_tokens=1000,
    avg_output_tokens=500,
    monthly_requests=800_000,
    retry_rate=0.05,
    quality_gate_pass_rate=0.92,
    repair_cost_per_failure=0.002,
    engineering_hours_per_month=12,
    engineer_hourly_cost=100,
)

# Mini vs open-weights comparison (line 173): voice classification
PART1_MINI_VOICE = WorkloadProfile(
    avg_input_tokens=300,
    avg_output_tokens=150,
    monthly_requests=3_000_000,
    retry_rate=0.03,
    quality_gate_pass_rate=0.95,
    repair_cost_per_failure=0.002,
    engineering_hours_per_month=8,
    engineer_hourly_cost=100,
)

# ─── Part 2: Multi-Source Architecture ────────────────────────────────────────

# Cresta Multi-LoRA comparison (line 149, 224): contact center at scale
PART2_CRESTA = WorkloadProfile(
    avg_input_tokens=800,
    avg_output_tokens=400,
    monthly_requests=3_000_000,
    retry_rate=0.03,
    quality_gate_pass_rate=0.95,
    repair_cost_per_failure=0.002,
    engineering_hours_per_month=8,
    engineer_hourly_cost=100,
)

# ─── Part 5: The Staged Playbook ─────────────────────────────────────────────

# Stage 0: 200K requests (line 481)
PART5_STAGE0 = replace(PART0_SAAS, monthly_requests=200_000)

# Stage 1: 2M requests (line 498) — all on GPT-5.5 before split
PART5_STAGE1 = replace(PART0_SAAS, monthly_requests=2_000_000)

# Stage 1: 70/30 split — GPT portion (1.4M requests)
PART5_STAGE1_GPT = replace(PART0_SAAS, monthly_requests=1_400_000)

# Stage 1: 70/30 split — Together portion (600K requests)
PART5_STAGE1_TOG = replace(PART0_SAAS, monthly_requests=600_000)

# Stage 2: 10M requests (line 515)
PART5_STAGE2 = replace(PART0_SAAS, monthly_requests=10_000_000)
