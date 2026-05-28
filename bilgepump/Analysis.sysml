// =============================================================================
// BilgePump::Analysis
// Layer: Analysis
// Purpose: Physics constraint definition and analysis case (the "test runner").
//
// Import chain: Analysis imports Library, Architecture, and Requirements.
//   Library ← Architecture ← Requirements ← Analysis   (no cycles)
//
// HOW THE ANALYSIS CASE ACTS AS A TEST RUNNER
// ─────────────────────────────────────────────
// In SysML v2, an 'analysis def' is an action definition specialised for
// evaluation.  It declares:
//   • A 'subject' — the system instance under test (BilgePumpSystem)
//   • 'assert requirement' statements — each is a test case
//   • 'bind' statements — wire physical attribute values from the subject
//     into constraint parameters
//
// When executed by the SysML v2 Pilot API server, each 'assert requirement'
// is evaluated against the bound attribute values and returns SATISFIED or
// VIOLATED.  The analysis def is therefore the integration harness that:
//   1. Assembles the system (subject binding)
//   2. Runs every requirement check (assert statements)
//   3. Evaluates the physics model (PumpFlowPhysics constraint)
//   4. Reports pass/fail per requirement
//
// In GUI tools (Cameo Systems Modeler, Eclipse Papyrus-SysML):
//   Executing this node generates a Verification & Validation (V&V) matrix
//   showing traceability from each requirement to its pass/fail result.
//
// In a CI/CD pipeline (GitHub Actions / Jenkins):
//   The Pilot REST API can be called headlessly — POST the project, POST an
//   analysis execution request, GET results.  Exit code 1 on any VIOLATED.
// =============================================================================

package 'BilgePump::Analysis' {

    import 'BilgePump::Library'::*;
    import 'BilgePump::Architecture'::*;
    import 'BilgePump::Requirements'::*;
//
    // =========================================================================
    // StateTransitionTimingPhysics  — state machine transition timing budget
    //
    // Models the timing chain from sensor threshold crossing to pump activation
    // command, as measured by the Simulink discrete-event model SIM-CTRL-001:
    //   totalTime_s = samplingLatency_s + processingTime_s + commandLatency_s
    //
    // The constraint asserts totalTime_s ≤ maxResponseTime_s.
    //
    // EXTERNAL TOOL BINDING:
    //   ← Simulink/Stateflow discrete-event model (SIM-CTRL-001 §3.1):
    //     samplingLatency_s = 0.1 s  (100 ms sample interval)
    //     processingTime_s  = 0.9 s  (firmware processing, nominal)
    //     commandLatency_s  = 0.0 s  (direct GPIO — negligible)
    //     → totalTime_s = 1.0 s (nominal) ≤ 5.0 s maxResponseTime_s ✓
    //   Watchdog recovery: processingTime_s = 3.9 s → total = 4.9 s ≤ 5.0 s (marginal)
    //   Hang case (FM-C-001): totalTime_s = 9999.0 s >> maxResponseTime_s → VIOLATED
    //
    // Linked requirement: BPS-REQ-005 (ControllerActivationTimingRequirement)
    // Linked state:       MONITORING → PUMP_A_ACTIVE transition (StateMachine.sysml)
    // =========================================================================
    constraint def StateTransitionTimingPhysics {
        // Input: timing budget components
        attribute samplingLatency_s : Real;   // Sensor poll interval (s)
        attribute processingTime_s  : Real;   // Firmware processing time (s)
        attribute commandLatency_s  : Real;   // Output command transmission latency (s)
        // Input: timing bound from requirement
        attribute maxResponseTime_s : Real;   // Maximum allowed response time (s) [BPS-REQ-005]
//
        // Computed: total response time
        attribute totalTime_s       : Real;
//
        // Timing budget assertion
        assert constraint {
            totalTime_s == samplingLatency_s + processingTime_s + commandLatency_s
            and totalTime_s <= maxResponseTime_s
        }
    }
//
    // =========================================================================
    // PumpFlowPhysics  — physics constraint definition
    //
    // Models the net discharge capacity of the bilge pump system after
    // accounting for hydraulic efficiency and pipe friction losses.
    //
    // Equation:
    //   Q_net = (Q_A + Q_B) × η × (1 − λ)
    //   where:
    //     Q_A   = Pump A volumetric flow rate (m³/s)
    //     Q_B   = Pump B volumetric flow rate (m³/s)
    //     η     = hydraulic efficiency (0.0–1.0; from CFD pump curve)
    //     λ     = Darcy-Weisbach pipe loss factor (0.0–1.0; from P&ID hydraulic calc)
    //     Q_net = net effective discharge rate (m³/s)
    //
    // The constraint asserts Q_net ≥ Q_inflow (design inflow from stability analysis).
    //
    // EXTERNAL TOOL BINDINGS (hypothetical):
    //   ← CFD tool (ANSYS Fluent / OpenFOAM): exports η as a function of impeller
    //     speed; in a full digital twin this would be a lookup table binding.
    //   ← P&ID hydraulic calculation (Caesar II / PIPESIM): exports λ per pipe run.
    //   ← Maxsurf / NAPA stability module: exports Q_inflow from damage case.
    //   → Structural analysis (FEA): Q_net feeds back into flooding time calculation
    //     which drives hydrostatic pressure loads on bulkheads.
    // =========================================================================
    constraint def PumpFlowPhysics {
        // Input parameters — bound to system attributes in the analysis case
        attribute flowRateA     : Real;   // Pump A flow rate (m³/s)
        attribute flowRateB     : Real;   // Pump B flow rate (m³/s)
        attribute efficiency    : Real;   // Hydraulic efficiency η (0.0–1.0)
        attribute pipeLossFactor: Real;   // Pipe friction factor λ (0.0–1.0)
        attribute designInflow  : Real;   // Required minimum discharge (m³/s)

        // Computed result — net effective discharge rate
        attribute netFlow       : Real;

        // Physics assertion: computed net flow must meet or exceed design inflow
        assert constraint {
            netFlow == (flowRateA + flowRateB) * efficiency * (1.0 - pipeLossFactor)
            and netFlow >= designInflow
        }
    }

    // =========================================================================
    // BilgePumpVerification  — analysis case (TEST RUNNER)
    //
    // This is the top-level analysis definition that acts as the complete
    // verification harness for the bilge pump system.
    //
    // Execution sequence (as performed by the SysML v2 Pilot engine):
    //   Step 1 — Subject instantiation: 'sys' is created as a usage of
    //            BilgePumpSystem with attribute values set (see bind statements).
    //   Step 2 — Requirement evaluation: each 'assert requirement' block is
    //            resolved against the bound attribute values of 'sys'.
    //            Result: SATISFIED or VIOLATED per requirement.
    //   Step 3 — Physics constraint evaluation: PumpFlowPhysics parameters
    //            are bound to sys attribute values; constraint assertion checked.
    //   Step 4 — Results aggregated and returned by the API server.
    //
    // Nominal test values (positive test — all should be SATISFIED):
    //   sensor.waterLevel       = 0.15 m    (below 0.3 m threshold)
    //   pumpB.isRedundant       = true
    //   alarm.activationDelay_s = 0.5 s     (below 2.0 s threshold)
    //   pumpA.flowRate          = 0.025 m³/s
    //   pumpB.flowRate          = 0.025 m³/s
    //   efficiency              = 0.82
    //   pipeLossFactor          = 0.05
    //   designInflow            = 0.030 m³/s
    //   → netFlow = (0.025+0.025) × 0.82 × (1−0.05) = 0.0389 m³/s ≥ 0.030 ✓
    //
    // Negative test (run from Verification.ipynb Cell 8):
    //   pumpA.flowRate = 0.0  →  DischargeCapacityRequirement VIOLATED
    // =========================================================================
    analysis def BilgePumpVerification {

        // The system under verification — instantiated with nominal attribute values
        subject sys : BilgePumpSystem {

            // --- BilgeWaterSensor ---
            // Nominal: water level well below trigger threshold
            // SOURCE: representative bilge sounding during calm-water operation
            bind sys.sensor.waterLevel          = 0.15;

            // --- PumpController ---
            // Trigger level: controller activates pump at 0.25 m (safety margin below 0.3 m req)
            bind sys.controller.triggerLevel_m  = 0.25;
            bind sys.controller.responseTime_s  = 1.0;

            // --- PowerSupply ---
            // Main bus active; emergency bus not yet engaged
            bind sys.power.nominalVoltage       = 440.0;
            bind sys.power.redundancyActive     = false;

            // --- BilgePumpA (primary) ---
            // Flow rate from vendor test certificate / CFD pump curve at rated speed
            bind sys.pumpA.flowRate             = 0.025;
            bind sys.pumpA.efficiency           = 0.82;
            bind sys.pumpA.runHours             = 120.0;

            // --- BilgePumpB (redundant) ---
            // Identical to A; isRedundant confirms DNV classification compliance
            bind sys.pumpB.flowRate             = 0.025;
            bind sys.pumpB.efficiency           = 0.82;
            bind sys.pumpB.runHours             = 85.0;
            bind sys.pumpB.isRedundant          = true;

            // --- DischargeLine ---
            // Pipe friction factor from P&ID hydraulic calculation (Darcy-Weisbach)
            bind sys.discharge.pipeLossFactor   = 0.05;

            // --- AlarmSystem ---
            // 0.5 s activation delay — well within IEC 60945 2.0 s limit
            bind sys.alarm.activationDelay_s    = 0.5;
            bind sys.alarm.isActive             = false;

            // --- OperatorInterface ---
            // No override active in nominal test
            bind sys.ui.overrideActive          = false;
        }

        // Physics constraint usage — parameters bound to system attribute values
        // This evaluates Q_net and confirms it meets the design inflow requirement.
        // Design inflow of 0.030 m³/s from damage stability analysis (Maxsurf export).
        constraint physicsCheck : PumpFlowPhysics {
            bind physicsCheck.flowRateA      = sys.pumpA.flowRate;
            bind physicsCheck.flowRateB      = sys.pumpB.flowRate;
            bind physicsCheck.efficiency     = sys.pumpA.efficiency;
            bind physicsCheck.pipeLossFactor = sys.discharge.pipeLossFactor;
            bind physicsCheck.designInflow   = 0.030;
        }

        // =====================================================================
        // TEST CASES — assert requirement statements
        // Each line is one test case. The analysis engine evaluates the
        // requirement def's constraint body against the bound 'sys' values.
        // In a V&V matrix these map to individual rows with SATISFIED/VIOLATED.
        // =====================================================================

        // TEST 1: Water level must not exceed 0.3 m  [BPS-REQ-001]
        assert requirement waterLevelCheck : WaterLevelRequirement { subject sys; }

        // TEST 2: Pump B must be designated redundant  [BPS-REQ-002]
        assert requirement redundancyCheck : PumpRedundancyRequirement { subject sys; }

        // TEST 3: Alarm activation must be within 2.0 s  [BPS-REQ-003]
        assert requirement alarmCheck : AlarmResponseRequirement { subject sys; }

        // TEST 4: Combined discharge must meet design inflow  [BPS-REQ-004]
        // Note: this also requires the physics constraint (physicsCheck) above
        // to have been evaluated; the require constraint in DischargeCapacityRequirement
        // checks pumpA.flowRate + pumpB.flowRate against the designInflow attribute.
        assert requirement dischargeCheck : DischargeCapacityRequirement {
            subject sys;
            bind dischargeCheck.designInflow = 0.030;
        }

        // =====================================================================
        // OBJECTIVE (documentation)
        // This analysis case serves as the complete integration test harness.
        // It demonstrates the following SysML v2 model features:
        //   • part def / part usage separation (Library vs Architecture)
        //   • Typed port connections with directional signal flow
        //   • Requirement defs with assert constraint bodies
        //   • Constraint defs for physics-based verification
        //   • bind statements connecting architecture attributes to constraints
        //   • analysis def as the V&V execution entry point
        //
        // To add a new test scenario:
        //   1. Add a new requirement def in Requirements.sysml
        //   2. Add an 'assert requirement' line here
        //   3. Override attribute values in the 'subject sys' block
        //   4. Re-run via Verification.ipynb Cell 7
        // =====================================================================
    }
//
    // =========================================================================
    // BilgePumpTimingVerification  — timing analysis case (TEST RUNNER)
    //
    // Verifies the two timing requirements introduced by the state machine
    // analysis (BPS-REQ-005, BPS-REQ-006) and re-asserts the alarm timing
    // requirement (BPS-REQ-003) in the same harness.
    //
    // Nominal test values (positive test — all should be SATISFIED):
    //   controller.responseTime_s = 1.0 s   (SIM-CTRL-001 §3.1 nominal)
    //   controller.failoverTime_s = 0.8 s   (SIM-CTRL-001 §3.2 normal failover)
    //   alarm.activationDelay_s   = 0.5 s   (nominal; well within 2.0 s limit)
    //   Timing budget: 0.1 s (sampling) + 0.9 s (processing) + 0.0 s (cmd) = 1.0 s
    //   → totalTime_s = 1.0 s ≤ 5.0 s ✓
    //
    // Negative tests (run from Safety.ipynb):
    //   FMEA_ControllerHang (FMEA.sysml): responseTime_s = 9999.0 → BPS-REQ-005 VIOLATED
    //   FMEA_FailoverNotTriggered (FMEA.sysml): failoverTime_s = 9999.0 → BPS-REQ-006 VIOLATED
    // =========================================================================
    analysis def BilgePumpTimingVerification {
//
        subject sys : BilgePumpSystem {
//
            // --- PumpController timing attributes (UNDER TEST) ---
            // Nominal response time from SIM-CTRL-001 §3.1
            bind sys.controller.responseTime_s  = 1.0;
            // Nominal failover time from SIM-CTRL-001 §3.2
            bind sys.controller.failoverTime_s  = 0.8;
            // Trigger level (required for subject completeness)
            bind sys.controller.triggerLevel_m  = 0.25;
//
            // --- BilgeWaterSensor (nominal) ---
            bind sys.sensor.waterLevel          = 0.15;
//
            // --- PowerSupply (nominal) ---
            bind sys.power.nominalVoltage       = 440.0;
            bind sys.power.redundancyActive     = false;
//
            // --- BilgePumpA and B (nominal — not timing-critical here) ---
            bind sys.pumpA.flowRate             = 0.025;
            bind sys.pumpA.efficiency           = 0.82;
            bind sys.pumpA.runHours             = 120.0;
            bind sys.pumpB.flowRate             = 0.025;
            bind sys.pumpB.efficiency           = 0.82;
            bind sys.pumpB.runHours             = 85.0;
            bind sys.pumpB.isRedundant          = true;
//
            // --- DischargeLine (nominal) ---
            bind sys.discharge.pipeLossFactor   = 0.05;
//
            // --- AlarmSystem timing (UNDER TEST) ---
            // 0.5 s activation delay — well within IEC 60945 2.0 s limit
            bind sys.alarm.activationDelay_s    = 0.5;
            bind sys.alarm.isActive             = false;
//
            // --- OperatorInterface (nominal) ---
            bind sys.ui.overrideActive          = false;
        }
//
        // Timing budget constraint usage
        // Decomposes responseTime_s into sampling + processing + command latency.
        // SOURCE: SIM-CTRL-001 §3.1 (100 ms sample interval + 900 ms processing)
        constraint timingBudget : StateTransitionTimingPhysics {
            bind timingBudget.samplingLatency_s = 0.1;    // 100 ms sample interval
            bind timingBudget.processingTime_s  = 0.9;    // Firmware processing (nominal)
            bind timingBudget.commandLatency_s  = 0.0;    // Direct GPIO — negligible
            bind timingBudget.maxResponseTime_s = 5.0;    // Limit from BPS-REQ-005
        }
//
        // TEST 5: Controller activation within 5.0 s of threshold crossing [BPS-REQ-005]
        // Linked: MONITORING → PUMP_A_ACTIVE transition (StateMachine.sysml)
        assert requirement activationTimingCheck : ControllerActivationTimingRequirement { subject sys; }
//
        // TEST 6: Failover switch within 3.0 s of Pump A fault [BPS-REQ-006]
        // Linked: PUMP_A_ACTIVE → FAILOVER transition (StateMachine.sysml)
        assert requirement failoverTimingCheck : FailoverSwitchTimingRequirement { subject sys; }
//
        // TEST 3 (re-asserted in timing context): Alarm within 2.0 s [BPS-REQ-003]
        // Linked: PUMP_A_ACTIVE → ALARM_TRIGGERED transition (StateMachine.sysml)
        assert requirement alarmTimingCheck : AlarmResponseRequirement { subject sys; }
    }
//
}
