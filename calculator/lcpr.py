# ABOUTME: Core LCPR (Loaded Cost Per Request) calculation engine.
# ABOUTME: Computes true cost per successful request across deployment modes.

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from pathlib import Path

import yaml

# Time constants for cost calculations
HOURS_PER_DAY = 24
DAYS_PER_MONTH = 30
SECONDS_PER_DAY = 86_400
HOURS_PER_MONTH = HOURS_PER_DAY * DAYS_PER_MONTH  # 720
SECONDS_PER_MONTH = SECONDS_PER_DAY * DAYS_PER_MONTH  # 2_592_000


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
    cache_hit_rate: float = 0.0  # 0.0 to 1.0 — fraction of input tokens served from cache
    batch_eligible_fraction: float = 0.0  # 0.0 to 1.0 — fraction of requests eligible for batch
    prefill_efficiency: float = 0.0
    # 0.0 to 1.0 — fraction of prefill (input) compute that displaces decode
    # (output) throughput on dedicated GPUs.  Only meaningful for long-context
    # workloads (>8 K input tokens) where prefill occupies a significant share
    # of GPU cycles.  Typical values:
    #   0.0        — chat / short prompts (prefill is negligible)
    #   0.05-0.15  — RAG extraction (moderate context windows)
    #   0.20+      — summarization / long-document QA (prefill-dominated)

    def __post_init__(self):
        if self.avg_input_tokens < 0:
            raise ValueError("avg_input_tokens must be >= 0")
        if self.avg_output_tokens < 0:
            raise ValueError("avg_output_tokens must be >= 0")
        if self.monthly_requests < 0:
            raise ValueError("monthly_requests must be >= 0")
        for field_name in (
            "retry_rate", "quality_gate_pass_rate", "cache_hit_rate",
            "batch_eligible_fraction", "prefill_efficiency",
        ):
            value = getattr(self, field_name)
            if not (0.0 <= value <= 1.0):
                raise ValueError(f"{field_name} must be between 0.0 and 1.0, got {value}")
        if self.repair_cost_per_failure < 0:
            raise ValueError("repair_cost_per_failure must be >= 0")
        if self.engineering_hours_per_month < 0:
            raise ValueError("engineering_hours_per_month must be >= 0")
        if self.engineer_hourly_cost < 0:
            raise ValueError("engineer_hourly_cost must be >= 0")


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

    # Cached input pricing
    cached_input_rate_per_m: float = 0.0  # $/M cached input tokens

    # Batch pricing
    batch_input_rate_per_m: float = 0.0  # $/M batch input tokens
    batch_output_rate_per_m: float = 0.0  # $/M batch output tokens

    # Model quality relative to frontier (1.0 = frontier, <1.0 = lower quality).
    # Adjusts effective quality_gate_pass_rate: effective = profile_rate * quality_score.
    quality_score: float = 1.0


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

    # Capacity-aware fields
    break_even_feasible: bool = True  # False when effective dedicated $/M > serverless rate
    effective_cost_per_m: float = 0.0  # $/M output tokens at stated utilization
    required_utilization: float = 0.0  # utilization needed for break-even on one GPU
    effective_capacity_tokens_per_day: float = 0.0  # max daily tokens at stated utilization


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
    # Adjust quality gate for model quality score
    if pricing.quality_score <= 0:
        raise ValueError("quality_score must be > 0")
    effective_profile = profile
    if pricing.quality_score < 1.0:
        effective_gate = profile.quality_gate_pass_rate * pricing.quality_score
        effective_profile = replace(profile, quality_gate_pass_rate=effective_gate)

    if pricing.deployment_mode == "dedicated":
        return _compute_dedicated_lcpr(effective_profile, pricing)

    return _compute_token_based_lcpr(effective_profile, pricing)


def _compute_token_based_lcpr(profile: WorkloadProfile, pricing: ProviderPricing) -> LCPRResult:
    """LCPR for per-token pricing (closed API, serverless)."""
    # Base cost per request (token cost only)
    if profile.cache_hit_rate > 0 and pricing.cached_input_rate_per_m > 0:
        cached_input = profile.avg_input_tokens * profile.cache_hit_rate
        uncached_input = profile.avg_input_tokens * (1 - profile.cache_hit_rate)
        input_cost = (uncached_input * pricing.input_rate_per_m / 1_000_000 +
                      cached_input * pricing.cached_input_rate_per_m / 1_000_000)
    else:
        input_cost = profile.avg_input_tokens * pricing.input_rate_per_m / 1_000_000
    output_cost = profile.avg_output_tokens * pricing.output_rate_per_m / 1_000_000

    # Blend batch pricing if applicable
    if profile.batch_eligible_fraction > 0 and pricing.batch_input_rate_per_m > 0:
        frac = profile.batch_eligible_fraction
        batch_input_cost = profile.avg_input_tokens * pricing.batch_input_rate_per_m / 1_000_000
        batch_output_cost = profile.avg_output_tokens * pricing.batch_output_rate_per_m / 1_000_000
        input_cost = input_cost * (1 - frac) + batch_input_cost * frac
        output_cost = output_cost * (1 - frac) + batch_output_cost * frac

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
        raise ValueError("quality_gate_pass_rate must be > 0: zero successful requests is undefined")

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
    monthly_gpu_cost = pricing.gpu_hourly_rate * HOURS_PER_MONTH

    # Effective throughput with utilization
    effective_tps = pricing.throughput_tps * pricing.utilization
    if effective_tps <= 0:
        raise ValueError("effective throughput must be > 0: check throughput_tps and utilization")

    # Monthly token capacity
    monthly_token_capacity = effective_tps * SECONDS_PER_MONTH

    # Total output tokens needed (including retries)
    total_output_tokens = (
        profile.avg_output_tokens * profile.monthly_requests * (1 + profile.retry_rate)
    )
    if profile.prefill_efficiency > 0:
        total_input_tokens = (
            profile.avg_input_tokens * profile.monthly_requests * (1 + profile.retry_rate)
        )
        total_output_tokens += total_input_tokens * profile.prefill_efficiency

    # Number of GPUs needed (at least 1)
    gpus_needed = max(1, total_output_tokens / monthly_token_capacity)
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
        raise ValueError("quality_gate_pass_rate must be > 0: zero successful requests is undefined")

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

    Returns a capacity-aware result that reports whether break-even is
    feasible at the stated utilization. When the effective dedicated $/M
    exceeds the serverless rate, no amount of volume makes dedicated
    cheaper on a single GPU — break_even_feasible will be False.
    """
    daily_gpu_cost = dedicated.gpu_hourly_rate * HOURS_PER_DAY
    serverless_rate_per_token = serverless.output_rate_per_m / 1_000_000

    utilization = dedicated.utilization if dedicated.utilization > 0 else 0.40
    effective_tps = dedicated.throughput_tps * utilization
    max_daily_tokens = effective_tps * SECONDS_PER_DAY
    max_daily_tokens_full = dedicated.throughput_tps * SECONDS_PER_DAY

    # Effective cost per million output tokens at stated utilization
    if max_daily_tokens > 0:
        effective_cost_per_m = daily_gpu_cost / (max_daily_tokens / 1_000_000)
    else:
        effective_cost_per_m = float("inf")

    # Required utilization: the utilization at which dedicated $/M equals serverless $/M
    if max_daily_tokens_full > 0 and serverless_rate_per_token > 0:
        theoretical_break_even = daily_gpu_cost / serverless_rate_per_token
        required_utilization = theoretical_break_even / max_daily_tokens_full
    else:
        required_utilization = float("inf")
        theoretical_break_even = float("inf")

    if serverless_rate_per_token <= 0:
        return BreakEvenResult(
            serverless_name=serverless.name,
            dedicated_name=dedicated.name,
            break_even_daily_output_tokens=float("inf"),
            serverless_daily_cost_at_break_even=0,
            dedicated_daily_cost=daily_gpu_cost,
            break_even_feasible=False,
            effective_cost_per_m=effective_cost_per_m,
            required_utilization=float("inf"),
            effective_capacity_tokens_per_day=max_daily_tokens,
        )

    # Check if dedicated is economical at the stated utilization
    feasible = effective_cost_per_m < serverless.output_rate_per_m

    if feasible:
        # Break-even volume: daily tokens where serverless cost = GPU cost
        break_even_tokens = theoretical_break_even
        serverless_cost_at_break_even = break_even_tokens * serverless_rate_per_token
    else:
        # No break-even at this utilization — dedicated always costs more per token
        break_even_tokens = float("inf")
        serverless_cost_at_break_even = float("inf")

    return BreakEvenResult(
        serverless_name=serverless.name,
        dedicated_name=dedicated.name,
        break_even_daily_output_tokens=break_even_tokens,
        serverless_daily_cost_at_break_even=serverless_cost_at_break_even,
        dedicated_daily_cost=daily_gpu_cost,
        break_even_feasible=feasible,
        effective_cost_per_m=effective_cost_per_m,
        required_utilization=required_utilization,
        effective_capacity_tokens_per_day=max_daily_tokens,
    )


def _safe_rate(value: object, default: float = 0.0) -> float:
    """Convert a YAML value to a float rate, treating None as default."""
    if value is None:
        return default
    return float(value)


def _validate_rate(value: float, context: str) -> None:
    """Raise ValueError if a rate is negative."""
    if value < 0:
        raise ValueError(f"negative rate in {context}: {value}")


def load_provider_pricing(yaml_path: Path) -> list[ProviderPricing]:
    """Load provider pricing from YAML file into ProviderPricing objects."""
    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    if data is None:
        return []

    providers: list[ProviderPricing] = []

    def _load_token_model(provider_data: dict, model_data: dict, mode: str) -> ProviderPricing:
        provider_name = provider_data.get("name")
        model_name = model_data.get("name")
        if not model_name:
            raise ValueError(f"missing 'name' field in model under {provider_name}")

        input_rate = _safe_rate(model_data.get("input_rate", 0))
        output_rate = _safe_rate(model_data.get("output_rate", 0))
        cached = _safe_rate(model_data.get("cached_input_rate", 0))
        batch_in = _safe_rate(model_data.get("batch_input_rate", 0))
        batch_out = _safe_rate(model_data.get("batch_output_rate", 0))

        context = f"{provider_name} {model_name}"
        _validate_rate(input_rate, context)
        _validate_rate(output_rate, context)
        _validate_rate(cached, context)
        _validate_rate(batch_in, context)
        _validate_rate(batch_out, context)

        return ProviderPricing(
            name=f"{provider_name} {model_name}",
            input_rate_per_m=input_rate,
            output_rate_per_m=output_rate,
            deployment_mode=mode,
            cached_input_rate_per_m=cached,
            batch_input_rate_per_m=batch_in,
            batch_output_rate_per_m=batch_out,
        )

    # Load closed APIs
    for provider_key, provider_data in data.get("closed_apis", {}).items():
        for model_key, model_data in provider_data.get("models", {}).items():
            providers.append(_load_token_model(provider_data, model_data, "closed_api"))

    # Load serverless open
    for provider_key, provider_data in data.get("serverless_open", {}).items():
        for model_key, model_data in provider_data.get("models", {}).items():
            providers.append(_load_token_model(provider_data, model_data, "serverless_open"))

    # Load dedicated GPU
    throughput = data.get("throughput_assumptions", {}).get("h100_70b_fp8", {})
    default_tps = throughput.get("theoretical_max_tps", 1500)
    default_util = throughput.get("realistic_utilization", 0.40)

    for provider_key, provider_data in data.get("dedicated_gpu", {}).items():
        for gpu_key, gpu_data in provider_data.get("gpus", {}).items():
            gpu_name = gpu_data.get("name")
            if not gpu_name:
                raise ValueError(f"missing 'name' field in GPU under {provider_data.get('name')}")

            hourly = _safe_rate(gpu_data.get("hourly_rate", 0))
            # For multi-GPU instances, use per_gpu_hourly if available
            if "per_gpu_hourly" in gpu_data:
                hourly = _safe_rate(gpu_data["per_gpu_hourly"])

            _validate_rate(hourly, f"{provider_data.get('name')} {gpu_name}")

            providers.append(
                ProviderPricing(
                    name=f"{provider_data['name']} {gpu_name}",
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
