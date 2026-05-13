# ABOUTME: Tests for the Goodput Frontier Test computation (Derivation 5).
# ABOUTME: Verifies goodput rate, cost per accepted result, and SLO gate logic.

import math

import pytest

from calculator.lcpr import (
    GoodputRequest,
    GoodputResult,
    compute_goodput,
)


@pytest.fixture
def route_a_requests():
    """Route A from the book's Part 2 worked example.

    100 requests, 10 seconds, high throughput but poor latency/quality.
    58 pass ALL gates.
    """
    requests = []
    # 72 pass quality, but only 58 pass quality AND latency
    for i in range(100):
        quality = i < 72  # 72% quality pass
        # 80% pass TTFT SLO (800ms), meaning 20 fail
        ttft = 500.0 if i < 80 else 1400.0
        tpot = 45.0 if i < 90 else 55.0
        # Of the 72 that pass quality AND 80 that pass latency,
        # 58 pass BOTH (intersection)
        if i < 58:
            quality = True
            ttft = 500.0
            tpot = 45.0
        elif i < 72:
            quality = True
            ttft = 1400.0  # fail latency
        elif i < 80:
            quality = False
            ttft = 500.0  # pass latency but fail quality
        else:
            quality = False
            ttft = 1400.0
        requests.append(GoodputRequest(
            ttft_ms=ttft,
            tpot_ms=tpot,
            output_tokens=200,
            quality_pass=quality,
            cost=0.011,  # $1.10 / 100
        ))
    return requests


@pytest.fixture
def route_b_requests():
    """Route B from the book's Part 2 worked example.

    100 requests, 10 seconds, lower throughput but better latency/quality.
    85 pass ALL gates.
    """
    requests = []
    for i in range(100):
        if i < 85:
            quality = True
            ttft = 500.0
            tpot = 35.0
        elif i < 91:
            quality = True
            ttft = 900.0  # fail TTFT SLO
        else:
            quality = False
            ttft = 500.0
        requests.append(GoodputRequest(
            ttft_ms=ttft,
            tpot_ms=tpot,
            output_tokens=200,
            quality_pass=quality,
            cost=0.0145,  # $1.45 / 100
        ))
    return requests


class TestComputeGoodput:
    """Tests for compute_goodput matching Derivation 5."""

    def test_route_a_accepted_count(self, route_a_requests):
        result = compute_goodput(route_a_requests, 10.0, 800.0, 50.0)
        assert result.accepted_requests == 58

    def test_route_a_goodput_rate(self, route_a_requests):
        result = compute_goodput(route_a_requests, 10.0, 800.0, 50.0)
        assert result.goodput_rate == pytest.approx(5.8)

    def test_route_a_cost_per_accepted(self, route_a_requests):
        result = compute_goodput(route_a_requests, 10.0, 800.0, 50.0)
        assert result.cost_per_accepted == pytest.approx(0.019, abs=0.001)

    def test_route_b_accepted_count(self, route_b_requests):
        result = compute_goodput(route_b_requests, 10.0, 800.0, 50.0)
        assert result.accepted_requests == 85

    def test_route_b_goodput_rate(self, route_b_requests):
        result = compute_goodput(route_b_requests, 10.0, 800.0, 50.0)
        assert result.goodput_rate == pytest.approx(8.5)

    def test_route_b_cost_per_accepted(self, route_b_requests):
        result = compute_goodput(route_b_requests, 10.0, 800.0, 50.0)
        assert result.cost_per_accepted == pytest.approx(0.017, abs=0.001)

    def test_route_b_cheaper_per_accepted(self, route_a_requests, route_b_requests):
        """Route B should win on cost per accepted despite higher total cost."""
        a = compute_goodput(route_a_requests, 10.0, 800.0, 50.0)
        b = compute_goodput(route_b_requests, 10.0, 800.0, 50.0)
        assert b.cost_per_accepted < a.cost_per_accepted
        assert b.total_cost > a.total_cost  # B costs more total

    def test_quality_pass_rate(self, route_a_requests):
        result = compute_goodput(route_a_requests, 10.0, 800.0, 50.0)
        assert result.quality_pass_rate == pytest.approx(0.72)

    def test_empty_requests_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            compute_goodput([], 10.0, 800.0, 50.0)

    def test_zero_duration_raises(self):
        req = [GoodputRequest(100, 30, 100, True, 0.01)]
        with pytest.raises(ValueError, match="duration_seconds must be > 0"):
            compute_goodput(req, 0.0, 800.0, 50.0)

    def test_all_fail_quality(self):
        requests = [
            GoodputRequest(100, 30, 100, False, 0.01)
            for _ in range(10)
        ]
        result = compute_goodput(requests, 10.0, 800.0, 50.0)
        assert result.accepted_requests == 0
        assert result.goodput_rate == 0.0
        assert result.cost_per_accepted == float("inf")

    def test_all_fail_latency(self):
        requests = [
            GoodputRequest(1500, 30, 100, True, 0.01)
            for _ in range(10)
        ]
        result = compute_goodput(requests, 10.0, 800.0, 50.0)
        assert result.accepted_requests == 0
        assert result.latency_pass_rate == 0.0

    def test_perfect_requests(self):
        requests = [
            GoodputRequest(100, 30, 100, True, 0.01)
            for _ in range(100)
        ]
        result = compute_goodput(requests, 10.0, 800.0, 50.0)
        assert result.accepted_requests == 100
        assert result.goodput_rate == pytest.approx(10.0)
        assert result.cost_per_accepted == pytest.approx(0.01)
