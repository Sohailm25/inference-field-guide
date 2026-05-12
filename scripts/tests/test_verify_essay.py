# ABOUTME: Tests for the essay verifier — ensures the verifier correctly detects
# ABOUTME: matches, mismatches, and missing claims when comparing essay text to calculator output.

from __future__ import annotations

import pytest

from scripts.verify_essay import (
    ClaimSpec,
    VerificationReport,
    format_dollar_lcpr,
    format_dollar_monthly,
    format_ratio,
    verify_claims,
)


class TestFormatFunctions:
    """Test that format functions produce essay-matching strings."""

    def test_format_dollar_lcpr_four_decimals(self):
        assert format_dollar_lcpr(0.019124) == "$0.0191"

    def test_format_dollar_lcpr_rounds_correctly(self):
        assert format_dollar_lcpr(0.003047) == "$0.0030"

    def test_format_dollar_lcpr_small_value(self):
        assert format_dollar_lcpr(0.00073) == "$0.0007"

    def test_format_dollar_monthly_with_commas(self):
        assert format_dollar_monthly(9090.0) == "$9,090"

    def test_format_dollar_monthly_large(self):
        assert format_dollar_monthly(166600.0) == "$166,600"

    def test_format_dollar_monthly_rounds(self):
        assert format_dollar_monthly(1447.4) == "$1,447"

    def test_format_ratio(self):
        assert format_ratio(6.28) == "6.3x"

    def test_format_ratio_single_decimal(self):
        assert format_ratio(1.20) == "1.2x"


class TestVerifyClaims:
    """Test the core verification logic."""

    def test_matching_claim_passes(self):
        essay = "The monthly cost is $9,090 for this workload."
        claims = [ClaimSpec("test", "Part 0", 9090.0, format_dollar_monthly)]
        report = verify_claims(essay, claims)
        assert report.passed == 1
        assert report.failed == 0
        assert report.missing == 0

    def test_mismatched_claim_fails(self):
        essay = "The monthly cost is $8,500 for this workload."
        claims = [ClaimSpec("test", "Part 0", 9090.0, format_dollar_monthly)]
        report = verify_claims(essay, claims)
        assert report.passed == 0
        assert report.failed == 1

    def test_missing_value_is_failure(self):
        essay = "No dollar amounts in this text at all."
        claims = [ClaimSpec("test", "Part 0", 9090.0, format_dollar_monthly)]
        report = verify_claims(essay, claims)
        assert report.failed == 1

    def test_lcpr_match_with_rounding(self):
        essay = "GPT-5.5 LCPR is $0.0191 per request."
        claims = [ClaimSpec("test", "Part 0", 0.019124, format_dollar_lcpr)]
        report = verify_claims(essay, claims)
        assert report.passed == 1

    def test_ratio_match(self):
        essay = "The ratio increases from 5.6x to 6.3x."
        claims = [ClaimSpec("ratio test", "Part 0", 6.28, format_ratio)]
        report = verify_claims(essay, claims)
        assert report.passed == 1

    def test_multiple_claims_mixed(self):
        essay = "Cost is $9,090 and LCPR is $0.0191 per request."
        claims = [
            ClaimSpec("monthly", "Part 0", 9090.0, format_dollar_monthly),
            ClaimSpec("lcpr", "Part 0", 0.019124, format_dollar_lcpr),
            ClaimSpec("wrong", "Part 0", 5000.0, format_dollar_monthly),
        ]
        report = verify_claims(essay, claims)
        assert report.passed == 2
        assert report.failed == 1

    def test_report_is_not_ok_on_failure(self):
        essay = "LCPR is $0.0200 per request."
        claims = [ClaimSpec("test", "Part 0", 0.0191, format_dollar_lcpr)]
        report = verify_claims(essay, claims)
        assert not report.ok

    def test_report_is_ok_on_all_pass(self):
        essay = "LCPR is $0.0191 per request."
        claims = [ClaimSpec("test", "Part 0", 0.0191, format_dollar_lcpr)]
        report = verify_claims(essay, claims)
        assert report.ok

    def test_report_details_contain_expected(self):
        essay = "LCPR is $0.0200 per request."
        claims = [ClaimSpec("lcpr claim", "Part 0", 0.0191, format_dollar_lcpr)]
        report = verify_claims(essay, claims)
        assert len(report.details) == 1
        detail = report.details[0]
        assert detail.label == "lcpr claim"
        assert detail.expected_str == "$0.0191"
        assert detail.status == "FAIL"
