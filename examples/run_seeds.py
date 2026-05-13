# ABOUTME: Runner script for calculator seed artifacts.
# ABOUTME: Loads YAML seeds, runs through compute_goodput and compute_trace_to_margin, writes output.

"""Run calculator seeds through Goodput Frontier Test and Trace-to-Margin views.

Usage:
    python -m examples.run_seeds [--example NAME]

Outputs JSON artifacts to examples/<name>/output.json for each seed.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

import yaml

from calculator.lcpr import (
    GoodputRequest,
    compute_goodput,
    compute_trace_to_margin,
)


def load_seed(seed_path: Path) -> dict:
    """Load a calculator seed YAML file."""
    with open(seed_path) as f:
        return yaml.safe_load(f)


def run_support_answer(seed: dict) -> dict:
    """Run Example 1: Support Answer Trace-to-Margin."""
    ttm = seed["trace_to_margin"]
    result = compute_trace_to_margin(
        trace_cost=ttm["trace_cost"],
        invoice_amount=ttm["invoice_amount"],
        eval_cost=ttm["eval_cost"],
        human_cost=ttm["human_cost"],
        ops_cost=ttm["ops_cost"],
        total_attempts=ttm["total_attempts"],
        accepted_units=ttm["accepted_units"],
        revenue_per_unit=ttm["revenue_per_unit"],
    )
    return {
        "example": seed["example_name"],
        "views": seed["calculator_views"],
        "trace_to_margin": asdict(result),
    }


def _build_route_requests(route_cfg: dict) -> list[GoodputRequest]:
    """Build GoodputRequest list from route config in benchmark audit seed."""
    gp = route_cfg["goodput_requests"]
    total = gp["total"]
    accepted = gp["accepted_count"]
    quality_count = gp["quality_pass_count"]
    ttft_pass = gp.get("ttft_pass_count", total)
    passing_ttft = gp["passing_ttft_ms"]
    failing_ttft = gp["failing_ttft_ms"]
    passing_tpot = gp["passing_tpot_ms"]
    failing_tpot = gp.get("failing_tpot_ms", passing_tpot)
    cost = gp["cost_per_request"]

    requests = []
    for i in range(total):
        if i < accepted:
            # Pass all gates
            requests.append(GoodputRequest(
                ttft_ms=passing_ttft,
                tpot_ms=passing_tpot,
                output_tokens=200,
                quality_pass=True,
                cost=cost,
            ))
        elif i < quality_count:
            # Pass quality, fail latency
            requests.append(GoodputRequest(
                ttft_ms=failing_ttft,
                tpot_ms=passing_tpot,
                output_tokens=200,
                quality_pass=True,
                cost=cost,
            ))
        elif i < ttft_pass:
            # Pass latency, fail quality
            requests.append(GoodputRequest(
                ttft_ms=passing_ttft,
                tpot_ms=passing_tpot,
                output_tokens=200,
                quality_pass=False,
                cost=cost,
            ))
        else:
            # Fail both
            requests.append(GoodputRequest(
                ttft_ms=failing_ttft,
                tpot_ms=failing_tpot,
                output_tokens=200,
                quality_pass=False,
                cost=cost,
            ))
    return requests


def run_benchmark_audit(seed: dict) -> dict:
    """Run Example 3: Benchmark Audit (Goodput Frontier Test)."""
    wi = seed["workload_identity"]
    ttft_slo = wi["ttft_slo_ms"]
    tpot_slo = wi["tpot_slo_ms"]

    results = {}
    for route_key in ("route_a", "route_b"):
        route_cfg = seed[route_key]
        gp = route_cfg["goodput_requests"]
        requests = _build_route_requests(route_cfg)
        result = compute_goodput(
            requests=requests,
            duration_seconds=gp["duration_seconds"],
            ttft_slo_ms=ttft_slo,
            tpot_slo_ms=tpot_slo,
        )
        results[route_key] = {
            "name": route_cfg["name"],
            "goodput": asdict(result),
        }

    # Determine winners
    a_cpa = results["route_a"]["goodput"]["cost_per_accepted"]
    b_cpa = results["route_b"]["goodput"]["cost_per_accepted"]

    # Naive throughput from benchmark claims (Route A claimed higher tps)
    a_naive_tps = seed["route_a"].get("naive_benchmark", {}).get("throughput_tps", 0)
    b_naive_tps = seed["route_b"].get("naive_benchmark", {}).get("throughput_tps", 0)

    results["analysis"] = {
        "winner_by_naive_throughput": "route_a" if a_naive_tps > b_naive_tps else "route_b",
        "winner_by_goodput_cost": "route_a" if a_cpa < b_cpa else "route_b",
        "reversal": a_naive_tps > b_naive_tps and b_cpa < a_cpa,
    }

    return {
        "example": seed["example_name"],
        "views": seed["calculator_views"],
        "methodology_gaps": seed.get("methodology_gaps", []),
        "routes": results,
    }


def run_coding_agent(seed: dict) -> dict:
    """Run Example 2: Coding Agent Task Lifecycle."""
    totals = seed["task_trace"]["totals"]
    derived = seed["task_trace"]["derived"]
    fleet = seed["fleet"]
    pricing = seed["pricing"]

    # Per-task cost calculation
    uncached_input = totals["input_tokens"] - totals["cache_read_tokens"]
    cached_input = totals["cache_read_tokens"]
    output = totals["output_tokens"]

    input_cost = (uncached_input / 1_000_000) * pricing["input_per_m"]
    cache_read_cost = (cached_input / 1_000_000) * pricing["cache_read_per_m"]
    output_cost = (output / 1_000_000) * pricing["output_per_m"]
    task_inference_cost = input_cost + cache_read_cost + output_cost

    # Without caching comparison
    no_cache_input_cost = (totals["input_tokens"] / 1_000_000) * pricing["input_per_m"]
    no_cache_total = no_cache_input_cost + output_cost
    cache_savings_ratio = no_cache_total / task_inference_cost

    # Fleet-level monthly
    tasks_per_month = fleet["tasks_per_day"] * 30
    accepted_per_month = int(tasks_per_month * fleet["acceptance_rate"])
    monthly_inference = task_inference_cost * tasks_per_month
    lcpr = monthly_inference / accepted_per_month if accepted_per_month > 0 else float("inf")

    # Build goodput requests from fleet data for the goodput view
    gp_cfg = seed["goodput_test"]
    requests = []
    tasks_in_window = int(fleet["tasks_per_day"] / 24)  # tasks per hour
    for i in range(tasks_in_window):
        quality_pass = i < int(tasks_in_window * fleet["acceptance_rate"])
        requests.append(GoodputRequest(
            ttft_ms=2000.0 if quality_pass else 6000.0,
            tpot_ms=60.0,
            output_tokens=totals["output_tokens"],
            quality_pass=quality_pass,
            cost=task_inference_cost,
        ))

    goodput_result = None
    if requests:
        goodput_result = compute_goodput(
            requests=requests,
            duration_seconds=gp_cfg["duration_seconds"],
            ttft_slo_ms=gp_cfg["ttft_slo_ms"],
            tpot_slo_ms=gp_cfg["tpot_slo_ms"],
        )

    return {
        "example": seed["example_name"],
        "views": seed["calculator_views"],
        "task_economics": {
            "input_tokens": totals["input_tokens"],
            "output_tokens": totals["output_tokens"],
            "cache_read_tokens": totals["cache_read_tokens"],
            "cache_hit_rate": derived["cache_hit_rate"],
            "fanout_multiplier": derived["fanout_multiplier"],
            "token_fanout": derived["token_fanout"],
            "per_task_inference_cost": round(task_inference_cost, 4),
            "without_caching_cost": round(no_cache_total, 4),
            "cache_savings_ratio": round(cache_savings_ratio, 2),
        },
        "fleet_economics": {
            "tasks_per_month": tasks_per_month,
            "accepted_per_month": accepted_per_month,
            "monthly_inference_cost": round(monthly_inference, 2),
            "lcpr_per_task": round(lcpr, 4),
        },
        "goodput": asdict(goodput_result) if goodput_result else None,
    }


EXAMPLES = {
    "support-answer": (
        "examples/support-answer.trace-margin.v1/calculator-seed.yaml",
        run_support_answer,
    ),
    "coding-agent": (
        "examples/coding-agent.lifecycle.v1/calculator-seed.yaml",
        run_coding_agent,
    ),
    "benchmark-audit": (
        "examples/support-rag-answer-drafting.audit.v1/calculator-seed.yaml",
        run_benchmark_audit,
    ),
}


def main(example_name: str | None = None):
    """Run one or all examples."""
    root = Path(__file__).parent.parent

    targets = EXAMPLES
    if example_name:
        if example_name not in EXAMPLES:
            print(f"Unknown example: {example_name}")
            print(f"Available: {', '.join(EXAMPLES.keys())}")
            sys.exit(1)
        targets = {example_name: EXAMPLES[example_name]}

    for name, (seed_path, runner) in targets.items():
        full_path = root / seed_path
        print(f"Running {name}...")
        seed = load_seed(full_path)
        output = runner(seed)

        output_path = full_path.parent / "output.json"
        with open(output_path, "w") as f:
            json.dump(output, f, indent=2, default=str)
        print(f"  Output: {output_path}")

    print("Done.")


if __name__ == "__main__":
    example_arg = sys.argv[1] if len(sys.argv) > 1 else None
    main(example_arg)
