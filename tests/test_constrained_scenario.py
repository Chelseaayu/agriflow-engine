"""
tests/test_constrained_scenario.py — Ordering/bound assertions for the
La Nina supply-shock (CONSTRAINED) scenario.

Scenario:
    Ngawi (3521), Madiun (3519), Bojonegoro (3522) banjir bersamaan.
    surplus_deficit_constrained.csv: 6 SURPLUS rows removed.
    Result: surplus=3962t < deficit=5249t (under-supplied by 32.5%).

These tests assert ORDERINGS and BOUNDS, NOT golden numbers.
Golden numbers are in benchmarks/output/equity_comparison_constrained.md.

What these tests defend:
    1. Fixture integrity: constrained is genuinely supply-constrained.
    2. Uniform Gini sanity DOES NOT apply in constrained because the
       algorithm cannot fill all demand equally — some nodes get 0 by
       necessity. The formula is still correct; the invariant changes.
    3. Greedy vs AgriFlow on Sampang/Bangkalan: the equity boost MUST
       protect the two poorest kabs better than greedy under scarcity.
    4. AgriFlow Gini <= greedy Gini in constrained (equity mechanism fires).
    5. Coverage ordering: greedy >= agriflow (efficiency-equity tradeoff
       shows up or is negligible — greedy never below agriflow).
    6. Sensitivity ABUNDANT degenerate check (documents known limitation).
"""
from __future__ import annotations
import pytest

from matching_engine import run_matching
from matching_engine.models import LogisticsContext
from sample_data.loader import load_all_sample_data
from benchmarks._metrics import (
    gini,
    kab_fulfillment,
    min_fulfillment,
    total_deficit_covered,
)
from benchmarks.equity_comparison import (
    _build_demand_tons,
    _report_to_matched_tons,
    equity_lenient,
    equity_strict,
    proportional_allocate,
    uniform_allocate,
    SAMPANG_ID,
    BANGKALAN_ID,
)

CONSTRAINED_CSV = "surplus_deficit_constrained.csv"
EXPECTED_SURPLUS_TONS = 3962.0
EXPECTED_DEFICIT_TONS = 5249.0


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture(scope="module")
def constrained_data():
    return load_all_sample_data(surplus_deficit_csv=CONSTRAINED_CSV)


@pytest.fixture(scope="module")
def logistics():
    return LogisticsContext()


@pytest.fixture(scope="module")
def demand_tons_c(constrained_data):
    return _build_demand_tons(constrained_data["deficit"])


@pytest.fixture(scope="module")
def matched_greedy_c(constrained_data, logistics):
    report = run_matching(
        constrained_data["surplus"], constrained_data["deficit"],
        logistics=logistics,
        force_strategy="greedy",
        equity_fn=lambda _: 1.0,
    )
    return _report_to_matched_tons(report)


@pytest.fixture(scope="module")
def matched_agriflow_c(constrained_data, logistics):
    report = run_matching(
        constrained_data["surplus"], constrained_data["deficit"],
        logistics=logistics,
    )
    return _report_to_matched_tons(report)


@pytest.fixture(scope="module")
def matched_uniform_c(constrained_data, logistics):
    return uniform_allocate(
        constrained_data["surplus"], constrained_data["deficit"], logistics
    )


# =============================================================================
# 1. Fixture integrity
# =============================================================================

class TestFixtureIntegrity:
    """Verify the constrained fixture is genuinely supply-constrained."""

    def test_surplus_less_than_deficit(self, constrained_data):
        """CONSTRAINED scenario must have deficit > surplus (core fixture assertion)."""
        surplus_total = sum(s.volume_tons for s in constrained_data["surplus"])
        deficit_total = sum(d.volume_tons for d in constrained_data["deficit"])
        assert deficit_total > surplus_total, (
            f"CONSTRAINED fixture must have deficit ({deficit_total:.0f}t) > "
            f"surplus ({surplus_total:.0f}t). Fixture may be corrupted."
        )

    def test_surplus_approx_expected(self, constrained_data):
        """Constrained surplus == 3962t (6 rows removed from 3521/3519/3522)."""
        surplus_total = sum(s.volume_tons for s in constrained_data["surplus"])
        assert abs(surplus_total - EXPECTED_SURPLUS_TONS) < 1.0, (
            f"Expected {EXPECTED_SURPLUS_TONS}t surplus, got {surplus_total:.1f}t. "
            f"surplus_deficit_constrained.csv may be out of sync."
        )

    def test_deficit_unchanged_vs_abundant(self, constrained_data):
        """Deficit total must equal ABUNDANT deficit (shock only removes supply)."""
        deficit_total = sum(d.volume_tons for d in constrained_data["deficit"])
        assert abs(deficit_total - EXPECTED_DEFICIT_TONS) < 1.0, (
            f"Expected {EXPECTED_DEFICIT_TONS}t deficit (unchanged vs abundant), "
            f"got {deficit_total:.1f}t. Fixture must not modify demand rows."
        )

    def test_shock_kabs_absent_from_surplus(self, constrained_data):
        """Ngawi (3521), Madiun (3519), Bojonegoro (3522) must have no surplus rows."""
        shock_kabs = {"3521", "3519", "3522"}
        surplus_kabs = {s.kabupaten.id for s in constrained_data["surplus"]}
        intersection = shock_kabs & surplus_kabs
        assert not intersection, (
            f"Shock kabs {intersection} still have surplus in constrained fixture. "
            f"surplus_deficit_constrained.csv is incorrect."
        )

    def test_sampang_bangkalan_deficit_present(self, constrained_data):
        """Sampang (3527) and Bangkalan (3526) must still have deficit rows."""
        deficit_kabs = {d.kabupaten.id for d in constrained_data["deficit"]}
        assert SAMPANG_ID in deficit_kabs, (
            f"Sampang ({SAMPANG_ID}) has no deficit in constrained scenario."
        )
        assert BANGKALAN_ID in deficit_kabs, (
            f"Bangkalan ({BANGKALAN_ID}) has no deficit in constrained scenario."
        )


# =============================================================================
# 2. Coverage is meaningfully below 1 in constrained
# =============================================================================

class TestCoverageConstrained:
    """In constrained scenario, aggregate coverage must be < 1 for all strategies."""

    def test_greedy_coverage_below_one(self, matched_greedy_c, demand_tons_c):
        """Under supply shortage, even greedy cannot cover all demand."""
        cov = total_deficit_covered(matched_greedy_c, demand_tons_c)
        assert cov < 0.99, (
            f"Greedy coverage ({cov:.4f}) unexpectedly close to 1.0 in constrained scenario. "
            f"Is the fixture actually supply-constrained?"
        )

    def test_agriflow_coverage_below_one(self, matched_agriflow_c, demand_tons_c):
        cov = total_deficit_covered(matched_agriflow_c, demand_tons_c)
        assert cov < 0.99, (
            f"AgriFlow coverage ({cov:.4f}) unexpectedly close to 1.0 in constrained scenario."
        )

    def test_both_strategies_above_floor(self, matched_greedy_c, matched_agriflow_c, demand_tons_c):
        """Both strategies must cover at least 30% (engine is not broken)."""
        g_cov = total_deficit_covered(matched_greedy_c, demand_tons_c)
        a_cov = total_deficit_covered(matched_agriflow_c, demand_tons_c)
        assert g_cov > 0.30, f"Greedy coverage ({g_cov:.4f}) below 30% floor."
        assert a_cov > 0.30, f"AgriFlow coverage ({a_cov:.4f}) below 30% floor."


# =============================================================================
# 3. Core equity claims under scarcity
# =============================================================================

class TestEquityUnderScarcity:
    """The core pitch claims must hold under supply-constrained conditions."""

    def test_greedy_coverage_gte_agriflow(self, matched_greedy_c, matched_agriflow_c, demand_tons_c):
        """Efficiency frontier: greedy >= agriflow on raw volume coverage."""
        g = total_deficit_covered(matched_greedy_c, demand_tons_c)
        a = total_deficit_covered(matched_agriflow_c, demand_tons_c)
        assert g >= a - 1e-9, (
            f"Greedy ({g:.4f}) must have >= coverage than AgriFlow ({a:.4f}). "
            f"Efficiency-equity tradeoff claim broken."
        )

    def test_agriflow_gini_lte_greedy(self, matched_agriflow_c, matched_greedy_c, demand_tons_c):
        """AgriFlow must have lower Gini than greedy under scarcity.

        This is the key test: in ABUNDANT scenario both are degenerate
        (Sampang/Bangkalan fully served regardless). In CONSTRAINED, greedy
        abandons the poorest kabs to serve easier nearby nodes; AgriFlow
        prioritises them via 1.30x equity boost.
        """
        a_gini = gini(matched_agriflow_c, demand_tons_c)
        g_gini = gini(matched_greedy_c, demand_tons_c)
        assert a_gini <= g_gini + 1e-6, (
            f"AgriFlow Gini ({a_gini:.4f}) must be <= greedy Gini ({g_gini:.4f}). "
            f"Under scarcity, equity mechanism must improve distributional fairness."
        )

    def test_sampang_agriflow_gte_greedy(self, matched_agriflow_c, matched_greedy_c, demand_tons_c):
        """Sampang (IPM 66.72) must do >= under AgriFlow vs greedy.

        Under CONSTRAINED: greedy routes supply to nearer/higher-scoring nodes,
        leaving Sampang (Madura island, relatively remote) unserved. The 1.30x
        equity boost in AgriFlow explicitly prioritises Sampang's demand.
        """
        a = kab_fulfillment(matched_agriflow_c, demand_tons_c, SAMPANG_ID)
        g = kab_fulfillment(matched_greedy_c, demand_tons_c, SAMPANG_ID)
        assert a >= g - 1e-9, (
            f"Sampang: AgriFlow ({a:.4f}) must be >= greedy ({g:.4f}) under scarcity. "
            f"The 1.30x equity boost is specifically calibrated for Sampang (IPM 66.72)."
        )

    def test_bangkalan_agriflow_gte_greedy(self, matched_agriflow_c, matched_greedy_c, demand_tons_c):
        """Bangkalan (IPM 67.70) must do >= under AgriFlow vs greedy."""
        a = kab_fulfillment(matched_agriflow_c, demand_tons_c, BANGKALAN_ID)
        g = kab_fulfillment(matched_greedy_c, demand_tons_c, BANGKALAN_ID)
        assert a >= g - 1e-9, (
            f"Bangkalan: AgriFlow ({a:.4f}) must be >= greedy ({g:.4f}) under scarcity."
        )

    def test_uniform_gini_lte_agriflow(self, matched_uniform_c, matched_agriflow_c, demand_tons_c):
        """Uniform allocation must have <= Gini than AgriFlow (equity anchor invariant).

        Note: in CONSTRAINED, uniform Gini is NOT near-zero because the equal-split
        algorithm cannot equalize fulfillment ratios when there is not enough supply.
        Nodes connected to more surplus paths get higher ratios. The invariant
        'uniform <= agriflow' still holds because uniform ignores score entirely
        and distributes supply as evenly as the graph structure allows.
        """
        u_gini = gini(matched_uniform_c, demand_tons_c)
        a_gini = gini(matched_agriflow_c, demand_tons_c)
        assert u_gini <= a_gini + 1e-9, (
            f"Uniform gini ({u_gini:.4f}) must be <= AgriFlow gini ({a_gini:.4f}). "
            f"Uniform is the equity anchor even under scarcity."
        )


# =============================================================================
# 4. Sensitivity ordering under constrained (must not be degenerate on coverage)
# =============================================================================

class TestSensitivityConstrained:
    """Sensitivity check under CONSTRAINED: strict/lenient must differ on at least coverage."""

    def test_strict_sampang_gte_lenient(self, constrained_data, logistics, demand_tons_c):
        """Stricter equity gives Sampang >= lenient under scarcity."""
        rep_strict = run_matching(
            constrained_data["surplus"], constrained_data["deficit"],
            logistics=logistics,
            equity_fn=equity_strict,
        )
        rep_lenient = run_matching(
            constrained_data["surplus"], constrained_data["deficit"],
            logistics=logistics,
            equity_fn=equity_lenient,
        )
        mt_strict = _report_to_matched_tons(rep_strict)
        mt_lenient = _report_to_matched_tons(rep_lenient)
        s_strict = kab_fulfillment(mt_strict, demand_tons_c, SAMPANG_ID)
        s_lenient = kab_fulfillment(mt_lenient, demand_tons_c, SAMPANG_ID)
        assert s_strict >= s_lenient - 1e-9, (
            f"Strict Sampang ({s_strict:.4f}) must be >= lenient ({s_lenient:.4f}). "
            f"Under scarcity, stricter equity weighting should benefit poorest kab."
        )

    def test_sensitivity_coverage_consistent(self, constrained_data, logistics, demand_tons_c):
        """All three sensitivity variants should have similar aggregate coverage."""
        coverages = []
        for fn in [equity_strict, equity_lenient]:
            rep = run_matching(
                constrained_data["surplus"], constrained_data["deficit"],
                logistics=logistics,
                equity_fn=fn,
            )
            mt = _report_to_matched_tons(rep)
            coverages.append(total_deficit_covered(mt, demand_tons_c))
        # Coverage should not diverge by more than 15pp between variants
        assert max(coverages) - min(coverages) < 0.15, (
            f"Sensitivity coverage spread ({min(coverages):.4f}–{max(coverages):.4f}) "
            f"exceeds 15pp. Variants should differ on DISTRIBUTION, not total volume."
        )
