"""
tests/unit/test_formal_analysis.py

Unit tests for examples/bilgepump/formal_analysis.py.
Skipped automatically if z3-solver is not installed.
"""
import pytest

# Skip entire module if z3 is not available
z3 = pytest.importorskip("z3", reason="z3-solver not installed; skipping formal analysis tests")

import formal_analysis as fa


pytestmark = pytest.mark.z3


# ── _nominal ──────────────────────────────────────────────────────────────────

def test_nominal_has_required_keys():
    n = fa._nominal()
    for key in ("waterLevel", "accuracy_m", "triggerLevel_m", "flowA", "effA",
                "flowB", "effB", "pipeLoss", "designInflow", "inflowRate_m3s"):
        assert key in n, f"missing key: {key}"


def test_nominal_values_in_physical_range():
    n = fa._nominal()
    assert 0.0 < n["waterLevel"] < n["triggerLevel_m"]
    assert 0.0 < n["designInflow"] <= n["flowA"] + n["flowB"]
    assert 0.0 < n["effA"] <= 1.0
    assert 0.0 < n["pipeLoss"] < 1.0


# ── Level 1: symbolic baseline ────────────────────────────────────────────────

def test_level_1_proves_req001_at_nominal():
    n = fa._nominal()
    result = fa.level_1_symbolic_baseline(n, verbose=False)
    assert result.level == 1
    assert result.outcome == "PROVED", (
        f"Level 1 should be PROVED at nominal; got {result.outcome}: {result.detail}"
    )


def test_level_1_returns_formal_result():
    n = fa._nominal()
    result = fa.level_1_symbolic_baseline(n, verbose=False)
    assert isinstance(result, fa.FormalResult)
    assert result.req_id.startswith("BPS-REQ-001")


# ── Level 2: efficiency floor ─────────────────────────────────────────────────

def test_level_2_finds_gap_at_nominal():
    """
    At nominal efficiency (0.82), REQ-004 (raw sum) can still pass while
    FT-002 (net flow) fails at lower efficiencies — Level 2 should find this gap.
    """
    n = fa._nominal()
    result = fa.level_2_efficiency_floor(n, verbose=False)
    assert result.level == 2
    # G-2 is a known structural gap in the original requirements
    assert result.outcome == "GAP", (
        f"Level 2 expected GAP; got {result.outcome}: {result.detail}"
    )


def test_level_2_counterexample_is_valid():
    n = fa._nominal()
    result = fa.level_2_efficiency_floor(n, verbose=False)
    if result.outcome == "GAP":
        cex = result.counterexample
        assert "eta" in cex
        eta = cex["eta"]
        # Counterexample η must be less than η_min
        total_flow = n["flowA"] + n["flowB"]
        eta_min = n["designInflow"] / (total_flow * (1.0 - n["pipeLoss"]))
        assert eta < eta_min + 1e-6


# ── Level 5: adversarial counterexample ───────────────────────────────────────

def test_level_5_finds_gap_with_original_reqs():
    """
    Level 5 checks the original 6 REQs only — the gap should still exist
    (REQ-004 passes while FT-002 fails in the adversarial parameter space).
    This test documents the historical gap; it is expected to be GAP.
    """
    n = fa._nominal()
    result = fa.level_5_adversarial(n, verbose=False)
    assert result.level == 5
    # G-5: the original 6-requirement set cannot prevent this adversarial case
    assert result.outcome == "GAP", (
        f"Level 5 expected GAP with original 6 REQs; got {result.outcome}"
    )


def test_level_5_counterexample_passes_req004_fails_ft002():
    n = fa._nominal()
    result = fa.level_5_adversarial(n, verbose=False)
    if result.outcome == "GAP":
        cex = result.counterexample
        raw_sum = cex["flowA"] + cex["flowB"]
        net = (cex["flowA"] * cex["effA"] + cex["flowB"] * cex["effB"]) * (1.0 - cex["pipeLoss"])
        assert raw_sum >= n["designInflow"], "REQ-004 should pass in counterexample"
        assert net < n["designInflow"], "FT-002 should fail in counterexample"


# ── run_all ───────────────────────────────────────────────────────────────────

def test_run_all_returns_all_6_levels():
    results = fa.run_all()
    levels = [r.level for r in results]
    # Level 3 returns two results (FT-001 + FT-003) so we get 7 total
    assert 1 in levels
    assert 2 in levels
    assert 5 in levels
    assert 6 in levels


def test_run_all_level_subset():
    results = fa.run_all(levels=[1, 2])
    assert all(r.level in (1, 2) for r in results)
    assert len(results) == 2


def test_run_all_outcomes_are_valid_strings():
    results = fa.run_all()
    valid = {"PROVED", "GAP", "UNKNOWN", "ERROR"}
    for r in results:
        assert r.outcome in valid, f"Level {r.level}: unexpected outcome '{r.outcome}'"
