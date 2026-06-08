"""
tests/unit/test_verify_helpers.py

Unit tests for the internal helper functions in verify.py.
No SysML kernel required — all tests use the Python regex/eval path.
"""
import json
import os
import tempfile

import pytest

import verify


# ── _eval_requirement ─────────────────────────────────────────────────────────

class TestEvalRequirement:
    """Tests for verify._eval_requirement()."""

    def test_simple_le_satisfied(self):
        bind = {"sys.sensor.waterLevel": 0.15}
        bare = {"waterLevel": 0.15}
        result = verify._eval_requirement(
            "WaterLevelRequirement",
            "sys.sensor.waterLevel <= 0.3",
            bind,
            bare,
        )
        assert result is True

    def test_simple_le_violated(self):
        bind = {"sys.sensor.waterLevel": 0.35}
        bare = {"waterLevel": 0.35}
        result = verify._eval_requirement(
            "WaterLevelRequirement",
            "sys.sensor.waterLevel <= 0.3",
            bind,
            bare,
        )
        assert result is False

    def test_boolean_true(self):
        bind = {"sys.pumpB.isRedundant": True}
        bare = {"isRedundant": True}
        result = verify._eval_requirement(
            "PumpRedundancyRequirement",
            "sys.pumpB.isRedundant == true",
            bind,
            bare,
        )
        assert result is True

    def test_boolean_false(self):
        bind = {"sys.pumpB.isRedundant": False}
        bare = {"isRedundant": False}
        result = verify._eval_requirement(
            "PumpRedundancyRequirement",
            "sys.pumpB.isRedundant == true",
            bind,
            bare,
        )
        assert result is False

    def test_product_expression(self):
        # FT-002: (pumpA.flowRate * pumpA.efficiency + pumpB.flowRate * pumpB.efficiency)
        #         * (1.0 - discharge.pipeLossFactor) >= 0.030
        bind = {
            "sys.pumpA.flowRate": 0.025,
            "sys.pumpA.efficiency": 0.82,
            "sys.pumpB.flowRate": 0.025,
            "sys.pumpB.efficiency": 0.82,
            "sys.discharge.pipeLossFactor": 0.05,
        }
        bare = {k.rsplit(".", 1)[-1]: v for k, v in bind.items()}
        expr = (
            "(sys.pumpA.flowRate * sys.pumpA.efficiency"
            " + sys.pumpB.flowRate * sys.pumpB.efficiency)"
            " * (1.0 - sys.discharge.pipeLossFactor) >= 0.030"
        )
        result = verify._eval_requirement("FT002", expr, bind, bare)
        # (0.025*0.82 + 0.025*0.82) * 0.95 = 0.02050 * 2 * 0.95 = 0.0390 ≥ 0.030 ✓
        assert result is True

    def test_unparseable_returns_none(self):
        result = verify._eval_requirement(
            "Mystery",
            "some.unknown.expr(foo)",
            {},
            {},
        )
        assert result is None

    def test_addition_constraint(self):
        bind = {"sys.sensor.waterLevel": 0.15, "sys.sensor.accuracy_m": 0.03}
        bare = {"waterLevel": 0.15, "accuracy_m": 0.03}
        result = verify._eval_requirement(
            "SensorAccuracyBoundRequirement",
            "sys.sensor.waterLevel + sys.sensor.accuracy_m <= 0.3",
            bind,
            bare,
        )
        # 0.15 + 0.03 = 0.18 ≤ 0.30 ✓
        assert result is True


# ── _build_bind_values ────────────────────────────────────────────────────────

class TestBuildBindValues:
    """Tests for verify._build_bind_values()."""

    SAMPLE_TEXT = """
        bind sys.sensor.waterLevel   = 0.15;
        bind sys.pumpA.flowRate      = 0.025;
        bind sys.pumpB.isRedundant   = true;
        bind sys.alarm.isActive      = false;
        bind sys.controller.triggerLevel_m = 0.25;
    """

    def test_numeric_values_parsed(self):
        full, bare = verify._build_bind_values(self.SAMPLE_TEXT, negative=False)
        assert full["sys.sensor.waterLevel"] == pytest.approx(0.15)
        assert full["sys.pumpA.flowRate"] == pytest.approx(0.025)

    def test_boolean_true_parsed(self):
        full, bare = verify._build_bind_values(self.SAMPLE_TEXT, negative=False)
        assert full["sys.pumpB.isRedundant"] is True

    def test_boolean_false_parsed(self):
        full, bare = verify._build_bind_values(self.SAMPLE_TEXT, negative=False)
        assert full["sys.alarm.isActive"] is False

    def test_bare_index_populated(self):
        full, bare = verify._build_bind_values(self.SAMPLE_TEXT, negative=False)
        assert bare["waterLevel"] == pytest.approx(0.15)
        assert bare["triggerLevel_m"] == pytest.approx(0.25)

    def test_negative_zeroes_pumpA_flowRate(self, capsys):
        full, bare = verify._build_bind_values(self.SAMPLE_TEXT, negative=True)
        assert full["sys.pumpA.flowRate"] == 0.0
        assert bare["flowRate"] == 0.0


# ── _read_manifest ────────────────────────────────────────────────────────────

class TestReadManifest:
    """Tests for verify._read_manifest()."""

    def test_reads_real_manifest(self, manifest_path):
        name, layers, validation_layers = verify._read_manifest(manifest_path)
        assert isinstance(name, str) and name
        assert isinstance(layers, list) and len(layers) > 0
        assert all(l.endswith(".sysml") for l in layers)

    def test_validation_layers_subset(self, manifest_path):
        name, layers, validation_layers = verify._read_manifest(manifest_path)
        if validation_layers is not None:
            vl_set = set(validation_layers)
            assert vl_set.issubset(set(layers))

    def test_synthetic_manifest(self, tmp_path):
        manifest = tmp_path / "sysml-project.yml"
        manifest.write_text(
            "name: TestProject\n"
            "layers:\n"
            "  - bilgepump/Library.sysml\n"
            "  - bilgepump/Architecture.sysml\n"
            "validation_layers:\n"
            "  - bilgepump/Library.sysml\n"
        )
        name, layers, vl = verify._read_manifest(str(manifest))
        assert name == "TestProject"
        assert layers == ["bilgepump/Library.sysml", "bilgepump/Architecture.sysml"]
        assert vl == ["bilgepump/Library.sysml"]


# ── _save_results aggregation bug fix ────────────────────────────────────────

class TestSaveResultsAggregation:
    """
    Regression test for the all_satisfied aggregation bug (Phase 1 fix).
    Before fix: all(r.get('satisfied') is True ...) → False when any result is None.
    After fix:  not any(r.get('satisfied') is False ...) → True when no result is False.
    """

    def _run_save(self, results, tmp_path):
        original_lib = verify.LIB_DIR
        verify.LIB_DIR = str(tmp_path)
        try:
            verify._save_results(results, "positive", "python-eval")
        finally:
            verify.LIB_DIR = original_lib
        with open(tmp_path / "verification-results.json") as f:
            return json.load(f)

    def test_all_true_gives_all_satisfied_true(self, tmp_path):
        results = [
            {"requirement": "R1", "satisfied": True},
            {"requirement": "R2", "satisfied": True},
        ]
        data = self._run_save(results, tmp_path)
        assert data["all_satisfied"] is True

    def test_one_false_gives_all_satisfied_false(self, tmp_path):
        results = [
            {"requirement": "R1", "satisfied": True},
            {"requirement": "R2", "satisfied": False},
        ]
        data = self._run_save(results, tmp_path)
        assert data["all_satisfied"] is False

    def test_none_does_not_count_as_failure(self, tmp_path):
        """
        None means 'could not evaluate' — not a formal violation.
        all_satisfied must be True when no requirement is explicitly False.
        """
        results = [
            {"requirement": "R1", "satisfied": True},
            {"requirement": "UCA_002", "satisfied": None},  # unevaluable UCA
        ]
        data = self._run_save(results, tmp_path)
        assert data["all_satisfied"] is True

    def test_mixed_none_and_false_gives_false(self, tmp_path):
        results = [
            {"requirement": "R1", "satisfied": True},
            {"requirement": "R2", "satisfied": None},
            {"requirement": "R3", "satisfied": False},
        ]
        data = self._run_save(results, tmp_path)
        assert data["all_satisfied"] is False
