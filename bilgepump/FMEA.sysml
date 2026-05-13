// =============================================================================
// BilgePump::FMEA
// Layer: Failure Mode and Effects Analysis
// Purpose: FMEA artifacts for the bilge pump system — failure mode attribute
//          definitions, reliability and risk constraint definitions (RPN, NPSH,
//          parallel failure rate), and negative-test analysis cases that inject
//          failure mode values to confirm requirement violations.
//
// This layer is parallel to (not downstream of) Safety.sysml.
// Both Safety.sysml and FMEA.sysml are imported by Analysis.sysml for the
// complete verification picture.
//
// Import chain:
//   BilgePump::RAAML       — FailureMode, FaultTree metadata stereotypes
//   BilgePump::Library     — part defs and attribute types
//   BilgePump::Architecture — BilgePumpSystem part usage instances
//   BilgePump::Requirements — existing 4 requirement defs for assert statements
//   BilgePump::Safety       — UCA requirement defs for assert statements
//
// SOURCE DOCUMENTS:
//   FMEA-BPS-001 — FMEA table (8 failure modes; S/O/D ratings)
//   FMEA-BPS-002 — Reliability and risk constraint equations
//   FMEA-BPS-003 — Negative test scenarios (one per critical failure mode)
//
// EXECUTION:
//   Each analysis def in this file is a negative test case.
//   Run via SysML v2 Pilot API (Safety.ipynb) AFTER the main
//   BilgePumpVerification positive test has passed.
//   Expected results are documented inline and in FMEA-BPS-003.
// =============================================================================

package 'BilgePump::FMEA' {

    import 'BilgePump::RAAML'::*;
    import 'BilgePump::Library'::*;
    import 'BilgePump::Architecture'::*;
    import 'BilgePump::Requirements'::*;
    import 'BilgePump::Safety'::*;

    // =========================================================================
    // Failure Mode Attribute Definition
    // Extends Library attribute types with FMEA rating fields.
    // Used as additional attributes on part def specialisations or as
    // standalone constraint parameters in the analysis cases below.
    // SOURCE: FMEA-BPS-001; MIL-STD-1629A; AIAG FMEA 4th Edition
    // =========================================================================
    attribute def FailureModeAttr {
        attribute severity   : Real;    // 1–10 AIAG severity scale
        attribute occurrence : Real;    // 1–10 occurrence likelihood
        attribute detection  : Real;    // 1–10 detection capability
        attribute rpn        : Real;    // Risk Priority Number = S × O × D
    }

    // =========================================================================
    // FMEA CONSTRAINT DEFINITIONS
    // Physics and reliability equations derived from FMEA-BPS-002.
    // Consumed by the analysis cases below.
    // =========================================================================

    // -------------------------------------------------------------------------
    // RiskPriorityNumber
    // Computes the FMEA Risk Priority Number.
    // SOURCE: FMEA-BPS-002 §2.1; MIL-STD-1629A; AIAG FMEA 4th Edition
    // NOTE: RPN alone is insufficient for safety-critical assessment.
    //       Use in conjunction with STPA hazard severity from Safety.sysml.
    // -------------------------------------------------------------------------
    #FaultTree {
        ftId      = "FT-RPN";
        topEvent  = "High Risk Priority Number (RPN ≥ 100)";
        gate      = "AND";
        cutSets   = "high_severity,high_occurrence";
        sourceDoc = "FMEA-BPS-002";
        section   = "2.1";
    }
    constraint def RiskPriorityNumber {
        attribute severity   : Real;    // Input: S rating (1–10)
        attribute occurrence : Real;    // Input: O rating (1–10)
        attribute detection  : Real;    // Input: D rating (1–10)
        attribute rpn        : Real;    // Output: computed RPN

        assert constraint {
            rpn == severity * occurrence * detection
        }
    }

    // -------------------------------------------------------------------------
    // ParallelRedundancyFailureRate
    // System failure rate for two pumps in active parallel redundancy.
    // Both must fail simultaneously for system loss — exponential model.
    // SOURCE: FMEA-BPS-002 §2.2; IEC 61508-6 Table B.5; MIL-HDBK-217F
    // NOTE: Valid for exponential lifetime distribution only.
    //       Use Weibull analysis for run hours > 8000 h (wear-out phase).
    //       Nominal lambda_A = lambda_B = 1.5e-5 failures/hour.
    // -------------------------------------------------------------------------
    constraint def ParallelRedundancyFailureRate {
        attribute lambda_A   : Real;    // Pump A failure rate (failures/hour)
        attribute lambda_B   : Real;    // Pump B failure rate (identical pump — equals lambda_A)
        attribute lambda_sys : Real;    // System failure rate with parallel redundancy

        assert constraint {
            lambda_sys == lambda_A * lambda_B
        }
    }

    // -------------------------------------------------------------------------
    // NPSHMarginCheck
    // Cavitation avoidance constraint: available NPSH must exceed required
    // NPSH by the Hydraulic Institute design margin (minimum 1.0 m).
    // SOURCE: FMEA-BPS-002 §2.3; Hydraulic Institute Standards; ISO 9906
    // FAILURE MODE LINK: FM-PA-002 (Pump A cavitation)
    // -------------------------------------------------------------------------
    constraint def NPSHMarginCheck {
        attribute npsh_available : Real;   // Input: NPSH available (m) from suction geometry
        attribute npsh_required  : Real;   // Input: NPSH required at rated flow from CFD curve
        attribute npsh_margin    : Real;   // Input: Design margin (Hydraulic Institute ≥ 1.0 m)

        assert constraint {
            npsh_available >= npsh_required + npsh_margin
        }
    }

    // =========================================================================
    // FMEA NEGATIVE TEST ANALYSIS CASES
    // Each analysis def injects a specific failure mode value and confirms that
    // the affected requirements are VIOLATED. This provides direct traceability
    // from FMEA failure modes to formal SysML v2 model verification.
    //
    // These tests are complementary to the positive tests in Analysis.sysml.
    // The Orchestrator runs them as Phase 3.5 verification BEFORE VerificationAgent.
    //
    // RPN action threshold: 100 (per FMEA-BPS-001 metadata).
    // All scenarios marked expected_violations must produce VIOLATED results.
    // =========================================================================

    // -------------------------------------------------------------------------
    // FMEA Negative Test 1: Sensor Stuck-At-Zero
    // Failure Mode: FM-S-001 (BilgeWaterSensor fail-silent)
    // RPN: 240 (S=10, O=3, D=8) — exceeds threshold
    // SOURCE: FMEA-BPS-003 §3.1
    // EXPECTED: UCA_002_SensorFailSilent VIOLATED
    //           DischargeCapacityRequirement VIOLATED
    //           AlarmResponseRequirement VIOLATED
    // -------------------------------------------------------------------------
    #FailureMode {
        fmId            = "FM-S-001";
        component       = "BilgeWaterSensor";
        instance        = "sensor";
        failureModeText = "Stuck-at-zero output (fail-silent)";
        failureEffect   = "Controller never activates pumps; bilge floods unchecked";
        severity        = 10;
        occurrence      = 3;
        detection       = 8;
        rpn             = 240;
        ucaRef          = "UCA-002";
        hazardRef       = "H-1";
        sourceDoc       = "FMEA-BPS-001";
        section         = "3.1";
    }
    analysis def FMEA_SensorStuckAtZero {
        subject sys : BilgePumpSystem {
            // Fault injection: sensor reports 0.0 m (stuck-at-zero)
            // Actual bilge level approximately 0.28 m and rising
            bind sys.sensor.waterLevel          = 0.0;     // FAULT: stuck-at-zero
            bind sys.controller.triggerLevel_m  = 0.25;    // Nominal trigger unchanged
            bind sys.controller.responseTime_s  = 1.0;     // Would respond if triggered
            bind sys.pumpA.flowRate             = 0.0;     // Not activated — no trigger
            bind sys.pumpB.flowRate             = 0.0;     // Not activated — no trigger
            bind sys.pumpA.efficiency           = 0.82;    // Nominal if activated
            bind sys.pumpB.efficiency           = 0.82;
            bind sys.discharge.pipeLossFactor   = 0.05;
            bind sys.alarm.activationDelay_s    = 999.0;   // FAULT: alarm never fires
            bind sys.alarm.isActive             = false;
            bind sys.pumpB.isRedundant          = true;
            bind sys.ui.overrideActive          = false;
        }

        // Physics check with zero-flow — expected VIOLATED
        constraint fmeaPhysicsCheck : RiskPriorityNumber {
            bind fmeaPhysicsCheck.severity   = 10.0;
            bind fmeaPhysicsCheck.occurrence = 3.0;
            bind fmeaPhysicsCheck.detection  = 8.0;
        }

        // Expected: VIOLATED (sensor reading = 0.0 but this req checks range 0.0–1.0;
        // the structural fail-silent violation is that the value never responds to real changes)
        assert requirement sensorRangeCheck : UCA_002_SensorFailSilent { subject sys; }

        // Expected: VIOLATED — combined flow = 0; design inflow = 0.030 m³/s
        assert requirement dischargeCheck : DischargeCapacityRequirement {
            subject sys;
            bind dischargeCheck.designInflow = 0.030;
        }

        // Expected: VIOLATED — alarm delay = 999 s >> 2.0 s limit
        assert requirement alarmCheck : AlarmResponseRequirement { subject sys; }
    }

    // -------------------------------------------------------------------------
    // FMEA Negative Test 2: Pump A Cavitation (Degraded Efficiency)
    // Failure Mode: FM-PA-002 (BilgePumpA reduced efficiency)
    // RPN: 210 (S=7, O=5, D=6) — exceeds threshold
    // SOURCE: FMEA-BPS-003 §3.2
    // EXPECTED: DischargeCapacityRequirement VIOLATED
    //           Q_net = (0.025+0.025) * 0.40 * (1-0.05) = 0.019 < 0.030
    // -------------------------------------------------------------------------
    #FailureMode {
        fmId            = "FM-PA-002";
        component       = "BilgePumpA";
        instance        = "pumpA";
        failureModeText = "Reduced efficiency due to cavitation at low NPSH";
        failureEffect   = "Net discharge flow drops below design inflow threshold";
        severity        = 7;
        occurrence      = 5;
        detection       = 6;
        rpn             = 210;
        ucaRef          = "";
        hazardRef       = "H-1";
        sourceDoc       = "FMEA-BPS-001";
        section         = "4.2";
    }
    analysis def FMEA_PumpACavitation {
        subject sys : BilgePumpSystem {
            bind sys.sensor.waterLevel          = 0.15;    // Normal sensor reading
            bind sys.controller.triggerLevel_m  = 0.25;
            bind sys.controller.responseTime_s  = 1.0;
            bind sys.pumpA.flowRate             = 0.025;   // Motor running — nominal flow
            bind sys.pumpA.efficiency           = 0.40;    // FAULT: cavitation-degraded efficiency
            bind sys.pumpA.runHours             = 120.0;
            bind sys.pumpB.flowRate             = 0.025;   // Nominal
            bind sys.pumpB.efficiency           = 0.82;    // Pump B unaffected
            bind sys.pumpB.runHours             = 85.0;
            bind sys.pumpB.isRedundant          = true;
            bind sys.discharge.pipeLossFactor   = 0.05;
            bind sys.alarm.activationDelay_s    = 0.5;
            bind sys.alarm.isActive             = false;
            bind sys.ui.overrideActive          = false;
        }

        // NPSH check — cavitation is occurring because NPSH margin insufficient
        constraint npshCheck : NPSHMarginCheck {
            bind npshCheck.npsh_available = 2.8;    // Reduced head due to flooding conditions
            bind npshCheck.npsh_required  = 2.5;
            bind npshCheck.npsh_margin    = 1.0;    // Hydraulic Institute minimum
            // npsh_available (2.8) < npsh_required + npsh_margin (3.5) → VIOLATED
        }

        // Expected: VIOLATED — Q_net = (0.025+0.025)*0.40*(1-0.05) = 0.019 < 0.030
        assert requirement dischargeCheck : DischargeCapacityRequirement {
            subject sys;
            bind dischargeCheck.designInflow = 0.030;
        }
    }

    // -------------------------------------------------------------------------
    // FMEA Negative Test 3: Emergency Power Bus Loss (Redundancy Violated)
    // Failure Mode: FM-PB-001 (BilgePumpB independent power feed lost)
    // RPN: 72 (S=9, O=2, D=4) — below threshold but Severity=9 flags review
    // SOURCE: FMEA-BPS-003 §3.3
    // EXPECTED: PumpRedundancyRequirement VIOLATED
    // -------------------------------------------------------------------------
    #FailureMode {
        fmId            = "FM-PB-001";
        component       = "BilgePumpB";
        instance        = "pumpB";
        failureModeText = "Redundant pump unavailable — independent power bus lost";
        failureEffect   = "PumpB.isRedundant effectively false; single point of failure";
        severity        = 9;
        occurrence      = 2;
        detection       = 4;
        rpn             = 72;
        ucaRef          = "";
        hazardRef       = "H-4";
        sourceDoc       = "FMEA-BPS-001";
        section         = "5.1";
    }
    analysis def FMEA_PowerBusLoss {
        subject sys : BilgePumpSystem {
            bind sys.sensor.waterLevel          = 0.15;
            bind sys.controller.triggerLevel_m  = 0.25;
            bind sys.controller.responseTime_s  = 1.0;
            bind sys.power.nominalVoltage        = 440.0;
            bind sys.power.redundancyActive      = false;  // FAULT: emergency bus down
            bind sys.pumpA.flowRate             = 0.025;   // Primary pump operating
            bind sys.pumpA.efficiency           = 0.82;
            bind sys.pumpA.runHours             = 120.0;
            bind sys.pumpB.flowRate             = 0.025;   // Running on main bus (not independent)
            bind sys.pumpB.efficiency           = 0.82;
            bind sys.pumpB.runHours             = 85.0;
            bind sys.pumpB.isRedundant          = false;   // FAULT: power feed not independent
            bind sys.discharge.pipeLossFactor   = 0.05;
            bind sys.alarm.activationDelay_s    = 0.5;
            bind sys.alarm.isActive             = false;
            bind sys.ui.overrideActive          = false;
        }

        // Expected: VIOLATED — pumpB.isRedundant = false
        assert requirement redundancyCheck : PumpRedundancyRequirement { subject sys; }

        // Also check UCA-004 — failover requirement is now structurally unmet
        assert requirement failoverCheck : UCA_004_ControllerNoFailover { subject sys; }
    }

    // -------------------------------------------------------------------------
    // FMEA Negative Test 4: Controller Software Hang
    // Failure Mode: FM-C-001 (PumpController hang — no outputs issued)
    // RPN: 140 (S=10, O=2, D=7) — exceeds threshold
    // SOURCE: FMEA-BPS-003 §3.4
    // EXPECTED: UCA_001_ControllerNoActivatePumpA VIOLATED
    //           DischargeCapacityRequirement VIOLATED
    //           AlarmResponseRequirement VIOLATED
    // -------------------------------------------------------------------------
    #FailureMode {
        fmId            = "FM-C-001";
        component       = "PumpController";
        instance        = "controller";
        failureModeText = "Controller software hang — no outputs issued";
        failureEffect   = "No pump commands; no alarm; all automation paths fail";
        severity        = 10;
        occurrence      = 2;
        detection       = 7;
        rpn             = 140;
        ucaRef          = "UCA-001";
        hazardRef       = "H-1";
        sourceDoc       = "FMEA-BPS-001";
        section         = "6.1";
    }
    analysis def FMEA_ControllerHang {
        subject sys : BilgePumpSystem {
            bind sys.sensor.waterLevel          = 0.28;    // Valid — rising flood
            bind sys.controller.triggerLevel_m  = 0.25;
            bind sys.controller.responseTime_s  = 9999.0;  // FAULT: controller hung
            bind sys.pumpA.flowRate             = 0.0;     // Not activated
            bind sys.pumpA.efficiency           = 0.82;
            bind sys.pumpA.runHours             = 120.0;
            bind sys.pumpB.flowRate             = 0.0;     // Not activated
            bind sys.pumpB.efficiency           = 0.82;
            bind sys.pumpB.runHours             = 85.0;
            bind sys.pumpB.isRedundant          = true;    // Structurally true but controller hung
            bind sys.discharge.pipeLossFactor   = 0.05;
            bind sys.alarm.activationDelay_s    = 9999.0;  // FAULT: alarm output frozen
            bind sys.alarm.isActive             = false;
            bind sys.ui.overrideActive          = false;
        }

        // Expected: VIOLATED — responseTime_s = 9999 > 5.0 s limit
        assert requirement controllerResponseCheck : UCA_001_ControllerNoActivatePumpA { subject sys; }

        // Expected: VIOLATED — combined flow = 0 < 0.030 m³/s design inflow
        assert requirement dischargeCheck : DischargeCapacityRequirement {
            subject sys;
            bind dischargeCheck.designInflow = 0.030;
        }

        // Expected: VIOLATED — alarm delay = 9999 s >> 2.0 s limit
        assert requirement alarmCheck : AlarmResponseRequirement { subject sys; }
    }

}
