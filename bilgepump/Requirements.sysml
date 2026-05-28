// =============================================================================
// BilgePump::Requirements
// Layer: Requirements
// Purpose: Formal requirement definitions that the bilge pump system must
//          satisfy. Each requirement def declares a subject (the system under
//          verification) and an assert constraint body containing the logic
//          that must evaluate to true.
//
// Import chain: Requirements imports Library and Architecture.
//
// Regulatory sources are cited in comments; these map to the external document
// inputs a real systems engineer would trace in a requirements management tool
// (e.g., IBM DOORS, Jama Connect, or Polarion).
//
// Traceability:
//   All four requirements are asserted in Analysis::BilgePumpVerification.
//   In a full MBSE toolchain (Cameo/Papyrus), each requirement def here would
//   be linked to a verification method element and a test case element,
//   forming the complete V-model traceability chain:
//     Stakeholder Need → System Requirement → Design → Verification
// =============================================================================

package 'BilgePump::Requirements' {

    import 'BilgePump::Library'::*;
    import 'BilgePump::Architecture'::*;

    // =========================================================================
    // Requirement 1: Water Level Threshold
    //
    // Regulatory basis:
    //   IMO MARPOL 73/78 Annex I, Regulation 22 — bilge water must be pumped
    //   overboard before accumulation reaches a level that threatens stability.
    //   Classification societies (DNV, Lloyd's) typically mandate automatic
    //   pump activation at ≤ 300 mm (0.3 m) above the bilge floor.
    //
    // Verification method: Analysis case evaluates sensor.waterLevel at
    //   steady-state nominal and at injected fault value.
    //
    // DOORS / Jama traceability ID: BPS-REQ-001
    // =========================================================================
    requirement def WaterLevelRequirement {
        subject sys : BilgePumpSystem;

        // The sensor's reported water level must never exceed 0.3 m when the
        // system is operating correctly (i.e., after controller has responded).
        doc /* The bilge water level shall not exceed 300 mm above the bilge
               floor during normal automated operation. */

        require constraint {
            sys.sensor.waterLevel <= 0.3
        }
    }

    // =========================================================================
    // Requirement 2: Pump Redundancy
    //
    // Regulatory basis:
    //   DNV Rules for Ships — Part 4 Chapter 6, Section 3:
    //   "The bilge system shall be arranged with at least two pumps, each
    //    capable of handling the required flow, with independent power supplies."
    //   SOLAS Chapter II-1, Regulation 35: similar mandate.
    //
    // Verification method: Confirm pumpB.isRedundant flag is true and that
    //   power.powerOutB is on an independent bus (modelled via isEmergency flag
    //   in Analysis negative test).
    //
    // DOORS / Jama traceability ID: BPS-REQ-002
    // =========================================================================
    requirement def PumpRedundancyRequirement {
        subject sys : BilgePumpSystem;

        doc /* The bilge pump system shall include a designated redundant pump
               (Pump B) with an independent power feed, capable of maintaining
               full discharge capacity in the event of Pump A failure. */

        require constraint {
            sys.pumpB.isRedundant == true
        }
    }

    // =========================================================================
    // Requirement 3: Alarm Response Time
    //
    // Regulatory basis:
    //   IEC 60945:2002 (Maritime navigation and radio communication equipment)
    //   Section 4.3 — Alarm systems: audible/visual alarm must activate within
    //   2 seconds of detecting an alarm condition.
    //   Also referenced in IMO MSC/Circ.982 (Guidelines for alarm management).
    //
    // Verification method: alarm.activationDelay_s is set to nominal value
    //   (0.5 s) in the positive test and mutated to 3.0 s in the negative test.
    //
    // DOORS / Jama traceability ID: BPS-REQ-003
    // =========================================================================
    requirement def AlarmResponseRequirement {
        subject sys : BilgePumpSystem;

        doc /* The alarm system shall activate audible and visual annunciation
               within 2.0 seconds of the controller issuing an alarm trigger,
               in compliance with IEC 60945 Section 4.3. */

        require constraint {
            sys.alarm.activationDelay_s <= 2.0
        }
    }

    // =========================================================================
    // Requirement 4: Discharge Capacity
    //
    // Regulatory basis:
    //   SOLAS Chapter II-1, Regulation 35: the bilge pumping system must be
    //   capable of evacuating bilge water at a rate that prevents flooding.
    //   The combined pump flow rate must exceed the maximum design inflow rate
    //   (typically calculated from the worst-case damage stability scenario).
    //
    // Modelling note:
    //   'designInflow' is the maximum water ingress rate from the damage
    //   stability calculation (naval architecture tool output — e.g., Maxsurf
    //   Stability or NAPA). In this model it is declared as an attribute on the
    //   system subject so the Analysis layer can bind it to the constraint.
    //
    // Verification method: PumpFlowPhysics constraint in Analysis layer
    //   evaluates (pumpA.flowRate + pumpB.flowRate) * efficiency * (1 - pipeLoss)
    //   against a bound designInflow value.
    //
    // DOORS / Jama traceability ID: BPS-REQ-004
    // =========================================================================
    requirement def DischargeCapacityRequirement {
        subject sys : BilgePumpSystem;

        // Design inflow rate from damage stability analysis (m³/s).
        // SOURCE: naval architecture tool (Maxsurf / NAPA stability module)
        attribute designInflow : Real;

        doc /* The combined discharge flow rate of Pump A and Pump B, after
               accounting for hydraulic efficiency and pipe losses, shall meet
               or exceed the design inflow rate derived from the damage stability
               analysis, as required by SOLAS II-1 Regulation 35. */

        require constraint {
            (sys.pumpA.flowRate + sys.pumpB.flowRate) >= designInflow
        }
    }
//
    // =========================================================================
    // Requirement 5: Controller Activation Timing
    //
    // Regulatory basis:
    //   Derived from STPA UCA-001 and UCA-005 safety constraints (SR-001/SR-005
    //   in Safety.sysml). Formalised here at the system-requirements layer
    //   with a directly measurable bound.
    //   Simulink discrete-event timing analysis (SIM-CTRL-001 §3.1) validates:
    //     Nominal:           responseTime_s = 1.0 s → PASS
    //     High CPU load:     responseTime_s = 2.8 s → PASS
    //     Watchdog recovery: responseTime_s = 4.9 s → PASS (marginal)
    //     Software hang:     responseTime_s = 9999.0 s → FAIL (FM-C-001)
    //
    // Verification method: BilgePumpTimingVerification analysis def.
    //   Nominal: responseTime_s = 1.0 → SATISFIED.
    //   Negative: responseTime_s = 9999.0 → VIOLATED (see FMEA_ControllerHang).
    //
    // State machine link: MONITORING → PUMP_A_ACTIVE transition guard.
    //   See PumpControllerBehavior in StateMachine.sysml.
    //
    // DOORS / Jama traceability ID: BPS-REQ-005
    // =========================================================================
    requirement def ControllerActivationTimingRequirement {
        subject sys : BilgePumpSystem;
//
        doc /* The PumpController shall issue a pump activation command within
               5.0 seconds of detecting a water level at or above triggerLevel_m.
               Derived from STPA SR-001/SR-005; validated by Simulink timing
               analysis SIM-CTRL-001 §3.1. */
//
        require constraint {
            sys.controller.responseTime_s <= 5.0
        }
    }
//
    // =========================================================================
    // Requirement 6: Failover Switch Timing
    //
    // Regulatory basis:
    //   Derived from STPA UCA-004 safety constraint (SR-004 in Safety.sysml).
    //   This requirement closes a gap in the original 4-requirement set:
    //   BPS-REQ-002 (PumpRedundancyRequirement) verifies structural redundancy
    //   (pumpB.isRedundant == true) but does NOT verify the TIMING of failover.
    //   SIM-CTRL-001 §3.2 provides the timing bound:
    //     Normal failover:   failoverTime_s = 0.8 s → PASS
    //     Delayed detection: failoverTime_s = 2.7 s → PASS
    //     No failover:       failoverTime_s = 9999.0 s → FAIL (FM-C-003)
    //
    // Verification method: BilgePumpTimingVerification analysis def.
    //   Nominal: failoverTime_s = 0.8 s → SATISFIED.
    //   Negative: failoverTime_s = 9999.0 s → VIOLATED (FMEA_FailoverNotTriggered).
    //
    // State machine link: PUMP_A_ACTIVE → FAILOVER transition guard.
    //   See PumpControllerBehavior in StateMachine.sysml.
    //
    // DOORS / Jama traceability ID: BPS-REQ-006
    // =========================================================================
    requirement def FailoverSwitchTimingRequirement {
        subject sys : BilgePumpSystem;
//
        doc /* The PumpController shall issue a Pump B activation command within
               3.0 seconds of detecting a Pump A fault condition.
               Derived from STPA SR-004 and Simulink failover timing analysis
               SIM-CTRL-001 §3.2. Closes the gap in BPS-REQ-002 which verifies
               structural redundancy but not failover timing. */
//
        require constraint {
            sys.controller.failoverTime_s <= 3.0
        }
    }
//
}
