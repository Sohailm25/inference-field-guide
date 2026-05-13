# ABOUTME: Tests for Derivation 2 (KV sizing) and Derivation 3 (cache break-even).
# ABOUTME: Verifies formulas against book-grade derivation pack specifications.

import math

import pytest

from calculator.lcpr import (
    CacheBreakEvenResult,
    KVSizingResult,
    compute_cache_break_even,
    compute_kv_sizing,
)


class TestCacheBreakEven:
    """Tests for compute_cache_break_even matching Derivation 3."""

    def test_anthropic_5min_break_even(self):
        """Anthropic 5-min cache: write=1.25x, read=0.10x input price.

        N = (1.25*p - 0.10*p) / (p - 0.10*p) = 1.15p / 0.90p = 1.2778
        """
        p_in = 3.00  # $/M input tokens
        result = compute_cache_break_even(
            prefix_tokens=10_000,
            uncached_input_price_per_m=p_in,
            cache_write_price_per_m=1.25 * p_in,
            cache_read_price_per_m=0.10 * p_in,
        )
        assert result.break_even_requests == pytest.approx(1.2778, abs=0.001)

    def test_anthropic_1hr_break_even(self):
        """Anthropic 1-hr cache: write=2.00x, read=0.10x input price.

        N = (2.00*p - 0.10*p) / (p - 0.10*p) = 1.90p / 0.90p = 2.1111
        """
        p_in = 3.00
        result = compute_cache_break_even(
            prefix_tokens=10_000,
            uncached_input_price_per_m=p_in,
            cache_write_price_per_m=2.00 * p_in,
            cache_read_price_per_m=0.10 * p_in,
        )
        assert result.break_even_requests == pytest.approx(2.1111, abs=0.001)

    def test_openai_style_automatic(self):
        """OpenAI automatic caching: write=1.0x, read=0.50x input price.

        N = (1.0*p - 0.50*p) / (p - 0.50*p) = 0.50p / 0.50p = 1.0
        Any cache hit saves money immediately.
        """
        p_in = 2.50
        result = compute_cache_break_even(
            prefix_tokens=10_000,
            uncached_input_price_per_m=p_in,
            cache_write_price_per_m=1.0 * p_in,
            cache_read_price_per_m=0.50 * p_in,
        )
        assert result.break_even_requests == pytest.approx(1.0)

    def test_savings_at_various_n(self):
        """Verify savings_at_n dict at N=1, 5, 10, 100 for Anthropic 5-min."""
        p_in = 3.00
        result = compute_cache_break_even(
            prefix_tokens=10_000,
            uncached_input_price_per_m=p_in,
            cache_write_price_per_m=1.25 * p_in,
            cache_read_price_per_m=0.10 * p_in,
        )
        # Per-token prices
        p_in_tok = p_in / 1_000_000
        p_write_tok = 1.25 * p_in / 1_000_000
        p_read_tok = 0.10 * p_in / 1_000_000
        tokens = 10_000

        # N=1: only write, no reads. savings = tokens * (1*p_in - 1*p_write) = negative
        expected_1 = tokens * (1 * p_in_tok) - tokens * (1 * p_write_tok)
        assert result.savings_at_n[1] == pytest.approx(expected_1, abs=1e-8)

        # N=5: savings = tokens*(5*p_in) - tokens*(1*p_write + 4*p_read)
        expected_5 = tokens * 5 * p_in_tok - tokens * (p_write_tok + 4 * p_read_tok)
        assert result.savings_at_n[5] == pytest.approx(expected_5, abs=1e-8)

        # N=10
        expected_10 = tokens * 10 * p_in_tok - tokens * (p_write_tok + 9 * p_read_tok)
        assert result.savings_at_n[10] == pytest.approx(expected_10, abs=1e-8)

        # N=100
        expected_100 = tokens * 100 * p_in_tok - tokens * (p_write_tok + 99 * p_read_tok)
        assert result.savings_at_n[100] == pytest.approx(expected_100, abs=1e-8)

    def test_zero_storage_cost(self):
        """When storage_price=0 and storage_hours=0, same as basic formula."""
        p_in = 3.00
        result = compute_cache_break_even(
            prefix_tokens=10_000,
            uncached_input_price_per_m=p_in,
            cache_write_price_per_m=1.25 * p_in,
            cache_read_price_per_m=0.10 * p_in,
            storage_price_per_m_hour=0.0,
            storage_hours=0.0,
        )
        assert result.storage_cost == 0.0
        assert result.break_even_requests == pytest.approx(1.2778, abs=0.001)

    def test_nonzero_storage_cost(self):
        """Storage cost increases the break-even threshold."""
        p_in = 3.00
        result_no_storage = compute_cache_break_even(
            prefix_tokens=10_000,
            uncached_input_price_per_m=p_in,
            cache_write_price_per_m=1.25 * p_in,
            cache_read_price_per_m=0.10 * p_in,
        )
        result_with_storage = compute_cache_break_even(
            prefix_tokens=10_000,
            uncached_input_price_per_m=p_in,
            cache_write_price_per_m=1.25 * p_in,
            cache_read_price_per_m=0.10 * p_in,
            storage_price_per_m_hour=0.50,
            storage_hours=1.0,
        )
        assert result_with_storage.storage_cost > 0
        assert result_with_storage.break_even_requests > result_no_storage.break_even_requests

    def test_large_prefix_100k(self):
        """Savings scale linearly with prefix size."""
        p_in = 3.00
        result_10k = compute_cache_break_even(
            prefix_tokens=10_000,
            uncached_input_price_per_m=p_in,
            cache_write_price_per_m=1.25 * p_in,
            cache_read_price_per_m=0.10 * p_in,
        )
        result_100k = compute_cache_break_even(
            prefix_tokens=100_000,
            uncached_input_price_per_m=p_in,
            cache_write_price_per_m=1.25 * p_in,
            cache_read_price_per_m=0.10 * p_in,
        )
        # Break-even N is the same (independent of prefix size)
        assert result_100k.break_even_requests == pytest.approx(
            result_10k.break_even_requests, abs=0.001
        )
        # But savings at N=10 are 10x larger
        assert result_100k.savings_at_n[10] == pytest.approx(
            result_10k.savings_at_n[10] * 10, abs=1e-6
        )

    def test_read_equals_uncached_inf(self):
        """When read price equals uncached price, break-even is infinite."""
        p_in = 3.00
        result = compute_cache_break_even(
            prefix_tokens=10_000,
            uncached_input_price_per_m=p_in,
            cache_write_price_per_m=1.25 * p_in,
            cache_read_price_per_m=p_in,  # read == uncached
        )
        assert result.break_even_requests == float("inf")

    def test_always_beneficial(self):
        """When write < read, caching is always beneficial (break_even < 0)."""
        p_in = 3.00
        result = compute_cache_break_even(
            prefix_tokens=10_000,
            uncached_input_price_per_m=p_in,
            cache_write_price_per_m=0.05 * p_in,  # write cheaper than read
            cache_read_price_per_m=0.10 * p_in,
        )
        assert result.break_even_requests < 0

    def test_negative_prefix_raises(self):
        with pytest.raises(ValueError, match="prefix_tokens must be >= 0"):
            compute_cache_break_even(
                prefix_tokens=-1,
                uncached_input_price_per_m=3.00,
                cache_write_price_per_m=3.75,
                cache_read_price_per_m=0.30,
            )

    def test_zero_prefix(self):
        """Zero prefix: formula result but all savings are 0."""
        result = compute_cache_break_even(
            prefix_tokens=0,
            uncached_input_price_per_m=3.00,
            cache_write_price_per_m=3.75,
            cache_read_price_per_m=0.30,
        )
        for n_val in (1, 5, 10, 100):
            assert result.savings_at_n[n_val] == pytest.approx(0.0)

    def test_real_pricing_anthropic_sonnet(self):
        """Real Anthropic Sonnet pricing: $3.00/M input, $3.75/M write, $0.30/M read."""
        result = compute_cache_break_even(
            prefix_tokens=50_000,
            uncached_input_price_per_m=3.00,
            cache_write_price_per_m=3.75,
            cache_read_price_per_m=0.30,
        )
        assert isinstance(result, CacheBreakEvenResult)
        assert result.prefix_tokens == 50_000
        assert result.break_even_requests == pytest.approx(1.2778, abs=0.001)
        # At N=10, significant savings
        assert result.savings_at_n[10] > 0


class TestKVSizing:
    """Tests for compute_kv_sizing matching Derivation 2."""

    def test_llama3_70b_bf16(self):
        """Llama 3 70B: 80 layers, 8 KV heads, 128 dim, bf16 (2 bytes).

        kv_per_token = 2 * 80 * 8 * 128 * 2 = 327,680 bytes = 320 KiB
        """
        result = compute_kv_sizing(
            n_layers=80,
            n_kv_heads=8,
            head_dim=128,
            element_bytes=2,
            kv_pool_bytes=40e9,
            resident_tokens=4096,
        )
        assert result.kv_bytes_per_token == 327_680
        assert result.kv_bytes_per_token == 320 * 1024  # 320 KiB

    def test_llama3_8b_bf16(self):
        """Llama 3 8B: 32 layers, 8 KV heads, 128 dim, bf16 (2 bytes).

        kv_per_token = 2 * 32 * 8 * 128 * 2 = 131,072 bytes = 128 KiB
        """
        result = compute_kv_sizing(
            n_layers=32,
            n_kv_heads=8,
            head_dim=128,
            element_bytes=2,
            kv_pool_bytes=40e9,
            resident_tokens=4096,
        )
        assert result.kv_bytes_per_token == 131_072
        assert result.kv_bytes_per_token == 128 * 1024

    def test_gqa_vs_mha(self):
        """GQA (8 KV heads) vs MHA (64 KV heads): 8x memory difference."""
        gqa = compute_kv_sizing(
            n_layers=80, n_kv_heads=8, head_dim=128, element_bytes=2,
            kv_pool_bytes=40e9, resident_tokens=4096,
        )
        mha = compute_kv_sizing(
            n_layers=80, n_kv_heads=64, head_dim=128, element_bytes=2,
            kv_pool_bytes=40e9, resident_tokens=4096,
        )
        assert mha.kv_bytes_per_token == 8 * gqa.kv_bytes_per_token
        assert mha.total_kv_memory_per_seq == 8 * gqa.total_kv_memory_per_seq

    def test_fp8_quantized(self):
        """FP8 quantized (element_bytes=1) halves KV memory vs bf16."""
        bf16 = compute_kv_sizing(
            n_layers=80, n_kv_heads=8, head_dim=128, element_bytes=2,
            kv_pool_bytes=40e9, resident_tokens=4096,
        )
        fp8 = compute_kv_sizing(
            n_layers=80, n_kv_heads=8, head_dim=128, element_bytes=1,
            kv_pool_bytes=40e9, resident_tokens=4096,
        )
        assert fp8.kv_bytes_per_token == bf16.kv_bytes_per_token / 2

    def test_max_sequences_short_context(self):
        """4096 tokens, 40GB pool → many sequences."""
        result = compute_kv_sizing(
            n_layers=80, n_kv_heads=8, head_dim=128, element_bytes=2,
            kv_pool_bytes=40e9, resident_tokens=4096,
            headroom_fraction=0.1,
        )
        # kv_per_token = 327,680; total per seq = 327680 * 4096 = 1,342,177,280
        # usable pool = 40e9 * 0.9 = 36e9
        # max_seqs = floor(36e9 / 1,342,177,280) = floor(26.82) = 26
        assert result.max_live_sequences == 26

    def test_max_sequences_long_context_128k(self):
        """128K tokens, 40GB pool → very few sequences."""
        result = compute_kv_sizing(
            n_layers=80, n_kv_heads=8, head_dim=128, element_bytes=2,
            kv_pool_bytes=40e9, resident_tokens=131072,
            headroom_fraction=0.1,
        )
        # total per seq = 327680 * 131072 = 42,949,672,960
        # usable = 36e9
        # max_seqs = floor(36e9 / 42,949,672,960) = floor(0.838) = 0
        assert result.max_live_sequences == 0

    def test_headroom_effect(self):
        """0% vs 10% vs 20% headroom changes max sequences."""
        args = dict(
            n_layers=80, n_kv_heads=8, head_dim=128, element_bytes=2,
            kv_pool_bytes=40e9, resident_tokens=4096,
        )
        r0 = compute_kv_sizing(**args, headroom_fraction=0.0)
        r10 = compute_kv_sizing(**args, headroom_fraction=0.1)
        r20 = compute_kv_sizing(**args, headroom_fraction=0.2)
        assert r0.max_live_sequences >= r10.max_live_sequences >= r20.max_live_sequences
        # With 0% headroom, more sequences than 10%
        assert r0.max_live_sequences > r20.max_live_sequences

    def test_context_at_weight_parity(self):
        """Llama 70B bf16 weights = 140GB. KV parity at ~427K tokens."""
        result = compute_kv_sizing(
            n_layers=80, n_kv_heads=8, head_dim=128, element_bytes=2,
            kv_pool_bytes=40e9, resident_tokens=4096,
            weight_bytes=140e9,
        )
        # parity = 140e9 / 327680 = 427,246.09 → floor = 427,246
        expected = int(140e9 / 327_680)
        assert result.context_length_at_weight_parity == expected

    def test_zero_pool_raises(self):
        with pytest.raises(ValueError, match="kv_pool_bytes must be > 0"):
            compute_kv_sizing(
                n_layers=80, n_kv_heads=8, head_dim=128, element_bytes=2,
                kv_pool_bytes=0, resident_tokens=4096,
            )

    def test_zero_layers_raises(self):
        with pytest.raises(ValueError, match="n_layers must be > 0"):
            compute_kv_sizing(
                n_layers=0, n_kv_heads=8, head_dim=128, element_bytes=2,
                kv_pool_bytes=40e9, resident_tokens=4096,
            )

    def test_zero_kv_heads_raises(self):
        with pytest.raises(ValueError, match="n_kv_heads must be > 0"):
            compute_kv_sizing(
                n_layers=80, n_kv_heads=0, head_dim=128, element_bytes=2,
                kv_pool_bytes=40e9, resident_tokens=4096,
            )

    def test_single_sequence(self):
        """Pool barely fits one sequence."""
        # kv_per_token = 327680, at 4096 tokens → 1,342,177,280 bytes per seq
        # Pool = 1.5 billion bytes, headroom 0% → floor(1.5e9/1.342e9) = 1
        result = compute_kv_sizing(
            n_layers=80, n_kv_heads=8, head_dim=128, element_bytes=2,
            kv_pool_bytes=1.5e9, resident_tokens=4096,
            headroom_fraction=0.0,
        )
        assert result.max_live_sequences == 1
