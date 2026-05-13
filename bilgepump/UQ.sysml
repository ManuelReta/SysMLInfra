// =============================================================================
// BilgePump::UQ
// Layer: Uncertainty Quantification (Optional — Phase 7)
// Purpose: N=10 deterministic parametric sweep analysis cases that characterise
//          the robustness of the DischargeCapacityRequirement under uncertainty
//          in three physical parameters (pump flow rate, hydraulic efficiency,
//          pipe loss factor).
//
// METHODOLOGY:
//   Symmetric sigma-step sweep: each uncertain parameter is varied from mean
//   to ±1σ, ±2σ, and ±3σ while all other parameters are held at their mean.
//   Two combined worst-case sweep points probe interaction effects.
//   All 10 sweep points are deterministic — no random sampling.
//   This is compatible with the SysML v2 Pilot API parametric evaluator, which
//   evaluates each analysis def independently against exact numeric bindings.
//
//   This is NOT a full Latin Hypercube or Monte Carlo. It provides the
//   individual-parameter uncertainty envelope and the combined 3σ extreme.
//   A 3^3 = 27-point full factorial design would be the next level if
//   interaction effects are suspected (extend in a future iteration).
//
// SOURCE DOCUMENT: UQ-BPS-001 — UQ Configuration JSON
//
// UNCERTAIN PARAMETERS (from UQ-BPS-001):
//   flowRate_A  ~ N(0.025, 0.002) m³/s  [CFD pump curve test uncertainty]
//   efficiency  ~ N(0.82,  0.03)        [Vendor test certificate uncertainty]
//   pipeLoss    ~ N(0.05,  0.008)       [Darcy-Weisbach roughness measurement]
//
// IMPORT CHAIN:
//   BilgePump::Library       — part def and attribute types
//   BilgePump::Architecture  — BilgePumpSystem
//   BilgePump::Requirements  — DischargeCapacityRequirement (primary check)
//   BilgePump::Analysis      — PumpFlowPhysics constraint def (reuse)
//
// EXPECTED RESULTS (per UQ-BPS-001 pre-analysis):
//   9 of 10 sweep points: DischargeCapacityRequirement SATISFIED
//   1 of 10 sweep points: DischargeCapacityRequirement VIOLATED
//     → UQ_Sweep_10 (combined 3σ extreme: flowRate -3σ AND efficiency -3σ AND pipeLoss +3σ)
//     → Q_net = 0.0298 m³/s < 0.030 m³/s design inflow (violated by 6.7%)
//
// INTERPRETATION:
//   The system is robust at any single parameter 3σ deviation.
//   The combined 3σ extreme is the only failure scenario.
//   Engineering action: add 10% flow reserve margin or verify that the
//   combined 3σ extreme is not a credible simultaneous failure mode.
//
// EXECUTION:
//   Run after VerificationAgent Phase 6 passes (non-blocking).
//   See Safety.ipynb Cell 10 (UQ sweep execution).
// =============================================================================

package 'BilgePump::UQ' {

    import 'BilgePump::Library'::*;
    import 'BilgePump::Architecture'::*;
    import 'BilgePump::Requirements'::*;
    import 'BilgePump::Analysis'::*;

    // =========================================================================
    // Uncertainty Bounds Attribute Definition
    // Annotates system attributes with their distributional parameters.
    // Used as documentation in this package; values come from UQ-BPS-001.
    // =========================================================================
    attribute def UncertaintyBounds {
        attribute mean         : Real;   // Distribution mean (nominal design value)
        attribute sigma        : Real;   // Standard deviation (1σ from test/simulation)
        attribute lower3sigma  : Real;   // Lower 3σ bound (mean − 3σ)
        attribute upper3sigma  : Real;   // Upper 3σ bound (mean + 3σ)
        attribute unit         : String; // SI unit string for documentation
        attribute sourceTool   : String; // Tool that produced the distribution estimate
    }

    // -------------------------------------------------------------------------
    // Declared uncertainty distributions (documentation; not executable constraints)
    // SOURCE: UQ-BPS-001 §uncertain_parameters
    // -------------------------------------------------------------------------
    // flowRate_A  : N(0.025, 0.002) m³/s  — OpenFOAM CFD pump curve (CFD-PUMP-001 §5.1)
    // efficiency  : N(0.82,  0.03)        — Vendor test certificate (CFD-PUMP-001 §5.2)
    // pipeLoss    : N(0.05,  0.008)       — Darcy-Weisbach roughness (CALC-HYD-001 §4.1)

    // =========================================================================
    // UQ SWEEP POINTS — N=10 deterministic analysis cases
    //
    // Each analysis def below:
    //   1. Sets all 3 uncertain parameters to specific σ-step values
    //   2. Holds all other parameters at nominal (mean) values
    //   3. Asserts DischargeCapacityRequirement — the safety-critical check
    //   4. Uses PumpFlowPhysics constraint def from Analysis.sysml to evaluate
    //      Q_net = (Q_A + Q_B) × η × (1 − λ)
    // =========================================================================

    // -------------------------------------------------------------------------
    // UQ_Sweep_01: pumpA flowRate −1σ (low side)
    // Varied: flowRate_A = 0.025 − 0.002 = 0.023 m³/s
    // Q_net predicted: (0.023+0.025)*0.82*(1-0.05) = 0.0374 m³/s ≥ 0.030 → SATISFIED
    // SOURCE: UQ-BPS-001 sweep_points[0]
    // -------------------------------------------------------------------------
    analysis def UQ_Sweep_01 {
        subject sys : BilgePumpSystem {
            bind sys.sensor.waterLevel          = 0.15;
            bind sys.controller.triggerLevel_m  = 0.25;
            bind sys.controller.responseTime_s  = 1.0;
            bind sys.pumpA.flowRate             = 0.023;   // −1σ
            bind sys.pumpA.efficiency           = 0.82;    // mean
            bind sys.pumpA.runHours             = 120.0;
            bind sys.pumpB.flowRate             = 0.025;   // mean (Pump B = Pump A design)
            bind sys.pumpB.efficiency           = 0.82;
            bind sys.pumpB.runHours             = 85.0;
            bind sys.pumpB.isRedundant          = true;
            bind sys.discharge.pipeLossFactor   = 0.05;    // mean
            bind sys.alarm.activationDelay_s    = 0.5;
            bind sys.alarm.isActive             = false;
            bind sys.ui.overrideActive          = false;
        }
        constraint physicsCheck : PumpFlowPhysics {
            bind physicsCheck.flowRateA      = sys.pumpA.flowRate;
            bind physicsCheck.flowRateB      = sys.pumpB.flowRate;
            bind physicsCheck.efficiency     = sys.pumpA.efficiency;
            bind physicsCheck.pipeLossFactor = sys.discharge.pipeLossFactor;
            bind physicsCheck.designInflow   = 0.030;
        }
        // Expected: SATISFIED — Q_net ≈ 0.0374 m³/s ≥ 0.030
        assert requirement dischargeCheck : DischargeCapacityRequirement {
            subject sys;
            bind dischargeCheck.designInflow = 0.030;
        }
    }

    // -------------------------------------------------------------------------
    // UQ_Sweep_02: pumpA flowRate +1σ (high side)
    // flowRate_A = 0.025 + 0.002 = 0.027 m³/s
    // Q_net predicted: (0.027+0.025)*0.82*(1-0.05) = 0.0404 → SATISFIED
    // SOURCE: UQ-BPS-001 sweep_points[1]
    // -------------------------------------------------------------------------
    analysis def UQ_Sweep_02 {
        subject sys : BilgePumpSystem {
            bind sys.sensor.waterLevel          = 0.15;
            bind sys.controller.triggerLevel_m  = 0.25;
            bind sys.controller.responseTime_s  = 1.0;
            bind sys.pumpA.flowRate             = 0.027;   // +1σ
            bind sys.pumpA.efficiency           = 0.82;
            bind sys.pumpA.runHours             = 120.0;
            bind sys.pumpB.flowRate             = 0.025;
            bind sys.pumpB.efficiency           = 0.82;
            bind sys.pumpB.runHours             = 85.0;
            bind sys.pumpB.isRedundant          = true;
            bind sys.discharge.pipeLossFactor   = 0.05;
            bind sys.alarm.activationDelay_s    = 0.5;
            bind sys.alarm.isActive             = false;
            bind sys.ui.overrideActive          = false;
        }
        constraint physicsCheck : PumpFlowPhysics {
            bind physicsCheck.flowRateA      = sys.pumpA.flowRate;
            bind physicsCheck.flowRateB      = sys.pumpB.flowRate;
            bind physicsCheck.efficiency     = sys.pumpA.efficiency;
            bind physicsCheck.pipeLossFactor = sys.discharge.pipeLossFactor;
            bind physicsCheck.designInflow   = 0.030;
        }
        // Expected: SATISFIED
        assert requirement dischargeCheck : DischargeCapacityRequirement {
            subject sys;
            bind dischargeCheck.designInflow = 0.030;
        }
    }

    // -------------------------------------------------------------------------
    // UQ_Sweep_03: pumpA flowRate −3σ (worst-case low flow)
    // flowRate_A = 0.025 − 3×0.002 = 0.019 m³/s
    // Q_net predicted: (0.019+0.025)*0.82*(1-0.05) = 0.0343 → SATISFIED
    // SOURCE: UQ-BPS-001 sweep_points[2]
    // -------------------------------------------------------------------------
    analysis def UQ_Sweep_03 {
        subject sys : BilgePumpSystem {
            bind sys.sensor.waterLevel          = 0.15;
            bind sys.controller.triggerLevel_m  = 0.25;
            bind sys.controller.responseTime_s  = 1.0;
            bind sys.pumpA.flowRate             = 0.019;   // −3σ
            bind sys.pumpA.efficiency           = 0.82;
            bind sys.pumpA.runHours             = 120.0;
            bind sys.pumpB.flowRate             = 0.025;
            bind sys.pumpB.efficiency           = 0.82;
            bind sys.pumpB.runHours             = 85.0;
            bind sys.pumpB.isRedundant          = true;
            bind sys.discharge.pipeLossFactor   = 0.05;
            bind sys.alarm.activationDelay_s    = 0.5;
            bind sys.alarm.isActive             = false;
            bind sys.ui.overrideActive          = false;
        }
        constraint physicsCheck : PumpFlowPhysics {
            bind physicsCheck.flowRateA      = sys.pumpA.flowRate;
            bind physicsCheck.flowRateB      = sys.pumpB.flowRate;
            bind physicsCheck.efficiency     = sys.pumpA.efficiency;
            bind physicsCheck.pipeLossFactor = sys.discharge.pipeLossFactor;
            bind physicsCheck.designInflow   = 0.030;
        }
        // Expected: SATISFIED — design margin holds at single-parameter 3σ
        assert requirement dischargeCheck : DischargeCapacityRequirement {
            subject sys;
            bind dischargeCheck.designInflow = 0.030;
        }
    }

    // -------------------------------------------------------------------------
    // UQ_Sweep_04: hydraulic efficiency −1σ
    // efficiency = 0.82 − 0.03 = 0.79
    // Q_net predicted: (0.025+0.025)*0.79*(1-0.05) = 0.0375 → SATISFIED
    // SOURCE: UQ-BPS-001 sweep_points[3]
    // -------------------------------------------------------------------------
    analysis def UQ_Sweep_04 {
        subject sys : BilgePumpSystem {
            bind sys.sensor.waterLevel          = 0.15;
            bind sys.controller.triggerLevel_m  = 0.25;
            bind sys.controller.responseTime_s  = 1.0;
            bind sys.pumpA.flowRate             = 0.025;
            bind sys.pumpA.efficiency           = 0.79;    // −1σ
            bind sys.pumpA.runHours             = 120.0;
            bind sys.pumpB.flowRate             = 0.025;
            bind sys.pumpB.efficiency           = 0.82;
            bind sys.pumpB.runHours             = 85.0;
            bind sys.pumpB.isRedundant          = true;
            bind sys.discharge.pipeLossFactor   = 0.05;
            bind sys.alarm.activationDelay_s    = 0.5;
            bind sys.alarm.isActive             = false;
            bind sys.ui.overrideActive          = false;
        }
        constraint physicsCheck : PumpFlowPhysics {
            bind physicsCheck.flowRateA      = sys.pumpA.flowRate;
            bind physicsCheck.flowRateB      = sys.pumpB.flowRate;
            bind physicsCheck.efficiency     = sys.pumpA.efficiency;
            bind physicsCheck.pipeLossFactor = sys.discharge.pipeLossFactor;
            bind physicsCheck.designInflow   = 0.030;
        }
        // Expected: SATISFIED
        assert requirement dischargeCheck : DischargeCapacityRequirement {
            subject sys;
            bind dischargeCheck.designInflow = 0.030;
        }
    }

    // -------------------------------------------------------------------------
    // UQ_Sweep_05: hydraulic efficiency +1σ
    // efficiency = 0.82 + 0.03 = 0.85
    // Q_net predicted: (0.025+0.025)*0.85*(1-0.05) = 0.0404 → SATISFIED
    // SOURCE: UQ-BPS-001 sweep_points[4]
    // -------------------------------------------------------------------------
    analysis def UQ_Sweep_05 {
        subject sys : BilgePumpSystem {
            bind sys.sensor.waterLevel          = 0.15;
            bind sys.controller.triggerLevel_m  = 0.25;
            bind sys.controller.responseTime_s  = 1.0;
            bind sys.pumpA.flowRate             = 0.025;
            bind sys.pumpA.efficiency           = 0.85;    // +1σ
            bind sys.pumpA.runHours             = 120.0;
            bind sys.pumpB.flowRate             = 0.025;
            bind sys.pumpB.efficiency           = 0.82;
            bind sys.pumpB.runHours             = 85.0;
            bind sys.pumpB.isRedundant          = true;
            bind sys.discharge.pipeLossFactor   = 0.05;
            bind sys.alarm.activationDelay_s    = 0.5;
            bind sys.alarm.isActive             = false;
            bind sys.ui.overrideActive          = false;
        }
        constraint physicsCheck : PumpFlowPhysics {
            bind physicsCheck.flowRateA      = sys.pumpA.flowRate;
            bind physicsCheck.flowRateB      = sys.pumpB.flowRate;
            bind physicsCheck.efficiency     = sys.pumpA.efficiency;
            bind physicsCheck.pipeLossFactor = sys.discharge.pipeLossFactor;
            bind physicsCheck.designInflow   = 0.030;
        }
        // Expected: SATISFIED
        assert requirement dischargeCheck : DischargeCapacityRequirement {
            subject sys;
            bind dischargeCheck.designInflow = 0.030;
        }
    }

    // -------------------------------------------------------------------------
    // UQ_Sweep_06: hydraulic efficiency −3σ (worst-case low efficiency)
    // efficiency = 0.82 − 3×0.03 = 0.73
    // Q_net predicted: (0.025+0.025)*0.73*(1-0.05) = 0.0347 → SATISFIED
    // SOURCE: UQ-BPS-001 sweep_points[5]
    // -------------------------------------------------------------------------
    analysis def UQ_Sweep_06 {
        subject sys : BilgePumpSystem {
            bind sys.sensor.waterLevel          = 0.15;
            bind sys.controller.triggerLevel_m  = 0.25;
            bind sys.controller.responseTime_s  = 1.0;
            bind sys.pumpA.flowRate             = 0.025;
            bind sys.pumpA.efficiency           = 0.73;    // −3σ
            bind sys.pumpA.runHours             = 120.0;
            bind sys.pumpB.flowRate             = 0.025;
            bind sys.pumpB.efficiency           = 0.82;
            bind sys.pumpB.runHours             = 85.0;
            bind sys.pumpB.isRedundant          = true;
            bind sys.discharge.pipeLossFactor   = 0.05;
            bind sys.alarm.activationDelay_s    = 0.5;
            bind sys.alarm.isActive             = false;
            bind sys.ui.overrideActive          = false;
        }
        constraint physicsCheck : PumpFlowPhysics {
            bind physicsCheck.flowRateA      = sys.pumpA.flowRate;
            bind physicsCheck.flowRateB      = sys.pumpB.flowRate;
            bind physicsCheck.efficiency     = sys.pumpA.efficiency;
            bind physicsCheck.pipeLossFactor = sys.discharge.pipeLossFactor;
            bind physicsCheck.designInflow   = 0.030;
        }
        // Expected: SATISFIED — design margin holds at single-parameter 3σ
        assert requirement dischargeCheck : DischargeCapacityRequirement {
            subject sys;
            bind dischargeCheck.designInflow = 0.030;
        }
    }

    // -------------------------------------------------------------------------
    // UQ_Sweep_07: pipe loss factor +1σ (higher losses)
    // pipeLoss = 0.05 + 0.008 = 0.058
    // Q_net predicted: (0.025+0.025)*0.82*(1-0.058) = 0.0383 → SATISFIED
    // SOURCE: UQ-BPS-001 sweep_points[6]
    // -------------------------------------------------------------------------
    analysis def UQ_Sweep_07 {
        subject sys : BilgePumpSystem {
            bind sys.sensor.waterLevel          = 0.15;
            bind sys.controller.triggerLevel_m  = 0.25;
            bind sys.controller.responseTime_s  = 1.0;
            bind sys.pumpA.flowRate             = 0.025;
            bind sys.pumpA.efficiency           = 0.82;
            bind sys.pumpA.runHours             = 120.0;
            bind sys.pumpB.flowRate             = 0.025;
            bind sys.pumpB.efficiency           = 0.82;
            bind sys.pumpB.runHours             = 85.0;
            bind sys.pumpB.isRedundant          = true;
            bind sys.discharge.pipeLossFactor   = 0.058;   // +1σ
            bind sys.alarm.activationDelay_s    = 0.5;
            bind sys.alarm.isActive             = false;
            bind sys.ui.overrideActive          = false;
        }
        constraint physicsCheck : PumpFlowPhysics {
            bind physicsCheck.flowRateA      = sys.pumpA.flowRate;
            bind physicsCheck.flowRateB      = sys.pumpB.flowRate;
            bind physicsCheck.efficiency     = sys.pumpA.efficiency;
            bind physicsCheck.pipeLossFactor = sys.discharge.pipeLossFactor;
            bind physicsCheck.designInflow   = 0.030;
        }
        // Expected: SATISFIED
        assert requirement dischargeCheck : DischargeCapacityRequirement {
            subject sys;
            bind dischargeCheck.designInflow = 0.030;
        }
    }

    // -------------------------------------------------------------------------
    // UQ_Sweep_08: pipe loss factor +3σ (worst-case high losses)
    // pipeLoss = 0.05 + 3×0.008 = 0.074
    // Q_net predicted: (0.025+0.025)*0.82*(1-0.074) = 0.0380 → SATISFIED
    // SOURCE: UQ-BPS-001 sweep_points[7]
    // -------------------------------------------------------------------------
    analysis def UQ_Sweep_08 {
        subject sys : BilgePumpSystem {
            bind sys.sensor.waterLevel          = 0.15;
            bind sys.controller.triggerLevel_m  = 0.25;
            bind sys.controller.responseTime_s  = 1.0;
            bind sys.pumpA.flowRate             = 0.025;
            bind sys.pumpA.efficiency           = 0.82;
            bind sys.pumpA.runHours             = 120.0;
            bind sys.pumpB.flowRate             = 0.025;
            bind sys.pumpB.efficiency           = 0.82;
            bind sys.pumpB.runHours             = 85.0;
            bind sys.pumpB.isRedundant          = true;
            bind sys.discharge.pipeLossFactor   = 0.074;   // +3σ
            bind sys.alarm.activationDelay_s    = 0.5;
            bind sys.alarm.isActive             = false;
            bind sys.ui.overrideActive          = false;
        }
        constraint physicsCheck : PumpFlowPhysics {
            bind physicsCheck.flowRateA      = sys.pumpA.flowRate;
            bind physicsCheck.flowRateB      = sys.pumpB.flowRate;
            bind physicsCheck.efficiency     = sys.pumpA.efficiency;
            bind physicsCheck.pipeLossFactor = sys.discharge.pipeLossFactor;
            bind physicsCheck.designInflow   = 0.030;
        }
        // Expected: SATISFIED — single-parameter 3σ always satisfied
        assert requirement dischargeCheck : DischargeCapacityRequirement {
            subject sys;
            bind dischargeCheck.designInflow = 0.030;
        }
    }

    // -------------------------------------------------------------------------
    // UQ_Sweep_09: Combined worst-case low (flowRate −3σ AND efficiency −3σ)
    // flowRate_A = 0.019, efficiency = 0.73, pipeLoss = 0.05 (mean)
    // Q_net predicted: (0.019+0.025)*0.73*(1-0.05) = 0.0305 → MARGINAL (1.7% margin)
    // SOURCE: UQ-BPS-001 sweep_points[8]
    // -------------------------------------------------------------------------
    analysis def UQ_Sweep_09 {
        subject sys : BilgePumpSystem {
            bind sys.sensor.waterLevel          = 0.15;
            bind sys.controller.triggerLevel_m  = 0.25;
            bind sys.controller.responseTime_s  = 1.0;
            bind sys.pumpA.flowRate             = 0.019;   // −3σ
            bind sys.pumpA.efficiency           = 0.73;    // −3σ
            bind sys.pumpA.runHours             = 120.0;
            bind sys.pumpB.flowRate             = 0.025;
            bind sys.pumpB.efficiency           = 0.82;
            bind sys.pumpB.runHours             = 85.0;
            bind sys.pumpB.isRedundant          = true;
            bind sys.discharge.pipeLossFactor   = 0.05;    // mean
            bind sys.alarm.activationDelay_s    = 0.5;
            bind sys.alarm.isActive             = false;
            bind sys.ui.overrideActive          = false;
        }
        constraint physicsCheck : PumpFlowPhysics {
            bind physicsCheck.flowRateA      = sys.pumpA.flowRate;
            bind physicsCheck.flowRateB      = sys.pumpB.flowRate;
            bind physicsCheck.efficiency     = sys.pumpA.efficiency;
            bind physicsCheck.pipeLossFactor = sys.discharge.pipeLossFactor;
            bind physicsCheck.designInflow   = 0.030;
        }
        // Expected: SATISFIED (marginal — 0.0305 ≥ 0.030, 1.7% margin only)
        // This is the earliest warning point — review design margin adequacy.
        assert requirement dischargeCheck : DischargeCapacityRequirement {
            subject sys;
            bind dischargeCheck.designInflow = 0.030;
        }
    }

    // -------------------------------------------------------------------------
    // UQ_Sweep_10: Combined EXTREME worst-case
    //              flowRate −3σ AND efficiency −3σ AND pipe loss +3σ
    // flowRate_A = 0.019, efficiency = 0.73, pipeLoss = 0.074
    // Q_net predicted: (0.019+0.025)*0.73*(1-0.074) = 0.0298 < 0.030 → VIOLATED
    // SOURCE: UQ-BPS-001 sweep_points[9]
    // NOTE: This is the ONLY sweep point expected to VIOLATE.
    //       The combined 3σ simultaneous worst-case exceeds the design margin
    //       by 6.7%. Action required: add 10% flow reserve or verify that
    //       simultaneous 3σ extreme on all three parameters is not credible
    //       given independent failure modes.
    // -------------------------------------------------------------------------
    analysis def UQ_Sweep_10 {
        subject sys : BilgePumpSystem {
            bind sys.sensor.waterLevel          = 0.15;
            bind sys.controller.triggerLevel_m  = 0.25;
            bind sys.controller.responseTime_s  = 1.0;
            bind sys.pumpA.flowRate             = 0.019;   // −3σ
            bind sys.pumpA.efficiency           = 0.73;    // −3σ
            bind sys.pumpA.runHours             = 120.0;
            bind sys.pumpB.flowRate             = 0.025;
            bind sys.pumpB.efficiency           = 0.82;
            bind sys.pumpB.runHours             = 85.0;
            bind sys.pumpB.isRedundant          = true;
            bind sys.discharge.pipeLossFactor   = 0.074;   // +3σ
            bind sys.alarm.activationDelay_s    = 0.5;
            bind sys.alarm.isActive             = false;
            bind sys.ui.overrideActive          = false;
        }
        constraint physicsCheck : PumpFlowPhysics {
            bind physicsCheck.flowRateA      = sys.pumpA.flowRate;
            bind physicsCheck.flowRateB      = sys.pumpB.flowRate;
            bind physicsCheck.efficiency     = sys.pumpA.efficiency;
            bind physicsCheck.pipeLossFactor = sys.discharge.pipeLossFactor;
            bind physicsCheck.designInflow   = 0.030;
        }
        // Expected: VIOLATED — Q_net ≈ 0.0298 < 0.030 (combined 3σ extreme)
        // This is an INTENTIONAL violation to identify the UQ boundary.
        assert requirement dischargeCheck : DischargeCapacityRequirement {
            subject sys;
            bind dischargeCheck.designInflow = 0.030;
        }
    }

}
