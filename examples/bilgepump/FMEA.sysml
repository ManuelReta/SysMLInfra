// =============================================================================
// BilgePump::FMEA
// Layer: Failure Mode and Effects Analysis
// Purpose: FMEA artifacts for the bilge pump system -- failure-mode attribute
// and constraint definitions (RPN, parallel failure rate, NPSH,
// failover timing) plus NEGATIVE verification cases that inject
// failure-mode values and confirm the affected requirements VIOLATE.
//
// This layer is parallel to Safety.sysml; both are imported into the unified
// BilgePump project for the complete verification picture.
//
// KERNEL-EVALUABLE NEGATIVE TESTS
// -------------------------------
// The kernel cannot override an attribute value already bound by Architecture
// (e.g. pumpA.flowRate, alarm.activationDelay_s).  Each fault is therefore
// injected on a fresh component instance typed by its Library part def (whose
// attributes are unbound), and the affected requirement is re-expressed as a
// computed Boolean.  Every Boolean below is expected to evaluate to FALSE
// (i.e. VIOLATED), which the publish pipeline captures via %eval and records in
// the `sysml_assertions` table with result_bool = false.
//
// %eval BilgePump_FMEA::FM_S_001_alarm     -> LiteralBoolean false   (VIOLATED)
//
// SOURCE DOCUMENTS:
// FMEA-BPS-001 -- FMEA table (failure modes; S/O/D ratings)
// FMEA-BPS-002 -- Reliability and risk constraint equations
// FMEA-BPS-003 -- Negative test scenarios (one per critical failure mode)
// =============================================================================

package BilgePump_FMEA {
    private import ScalarValues::*;
    // RAAML stereotypes (Hazard/Loss/UCA/FailureMode/…) were folded into
    // Requirements.sysml; they arrive via the BilgePump_Requirements import below.
    public import BilgePump_Library::*;
    public import BilgePump_Architecture::*;
    public import BilgePump_Requirements::*;

    // =========================================================================
    // Failure Mode Attribute Definition
    // Extends Library attribute types with FMEA rating fields.
    // SOURCE: FMEA-BPS-001; MIL-STD-1629A; AIAG FMEA 4th Edition
    // NOTE: 'occurrence' is a reserved SysML v2 keyword -> 'occurrenceRating'.
    // =========================================================================
    attribute def FailureModeAttr {
        attribute severity : Real; // 1-10 AIAG severity scale
        attribute occurrenceRating : Real; // 1-10 occurrence likelihood
        attribute detection : Real; // 1-10 detection capability
        attribute rpn : Real; // Risk Priority Number = S x O x D
    }

    // =========================================================================
    // FMEA CONSTRAINT DEFINITIONS  (from FMEA-BPS-002)
    // =========================================================================

    // RiskPriorityNumber -- RPN = S x O x D.
    // SOURCE: FMEA-BPS-002 §2.1; MIL-STD-1629A; AIAG FMEA 4th Edition.
    // Fault-tree tag: FT-RPN, top event "High Risk Priority Number (RPN >= 100)".
    constraint def RiskPriorityNumber {
        attribute severity : Real; // Input: S rating (1-10)
        attribute occurrenceRating : Real; // Input: O rating (1-10)
        attribute detection : Real; // Input: D rating (1-10)
        attribute rpn : Real; // Output: computed RPN

        assert constraint {
            rpn == severity * occurrenceRating * detection
        }
    }

    // ParallelRedundancyFailureRate -- system failure rate for two pumps in
    // active parallel redundancy (both must fail; exponential model).
    // SOURCE: FMEA-BPS-002 §2.2; IEC 61508-6 Table B.5; MIL-HDBK-217F.
    constraint def ParallelRedundancyFailureRate {
        attribute lambda_A : Real; // Pump A failure rate (failures/hour)
        attribute lambda_B : Real; // Pump B failure rate (= lambda_A, identical pump)
        attribute lambda_sys : Real; // System failure rate with parallel redundancy

        assert constraint {
            lambda_sys == lambda_A * lambda_B
        }
    }

    // NPSHMarginCheck -- cavitation avoidance: available NPSH must exceed
    // required NPSH by the Hydraulic Institute design margin (>= 1.0 m).
    // SOURCE: FMEA-BPS-002 §2.3; Hydraulic Institute Standards; ISO 9906.
    // FAILURE MODE LINK: FM-PA-002 (Pump A cavitation).
    constraint def NPSHMarginCheck {
        attribute npsh_available : Real; // NPSH available (m) from suction geometry
        attribute npsh_required : Real; // NPSH required at rated flow (CFD curve)
        attribute npsh_margin : Real; // Design margin (Hydraulic Institute >= 1.0 m)

        assert constraint {
            npsh_available >= npsh_required + npsh_margin
        }
    }

    // FailoverSwitchTimeConstraint -- timing of controller failover A -> B.
    // SOURCE: SIM-CTRL-001 §3.2. FAILURE MODE LINK: FM-C-003.
    constraint def FailoverSwitchTimeConstraint {
        attribute failoverTime_s : Real; // Actual fault-to-Pump-B-command time (s)
        attribute maxFailoverTime_s : Real; // Maximum allowed failover time (s)

        assert constraint {
            failoverTime_s <= maxFailoverTime_s
        }
    }

    // =========================================================================
    // FMEA NEGATIVE TEST CASES (fault injection -> expected VIOLATED)
    //
    // Each fault is injected on Library-typed component instances; the affected
    // requirement is re-expressed as a computed Boolean expected to be FALSE.
    // RPN action threshold: 100 (FMEA-BPS-001).
    // =========================================================================

    // -------------------------------------------------------------------------
    // FM-S-001: BilgeWaterSensor stuck-at-zero (fail-silent).  RPN=240.
    // SOURCE: FMEA-BPS-003 §3.1.
    // Effect: controller never activates pumps; alarm never fires.
    // EXPECTED VIOLATED: AlarmResponseRequirement, DischargeCapacityRequirement.
    // -------------------------------------------------------------------------
    part fmS001_alarm : AlarmSystem {
        @FailureMode {
            fmId = "FM-S-001";
            component = "BilgeWaterSensor";
            instance = "sensor";
            failureModeText = "Stuck-at-zero output (fail-silent)";
            failureEffect = "Controller never activates pumps; bilge floods unchecked";
            severity = 10;
            occurrenceRating = 3;
            detection = 8;
            rpn = 240;
            ucaRef = "UCA-002";
            hazardRef = "H-1";
            sourceDoc = "FMEA-BPS-001";
            section = "3.1";
        }
        attribute :>> activationDelay_s = 999.0; // FAULT: alarm never annunciates
    }
    part fmS001_pumpA : BilgePumpA { attribute :>> flowRate = 0.0; } // not activated
    part fmS001_pumpB : BilgePumpB { attribute :>> flowRate = 0.0; } // not activated
    // VIOLATED: alarm delay 999 s > 2.0 s [BPS-REQ-003]
    attribute FM_S_001_alarm : Boolean = fmS001_alarm.activationDelay_s <= 2.0;
    // VIOLATED: combined flow 0 < 0.030 m^3/s [BPS-REQ-004]
    attribute FM_S_001_discharge : Boolean = fmS001_pumpA.flowRate + fmS001_pumpB.flowRate >= 0.030;

    // -------------------------------------------------------------------------
    // FM-PA-002: BilgePumpA cavitation (degraded efficiency 0.40).  RPN=210.
    // SOURCE: FMEA-BPS-003 §3.2.
    // EXPECTED VIOLATED: EffectiveDischargeCapacityRequirement (per-pump eta).
    // netFlow = (0.025*0.40 + 0.025*0.82) * (1-0.05) = 0.028975 < 0.030.
    // Note: the raw-sum DischargeCapacityRequirement would NOT catch this; the
    // effective (efficiency-aware) check FT-002 is the discriminating test.
    // -------------------------------------------------------------------------
    part fmPA002_pumpA : BilgePumpA {
        @FailureMode {
            fmId = "FM-PA-002";
            component = "BilgePumpA";
            instance = "pumpA";
            failureModeText = "Reduced efficiency due to cavitation at low NPSH";
            failureEffect = "Net discharge flow drops below design inflow threshold";
            severity = 7;
            occurrenceRating = 5;
            detection = 6;
            rpn = 210;
            ucaRef = "";
            hazardRef = "H-1";
            sourceDoc = "FMEA-BPS-001";
            section = "4.2";
        }
        attribute :>> flowRate = 0.025;
        attribute :>> efficiency = 0.40; // FAULT: cavitation-degraded efficiency
    }
    part fmPA002_pumpB : BilgePumpB {
        attribute :>> flowRate = 0.025;
        attribute :>> efficiency = 0.82; // Pump B unaffected
    }
    part fmPA002_disch : DischargeLine { attribute :>> pipeLossFactor = 0.05; }
    attribute FM_PA_002_netFlow : Real =
        (fmPA002_pumpA.flowRate * fmPA002_pumpA.efficiency +
            fmPA002_pumpB.flowRate * fmPA002_pumpB.efficiency) *
        (1.0 - fmPA002_disch.pipeLossFactor);
    // VIOLATED: netFlow 0.028975 < 0.030 [BPS-FT-002]
    attribute FM_PA_002_effDischarge : Boolean = FM_PA_002_netFlow >= 0.030;

    // -------------------------------------------------------------------------
    // FM-PB-001: BilgePumpB redundant feed lost (isRedundant -> false).  RPN=72
    // (Severity=9 flags mandatory review).  SOURCE: FMEA-BPS-003 §3.3.
    // EXPECTED VIOLATED: PumpRedundancyRequirement.
    // -------------------------------------------------------------------------
    part fmPB001_pumpB : BilgePumpB {
        @FailureMode {
            fmId = "FM-PB-001";
            component = "BilgePumpB";
            instance = "pumpB";
            failureModeText = "Redundant pump unavailable -- independent power bus lost";
            failureEffect = "PumpB.isRedundant effectively false; single point of failure";
            severity = 9;
            occurrenceRating = 2;
            detection = 4;
            rpn = 72;
            ucaRef = "";
            hazardRef = "H-4";
            sourceDoc = "FMEA-BPS-001";
            section = "5.1";
        }
        attribute :>> isRedundant = false; // FAULT: power feed not independent
    }
    // VIOLATED: isRedundant == true is false [BPS-REQ-002]
    attribute FM_PB_001_redundancy : Boolean = fmPB001_pumpB.isRedundant == true;

    // -------------------------------------------------------------------------
    // FM-C-001: PumpController software hang (no outputs).  RPN=140.
    // SOURCE: FMEA-BPS-003 §3.4.  State: FAULT.
    // EXPECTED VIOLATED: ControllerActivationTimingRequirement,
    // DischargeCapacityRequirement, AlarmResponseRequirement.
    // -------------------------------------------------------------------------
    part fmC001_controller : PumpController {
        @FailureMode {
            fmId = "FM-C-001";
            component = "PumpController";
            instance = "controller";
            failureModeText = "Controller software hang -- no outputs issued";
            failureEffect = "No pump commands; no alarm; all automation paths fail";
            severity = 10;
            occurrenceRating = 2;
            detection = 7;
            rpn = 140;
            ucaRef = "UCA-001";
            hazardRef = "H-1";
            stateRef = "FAULT";
            sourceDoc = "FMEA-BPS-001";
            section = "6.1";
        }
        attribute :>> responseTime_s = 9999.0; // FAULT: controller hung
    }
    part fmC001_alarm : AlarmSystem { attribute :>> activationDelay_s = 9999.0; } // output frozen
    part fmC001_pumpA : BilgePumpA { attribute :>> flowRate = 0.0; }
    part fmC001_pumpB : BilgePumpB { attribute :>> flowRate = 0.0; }
    // VIOLATED: responseTime 9999 > 5.0 s [BPS-REQ-005]
    attribute FM_C_001_activation : Boolean = fmC001_controller.responseTime_s <= 5.0;
    // VIOLATED: alarm delay 9999 > 2.0 s [BPS-REQ-003]
    attribute FM_C_001_alarm : Boolean = fmC001_alarm.activationDelay_s <= 2.0;
    // VIOLATED: combined flow 0 < 0.030 m^3/s [BPS-REQ-004]
    attribute FM_C_001_discharge : Boolean = fmC001_pumpA.flowRate + fmC001_pumpB.flowRate >= 0.030;

    // -------------------------------------------------------------------------
    // FM-C-003: PumpController failover not triggered (failoverTime 9999).
    // RPN=90 (Severity=9 flags mandatory review).  State: FAILOVER.
    // SOURCE: FMEA-BPS-001 §6.3; SIM-CTRL-001 §3.2 (no-failover scenario).
    // GAP CLOSED: BPS-REQ-002 verified structural redundancy but not failover
    // TIMING; this closes it via BPS-REQ-006.
    // EXPECTED VIOLATED: FailoverSwitchTimingRequirement, DischargeCapacityRequirement.
    // -------------------------------------------------------------------------
    part fmC003_controller : PumpController {
        @FailureMode {
            fmId = "FM-C-003";
            component = "PumpController";
            instance = "controller";
            failureModeText = "Failover path not triggered -- Pump B command never issued";
            failureEffect = "Pump A fault uncompensated; combined discharge drops to zero";
            severity = 9;
            occurrenceRating = 2;
            detection = 5;
            rpn = 90;
            ucaRef = "UCA-004";
            hazardRef = "H-4";
            stateRef = "FAILOVER";
            sourceDoc = "FMEA-BPS-001";
            section = "6.3";
        }
        attribute :>> failoverTime_s = 9999.0; // FAULT: failover command never issued
    }
    part fmC003_pumpA : BilgePumpA { attribute :>> flowRate = 0.0; } // Pump A failed
    part fmC003_pumpB : BilgePumpB { attribute :>> flowRate = 0.0; } // failover not triggered
    // VIOLATED: failoverTime 9999 > 3.0 s [BPS-REQ-006]
    attribute FM_C_003_failover : Boolean = fmC003_controller.failoverTime_s <= 3.0;
    // VIOLATED: combined flow 0 < 0.030 m^3/s [BPS-REQ-004]
    attribute FM_C_003_discharge : Boolean = fmC003_pumpA.flowRate + fmC003_pumpB.flowRate >= 0.030;
} // package BilgePump_FMEA
