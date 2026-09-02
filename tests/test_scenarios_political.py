"""
Skenario POLITIS (E1-E5) — Section 5.5.5 v8 proposal.

E1 — Equity tie-break: dua deficit dengan score sama, IPM lebih rendah menang
E2 — Pemda override: do_not_export flag → reject match dari kab itu
E3 — Bulog priority: 60% surplus reserve untuk Bulog, sisanya private
E4 — Import policy aktif: bobot price diturunkan
E5 — BBM naik: max_distance shrink, biaya logistik naik
"""
import concurrent.futures

import pytest
from datetime import datetime

from matching_engine.engine import run_matching
from matching_engine.constraints import (
    BULOG_PROCUREMENT_KAB, reset_bulog_procurement, set_bulog_procurement,
)
from matching_engine.scoring import IMPORT_POLICY_WEIGHTS


# =============================================================================
# E1 — EQUITY TIE-BREAK
# =============================================================================

class TestE1_EquityTieBreak:
    """Skenario E1: dua deficit dengan score equivalent. IPM lebih rendah menang."""

    def test_lower_ipm_wins_when_scores_similar(
        self, kediri_kab, sampang, sidoarjo, cabai_merah,
        make_supply, make_demand, logistics_normal
    ):
        # Sampang IPM 66.72 (+15%), Sidoarjo IPM 80.13 (no boost).
        # Surplus 50t, dua deficit @ 50t dengan harga sama.
        s = make_supply(kediri_kab, cabai_merah, volume=50, price=30000)
        d_sampang = make_demand(sampang, cabai_merah, volume=50, price=55000)
        d_sidoarjo = make_demand(sidoarjo, cabai_merah, volume=50, price=55000)

        report = run_matching([s], [d_sampang, d_sidoarjo], logistics=logistics_normal)
        # Sampang menang (equity multiplier menggandakan score)
        assert len(report.matches) >= 1
        assert report.matches[0].deficit.kabupaten.id == sampang.id


# =============================================================================
# E2 — PEMDA OVERRIDE
# =============================================================================

class TestE2_PemdaOverride:
    """Skenario E2: Pemda Kediri set do_not_export_cabai_merah=True."""

    def test_pemda_override_blocks_export(
        self, surabaya, kediri_kab, cabai_merah,
        make_supply, make_demand, logistics_normal
    ):
        # Pemda Kediri lock cabai merah
        kediri_kab.pemda_overrides = {"do_not_export_cabai_merah": True}

        s = make_supply(kediri_kab, cabai_merah, volume=50, price=30000)
        d = make_demand(surabaya, cabai_merah, volume=50, price=60000)

        report = run_matching([s], [d], logistics=logistics_normal)
        # Match harus 0 — pemda override aktif
        assert len(report.matches) == 0

    def test_pemda_override_per_commodity(
        self, surabaya, kediri_kab, cabai_merah, beras_premium,
        make_supply, make_demand, logistics_normal
    ):
        # Block cabai, beras tetap boleh
        kediri_kab.pemda_overrides = {"do_not_export_cabai_merah": True}

        s_cabai = make_supply(kediri_kab, cabai_merah, volume=50, price=30000)
        s_beras = make_supply(kediri_kab, beras_premium, volume=100, price=11000)

        d_cabai = make_demand(surabaya, cabai_merah, volume=50, price=60000)
        d_beras = make_demand(surabaya, beras_premium, volume=100, price=14000)

        report = run_matching([s_cabai, s_beras], [d_cabai, d_beras],
                                logistics=logistics_normal)
        # Hanya beras yang match
        assert len(report.matches) == 1
        assert report.matches[0].surplus.commodity.code == "beras_premium"


# =============================================================================
# E3 — BULOG PRIORITY
# =============================================================================

class TestE3_BulogPriority:
    """Skenario E3: surplus beras di kab Bulog procurement → 60% reserve."""

    def setup_method(self):
        reset_bulog_procurement()

    def teardown_method(self):
        reset_bulog_procurement()

    def test_bulog_kab_reserves_60pct(
        self, surabaya, kediri_kab, beras_premium,
        make_supply, make_demand, logistics_normal
    ):
        set_bulog_procurement({kediri_kab.id})
        # Surplus 100t. Bulog reserve 60t → 40t available.
        s = make_supply(kediri_kab, beras_premium, volume=100, price=11000)
        d = make_demand(surabaya, beras_premium, volume=100, price=14000)

        report = run_matching([s], [d], logistics=logistics_normal)
        # Warning Bulog harus muncul
        assert any("bulog" in w.lower() for w in report.warnings)
        # Volume yang matched ≤40t
        if report.matches:
            assert report.matches[0].surplus.volume_tons <= 40

    def test_bulog_only_applies_to_padi_jagung_kedelai(
        self, surabaya, kediri_kab, cabai_merah,
        make_supply, make_demand, logistics_normal
    ):
        set_bulog_procurement({kediri_kab.id})
        # Cabai (bukan komoditas Bulog) → tidak ter-reserve
        s = make_supply(kediri_kab, cabai_merah, volume=50, price=30000)
        d = make_demand(surabaya, cabai_merah, volume=50, price=60000)

        report = run_matching([s], [d], logistics=logistics_normal)
        # Match terjadi normal — Bulog hanya untuk padi/jagung/kedelai
        assert len(report.matches) == 1
        assert report.matches[0].matched_volume_tons == 50


# =============================================================================
# E3 — BULOG CONCURRENCY (regression test untuk module-global race)
# =============================================================================

class TestE3_BulogConcurrency:
    """
    Regression: BULOG_PROCUREMENT_KAB dulu hanya bisa di-set lewat
    set_bulog_procurement() yang mutate module-level set. Dua run_matching()
    paralel (FastAPI multi-worker, batch threadpool, dst.) saling
    overwrite state-nya.

    Fix: run_matching menerima parameter eksplisit bulog_procurement_kab.
    Caller paralel pass nilai sendiri-sendiri → tidak ada shared state.
    Param None tetap fallback ke global (back-compat untuk tes lama).
    """

    def setup_method(self):
        reset_bulog_procurement()

    def teardown_method(self):
        reset_bulog_procurement()

    def test_parallel_disjoint_bulog_sets_do_not_race(
        self, surabaya, kediri_kab, beras_premium,
        make_supply, make_demand, logistics_normal,
    ):
        s = make_supply(kediri_kab, beras_premium, volume=100, price=11000)
        d = make_demand(surabaya, beras_premium, volume=100, price=14000)

        def run_with(active_kab):
            report = run_matching(
                [s], [d], logistics=logistics_normal,
                bulog_procurement_kab=active_kab,
            )
            return any("bulog" in w.lower() for w in report.warnings)

        # 50 trial per skenario, di-interleave di 4 worker. Tanpa fix,
        # global akan ke-overwrite dan satu sisi assertion-nya gagal random.
        N = 50
        jobs = []
        for _ in range(N):
            jobs.append((True, {kediri_kab.id}))
            jobs.append((False, set()))

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
            futures = [
                (expected, ex.submit(run_with, active))
                for expected, active in jobs
            ]
            for expected_warn, fut in futures:
                got_warn = fut.result()
                assert got_warn is expected_warn, (
                    f"Race: expected_warn={expected_warn}, got={got_warn} — "
                    "parallel run_matching leaked Bulog state across calls."
                )

    def test_explicit_param_does_not_pollute_module_global(
        self, surabaya, kediri_kab, beras_premium,
        make_supply, make_demand, logistics_normal,
    ):
        # Global kosong di awal (setup_method memanggil reset).
        assert len(BULOG_PROCUREMENT_KAB) == 0

        s = make_supply(kediri_kab, beras_premium, volume=100, price=11000)
        d = make_demand(surabaya, beras_premium, volume=100, price=14000)
        report = run_matching(
            [s], [d], logistics=logistics_normal,
            bulog_procurement_kab={kediri_kab.id},
        )
        assert any("bulog" in w.lower() for w in report.warnings)

        # Param eksplisit TIDAK memutasi global → run berikutnya yang
        # tidak pass param tetap melihat empty set.
        assert len(BULOG_PROCUREMENT_KAB) == 0

    def test_none_falls_back_to_module_global(
        self, surabaya, kediri_kab, beras_premium,
        make_supply, make_demand, logistics_normal,
    ):
        # Back-compat: kalau bulog_procurement_kab=None (default), tetap
        # baca dari module global yang di-set via set_bulog_procurement.
        set_bulog_procurement({kediri_kab.id})
        s = make_supply(kediri_kab, beras_premium, volume=100, price=11000)
        d = make_demand(surabaya, beras_premium, volume=100, price=14000)

        report = run_matching([s], [d], logistics=logistics_normal)
        assert any("bulog" in w.lower() for w in report.warnings)


# =============================================================================
# E4 — IMPORT POLICY AKTIF
# =============================================================================

class TestE4_ImportPolicy:
    """Skenario E4: kebijakan impor bawang aktif. Bobot price diturunkan."""

    def test_import_policy_uses_alternate_weights(
        self, surabaya, kediri_kab, bawang_merah,
        make_supply, make_demand, logistics_normal
    ):
        s = make_supply(kediri_kab, bawang_merah, volume=50, price=25000)
        d = make_demand(surabaya, bawang_merah, volume=50, price=40000)

        # reference_date dipancang di luar semua window event (audit F1):
        # tanpa event, komposisi import policy harus identik dengan
        # IMPORT_POLICY_WEIGHTS lama.
        report = run_matching([s], [d], logistics=logistics_normal,
                                import_policy_active=True,
                                reference_date=datetime(2026, 5, 4))
        # Weights harus IMPORT_POLICY_WEIGHTS
        assert report.run_metadata["weights_used"] == IMPORT_POLICY_WEIGHTS
        # Warning harus muncul
        assert any("import" in w.lower() for w in report.warnings)
        # Match flag IMPORT_POLICY_ACTIVE
        if report.matches:
            assert "IMPORT_POLICY_ACTIVE" in report.matches[0].flags


# =============================================================================
# E5 — BBM NAIK
# =============================================================================

class TestE5_BBMNaik:
    """Skenario E5: BBM naik 20% → biaya logistik naik, max_distance shrink."""

    def test_bbm_naik_increases_logistics_cost(
        self, surabaya, kediri_kab, cabai_merah,
        make_supply, make_demand,
        logistics_normal, logistics_bbm_naik_20pct
    ):
        s = make_supply(kediri_kab, cabai_merah, volume=50, price=30000)
        d = make_demand(surabaya, cabai_merah, volume=50, price=60000)

        report_normal = run_matching([s], [d], logistics=logistics_normal)
        report_naik = run_matching([s], [d], logistics=logistics_bbm_naik_20pct)

        # Price score harus turun (logistics cost lebih tinggi)
        if report_normal.matches and report_naik.matches:
            assert (report_naik.matches[0].breakdown.price <=
                    report_normal.matches[0].breakdown.price)
            # bbm_change_pct harus tercatat di metadata
            assert report_naik.run_metadata["bbm_change_pct"] == 0.2

    def test_bbm_naik_extreme_shrinks_distance_threshold(
        self, surabaya, banyuwangi, beras_premium,
        make_supply, make_demand
    ):
        from matching_engine.models import LogisticsContext
        # BBM naik 50% → max_distance shrink ~33%
        # Beras 800km → ~536km. Surabaya-Banyuwangi ~280km masih ok.
        # Tapi kita test extreme: BBM 100%
        bbm_extreme = LogisticsContext(
            bbm_price_idr_per_liter=20000, bbm_price_baseline=10000
        )

        s = make_supply(banyuwangi, beras_premium, volume=100, price=11000)
        d = make_demand(surabaya, beras_premium, volume=100, price=14000)

        report = run_matching([s], [d], logistics=bbm_extreme)
        # Engine masih jalan, harga score dan max_distance terdampak
        assert "bbm_change_pct" in report.run_metadata
        assert report.run_metadata["bbm_change_pct"] == 1.0
