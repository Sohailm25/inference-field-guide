# ABOUTME: Core LCPR (Loaded Cost Per Request) calculation engine.
# ABOUTME: Computes true cost per successful request across deployment modes.

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import yaml


@dataclass(frozen=True)
class WorkloadProfile:
    """Describes a workload's characteristics for LCPR calculation."""

    avg_input_tokens: int
    avg_output_tokens: int
    monthly_requests: int
    retry_rate: float  # 0.0 to 1.0 — fraction of requests that are retried
    quality_gate_pass_rate: float  # 0.0 to 1.0 — fraction that pass quality/schema gates
    repair_cost_per_failure: float  # $ cost to re-prompt a failed request
    engineering_hours_per_month: float
    engineer_hourly_cost: float


@dataclass(frozen=True)
class ProviderPricing:
    """Pricing for a single provider/model combination."""

    name: str
    input_rate_per_m: float  # $/M input tokens
    output_rate_per_m: float  # $/M output tokens
    deployment_mode: str  # "closed_api", "serverless_open", "dedicated"

    # Dedicated-specific fields
    gpu_hourly_rate: float = 0.0  # $/hr per GPU
    throughput_tps: int = 0  # theoretical max tokens/sec
    utilization: float = 0.0  # realistic utilization fraction (0.0 to 1.0)


@dataclass(frozen=True)
class LCPRResult:
    """Result of an LCPR calculation for one provider."""

    provider_name: str
    deployment_mode: str
    lcpr: float  # $ per successful request
    cost_per_1k_requests: float  # $ per 1,000 successful requests
    monthly_cost: float  # total monthly cost


@dataclass(frozen=True)
class BreakEvenResult:
    """Result of a break-even analysis between two deployment modes."""

    serverless_name: str
    dedicated_name: str
    break_even_daily_output_tokens: float  # daily output tokens where dedicated wins
    serverless_daily_cost_at_break_even: float
    dedicated_daily_cost: float


def compute_lcpr(profile: WorkloadProfile, pricing: ProviderPricing) -> LCPRResult:
    """Compute LCPR for a workload on a given provider.

    LCPR formula:
        LCPR = (token_cost + retry_cost + repair_cost + engineering_cost)
               / successful_requests

    Where:
        token_cost = (input_tokens * input_rate + output_tokens * output_rate) * total_attempts
        retry_cost = retry_rate * base_token_cost (already in total_attempts)
        repair_cost = failed_requests * repair_cost_per_failure
        engineering_cost = monthly engineering hours * hourly rate
        successful_requests = monthly_requests * quality_gate_pass_rate
    """
    if pricing.deployment_mode == "dedicated":
        return _compute_dedicated_lcpr(profile, pricing)

    return _compute_token_based_lcpr(profile, pricing)


def _compute_token_based_lcpr(profile: WorkloadProfile, pricing: ProviderPricing) -> LCPRResult:
    """LCPR for per-token pricing (closed API, serverless)."""
    # Base cost per request (token cost only)
    input_cost = profile.avg_input_tokens * pricing.input_rate_per_m / 1_000_000
    output_cost = profile.avg_output_tokens * pricing.output_rate_per_m / 1_000_000
    base_cost_per_request = input_cost + output_cost

    # Total attempts = original requests + retries
    total_attempts = profile.monthly_requests * (1 + profile.retry_rate)
    total_token_cost = base_cost_per_request * total_attempts

    # Repair cost for requests that fail quality/schema gates
    failed_requests = profile.monthly_requests * (1 - profile.quality_gate_pass_rate)
    total_repair_cost = failed_requests * profile.repair_cost_per_failure

    # Engineering cost
    total_engineering_cost = profile.engineering_hours_per_month * profile.engineer_hourly_cost

    # Total monthly cost
    monthly_cost = total_token_cost + total_repair_cost + total_engineering_cost

    # Successful requests
    successful_requests = profile.monthly_requests * profile.quality_gate_pass_rate
    if successful_requests == 0:
        successful_requests = 1  # avoid division by zero

    lcpr = monthly_cost / successful_requests

    return LCPRResult(
        provider_name=pricing.name,
        deployment_mode=pricing.deployment_mode,
        lcpr=lcpr,
        cost_per_1k_requests=lcpr * 1000,
        monthly_cost=monthly_cost,
    )


def _compute_dedicated_lcpr(profile: WorkloadProfile, pricing: ProviderPricing) -> LCPRResult:
    """LCPR for dedicated GPU pricing."""
    # Monthly GPU cost: assume 24/7 provisioning
    monthly_gpu_cost = pricing.gpu_hourly_rate * 24 * 30

    # Effective throughput with utilization
    effective_tps = pricing.throughput_tps * pricing.utilization
    if effective_tps <= 0:
        effective_tps = 1  # avoid division by zero

    # Monthly token capacity
    monthly_token_capacity = effective_tps * 3600 * 24 * 30

    # Total output tokens needed (including retries)
    total_output_tokens = (
        profile.avg_output_tokens * profile.monthly_requests * (1 + profile.retry_rate)
    )

    # Number of GPUs needed (at least 1)
    gpus_needed = max(1, total_output_tokens / monthly_token_capacity)
    # Round up to whole GPUs
    import math

    gpus_needed = math.ceil(gpus_needed)

    total_gpu_cost = monthly_gpu_cost * gpus_needed

    # Repair cost
    failed_requests = profile.monthly_requests * (1 - profile.quality_gate_pass_rate)
    total_repair_cost = failed_requests * profile.repair_cost_per_failure

    # Engineering cost (dedicated typically higher)
    total_engineering_cost = profile.engineering_hours_per_month * profile.engineer_hourly_cost

    monthly_cost = total_gpu_cost + total_repair_cost + total_engineering_cost

    successful_requests = profile.monthly_requests * profile.quality_gate_pass_rate
    if successful_requests == 0:
        successful_requests = 1

    lcpr = monthly_cost / successful_requests

    return LCPRResult(
        provider_name=pricing.name,
        deployment_mode=pricing.deployment_mode,
        lcpr=lcpr,
        cost_per_1k_requests=lcpr * 1000,
        monthly_cost=monthly_cost,
    )


def compute_break_even(serverless: ProviderPricing, dedicated: ProviderPricing) -> BreakEvenResult:
    """Compute the daily output token volume where dedicated becomes cheaper.

    Break-even = (gpu_hourly_rate * 24) / serverless_output_rate_per_token

    Adjusted for utilization: effective break-even is higher because real
    workloads don't saturate GPUs.
    """
    # Daily GPU cost
    daily_gpu_cost = dedicated.gpu_hourly_rate * 24

    # Serverless cost per output token
    serverless_rate_per_token = serverless.output_rate_per_m / 1_000_000

    if serverless_rate_per_token <= 0:
        # Can't break even against free serverless
        return BreakEvenResult(
            serverless_name=serverless.name,
            dedicated_name=dedicated.name,
            break_even_daily_output_tokens=float("inf"),
            serverless_daily_cost_at_break_even=0,
            dedicated_daily_cost=daily_gpu_cost,
        )

    # Theoretical break-even (assuming 100% utilization)
    theoretical_break_even = daily_gpu_cost / serverless_rate_per_token

    # Adjusted for real-world utilization
    utilization = dedicated.utilization if dedicated.utilization > 0 else 0.40
    effective_tps = dedicated.throughput_tps * utilization
    max_daily_tokens = effective_tps * 3600 * 24

    # If GPU can't even produce enough tokens at this utilization,
    # the break-even is at theoretical / utilization
    if max_daily_tokens < theoretical_break_even:
        # Need multiple GPUs — break-even scales accordingly
        adjusted_break_even = theoretical_break_even / utilization
    else:
        adjusted_break_even = theoretical_break_even

    serverless_cost_at_break_even = adjusted_break_even * serverless_rate_per_token

    return BreakEvenResult(
        serverless_name=serverless.name,
        dedicated_name=dedicated.name,
        break_even_daily_output_tokens=adjusted_break_even,
        serverless_daily_cost_at_break_even=serverless_cost_at_break_even,
        dedicated_daily_cost=daily_gpu_cost,
    )


def load_provider_pricing(yaml_path: Path) -> list[ProviderPricing]:
    """Load provider pricing from YAML file into ProviderPricing objects."""
    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    providers: list[ProviderPricing] = []

    # Load closed APIs
    for provider_key, provider_data in data.get("closed_apis", {}).items():
        for model_key, model_data in provider_data.get("models", {}).items():
            providers.append(
                ProviderPricing(
                    name=f"{provider_data['name']} {model_data['name']}",
                    input_rate_per_m=model_data["input_rate"],
                    output_rate_per_m=model_data["output_rate"],
                    deployment_mode="closed_api",
                )
            )

    # Load serverless open
    for provider_key, provider_data in data.get("serverless_open", {}).items():
        for model_key, model_data in provider_data.get("models", {}).items():
            providers.append(
                ProviderPricing(
                    name=f"{provider_data['name']} {model_data['name']}",
                    input_rate_per_m=model_data.get("input_rate", 0),
                    output_rate_per_m=model_data.get("output_rate", 0),
                    deployment_mode="serverless_open",
                )
            )

    # Load dedicated GPU
    throughput = data.get("throughput_assumptions", {}).get("h100_70b_fp8", {})
    default_tps = throughput.get("theoretical_max_tps", 1500)
    default_util = throughput.get("realistic_utilization", 0.40)

    for provider_key, provider_data in data.get("dedicated_gpu", {}).items():
        for gpu_key, gpu_data in provider_data.get("gpus", {}).items():
            hourly = gpu_data.get("hourly_rate", 0)
            # For multi-GPU instances, use per_gpu_hourly if available
            if "per_gpu_hourly" in gpu_data:
                hourly = gpu_data["per_gpu_hourly"]

            providers.append(
                ProviderPricing(
                    name=f"{provider_data['name']} {gpu_data['name']}",
                    input_rate_per_m=0.0,
                    output_rate_per_m=0.0,
                    deployment_mode="dedicated",
                    gpu_hourly_rate=hourly,
                    throughput_tps=default_tps,
                    utilization=default_util,
                )
            )

    return providers


class LCPRCalculator:
    """High-level calculator that compares LCPR across all providers."""

    def __init__(self, pricing_path: Path):
        self.providers = load_provider_pricing(pricing_path)

    def compare(self, profile: WorkloadProfile) -> list[LCPRResult]:
        """Compare LCPR across all loaded providers, sorted by LCPR ascending."""
        results = [compute_lcpr(profile, p) for p in self.providers]
        results.sort(key=lambda r: r.lcpr)
        return results

    def sensitivity(
        self,
        profile: WorkloadProfile,
        vary: str,
        values: list[float],
        provider_name: str | None = None,
    ) -> list[dict]:
        """Run sensitivity analysis varying one parameter.

        Returns list of dicts with the varied parameter value and resulting LCPR
        for each provider (or a specific provider if named).
        """
        if provider_name:
            target_providers = [p for p in self.providers if p.name == provider_name]
        else:
            # Use the cheapest serverless provider as default
            target_providers = [p for p in self.providers if p.deployment_mode == "serverless_open"]
            if target_providers:
                # Pick the one with lowest blended rate
                target_providers = [
                    min(
                        target_providers,
                        key=lambda p: p.input_rate_per_m + p.output_rate_per_m,
                    )
                ]

        if not target_providers:
            target_providers = self.providers[:1]

        provider = target_providers[0]
        results = []

        for val in values:
            modified_profile = replace(profile, **{vary: val})
            result = compute_lcpr(modified_profile, provider)
            results.append(
                {
                    vary: val,
                    "lcpr": result.lcpr,
                    "monthly_cost": result.monthly_cost,
                    "provider": result.provider_name,
                }
            )

        return results
