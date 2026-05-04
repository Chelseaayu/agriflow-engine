"""
Skenario TEMPORAL (C1-C3) — Section 5.5.5 v8 proposal.

C1 — Ramadan/Idul Fitri spike: H-14 sebelum lebaran, bobot perishability & price naik
C2 — Pasca panen raya: oversupply musiman, harga drop
C3 — Stale data: data >24 jam → confidence di-downgrade
"""
from datetime import datetime, timedelta

import pytest

from matching_engine.engine import is_ramadan_proximity, run_matching
from matching_engine.scoring import RAMADAN_WEIGHTS


# =============================================================================
# C1 — RAMADAN SPIKE
# =============================================================================

class TestC1_RamadanSpike:
    """Skenario C1: pre-Idul Fitri H-14, bobot disesuaikan."""

    def test_ramadan_proximity_2026_detected(self):
        """Idul Fitri 2026 tanggal 20 Maret. H-14 = 6 Maret."""
        date_h14 = datetime(2026, 3, 6)
        assert is_ramadan_proximity(date_h14) is True

    def test_ramadan_proximity_2027_detected(self):
        """Idul Fitri 2027 ~9 Maret. H-14 = 23 Februari."""
        date_h14 = datetime(2027, 2, 23)
        assert is_ramadan_proximity(date_h14) is True

    def test_outside_window_not_ramadan(self):
        """Tanggal 1 Januari 2026 tidak dalam window."""
        date_normal = datetime(2026, 1, 1)
        assert is_ramadan_proximity(date_normal) is False

    def test_ramadan_active_uses_ramadan_weights(
        self, surabaya, kediri_kab, cabai_merah,
        make_supply, make_demand, logistics_ramadan
    ):
        s = make_supply(kediri_kab, cabai_merah, volume=50, price=30000)
        d = make_demand(surabaya, cabai_merah, volume=50, price=70000)  # spike price

        report = run_matching([s], [d], logistics=logistics_ramadan)
        # Engine harus log warning tentang Ramadan mode
        assert any("ramadan" in w.lower() or "fitri" in w.lower() for w in report.warnings)
        # Metadata harus catat ramadan_active
        assert report.run_metadata.get("ramadan_active") is True
        # Weights yang dipakai = RAMADAN_WEIGHTS
        assert report.run_metadata["weights_used"] == RAMADAN_WEIGHTS
        # Match tetap terjadi & di-flag
        if report.matches:
            assert "RAMADAN_SPIKE" in report.matches[0].flags


# =============================================================================
# C2 — PASCA PANEN RAYA (oversupply)
# =============================================================================

class TestC2_PostHarvest:
    """
    Skenario C2: pasca panen raya padi (Maret-April).
    Multiple kab surplus beras, harga drop. Engine harus tetap match efficiently.
    """

    def test_oversupply_handled_by_greedy(
        self, surabaya, gresik, sidoarjo,
        beras_premium, make_supply, make_demand, logistics_normal
    ):
        # Multiple sentra surplus beras dengan harga rendah
        from matching_engine.models import Kabupaten, Tier
        ngawi = Kabupaten(id="3521", nama="Ngawi", latitude=-7.4042, longitude=111.4467,
                          ipm=72.50, tier=Tier.MEDIUM)
        bojonegoro = Kabupaten(id="3522", nama="Bojonegoro", latitude=-7.1500, longitude=111.8853,
                                ipm=71.80, tier=Tier.MEDIUM)
        tuban = Kabupaten(id="3523", nama="Tuban", latitude=-6.8979, longitude=112.0639,
                           ipm=70.95, tier=Tier.MEDIUM)
        lamongan = Kabupaten(id="3524", nama="Lamongan", latitude=-7.1175, longitude=112.4170,
                              ipm=74.05, tier=Tier.MEDIUM)

        # Surplus dari 4 sentra padi
        surplus = [
            make_supply(ngawi, beras_premium, volume=300, price=10500),
            make_supply(bojonegoro, beras_premium, volume=250, price=10500),
            make_supply(tuban, beras_premium, volume=200, price=10800),
            make_supply(lamongan, beras_premium, volume=180, price=10800),
        ]
        # Pasar besar absorb sebagian
        deficit = [
            make_demand(surabaya, beras_premium, volume=400, price=14000),
            make_demand(gresik, beras_premium, volume=150, price=14000),
            make_demand(sidoarjo, beras_premium, volume=200, price=14000),
        ]

        report = run_matching(surplus, deficit, logistics=logistics_normal)
        # Multiple match harus terjadi
        assert len(report.matches) >= 2
        # Latency harus sub-target
        assert report.run_metadata["latency_ms"] < 500


# =============================================================================
# C3 — STALE DATA
# =============================================================================

class TestC3_StaleData:
    """Skenario C3: data >24 jam → flag STALE_DATA_24H, confidence downgrade."""

    def test_stale_supply_flagged(
        self, surabaya, kediri_kab, cabai_merah,
        make_stale_supply, make_demand, logistics_normal
    ):
        # Supply dengan timestamp 48 jam lalu
        s = make_stale_supply(kediri_kab, cabai_merah, hours_old=48,
                               volume=50, price=30000)
        d = make_demand(surabaya, cabai_merah, volume=50, price=60000)

        report = run_matching([s], [d], logistics=logistics_normal)
        # Warning harus muncul
        assert any("stale" in w.lower() for w in report.warnings)
        # Run metadata harus catat
        assert report.run_metadata["stale_data_count"] >= 1
        if report.matches:
            assert "STALE_DATA_24H" in report.matches[0].flags

    def test_fresh_data_no_stale_flag(
        self, surabaya, kediri_kab, cabai_merah,
        make_supply, make_demand, logistics_normal
    ):
        s = make_supply(kediri_kab, cabai_merah, volume=50, price=30000)
        d = make_demand(surabaya, cabai_merah, volume=50, price=60000)

        report = run_matching([s], [d], logistics=logistics_normal)
        if report.matches:
            assert "STALE_DATA_24H" not in report.matches[0].flags
        assert report.run_metadata["stale_data_count"] == 0
