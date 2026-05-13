# ABOUTME: Tests for the Trace-to-Margin reconciliation computation (Derivation 6).
# ABOUTME: Verifies LCPR, margin, delta analysis, and naive-vs-loaded gap.

import pytest

from calculator.lcpr import (
    TraceToMarginResult,
    compute_trace_to_margin,
)


class TestComputeTraceToMargin:
    """Tests matching the book's Derivation 6 worked example."""

    def test_book_example_total_loaded_cost(self):
        """Book example: $14.20 + $0.65 + $0.80 + $100.00 + $25.00 = $140.65"""
        result = compute_trace_to_margin(
            trace_cost=14.20,
            invoice_amount=14.85,
            eval_cost=0.80,
            human_cost=100.00,
            ops_cost=25.00,
            total_attempts=1000,
            accepted_units=820,
            revenue_per_unit=0.25,
        )
        assert result.total_loaded_cost == pytest.approx(140.65)

    def test_book_example_delta(self):
        result = compute_trace_to_margin(
            trace_cost=14.20,
            invoice_amount=14.85,
            eval_cost=0.80,
            human_cost=100.00,
            ops_cost=25.00,
            total_attempts=1000,
            accepted_units=820,
            revenue_per_unit=0.25,
        )
        assert result.delta == pytest.approx(0.65)

    def test_book_example_lcpr(self):
        """LCPR = $140.65 / 820 = $0.172"""
        result = compute_trace_to_margin(
            trace_cost=14.20,
            invoice_amount=14.85,
            eval_cost=0.80,
            human_cost=100.00,
            ops_cost=25.00,
            total_attempts=1000,
            accepted_units=820,
            revenue_per_unit=0.25,
        )
        assert result.lcpr == pytest.approx(0.1715, abs=0.001)

    def test_book_example_naive_cost(self):
        """Naive = $14.20 / 1000 = $0.0142"""
        result = compute_trace_to_margin(
            trace_cost=14.20,
            invoice_amount=14.85,
            eval_cost=0.80,
            human_cost=100.00,
            ops_cost=25.00,
            total_attempts=1000,
            accepted_units=820,
            revenue_per_unit=0.25,
        )
        assert result.naive_cost_per_unit == pytest.approx(0.0142)

    def test_book_example_12x_gap(self):
        """Loaded cost is ~12x the naive cost."""
        result = compute_trace_to_margin(
            trace_cost=14.20,
            invoice_amount=14.85,
            eval_cost=0.80,
            human_cost=100.00,
            ops_cost=25.00,
            total_attempts=1000,
            accepted_units=820,
            revenue_per_unit=0.25,
        )
        assert result.lcpr_to_naive_ratio == pytest.approx(12.1, abs=0.5)

    def test_book_example_gross_margin(self):
        """Revenue = 820 * $0.25 = $205. Margin = $205 - $140.65 = $64.35"""
        result = compute_trace_to_margin(
            trace_cost=14.20,
            invoice_amount=14.85,
            eval_cost=0.80,
            human_cost=100.00,
            ops_cost=25.00,
            total_attempts=1000,
            accepted_units=820,
            revenue_per_unit=0.25,
        )
        assert result.revenue == pytest.approx(205.00)
        assert result.gross_margin == pytest.approx(64.35)
        assert result.gross_margin_pct == pytest.approx(0.314, abs=0.01)

    def test_zero_accepted_raises(self):
        with pytest.raises(ValueError, match="accepted_units must be > 0"):
            compute_trace_to_margin(10, 10, 1, 50, 10, 100, 0, 0.25)

    def test_zero_attempts_raises(self):
        with pytest.raises(ValueError, match="total_attempts must be > 0"):
            compute_trace_to_margin(10, 10, 1, 50, 10, 0, 80, 0.25)

    def test_negative_margin(self):
        """When costs exceed revenue, margin is negative."""
        result = compute_trace_to_margin(
            trace_cost=100.00,
            invoice_amount=105.00,
            eval_cost=10.00,
            human_cost=500.00,
            ops_cost=100.00,
            total_attempts=1000,
            accepted_units=800,
            revenue_per_unit=0.10,
        )
        assert result.gross_margin < 0

    def test_zero_revenue(self):
        """Internal tools: no revenue attribution."""
        result = compute_trace_to_margin(
            trace_cost=14.20,
            invoice_amount=14.85,
            eval_cost=0.80,
            human_cost=100.00,
            ops_cost=25.00,
            total_attempts=1000,
            accepted_units=820,
            revenue_per_unit=0.0,
        )
        assert result.revenue == 0.0
        assert result.gross_margin_pct == 0.0
        assert result.lcpr == pytest.approx(0.1715, abs=0.001)

    def test_no_delta(self):
        """When trace matches invoice exactly, delta is 0."""
        result = compute_trace_to_margin(
            trace_cost=14.85,
            invoice_amount=14.85,
            eval_cost=0.80,
            human_cost=100.00,
            ops_cost=25.00,
            total_attempts=1000,
            accepted_units=820,
            revenue_per_unit=0.25,
        )
        assert result.delta == pytest.approx(0.0)
        assert result.total_loaded_cost == pytest.approx(140.65)
