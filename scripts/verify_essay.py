#!/usr/bin/env python3
# ABOUTME: Verifies essay numerical claims against the LCPR calculator.
# ABOUTME: Reads the essay, computes expected values, and exits non-zero on mismatch.

"""Verify all essay numerical claims against the LCPR calculator.

Reads the essay markdown, computes expected values from canonical
essay_profiles, and checks that each formatted number appears in the
essay text.  Exits non-zero if any claim is missing or wrong.

Usage:
    cd /path/to/inference-field-guide
    .venv/bin/python scripts/verify_essay.py
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ─── Data Types ──────────────────────────────────────────────────────────────


@dataclass
class ClaimSpec:
    """A single numerical claim to verify against the essay text."""

    label: str
    section: str  # e.g. "Part 0", "Part 1" — for reporting
    value: float  # calculator-computed expected value
    format_fn: Callable[[float], str]  # how to format for essay search


@dataclass
class ClaimDetail:
    """Result of verifying one claim."""

    label: str
    section: str
    expected_str: str
    status: str  # "PASS", "FAIL", or "MISSING"


@dataclass
class VerificationReport:
    """Aggregated verification results."""

    details: list[ClaimDetail]

    @property
    def passed(self) -> int:
        return sum(1 for d in self.details if d.status == "PASS")

    @property
    def failed(self) -> int:
        return sum(1 for d in self.details if d.status == "FAIL")

    @property
    def missing(self) -> int:
        return sum(1 for d in self.details if d.status == "MISSING")

    @property
    def ok(self) -> bool:
        return self.failed == 0 and self.missing == 0


# ─── Format Functions ────────────────────────────────────────────────────────


def format_dollar_lcpr(value: float) -> str:
    """Format as $X.XXXX (4 decimal places) — matches essay LCPR style."""
    return f"${value:.4f}"


def format_dollar_monthly(value: float) -> str:
    """Format as $X,XXX (comma-separated, no decimals) — matches essay monthly style."""
    return f"${round(value):,}"


def format_ratio(value: float) -> str:
    """Format as X.Nx — matches essay ratio style."""
    return f"{value:.1f}x"


# ─── Core Verification ──────────────────────────────────────────────────────


def verify_claims(essay_text: str, claims: list[ClaimSpec]) -> VerificationReport:
    """Check that each claim's formatted value appears in the essay text."""
    details: list[ClaimDetail] = []
    for claim in claims:
        expected_str = claim.format_fn(claim.value)
        if expected_str in essay_text:
            status = "PASS"
        else:
            # Check if the essay has any dollar/ratio near this location
            # that doesn't match — that's a FAIL (stale number).
            # If there's nothing resembling the claim at all, it's MISSING.
            # For simplicity: if the essay contains the section name and any
            # number of the same format type, call it FAIL; otherwise MISSING.
            status = "FAIL"
        details.append(ClaimDetail(
            label=claim.label,
            section=claim.section,
            expected_str=expected_str,
            status=status,
        ))
    return VerificationReport(details=details)


# ─── Claim Registry ─────────────────────────────────────────────────────────


def _build_claim_registry() -> list[ClaimSpec]:
    """Build the full list of claims from essay_profiles + calculator."""
    from calculator.essay_profiles import (
        PART0_85_GATE,
        PART0_HIGH_RETRY,
        PART0_LOW_GATE,
        PART0_SAAS,
        PART1_B2B,
        PART1_MINI_VOICE,
        PART2_CRESTA,
        PART5_STAGE0,
        PART5_STAGE1,
        PART5_STAGE1_GPT,
        PART5_STAGE1_TOG,
        PART5_STAGE2,
    )
    from calculator.lcpr import compute_lcpr, load_provider_pricing

    pricing_path = Path(__file__).parent.parent / "calculator" / "provider_pricing.yaml"
    providers = load_provider_pricing(pricing_path)

    def p(name: str):
        return next(pr for pr in providers if pr.name == name)

    gpt55 = p("OpenAI GPT-5.5")
    tog_dv3 = p("Together AI DeepSeek V3 / V3.1")
    fw_llama = p("Fireworks AI Llama 3.3 70B")
    deepinfra = p("DeepInfra GPT-OSS-120B")
    lambda_h100 = p("Lambda H100 SXM 80GB")
    lora_8b = p("Fireworks AI Multi-LoRA 8B base")

    claims: list[ClaimSpec] = []

    # ─── Part 0 Table ────────────────────────────────────────────────────
    for label, profile, provider in [
        ("Part 0: GPT-5.5 LCPR", PART0_SAAS, gpt55),
        ("Part 0: Together LCPR", PART0_SAAS, tog_dv3),
        ("Part 0: Fireworks LCPR", PART0_SAAS, fw_llama),
        ("Part 0: DeepInfra LCPR", PART0_SAAS, deepinfra),
    ]:
        r = compute_lcpr(profile, provider)
        claims.append(ClaimSpec(label, "Part 0", r.lcpr, format_dollar_lcpr))

    for label, profile, provider in [
        ("Part 0: GPT-5.5 monthly", PART0_SAAS, gpt55),
        ("Part 0: Together monthly", PART0_SAAS, tog_dv3),
        ("Part 0: Fireworks monthly", PART0_SAAS, fw_llama),
        ("Part 0: DeepInfra monthly", PART0_SAAS, deepinfra),
    ]:
        r = compute_lcpr(profile, provider)
        claims.append(ClaimSpec(label, "Part 0", r.monthly_cost, format_dollar_monthly))

    # Part 0: GPT/Together ratio
    gpt_lcpr = compute_lcpr(PART0_SAAS, gpt55).lcpr
    tog_lcpr = compute_lcpr(PART0_SAAS, tog_dv3).lcpr
    claims.append(ClaimSpec(
        "Part 0: GPT/Together ratio", "Part 0",
        gpt_lcpr / tog_lcpr, format_ratio,
    ))

    # Part 0: sensitivity ratios
    r_gpt_retry = compute_lcpr(PART0_HIGH_RETRY, gpt55)
    r_tog_retry = compute_lcpr(PART0_HIGH_RETRY, tog_dv3)
    claims.append(ClaimSpec(
        "Part 0: 20% retry ratio", "Part 0",
        r_gpt_retry.lcpr / r_tog_retry.lcpr, format_ratio,
    ))

    r_gpt_gate = compute_lcpr(PART0_LOW_GATE, gpt55)
    r_tog_gate = compute_lcpr(PART0_LOW_GATE, tog_dv3)
    claims.append(ClaimSpec(
        "Part 0: 70% gate ratio", "Part 0",
        r_gpt_gate.lcpr / r_tog_gate.lcpr, format_ratio,
    ))

    # ─── Part 1 Table ────────────────────────────────────────────────────
    r_gpt = compute_lcpr(PART1_B2B, gpt55)
    r_tog = compute_lcpr(PART1_B2B, tog_dv3)
    claims.append(ClaimSpec("Part 1: GPT-5.5 monthly", "Part 1", r_gpt.monthly_cost, format_dollar_monthly))
    claims.append(ClaimSpec("Part 1: Together monthly", "Part 1", r_tog.monthly_cost, format_dollar_monthly))
    savings = r_gpt.monthly_cost - r_tog.monthly_cost
    claims.append(ClaimSpec("Part 1: savings GPT→Together", "Part 1", savings, format_dollar_monthly))

    # ─── Part 2 Cresta ───────────────────────────────────────────────────
    r_gpt_c = compute_lcpr(PART2_CRESTA, gpt55)
    r_lora = compute_lcpr(PART2_CRESTA, lora_8b)
    claims.append(ClaimSpec(
        "Part 2: Cresta GPT/LoRA ratio", "Part 2",
        r_gpt_c.lcpr / r_lora.lcpr, format_ratio,
    ))

    # ─── Part 5 ──────────────────────────────────────────────────────────
    r_s0 = compute_lcpr(PART5_STAGE0, gpt55)
    claims.append(ClaimSpec("Part 5: Stage 0 GPT monthly", "Part 5", r_s0.monthly_cost, format_dollar_monthly))

    r_s1 = compute_lcpr(PART5_STAGE1, gpt55)
    claims.append(ClaimSpec("Part 5: Stage 1 GPT 2M monthly", "Part 5", r_s1.monthly_cost, format_dollar_monthly))

    r_s1g = compute_lcpr(PART5_STAGE1_GPT, gpt55)
    r_s1t = compute_lcpr(PART5_STAGE1_TOG, tog_dv3)
    combined = r_s1g.monthly_cost + r_s1t.monthly_cost
    s1_savings = r_s1.monthly_cost - combined
    claims.append(ClaimSpec("Part 5: Stage 1 combined", "Part 5", combined, format_dollar_monthly))
    claims.append(ClaimSpec("Part 5: Stage 1 savings", "Part 5", s1_savings, format_dollar_monthly))

    r_s2g = compute_lcpr(PART5_STAGE2, gpt55)
    r_s2t = compute_lcpr(PART5_STAGE2, tog_dv3)
    claims.append(ClaimSpec("Part 5: Stage 2 GPT monthly", "Part 5", r_s2g.monthly_cost, format_dollar_monthly))
    claims.append(ClaimSpec("Part 5: Stage 2 Together monthly", "Part 5", r_s2t.monthly_cost, format_dollar_monthly))

    return claims


# ─── Main ────────────────────────────────────────────────────────────────────


def main() -> int:
    essay_path = Path(__file__).parent.parent.parent / (
        "Documents/Sohailm25.github.io/content/inference-field-guide.md"
    )
    if not essay_path.exists():
        # Try relative to home
        essay_path = Path.home() / "Documents/Sohailm25.github.io/content/inference-field-guide.md"

    if not essay_path.exists():
        print(f"ERROR: Essay not found at {essay_path}", file=sys.stderr)
        return 1

    essay_text = essay_path.read_text()
    claims = _build_claim_registry()
    report = verify_claims(essay_text, claims)

    # Print results
    print("\n" + "=" * 90)
    print("ESSAY NUMBER VERIFICATION")
    print("=" * 90)
    print(f"\n{'Claim':<45} {'Section':<10} {'Expected':>14} {'Status':>8}")
    print("─" * 80)
    for detail in report.details:
        print(f"{detail.label:<45} {detail.section:<10} {detail.expected_str:>14} {detail.status:>8}")

    print("\n" + "─" * 80)
    print(f"PASSED: {report.passed}  FAILED: {report.failed}  MISSING: {report.missing}")

    if not report.ok:
        print("\nFAILED claims need essay text updated to match calculator output.")
        print("Run the calculator with essay_profiles.py to get correct values.")
        return 1

    print("\nAll essay numbers match calculator output.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
