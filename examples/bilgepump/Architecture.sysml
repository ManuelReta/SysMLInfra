// =============================================================================
// BilgePump::Architecture
// Layer: Architecture
// Purpose: Instantiate Library part defs as part usages inside the top-level
// BilgePumpSystem composite part. All signal flows from the SysML
// block diagram are represented as connect statements here.
//
// Import chain: Architecture imports Library (one-way; no circular deps).
//
// Naming convention:
// - Part usages are lower-camel (sensor, controller, pumpA …)
// - Port references follow: <usage>.<portName>
// - Connections are directional: source port → destination port
// (where destination uses the conjugate ~Port def)
// =============================================================================

package BilgePump_Architecture {
    private import ScalarValues::*;
    public import BilgePump_Library::*;

    // =========================================================================
    // BilgePumpSystem
    // Top-level composite system.  Contains all 8 subsystem part usages and
    // the 11 connect statements that fully wire the signal/flow architecture
    // shown in the SysML IBD (internal block diagram).
    //
    // This part def is the subject bound in Requirements and Analysis layers.
    // It is intentionally definition-only here; the Analysis layer instantiates
    // it as a usage named 'sys' for constraint evaluation.
    // =========================================================================
    part def BilgePumpSystem {
        // ---------------------------------------------------------------------
        // System-level operational parameters — fault-tolerance analysis (FT-*)
        // These are not component attributes; they describe the operational
        // envelope of the entire system in the damage stability scenario.
        //
        // SOURCE (inflowRate_m3s): Naval architecture stability analysis tool
        // (Maxsurf / NAPA) — worst-case water ingress rate for the design flood
        // scenario.  Nominal design storm: 0.020 m³/s.
        // Catastrophic breach scenario (SOLAS damage case): up to 0.233 m³/s.
        //
        // SOURCE (criticalLevel_m): SOLAS Chapter II-1 structural margin.
        // Water level above which freeboard is compromised.
        // Conservative bound: 0.5 m above bilge floor.
        // ---------------------------------------------------------------------
        attribute inflowRate_m3s : Real = 0.020; // Design water ingress rate (m³/s)
        attribute criticalLevel_m : Real = 0.5; // Max tolerable level before SOLAS breach (m)

        // ---------------------------------------------------------------------
        // Part Usages
        // Each entry instantiates a Library part def as a named role within
        // the system boundary.
        // ---------------------------------------------------------------------

        // Water level sensing — bottom of the signal-flow hierarchy
        part sensor : BilgeWaterSensor {
            attribute waterLevel = 0.15; // nominal bilge sounding (m)
        }

        // Central control logic — receives level, drives pumps and alarm
        part controller : PumpController {
            attribute triggerLevel_m = 0.25; // activation level (m)
            attribute responseTime_s = 1.0; // breach→start (s)
        }

        // Dual-source power (main + emergency bus)
        part power : PowerSupply {
            attribute nominalVoltage = 440.0; // bus voltage (V)
            attribute redundancyActive = false; // emergency bus idle
        }

        // Primary bilge pump
        part pumpA : BilgePumpA {
            attribute flowRate = 0.025; // rated flow (m³/s)
            attribute efficiency = 0.82; // hydraulic efficiency
            attribute runHours = 120.0; // cumulative run hours
        }

        // Redundant bilge pump — independent power feed per DNV Pt.4 Ch.6
        part pumpB : BilgePumpB {
            attribute flowRate = 0.025; // rated flow (m³/s)
            attribute efficiency = 0.82; // hydraulic efficiency
            attribute runHours = 85.0; // cumulative run hours
            attribute isRedundant = true; // designated redundant unit
        }

        // Overboard discharge piping, strainer, and check valves
        part discharge : DischargeLine {
            attribute pipeLossFactor = 0.05; // Darcy-Weisbach λ
            attribute marpolLimit_m = 0.30; // MARPOL 73/78 max bilge-well level
        }

        // Audible / visual alarm unit
        part alarm : AlarmSystem {
            attribute activationDelay_s = 0.5; // IEC 60945 ≤ 2.0 s
            attribute isActive = false; // not sounding (nominal)
        }

        // Operator HMI panel — status display and manual override
        part ui : OperatorInterface {
            attribute overrideActive = false; // no override (nominal)
        }

        // ---------------------------------------------------------------------
        // Connect Statements — 11 signal / flow paths
        // Ordered to follow the data flow top-to-bottom as drawn in the SysML
        // block diagram:
        // Sensor → Controller → Pumps → Discharge
        // → Alarm → UI
        // ↔ UI (status / override)
        // Power  → Pumps
        // ---------------------------------------------------------------------

        // [1] Water level measurement: Sensor → Controller
        // This is the primary trigger signal for the entire system.
        // In vessel integration: also tapped by SCADA historian.
        connect sensor.levelOut to controller.levelIn;

        // [2] Pump A start/stop command: Controller → PumpA
        // Controller evaluates triggerLevel_m and responseTime_s before
        // issuing this command. Firmware generated from Simulink model.
        connect controller.pumpAControl to pumpA.controlIn;

        // [3] Pump B start/stop command: Controller → PumpB
        // Issued when Pump A is faulted or on manual override.
        connect controller.pumpBControl to pumpB.controlIn;

        // [4] Electrical power rail: PowerSupply → PumpA
        // Carries nominal voltage; isEmergency flag raised during bus transfer.
        connect power.powerOutA to pumpA.powerIn;

        // [5] Electrical power rail: PowerSupply → PumpB
        // Independent feed path required for redundancy per SOLAS II-1.
        connect power.powerOutB to pumpB.powerIn;

        // [6] Fluid discharge flow: PumpA → DischargeLine
        // Flow rate attribute is evaluated against inflow in Analysis layer.
        connect pumpA.flowOut to discharge.flowInA;

        // [7] Fluid discharge flow: PumpB → DischargeLine
        // Combined with PumpA flow for DischargeCapacityRequirement.
        connect pumpB.flowOut to discharge.flowInB;

        // [8] System status: Controller → OperatorInterface
        // Status string updated on every pump state change.
        // Also routed to VDR in vessel integration.
        connect controller.statusOut to ui.statusIn;

        // [9] Manual override: OperatorInterface → Controller
        // Bridge crew can force-start/stop pumps; controller logs override event.
        connect ui.overrideOut to controller.overrideIn;

        // [10] Alarm trigger: Controller → AlarmSystem
        // Fires when waterLevel > triggerLevel_m or fault detected.
        connect controller.alarmOut to alarm.alarmIn;

        // [11] Alarm notification: AlarmSystem → OperatorInterface
        // AlarmSystem annunciates locally; also mirrors to bridge BNWAS.
        connect alarm.notifyOut to ui.notifyIn;

        // ---------------------------------------------------------------------
        // State machine behavioral bindings
        // Links part instances to state machine definitions in StateMachine.sysml.
        // PumpControllerBehavior models 7 discrete controller operating states.
        // BilgePumpSystemBehavior models 5 system-level operational modes.
        // SOURCE: BilgePump_StateMachine (StateMachine.sysml)
        //
        // NOTE: These exhibits are commented out so that Architecture.sysml is
        // self-contained and kernel-publishable on its own. They reference types
        // defined in StateMachine.sysml; re-enable them only when StateMachine is
        // co-loaded/published in the same kernel session.
        // ---------------------------------------------------------------------
        // exhibit state controllerBehavior : PumpControllerBehavior;
        // exhibit state systemBehavior     : BilgePumpSystemBehavior;
    }
} // package BilgePump_Architecture
