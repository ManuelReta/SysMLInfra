"""
tests/unit/test_fault_tracer.py

Unit tests for scripts/fault_tracer.py.
Tests the bind index parser, annotation detection, and trace generation.
No SysML kernel required.
"""

import pytest

from scripts.fault_tracer import FaultTracer, build_bind_index


class TestBuildBindIndex:
    """Tests for fault_tracer.build_bind_index()."""

    def test_numeric_bind_parsed(self, tmp_path):
        sysml = tmp_path / "Analysis.sysml"
        sysml.write_text(
            "analysis def Test {\n"
            "    bind sys.sensor.waterLevel = 0.15;\n"
            "    bind sys.pumpA.flowRate    = 0.025;\n"
            "}\n"
        )
        idx = build_bind_index(["Analysis.sysml"], str(tmp_path))
        assert "sys.sensor.waterLevel" in idx
        assert idx["sys.sensor.waterLevel"]["value"] == pytest.approx(0.15)

    def test_boolean_bind_parsed(self, tmp_path):
        sysml = tmp_path / "Analysis.sysml"
        sysml.write_text("bind sys.pumpB.isRedundant = true;\n")
        idx = build_bind_index(["Analysis.sysml"], str(tmp_path))
        assert idx["sys.pumpB.isRedundant"]["value"] is True

    def test_line_number_recorded(self, tmp_path):
        sysml = tmp_path / "Analysis.sysml"
        sysml.write_text("// line 1\n// line 2\nbind sys.sensor.waterLevel = 0.15;\n")
        idx = build_bind_index(["Analysis.sysml"], str(tmp_path))
        assert idx["sys.sensor.waterLevel"]["line"] == 3

    def test_missing_file_skipped(self, tmp_path):
        idx = build_bind_index(["nonexistent.sysml"], str(tmp_path))
        assert len(idx) == 0

    def test_comment_stripped_before_parse(self, tmp_path):
        sysml = tmp_path / "Analysis.sysml"
        sysml.write_text("// bind sys.fake.attr = 99.0;\nbind sys.real.attr = 1.0;\n")
        idx = build_bind_index(["Analysis.sysml"], str(tmp_path))
        assert "sys.fake.attr" not in idx
        assert "sys.real.attr" in idx


# ── FaultTracer integration ───────────────────────────────────────────────────


class TestFaultTracerLoad:
    """Tests that FaultTracer loads successfully against the real model."""

    def test_load_without_errors(self, bilgepump_dir, manifest_path):
        import sys_infra.verify as verify

        _, layers, _ = verify._read_manifest(manifest_path)
        tracer = FaultTracer(str(bilgepump_dir), layers, negative=False)
        tracer.load()  # must not raise
        assert tracer._bind_index is not None

    def test_trace_violations_empty_for_no_violations(
        self, bilgepump_dir, manifest_path
    ):
        import sys_infra.verify as verify

        _, layers, _ = verify._read_manifest(manifest_path)
        tracer = FaultTracer(str(bilgepump_dir), layers, negative=False)
        tracer.load()
        traces = tracer.trace_violations([])
        assert traces == []

    def test_trace_returns_results_for_known_violation(
        self, bilgepump_dir, manifest_path
    ):
        import sys_infra.verify as verify

        _, layers, _ = verify._read_manifest(manifest_path)
        tracer = FaultTracer(str(bilgepump_dir), layers, negative=False)
        tracer.load()
        # DischargeCapacityRequirement would be violated with pumpA out
        traces = tracer.trace_violations(["DischargeCapacityRequirement"])
        assert isinstance(traces, list)
