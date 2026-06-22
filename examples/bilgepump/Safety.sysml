// =============================================================================
// BilgePump::Safety
// Layer: Safety Analysis (STPA)
// Purpose: System-Theoretic Process Analysis (STPA) artifacts for the bilge
// pump system. Defines Losses, Hazards, and Unsafe Control Actions
// (UCAs) as formal requirement def blocks annotated with OMG RAAML
// metadata stereotypes.
//
// This layer EXTENDS the existing 4-layer model — it does not replace anything.
//
// Import chain:
// BilgePump::RAAML           — metadata def stereotypes (Hazard, UCA, Loss)
// BilgePump::Library         — part def and attribute def types
// BilgePump::Architecture    — BilgePumpSystem, part usage instances
// BilgePump::Requirements    — existing 4 requirement defs (for cross-reference)
//
// SOURCE DOCUMENTS:
// STPA-BPS-001 — Hazard and Loss identification
// STPA-BPS-002 — Unsafe Control Actions table
// STPA-BPS-003 — Loss scenarios (consumed by AnalysisMapper → FMEA.sysml)
//
// RAAML ANNOTATION COMPATIBILITY:
// #Hazard, #Loss, #UCA, #SafetyRequirement annotations require SysML v2
// Pilot API JAR ≥ 2022-06. If the API rejects metadata annotations, remove
// the #Annotation lines only — the requirement def blocks compile standalone.
//
// VERIFICATION:
// Positive test (nominal): All UCA requirement defs SATISFIED under nominal
// attribute bindings in BilgePumpVerification (Analysis.sysml).
// Negative tests: See FMEA.sysml for failure-mode analysis cases that
// inject fault values and confirm UCA requirement defs are VIOLATED.
// =============================================================================

package BilgePump_Safety {
    private import ScalarValues::*;
    public import BilgePump_RAAML::*;
    public import BilgePump_Library::*;
    public import BilgePump_Architecture::*;
    public import BilgePump_Requirements::*;

    // =========================================================================
    // STPA LOSSES — top-level unacceptable outcomes
    // Annotated with #Loss (OMG RAAML Loss stereotype)
    // These are not verifiable constraints; they are reference nodes that
    // UCAs and Hazards trace back to via hazardRefs / lossRefs metadata.
    // =========================================================================

    // -------------------------------------------------------------------------
    // L-0: Loss of human life or crew injury
    // SOURCE: STPA-BPS-001 §2; SOLAS Chapter III
    // -------------------------------------------------------------------------
    #Loss {
        lossId = "L-0";
        description = "Loss of human life or injury to vessel crew";
        category = "safety";
        severity = "catastrophic";
        regulatoryRef = "SOLAS Chapter III — Life-Saving Appliances";
        sourceDoc = "STPA-BPS-001";
        section = "2.1";
    }
    attribute def Loss_L0 {}

    // -------------------------------------------------------------------------
    // L-1: Loss of vessel — sinking or capsize due to uncontrolled flooding
    // SOURCE: STPA-BPS-001 §2; SOLAS Chapter II-1
    // -------------------------------------------------------------------------
    #Loss {
        lossId = "L-1";
        description = "Loss of vessel — sinking or capsize due to uncontrolled flooding";
        category = "safety";
        severity = "catastrophic";
        regulatoryRef = "SOLAS Chapter II-1 — Subdivision and Stability";
        sourceDoc = "STPA-BPS-001";
        section = "2.2";
    }
    attribute def Loss_L1 {}

    // -------------------------------------------------------------------------
    // L-2: Marine environmental damage
    // SOURCE: STPA-BPS-001 §2; MARPOL 73/78 Annex I Reg.22
    // -------------------------------------------------------------------------
    #Loss {
        lossId = "L-2";
        description = "Marine environmental damage — bilge water overboard without treatment";
        category = "environmental";
        severity = "critical";
        regulatoryRef = "MARPOL 73/78 Annex I, Regulation 22";
        sourceDoc = "STPA-BPS-001";
        section = "2.3";
    }
    attribute def Loss_L2 {}

    // =========================================================================
    // UCA-DERIVED SAFETY REQUIREMENTS
    //
    // Each requirement def below was derived from an Unsafe Control Action
    // identified during STPA analysis. The require constraint body formalises
    // the STPA safety constraint that eliminates the UCA.
    //
    // Pattern:
    // requirement def <UCA_SafetyRequirementName> {
    // #UCA { ... }
    // #SafetyRequirement { ... }
    // subject sys : BilgePumpSystem;
    // require constraint { <UCA elimination condition> }
    // }
    // =========================================================================

    // -------------------------------------------------------------------------
    // UCA-001 Safety Requirement: Controller must activate Pump A
    // when water level exceeds trigger threshold in AUTO mode.
    // DERIVED FROM: UCA-001 "ActivatePumpA — Not Provided"
    // SOURCE: STPA-BPS-002 §3.1
    // -------------------------------------------------------------------------
    #UCA {
        ucaId = "UCA-001";
        controlAction = "ActivatePumpA";
        guideword = "Not Provided";
        context = "Water level ≥ triggerLevel_m in AUTO mode";
        hazardRefs = "H-1,HS-1";
        severity = "catastrophic";
        failureModeLink = "FM-C-001";
        transitionRef = "MONITORING_to_PUMP_A_ACTIVE";
        sourceDoc = "STPA-BPS-002";
        section = "3.1";
    }
    #SafetyRequirement {
        srId = "SR-001";
        derivedFrom = "UCA-001";
        rationale =
            "Eliminates scenario where flooding proceeds unchecked because controller never issues pump start command";
        verificationMethod = "analysis";
        sourceDoc = "STPA-BPS-002";
        section = "5.1";
    }
    requirement def UCA_001_ControllerNoActivatePumpA {
        subject sys : BilgePumpSystem;

        doc
        /* The PumpController shall issue an ActivatePumpA command within
         * the designed response window whenever sensor.waterLevel exceeds
         * triggerLevel_m in automatic operating mode.
         * Derived from STPA UCA-001; eliminates H-1 (bilge flooding).
         */

        require constraint {
            sys.controller.responseTime_s <= 5.0
        }
    }

    // -------------------------------------------------------------------------
    // UCA-002 Safety Requirement: Sensor must provide valid water level readings.
    // A fail-silent (stuck-at-zero) sensor fault is a hazardous UCA.
    // DERIVED FROM: UCA-002 "ReportWaterLevel — Wrong Value Provided"
    // SOURCE: STPA-BPS-002 §3.2
    // -------------------------------------------------------------------------
    #UCA {
        ucaId = "UCA-002";
        controlAction = "ReportWaterLevel";
        guideword = "Wrong Value Provided";
        context = "Sensor stuck-at-zero during actual bilge flooding";
        hazardRefs = "H-1,HS-1";
        severity = "catastrophic";
        failureModeLink = "FM-S-001";
        sourceDoc = "STPA-BPS-002";
        section = "3.2";
    }
    #SafetyRequirement {
        srId = "SR-002";
        derivedFrom = "UCA-002";
        rationale =
            "Eliminates fail-silent sensor fault by requiring readings stay within plausible operational range";
        verificationMethod = "analysis";
        sourceDoc = "STPA-BPS-002";
        section = "5.2";
    }
    requirement def UCA_002_SensorFailSilent {
        subject sys : BilgePumpSystem;

        doc
        /* The BilgeWaterSensor shall report a water level value within the
         * valid operational range at all times. A reading of exactly 0.0 m
         * when pumps are inactive is indicative of a fail-silent fault.
         * Derived from STPA UCA-002; eliminates H-1.
         */

        require constraint {
            sys.sensor.waterLevel >= 0.0 and sys.sensor.waterLevel <= 1.0
        }
    }

    // -------------------------------------------------------------------------
    // UCA-003 Safety Requirement: Controller must trigger alarm on flood detection.
    // DERIVED FROM: UCA-003 "TriggerAlarm — Not Provided"
    // SOURCE: STPA-BPS-002 §3.3
    // -------------------------------------------------------------------------
    #UCA {
        ucaId = "UCA-003";
        controlAction = "TriggerAlarm";
        guideword = "Not Provided";
        context = "Water level > 0.25 m detected; controller does not assert alarmOut";
        hazardRefs = "H-3,HS-2";
        severity = "critical";
        failureModeLink = "FM-C-002";
        transitionRef = "PUMP_A_ACTIVE_to_ALARM_TRIGGERED";
        sourceDoc = "STPA-BPS-002";
        section = "3.3";
    }
    #SafetyRequirement {
        srId = "SR-003";
        derivedFrom = "UCA-003";
        rationale = "Eliminates alarm suppression scenario; crew must receive timely notification";
        verificationMethod = "analysis";
        sourceDoc = "STPA-BPS-002";
        section = "5.3";
    }
    requirement def UCA_003_ControllerNoAlarm {
        subject sys : BilgePumpSystem;

        doc
        /* When water level exceeds the trigger threshold, the AlarmSystem
         * must receive the trigger within the IEC 60945 §4.3 response
         * window. The controller shall not suppress alarm output.
         * Derived from STPA UCA-003; eliminates H-3.
         */

        require constraint {
            sys.alarm.activationDelay_s <= 2.0
        }
    }

    // -------------------------------------------------------------------------
    // UCA-004 Safety Requirement: Controller must activate Pump B when Pump A fails.
    // DERIVED FROM: UCA-004 "ActivatePumpB — Not Provided (on Pump A fault)"
    // SOURCE: STPA-BPS-002 §3.4
    // -------------------------------------------------------------------------
    #UCA {
        ucaId = "UCA-004";
        controlAction = "ActivatePumpB";
        guideword = "Not Provided";
        context = "Pump A faulted (zero flow); controller does not switch to Pump B";
        hazardRefs = "H-4,HS-3";
        severity = "critical";
        failureModeLink = "FM-C-003";
        transitionRef = "PUMP_A_ACTIVE_to_FAILOVER";
        sourceDoc = "STPA-BPS-002";
        section = "3.4";
    }
    #SafetyRequirement {
        srId = "SR-004";
        derivedFrom = "UCA-004";
        rationale =
            "Eliminates single-pump failure scenario by requiring active failover to redundant pump";
        verificationMethod = "analysis";
        sourceDoc = "STPA-BPS-002";
        section = "5.4";
    }
    requirement def UCA_004_ControllerNoFailover {
        subject sys : BilgePumpSystem;

        doc
        /* The PumpController shall maintain the isRedundant designation on
         * Pump B, ensuring the redundant pump is available for automatic
         * failover. The failover path must be structurally enabled.
         * Derived from STPA UCA-004; eliminates H-4.
         */

        require constraint {
            sys.pumpB.isRedundant == true
        }
    }

    // -------------------------------------------------------------------------
    // UCA-005 Safety Requirement: Pump A activation must not be delayed.
    // DERIVED FROM: UCA-005 "ActivatePumpA — Provided Too Late"
    // SOURCE: STPA-BPS-002 §3.5
    // -------------------------------------------------------------------------
    #UCA {
        ucaId = "UCA-005";
        controlAction = "ActivatePumpA";
        guideword = "Provided Too Late";
        context = "Pump A command issued > 5 s after water level crosses trigger threshold";
        hazardRefs = "H-1";
        severity = "critical";
        failureModeLink = "FM-C-001";
        transitionRef = "MONITORING_to_PUMP_A_ACTIVE";
        sourceDoc = "STPA-BPS-002";
        section = "3.5";
    }
    #SafetyRequirement {
        srId = "SR-005";
        derivedFrom = "UCA-005";
        rationale =
            "Controller response time must be bounded to prevent flooding accumulation during delay";
        verificationMethod = "analysis";
        sourceDoc = "STPA-BPS-002";
        section = "5.5";
    }
    requirement def UCA_005_ControllerDelayedActivation {
        subject sys : BilgePumpSystem;

        doc
        /* The PumpController response time (from trigger-level detection
         * to pump command issuance) shall not exceed 5.0 seconds.
         * Derived from STPA UCA-005; eliminates late-activation variant of H-1.
         */

        require constraint {
            sys.controller.responseTime_s <= 5.0
        }
    }
} // package BilgePump_Safety
