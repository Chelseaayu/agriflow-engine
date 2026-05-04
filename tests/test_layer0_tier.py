"""
Unit tests Layer 0 — Tier Classification.
"""
import pytest
from matching_engine.constraints import determine_tier, TIER_1_KOTA_IHK
from matching_engine.models import Tier


class TestTierClassification:
    def test_kota_surabaya_is_tier1(self):
        assert determine_tier("3578") == Tier.HIGH

    def test_kota_malang_is_tier1(self):
        assert determine_tier("3573") == Tier.HIGH

    def test_kota_kediri_is_tier1(self):
        assert determine_tier("3571") == Tier.HIGH

    def test_kota_madiun_is_tier1(self):
        assert determine_tier("3577") == Tier.HIGH

    def test_kota_probolinggo_is_tier1(self):
        assert determine_tier("3574") == Tier.HIGH

    def test_banyuwangi_is_tier1(self):
        assert determine_tier("3510") == Tier.HIGH

    def test_sumenep_is_tier1(self):
        assert determine_tier("3529") == Tier.HIGH

    def test_jember_is_tier1(self):
        assert determine_tier("3509") == Tier.HIGH

    def test_kabupaten_kediri_is_tier2(self):
        # Kabupaten Kediri (3506) berbeda dengan Kota Kediri (3571)
        assert determine_tier("3506") == Tier.MEDIUM

    def test_sidoarjo_is_tier2(self):
        # Sidoarjo bukan kota IHK meskipun IPM tinggi
        assert determine_tier("3515") == Tier.MEDIUM

    def test_sampang_is_tier2(self):
        assert determine_tier("3527") == Tier.MEDIUM

    def test_pacitan_is_tier2(self):
        assert determine_tier("3501") == Tier.MEDIUM

    def test_kota_batu_is_tier2(self):
        # Kota Batu (3579) bukan kota IHK
        assert determine_tier("3579") == Tier.MEDIUM

    def test_unknown_kabupaten_is_tier2(self):
        # Default fallback untuk kab yang tidak dikenali
        assert determine_tier("9999") == Tier.MEDIUM

    def test_tier1_count_is_8(self):
        """8 kota IHK Jawa Timur tepat."""
        assert len(TIER_1_KOTA_IHK) == 8

    def test_tier1_set_membership(self):
        expected = {"3578", "3573", "3571", "3577", "3574", "3510", "3529", "3509"}
        assert TIER_1_KOTA_IHK == expected
