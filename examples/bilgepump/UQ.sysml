// =============================================================================
// BilgePump::UQ
// Layer: Uncertainty Quantification (Optional)
// Purpose: N=10 deterministic parametric-sweep verdicts that characterise the
// robustness of the discharge-capacity property under uncertainty in
// three physical parameters (pump flow rate, hydraulic efficiency,
// pipe loss factor).
//
// METHODOLOGY
// -----------
// Symmetric sigma-step sweep: each uncertain parameter is varied to +/-1 sigma
// and +/-3 sigma while the others are held at their mean; two combined
// worst-case points probe interaction effects.  All 10 points are
// deterministic (no random sampling) -- this is NOT a Monte Carlo / LHS study.
//
// Because the kernel cannot override Architecture's bound attribute values, and
// a UQ sweep IS by definition an experiment over explicit numeric points, each
// sweep point is encoded as a computed net-flow attribute plus a verdict
// Boolean:
//
// netFlow = (flowRate_A + flowRate_B) * efficiency * (1 - pipeLoss)
// verdict = netFlow >= designInflow (0.030 m^3/s)
//
// The publish pipeline emits one %eval per verdict and records it in the
// `sysml_assertions` table.  9 of 10 verdicts are SATISFIED (true); the
// combined 3-sigma extreme UQ_Sweep_10 is the single VIOLATED (false) point.
//
// SOURCE DOCUMENT: UQ-BPS-001.
// UNCERTAIN PARAMETERS:
// flowRate_A ~ N(0.025, 0.002) m^3/s  [OpenFOAM CFD pump curve, CFD-PUMP-001 §5.1]
// efficiency ~ N(0.82,  0.03)         [vendor test certificate, CFD-PUMP-001 §5.2]
// pipeLoss   ~ N(0.05,  0.008)        [Darcy-Weisbach roughness, CALC-HYD-001 §4.1]
// (flowRate_B is held at its mean 0.025 m^3/s -- Pump B == Pump A design.)
// =============================================================================

package BilgePump_UQ {
    private import ScalarValues::*;
    public import BilgePump_Library::*;
    public import BilgePump_Architecture::*;
    public import BilgePump_Requirements::*;
    public import BilgePump_Analysis::*;

    // =========================================================================
    // Uncertainty Bounds Attribute Definition (documentation)
    // SOURCE: UQ-BPS-001 §uncertain_parameters.
    // =========================================================================
    attribute def UncertaintyBounds {
        attribute mean : Real; // Distribution mean (nominal design value)
        attribute sigma : Real; // Standard deviation (1 sigma)
        attribute lower3sigma : Real; // Lower 3 sigma bound (mean - 3 sigma)
        attribute upper3sigma : Real; // Upper 3 sigma bound (mean + 3 sigma)
        attribute unit : String; // SI unit string
        attribute sourceTool : String; // Tool that produced the distribution estimate
    }

    // Design inflow threshold from damage stability analysis (m^3/s).
    attribute uqDesignInflow : Real = 0.030;

    // =========================================================================
    // UQ SWEEP POINTS -- N=10 deterministic verdicts
    // netFlow = (flowRate_A + 0.025) * efficiency * (1 - pipeLoss)
    // verdict = netFlow >= 0.030
    // =========================================================================

    // UQ_Sweep_01: pumpA flowRate -1 sigma (0.023). netFlow=0.0374 -> SATISFIED.
    attribute UQ_Sweep_01_netFlow : Real = (0.023 + 0.025) * 0.82 * (1.0 - 0.05);
    attribute UQ_Sweep_01 : Boolean = UQ_Sweep_01_netFlow >= uqDesignInflow;

    // UQ_Sweep_02: pumpA flowRate +1 sigma (0.027). netFlow=0.0405 -> SATISFIED.
    attribute UQ_Sweep_02_netFlow : Real = (0.027 + 0.025) * 0.82 * (1.0 - 0.05);
    attribute UQ_Sweep_02 : Boolean = UQ_Sweep_02_netFlow >= uqDesignInflow;

    // UQ_Sweep_03: pumpA flowRate -3 sigma (0.019). netFlow=0.0343 -> SATISFIED.
    attribute UQ_Sweep_03_netFlow : Real = (0.019 + 0.025) * 0.82 * (1.0 - 0.05);
    attribute UQ_Sweep_03 : Boolean = UQ_Sweep_03_netFlow >= uqDesignInflow;

    // UQ_Sweep_04: efficiency -1 sigma (0.79). netFlow=0.0375 -> SATISFIED.
    attribute UQ_Sweep_04_netFlow : Real = (0.025 + 0.025) * 0.79 * (1.0 - 0.05);
    attribute UQ_Sweep_04 : Boolean = UQ_Sweep_04_netFlow >= uqDesignInflow;

    // UQ_Sweep_05: efficiency +1 sigma (0.85). netFlow=0.0404 -> SATISFIED.
    attribute UQ_Sweep_05_netFlow : Real = (0.025 + 0.025) * 0.85 * (1.0 - 0.05);
    attribute UQ_Sweep_05 : Boolean = UQ_Sweep_05_netFlow >= uqDesignInflow;

    // UQ_Sweep_06: efficiency -3 sigma (0.73). netFlow=0.0347 -> SATISFIED.
    attribute UQ_Sweep_06_netFlow : Real = (0.025 + 0.025) * 0.73 * (1.0 - 0.05);
    attribute UQ_Sweep_06 : Boolean = UQ_Sweep_06_netFlow >= uqDesignInflow;

    // UQ_Sweep_07: pipe loss +1 sigma (0.058). netFlow=0.0386 -> SATISFIED.
    attribute UQ_Sweep_07_netFlow : Real = (0.025 + 0.025) * 0.82 * (1.0 - 0.058);
    attribute UQ_Sweep_07 : Boolean = UQ_Sweep_07_netFlow >= uqDesignInflow;

    // UQ_Sweep_08: pipe loss +3 sigma (0.074). netFlow=0.0380 -> SATISFIED.
    attribute UQ_Sweep_08_netFlow : Real = (0.025 + 0.025) * 0.82 * (1.0 - 0.074);
    attribute UQ_Sweep_08 : Boolean = UQ_Sweep_08_netFlow >= uqDesignInflow;

    // UQ_Sweep_09: combined low (flowRate -3 sigma AND efficiency -3 sigma).
    // netFlow=0.0305 -> SATISFIED (marginal, 1.7% margin -- earliest warning).
    attribute UQ_Sweep_09_netFlow : Real = (0.019 + 0.025) * 0.73 * (1.0 - 0.05);
    attribute UQ_Sweep_09 : Boolean = UQ_Sweep_09_netFlow >= uqDesignInflow;

    // UQ_Sweep_10: combined EXTREME (flowRate -3 sigma AND efficiency -3 sigma
    // AND pipe loss +3 sigma).  netFlow=0.02974 < 0.030 -> VIOLATED.
    // The ONLY violated point: combined 3-sigma worst-case exceeds the design
    // margin by ~6.7%.  Action: add 10% flow reserve, or verify the simultaneous
    // 3-sigma extreme on all three parameters is not credible.
    attribute UQ_Sweep_10_netFlow : Real = (0.019 + 0.025) * 0.73 * (1.0 - 0.074);
    attribute UQ_Sweep_10 : Boolean = UQ_Sweep_10_netFlow >= uqDesignInflow;
} // package BilgePump_UQ
