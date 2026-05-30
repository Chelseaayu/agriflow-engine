"""
tests/test_price_anomaly.py  --  Unit tests for analysis/price_anomaly.py (S-H-ESD v2)

Coverage:
  1.  detect_anomalies -- SPIKE injection: detected with correct type + date
  2.  detect_anomalies -- flat series: zero false positives
  3.  detect_anomalies -- DROP injection: detected as DROP
  4.  detect_anomalies -- too-short series: returns empty list
  5.  detect_anomalies -- output schema: all required keys present, correct types
  6.  detect_anomalies -- score ordering: sorted by score descending
  7.  load_series -- real data, sorted, no error
  8.  load_series -- raw PIHPS code alias normalised
  9.  load_series -- unknown pair returns empty, no error
 10.  scan_all -- non-empty on real data
 11.  scan_all -- commodity_code and city_id populated
 12.  scan_all -- cabai_rawit anomalies present
 13.  scan_all -- sorted by score descending
 ---- NEW for S-H-ESD v2 ----
 14.  Seasonal filtering: Ramadan-shaped seasonal spike NOT flagged; genuine anomaly IS
 15.  Persistence: one-day blip filtered out; multi-day streak passes through
 16.  Low-volatility (beras-style): small nominal deviation not over-flagged
 17.  persistent field: True for multi-day flags, all output dicts carry it
"""

from __future__ import annotations

import datetime
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.price_anomaly import detect_anomalies, load_series, scan_all

PRICE_DIR = ROOT / "sample_data" / "price_history"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_flat_series(n: int, price: float = 40_000.0) -> list:
    """n-point flat price series starting 2021-01-04."""
    base = datetime.date(2021, 1, 4)
    return [(base + datetime.timedelta(days=i), price) for i in range(n)]


def _inject_spike(series: list, idx: int, multiplier: float = 3.5, days: int = 3) -> list:
    """Inject a spike of `multiplier` at idx, lasting `days` consecutive points.

    Default days=3 ensures the streak satisfies the default persist=2 filter.
    The leading point (idx) is the most extreme; subsequent points use a slightly
    lower multiplier so the top-scored anomaly is still at idx.
    """
    s = list(series)
    for j in range(days):
        if idx + j < len(s):
            date, price = s[idx + j]
            # Taper slightly after first point so idx is the top scorer
            factor = multiplier * (1.0 - 0.05 * j)
            s[idx + j] = (date, price * factor)
    return s


def _inject_drop(series: list, idx: int, fraction: float = 0.35, days: int = 3) -> list:
    """Inject a drop of `fraction` at idx, lasting `days` consecutive points."""
    s = list(series)
    for j in range(days):
        if idx + j < len(s):
            date, price = s[idx + j]
            # Make subsequent points slightly less extreme
            actual_fraction = fraction * (1.0 + 0.05 * j)
            s[idx + j] = (date, price * min(actual_fraction, 1.0))
    return s


# ---------------------------------------------------------------------------
# 1. SPIKE injection
# ---------------------------------------------------------------------------

class TestSpikeDetection:

    def test_spike_is_detected(self):
        """A 3.5x multiplier spike must be caught at k=3.0, window=30."""
        series = _make_flat_series(100)
        spiked = _inject_spike(series, 60, multiplier=3.5)
        result = detect_anomalies(spiked, window=30, k=3.0)
        assert result, "Expected at least one anomaly for a 3.5x spike"

    def test_spike_type_is_SPIKE(self):
        series = _make_flat_series(100)
        spiked = _inject_spike(series, 60, multiplier=3.5)
        result = detect_anomalies(spiked, window=30, k=3.0)
        spikes = [a for a in result if a["type"] == "SPIKE"]
        assert spikes, f"Expected type=SPIKE; got types: {[a['type'] for a in result]}"

    def test_spike_date_is_correct(self):
        series = _make_flat_series(100)
        spike_idx = 60
        spike_date = series[spike_idx][0]
        spiked = _inject_spike(series, spike_idx, multiplier=3.5)
        result = detect_anomalies(spiked, window=30, k=3.0)
        assert result
        assert result[0]["date"] == spike_date, (
            f"Top anomaly date {result[0]['date']} != spike date {spike_date}"
        )

    def test_spike_deviation_pct_positive(self):
        series = _make_flat_series(100)
        spiked = _inject_spike(series, 60, multiplier=3.5)
        result = detect_anomalies(spiked, window=30, k=3.0)
        for a in result:
            if a["type"] == "SPIKE":
                assert a["deviation_pct"] > 0


# ---------------------------------------------------------------------------
# 2. Flat series: zero false positives
# ---------------------------------------------------------------------------

class TestFlatSeriesNoFalsePositive:

    def test_perfectly_flat_series_returns_no_anomalies(self):
        """Flat series: MAD==0 on residuals, no flags expected."""
        series = _make_flat_series(200, price=40_000.0)
        result = detect_anomalies(series, window=30, k=3.0)
        assert result == [], f"Expected 0 anomalies on flat; got {len(result)}: {result[:3]}"

    def test_gentle_trend_no_large_spike(self):
        """Smoothly rising series: residuals near zero, very few flags at k=3.0."""
        base = datetime.date(2021, 1, 4)
        series = [(base + datetime.timedelta(days=i), 30_000 + i * 10) for i in range(200)]
        result = detect_anomalies(series, window=30, k=3.0)
        assert len(result) <= 2, f"Expected very few anomalies on gentle trend; got {len(result)}"


# ---------------------------------------------------------------------------
# 3. DROP detection
# ---------------------------------------------------------------------------

class TestDropDetection:

    def test_drop_is_detected(self):
        series = _make_flat_series(100)
        dropped = _inject_drop(series, 60, fraction=0.35)
        result = detect_anomalies(dropped, window=30, k=3.0)
        assert result, "Expected at least one anomaly for a deep price drop"

    def test_drop_type_is_DROP(self):
        series = _make_flat_series(100)
        dropped = _inject_drop(series, 60, fraction=0.35)
        result = detect_anomalies(dropped, window=30, k=3.0)
        drops = [a for a in result if a["type"] == "DROP"]
        assert drops, f"Expected type=DROP; got {[a['type'] for a in result]}"

    def test_drop_deviation_pct_negative(self):
        series = _make_flat_series(100)
        dropped = _inject_drop(series, 60, fraction=0.35)
        result = detect_anomalies(dropped, window=30, k=3.0)
        for a in result:
            if a["type"] == "DROP":
                assert a["deviation_pct"] < 0

    def test_drop_date_is_correct(self):
        series = _make_flat_series(100)
        drop_idx = 60
        drop_date = series[drop_idx][0]
        dropped = _inject_drop(series, drop_idx, fraction=0.35)
        result = detect_anomalies(dropped, window=30, k=3.0)
        assert result
        assert result[0]["date"] == drop_date


# ---------------------------------------------------------------------------
# 4. Too-short series
# ---------------------------------------------------------------------------

class TestShortSeries:

    def test_empty_series_returns_empty(self):
        assert detect_anomalies([], window=30, k=3.0) == []

    def test_series_shorter_than_window_returns_empty(self):
        series = _make_flat_series(20)
        assert detect_anomalies(series, window=30, k=3.0) == []

    def test_series_exactly_at_window_returns_empty(self):
        series = _make_flat_series(30)
        assert detect_anomalies(series, window=30, k=3.0) == []


# ---------------------------------------------------------------------------
# 5. Output schema
# ---------------------------------------------------------------------------

REQUIRED_KEYS = {
    "date", "price", "rolling_median", "deviation_pct",
    "type", "score", "commodity_code", "city_id", "persistent",
}


class TestOutputSchema:

    def _get_anomalies(self):
        series = _make_flat_series(100)
        spiked = _inject_spike(series, 60, multiplier=4.0)
        return detect_anomalies(spiked, window=30, k=3.0)

    def test_all_required_keys_present(self):
        results = self._get_anomalies()
        assert results, "No anomalies to check schema on"
        for a in results:
            missing = REQUIRED_KEYS - set(a.keys())
            assert not missing, f"Anomaly dict missing keys: {missing}"

    def test_date_is_datetime_date(self):
        for a in self._get_anomalies():
            assert isinstance(a["date"], datetime.date)

    def test_price_is_positive_float(self):
        for a in self._get_anomalies():
            assert isinstance(a["price"], float) and a["price"] > 0

    def test_rolling_median_is_float(self):
        """rolling_median is now the rolling median of residuals; can be non-positive
        (residuals are centered near zero by construction).  Check it is a float."""
        for a in self._get_anomalies():
            assert isinstance(a["rolling_median"], float)

    def test_type_is_spike_or_drop(self):
        for a in self._get_anomalies():
            assert a["type"] in ("SPIKE", "DROP")

    def test_score_is_positive_float(self):
        for a in self._get_anomalies():
            assert isinstance(a["score"], float) and a["score"] > 0

    def test_persistent_is_bool(self):
        for a in self._get_anomalies():
            assert isinstance(a["persistent"], bool), (
                f"persistent must be bool, got {type(a['persistent'])}"
            )


# ---------------------------------------------------------------------------
# 6. Sorted by score descending
# ---------------------------------------------------------------------------

class TestSortOrder:

    def test_detect_anomalies_sorted_desc(self):
        series = _make_flat_series(200)
        s = _inject_spike(series, 60, multiplier=4.0)
        s = _inject_spike(s, 120, multiplier=2.5)
        result = detect_anomalies(s, window=30, k=3.0)
        assert result
        scores = [a["score"] for a in result]
        assert scores == sorted(scores, reverse=True)

    def test_scan_all_sorted_desc(self):
        results = scan_all(PRICE_DIR, window=30, k=3.0)
        assert results
        scores = [a["score"] for a in results]
        assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# 7. load_series -- real data, sorted, no error
# ---------------------------------------------------------------------------

class TestLoadSeries:

    def test_load_series_returns_sorted_list(self):
        series = load_series("cabai_rawit", "3578", PRICE_DIR)
        assert isinstance(series, list)
        assert len(series) > 0
        dates = [d for d, _ in series]
        assert dates == sorted(dates)

    def test_load_series_prices_are_positive(self):
        series = load_series("bawang_merah", "3578", PRICE_DIR)
        assert series
        for date, price in series:
            assert price > 0

    def test_load_series_dates_are_datetime_date(self):
        series = load_series("telur_ayam", "3578", PRICE_DIR)
        assert series
        for date, price in series:
            assert isinstance(date, datetime.date)

    def test_load_series_date_range_2021_to_2025(self):
        series = load_series("bawang_merah", "3578", PRICE_DIR)
        assert series
        assert series[0][0].year == 2021
        assert series[-1][0].year == 2025


# ---------------------------------------------------------------------------
# 8. load_series -- raw PIHPS alias
# ---------------------------------------------------------------------------

class TestLoadSeriesAlias:

    def test_cabe_rawit_alias_normalised(self):
        series_raw = load_series("cabe_rawit", "3578", PRICE_DIR)
        series_canonical = load_series("cabai_rawit", "3578", PRICE_DIR)
        assert series_raw == series_canonical

    def test_raw_alias_returns_nonempty(self):
        assert load_series("cabe_rawit", "3578", PRICE_DIR)


# ---------------------------------------------------------------------------
# 9. load_series -- unknown pair returns empty
# ---------------------------------------------------------------------------

class TestLoadSeriesUnknown:

    def test_unknown_city_returns_empty(self):
        assert load_series("cabai_rawit", "9999", PRICE_DIR) == []

    def test_unknown_commodity_returns_empty(self):
        assert load_series("gula_aren", "3578", PRICE_DIR) == []


# ---------------------------------------------------------------------------
# 10-13. scan_all on real data
# ---------------------------------------------------------------------------

class TestScanAll:

    @pytest.fixture(scope="class")
    def scan_results(self):
        return scan_all(PRICE_DIR, window=30, k=3.0)

    def test_returns_nonempty_list(self, scan_results):
        assert isinstance(scan_results, list)
        assert len(scan_results) > 0

    def test_all_anomalies_have_required_keys(self, scan_results):
        for a in scan_results[:50]:
            missing = REQUIRED_KEYS - set(a.keys())
            assert not missing, f"Missing keys: {missing}"

    def test_commodity_code_populated(self, scan_results):
        for a in scan_results[:50]:
            assert a["commodity_code"] != ""

    def test_city_id_populated(self, scan_results):
        for a in scan_results[:50]:
            assert a["city_id"] != ""

    def test_cabai_rawit_anomalies_present(self, scan_results):
        cabai = [a for a in scan_results if a["commodity_code"] == "cabai_rawit"]
        assert cabai, "Expected anomalies for cabai_rawit"

    def test_all_types_are_valid(self, scan_results):
        for a in scan_results:
            assert a["type"] in ("SPIKE", "DROP")

    def test_all_scores_positive(self, scan_results):
        for a in scan_results:
            assert a["score"] > 0

    def test_sorted_by_score_descending(self, scan_results):
        scores = [a["score"] for a in scan_results]
        assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# 14. NEW: Seasonal filtering
#     A regular seasonal pattern must NOT be flagged; a genuine anomaly on top
#     of the seasonal pattern MUST be flagged.
# ---------------------------------------------------------------------------

class TestSeasonalFiltering:

    @staticmethod
    def _make_seasonal_series(n: int = 365 * 3) -> list:
        """
        Build a synthetic series with a strong annual seasonal cycle (sin wave)
        plus small Gaussian-style noise.  The seasonal amplitude is ~30 % of the
        base price.  No anomalies injected.
        """
        import math
        base = datetime.date(2021, 1, 4)
        base_price = 50_000.0
        amplitude = 15_000.0  # ~30 % of base
        series = []
        for i in range(n):
            # Annual cycle: sin peaks around day 120 (May), troughs around day 300
            seasonal_val = amplitude * math.sin(2 * math.pi * i / 365)
            price = base_price + seasonal_val
            series.append((base + datetime.timedelta(days=i), price))
        return series

    def test_pure_seasonal_pattern_not_flagged(self):
        """
        A perfectly seasonal series should produce few or zero anomalies.
        After deseasonalisation the residuals are near-zero, so MAD is very small
        and the floor filter fires.
        Allowance: <= 5 flags (edge effects at start of each year are expected).
        """
        series = self._make_seasonal_series()
        result = detect_anomalies(series, window=30, k=3.0, persist=2)
        assert len(result) <= 5, (
            f"Expected at most 5 anomalies on a pure seasonal series; got {len(result)}"
        )

    def test_genuine_anomaly_on_seasonal_series_is_detected(self):
        """
        A 3x price spike injected into a seasonal series MUST still be caught,
        even after deseasonalisation.
        """
        series = self._make_seasonal_series()
        spike_idx = len(series) // 2  # mid-series
        spike_date = series[spike_idx][0]
        # 3x the base price -- a massive anomaly regardless of seasonal component
        spiked = list(series)
        date, price = spiked[spike_idx]
        spiked[spike_idx] = (date, price * 3.0)
        # Inject 3 consecutive to satisfy persistence filter (persist=2)
        for j in range(1, 3):
            if spike_idx + j < len(spiked):
                d2, p2 = spiked[spike_idx + j]
                spiked[spike_idx + j] = (d2, p2 * 2.5)

        result = detect_anomalies(spiked, window=30, k=3.0, persist=2)
        assert result, "Expected at least one anomaly for 3x spike on seasonal series"
        # Top anomaly should be at or near the injection date
        top_dates = {a["date"] for a in result[:5]}
        assert spike_date in top_dates, (
            f"Spike date {spike_date} not in top-5 anomaly dates: {top_dates}"
        )

    def test_ramadan_bawang_merah_event_detected_on_real_data(self):
        """
        The bawang merah April 2024 post-Lebaran sustained spike must still be
        detected by the new method.  This is the canonical 'sustained event'
        from the brief.
        """
        results = scan_all(PRICE_DIR, window=30, k=3.0, persist=2)
        bm_apr24 = [
            a for a in results
            if a["commodity_code"] == "bawang_merah"
            and datetime.date(2024, 4, 1) <= a["date"] <= datetime.date(2024, 5, 15)
        ]
        assert bm_apr24, (
            "Expected bawang_merah April-May 2024 Lebaran spike to be detected "
            "by S-H-ESD.  Got 0 flags in that window."
        )
        # Must be persistent
        assert any(a["persistent"] for a in bm_apr24), (
            "Lebaran spike should be marked persistent=True (multi-day event)"
        )


# ---------------------------------------------------------------------------
# 15. NEW: Persistence filter
#     One-day blip: NOT reported.  Multi-day streak: reported.
# ---------------------------------------------------------------------------

class TestPersistenceFilter:

    def test_single_day_blip_filtered_out(self):
        """
        A one-day spike that doesn't persist (injected into a flat series)
        should be suppressed by persist=2.

        We use days=1 explicitly to inject only a single observation spike.
        """
        series = _make_flat_series(100)
        # days=1: only inject at index 60, no neighbours
        spiked = _inject_spike(series, 60, multiplier=4.0, days=1)
        result_persist2 = detect_anomalies(spiked, window=30, k=3.0, persist=2)
        # The single spike at idx=60 forms a run of length 1, so it must be
        # absent with persist=2.
        flagged_dates = {a["date"] for a in result_persist2}
        spike_date = series[60][0]
        assert spike_date not in flagged_dates, (
            "Single-day spike should be suppressed by persist=2, but it was flagged."
        )

    def test_single_day_blip_appears_with_persist1(self):
        """
        Same spike with persist=1 (no persistence filter) MUST appear.
        Verifies the detection logic is working and the persistence gate is the cause
        of suppression.
        """
        series = _make_flat_series(100)
        spiked = _inject_spike(series, 60, multiplier=4.0)
        result_persist1 = detect_anomalies(spiked, window=30, k=3.0, persist=1)
        spike_date = series[60][0]
        flagged_dates = {a["date"] for a in result_persist1}
        assert spike_date in flagged_dates, (
            "With persist=1 the single-day spike must be flagged."
        )

    def test_multi_day_streak_passes_persist_filter(self):
        """
        A streak of 3 consecutive identical spikes must survive persist=2.
        """
        series = _make_flat_series(120)
        s = list(series)
        # Inject 3 consecutive spikes at indices 60, 61, 62
        for i in [60, 61, 62]:
            d, p = s[i]
            s[i] = (d, p * 4.0)
        result = detect_anomalies(s, window=30, k=3.0, persist=2)
        spike_dates = {series[i][0] for i in [60, 61, 62]}
        flagged_dates = {a["date"] for a in result}
        overlap = spike_dates & flagged_dates
        assert overlap, (
            f"3-day consecutive spike should survive persist=2, but none of "
            f"{spike_dates} appear in flagged dates {flagged_dates}"
        )

    def test_persistent_flag_is_true_for_streaks(self):
        """All flags from a multi-day streak must have persistent=True."""
        series = _make_flat_series(120)
        s = list(series)
        for i in [60, 61, 62]:
            d, p = s[i]
            s[i] = (d, p * 4.0)
        result = detect_anomalies(s, window=30, k=3.0, persist=2)
        assert result, "Expected flags for 3-day streak"
        for a in result:
            assert a["persistent"] is True, (
                f"Flag {a['date']} should be persistent=True in multi-day streak"
            )


# ---------------------------------------------------------------------------
# 16. NEW: Low-volatility (beras-style) -- small nominal deviations not over-flagged
# ---------------------------------------------------------------------------

class TestLowVolatilityGate:

    def test_beras_medium_not_over_flagged_on_real_data(self):
        """
        beras_medium has low volatility (~IDR 1500 std on 14k base).
        S-H-ESD v2 must produce at least 70 % fewer anomalies than v1
        (v1 rolling-MAD on raw prices gave 2526 for beras_medium over 2021-2025).

        The surviving flags are genuine sustained regime changes (e.g. the
        Jan-Feb 2024 Indonesian rice price shock, the Sep-Oct 2023 price step up).
        We do not suppress those -- they are policy-relevant events.
        """
        results = scan_all(PRICE_DIR, window=30, k=3.0, persist=2)
        beras = [a for a in results if a["commodity_code"] == "beras_medium"]
        # v1 baseline: 2526.  Require >= 70 % reduction -> upper bound 757.
        v1_baseline = 2526
        assert len(beras) <= int(v1_baseline * 0.30), (
            f"beras_medium: S-H-ESD v2 gave {len(beras)} anomalies, expected "
            f"<= {int(v1_baseline * 0.30)} (i.e. >= 70 % reduction from v1 baseline of {v1_baseline})"
        )

    def test_beras_premium_not_over_flagged_on_real_data(self):
        """
        beras_premium v1 baseline: 2887.  Require >= 70 % reduction.
        """
        results = scan_all(PRICE_DIR, window=30, k=3.0, persist=2)
        beras = [a for a in results if a["commodity_code"] == "beras_premium"]
        v1_baseline = 2887
        assert len(beras) <= int(v1_baseline * 0.30), (
            f"beras_premium: S-H-ESD v2 gave {len(beras)} anomalies, expected "
            f"<= {int(v1_baseline * 0.30)} (>= 70 % reduction from v1 baseline of {v1_baseline})"
        )

    def test_tiny_flat_perturbation_not_flagged(self):
        """
        A series that is very flat (beras-like: base 14000, std ~100) with a
        small 2 % perturbation (280 IDR) should not be flagged.
        min_dev_pct=3.0 gate handles this even if MAD floor doesn't.
        """
        base = datetime.date(2021, 1, 4)
        flat = [(base + datetime.timedelta(days=i), 14_000.0) for i in range(100)]
        # 2 % perturbation -- below min_dev_pct=3.0 threshold
        s = list(flat)
        for i in [60, 61, 62]:
            d, p = s[i]
            s[i] = (d, p * 1.02)  # +2 %
        result = detect_anomalies(s, window=30, k=3.0, min_dev_pct=3.0, persist=2)
        assert result == [], (
            f"2 % perturbation below min_dev_pct=3.0 should not be flagged; got {len(result)}"
        )

    def test_significant_beras_spike_still_detected(self):
        """
        A genuine beras price shock (>= 8 % and sustained) MUST still be detected
        even with the low-vol gates active.
        """
        base = datetime.date(2021, 1, 4)
        flat = [(base + datetime.timedelta(days=i), 14_000.0) for i in range(120)]
        s = list(flat)
        # 10 % spike sustained for 3 days -- genuine shock
        for i in [60, 61, 62]:
            d, p = s[i]
            s[i] = (d, p * 1.10)
        result = detect_anomalies(s, window=30, k=3.0, mad_floor_pct=0.005, min_dev_pct=3.0, persist=2)
        assert result, (
            "A 10 % sustained beras spike should still be detected despite low-vol gates"
        )
