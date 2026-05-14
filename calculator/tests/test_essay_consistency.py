# ABOUTME: Parametrized pytest that verifies essay numerical claims against the LCPR calculator.
# ABOUTME: Replacement for the old scripts/verify_essay.py crash-on-startup harness.

"""Essay consistency tests.

Computes expected values from canonical essay_profiles + provider_pricing.yaml
and asserts each formatted number appears in the essay markdown. Skips
gracefully when the website repo isn't mounted alongside this one.

Each ClaimSpec is a single parametrized test case, so assertion failures
isolate the *specific* number that has drifted between essay and calculator
rather than aborting the whole sweep on the first miss.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pytest

from calculator.essay_profiles import (
    PART0_HIGH_RETRY,
    PART0_LOW_GATE,
    PART0_SAAS,
    PART1_B2B,
    PART2_CRESTA,
    PART5_STAGE0,
    PART5_STAGE1,
    PART5_STAGE1_GPT,
    PART5_STAGE1_TOG,
    PART5_STAGE2,
)
from calculator.lcpr import compute_lcpr, load_provider_pricing

# --- Paths ---

essay_path = Path.home() / "Documents/Sohailm25.github.io/content/inference-field-guide.md"
pricing_path = Path(__file__).parent.parent / "provider_pricing.yaml"


# --- Format Helpers ---


def format_dollar_lcpr(value: float) -> str:
    """$X.XXXX (4 decimal places) — matches essay LCPR style."""
    return f"${value:.4f}"


def format_dollar_monthly(value: float) -> str:
    """$X,XXX (comma-separated, no decimals) — matches essay monthly style."""
    return f"${round(value):,}"


def format_ratio(value: float) -> str:
    """X.Nx — matches essay ratio style."""
    return f"{value:.1f}x"


# --- ClaimSpec ---


@dataclass
class ClaimSpec:
    """A single numerical claim to verify against the essay text."""

    label: str
    section: str
    value: float
    format_fn: Callable[[float], str]

    @property
    def expected_str(self) -> str:
        return self.format_fn(self.value)

    def __repr__(self) -> str:  # nicer parametrize ID
        return self.label


# --- Claim Registry ---


def _build_claim_registry() -> list[ClaimSpec]:
    """Build the full list of claims from essay_profiles + calculator.

    Mirrors the registry from the deprecated scripts/verify_essay.py, but
    with the broken "Fireworks AI Llama 3.3 70B" reference replaced by
    "Fireworks AI Llama 4 Maverick" to match the current YAML.
    """
    providers = load_provider_pricing(pricing_path)

    def p(name: str):
        try:
            return next(pr for pr in providers if pr.name == name)
        except StopIteration as exc:
            available = "\n  ".join(sorted(pr.name for pr in providers))
            raise LookupError(
                f"Provider {name!r} not found in {pricing_path}.\nAvailable:\n  {available}"
            ) from exc

    gpt55 = p("OpenAI GPT-5.5")
    tog_dv3 = p("Together AI DeepSeek V3 / V3.1")
    fw_llama = p("Fireworks AI Llama 4 Maverick")
    deepinfra = p("DeepInfra GPT-OSS-120B")
    lora_8b = p("Fireworks AI Multi-LoRA 8B base")

    claims: list[ClaimSpec] = []

    # --- Part 0 Table ---
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
    claims.append(
        ClaimSpec("Part 0: GPT/Together ratio", "Part 0", gpt_lcpr / tog_lcpr, format_ratio)
    )

    # Part 0: sensitivity ratios
    r_gpt_retry = compute_lcpr(PART0_HIGH_RETRY, gpt55)
    r_tog_retry = compute_lcpr(PART0_HIGH_RETRY, tog_dv3)
    claims.append(
        ClaimSpec(
            "Part 0: 20% retry ratio",
            "Part 0",
            r_gpt_retry.lcpr / r_tog_retry.lcpr,
            format_ratio,
        )
    )

    r_gpt_gate = compute_lcpr(PART0_LOW_GATE, gpt55)
    r_tog_gate = compute_lcpr(PART0_LOW_GATE, tog_dv3)
    claims.append(
        ClaimSpec(
            "Part 0: 70% gate ratio",
            "Part 0",
            r_gpt_gate.lcpr / r_tog_gate.lcpr,
            format_ratio,
        )
    )

    # --- Part 1 Table ---
    r_gpt = compute_lcpr(PART1_B2B, gpt55)
    r_tog = compute_lcpr(PART1_B2B, tog_dv3)
    claims.append(
        ClaimSpec("Part 1: GPT-5.5 monthly", "Part 1", r_gpt.monthly_cost, format_dollar_monthly)
    )
    claims.append(
        ClaimSpec("Part 1: Together monthly", "Part 1", r_tog.monthly_cost, format_dollar_monthly)
    )
    savings = r_gpt.monthly_cost - r_tog.monthly_cost
    claims.append(
        ClaimSpec("Part 1: savings GPT->Together", "Part 1", savings, format_dollar_monthly)
    )

    # --- Part 2 Cresta ---
    r_gpt_c = compute_lcpr(PART2_CRESTA, gpt55)
    r_lora = compute_lcpr(PART2_CRESTA, lora_8b)
    claims.append(
        ClaimSpec(
            "Part 2: Cresta GPT/LoRA ratio", "Part 2", r_gpt_c.lcpr / r_lora.lcpr, format_ratio
        )
    )

    # --- Part 5 ---
    r_s0 = compute_lcpr(PART5_STAGE0, gpt55)
    claims.append(
        ClaimSpec(
            "Part 5: Stage 0 GPT monthly", "Part 5", r_s0.monthly_cost, format_dollar_monthly
        )
    )

    r_s1 = compute_lcpr(PART5_STAGE1, gpt55)
    claims.append(
        ClaimSpec(
            "Part 5: Stage 1 GPT 2M monthly",
            "Part 5",
            r_s1.monthly_cost,
            format_dollar_monthly,
        )
    )

    r_s1g = compute_lcpr(PART5_STAGE1_GPT, gpt55)
    r_s1t = compute_lcpr(PART5_STAGE1_TOG, tog_dv3)
    combined = r_s1g.monthly_cost + r_s1t.monthly_cost
    s1_savings = r_s1.monthly_cost - combined
    claims.append(
        ClaimSpec("Part 5: Stage 1 combined", "Part 5", combined, format_dollar_monthly)
    )
    claims.append(
        ClaimSpec("Part 5: Stage 1 savings", "Part 5", s1_savings, format_dollar_monthly)
    )

    r_s2g = compute_lcpr(PART5_STAGE2, gpt55)
    r_s2t = compute_lcpr(PART5_STAGE2, tog_dv3)
    claims.append(
        ClaimSpec(
            "Part 5: Stage 2 GPT monthly",
            "Part 5",
            r_s2g.monthly_cost,
            format_dollar_monthly,
        )
    )
    claims.append(
        ClaimSpec(
            "Part 5: Stage 2 Together monthly",
            "Part 5",
            r_s2t.monthly_cost,
            format_dollar_monthly,
        )
    )

    return claims


CLAIMS = _build_claim_registry()


# --- Tests ---


@pytest.mark.skipif(not essay_path.exists(), reason="essay file not present")
@pytest.mark.parametrize("claim", CLAIMS, ids=[c.label for c in CLAIMS])
def test_essay_claim_present(claim: ClaimSpec) -> None:
    """Each ClaimSpec's formatted value must appear verbatim in the essay text."""
    essay_text = essay_path.read_text()
    assert claim.expected_str in essay_text, (
        f"[{claim.section}] {claim.label}: expected {claim.expected_str!r} "
        f"in essay at {essay_path}"
    )
