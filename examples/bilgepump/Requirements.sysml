// =============================================================================
// BilgePump::Requirements
// Layer: Requirements
// Purpose: Formal requirement definitions that the bilge pump system must
// satisfy. Each requirement def declares a subject (the system under
// verification) and an assert constraint body containing the logic
// that must evaluate to true.
//
// Import chain: Requirements imports Library and Architecture.
//
// Regulatory sources are cited in comments; these map to the external document
// inputs a real systems engineer would trace in a requirements management tool
// (e.g., IBM DOORS, Jama Connect, or Polarion).
//
// Traceability:
// All four requirements are asserted in Analysis::BilgePumpVerification.
// In a full MBSE toolchain (Cameo/Papyrus), each requirement def here would
// be linked to a verification method element and a test case element,
// forming the complete V-model traceability chain:
// Stakeholder Need → System Requirement → Design → Verification
// =============================================================================

package BilgePump_Requirements {
    private import ScalarValues::*;
    public import BilgePump_Library::*;
    public import BilgePump_Architecture::*;

    // =========================================================================
    // Requirement 1: Water Level Threshold
    //
    // Regulatory basis:
    // IMO MARPOL 73/78 Annex I, Regulation 22 — bilge water must be pumped
    // overboard before accumulation reaches a level that threatens stability.
    // Classification societies (DNV, Lloyd's) typically mandate automatic
    // pump activation at ≤ 300 mm (0.3 m) above the bilge floor.
    //
    // Verification method: Analysis case evaluates sensor.waterLevel at
    // steady-state nominal and at injected fault value.
    //
    // DOORS / Jama traceability ID: BPS-REQ-001
    // =========================================================================
    requirement def WaterLevelRequirement {
        subject sys : BilgePumpSystem;

        // The sensor's reported water level must never exceed 0.3 m when the
        // system is operating correctly (i.e., after controller has responded).
        doc
        /* The bilge water level shall not exceed 300 mm above the bilge
         * floor during normal automated operation.
         */

        require constraint {
            sys.sensor.waterLevel <= 0.3
        }
    }

    // =========================================================================
    // Requirement 2: Pump Redundancy
    //
    // Regulatory basis:
    // DNV Rules for Ships — Part 4 Chapter 6, Section 3:
    // "The bilge system shall be arranged with at least two pumps, each
    // capable of handling the required flow, with independent power supplies."
    // SOLAS Chapter II-1, Regulation 35: similar mandate.
    //
    // Verification method: Confirm pumpB.isRedundant flag is true and that
    // power.powerOutB is on an independent bus (modelled via isEmergency flag
    // in Analysis negative test).
    //
    // DOORS / Jama traceability ID: BPS-REQ-002
    // =========================================================================
    requirement def PumpRedundancyRequirement {
        subject sys : BilgePumpSystem;

        doc
        /* The bilge pump system shall include a designated redundant pump
         * (Pump B) with an independent power feed, capable of maintaining
         * full discharge capacity in the event of Pump A failure.
         */

        require constraint {
            sys.pumpB.isRedundant == true
        }
    }

    // =========================================================================
    // Requirement 3: Alarm Response Time
    //
    // Regulatory basis:
    // IEC 60945:2002 (Maritime navigation and radio communication equipment)
    // Section 4.3 — Alarm systems: audible/visual alarm must activate within
    // 2 seconds of detecting an alarm condition.
    // Also referenced in IMO MSC/Circ.982 (Guidelines for alarm management).
    //
    // Verification method: alarm.activationDelay_s is set to nominal value
    // (0.5 s) in the positive test and mutated to 3.0 s in the negative test.
    //
    // DOORS / Jama traceability ID: BPS-REQ-003
    // =========================================================================
    requirement def AlarmResponseRequirement {
        subject sys : BilgePumpSystem;

        doc
        /* The alarm system shall activate audible and visual annunciation
         * within 2.0 seconds of the controller issuing an alarm trigger,
         * in compliance with IEC 60945 Section 4.3.
         */

        require constraint {
            sys.alarm.activationDelay_s <= 2.0
        }
    }

    // =========================================================================
    // Requirement 4: Discharge Capacity
    //
    // Regulatory basis:
    // SOLAS Chapter II-1, Regulation 35: the bilge pumping system must be
    // capable of evacuating bilge water at a rate that prevents flooding.
    // The combined pump flow rate must exceed the maximum design inflow rate
    // (typically calculated from the worst-case damage stability scenario).
    //
    // Modelling note:
    // 'designInflow' is the maximum water ingress rate from the damage
    // stability calculation (naval architecture tool output — e.g., Maxsurf
    // Stability or NAPA). In this model it is declared as an attribute on the
    // system subject so the Analysis layer can bind it to the constraint.
    //
    // Verification method: PumpFlowPhysics constraint in Analysis layer
    // evaluates (pumpA.flowRate + pumpB.flowRate) * efficiency * (1 - pipeLoss)
    // against a bound designInflow value.
    //
    // DOORS / Jama traceability ID: BPS-REQ-004
    // =========================================================================
    requirement def DischargeCapacityRequirement {
        subject sys : BilgePumpSystem;

        // Design inflow rate from damage stability analysis (m³/s).
        // SOURCE: naval architecture tool (Maxsurf / NAPA stability module)
        attribute designInflow : Real;

        doc
        /* The combined discharge flow rate of Pump A and Pump B, after
         * accounting for hydraulic efficiency and pipe losses, shall meet
         * or exceed the design inflow rate derived from the damage stability
         * analysis, as required by SOLAS II-1 Regulation 35.
         */

        require constraint {
            sys.pumpA.flowRate + sys.pumpB.flowRate >= designInflow
        }
    }
    //
    // =========================================================================
    // Requirement 5: Controller Activation Timing
    //
    // Regulatory basis:
    // Derived from STPA UCA-001 and UCA-005 safety constraints (SR-001/SR-005
    // in Safety.sysml). Formalised here at the system-requirements layer
    // with a directly measurable bound.
    // Simulink discrete-event timing analysis (SIM-CTRL-001 §3.1) validates:
    // Nominal:           responseTime_s = 1.0 s → PASS
    // High CPU load:     responseTime_s = 2.8 s → PASS
    // Watchdog recovery: responseTime_s = 4.9 s → PASS (marginal)
    // Software hang:     responseTime_s = 9999.0 s → FAIL (FM-C-001)
    //
    // Verification method: BilgePumpTimingVerification analysis def.
    // Nominal: responseTime_s = 1.0 → SATISFIED.
    // Negative: responseTime_s = 9999.0 → VIOLATED (see FMEA_ControllerHang).
    //
    // State machine link: MONITORING → PUMP_A_ACTIVE transition guard.
    // See PumpControllerBehavior in StateMachine.sysml.
    //
    // DOORS / Jama traceability ID: BPS-REQ-005
    // =========================================================================
    requirement def ControllerActivationTimingRequirement {
        subject sys : BilgePumpSystem;
        //
        doc
        /* The PumpController shall issue a pump activation command within
         * 5.0 seconds of detecting a water level at or above triggerLevel_m.
         * Derived from STPA SR-001/SR-005; validated by Simulink timing
         * analysis SIM-CTRL-001 §3.1.
         */
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
    // Derived from STPA UCA-004 safety constraint (SR-004 in Safety.sysml).
    // This requirement closes a gap in the original 4-requirement set:
    // BPS-REQ-002 (PumpRedundancyRequirement) verifies structural redundancy
    // (pumpB.isRedundant == true) but does NOT verify the TIMING of failover.
    // SIM-CTRL-001 §3.2 provides the timing bound:
    // Normal failover:   failoverTime_s = 0.8 s → PASS
    // Delayed detection: failoverTime_s = 2.7 s → PASS
    // No failover:       failoverTime_s = 9999.0 s → FAIL (FM-C-003)
    //
    // Verification method: BilgePumpTimingVerification analysis def.
    // Nominal: failoverTime_s = 0.8 s → SATISFIED.
    // Negative: failoverTime_s = 9999.0 s → VIOLATED (FMEA_FailoverNotTriggered).
    //
    // State machine link: PUMP_A_ACTIVE → FAILOVER transition guard.
    // See PumpControllerBehavior in StateMachine.sysml.
    //
    // DOORS / Jama traceability ID: BPS-REQ-006
    // =========================================================================
    requirement def FailoverSwitchTimingRequirement {
        subject sys : BilgePumpSystem;
        //
        doc
        /* The PumpController shall issue a Pump B activation command within
         * 3.0 seconds of detecting a Pump A fault condition.
         * Derived from STPA SR-004 and Simulink failover timing analysis
         * SIM-CTRL-001 §3.2. Closes the gap in BPS-REQ-002 which verifies
         * structural redundancy but not failover timing.
         */
        //
        require constraint {
            sys.controller.failoverTime_s <= 3.0
        }
    }
    //
    // =========================================================================
    // Fault-Tolerance Requirements (FT-*)
    //
    // These requirements decompose the abstract safety property:
    // "The bilge pump system shall remain safe under all conditions within
    // its defined operating envelope."
    //
    // Motivation: the original 6 requirements (REQ-001..006) each check a
    // single attribute at a single point in time.  They CANNOT detect:
    // - sensor accuracy consuming the margin between trigger and MARPOL limit
    // - the efficiency + pipe-loss product undermining REQ-004's simple sum
    // - the timing chain (response + alarm) vs the physical overflow window
    // - adversarial parameter combinations where all 6 pass yet system fails
    //
    // All FT-* requirements are also checked by the Z3 formal analyser
    // (bilgepump/formal_analysis.py), which discovers the parametric envelopes
    // and counterexamples the SysML point-in-time engine cannot find.
    // =========================================================================

    // =========================================================================
    // FT-001: Sensor Accuracy Bound
    //
    // Gap closed: BPS-REQ-001 checks sys.sensor.waterLevel ≤ 0.3.
    // But waterLevel is the REPORTED value; the true level can be up to
    // (waterLevel + accuracy_m) if the sensor under-reads.  This requirement
    // closes the gap by adding the accuracy margin into the bound.
    //
    // Regulatory basis: sensor calibration certificate + IMO MARPOL 73/78 —
    // the 300 mm limit applies to the ACTUAL level, not the instrument reading.
    //
    // DOORS / Jama traceability ID: BPS-FT-001
    // =========================================================================
    requirement def SensorAccuracyBoundRequirement {
        subject sys : BilgePumpSystem;

        doc
        /* The reported water level plus the sensor accuracy margin shall
         * not exceed 300 mm.  This ensures the actual bilge level remains
         * within the MARPOL limit even under worst-case sensor under-reading.
         */

        require constraint {
            sys.sensor.waterLevel + sys.sensor.accuracy_m <= 0.3
        }
    }

    // =========================================================================
    // FT-002: Effective Discharge Capacity
    //
    // Gap closed: BPS-REQ-004 checks (flowA + flowB) ≥ designInflow, but the
    // PumpFlowPhysics constraint shows the net flow is actually:
    // Q_net = (flowA × η_A + flowB × η_B) × (1 − λ)
    // A pump pair that satisfies REQ-004 may still fail to overcome inflow
    // if efficiency is low and pipe losses are high.
    //
    // Regulatory basis: SOLAS II-1 Reg. 35 — required flow must be achievable
    // after accounting for all hydraulic losses.
    //
    // Modelling note: η_A and η_B are per-pump efficiencies, which may differ
    // (e.g., after wear).  designInflow is the same damage-stability value
    // used by REQ-004.
    //
    // DOORS / Jama traceability ID: BPS-FT-002
    // =========================================================================
    requirement def EffectiveDischargeCapacityRequirement {
        subject sys : BilgePumpSystem;

        // Design inflow rate from damage stability analysis (m³/s).
        // Same source as REQ-004: naval architecture tool (Maxsurf / NAPA).
        attribute designInflow : Real;

        doc
        /* The net discharge flow, after accounting for per-pump hydraulic
         * efficiency and pipe friction losses, shall meet or exceed the
         * design inflow rate.  This is more conservative than BPS-REQ-004,
         * which only checks the raw sum of pump flow rates.
         */

        require constraint {
            (sys.pumpA.flowRate * sys.pumpA.efficiency +
                sys.pumpB.flowRate * sys.pumpB.efficiency) *
            (1.0 - sys.discharge.pipeLossFactor) >=
            designInflow
        }
    }

    // =========================================================================
    // FT-003: Trigger Level Accuracy
    //
    // Gap closed: BPS-REQ-001 and BPS-REQ-005 both ignore sensor accuracy.
    // If the controller uses triggerLevel_m to decide when to start the pump,
    // and the sensor can under-read by accuracy_m, then the pump may not start
    // until the true level is (triggerLevel_m + accuracy_m) — which must still
    // be below the 300 mm MARPOL limit.
    //
    // Concrete scenario: triggerLevel_m=0.25, accuracy_m=0.05 → trigger
    // fires at apparent 0.25, but true level could be 0.30 (at the limit).
    //
    // DOORS / Jama traceability ID: BPS-FT-003
    // =========================================================================
    requirement def TriggerLevelAccuracyRequirement {
        subject sys : BilgePumpSystem;

        doc
        /* The controller trigger threshold plus the sensor accuracy margin
         * shall not exceed 300 mm.  This ensures pump activation occurs
         * before the actual water level reaches the MARPOL limit, even
         * under worst-case sensor under-reading.
         */

        require constraint {
            sys.controller.triggerLevel_m + sys.sensor.accuracy_m <= 0.3
        }
    }

    // =========================================================================
    // FT-004: End-to-End Response Time vs Overflow Window
    //
    // Gap closed: BPS-REQ-005 checks responseTime_s ≤ 5.0 s and BPS-REQ-003
    // checks alarmDelay_s ≤ 2.0 s.  Neither requirement verifies whether the
    // COMBINED timing chain (controller response + alarm activation) is short
    // enough relative to the physical overflow window — defined as the time
    // from water level at sensor threshold to SOLAS critical level, at the
    // current inflow rate.
    //
    // Formulation (division-free, equivalent form):
    // (responseTime_s + activationDelay_s) × inflowRate_m3s
    // ≤ criticalLevel_m − sensor.waterLevel
    //
    // Interpretation: the volume added to the bilge during the total response
    // delay must not exceed the remaining safe headroom.
    //
    // NOTE: inflowRate_m3s and criticalLevel_m are system-level attributes
    // added to BilgePumpSystem (Architecture.sysml) for this requirement.
    //
    // DOORS / Jama traceability ID: BPS-FT-004
    // =========================================================================
    requirement def EndToEndResponseRequirement {
        subject sys : BilgePumpSystem;

        doc
        /* The product of the total system response time (controller
         * activation delay plus alarm activation delay) and the water
         * inflow rate shall not exceed the remaining safe headroom
         * (critical level minus current water level).  This ensures
         * the timing chain is feasible for the physical flooding scenario.
         */

        require constraint {
            (sys.controller.responseTime_s + sys.alarm.activationDelay_s) * sys.inflowRate_m3s <=
            sys.criticalLevel_m - sys.sensor.waterLevel
        }
    }

    // =========================================================================
    // OOR-001: Override Ordering Requirement
    //
    // Gap closed: StateMachine.sysml has no guard preventing operator override
    // before the alarm notification arrives at the UI (alarm.notifyOut →
    // ui.notifyIn, connection [11]).  Z3 Level 6 (formal_analysis.py) found a
    // satisfiable trace where t_operator_override < t_alarm_notify_ui, meaning
    // a crew member could act on an override before seeing the alarm.
    //
    // This requirement closes that gap with a static snapshot constraint:
    // "if override is active, the alarm must already be active"
    // This is a conservative instantaneous approximation.  Full temporal proof
    // (for all traces, not just a single snapshot) requires Z3 Level 6 or a
    // model checker such as nuXmv / PRISM fed the StateMachine.sysml states.
    //
    // Regulatory basis:
    // IMO MSC/Circ.982 (Alarm Management Guidelines):
    // "Operator action must only be available after alarm acknowledgement."
    // DNV Rules Pt.4 Ch.9 (Alarm Systems): alarm acknowledgement prerequisite
    // before operator can suppress or override alarm-triggered actuation.
    //
    // State machine fix required: add a guard to controller.overrideIn port
    // that rejects commands unless sys.alarm.isActive == true.
    //
    // DOORS / Jama traceability ID: BPS-OOR-001
    // =========================================================================
    requirement def OverrideOrderingRequirement {
        subject sys : BilgePumpSystem;

        doc
        /* If the operator override is active, the alarm system must already
         * be active.  This ensures crew acts only after receiving the alarm
         * notification, preventing premature override before hazard awareness.
         * Derived from STPA Level-6 temporal ordering gap (Z3 formal_analysis).
         */

        require constraint {
            // "override active" implies "alarm active"
            // Instantaneous approximation of the temporal ordering property:
            // t_operator_override ≥ t_alarm_notify_ui
            sys.ui.overrideActive == false or sys.alarm.isActive == true
        }
    }
} // package BilgePump_Requirements
