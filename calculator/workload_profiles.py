# ABOUTME: Pre-built workload profile templates for common inference use cases.
# ABOUTME: Profiles: SaaS chat, code completion, batch processing, voice agent, RAG pipeline.

from calculator.lcpr import WorkloadProfile

PROFILES: dict[str, WorkloadProfile] = {
    "saas_chat": WorkloadProfile(
        avg_input_tokens=800,
        avg_output_tokens=400,
        monthly_requests=500_000,
        retry_rate=0.03,
        quality_gate_pass_rate=0.95,
        repair_cost_per_failure=0.002,
        engineering_hours_per_month=8,
        engineer_hourly_cost=100,
    ),
    "code_completion": WorkloadProfile(
        avg_input_tokens=2000,
        avg_output_tokens=300,
        monthly_requests=2_000_000,
        retry_rate=0.02,
        quality_gate_pass_rate=0.92,
        repair_cost_per_failure=0.002,
        engineering_hours_per_month=12,
        engineer_hourly_cost=120,
    ),
    "batch_processing": WorkloadProfile(
        avg_input_tokens=3000,
        avg_output_tokens=1000,
        monthly_requests=1_000_000,
        retry_rate=0.01,
        quality_gate_pass_rate=0.98,
        repair_cost_per_failure=0.002,
        engineering_hours_per_month=4,
        engineer_hourly_cost=100,
    ),
    "voice_agent": WorkloadProfile(
        avg_input_tokens=200,
        avg_output_tokens=150,
        monthly_requests=3_000_000,
        retry_rate=0.05,
        quality_gate_pass_rate=0.90,
        repair_cost_per_failure=0.003,
        engineering_hours_per_month=16,
        engineer_hourly_cost=110,
    ),
    "rag_pipeline": WorkloadProfile(
        avg_input_tokens=4000,
        avg_output_tokens=600,
        monthly_requests=800_000,
        retry_rate=0.04,
        quality_gate_pass_rate=0.93,
        repair_cost_per_failure=0.002,
        engineering_hours_per_month=10,
        engineer_hourly_cost=100,
    ),
}


def list_profiles() -> list[str]:
    """Return names of all available profiles."""
    return list(PROFILES.keys())


def get_profile(name: str) -> WorkloadProfile:
    """Get a workload profile by name. Raises KeyError if not found."""
    return PROFILES[name]
