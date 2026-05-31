"""
Smoke test: real data pipeline end-to-end
==========================================

Muat surplus_deficit_real.csv -> run_matching -> validasi MatchingReport.

Prinsip:
  - Tidak assert golden numbers (rapuh terhadap perubahan constraints/scoring).
  - Assert structural / behavioral invariants: tidak crash, matches berupa list,
    confidence labels valid, volume tidak negatif, bawang_putih ditangani gracefully.
  - Default surplus_deficit.csv TIDAK digunakan di sini — load_real_data() only.
"""

from __future__ import annotations

import sys
import os
import pathlib

import pytest

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from matching_engine import run_matching, LogisticsContext, Confidence
from sample_data import load_real_data


# ---------------------------------------------------------------------------
# Shared fixture: load real data + run engine once per module
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def real_report():
    """Run engine on real BPS data; shared across all tests in this module."""
    data = load_real_data()
    logistics = LogisticsContext(
        bbm_price_idr_per_liter=10000,
        bbm_price_baseline=10000,
    )
    report = run_matching(
        surplus_nodes=data["surplus"],
        deficit_nodes=data["deficit"],
        logistics=logistics,
        weather_forecasts=data["weather"],
        historical_prices=data["historical_prices"],
    )
    return report


@pytest.fixture(scope="module")
def real_data():
    """Raw data dict from load_real_data()."""
    return load_real_data()


# ---------------------------------------------------------------------------
# P1. Loader: load_real_data() tidak crash dan mengembalikan 6 komoditas
# ---------------------------------------------------------------------------

def test_load_real_data_no_crash(real_data):
    """load_real_data() harus berhasil dan mengisi semua keys."""
    assert "surplus" in real_data
    assert "deficit" in real_data
    assert "kabupaten" in real_data
    assert "komoditas" in real_data


def test_real_data_has_6_commodities(real_data):
    """Harus ada 6 komoditas real: beras_premium, beras_medium, cabai_merah,
    cabai_rawit, bawang_merah, bawang_putih."""
    all_nodes = real_data["surplus"] + real_data["deficit"]
    codes = {n.commodity.code for n in all_nodes}
    expected = {
        "beras_premium", "beras_medium",
        "cabai_merah", "cabai_rawit",
        "bawang_merah", "bawang_putih",
    }
    assert codes == expected, f"Expected 6 real commodity codes, got: {codes}"


def test_real_data_row_counts(real_data):
    """228 baris = 38 kab * 6 komoditas (beras 2 grades) — bagi surplus+deficit."""
    total_nodes = len(real_data["surplus"]) + len(real_data["deficit"])
    assert total_nodes == 228, (
        f"Expected 228 total nodes from real CSV, got {total_nodes}"
    )


def test_load_real_data_does_not_alter_default(real_data):
    """Default load_all_sample_data() harus masih berupa 19-komoditas sintetis —
    dipastikan dengan cek bahwa real_data hanya berisi 6 komoditas."""
    from sample_data import load_all_sample_data
    default_data = load_all_sample_data()
    default_codes = {n.commodity.code for n in default_data["surplus"] + default_data["deficit"]}
    real_codes    = {n.commodity.code for n in real_data["surplus"] + real_data["deficit"]}
    # Default punya lebih banyak komoditas dari real
    assert len(default_codes) > len(real_codes), (
        f"Default data seharusnya punya lebih banyak komoditas dari real. "
        f"default={default_codes}, real={real_codes}"
    )


# ---------------------------------------------------------------------------
# P2. Engine tidak crash pada data real
# ---------------------------------------------------------------------------

def test_engine_does_not_crash(real_report):
    """run_matching pada data real tidak raise exception."""
    assert real_report is not None


def test_report_has_required_fields(real_report):
    """MatchingReport harus punya semua field yang diharapkan."""
    assert hasattr(real_report, "matches")
    assert hasattr(real_report, "unmatched_surplus")
    assert hasattr(real_report, "unmatched_deficit")
    assert hasattr(real_report, "external_opportunities")
    assert hasattr(real_report, "warnings")
    assert hasattr(real_report, "run_metadata")


def test_matches_is_list(real_report):
    """report.matches harus berupa list (bisa kosong tapi tidak None)."""
    assert isinstance(real_report.matches, list)


def test_unmatched_fields_are_lists(real_report):
    """unmatched_surplus dan unmatched_deficit harus list."""
    assert isinstance(real_report.unmatched_surplus, list)
    assert isinstance(real_report.unmatched_deficit, list)


# ---------------------------------------------------------------------------
# P3. Match structural validity
# ---------------------------------------------------------------------------

def test_no_negative_matched_volume(real_report):
    """Semua matched_volume_tons harus > 0."""
    for m in real_report.matches:
        assert m.matched_volume_tons > 0, (
            f"Negative/zero matched_volume: {m.surplus.kabupaten.nama} -> "
            f"{m.deficit.kabupaten.nama} {m.surplus.commodity.code}: "
            f"{m.matched_volume_tons}"
        )


def test_confidence_labels_valid(real_report):
    """Semua confidence harus berupa nilai Confidence enum yang valid."""
    valid_confs = {Confidence.HIGH, Confidence.MEDIUM, Confidence.LOW}
    for m in real_report.matches:
        assert m.confidence in valid_confs, (
            f"Invalid confidence value: {m.confidence!r}"
        )


def test_distance_km_positive(real_report):
    """Semua distance_km pada match harus > 0."""
    for m in real_report.matches:
        assert m.distance_km > 0, (
            f"Non-positive distance_km: {m.surplus.kabupaten.nama} -> "
            f"{m.deficit.kabupaten.nama}: {m.distance_km}"
        )


def test_final_score_positive(real_report):
    """final_score harus positif."""
    for m in real_report.matches:
        assert m.final_score > 0, (
            f"Non-positive final_score: {m.surplus.kabupaten.nama} -> "
            f"{m.deficit.kabupaten.nama}: {m.final_score}"
        )


def test_commodity_codes_same_per_match(real_report):
    """Setiap match (tanpa grade substitution): surplus.commodity == deficit.commodity."""
    for m in real_report.matches:
        if m.flags and "GRADE_SUBSTITUTION" in m.flags:
            continue  # grade sub diizinkan
        assert m.surplus.commodity.code == m.deficit.commodity.code, (
            f"Commodity mismatch in match without GRADE_SUBSTITUTION flag: "
            f"{m.surplus.commodity.code} vs {m.deficit.commodity.code}"
        )


# ---------------------------------------------------------------------------
# P4. bawang_putih all-deficit — engine harus handle gracefully
# ---------------------------------------------------------------------------

def test_bawang_putih_no_surplus_nodes(real_data):
    """Tidak ada surplus node bawang_putih dalam data real."""
    bp_surplus = [s for s in real_data["surplus"] if s.commodity.code == "bawang_putih"]
    assert len(bp_surplus) == 0, (
        f"Expected 0 bawang_putih surplus nodes, got {len(bp_surplus)}"
    )


def test_bawang_putih_zero_matches(real_report):
    """Karena tidak ada surplus bawang_putih, engine harus menghasilkan 0 matches."""
    bp_matches = [
        m for m in real_report.matches
        if m.surplus.commodity.code == "bawang_putih"
        or m.deficit.commodity.code == "bawang_putih"
    ]
    assert len(bp_matches) == 0, (
        f"Expected 0 bawang_putih matches (all-deficit), got {len(bp_matches)}"
    )


def test_bawang_putih_handled_gracefully(real_report):
    """bawang_putih (all-deficit): semua 38 kab Jatim 2022 deficit.
    Engine harus handle gracefully — tidak crash, dan melaporkan bawang_putih
    melalui salah satu channel: warnings, external_opportunities, ATAU
    unmatched_deficit (ketika tidak ada surplus domestik sama sekali).

    Perilaku aktual (post data-prep fix): historical_price_stats.csv menggunakan
    real PIHPS 2022 median (20,750, std 3,518). Harga deficit node 20,750 = median
    -> z=0, tidak ada anomaly exclusion. Tidak ada surplus, jadi engine meletakkan
    semua 38 bawang_putih deficit nodes ke unmatched_deficit.

    Test ini memvalidasi perilaku graceful engine, bukan endpoint output spesifik.
    """
    bp_warnings = [
        w for w in real_report.warnings
        if "bawang_putih" in w.lower() or "Bawang Putih" in w
    ]
    bp_opps = [
        o for o in real_report.external_opportunities
        if "bawang_putih" in o
    ]
    bp_unmatched = [
        d for d in real_report.unmatched_deficit
        if d.commodity.code == "bawang_putih"
    ]
    # Engine harus melaporkan bawang_putih di salah satu channel
    # (warning, external_opp, atau unmatched_deficit — tergantung path engine)
    assert len(bp_warnings) > 0 or len(bp_opps) > 0 or len(bp_unmatched) > 0, (
        "Engine harus melaporkan bawang_putih melalui warnings, "
        "external_opportunities, atau unmatched_deficit — tidak boleh diam. "
        f"warnings={bp_warnings}, opps={bp_opps}, "
        f"unmatched_deficit_count={len(bp_unmatched)}"
    )


def test_bawang_putih_zero_matches_and_no_crash(real_report, real_data):
    """bawang_putih: 0 matches, engine tidak crash.
    Sebab: tidak ada surplus domestik (all-deficit, 38 nodes). Engine reports
    via external_opportunities. Ini dokumentasi engine behavior.
    """
    bp_matches = [
        m for m in real_report.matches
        if m.surplus.commodity.code == "bawang_putih"
        or m.deficit.commodity.code == "bawang_putih"
    ]
    # 0 matches expected (either all-deficit OR price-anomaly-excluded)
    assert len(bp_matches) == 0, (
        f"Expected 0 bawang_putih matches, got {len(bp_matches)}"
    )
    # Engine returned a valid report — tidak crash
    assert real_report is not None


# ---------------------------------------------------------------------------
# P5. Sanity: at least some matches exist for commodities with real surplus
# ---------------------------------------------------------------------------

def test_has_some_matches(real_report):
    """Engine harus menghasilkan setidaknya 1 match dari 5 komoditas yang punya surplus."""
    assert len(real_report.matches) >= 1, (
        "Expected at least 1 match from real data "
        "(5 commodities have surplus: beras, cabai, bawang_merah)"
    )


def test_bawang_merah_has_matches(real_report):
    """bawang_merah punya surplus besar (Nganjuk 190k ton) — harus ada matches."""
    bm_matches = [
        m for m in real_report.matches
        if m.surplus.commodity.code == "bawang_merah"
    ]
    assert len(bm_matches) >= 1, (
        "Expected at least 1 bawang_merah match "
        "(Nganjuk/Probolinggo surplus, many deficit kab)"
    )


def test_beras_has_matches(real_report):
    """beras_premium dan/atau beras_medium punya surplus besar — harus ada matches."""
    beras_matches = [
        m for m in real_report.matches
        if m.surplus.commodity.code in {"beras_premium", "beras_medium"}
    ]
    assert len(beras_matches) >= 1, (
        "Expected at least 1 beras match "
        "(Lamongan/Ngawi/Bojonegoro surplus, Surabaya/kota deficit)"
    )


# ---------------------------------------------------------------------------
# P6. run_metadata integrity
# ---------------------------------------------------------------------------

def test_metadata_latency_present(real_report):
    """run_metadata harus mengandung latency_ms."""
    assert "latency_ms" in real_report.run_metadata
    assert real_report.run_metadata["latency_ms"] >= 0


def test_metadata_total_matches_consistent(real_report):
    """run_metadata['total_matches'] harus konsisten dengan len(report.matches)."""
    assert real_report.run_metadata["total_matches"] == len(real_report.matches)


def test_metadata_candidate_pairs_present(real_report):
    """candidate_pairs_evaluated harus ada dan >= total_matches."""
    meta = real_report.run_metadata
    assert "candidate_pairs_evaluated" in meta
    assert meta["candidate_pairs_evaluated"] >= meta["total_matches"]
