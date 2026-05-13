# ABOUTME: Core LCPR (Loaded Cost Per Result) calculation engine.
# ABOUTME: Computes true cost per successful result across deployment modes.

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


@dataclass(frozen=True)
class GoodputRequest:
    """A single request's metrics for goodput analysis."""

    ttft_ms: float  # time to first token in milliseconds
    tpot_ms: float  # time per output token in milliseconds
    output_tokens: int  # output tokens generated
    quality_pass: bool  # whether the output passed the quality gate
    cost: float  # total cost for this request


@dataclass(frozen=True)
class GoodputResult:
    """Result of a goodput frontier test."""

    total_requests: int
    accepted_requests: int  # requests meeting ALL gates (latency + quality)
    goodput_rate: float  # accepted requests per second
    cost_per_accepted: float  # total cost / accepted requests
    total_cost: float
    ttft_p99_ms: float
    tpot_p99_ms: float
    quality_pass_rate: float
    latency_pass_rate: float  # fraction meeting latency SLOs


def compute_goodput(
    requests: list[GoodputRequest],
    duration_seconds: float,
    ttft_slo_ms: float,
    tpot_slo_ms: float,
) -> GoodputResult:
    """Compute goodput from per-request metrics.

    Goodput = count(requests meeting ALL gates) / duration.
    Cost per accepted = sum(ALL costs) / count(accepted requests).
    Derivation 5 formula.
    """
    if not requests:
        raise ValueError("requests must not be empty")
    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be > 0")

    total = len(requests)
    total_cost = sum(r.cost for r in requests)

    # Latency + quality gates
    accepted = [
        r for r in requests
        if r.ttft_ms <= ttft_slo_ms
        and r.tpot_ms <= tpot_slo_ms
        and r.quality_pass
    ]
    latency_passing = [
        r for r in requests
        if r.ttft_ms <= ttft_slo_ms and r.tpot_ms <= tpot_slo_ms
    ]
    quality_passing = [r for r in requests if r.quality_pass]

    n_accepted = len(accepted)
    if n_accepted == 0:
        return GoodputResult(
            total_requests=total,
            accepted_requests=0,
            goodput_rate=0.0,
            cost_per_accepted=float("inf"),
            total_cost=total_cost,
            ttft_p99_ms=_percentile([r.ttft_ms for r in requests], 0.99),
            tpot_p99_ms=_percentile([r.tpot_ms for r in requests], 0.99),
            quality_pass_rate=len(quality_passing) / total,
            latency_pass_rate=len(latency_passing) / total,
        )

    return GoodputResult(
        total_requests=total,
        accepted_requests=n_accepted,
        goodput_rate=n_accepted / duration_seconds,
        cost_per_accepted=total_cost / n_accepted,
        total_cost=total_cost,
        ttft_p99_ms=_percentile([r.ttft_ms for r in requests], 0.99),
        tpot_p99_ms=_percentile([r.tpot_ms for r in requests], 0.99),
        quality_pass_rate=len(quality_passing) / total,
        latency_pass_rate=len(latency_passing) / total,
    )


def _percentile(values: list[float], p: float) -> float:
    """Compute the p-th percentile of a list of values."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = p * (len(sorted_vals) - 1)
    lower = int(idx)
    upper = min(lower + 1, len(sorted_vals) - 1)
    frac = idx - lower
    return sorted_vals[lower] * (1 - frac) + sorted_vals[upper] * frac


@dataclass(frozen=True)
class TraceToMarginResult:
    """Result of a trace-to-margin reconciliation (Derivation 6)."""

    trace_cost: float  # C_trace
    invoice_amount: float  # C_invoice
    delta: float  # invoice - trace
    eval_cost: float
    human_cost: float
    ops_cost: float
    total_loaded_cost: float  # numerator of LCPR
    accepted_units: int
    lcpr: float  # total_loaded_cost / accepted_units
    revenue: float
    gross_margin: float  # revenue - total_loaded_cost
    gross_margin_pct: float  # gross_margin / revenue
    naive_cost_per_unit: float  # trace_cost / total_attempts
    lcpr_to_naive_ratio: float  # lcpr / naive_cost_per_unit


def compute_trace_to_margin(
    trace_cost: float,
    invoice_amount: float,
    eval_cost: float,
    human_cost: float,
    ops_cost: float,
    total_attempts: int,
    accepted_units: int,
    revenue_per_unit: float,
) -> TraceToMarginResult:
    """Compute trace-to-margin reconciliation.

    LCPR = (C_trace + delta + eval + human + ops) / accepted_units
    Derivation 6 formula.
    """
    if accepted_units <= 0:
        raise ValueError("accepted_units must be > 0")
    if total_attempts <= 0:
        raise ValueError("total_attempts must be > 0")

    delta = invoice_amount - trace_cost
    total_loaded = trace_cost + delta + eval_cost + human_cost + ops_cost
    lcpr = total_loaded / accepted_units
    revenue = revenue_per_unit * accepted_units
    gross_margin = revenue - total_loaded
    gross_margin_pct = gross_margin / revenue if revenue > 0 else 0.0
    naive = trace_cost / total_attempts

    return TraceToMarginResult(
        trace_cost=trace_cost,
        invoice_amount=invoice_amount,
        delta=delta,
        eval_cost=eval_cost,
        human_cost=human_cost,
        ops_cost=ops_cost,
        total_loaded_cost=total_loaded,
        accepted_units=accepted_units,
        lcpr=lcpr,
        revenue=revenue,
        gross_margin=gross_margin,
        gross_margin_pct=gross_margin_pct,
        naive_cost_per_unit=naive,
        lcpr_to_naive_ratio=lcpr / naive if naive > 0 else float("inf"),
    )


@dataclass(frozen=True)
class KVSizingResult:
    """Result of a KV cache sizing analysis (Derivation 2)."""

    kv_bytes_per_token: float          # bytes per token per sequence
    max_live_sequences: int            # at given context length
    total_kv_memory_per_seq: float     # kv_bytes_per_token * resident_tokens
    context_length_at_weight_parity: int  # where KV for one seq = weight memory (0 if not provided)


def compute_kv_sizing(
    n_layers: int,
    n_kv_heads: int,
    head_dim: int,
    element_bytes: int,
    kv_pool_bytes: float,
    resident_tokens: int,
    headroom_fraction: float = 0.1,
    weight_bytes: float = 0.0,
) -> KVSizingResult:
    """Compute KV cache memory sizing for a transformer model.

    KV bytes per token = 2 * n_layers * n_kv_heads * head_dim * element_bytes
    Max live sequences = floor(usable_pool / (kv_bytes_per_token * resident_tokens))
    Derivation 2 formula.
    """
    if n_layers <= 0:
        raise ValueError("n_layers must be > 0")
    if n_kv_heads <= 0:
        raise ValueError("n_kv_heads must be > 0")
    if kv_pool_bytes <= 0:
        raise ValueError("kv_pool_bytes must be > 0")

    kv_bytes_per_token = 2 * n_layers * n_kv_heads * head_dim * element_bytes
    total_kv_memory_per_seq = kv_bytes_per_token * resident_tokens
    usable_pool = kv_pool_bytes * (1 - headroom_fraction)

    if total_kv_memory_per_seq > 0:
        max_live_sequences = int(usable_pool // total_kv_memory_per_seq)
    else:
        max_live_sequences = 0

    if weight_bytes > 0 and kv_bytes_per_token > 0:
        context_length_at_weight_parity = int(weight_bytes / kv_bytes_per_token)
    else:
        context_length_at_weight_parity = 0

    return KVSizingResult(
        kv_bytes_per_token=kv_bytes_per_token,
        max_live_sequences=max_live_sequences,
        total_kv_memory_per_seq=total_kv_memory_per_seq,
        context_length_at_weight_parity=context_length_at_weight_parity,
    )


@dataclass(frozen=True)
class CacheBreakEvenResult:
    """Result of a cache break-even analysis (Derivation 3)."""

    prefix_tokens: int
    write_price_per_token: float      # per-token (not per-M)
    read_price_per_token: float       # per-token
    uncached_price_per_token: float   # per-token
    break_even_requests: float        # N where caching becomes cheaper (can be float)
    savings_at_n: dict[int, float]    # savings in USD at various N values
    storage_cost: float               # total storage cost for the retention period


def compute_cache_break_even(
    prefix_tokens: int,
    uncached_input_price_per_m: float,
    cache_write_price_per_m: float,
    cache_read_price_per_m: float,
    storage_price_per_m_hour: float = 0.0,
    storage_hours: float = 0.0,
) -> CacheBreakEvenResult:
    """Compute cache break-even point for prompt caching.

    N_break_even = (p_write - p_read + H * p_storage) / (p_in - p_read)
    Derivation 3 formula.
    """
    if prefix_tokens < 0:
        raise ValueError("prefix_tokens must be >= 0")

    # Convert per-million prices to per-token prices
    p_in = uncached_input_price_per_m / 1_000_000
    p_write = cache_write_price_per_m / 1_000_000
    p_read = cache_read_price_per_m / 1_000_000
    p_storage = storage_price_per_m_hour / 1_000_000

    # Storage cost for the retention period (per token)
    storage_cost_per_token = p_storage * storage_hours
    storage_cost = storage_cost_per_token * prefix_tokens

    # Break-even formula: N = (p_write - p_read + H*p_storage) / (p_in - p_read)
    denominator = p_in - p_read
    if denominator == 0:
        break_even_requests = float("inf")
    else:
        break_even_requests = (p_write - p_read + storage_cost_per_token) / denominator

    # Compute savings at various N values
    savings_at_n: dict[int, float] = {}
    for n in (1, 5, 10, 100):
        c_no_cache = prefix_tokens * n * p_in
        c_cache = prefix_tokens * (1 * p_write + (n - 1) * p_read) + storage_cost
        savings_at_n[n] = c_no_cache - c_cache

    return CacheBreakEvenResult(
        prefix_tokens=prefix_tokens,
        write_price_per_token=p_write,
        read_price_per_token=p_read,
        uncached_price_per_token=p_in,
        break_even_requests=break_even_requests,
        savings_at_n=savings_at_n,
        storage_cost=storage_cost,
    )


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
