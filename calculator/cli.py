# ABOUTME: CLI interface for the LCPR calculator.
# ABOUTME: Provides command-line access to cost analysis, crossover, and sensitivity functions.

from __future__ import annotations

import json
import sys
from dataclasses import fields, replace
from pathlib import Path

import click

from calculator.lcpr import (
    LCPRCalculator,
    WorkloadProfile,
    compute_break_even,
    compute_lcpr,
    load_provider_pricing,
)
from calculator.workload_profiles import get_profile, list_profiles

PRICING_PATH = Path(__file__).parent / "provider_pricing.yaml"

VALID_VARY_FIELDS = {f.name for f in fields(WorkloadProfile)}


def _format_tokens(n: float) -> str:
    """Format large token counts with M/B suffixes."""
    if n >= 1e9:
        return f"{n / 1e9:.1f}B"
    if n >= 1e6:
        return f"{n / 1e6:.1f}M"
    if n >= 1e3:
        return f"{n / 1e3:.0f}K"
    return f"{n:.0f}"


def _format_dollar(n: float) -> str:
    """Format dollar amounts."""
    if n < 0.01:
        return f"${n:.6f}"
    if n < 1:
        return f"${n:.4f}"
    if n < 1000:
        return f"${n:.2f}"
    return f"${n:,.0f}"


@click.group()
def cli():
    """LCPR Calculator — Loaded Cost Per Result analysis for production inference."""
    pass


@cli.command()
def profiles():
    """List available workload profiles."""
    names = list_profiles()
    click.echo("Available workload profiles:\n")
    for name in names:
        p = get_profile(name)
        click.echo(f"  {name}")
        click.echo(f"    Input tokens: {p.avg_input_tokens}  Output tokens: {p.avg_output_tokens}")
        click.echo(f"    Monthly requests: {p.monthly_requests:,}")
        click.echo(
            f"    Retry rate: {p.retry_rate:.0%}  Quality gate: {p.quality_gate_pass_rate:.0%}"
        )
        click.echo()


@cli.command()
@click.option("--profile", "profile_name", default=None, help="Named workload profile")
@click.option("--input-tokens", type=int, default=None, help="Average input tokens per request")
@click.option("--output-tokens", type=int, default=None, help="Average output tokens per request")
@click.option("--monthly-requests", type=int, default=None, help="Monthly request volume")
@click.option("--retry-rate", type=float, default=None, help="Retry rate (0.0-1.0)")
@click.option("--quality-gate", type=float, default=None, help="Quality gate pass rate (0.0-1.0)")
@click.option("--repair-cost", type=float, default=0.002, help="Repair cost per failure ($)")
@click.option("--eng-hours", type=float, default=10, help="Engineering hours per month")
@click.option("--eng-rate", type=float, default=100, help="Engineer hourly cost ($)")
@click.option("--cache-hit-rate", type=float, default=0.0, help="Prompt cache hit rate (0.0-1.0)")
@click.option(
    "--batch-fraction",
    type=float,
    default=0.0,
    help="Fraction eligible for batch pricing (0.0-1.0)",
)
@click.option("--format", "fmt", type=click.Choice(["table", "json"]), default="table")
def compare(profile_name, input_tokens, output_tokens, monthly_requests, retry_rate,
            quality_gate, repair_cost, eng_hours, eng_rate, cache_hit_rate, batch_fraction, fmt):
    """Compare LCPR across all providers for a workload."""
    if profile_name:
        try:
            profile = get_profile(profile_name)
        except KeyError:
            click.echo(f"Error: Unknown profile '{profile_name}'", err=True)
            sys.exit(1)
    elif input_tokens is not None and output_tokens is not None and monthly_requests is not None:
        profile = WorkloadProfile(
            avg_input_tokens=input_tokens,
            avg_output_tokens=output_tokens,
            monthly_requests=monthly_requests,
            retry_rate=retry_rate if retry_rate is not None else 0.03,
            quality_gate_pass_rate=quality_gate if quality_gate is not None else 0.95,
            repair_cost_per_failure=repair_cost,
            engineering_hours_per_month=eng_hours,
            engineer_hourly_cost=eng_rate,
            cache_hit_rate=cache_hit_rate,
            batch_eligible_fraction=batch_fraction,
        )
    else:
        click.echo(
            "Error: Provide --profile or custom params "
            "(--input-tokens, --output-tokens, --monthly-requests)",
            err=True,
        )
        sys.exit(1)

    calc = LCPRCalculator(PRICING_PATH)
    results = calc.compare(profile)

    if fmt == "json":
        data = [
            {
                "provider_name": r.provider_name,
                "deployment_mode": r.deployment_mode,
                "lcpr": round(r.lcpr, 6),
                "cost_per_1k_requests": round(r.cost_per_1k_requests, 4),
                "monthly_cost": round(r.monthly_cost, 2),
            }
            for r in results
        ]
        click.echo(json.dumps(data, indent=2))
        return

    # Table output
    click.echo("\nLCPR Comparison (sorted cheapest first)\n")
    click.echo(f"{'Provider':<40} {'Mode':<16} {'LCPR':>12} {'$/1K req':>12} {'Monthly':>12}")
    click.echo("─" * 94)
    for r in results:
        click.echo(
            f"{r.provider_name:<40} {r.deployment_mode:<16} "
            f"{_format_dollar(r.lcpr):>12} "
            f"{_format_dollar(r.cost_per_1k_requests):>12} "
            f"{_format_dollar(r.monthly_cost):>12}"
        )


@cli.command()
@click.option("--serverless", default=None, help="Serverless provider name (from pricing YAML)")
@click.option("--dedicated", default=None, help="Dedicated provider name (from pricing YAML)")
@click.option("--format", "fmt", type=click.Choice(["table", "json"]), default="table")
def crossover(serverless, dedicated, fmt):
    """Break-even analysis: when does dedicated beat serverless?"""
    providers = load_provider_pricing(PRICING_PATH)

    # Find serverless provider
    serverless_providers = [p for p in providers if p.deployment_mode in ("serverless_open",)]
    dedicated_providers = [p for p in providers if p.deployment_mode == "dedicated"]

    if serverless:
        matches = [p for p in serverless_providers if serverless.lower() in p.name.lower()]
        if not matches:
            click.echo(f"Error: No serverless provider matching '{serverless}'", err=True)
            sys.exit(1)
        sv = matches[0]
    else:
        # Default: cheapest serverless by output rate
        sv = min(serverless_providers, key=lambda p: p.output_rate_per_m)

    if dedicated:
        matches = [p for p in dedicated_providers if dedicated.lower() in p.name.lower()]
        if not matches:
            click.echo(f"Error: No dedicated provider matching '{dedicated}'", err=True)
            sys.exit(1)
        dd = matches[0]
    else:
        # Default: cheapest dedicated by hourly rate
        dd = min(dedicated_providers, key=lambda p: p.gpu_hourly_rate)

    result = compute_break_even(sv, dd)

    if fmt == "json":
        data = {
            "serverless_name": result.serverless_name,
            "dedicated_name": result.dedicated_name,
            "break_even_daily_output_tokens": round(result.break_even_daily_output_tokens, 0),
            "serverless_daily_cost_at_break_even": round(
                result.serverless_daily_cost_at_break_even, 2
            ),
            "dedicated_daily_cost": round(result.dedicated_daily_cost, 2),
        }
        click.echo(json.dumps(data, indent=2))
        return

    # Table output
    be_tokens = _format_tokens(result.break_even_daily_output_tokens)
    be_cost = _format_dollar(result.serverless_daily_cost_at_break_even)
    dd_cost = _format_dollar(result.dedicated_daily_cost)

    click.echo("\nBreak-Even Analysis")
    click.echo(f"  Serverless: {result.serverless_name}")
    click.echo(f"  Dedicated:  {result.dedicated_name}")
    click.echo()
    click.echo(f"  Break-even daily output tokens: {be_tokens}")
    click.echo(f"  Serverless daily cost at break-even: {be_cost}")
    click.echo(f"  Dedicated daily cost (fixed): {dd_cost}")
    click.echo()
    click.echo(f"  Below {be_tokens} tokens/day → stay serverless")
    click.echo(f"  Above {be_tokens} tokens/day → dedicated saves money")


@cli.command()
@click.option("--profile", "profile_name", required=True, help="Named workload profile")
@click.option("--vary", required=True, help="Parameter to vary (e.g. retry_rate)")
@click.option("--values", required=True, help="Comma-separated values to test")
@click.option("--provider", default=None, help="Specific provider name to analyze")
@click.option("--format", "fmt", type=click.Choice(["table", "json"]), default="table")
def sensitivity(profile_name, vary, values, provider, fmt):
    """Sensitivity analysis: how LCPR changes when varying one parameter."""
    if vary not in VALID_VARY_FIELDS:
        click.echo(f"Error: '{vary}' is not a valid WorkloadProfile field.", err=True)
        click.echo(f"Valid fields: {', '.join(sorted(VALID_VARY_FIELDS))}", err=True)
        sys.exit(1)

    try:
        profile = get_profile(profile_name)
    except KeyError:
        click.echo(f"Error: Unknown profile '{profile_name}'", err=True)
        sys.exit(1)

    parsed_values = [float(v.strip()) for v in values.split(",")]

    calc = LCPRCalculator(PRICING_PATH)
    results = calc.sensitivity(profile, vary=vary, values=parsed_values, provider_name=provider)

    if fmt == "json":
        click.echo(json.dumps(results, indent=2))
        return

    # Table output
    click.echo(f"\nSensitivity Analysis: varying {vary}")
    click.echo(f"Provider: {results[0]['provider']}\n")
    click.echo(f"  {vary:<30} {'LCPR':>12} {'Monthly':>12}")
    click.echo("  " + "─" * 56)
    for row in results:
        click.echo(
            f"  {str(row[vary]):<30} "
            f"{_format_dollar(row['lcpr']):>12} "
            f"{_format_dollar(row['monthly_cost']):>12}"
        )


DEFAULT_SWEEP_VOLUMES = [
    10_000, 50_000, 100_000, 250_000, 500_000,
    1_000_000, 2_000_000, 5_000_000, 10_000_000,
]


@cli.command()
@click.option("--profile", "profile_name", required=True, help="Named workload profile")
@click.option(
    "--providers", default=None,
    help="Comma-separated provider name substrings to include",
)
@click.option(
    "--volumes", default=None,
    help="Comma-separated monthly request volumes to sweep",
)
def sweep(profile_name, providers, volumes):
    """Sweep volume vs cost — JSON output for charting (Streamlit)."""
    try:
        base_profile = get_profile(profile_name)
    except KeyError:
        click.echo(f"Error: Unknown profile '{profile_name}'", err=True)
        sys.exit(1)

    all_providers = load_provider_pricing(PRICING_PATH)
    if providers:
        filters = [f.strip().lower() for f in providers.split(",")]
        all_providers = [
            p for p in all_providers
            if any(f in p.name.lower() for f in filters)
        ]

    volume_list = (
        [int(v.strip()) for v in volumes.split(",")]
        if volumes
        else DEFAULT_SWEEP_VOLUMES
    )

    data = []
    for vol in volume_list:
        modified = replace(base_profile, monthly_requests=vol)
        for provider in all_providers:
            result = compute_lcpr(modified, provider)
            data.append({
                "monthly_requests": vol,
                "provider_name": result.provider_name,
                "deployment_mode": result.deployment_mode,
                "lcpr": round(result.lcpr, 6),
                "monthly_cost": round(result.monthly_cost, 2),
            })

    click.echo(json.dumps(data, indent=2))


def main():
    cli()


if __name__ == "__main__":
    main()
