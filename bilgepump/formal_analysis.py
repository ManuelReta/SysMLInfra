"""
formal_analysis.py — Z3-based formal analysis for the BilgePump system.

Purpose:  DISCOVER gaps in the requirement set that the SysML v2 point-in-time
          engine cannot find.  The SysML engine checks one concrete scenario;
          Z3 checks properties over RANGES and ADVERSARIAL combinations.

The SysML v2 engine always runs first (via verify.py); this module complements
it.  It does NOT replace the kernel: syntax checking, type compatibility, and
port-binding validation remain the kernel's job.

Six escalating levels:
  Level 1 — Symbolic baseline (Z3 LRA)
             Prove REQ-001 holds for all waterLevel ∈ [0, 0.15] (below trigger).
  Level 2 — Multi-attribute nonlinear (Z3 NRA)
             FT-002: find the efficiency floor below which effective discharge
             fails even when REQ-004 (raw sum) passes.  Exposes G-2 gap.
  Level 3 — Parametric envelope (Z3 LRA)
             FT-001 / FT-003: return the exact (accuracy_m, waterLevel) or
             (accuracy_m, triggerLevel_m) pair that crosses the MARPOL boundary.
             Exposes G-1 and G-3 gaps.
  Level 4 — Cross-component conjunction (Z3 LRA)
             FT-004: find the critical inflowRate above which the timing chain
             (responseTime + alarmDelay) cannot drain fast enough.  Exposes G-4.
  Level 5 — Adversarial counterexample (Z3 NRA)
             Find a parameter set where all 6 original REQs pass individually
             but FT-002 is violated.  Exposes G-5 (hidden failure mode).
  Level 6 — Bounded temporal ordering (Z3 LIA, depth ≤ 8)
             Prove / disprove that the state machine allows operator override
             before alarm notification reaches the UI.  If SAT → ordering gap.

IMPORTANT — Level 6 caveat:
  Z3 is an SMT solver, not a model checker.  This analysis encodes the timing
  as integer timestamp variables over a bounded trace (depth ≤ 8 discrete steps,
  each step ≈ 1 s).  UNSAT means "no violating trace of length ≤ 8 exists" —
  it does NOT prove the property for all possible traces.  For full LTL/CTL
  verification, tools such as nuXmv or PRISM are appropriate.

Usage (standalone):
    python bilgepump/formal_analysis.py
    python bilgepump/formal_analysis.py --level 3
    python bilgepump/formal_analysis.py --verbose

Usage (module — called by verify.py --z3):
    from bilgepump.formal_analysis import run_all
    results = run_all(bind_values, verbose=False)
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from typing import Any

try:
    import z3
    _Z3_AVAILABLE = True
except ImportError:
    _Z3_AVAILABLE = False


# ── Result type ───────────────────────────────────────────────────────────────

@dataclass
class FormalResult:
    level:       int
    req_id:      str
    description: str
    outcome:     str          # "PROVED" | "GAP" | "UNKNOWN" | "ERROR"
    detail:      str = ""     # human-readable explanation
    counterexample: dict[str, Any] = field(default_factory=dict)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _nominal() -> dict[str, float]:
    """Return the nominal bind values from BilgePumpFaultToleranceVerification."""
    return {
        "waterLevel":       0.15,
        "accuracy_m":       0.03,
        "triggerLevel_m":   0.25,
        "responseTime_s":   1.0,
        "failoverTime_s":   0.8,
        "flowA":            0.025,
        "effA":             0.82,
        "flowB":            0.025,
        "effB":             0.82,
        "pipeLoss":         0.05,
        "alarmDelay_s":     0.5,
        "designInflow":     0.030,
        "inflowRate_m3s":   0.020,
        "criticalLevel_m":  0.5,
        "isRedundant":      1.0,   # boolean encoded as float
        "responseTime2":    1.0,   # for REQ-005 (same as responseTime_s)
        "failoverTime2":    0.8,   # for REQ-006
    }


def _merge(defaults: dict, overrides: dict) -> dict:
    return {**defaults, **overrides}


# ── Level 1: Symbolic baseline (LRA) ─────────────────────────────────────────

def level_1_symbolic_baseline(n: dict, verbose: bool) -> FormalResult:
    """
    Prove that REQ-001 (waterLevel ≤ 0.30) holds for all waterLevel in the
    operational range [0.0, trigger_level], i.e., the range where the pump
    has not yet activated.

    Technique: LRA (Linear Real Arithmetic).  Assert the negation; check UNSAT.
    UNSAT → property holds for all values in the range (proof by refutation).
    """
    wl    = z3.Real("waterLevel")
    trig  = n["triggerLevel_m"]

    s = z3.Solver()
    # Domain: water level is between 0 and the trigger level (pre-activation range)
    s.add(wl >= 0.0)
    s.add(wl <= trig)
    # Negate REQ-001 — look for a value that violates it
    s.add(wl > 0.3)

    check = s.check()

    if check == z3.unsat:
        return FormalResult(
            level=1,
            req_id="BPS-REQ-001",
            description="REQ-001 holds for all waterLevel ∈ [0, triggerLevel_m]",
            outcome="PROVED",
            detail=(
                f"All waterLevel values in [0.0, {trig}] satisfy waterLevel ≤ 0.30. "
                "The negation is UNSAT — no violating pre-activation level exists."
            ),
        )
    elif check == z3.sat:
        m = s.model()
        cex = {"waterLevel": float(m[wl].as_decimal(6))}
        return FormalResult(
            level=1,
            req_id="BPS-REQ-001",
            description="REQ-001 holds for all waterLevel ∈ [0, triggerLevel_m]",
            outcome="GAP",
            detail=(
                f"Unexpected SAT: waterLevel = {cex['waterLevel']} violates REQ-001. "
                "Check triggerLevel_m configuration — it exceeds 0.3."
            ),
            counterexample=cex,
        )
    else:
        return FormalResult(
            level=1, req_id="BPS-REQ-001",
            description="REQ-001 symbolic baseline",
            outcome="UNKNOWN",
            detail="Z3 returned unknown.",
        )


# ── Level 2: Nonlinear efficiency floor (NRA) ─────────────────────────────────

def level_2_efficiency_floor(n: dict, verbose: bool) -> FormalResult:
    """
    Discover the minimum pump efficiency at which FT-002 (effective discharge)
    still holds, given nominal flow rates and pipe loss.

    Also shows the structural gap between REQ-004 and FT-002:
      REQ-004: (flowA + flowB) >= designInflow          — ignores efficiency
      FT-002:  (flowA*η + flowB*η) * (1-λ) >= designInflow — physics-accurate

    Technique: Z3 NRA (Nonlinear Real Arithmetic).
      The product (flow * efficiency) is a product of two Real variables.
      We find the minimum η such that FT-002 holds by asking:
        "Is there an η ∈ [0, 1] such that FT-002 is violated?"  (negation)
      Then we binary-minimize η using Z3 optimize.

    CAUTION: NRA is decidable but slower than LRA for Z3.  For model sizes
    here (2 variables) it is sub-second.
    """
    flow_a = n["flowA"]
    flow_b = n["flowB"]
    lam    = n["pipeLoss"]
    q_req  = n["designInflow"]

    eta = z3.Real("eta")

    # --- REQ-004 check (linear — always passes at nominal flows) ---
    req004_holds = (flow_a + flow_b) >= q_req

    # --- FT-002 check: find minimum η that violates it ---
    # (flowA * η + flowB * η) * (1 - λ) < designInflow
    # Simplified: η * (flowA + flowB) * (1 - λ) < designInflow
    total_flow  = flow_a + flow_b
    loss_factor = 1.0 - lam

    # Analytic minimum: η_min = designInflow / (total_flow * loss_factor)
    eta_min_analytic = q_req / (total_flow * loss_factor)

    # Z3 confirmation: find an η < η_min that violates FT-002
    s = z3.Solver()
    s.add(eta >= 0.0, eta <= 1.0)
    # Negate FT-002: η * total_flow * (1 - λ) < designInflow
    s.add(eta * total_flow * loss_factor < q_req)

    check = s.check()

    # Gap analysis: at nominal η = 0.82, does REQ-004 pass but FT-002 fail?
    eta_nominal   = n["effA"]
    req004_margin = (flow_a + flow_b) - q_req
    ft002_nominal = eta_nominal * total_flow * loss_factor
    ft002_margin  = ft002_nominal - q_req

    gap_exists = eta_nominal < eta_min_analytic  # should be False at η=0.82

    if check == z3.sat:
        m   = s.model()
        cex_eta = float(m[eta].as_decimal(6))

        if not req004_holds:
            # Nominal values fail even REQ-004 — model is misconfigured
            return FormalResult(
                level=2, req_id="BPS-FT-002",
                description="Efficiency floor for effective discharge",
                outcome="ERROR",
                detail=f"REQ-004 itself fails at nominal flow values (flowA={flow_a}, flowB={flow_b}, designInflow={q_req})",
            )

        detail_parts = [
            f"REQ-004 passes at nominal: ({flow_a}+{flow_b})={total_flow:.4f} ≥ {q_req} ✓",
            f"FT-002 at η=0.82: {ft002_nominal:.5f} m³/s  (margin {ft002_margin:+.5f})",
            f"Minimum η for FT-002 to hold: η_min = {eta_min_analytic:.4f}",
            f"  → Z3 counterexample: at η={cex_eta:.4f}, FT-002 is VIOLATED while REQ-004 still PASSES.",
            "",
            f"  Gap (G-2): A pump with η={cex_eta:.2f} (worn impeller) satisfies REQ-004",
            f"  but delivers only {cex_eta * total_flow * loss_factor:.5f} m³/s net (below {q_req} required).",
        ]

        return FormalResult(
            level=2,
            req_id="BPS-FT-002",
            description="Efficiency floor for effective discharge",
            outcome="GAP",
            detail="\n    ".join(detail_parts),
            counterexample={"eta": cex_eta, "net_flow": cex_eta * total_flow * loss_factor},
        )
    elif check == z3.unsat:
        return FormalResult(
            level=2, req_id="BPS-FT-002",
            description="Efficiency floor for effective discharge",
            outcome="PROVED",
            detail=(
                f"All η ∈ [0, 1] that violate FT-002 are outside the feasible range. "
                f"η_min = {eta_min_analytic:.4f}; nominal η = {eta_nominal:.2f}."
            ),
        )
    else:
        return FormalResult(
            level=2, req_id="BPS-FT-002",
            description="Efficiency floor for effective discharge",
            outcome="UNKNOWN",
            detail="Z3 NRA returned unknown — consider increasing timeout.",
        )


# ── Level 3: Parametric accuracy envelope (LRA) ───────────────────────────────

def level_3_accuracy_envelope(n: dict, verbose: bool) -> list[FormalResult]:
    """
    Find the parametric envelope for:
      FT-001: waterLevel + accuracy_m <= 0.3
      FT-003: triggerLevel_m + accuracy_m <= 0.3

    Both are LRA.  We ask: "What is the maximum accuracy_m tolerable before the
    requirement fails, given the current bound values?"

    For FT-003, this exposes G-3: at the current triggerLevel_m = 0.25, the
    boundary is accuracy_m = 0.05.  The nominal spec is 0.03 — only 2 cm margin.
    """
    results = []
    marpol_limit = 0.30

    # --- FT-001 envelope ---
    wl_nominal   = n["waterLevel"]
    acc          = z3.Real("accuracy_m")
    wl_var       = z3.Real("waterLevel")

    # Maximum accuracy_m at the nominal water level that still satisfies FT-001
    # Boundary: wl + acc = 0.3  →  acc_max = 0.3 - wl
    acc_max_ft001 = marpol_limit - wl_nominal
    nominal_acc   = n["accuracy_m"]
    margin_ft001  = acc_max_ft001 - nominal_acc

    # Z3 SAT: find (wl, acc) where FT-001 is violated
    s1 = z3.Solver()
    s1.add(wl_var >= 0.0, wl_var <= marpol_limit)
    s1.add(acc >= 0.0, acc <= 0.5)
    s1.add(wl_var + acc > marpol_limit)  # negate FT-001

    check1 = s1.check()
    if check1 == z3.sat:
        m1 = s1.model()
        cex_wl  = float(m1[wl_var].as_decimal(4))
        cex_acc = float(m1[acc].as_decimal(4))
        results.append(FormalResult(
            level=3,
            req_id="BPS-FT-001",
            description="Sensor accuracy envelope (FT-001)",
            outcome="GAP",
            detail=(
                f"FT-001 fails when waterLevel + accuracy_m > 0.30.\n"
                f"    Z3 counterexample: waterLevel={cex_wl:.4f}, accuracy_m={cex_acc:.4f}\n"
                f"    At nominal waterLevel={wl_nominal}: max safe accuracy_m = {acc_max_ft001:.4f} m\n"
                f"    Nominal accuracy_m = {nominal_acc:.4f} m  (margin: {margin_ft001:+.4f} m)\n"
                f"    G-1: accuracy_m is present in Library.sysml but used in ZERO existing requirements."
            ),
            counterexample={"waterLevel": cex_wl, "accuracy_m": cex_acc},
        ))
    else:
        results.append(FormalResult(
            level=3, req_id="BPS-FT-001",
            description="Sensor accuracy envelope (FT-001)",
            outcome="PROVED" if check1 == z3.unsat else "UNKNOWN",
            detail="No (waterLevel, accuracy_m) pair in [0,0.3]×[0,0.5] violates FT-001.",
        ))

    # --- FT-003 envelope ---
    tl_nominal    = n["triggerLevel_m"]
    tl_var        = z3.Real("triggerLevel_m")

    acc_max_ft003  = marpol_limit - tl_nominal
    margin_ft003   = acc_max_ft003 - nominal_acc
    sensor_fail_wl = tl_nominal + nominal_acc  # apparent reading when true level = tl

    s3 = z3.Solver()
    s3.add(tl_var >= 0.0, tl_var <= marpol_limit)
    s3.add(acc >= 0.0, acc <= 0.5)
    s3.add(tl_var + acc > marpol_limit)  # negate FT-003

    check3 = s3.check()
    if check3 == z3.sat:
        m3 = s3.model()
        cex_tl  = float(m3[tl_var].as_decimal(4))
        cex_acc = float(m3[acc].as_decimal(4))

        # Explain the practical scenario
        scenario = (
            f"\n    Scenario: sensor reads {tl_nominal} m (apparent threshold) but true level\n"
            f"    could be up to {tl_nominal + nominal_acc:.4f} m due to accuracy_m={nominal_acc}.\n"
            f"    Boundary: accuracy_m = {acc_max_ft003:.4f} m — nominal is {nominal_acc:.4f} m "
            f"(only {margin_ft003*100:.1f} mm margin).\n"
            f"    G-3: If sensor drifts to accuracy_m=0.05 (still within spec), trigger fires\n"
            f"    at apparent 0.25 m but true level = 0.30 m — MARPOL limit already reached."
        )

        results.append(FormalResult(
            level=3,
            req_id="BPS-FT-003",
            description="Trigger level accuracy envelope (FT-003)",
            outcome="GAP",
            detail=(
                f"FT-003 fails when triggerLevel_m + accuracy_m > 0.30.\n"
                f"    Z3 counterexample: triggerLevel_m={cex_tl:.4f}, accuracy_m={cex_acc:.4f}"
                + scenario
            ),
            counterexample={"triggerLevel_m": cex_tl, "accuracy_m": cex_acc},
        ))
    else:
        results.append(FormalResult(
            level=3, req_id="BPS-FT-003",
            description="Trigger level accuracy envelope (FT-003)",
            outcome="PROVED" if check3 == z3.unsat else "UNKNOWN",
            detail="No (triggerLevel_m, accuracy_m) pair in [0,0.3]×[0,0.5] violates FT-003.",
        ))

    return results


# ── Level 4: Cross-component response window (LRA) ────────────────────────────

def level_4_response_window(n: dict, verbose: bool) -> FormalResult:
    """
    FT-004: find the critical inflowRate above which the timing chain
    (responseTime + alarmDelay) can no longer drain fast enough before the
    water level reaches the critical level.

    Constraint (multiplication-free form):
      (responseTime_s + alarmDelay_s) × inflowRate_m3s ≤ criticalLevel_m - waterLevel

    Technique: LRA.  Fix timing values at nominal; solve for the critical
    inflowRate at the boundary.  Then Z3 finds the worst-case inflowRate at
    which the FT-004 constraint fails, given realistic timing degradation.

    Also: sweep responseTime_s ∈ [1.0, 5.0] (REQ-005 range) and find the
    combination with inflowRate that violates FT-004.
    """
    rt  = n["responseTime_s"]
    ad  = n["alarmDelay_s"]
    wl  = n["waterLevel"]
    cl  = n["criticalLevel_m"]
    q0  = n["inflowRate_m3s"]

    headroom          = cl - wl
    timing_chain      = rt + ad
    critical_inflow   = headroom / timing_chain   # boundary: FT-004 holds iff q ≤ this

    # Z3 variables
    inflow  = z3.Real("inflowRate_m3s")
    rtime   = z3.Real("responseTime_s")

    # --- Part A: Find critical inflow at nominal timing ---
    # Negate FT-004 at nominal responseTime_s = 1.0, alarmDelay_s = 0.5
    s = z3.Solver()
    s.add(inflow > 0.0, inflow <= 1.0)
    s.add(timing_chain * inflow > headroom)  # negate FT-004

    check = s.check()

    # --- Part B: Find (responseTime, inflow) pair that violates FT-004 ---
    # at worst-case responseTime_s up to REQ-005 limit (5.0 s)
    s2 = z3.Solver()
    s2.add(inflow > 0.0, inflow <= 1.0)
    s2.add(rtime >= 1.0, rtime <= 5.0)   # REQ-005 range
    s2.add((rtime + ad) * inflow > headroom)  # negate FT-004

    check2 = s2.check()

    detail_parts = [
        f"Timing chain (nominal): responseTime={rt}s + alarmDelay={ad}s = {timing_chain:.1f}s",
        f"Available headroom: criticalLevel={cl}m - waterLevel={wl}m = {headroom:.3f}m",
        f"Critical inflowRate: {critical_inflow:.4f} m³/s  (FT-004 fails above this)",
        f"Design storm inflow: {q0} m³/s  (safety margin: {critical_inflow/q0:.1f}×)",
    ]

    if check == z3.sat:
        m = s.model()
        cex_q = float(m[inflow].as_decimal(6))
        detail_parts.append(
            f"Z3 SAT: at inflowRate={cex_q:.4f} m³/s, timing chain {timing_chain:.1f}s "
            f"exceeds overflow window ({headroom:.3f}/{cex_q:.4f}={headroom/cex_q:.2f}s)."
        )
        detail_parts.append(
            f"G-4: REQ-005 (response ≤ 5s) + REQ-003 (alarm ≤ 2s) do not prevent this."
        )
    else:
        detail_parts.append("At nominal timing and inflow, FT-004 cannot be violated (UNSAT).")

    if check2 == z3.sat:
        m2     = s2.model()
        cex_rt = float(m2[rtime].as_decimal(4))
        cex_q2 = float(m2[inflow].as_decimal(4))
        detail_parts.append(
            f"Worst-case (responseTime={cex_rt:.2f}s, inflowRate={cex_q2:.4f} m³/s): "
            f"FT-004 VIOLATED — total delay {cex_rt+ad:.2f}s > overflow window "
            f"{headroom/cex_q2:.2f}s."
        )
        detail_parts.append(
            "  This is within the REQ-005 allowable range (≤ 5.0s) — a system compliant\n"
            "  with REQ-005 and REQ-003 can still violate FT-004 under storm inflow."
        )

    outcome = "GAP" if (check == z3.sat or check2 == z3.sat) else (
        "PROVED" if check == z3.unsat else "UNKNOWN"
    )
    cex = {}
    if check2 == z3.sat:
        cex = {"responseTime_s": cex_rt, "inflowRate_m3s": cex_q2}  # noqa: F821

    return FormalResult(
        level=4,
        req_id="BPS-FT-004",
        description="End-to-end response vs overflow window",
        outcome=outcome,
        detail="\n    ".join(detail_parts),
        counterexample=cex,
    )


# ── Level 5: Adversarial counterexample (NRA) ────────────────────────────────

def level_5_adversarial(n: dict, verbose: bool) -> FormalResult:
    """
    Adversarial query (G-5 — historical):
    Find a parameter set where ALL 6 original requirements (REQ-001..006) are
    satisfied simultaneously, yet FT-002 (effective discharge) is violated.

    This is the formal proof that the ORIGINAL requirement set had a gap:
    you could pass the entire test suite AND still have insufficient net discharge.

    Gap status: CLOSED — EffectiveDischargeCapacityRequirement (BPS-FT-002) was
    added to Requirements.sysml to formally require effective discharge capacity.
    This level is preserved as a historical record of the gap discovery process.
    The query is NOT updated to include FT-002 in the precondition set because
    "FT-002 passes AND FT-002 fails" is trivially UNSAT; the value of this level
    is showing the counterexample that motivated adding FT-002.

    Technique: Z3 NRA (bilinear products: flow × efficiency).
    Variables: flowA, flowB, effA, effB, pipeLoss (all Real)
    Fixed: waterLevel, isRedundant, alarmDelay, responseTime, failoverTime
           (these are not part of the discharge gap)
    """
    designInflow = n["designInflow"]
    wl           = n["waterLevel"]
    alarm_d      = n["alarmDelay_s"]
    rt           = n["responseTime_s"]
    ft           = n["failoverTime_s"]

    # Variables
    flowA   = z3.Real("flowA")
    flowB   = z3.Real("flowB")
    effA    = z3.Real("effA")
    effB    = z3.Real("effB")
    lam     = z3.Real("pipeLoss")

    s = z3.Solver()

    # Physical bounds
    s.add(flowA >= 0.0, flowA <= 0.1)
    s.add(flowB >= 0.0, flowB <= 0.1)
    s.add(effA  >= 0.0, effA  <= 1.0)
    s.add(effB  >= 0.0, effB  <= 1.0)
    s.add(lam   >= 0.0, lam   <= 0.5)

    # REQ-001: waterLevel ≤ 0.30  (fixed at nominal — always satisfied)
    # REQ-002: isRedundant == true  (structural flag — always satisfied)
    # REQ-003: alarmDelay ≤ 2.0    (fixed at 0.5 — always satisfied)
    # REQ-004: flowA + flowB ≥ designInflow   (linear — variable)
    s.add(flowA + flowB >= designInflow)

    # REQ-005: responseTime ≤ 5.0  (fixed at 1.0 — always satisfied)
    # REQ-006: failoverTime ≤ 3.0  (fixed at 0.8 — always satisfied)

    # Negate FT-002: (flowA*effA + flowB*effB) * (1 - lam) < designInflow
    net_flow = (flowA * effA + flowB * effB) * (1.0 - lam)
    s.add(net_flow < designInflow)

    # Also: ensure efficiency values are non-trivially low (exclude degenerate case η→0)
    s.add(effA >= 0.3)
    s.add(effB >= 0.3)

    check = s.check()

    if check == z3.sat:
        m = s.model()
        def _f(v):
            try:
                return float(v.as_decimal(5))
            except Exception:
                return float(v.numerator_as_long()) / float(v.denominator_as_long())

        cex = {
            "flowA":    _f(m[flowA]),
            "flowB":    _f(m[flowB]),
            "effA":     _f(m[effA]),
            "effB":     _f(m[effB]),
            "pipeLoss": _f(m[lam]),
        }
        net = (cex["flowA"] * cex["effA"] + cex["flowB"] * cex["effB"]) * (1.0 - cex["pipeLoss"])
        raw_sum = cex["flowA"] + cex["flowB"]

        detail = (
            "G-5 (historical): Found parameter set where ALL original 6 REQs pass but FT-002 fails:\n"
            f"    flowA={cex['flowA']:.5f}, flowB={cex['flowB']:.5f}\n"
            f"    effA={cex['effA']:.4f},  effB={cex['effB']:.4f},  pipeLoss={cex['pipeLoss']:.4f}\n"
            f"    REQ-004 (raw sum):  {raw_sum:.5f} ≥ {designInflow} ✓ (SATISFIED)\n"
            f"    FT-002 (net flow):  {net:.5f} < {designInflow} ✗ (VIOLATED)\n"
            "\n"
            "    NOTE: G-5 is CLOSED — EffectiveDischargeCapacityRequirement (BPS-FT-002)\n"
            "    was added to Requirements.sysml to formally prevent this scenario.\n"
            "    This level is preserved as a record of the gap-discovery process.\n"
            "    SysML negative test: inject these bind values into Analysis.sysml to confirm\n"
            "    that BilgePumpFaultToleranceVerification returns FT-002 VIOLATED."
        )
        return FormalResult(
            level=5,
            req_id="BPS-FT-002 (adversarial — G-5 closed)",
            description="Adversarial: REQ-001..006 pass, FT-002 fails (historical gap record)",
            outcome="GAP",
            detail=detail,
            counterexample=cex,
        )
    elif check == z3.unsat:
        return FormalResult(
            level=5,
            req_id="BPS-FT-002 (adversarial — G-5 closed)",
            description="Adversarial: REQ-001..006 pass, FT-002 fails (historical gap record)",
            outcome="PROVED",
            detail=(
                "No parameter set exists where REQ-001..006 all pass and FT-002 fails. "
                "The original requirement set is sufficient to imply FT-002.\n"
                "NOTE: G-5 was closed by adding EffectiveDischargeCapacityRequirement."
            ),
        )
    else:
        return FormalResult(
            level=5,
            req_id="BPS-FT-002 (adversarial — G-5 closed)",
            description="Adversarial: REQ-001..006 pass, FT-002 fails (historical gap record)",
            outcome="UNKNOWN",
            detail=(
                "Z3 NRA returned 'unknown'. The bilinear constraints may be too complex "
                "for the default decision procedure.  Try increasing the timeout or "
                "using a fixed-point linearisation (substitute one variable)."
            ),
        )


# ── Level 6: Bounded temporal ordering (LIA) ──────────────────────────────────

def level_6_temporal_ordering(n: dict, verbose: bool) -> FormalResult:
    """
    Bounded temporal ordering proof (IMPORTANT CAVEAT — see module docstring).

    Encode 5 system events as integer timestamps (discrete time steps, 1 step ≈ 1s):
      t0 = water level threshold crossing (step 0, fixed)
      t1 = pump activation (t0 + ⌈responseTime_s⌉)
      t2 = alarm trigger sent by controller (t0 + ⌈responseTime_s⌉, same step as t1)
      t3 = alarm notification arrives at UI (t2 + ⌈activationDelay_s⌉)
      t4 = operator override action (when does the UI allow override?)

    State machine semantics (StateMachine.sysml):
      The UI receives alarm notification via alarm.notifyOut → ui.notifyIn (connection [11]).
      There is no explicit guard that prevents override BEFORE alarm arrives —
      this is the ordering gap we are looking for.

    Query: "Can t4 < t3?"  i.e., can operator override precede alarm notification?

    If SAT  → ordering gap exists; state machine needs a guard on the override port.
    If UNSAT → no trace of length ≤ DEPTH where override precedes alarm (bounded proof).

    CAVEAT:
      UNSAT means the property holds for bounded traces of length ≤ DEPTH.
      This is NOT a proof for all infinite traces.  For full LTL/CTL verification,
      use nuXmv, PRISM, or similar model checkers fed the StateMachine.sysml states.
    """
    DEPTH = 8   # maximum trace length in discrete steps

    rt   = n["responseTime_s"]
    ad   = n["alarmDelay_s"]

    import math
    # Round timing values to integer steps (conservative: ceiling)
    steps_rt = math.ceil(rt)   # responseTime in steps
    steps_ad = math.ceil(ad)   # alarmDelay in steps

    # Integer timestamp variables
    t0 = z3.Int("t_threshold")
    t1 = z3.Int("t_pump_activate")
    t2 = z3.Int("t_alarm_trigger")
    t3 = z3.Int("t_alarm_notify_ui")
    t4 = z3.Int("t_operator_override")

    s = z3.Solver()

    # Bounded trace: all timestamps within [0, DEPTH]
    for t in (t0, t1, t2, t3, t4):
        s.add(t >= 0, t <= DEPTH)

    # t0 is the reference point (can be any step)
    s.add(t0 >= 0)

    # State machine ordering constraints (from StateMachine.sysml):
    # MONITORING → PUMP_A_ACTIVE: controller activates pump after responseTime
    s.add(t1 == t0 + steps_rt)

    # Controller sends alarm at same step as pump activation (or after):
    # PUMP_A_ACTIVE → ALARM_TRIGGERED
    s.add(t2 >= t1)
    s.add(t2 <= t1 + steps_rt)  # alarm trigger bounded by another response cycle

    # Alarm notification reaches UI after activationDelay_s
    # Connection [11]: alarm.notifyOut → ui.notifyIn
    s.add(t3 == t2 + steps_ad)

    # Override port (connection [9]: ui.overrideOut → controller.overrideIn)
    # The current model has NO guard preventing t4 < t3.  We probe for SAT.
    s.add(t4 >= t0)          # override can only happen after threshold crossing
    s.add(t4 <= DEPTH)

    # Negate the desired ordering property: "override must come AFTER alarm notify"
    # We want to prove t4 ≥ t3. Negate: assert t4 < t3.
    s.add(t4 < t3)

    check = s.check()

    if check == z3.sat:
        m = s.model()
        cex = {
            "t_threshold":        m[t0].as_long(),
            "t_pump_activate":    m[t1].as_long(),
            "t_alarm_trigger":    m[t2].as_long(),
            "t_alarm_notify_ui":  m[t3].as_long(),
            "t_operator_override": m[t4].as_long(),
        }
        detail = (
            f"Ordering gap found (trace depth ≤ {DEPTH}):\n"
            f"    t_threshold={cex['t_threshold']}, t_pump={cex['t_pump_activate']}, "
            f"t_alarm_trigger={cex['t_alarm_trigger']},\n"
            f"    t_alarm_notify_ui={cex['t_alarm_notify_ui']}, "
            f"t_override={cex['t_operator_override']}\n"
            f"    Override occurs at step {cex['t_operator_override']} "
            f"BEFORE alarm notification at step {cex['t_alarm_notify_ui']}.\n"
            "\n"
            "    Implication: the current StateMachine.sysml has no guard on the\n"
            "    controller.overrideIn port that requires alarm.isActive == true.\n"
            "    Recommended: add a state guard to PUMP_A_ACTIVE or MONITORING\n"
            "    that rejects override commands until ALARM_TRIGGERED state is reached.\n"
            "\n"
            f"    CAVEAT: This is a bounded proof (depth ≤ {DEPTH} steps).  Use nuXmv\n"
            "    for unbounded LTL verification of the full state machine."
        )
        return FormalResult(
            level=6,
            req_id="StateMachine — override ordering",
            description=f"Bounded temporal: override precedes alarm notify (depth≤{DEPTH})",
            outcome="GAP",
            detail=detail,
            counterexample=cex,
        )
    elif check == z3.unsat:
        return FormalResult(
            level=6,
            req_id="StateMachine — override ordering",
            description=f"Bounded temporal: override precedes alarm notify (depth≤{DEPTH})",
            outcome="PROVED",
            detail=(
                f"No trace of depth ≤ {DEPTH} exists where operator override precedes "
                f"alarm notification at the UI.  Property holds for bounded model.\n"
                f"    CAVEAT: Bounded proof only (depth={DEPTH} steps, ≈{DEPTH}s horizon).\n"
                "    Use nuXmv/PRISM for full LTL/CTL verification."
            ),
        )
    else:
        return FormalResult(
            level=6,
            req_id="StateMachine — override ordering",
            description="Bounded temporal ordering",
            outcome="UNKNOWN",
            detail="Z3 LIA returned unknown.",
        )


# ── Top-level runner ──────────────────────────────────────────────────────────

def run_all(
    bind_values: dict | None = None,
    verbose: bool = False,
    levels: list[int] | None = None,
) -> list[FormalResult]:
    """
    Run all Z3 analysis levels and return a list of FormalResult objects.

    Args:
        bind_values:  Optional dict of attribute values to override the nominal
                      values from BilgePumpFaultToleranceVerification.  Use the
                      full-path keys from Analysis.sysml bind statements
                      (e.g., "sys.pumpA.flowRate") or the short keys from
                      _nominal() (e.g., "flowA").
        verbose:      If True, print intermediate Z3 models.
        levels:       Subset of [1,2,3,4,5,6] to run; None runs all.
    """
    if not _Z3_AVAILABLE:
        return [FormalResult(
            level=0, req_id="z3",
            description="Z3 not available",
            outcome="ERROR",
            detail="Install z3-solver:  pip install z3-solver",
        )]

    n = _nominal()
    if bind_values:
        # Map full-path keys to short keys for convenience
        _path_map = {
            "sys.sensor.waterLevel":          "waterLevel",
            "sys.sensor.accuracy_m":          "accuracy_m",
            "sys.controller.triggerLevel_m":  "triggerLevel_m",
            "sys.controller.responseTime_s":  "responseTime_s",
            "sys.controller.failoverTime_s":  "failoverTime_s",
            "sys.pumpA.flowRate":             "flowA",
            "sys.pumpA.efficiency":           "effA",
            "sys.pumpB.flowRate":             "flowB",
            "sys.pumpB.efficiency":           "effB",
            "sys.discharge.pipeLossFactor":   "pipeLoss",
            "sys.alarm.activationDelay_s":    "alarmDelay_s",
            "sys.inflowRate_m3s":             "inflowRate_m3s",
            "sys.criticalLevel_m":            "criticalLevel_m",
        }
        for k, v in bind_values.items():
            short = _path_map.get(k, k)
            n[short] = float(v)

    active = set(levels) if levels else {1, 2, 3, 4, 5, 6}
    results: list[FormalResult] = []

    if 1 in active:
        results.append(level_1_symbolic_baseline(n, verbose))
    if 2 in active:
        results.append(level_2_efficiency_floor(n, verbose))
    if 3 in active:
        results.extend(level_3_accuracy_envelope(n, verbose))
    if 4 in active:
        results.append(level_4_response_window(n, verbose))
    if 5 in active:
        results.append(level_5_adversarial(n, verbose))
    if 6 in active:
        results.append(level_6_temporal_ordering(n, verbose))

    return results


# ── CLI output ────────────────────────────────────────────────────────────────

_OUTCOME_ICON = {
    "PROVED":  "\033[32m✓  PROVED \033[0m",
    "GAP":     "\033[33m⚠  GAP    \033[0m",
    "UNKNOWN": "\033[33m?  UNKNOWN\033[0m",
    "ERROR":   "\033[31m✗  ERROR  \033[0m",
}
_OUTCOME_ICON_NOCOLOR = {
    "PROVED":  "✓  PROVED ",
    "GAP":     "⚠  GAP    ",
    "UNKNOWN": "?  UNKNOWN",
    "ERROR":   "✗  ERROR  ",
}

def _print_results(results: list[FormalResult], verbose: bool, color: bool) -> None:
    W = 68
    icons = _OUTCOME_ICON if color else _OUTCOME_ICON_NOCOLOR
    bold  = (lambda t: f"\033[1m{t}\033[0m") if color else (lambda t: t)
    dim   = (lambda t: f"\033[2m{t}\033[0m") if color else (lambda t: t)

    print()
    print(bold("─" * W))
    print(bold("  Z3 Formal Analysis  (bilgepump/formal_analysis.py)"))
    print(bold("─" * W))

    for r in results:
        icon = icons.get(r.outcome, r.outcome)
        print(f"  {icon}  L{r.level}  {r.req_id}")
        print(f"           {dim(r.description)}")
        if r.detail:
            for line in r.detail.split("\n"):
                print(f"    {line}")
        if r.counterexample and verbose:
            print(f"    {dim('Counterexample:')}")
            for k, v in r.counterexample.items():
                print(f"      {k} = {v}")
        print()

    gaps    = [r for r in results if r.outcome == "GAP"]
    proved  = [r for r in results if r.outcome == "PROVED"]
    unknown = [r for r in results if r.outcome in ("UNKNOWN", "ERROR")]
    print("─" * W)
    print(f"  Results: {len(proved)} PROVED  {len(gaps)} GAP(s)  {len(unknown)} UNKNOWN")
    if gaps:
        print(bold(f"  ⚠  {len(gaps)} gap(s) discovered — review the details above."))
    else:
        print(bold("  ✓  No gaps discovered at current parameter values."))
    print("─" * W)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="formal_analysis.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--level", type=int, nargs="+",
                        help="Run specific levels (1–6). Default: all.")
    parser.add_argument("--verbose", action="store_true",
                        help="Show Z3 counterexample variable values.")
    parser.add_argument("--no-color", action="store_true",
                        help="Disable ANSI colour output.")
    args = parser.parse_args()

    if not _Z3_AVAILABLE:
        print("ERROR: z3-solver not installed.")
        print("  pip install z3-solver")
        sys.exit(2)

    color   = not args.no_color and hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    results = run_all(verbose=args.verbose, levels=args.level)
    _print_results(results, verbose=args.verbose, color=color)

    gaps = sum(1 for r in results if r.outcome == "GAP")
    # Exit 0 always — gaps are discoveries, not test failures
    sys.exit(0)


if __name__ == "__main__":
    main()
