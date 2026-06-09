"""
tests/model/test_model_fallback.py

Model-level tests using the Python regex/eval fallback evaluator.
No SysML kernel required — all tests complete in ~10 s.

Tests:
  1. Positive test — all requirements satisfied at nominal values
  2. Negative test — pump A failure violates discharge requirements
  3. Key requirement checks — assert specific requirements are satisfied/violated
"""

import pytest

import sys_infra.verify as verify


pytestmark = pytest.mark.model


@pytest.fixture(scope="module")
def manifest(manifest_path):
    name, layers, validation_layers = verify._read_manifest(manifest_path)
    return name, layers, validation_layers


@pytest.fixture(scope="module")
def positive_results(manifest):
    _, layers, validation_layers = manifest
    layer_set = validation_layers if validation_layers else layers
    return verify._run_fallback(layer_set, negative=False)


@pytest.fixture(scope="module")
def negative_results(manifest):
    _, layers, _ = manifest
    return verify._run_fallback(layers, negative=True)


# ── Positive test (nominal values) ────────────────────────────────────────────


class TestPositiveCase:
    """All validation_layers requirements must be SATISFIED at nominal values."""

    def test_no_requirement_violated(self, positive_results):
        violated = [
            r["requirement"] for r in positive_results if r.get("satisfied") is False
        ]
        assert violated == [], f"Unexpected violations at nominal: {violated}"

    def test_all_key_requirements_satisfied(self, positive_results):
        by_name = {r["requirement"]: r for r in positive_results}
        key_reqs = [
            "WaterLevelRequirement",
            "PumpRedundancyRequirement",
            "AlarmResponseRequirement",
            "DischargeCapacityRequirement",
            "ControllerActivationTimingRequirement",
            "FailoverSwitchTimingRequirement",
            "SensorAccuracyBoundRequirement",
            "EffectiveDischargeCapacityRequirement",
            "TriggerLevelAccuracyRequirement",
            "EndToEndResponseRequirement",
        ]
        for req in key_reqs:
            assert req in by_name, f"Requirement '{req}' not found in results"
            assert by_name[req]["satisfied"] is True, (
                f"'{req}' expected SATISFIED; got {by_name[req]['satisfied']}"
            )

    def test_all_satisfied_flag_is_true(self, positive_results, tmp_path):
        """Regression: all_satisfied must be True when no requirement is False."""
        import json

        original_lib = verify.LIB_DIR
        verify.LIB_DIR = str(tmp_path)
        try:
            verify._save_results(positive_results, "positive", "python-eval")
        finally:
            verify.LIB_DIR = original_lib
        with open(tmp_path / "verification-results.json") as f:
            data = json.load(f)
        assert data["all_satisfied"] is True


# ── Negative test (pump A failure) ────────────────────────────────────────────


class TestNegativeCase:
    """With pumpA.flowRate=0, discharge requirements should be violated."""

    def test_discharge_capacity_violated(self, negative_results):
        by_name = {r["requirement"]: r for r in negative_results}
        # REQ-004: raw sum 0 + 0.025 = 0.025 < 0.030 → VIOLATED
        assert by_name["DischargeCapacityRequirement"]["satisfied"] is False

    def test_effective_discharge_violated(self, negative_results):
        by_name = {r["requirement"]: r for r in negative_results}
        # FT-002: (0*effA + 0.025*effB) * 0.95 < 0.030 → VIOLATED
        assert by_name["EffectiveDischargeCapacityRequirement"]["satisfied"] is False

    def test_water_level_still_satisfied(self, negative_results):
        """Water level check is independent of pump operation."""
        by_name = {r["requirement"]: r for r in negative_results}
        assert by_name["WaterLevelRequirement"]["satisfied"] is True

    def test_redundancy_still_satisfied(self, negative_results):
        """isRedundant flag is structural — unaffected by flow rate override."""
        by_name = {r["requirement"]: r for r in negative_results}
        assert by_name["PumpRedundancyRequirement"]["satisfied"] is True


# ── Result structure ──────────────────────────────────────────────────────────


class TestResultStructure:
    """Verify the result list has the expected shape."""

    def test_results_non_empty(self, positive_results):
        assert len(positive_results) > 0

    def test_each_result_has_required_keys(self, positive_results):
        for r in positive_results:
            assert "requirement" in r
            assert "satisfied" in r
            assert "expr" in r

    def test_satisfied_values_are_bool_or_none(self, positive_results):
        for r in positive_results:
            assert r["satisfied"] in (True, False, None), (
                f"Unexpected satisfied value for {r['requirement']}: {r['satisfied']}"
            )
