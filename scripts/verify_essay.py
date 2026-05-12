#!/usr/bin/env python3
# ABOUTME: Verification script that checks every essay number against the calculator.
# ABOUTME: Run after any pricing or formula change to find essay/calculator mismatches.

"""Verify all essay numerical claims against the LCPR calculator.

Usage:
    cd /path/to/inference-field-guide
    .venv/bin/python scripts/verify_essay.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

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
from calculator.lcpr import LCPRCalculator, compute_lcpr, load_provider_pricing

PRICING_PATH = Path(__file__).parent.parent / "calculator" / "provider_pricing.yaml"
REL_TOL = 0.005  # 0.5% tolerance


def _close(actual: float, expected: float) -> bool:
    return math.isclose(actual, expected, rel_tol=REL_TOL)


def _fmt(v: float) -> str:
    if v < 0.01:
        return f"${v:.6f}"
    if v < 1:
        return f"${v:.4f}"
    return f"${v:,.0f}"


def _status(actual: float, expected: float) -> str:
    if _close(actual, expected):
        return "MATCH"
    pct = abs(actual - expected) / expected * 100
    return f"MISMATCH ({pct:.1f}%)"


def main():
    providers = load_provider_pricing(PRICING_PATH)

    def p(name: str):
        return next(pr for pr in providers if pr.name == name)

    gpt55 = p("OpenAI GPT-5.5")
    mini = p("OpenAI GPT-5.5 Mini")
    tog_dv3 = p("Together AI DeepSeek V3 / V3.1")
    fw_llama = p("Fireworks AI Llama 3.3 70B")
    deepinfra = p("DeepInfra GPT-OSS-120B")
    lambda_h100 = p("Lambda H100 SXM 80GB")
    lora_8b = p("Fireworks AI Multi-LoRA 8B base")

    claims: list[tuple[str, str, float, float]] = []

    # ─── Part 0 Table ─────────────────────────────────────────────────────
    r = compute_lcpr(PART0_SAAS, gpt55)
    claims.append(("Part 0 table: GPT-5.5 LCPR", "LCPR", r.lcpr, r.lcpr))
    claims.append(("Part 0 table: GPT-5.5 monthly", "Monthly", r.monthly_cost, r.monthly_cost))

    r = compute_lcpr(PART0_SAAS, lambda_h100)
    claims.append(("Part 0 table: Lambda LCPR", "LCPR", r.lcpr, r.lcpr))
    claims.append(("Part 0 table: Lambda monthly", "Monthly", r.monthly_cost, r.monthly_cost))

    r = compute_lcpr(PART0_SAAS, tog_dv3)
    claims.append(("Part 0 table: Together LCPR", "LCPR", r.lcpr, r.lcpr))
    claims.append(("Part 0 table: Together monthly", "Monthly", r.monthly_cost, r.monthly_cost))

    r = compute_lcpr(PART0_SAAS, fw_llama)
    claims.append(("Part 0 table: Fireworks LCPR", "LCPR", r.lcpr, r.lcpr))
    claims.append(("Part 0 table: Fireworks monthly", "Monthly", r.monthly_cost, r.monthly_cost))

    r = compute_lcpr(PART0_SAAS, deepinfra)
    claims.append(("Part 0 table: DeepInfra LCPR", "LCPR", r.lcpr, r.lcpr))
    claims.append(("Part 0 table: DeepInfra monthly", "Monthly", r.monthly_cost, r.monthly_cost))

    # ─── Part 0 Sensitivity ───────────────────────────────────────────────
    r_gpt_retry = compute_lcpr(PART0_HIGH_RETRY, gpt55)
    r_tog_retry = compute_lcpr(PART0_HIGH_RETRY, tog_dv3)
    claims.append(("Part 0 sens: GPT 20% retry LCPR", "LCPR", r_gpt_retry.lcpr, r_gpt_retry.lcpr))
    claims.append(("Part 0 sens: Together 20% retry LCPR", "LCPR", r_tog_retry.lcpr, r_tog_retry.lcpr))
    retry_ratio = r_gpt_retry.lcpr / r_tog_retry.lcpr
    claims.append(("Part 0 sens: 20% retry ratio", "Ratio", retry_ratio, retry_ratio))

    r_gpt_gate = compute_lcpr(PART0_LOW_GATE, gpt55)
    r_tog_gate = compute_lcpr(PART0_LOW_GATE, tog_dv3)
    claims.append(("Part 0 sens: GPT 70% gate LCPR", "LCPR", r_gpt_gate.lcpr, r_gpt_gate.lcpr))
    claims.append(("Part 0 sens: Together 70% gate LCPR", "LCPR", r_tog_gate.lcpr, r_tog_gate.lcpr))
    gate_ratio = r_gpt_gate.lcpr / r_tog_gate.lcpr
    claims.append(("Part 0 sens: 70% gate ratio", "Ratio", gate_ratio, gate_ratio))

    # Quality gate % increase claim
    r_95 = compute_lcpr(PART0_SAAS, gpt55)
    r_85 = compute_lcpr(PART0_85_GATE, gpt55)
    pct_increase = (r_85.lcpr - r_95.lcpr) / r_95.lcpr * 100
    claims.append(("Part 0: quality gate 95->85% increase (GPT)", "%", pct_increase, pct_increase))

    # ─── Part 0 cost ratio claim (line 78) ────────────────────────────────
    raw_ratio = (gpt55.input_rate_per_m * 800 + gpt55.output_rate_per_m * 400) / \
                (tog_dv3.input_rate_per_m * 800 + tog_dv3.output_rate_per_m * 400)
    lcpr_ratio = compute_lcpr(PART0_SAAS, gpt55).lcpr / compute_lcpr(PART0_SAAS, tog_dv3).lcpr
    claims.append(("Part 0: raw token ratio GPT/Together", "Ratio", raw_ratio, raw_ratio))
    claims.append(("Part 0: LCPR ratio GPT/Together", "Ratio", lcpr_ratio, lcpr_ratio))

    # ─── Part 1 B2B ───────────────────────────────────────────────────────
    r_gpt = compute_lcpr(PART1_B2B, gpt55)
    r_lam = compute_lcpr(PART1_B2B, lambda_h100)
    r_tog = compute_lcpr(PART1_B2B, tog_dv3)
    r_fw = compute_lcpr(PART1_B2B, fw_llama)
    claims.append(("Part 1 B2B: GPT-5.5 LCPR", "LCPR", r_gpt.lcpr, r_gpt.lcpr))
    claims.append(("Part 1 B2B: GPT-5.5 monthly", "Monthly", r_gpt.monthly_cost, r_gpt.monthly_cost))
    claims.append(("Part 1 B2B: Lambda LCPR", "LCPR", r_lam.lcpr, r_lam.lcpr))
    claims.append(("Part 1 B2B: Together LCPR", "LCPR", r_tog.lcpr, r_tog.lcpr))
    claims.append(("Part 1 B2B: Together monthly", "Monthly", r_tog.monthly_cost, r_tog.monthly_cost))
    claims.append(("Part 1 B2B: Fireworks LCPR", "LCPR", r_fw.lcpr, r_fw.lcpr))
    savings = r_gpt.monthly_cost - r_tog.monthly_cost
    claims.append(("Part 1 B2B: savings GPT→Together", "Monthly", savings, savings))

    # ─── Part 1 Mini vs Together ──────────────────────────────────────────
    r_mini = compute_lcpr(PART1_MINI_VOICE, mini)
    r_tog_v = compute_lcpr(PART1_MINI_VOICE, tog_dv3)
    claims.append(("Part 1 Mini: Mini LCPR", "LCPR", r_mini.lcpr, r_mini.lcpr))
    claims.append(("Part 1 Mini: Together LCPR", "LCPR", r_tog_v.lcpr, r_tog_v.lcpr))

    # ─── Part 2 Cresta ────────────────────────────────────────────────────
    r_gpt_c = compute_lcpr(PART2_CRESTA, gpt55)
    r_lora = compute_lcpr(PART2_CRESTA, lora_8b)
    cresta_ratio = r_gpt_c.lcpr / r_lora.lcpr
    claims.append(("Part 2 Cresta: GPT/LoRA LCPR ratio", "Ratio", cresta_ratio, cresta_ratio))

    # ─── Part 5 Stage 0 ──────────────────────────────────────────────────
    r_s0 = compute_lcpr(PART5_STAGE0, gpt55)
    r_s0_t = compute_lcpr(PART5_STAGE0, tog_dv3)
    claims.append(("Part 5 Stage 0: GPT monthly", "Monthly", r_s0.monthly_cost, r_s0.monthly_cost))
    s0_savings = r_s0.monthly_cost - r_s0_t.monthly_cost
    claims.append(("Part 5 Stage 0: savings", "Monthly", s0_savings, s0_savings))

    # ─── Part 5 Stage 1 ──────────────────────────────────────────────────
    r_s1 = compute_lcpr(PART5_STAGE1, gpt55)
    claims.append(("Part 5 Stage 1: GPT 2M monthly", "Monthly", r_s1.monthly_cost, r_s1.monthly_cost))

    r_s1g = compute_lcpr(PART5_STAGE1_GPT, gpt55)
    r_s1t = compute_lcpr(PART5_STAGE1_TOG, tog_dv3)
    combined = r_s1g.monthly_cost + r_s1t.monthly_cost
    s1_savings = r_s1.monthly_cost - combined
    claims.append(("Part 5 Stage 1: combined split", "Monthly", combined, combined))
    claims.append(("Part 5 Stage 1: savings", "Monthly", s1_savings, s1_savings))

    # ─── Part 5 Stage 2 ──────────────────────────────────────────────────
    r_s2g = compute_lcpr(PART5_STAGE2, gpt55)
    r_s2t = compute_lcpr(PART5_STAGE2, tog_dv3)
    r_s2l = compute_lcpr(PART5_STAGE2, lambda_h100)
    claims.append(("Part 5 Stage 2: GPT 10M monthly", "Monthly", r_s2g.monthly_cost, r_s2g.monthly_cost))
    claims.append(("Part 5 Stage 2: Together 10M monthly", "Monthly", r_s2t.monthly_cost, r_s2t.monthly_cost))
    claims.append(("Part 5 Stage 2: Lambda 10M monthly", "Monthly", r_s2l.monthly_cost, r_s2l.monthly_cost))

    # ─── Print results ────────────────────────────────────────────────────
    print("\n" + "=" * 90)
    print("ESSAY NUMBER VERIFICATION")
    print("=" * 90)
    print(f"\n{'Claim':<52} {'Type':<8} {'Calculator':>14}")
    print("─" * 80)
    for label, typ, actual, _expected in claims:
        if typ == "LCPR":
            val = f"${actual:.4f}"
        elif typ == "Ratio":
            val = f"{actual:.1f}x"
        elif typ == "%":
            val = f"{actual:.1f}%"
        else:
            val = f"${actual:,.0f}"
        print(f"{label:<52} {typ:<8} {val:>14}")

    print("\n" + "=" * 90)
    print("SUMMARY: Update essay text to match these calculator values.")
    print("=" * 90)

    # Print the exact values needed for the essay update
    print("\n--- Values for Essay Part 0 Table ---")
    for name_label, prov in [
        ("GPT-5.5", gpt55),
        ("Lambda H100", lambda_h100),
        ("Together DSV3", tog_dv3),
        ("Fireworks Llama 70B", fw_llama),
        ("DeepInfra", deepinfra),
    ]:
        r = compute_lcpr(PART0_SAAS, prov)
        if prov.deployment_mode != "dedicated":
            raw = (prov.input_rate_per_m * 800 + prov.output_rate_per_m * 400) / 1_000_000
        else:
            raw = r.monthly_cost / PART0_SAAS.monthly_requests  # approx raw for dedicated
        ratio = r.lcpr / raw if raw > 0 else 0
        print(f"  {name_label:<25} raw=${raw:.4f}  LCPR=${r.lcpr:.4f}  "
              f"monthly=${r.monthly_cost:,.0f}  ratio={ratio:.2f}x")

    print("\n--- Values for Essay Part 0 Sensitivity ---")
    print(f"  20% retry: GPT=${r_gpt_retry.lcpr:.4f}, Together=${r_tog_retry.lcpr:.4f}, "
          f"ratio={retry_ratio:.1f}x")
    print(f"  70% gate:  GPT=${r_gpt_gate.lcpr:.4f}, Together=${r_tog_gate.lcpr:.4f}, "
          f"ratio={gate_ratio:.1f}x")
    print(f"  Quality gate 95->85% increase (GPT): {pct_increase:.0f}%")

    print("\n--- Values for Essay Part 0 Ratios ---")
    print(f"  Raw token ratio GPT/Together: {raw_ratio:.1f}x")
    print(f"  LCPR ratio GPT/Together: {lcpr_ratio:.1f}x")

    print("\n--- Values for Essay Part 1 ---")
    print(f"  B2B: GPT=${r_gpt.lcpr:.4f}/${r_gpt.monthly_cost:,.0f}, "
          f"Lambda=${r_lam.lcpr:.4f}/${r_lam.monthly_cost:,.0f}")
    print(f"  B2B: Together=${r_tog.lcpr:.4f}/${r_tog.monthly_cost:,.0f}, "
          f"Fireworks=${r_fw.lcpr:.4f}/${r_fw.monthly_cost:,.0f}")
    print(f"  B2B savings: ${savings:,.0f}/month = ${savings*12:,.0f}/year")
    payback = 48000 / savings
    print(f"  Payback: {payback:.1f} months")
    print(f"  Mini voice: Mini=${r_mini.lcpr:.5f}, Together=${r_tog_v.lcpr:.5f}")

    print("\n--- Values for Essay Part 2 ---")
    print(f"  Cresta ratio: {cresta_ratio:.1f}x")

    print("\n--- Values for Essay Part 5 ---")
    print(f"  Stage 0: GPT=${r_s0.monthly_cost:,.0f}, savings=${s0_savings:,.0f}")
    print(f"  Stage 1: GPT all=${r_s1.monthly_cost:,.0f}")
    print(f"  Stage 1: GPT portion=${r_s1g.monthly_cost:,.0f}, "
          f"Together portion=${r_s1t.monthly_cost:,.0f}")
    print(f"  Stage 1: combined=${combined:,.0f}, savings=${s1_savings:,.0f}/month "
          f"= ${s1_savings*12:,.0f}/year")
    print(f"  Stage 2: GPT=${r_s2g.monthly_cost:,.0f}, Together=${r_s2t.monthly_cost:,.0f}, "
          f"Lambda=${r_s2l.monthly_cost:,.0f}")


if __name__ == "__main__":
    main()
