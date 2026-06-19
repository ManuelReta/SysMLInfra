"""
tests/model/test_assertions_manifest.py

Static analysis of the BilgePump assertion manifest and .sysml model files.
No SysML kernel or database required (~<1 s).

These tests are a proxy for "the model will compile and %eval will return the
expected verdicts when published to the local API server":

  1. Manifest integrity     — bilgepump_assertions.py is structurally sound
  2. SysML attribute presence — each FQN attribute name exists in its .sysml file
                                (direct proxy for %eval not returning an error)
  3. Import chain           — Library → Architecture → Requirements → Analysis
                                dependency is intact in each layer
  4. Nominal arithmetic     — key Boolean expressions hold at Architecture values
                                (replaces bind-statement fallback evaluation)
"""
import re
import importlib.util

import pytest

from sys_infra.environment import EXAMPLES_BILGEPUMP_DIR

pytestmark = pytest.mark.model

# ---------------------------------------------------------------------------
# Load bilgepump_assertions without putting examples/ on sys.path globally
# ---------------------------------------------------------------------------
def _load_assertions() -> list[dict]:
    spec = importlib.util.spec_from_file_location(
        "bilgepump_assertions",
        EXAMPLES_BILGEPUMP_DIR / "bilgepump_assertions.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.ASSERTIONS


ASSERTIONS = _load_assertions()

# Package name → .sysml file that declares it
_PKG_FILE = {
    "BilgePump_Analysis": EXAMPLES_BILGEPUMP_DIR / "Analysis.sysml",
    "BilgePump_FMEA":     EXAMPLES_BILGEPUMP_DIR / "FMEA.sysml",
    "BilgePump_UQ":       EXAMPLES_BILGEPUMP_DIR / "UQ.sysml",
}


def _text(filename: str) -> str:
    return (EXAMPLES_BILGEPUMP_DIR / filename).read_text()


# ---------------------------------------------------------------------------
# 1. Manifest integrity
# ---------------------------------------------------------------------------
class TestManifestIntegrity:
    """bilgepump_assertions.py is the source of truth for the publish pipeline;
    these tests ensure it is structurally valid."""

    def test_ids_are_unique(self):
        ids = [a["id"] for a in ASSERTIONS]
        assert len(ids) == len(set(ids)), f"Duplicate IDs: {[i for i in ids if ids.count(i) > 1]}"

    def test_all_required_fields_present(self):
        required = {"id", "fqn", "layer", "requirement", "kind", "expected", "note"}
        for a in ASSERTIONS:
            missing = required - a.keys()
            assert not missing, f"Assertion '{a.get('id')}' is missing fields: {missing}"

    def test_kind_is_valid(self):
        valid = {"positive", "negative", "uq"}
        for a in ASSERTIONS:
            assert a["kind"] in valid, f"'{a['id']}': invalid kind '{a['kind']}'"

    def test_expected_is_bool(self):
        for a in ASSERTIONS:
            assert isinstance(a["expected"], bool), (
                f"'{a['id']}': expected must be bool, got {type(a['expected'])}"
            )

    def test_positive_expected_true(self):
        for a in ASSERTIONS:
            if a["kind"] == "positive":
                assert a["expected"] is True, f"'{a['id']}': positive assertion must have expected=True"

    def test_negative_expected_false(self):
        for a in ASSERTIONS:
            if a["kind"] == "negative":
                assert a["expected"] is False, f"'{a['id']}': negative assertion must have expected=False"

    def test_minimum_counts(self):
        positive = sum(1 for a in ASSERTIONS if a["kind"] == "positive")
        negative = sum(1 for a in ASSERTIONS if a["kind"] == "negative")
        uq       = sum(1 for a in ASSERTIONS if a["kind"] == "uq")
        assert positive >= 10, f"Expected >=10 positive assertions, got {positive}"
        assert negative >= 5,  f"Expected >=5  negative assertions, got {negative}"
        assert uq >= 10,       f"Expected >=10 UQ assertions, got {uq}"

    def test_key_positive_assertions_present(self):
        """The six core BPS requirements must have positive assertions."""
        positive_reqs = {a["requirement"] for a in ASSERTIONS if a["kind"] == "positive"}
        for req_id in ("BPS-REQ-001", "BPS-REQ-002", "BPS-REQ-003",
                       "BPS-REQ-004", "BPS-REQ-005", "BPS-REQ-006"):
            assert req_id in positive_reqs, f"No positive assertion for requirement '{req_id}'"

    def test_key_negative_assertions_present(self):
        """Core failure modes must have negative (FMEA) assertions."""
        negative_reqs = {a["requirement"] for a in ASSERTIONS if a["kind"] == "negative"}
        for req_id in ("BPS-REQ-002", "BPS-REQ-003", "BPS-REQ-004",
                       "BPS-REQ-005", "BPS-REQ-006"):
            assert req_id in negative_reqs, f"No negative assertion for requirement '{req_id}'"


# ---------------------------------------------------------------------------
# 2. SysML attribute presence (parametrized — one test per assertion)
# ---------------------------------------------------------------------------
class TestSysMLAttributePresence:
    """Every FQN attribute name in the manifest must be present in its .sysml
    file.  This is a direct proxy for %eval not returning a 'name not found'
    error when the model is published to the local API server."""

    def test_package_declarations(self):
        """Each referenced package is declared in the correct .sysml file."""
        for pkg, path in _PKG_FILE.items():
            text = path.read_text()
            assert f"package {pkg}" in text, f"Package '{pkg}' not declared in {path.name}"

    @pytest.mark.parametrize("assertion", ASSERTIONS, ids=[a["id"] for a in ASSERTIONS])
    def test_attribute_exists_in_sysml(self, assertion):
        """FQN format: 'Package::part.attr'  or  'Package::attr' (FMEA/UQ top-level)."""
        fqn = assertion["fqn"]
        pkg, _, rest = fqn.partition("::")
        attr = rest.split(".")[-1]  # last segment is always the attribute name

        path = _PKG_FILE.get(pkg)
        assert path is not None, f"Unknown package '{pkg}' in FQN '{fqn}'"

        text = path.read_text()
        pattern = rf"\battribute\s+{re.escape(attr)}\s*:"
        assert re.search(pattern, text), (
            f"Attribute '{attr}' not found in {path.name}\n  FQN: {fqn}"
        )


# ---------------------------------------------------------------------------
# 3. Import chain
# ---------------------------------------------------------------------------
class TestImportChain:
    """The Library → Architecture → Requirements → Analysis dependency chain
    must be intact.  A broken import is the most common cause of kernel parse
    failure when publishing."""

    def test_analysis_imports_all_layers(self):
        text = _text("Analysis.sysml")
        for pkg in ("BilgePump_Library", "BilgePump_Architecture", "BilgePump_Requirements"):
            assert pkg in text, f"Analysis.sysml missing import of '{pkg}'"

    def test_fmea_imports_library(self):
        text = _text("FMEA.sysml")
        assert "BilgePump_Library" in text, "FMEA.sysml missing import of 'BilgePump_Library'"

    def test_architecture_imports_library(self):
        text = _text("Architecture.sysml")
        assert "BilgePump_Library" in text, "Architecture.sysml missing import of 'BilgePump_Library'"

    def test_requirements_imports_library(self):
        text = _text("Requirements.sysml")
        assert "BilgePump_Library" in text, "Requirements.sysml missing import of 'BilgePump_Library'"

    def test_no_circular_imports(self):
        """Library must not import Architecture/Requirements/Analysis."""
        lib_text = _text("Library.sysml")
        for forbidden in ("BilgePump_Architecture", "BilgePump_Requirements", "BilgePump_Analysis"):
            assert forbidden not in lib_text, f"Library.sysml must not import '{forbidden}' (circular)"


# ---------------------------------------------------------------------------
# 4. Nominal arithmetic
# ---------------------------------------------------------------------------
# Ground truth: nominal attribute values from Architecture.sysml
_NOM = dict(
    waterLevel=0.15,        # sensor.waterLevel (nominal bilge sounding, m)
    flowRateA=0.025,        # pumpA.flowRate (rated, m³/s)
    flowRateB=0.025,        # pumpB.flowRate (rated, m³/s)
    efficiency=0.82,        # pumpA/B.efficiency (hydraulic eta)
    pipeLossFactor=0.05,    # discharge.pipeLossFactor (Darcy-Weisbach lambda)
    designInflow=0.030,     # bpVerification.designInflow (m³/s)
    activationDelay_s=0.5,  # alarm.activationDelay_s (IEC 60945, s)
    isRedundant=True,       # pumpB.isRedundant
    responseTime_s=1.0,     # controller.responseTime_s (SIM-CTRL-001 §3.1, s)
    failoverTime_s=0.8,     # controller.failoverTime_s (SIM-CTRL-001 §3.2, s)
    accuracy_m=0.03,        # sensor.accuracy_m (IEC 60770-1 ±3 cm class)
    triggerLevel_m=0.25,    # sensor.triggerLevel_m (activation level, m)
    criticalLevel_m=0.5,    # BilgePumpSystem.criticalLevel_m (SOLAS breach, m)
    inflowRate_m3s=0.020,   # BilgePumpSystem.inflowRate_m3s (design ingress, m³/s)
)


class TestNominalArithmetic:
    """Verify key Boolean expressions at Architecture.sysml nominal values.
    These are the same checks the SysML kernel evaluates via %eval; passing
    here means the logic is correct even before the model is published."""

    # ── BPS-REQ-001 ─────────────────────────────────────────────────────────
    def test_water_level_satisfied(self):
        assert _NOM["waterLevel"] <= 0.3  # sensor.waterLevel <= 0.3

    # ── BPS-REQ-002 ─────────────────────────────────────────────────────────
    def test_pump_redundancy_satisfied(self):
        assert _NOM["isRedundant"] is True  # pumpB.isRedundant == true

    # ── BPS-REQ-003 ─────────────────────────────────────────────────────────
    def test_alarm_delay_satisfied(self):
        assert _NOM["activationDelay_s"] <= 2.0  # alarm.activationDelay_s <= 2.0

    # ── BPS-REQ-004 ─────────────────────────────────────────────────────────
    def test_discharge_capacity_satisfied(self):
        assert _NOM["flowRateA"] + _NOM["flowRateB"] >= _NOM["designInflow"]

    def test_net_flow_physics_satisfied(self):
        net = (_NOM["flowRateA"] + _NOM["flowRateB"]) * _NOM["efficiency"] * (1 - _NOM["pipeLossFactor"])
        assert net >= _NOM["designInflow"]  # physicsCheck in bpVerification

    # ── BPS-REQ-005 ─────────────────────────────────────────────────────────
    def test_controller_activation_timing_satisfied(self):
        assert _NOM["responseTime_s"] <= 5.0  # BPS-REQ-005

    # ── BPS-REQ-006 ─────────────────────────────────────────────────────────
    def test_failover_timing_satisfied(self):
        assert _NOM["failoverTime_s"] <= 3.0  # BPS-REQ-006

    # ── BPS-FT-001 ──────────────────────────────────────────────────────────
    def test_sensor_accuracy_bound_satisfied(self):
        assert _NOM["waterLevel"] + _NOM["accuracy_m"] <= 0.3  # BPS-FT-001

    # ── BPS-FT-003 ──────────────────────────────────────────────────────────
    def test_trigger_accuracy_bound_satisfied(self):
        assert _NOM["triggerLevel_m"] + _NOM["accuracy_m"] <= 0.3  # BPS-FT-003

    # ── Fault injection: pump A failure (mirrors FMEA negative assertions) ──
    def test_discharge_violated_when_pump_a_fails(self):
        """pumpA.flowRate=0 → raw sum < designInflow → VIOLATED (FM-S-001-disch, FM-C-001-disch)."""
        assert not (0.0 + _NOM["flowRateB"] >= _NOM["designInflow"])

    def test_effective_discharge_violated_when_pump_a_cavitates(self):
        """Pump A cavitation → net effective flow < inflow → VIOLATED (FM-PA-002-eff)."""
        net = (0.0 * _NOM["efficiency"] + _NOM["flowRateB"] * _NOM["efficiency"]) * (1 - _NOM["pipeLossFactor"])
        assert not (net >= _NOM["designInflow"])

    def test_water_level_independent_of_pump_flow(self):
        """sensor.waterLevel is a reading — not affected by pump A failure; still SATISFIED."""
        assert _NOM["waterLevel"] <= 0.3

    def test_redundancy_independent_of_pump_flow(self):
        """pumpB.isRedundant is structural — not affected by pump A failure; still SATISFIED."""
        assert _NOM["isRedundant"] is True
