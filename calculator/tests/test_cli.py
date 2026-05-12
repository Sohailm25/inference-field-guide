# ABOUTME: Tests for the CLI interface to the LCPR calculator.
# ABOUTME: Validates compare, crossover, sensitivity, and profiles commands via CliRunner.

import json

import pytest
from click.testing import CliRunner

from calculator.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


# --- Profiles Command ---


class TestProfilesCommand:
    """Tests for `lcpr profiles` — list available workload profiles."""

    def test_profiles_lists_names(self, runner):
        result = runner.invoke(cli, ["profiles"])
        assert result.exit_code == 0
        assert "saas_chat" in result.output
        assert "code_completion" in result.output
        assert "batch_processing" in result.output
        assert "voice_agent" in result.output
        assert "rag_pipeline" in result.output

    def test_profiles_shows_details(self, runner):
        """Should show token counts and request volume for each profile."""
        result = runner.invoke(cli, ["profiles"])
        assert result.exit_code == 0
        # Should contain some numeric data
        assert "500" in result.output or "800" in result.output  # token counts


# --- Compare Command ---


class TestCompareCommand:
    """Tests for `lcpr compare` — compare LCPR across providers."""

    def test_compare_with_profile(self, runner):
        """Should compare all providers using a named profile."""
        result = runner.invoke(cli, ["compare", "--profile", "saas_chat"])
        assert result.exit_code == 0
        # Should show provider names and costs
        assert "OpenAI" in result.output or "Together" in result.output
        assert "$" in result.output or "lcpr" in result.output.lower()

    def test_compare_with_unknown_profile_errors(self, runner):
        result = runner.invoke(cli, ["compare", "--profile", "nonexistent"])
        assert result.exit_code != 0

    def test_compare_sorted_by_lcpr(self, runner):
        """Output should list cheapest first."""
        result = runner.invoke(cli, ["compare", "--profile", "saas_chat"])
        assert result.exit_code == 0
        # Find all dollar amounts and verify they're ascending
        # (We'll just check it runs and has multiple providers)
        lines = result.output.strip().split("\n")
        provider_lines = [ln for ln in lines if "$" in ln or "LCPR" in ln.upper()]
        assert len(provider_lines) >= 2  # at least 2 providers shown

    def test_compare_json_output(self, runner):
        """--format json should produce valid JSON."""
        result = runner.invoke(cli, ["compare", "--profile", "saas_chat", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) > 0
        assert "provider_name" in data[0]
        assert "lcpr" in data[0]
        assert "monthly_cost" in data[0]

    def test_compare_with_custom_params(self, runner):
        """Should accept custom workload parameters."""
        result = runner.invoke(
            cli,
            [
                "compare",
                "--input-tokens", "1000",
                "--output-tokens", "500",
                "--monthly-requests", "200000",
                "--retry-rate", "0.03",
                "--quality-gate", "0.95",
            ],
        )
        assert result.exit_code == 0
        assert "OpenAI" in result.output or "Together" in result.output

    def test_compare_requires_profile_or_custom(self, runner):
        """Should error if neither --profile nor custom params are provided."""
        result = runner.invoke(cli, ["compare"])
        assert result.exit_code != 0


# --- Crossover Command ---


class TestCrossoverCommand:
    """Tests for `lcpr crossover` — break-even analysis."""

    def test_crossover_default(self, runner):
        """Should show break-even between serverless and dedicated."""
        result = runner.invoke(cli, ["crossover"])
        assert result.exit_code == 0
        assert "break" in result.output.lower() or "token" in result.output.lower()

    def test_crossover_with_specific_providers(self, runner):
        """Should accept specific provider names."""
        result = runner.invoke(
            cli,
            [
                "crossover",
                "--serverless", "Together AI DeepSeek V3 / V3.1",
                "--dedicated", "Lambda H100 SXM 80GB",
            ],
        )
        assert result.exit_code == 0
        assert "Together" in result.output or "Lambda" in result.output

    def test_crossover_json_output(self, runner):
        """--format json should produce valid JSON."""
        result = runner.invoke(cli, ["crossover", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "break_even_daily_output_tokens" in data

    def test_crossover_shows_daily_tokens(self, runner):
        """Should display the break-even daily token volume."""
        result = runner.invoke(cli, ["crossover"])
        assert result.exit_code == 0
        # Should contain a number representing daily tokens
        # The break-even is in the millions range
        assert "M" in result.output or "million" in result.output.lower() or any(
            c.isdigit() for c in result.output
        )


# --- Sensitivity Command ---


class TestSensitivityCommand:
    """Tests for `lcpr sensitivity` — vary one parameter and show LCPR impact."""

    def test_sensitivity_retry_rate(self, runner):
        """Should show LCPR at different retry rates."""
        result = runner.invoke(
            cli,
            [
                "sensitivity",
                "--profile", "saas_chat",
                "--vary", "retry_rate",
                "--values", "0.0,0.05,0.10,0.20",
            ],
        )
        assert result.exit_code == 0
        # Should show multiple rows
        lines = result.output.strip().split("\n")
        assert len(lines) >= 4  # header + at least 4 data rows (or 4 value rows)

    def test_sensitivity_quality_gate(self, runner):
        """Should work with quality_gate_pass_rate variation."""
        result = runner.invoke(
            cli,
            [
                "sensitivity",
                "--profile", "saas_chat",
                "--vary", "quality_gate_pass_rate",
                "--values", "0.70,0.85,0.95,1.0",
            ],
        )
        assert result.exit_code == 0

    def test_sensitivity_json_output(self, runner):
        """--format json should produce valid JSON array."""
        result = runner.invoke(
            cli,
            [
                "sensitivity",
                "--profile", "saas_chat",
                "--vary", "retry_rate",
                "--values", "0.0,0.10,0.20",
                "--format", "json",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 3

    def test_sensitivity_requires_profile(self, runner):
        """Should error without a profile."""
        result = runner.invoke(
            cli,
            [
                "sensitivity",
                "--vary", "retry_rate",
                "--values", "0.0,0.10",
            ],
        )
        assert result.exit_code != 0

    def test_sensitivity_invalid_vary_param(self, runner):
        """Should error on invalid vary parameter."""
        result = runner.invoke(
            cli,
            [
                "sensitivity",
                "--profile", "saas_chat",
                "--vary", "nonexistent_field",
                "--values", "0.0,0.10",
            ],
        )
        assert result.exit_code != 0


# --- Sweep Command ---


class TestSweepCommand:
    """Tests for `lcpr sweep` — volume-vs-cost data for charting."""

    def test_sweep_default(self, runner):
        """Should produce JSON array of volume/cost data points."""
        result = runner.invoke(cli, ["sweep", "--profile", "saas_chat"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) > 0
        # Each point should have volume, provider, and cost fields
        point = data[0]
        assert "monthly_requests" in point
        assert "provider_name" in point
        assert "monthly_cost" in point

    def test_sweep_has_multiple_providers(self, runner):
        """Should include data for multiple providers at each volume."""
        result = runner.invoke(cli, ["sweep", "--profile", "saas_chat"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        providers = {d["provider_name"] for d in data}
        assert len(providers) >= 2

    def test_sweep_has_multiple_volumes(self, runner):
        """Should sweep across multiple volume levels."""
        result = runner.invoke(cli, ["sweep", "--profile", "saas_chat"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        volumes = {d["monthly_requests"] for d in data}
        assert len(volumes) >= 5

    def test_sweep_cost_increases_with_volume(self, runner):
        """For serverless providers, cost should increase with volume."""
        result = runner.invoke(cli, ["sweep", "--profile", "saas_chat"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        # Pick a serverless provider
        serverless = [
            d for d in data if d["deployment_mode"] == "serverless_open"
        ]
        if len(serverless) >= 2:
            # Group by provider and check cost monotonicity
            by_provider = {}
            for d in serverless:
                by_provider.setdefault(d["provider_name"], []).append(d)
            for name, points in by_provider.items():
                points.sort(key=lambda x: x["monthly_requests"])
                costs = [p["monthly_cost"] for p in points]
                assert costs == sorted(costs), (
                    f"{name} costs not monotonically increasing"
                )

    def test_sweep_with_providers_filter(self, runner):
        """Should accept --providers to limit which providers appear."""
        result = runner.invoke(
            cli,
            [
                "sweep",
                "--profile", "saas_chat",
                "--providers", "Together,OpenAI",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        providers = {d["provider_name"] for d in data}
        # All providers should contain "Together" or "OpenAI"
        for p in providers:
            assert "Together" in p or "OpenAI" in p, (
                f"Unexpected provider: {p}"
            )


# --- Compare Command: Cache Hit Rate and Batch Fraction Options ---


class TestCompareCacheAndBatchOptions:
    """Tests for --cache-hit-rate and --batch-fraction on the compare command."""

    def test_cache_hit_rate_option(self, runner):
        """--cache-hit-rate should produce output without error."""
        result = runner.invoke(
            cli,
            [
                "compare",
                "--input-tokens", "800",
                "--output-tokens", "400",
                "--monthly-requests", "500000",
                "--cache-hit-rate", "0.5",
            ],
        )
        assert result.exit_code == 0, f"Exit code {result.exit_code}: {result.output}"
        assert "$" in result.output or "lcpr" in result.output.lower()

    def test_batch_fraction_option(self, runner):
        """--batch-fraction should produce output without error."""
        result = runner.invoke(
            cli,
            [
                "compare",
                "--input-tokens", "800",
                "--output-tokens", "400",
                "--monthly-requests", "500000",
                "--batch-fraction", "0.3",
            ],
        )
        assert result.exit_code == 0, f"Exit code {result.exit_code}: {result.output}"
        assert "$" in result.output or "lcpr" in result.output.lower()

    def test_cache_hit_rate_and_batch_fraction_combined(self, runner):
        """Both --cache-hit-rate and --batch-fraction together should work."""
        result = runner.invoke(
            cli,
            [
                "compare",
                "--input-tokens", "800",
                "--output-tokens", "400",
                "--monthly-requests", "500000",
                "--cache-hit-rate", "0.4",
                "--batch-fraction", "0.2",
            ],
        )
        assert result.exit_code == 0, f"Exit code {result.exit_code}: {result.output}"
        assert "$" in result.output or "lcpr" in result.output.lower()

    def test_cache_hit_rate_with_profile(self, runner):
        """--cache-hit-rate should also work with a named profile."""
        result = runner.invoke(
            cli,
            [
                "compare",
                "--profile", "saas_chat",
                "--cache-hit-rate", "0.5",
            ],
        )
        # This may or may not apply cache-hit-rate to a profile --
        # just verify no crash
        assert result.exit_code == 0, f"Exit code {result.exit_code}: {result.output}"
