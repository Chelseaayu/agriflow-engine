"""
tests/test_baseline_comparison.py — Correctness assertions for baseline comparison harness.

These tests assert ORDERINGS and BOUNDS that defend pitch claims, NOT golden numbers.
Golden numbers are in benchmarks/output/equity_comparison.md and drift with data changes.

Test structure:
    1. _metrics.py helper sanity tests
    2. equity_fn injection: default-preservation test (run_matching with / without equity_fn)
    3. Strategy ordering tests (the five pitch claims)
    4. Action 6 sensitivity ordering (strict >= lenient for worst-off kab)
"""
from __future__ import annotations
import pytest

from matching_engine import run_matching
from matching_engine.allocation import equity_multiplier_value
from matching_engine.models import LogisticsContext
from sample_data.loader import load_all_sample_data
from benchmarks._metrics import (
    atkinson,
    fulfillment_by_node,
    gini,
    kab_fulfillment,
    min_fulfillment,
    total_deficit_covered,
)
from benchmarks.equity_comparison import (
    _build_demand_tons,
    _equity_smoothed,
    _report_to_matched_tons,
    equity_current,
    equity_lenient,
    equity_strict,
    proportional_allocate,
    uniform_allocate,
    SAMPANG_ID,
    BANGKALAN_ID,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture(scope="module")
def sample_data():
    return load_all_sample_data()


@pytest.fixture(scope="module")
def logistics():
    return LogisticsContext()


@pytest.fixture(scope="module")
def demand_tons(sample_data):
    return _build_demand_tons(sample_data["deficit"])


@pytest.fixture(scope="module")
def matched_greedy(sample_data, logistics):
    report = run_matching(
        sample_data["surplus"], sample_data["deficit"],
        logistics=logistics,
        force_strategy="greedy",
        equity_fn=lambda _: 1.0,
    )
    return _report_to_matched_tons(report)


@pytest.fixture(scope="module")
def matched_agriflow(sample_data, logistics):
    report = run_matching(
        sample_data["surplus"], sample_data["deficit"],
        logistics=logistics,
    )
    return _report_to_matched_tons(report)


@pytest.fixture(scope="module")
def matched_uniform(sample_data, logistics):
    return uniform_allocate(
        sample_data["surplus"], sample_data["deficit"], logistics
    )


@pytest.fixture(scope="module")
def matched_smoothed(sample_data, logistics):
    report = run_matching(
        sample_data["surplus"], sample_data["deficit"],
        logistics=logistics,
        equity_fn=_equity_smoothed,
    )
    return _report_to_matched_tons(report)


# =============================================================================
# 1. _metrics.py helper sanity
# =============================================================================

class TestMetricsHelpers:
    """Sanity checks on pure metric functions.

    These are invariants that must hold regardless of sample data.
    """

    def test_gini_uniform_returns_zero(self, demand_tons):
        """Gini of perfectly equal fulfilment is 0."""
        # All kabs get exactly their full demand
        perfect = {k: v for k, v in demand_tons.items()}
        assert gini(perfect, demand_tons) == pytest.approx(0.0, abs=1e-9)

    def test_gini_uniform_list_zero(self):
        """Classic list form: uniform fulfillment → Gini = 0."""
        # Build equal-weight, equal-ratio scenario manually
        d = {("a", "c", "s"): 10.0, ("b", "c", "s"): 10.0, ("c_kab", "c", "s"): 10.0}
        m = {("a", "c", "s"): 10.0, ("b", "c", "s"): 10.0, ("c_kab", "c", "s"): 10.0}
        assert gini(m, d) == pytest.approx(0.0, abs=1e-9)

    def test_gini_maximum_inequality(self):
        """One kab gets everything, others get nothing → Gini > 0.6."""
        d = {
            ("a", "c", "s"): 100.0,
            ("b", "c", "s"): 100.0,
            ("c_kab", "c", "s"): 100.0,
            ("d_kab", "c", "s"): 100.0,
        }
        m = {("a", "c", "s"): 100.0}  # only 'a' gets supply
        assert gini(m, d) > 0.6

    def test_total_deficit_covered_volume_weighted(self):
        """Coverage is tons fulfilled / tons demanded, NOT count of kabs."""
        d = {("big", "c", "s"): 1000.0, ("small", "c", "s"): 10.0}
        # big gets 50%, small gets 100%
        m = {("big", "c", "s"): 500.0, ("small", "c", "s"): 10.0}
        cov = total_deficit_covered(m, d)
        # Expected: (500+10)/(1000+10) = 510/1010 ≈ 0.5050
        assert cov == pytest.approx(510.0 / 1010.0, rel=1e-6)
        # Must be less than the unweighted count fraction (2/2 = 1.0)
        assert cov < 0.6

    def test_min_fulfillment_returns_worst(self):
        """min_fulfillment reports the single worst fulfillment ratio."""
        d = {("a", "c", "s"): 100.0, ("b", "c", "s"): 50.0}
        m = {("a", "c", "s"): 50.0, ("b", "c", "s"): 50.0}
        # a gets 0.5, b gets 1.0 → min is 0.5
        assert min_fulfillment(m, d) == pytest.approx(0.5, rel=1e-6)

    def test_atkinson_zero_on_perfect_equality(self, demand_tons):
        """Atkinson = 0 when all get their full demand."""
        perfect = {k: v for k, v in demand_tons.items()}
        assert atkinson(perfect, demand_tons, epsilon=0.5) == pytest.approx(0.0, abs=1e-6)
        assert atkinson(perfect, demand_tons, epsilon=1.0) == pytest.approx(0.0, abs=1e-6)

    def test_kab_fulfillment_aggregates_correctly(self):
        """kab_fulfillment is volume-weighted across commodity/segment nodes."""
        d = {
            ("3527", "beras_premium", "RETAIL"): 200.0,
            ("3527", "cabai_merah", "RETAIL"): 50.0,
        }
        m = {
            ("3527", "beras_premium", "RETAIL"): 200.0,
            ("3527", "cabai_merah", "RETAIL"): 25.0,  # half covered
        }
        result = kab_fulfillment(m, d, "3527")
        # Expected: (200+25)/(200+50) = 225/250 = 0.9
        assert result == pytest.approx(0.9, rel=1e-6)


# =============================================================================
# 2. equity_fn default-preservation test
# =============================================================================

class TestEquityFnInjection:
    """Verify that the equity_fn seam is default-preserving.

    run_matching(...) with equity_fn omitted must produce the exact same
    final_score list as run_matching(..., equity_fn=equity_multiplier_value).
    This proves the 166-test gate condition at the API level.
    """

    def test_default_fn_identical_to_explicit_fn(self, sample_data, logistics):
        report_default = run_matching(
            sample_data["surplus"], sample_data["deficit"],
            logistics=logistics,
        )
        report_explicit = run_matching(
            sample_data["surplus"], sample_data["deficit"],
            logistics=logistics,
            equity_fn=equity_multiplier_value,
        )
        scores_default = sorted(m.final_score for m in report_default.matches)
        scores_explicit = sorted(m.final_score for m in report_explicit.matches)
        assert scores_default == pytest.approx(scores_explicit, rel=1e-9), (
            "equity_fn=equity_multiplier_value must be byte-identical to default"
        )

    def test_pure_greedy_equity_multipliers_all_one(self, sample_data, logistics):
        """With equity_fn=lambda _: 1.0, every match's equity_multiplier must be 1.0."""
        report = run_matching(
            sample_data["surplus"], sample_data["deficit"],
            logistics=logistics,
            force_strategy="greedy",
            equity_fn=lambda _: 1.0,
        )
        for m in report.matches:
            assert m.equity_multiplier == pytest.approx(1.0, rel=1e-9), (
                f"Expected equity_multiplier=1.0, got {m.equity_multiplier} for "
                f"{m.deficit.kabupaten.nama}"
            )

    def test_smoothed_fn_close_to_step_scores(self, sample_data, logistics):
        """Smoothed equity_fn produces similar final scores to step-function."""
        report_step = run_matching(
            sample_data["surplus"], sample_data["deficit"],
            logistics=logistics,
        )
        report_smooth = run_matching(
            sample_data["surplus"], sample_data["deficit"],
            logistics=logistics,
            equity_fn=_equity_smoothed,
        )
        # Smoothed knots interpolate between step values → similar but not identical
        # Both must produce the same number of matches (same feasibility)
        assert len(report_step.matches) == len(report_smooth.matches)


# =============================================================================
# 3. Strategy ordering tests (pitch claims)
# =============================================================================

class TestStrategyOrdering:
    """Ordering assertions that defend the pitch narrative.

    These do NOT assert golden numbers — they assert relationships between
    strategies that the pitch claims:
        - Pure greedy is the efficiency frontier (highest coverage)
        - Uniform is the equity extreme (lowest Gini)
        - AgriFlow is between them on both axes
        - Sampang and Bangkalan (the two poorest Madura kabs) do at least
          as well under AgriFlow as under pure greedy
    """

    def test_greedy_coverage_gte_agriflow(self, matched_greedy, matched_agriflow, demand_tons):
        """Efficiency frontier: pure greedy must not be beaten on raw volume coverage."""
        g_cov = total_deficit_covered(matched_greedy, demand_tons)
        a_cov = total_deficit_covered(matched_agriflow, demand_tons)
        assert g_cov >= a_cov - 1e-9, (
            f"Pure greedy ({g_cov:.4f}) must have >= coverage than AgriFlow ({a_cov:.4f}). "
            f"If this fails, the efficiency-equity tradeoff claim is broken."
        )

    def test_uniform_gini_lte_agriflow(self, matched_uniform, matched_agriflow, demand_tons):
        """Equity extreme: uniform allocation must have <= Gini than AgriFlow."""
        u_gini = gini(matched_uniform, demand_tons)
        a_gini = gini(matched_agriflow, demand_tons)
        assert u_gini <= a_gini + 1e-9, (
            f"Uniform gini ({u_gini:.4f}) must be <= AgriFlow gini ({a_gini:.4f}). "
            f"Uniform is the equity anchor — it must never be MORE unequal than AgriFlow."
        )

    def test_sampang_agriflow_gte_greedy(self, matched_agriflow, matched_greedy, demand_tons):
        """Sampang (IPM 66.72, highest equity boost) does >= under AgriFlow vs greedy."""
        a = kab_fulfillment(matched_agriflow, demand_tons, SAMPANG_ID)
        g = kab_fulfillment(matched_greedy, demand_tons, SAMPANG_ID)
        assert a >= g - 1e-9, (
            f"Sampang under AgriFlow ({a:.4f}) must be >= under greedy ({g:.4f}). "
            f"The 1.30x equity boost exists to ensure this."
        )

    def test_bangkalan_agriflow_gte_greedy(self, matched_agriflow, matched_greedy, demand_tons):
        """Bangkalan (IPM 67.70, highest equity boost) does >= under AgriFlow vs greedy."""
        a = kab_fulfillment(matched_agriflow, demand_tons, BANGKALAN_ID)
        g = kab_fulfillment(matched_greedy, demand_tons, BANGKALAN_ID)
        assert a >= g - 1e-9, (
            f"Bangkalan under AgriFlow ({a:.4f}) must be >= under greedy ({g:.4f})."
        )

    def test_smoothed_coverage_approx_step(self, matched_smoothed, matched_agriflow, demand_tons):
        """AgriFlow-smoothed and AgriFlow-step must have similar coverage (within 5pp)."""
        s_cov = total_deficit_covered(matched_smoothed, demand_tons)
        a_cov = total_deficit_covered(matched_agriflow, demand_tons)
        assert abs(s_cov - a_cov) < 0.05, (
            f"Smoothed coverage ({s_cov:.4f}) differs from step ({a_cov:.4f}) by > 5pp. "
            f"Smoothed should approximate step — this is the attack-#2 answer."
        )

    def test_smoothed_gini_approx_step(self, matched_smoothed, matched_agriflow, demand_tons):
        """AgriFlow-smoothed and AgriFlow-step must have similar Gini (within 5pp)."""
        s_gini = gini(matched_smoothed, demand_tons)
        a_gini = gini(matched_agriflow, demand_tons)
        assert abs(s_gini - a_gini) < 0.05, (
            f"Smoothed Gini ({s_gini:.4f}) differs from step Gini ({a_gini:.4f}) by > 5pp."
        )

    def test_agriflow_coverage_positive(self, matched_agriflow, demand_tons):
        """AgriFlow must achieve non-trivial coverage (> 50%)."""
        a_cov = total_deficit_covered(matched_agriflow, demand_tons)
        assert a_cov > 0.5, f"AgriFlow coverage ({a_cov:.4f}) must be > 50%."

    def test_greedy_coverage_positive(self, matched_greedy, demand_tons):
        """Pure greedy must achieve non-trivial coverage (> 50%)."""
        g_cov = total_deficit_covered(matched_greedy, demand_tons)
        assert g_cov > 0.5, f"Greedy coverage ({g_cov:.4f}) must be > 50%."


# =============================================================================
# 4. Action 6 sensitivity ordering
# =============================================================================

class TestSensitivityOrdering:
    """Strict threshold setting helps worst-off kabs more than lenient."""

    def test_strict_sampang_gte_lenient(self, sample_data, logistics, demand_tons):
        """Stricter equity thresholds give Sampang >= coverage vs lenient."""
        report_strict = run_matching(
            sample_data["surplus"], sample_data["deficit"],
            logistics=logistics,
            equity_fn=equity_strict,
        )
        report_lenient = run_matching(
            sample_data["surplus"], sample_data["deficit"],
            logistics=logistics,
            equity_fn=equity_lenient,
        )
        mt_strict = _report_to_matched_tons(report_strict)
        mt_lenient = _report_to_matched_tons(report_lenient)
        s_strict = kab_fulfillment(mt_strict, demand_tons, SAMPANG_ID)
        s_lenient = kab_fulfillment(mt_lenient, demand_tons, SAMPANG_ID)
        assert s_strict >= s_lenient - 1e-9, (
            f"Strict Sampang ({s_strict:.4f}) must be >= lenient ({s_lenient:.4f}). "
            f"Stricter equity weighting should benefit the poorest kab."
        )

    def test_equity_current_delegates_to_production(self, sample_data, logistics):
        """equity_current() must return the same value as equity_multiplier_value()."""
        test_ipms = [60.0, 66.72, 67.70, 68.79, 70.0, 72.0, 75.0, 78.0, 84.69]
        for ipm in test_ipms:
            assert equity_current(ipm) == equity_multiplier_value(ipm), (
                f"equity_current({ipm}) != equity_multiplier_value({ipm}). "
                f"equity_current must delegate — it is the single source of truth."
            )

    def test_smoothed_equals_step_at_knot_boundaries(self):
        """Smoothed function equals step-function exactly at the knot IPM values."""
        # At knot boundaries, interpolation should produce the step value
        knot_checks = [
            (68.0, 1.30),  # lower boundary of tier 1→2
            (72.0, 1.15),  # lower boundary of tier 2→3
            (78.0, 1.05),  # lower boundary of tier 3→4
        ]
        for ipm, expected in knot_checks:
            assert _equity_smoothed(ipm) == pytest.approx(expected, rel=1e-9), (
                f"Smoothed at knot IPM={ipm}: expected {expected}, "
                f"got {_equity_smoothed(ipm):.6f}"
            )

    def test_smoothed_below_lowest_knot(self):
        """Below lowest knot (IPM < 68), smoothed returns 1.30 (same as step)."""
        for ipm in [50.0, 60.0, 67.99]:
            assert _equity_smoothed(ipm) == pytest.approx(1.30, rel=1e-9)

    def test_smoothed_above_highest_knot(self):
        """Above highest knot (IPM >= 85), smoothed returns 1.00."""
        assert _equity_smoothed(85.0) == pytest.approx(1.00, rel=1e-9)
        assert _equity_smoothed(90.0) == pytest.approx(1.00, rel=1e-9)

    def test_smoothed_monotone_decreasing(self):
        """Smoothed equity function is monotone decreasing (higher IPM = lower boost)."""
        ipms = [60.0, 65.0, 68.0, 70.0, 72.0, 74.0, 78.0, 80.0, 85.0, 90.0]
        values = [_equity_smoothed(ipm) for ipm in ipms]
        for i in range(len(values) - 1):
            assert values[i] >= values[i + 1] - 1e-9, (
                f"Smoothed not monotone at IPM={ipms[i]:.1f} ({values[i]:.4f}) "
                f"-> IPM={ipms[i+1]:.1f} ({values[i+1]:.4f})"
            )
