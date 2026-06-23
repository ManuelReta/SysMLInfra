#!/usr/bin/env python3
"""
bilgepump_assertions.py
=======================
SINGLE SOURCE OF TRUTH for the BilgePump verification assertions.

Each entry names a computed-Boolean attribute in the published model that the
SysML v2 kernel can evaluate with ``%eval``.  ``make_publish_notebook.py`` emits
one ``%eval`` cell per assertion (tagged with the entry's metadata); after the
notebook is executed headlessly, ``materialize_sysml_values.py`` reads those
cell outputs and writes the ``sysml_assertions`` database table.

WHY COMPUTED BOOLEANS (not ``assert requirement``)
--------------------------------------------------
The Pilot kernel does not execute ``assert requirement`` / ``analysis def`` and
cannot override an attribute already bound by Architecture.  So every check is
re-expressed as a computed Boolean attribute on a concrete subject:

    part bpVerification : BilgePumpSystem {
        attribute BPS_REQ_001_waterLevel : Boolean = sensor.waterLevel <= 0.3;
    }

``%eval BilgePump_Analysis::bpVerification.BPS_REQ_001_waterLevel`` then returns
``LiteralBoolean true`` (SATISFIED) or ``false`` (VIOLATED).

FORESIGHT — ADDING / CHANGING ASSERTIONS
----------------------------------------
* New positive check  -> add a computed Boolean to Analysis.sysml + an entry
  here with kind="positive", expected=True.
* New negative (FMEA) -> add a fault instance + Boolean to FMEA.sysml + an entry
  here with kind="negative", expected=False.
* New UQ sweep point  -> add a Boolean to UQ.sysml + an entry here.
The pipeline (generator + materializer) picks up the new entry automatically;
nothing else needs editing.

Each entry:
    id           short stable assertion id (DB primary identity within a commit)
    fqn          fully-qualified attribute path for ``%eval``
    layer        owning layer name (Analysis | FMEA | UQ)
    requirement  requirement / failure-mode / sweep id this verifies
    kind         "positive" | "negative" | "uq"
    expected     expected Boolean verdict (True = SATISFIED / pass-as-designed)
    note         human-readable description
"""

from __future__ import annotations

ANALYSIS = "BilgePump_Analysis"
FMEA = "BilgePump_FMEA"
UQ = "BilgePump_UQ"


def _a(id, fqn, layer, requirement, kind, expected, note):
    return dict(
        id=id,
        fqn=fqn,
        layer=layer,
        requirement=requirement,
        kind=kind,
        expected=expected,
        note=note,
    )


ASSERTIONS: list[dict] = [
    # ---- POSITIVE: functional verification (bpVerification) -----------------
    _a(
        "BPS-REQ-001",
        f"{ANALYSIS}::bpVerification.BPS_REQ_001_waterLevel",
        "Analysis",
        "BPS-REQ-001",
        "positive",
        True,
        "Water level <= 0.30 m (MARPOL 73/78)",
    ),
    _a(
        "BPS-REQ-002",
        f"{ANALYSIS}::bpVerification.BPS_REQ_002_redundancy",
        "Analysis",
        "BPS-REQ-002",
        "positive",
        True,
        "Pump B redundancy active (DNV Pt.4 Ch.6)",
    ),
    _a(
        "BPS-REQ-003",
        f"{ANALYSIS}::bpVerification.BPS_REQ_003_alarm",
        "Analysis",
        "BPS-REQ-003",
        "positive",
        True,
        "Alarm delay <= 2.0 s (IEC 60945)",
    ),
    _a(
        "BPS-REQ-004",
        f"{ANALYSIS}::bpVerification.BPS_REQ_004_discharge",
        "Analysis",
        "BPS-REQ-004",
        "positive",
        True,
        "Combined discharge >= design inflow (SOLAS II-1)",
    ),
    _a(
        "PHYSICS-NET",
        f"{ANALYSIS}::bpVerification.physicsCheck",
        "Analysis",
        "BPS-REQ-004",
        "positive",
        True,
        "Net effective discharge (eta, losses) >= inflow",
    ),
    # ---- POSITIVE: timing verification (bpTimingVerification) ----------------
    _a(
        "BPS-REQ-005",
        f"{ANALYSIS}::bpTimingVerification.BPS_REQ_005_activation",
        "Analysis",
        "BPS-REQ-005",
        "positive",
        True,
        "Controller activation <= 5.0 s",
    ),
    _a(
        "BPS-REQ-006",
        f"{ANALYSIS}::bpTimingVerification.BPS_REQ_006_failover",
        "Analysis",
        "BPS-REQ-006",
        "positive",
        True,
        "Failover switch <= 3.0 s",
    ),
    _a(
        "BPS-REQ-003T",
        f"{ANALYSIS}::bpTimingVerification.BPS_REQ_003_alarmTiming",
        "Analysis",
        "BPS-REQ-003",
        "positive",
        True,
        "Alarm delay <= 2.0 s (timing context)",
    ),
    _a(
        "TIMING-BUDGET",
        f"{ANALYSIS}::bpTimingVerification.timingBudgetOk",
        "Analysis",
        "BPS-REQ-005",
        "positive",
        True,
        "Timing budget total <= 5.0 s",
    ),
    # ---- POSITIVE: fault-tolerance verification (bpFaultToleranceVerification)
    _a(
        "BPS-FT-001",
        f"{ANALYSIS}::bpFaultToleranceVerification.BPS_FT_001_sensorAccuracy",
        "Analysis",
        "BPS-FT-001",
        "positive",
        True,
        "Reported level + sensor accuracy <= 0.30 m",
    ),
    _a(
        "BPS-FT-002",
        f"{ANALYSIS}::bpFaultToleranceVerification.BPS_FT_002_effDischarge",
        "Analysis",
        "BPS-FT-002",
        "positive",
        True,
        "Per-pump effective discharge >= inflow",
    ),
    _a(
        "BPS-FT-003",
        f"{ANALYSIS}::bpFaultToleranceVerification.BPS_FT_003_triggerAccuracy",
        "Analysis",
        "BPS-FT-003",
        "positive",
        True,
        "Trigger level + sensor accuracy <= 0.30 m",
    ),
    _a(
        "BPS-FT-004",
        f"{ANALYSIS}::bpFaultToleranceVerification.BPS_FT_004_responseWindow",
        "Analysis",
        "BPS-FT-004",
        "positive",
        True,
        "Response chain feasible vs overflow window",
    ),
    _a(
        "BPS-OOR-001",
        f"{ANALYSIS}::bpFaultToleranceVerification.BPS_OOR_001_overrideOrdering",
        "Analysis",
        "BPS-OOR-001",
        "positive",
        True,
        "Override only after alarm active",
    ),
    # ---- NEGATIVE: FMEA fault injections (expected VIOLATED) ----------------
    _a(
        "FM-S-001-alarm",
        f"{FMEA}::FM_S_001_alarm",
        "FMEA",
        "BPS-REQ-003",
        "negative",
        False,
        "Sensor fail-silent -> alarm never fires",
    ),
    _a(
        "FM-S-001-disch",
        f"{FMEA}::FM_S_001_discharge",
        "FMEA",
        "BPS-REQ-004",
        "negative",
        False,
        "Sensor fail-silent -> no discharge",
    ),
    _a(
        "FM-PA-002-eff",
        f"{FMEA}::FM_PA_002_effDischarge",
        "FMEA",
        "BPS-FT-002",
        "negative",
        False,
        "Pump A cavitation -> effective discharge < inflow",
    ),
    _a(
        "FM-PB-001-red",
        f"{FMEA}::FM_PB_001_redundancy",
        "FMEA",
        "BPS-REQ-002",
        "negative",
        False,
        "Pump B feed lost -> redundancy violated",
    ),
    _a(
        "FM-C-001-act",
        f"{FMEA}::FM_C_001_activation",
        "FMEA",
        "BPS-REQ-005",
        "negative",
        False,
        "Controller hang -> activation timing violated",
    ),
    _a(
        "FM-C-001-alarm",
        f"{FMEA}::FM_C_001_alarm",
        "FMEA",
        "BPS-REQ-003",
        "negative",
        False,
        "Controller hang -> alarm frozen",
    ),
    _a(
        "FM-C-001-disch",
        f"{FMEA}::FM_C_001_discharge",
        "FMEA",
        "BPS-REQ-004",
        "negative",
        False,
        "Controller hang -> no discharge",
    ),
    _a(
        "FM-C-003-fail",
        f"{FMEA}::FM_C_003_failover",
        "FMEA",
        "BPS-REQ-006",
        "negative",
        False,
        "Failover not triggered -> timing violated",
    ),
    _a(
        "FM-C-003-disch",
        f"{FMEA}::FM_C_003_discharge",
        "FMEA",
        "BPS-REQ-004",
        "negative",
        False,
        "Failover not triggered -> no discharge",
    ),
    # ---- UQ: deterministic sigma-step sweep (1-9 SATISFIED, 10 VIOLATED) -----
    *[
        _a(
            f"UQ-SWEEP-{i:02d}",
            f"{UQ}::UQ_Sweep_{i:02d}",
            "UQ",
            f"UQ-{i:02d}",
            "uq",
            i != 10,
            "Combined 3-sigma extreme -> discharge < inflow"
            if i == 10
            else "Parametric sweep point -> discharge >= inflow",
        )
        for i in range(1, 11)
    ],
]


def summary() -> str:
    pos = sum(1 for a in ASSERTIONS if a["kind"] == "positive")
    neg = sum(1 for a in ASSERTIONS if a["kind"] == "negative")
    uq = sum(1 for a in ASSERTIONS if a["kind"] == "uq")
    return f"{len(ASSERTIONS)} assertions ({pos} positive, {neg} negative, {uq} UQ)"


if __name__ == "__main__":
    print(summary())
    for a in ASSERTIONS:
        print(f"  {a['id']:<16} expect={str(a['expected']):<5} {a['fqn']}")
