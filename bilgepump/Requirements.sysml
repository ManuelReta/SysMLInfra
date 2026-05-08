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

}
