// =============================================================================
// BilgePump::StateMachine
// Layer: Behavioral Modeling
// Purpose: Discrete-event state machine definitions for the BilgePumpSystem.
// Two interlocking state machines:
// 1. PumpControllerBehavior — 7-state sub-machine for PumpController
// 2. BilgePumpSystemBehavior — 5-state top-level system machine
// (aggregates controller sub-states into crew-visible modes)
//
// Import chain:
// BilgePump::Library       — part def and attribute types
// BilgePump::Architecture  — BilgePumpSystem, PumpController part instances
//
// SOURCE DOCUMENTS:
// SIM-CTRL-001  — Simulink/Stateflow discrete-event timing model (controller firmware)
// STPA-BPS-002  — Unsafe Control Actions (UCA guidewords → transition semantics)
// FMEA-BPS-001  — Failure mode → fault/failover state mapping
//
// STATE DESIGN RATIONALE:
// (a) SIM-CTRL-001 timing bounds: responseTime_s ≤ 5.0 s, failoverTime_s ≤ 3.0 s
// (b) UCA guidewords "Not Provided" and "Provided Too Late" define activation transitions
// (c) FM-C-001 (controller hang) → FAULT state
// FM-C-003 (failover not triggered) → FAILOVER state
//
// INTEGRATION WITH OTHER LAYERS:
// Architecture.sysml : exhibit statements link part instances to state defs here
// Requirements.sysml : BPS-REQ-005, BPS-REQ-006 — timing guards formalised
// Analysis.sysml     : BilgePumpTimingVerification asserts BPS-REQ-005/006
// Safety.sysml       : transitionRef fields in #UCA blocks cross-reference transitions
// FMEA.sysml         : stateRef fields in #FailureMode blocks cross-reference states
//
// STATE SPACE RESPONSIBILITY:
// The agent output artifact lib/state-space.json maps each state to its owning
// component, entry/exit conditions, linked safety requirements (SR-xxx),
// linked failure modes (FM-xxx), and timing constraints.
// See sysml-state-machine-mapper.agent.md for the generation specification.
//
// PILOT API NOTE:
// state def and transition are core SysML v2 constructs (SysML v2 §7.14).
// Guard expressions use inline comments rather than executable if-clauses to
// ensure compatibility across Pilot API JAR versions. The guard semantics are
// formally captured in linked constraint defs (Analysis.sysml) and requirement
// defs (Requirements.sysml).
// =============================================================================

package BilgePump_StateMachine {
    private import ScalarValues::*;
    public import BilgePump_Library::*;
    public import BilgePump_Architecture::*;

    // =========================================================================
    // PumpControllerBehavior
    // Sub-state machine for the PumpController component.
    // Exhibited by: controller : PumpController (Architecture.sysml)
    //
    // STATE INVENTORY (7 states):
    // IDLE              — system energised, no bilge threat detected
    // MONITORING        — continuously polling sensor.waterLevel
    // PUMP_A_ACTIVE     — Pump A commanded ON; waterLevel ≥ triggerLevel_m
    // DUAL_PUMP_ACTIVE  — both pumps active (high-demand or failover handoff complete)
    // ALARM_TRIGGERED   — alarm.alarmIn asserted; IEC 60945 notification window active
    // FAILOVER          — Pump A fault detected; Pump B bearing sole responsibility
    // FAULT             — unrecoverable state; controller hang or both pumps unavailable
    //
    // TIMING CONSTRAINTS (source: SIM-CTRL-001):
    // MONITORING → PUMP_A_ACTIVE    : responseTime_s ≤ 5.0 s  [UCA-001/005, BPS-REQ-005]
    // PUMP_A_ACTIVE → ALARM_TRIGGERED: activationDelay_s ≤ 2.0 s [UCA-003, BPS-REQ-003]
    // PUMP_A_ACTIVE → FAILOVER       : failoverTime_s ≤ 3.0 s   [UCA-004, BPS-REQ-006]
    // =========================================================================
    state def PumpControllerBehavior {
        // -----------------------------------------------------------------
        // IDLE
        // Entry condition:  system power-on or operator hardware reset via ui.overrideOut
        // Exit condition:   auto-transition to MONITORING on startup
        // Linked SRs:       none (passive, no constraints active)
        // Linked FMs:       none
        // -----------------------------------------------------------------
        state IDLE;

        // -----------------------------------------------------------------
        // MONITORING
        // Entry condition:  auto-transition from IDLE; re-entered after ALARM ack
        // or after dewatering completes (waterLevel < triggerLevel_m)
        // Do:               continuous evaluation of sensor.waterLevel vs triggerLevel_m
        // Exit condition:   waterLevel ≥ triggerLevel_m → PUMP_A_ACTIVE
        // Timing guard:     responseTime_s ≤ 5.0 s from detection to command [BPS-REQ-005]
        // SOURCE: SIM-CTRL-001 §3.1 (nominal 1.0 s; watchdog 4.9 s)
        // -----------------------------------------------------------------
        state MONITORING;

        // -----------------------------------------------------------------
        // PUMP_A_ACTIVE
        // Entry condition:  waterLevel ≥ triggerLevel_m; responseTime_s ≤ 5.0 s [SR-001/005]
        // Exit paths:
        // → ALARM_TRIGGERED   : activationDelay_s ≤ 2.0 s [SR-003, BPS-REQ-003]
        // → FAILOVER          : Pump A fault; failoverTime_s ≤ 3.0 s [SR-004, BPS-REQ-006]
        // → MONITORING        : waterLevel < triggerLevel_m (dewatering complete)
        // → FAULT             : responseTime_s > 5.0 s (controller hang, FM-C-001)
        // -----------------------------------------------------------------
        state PUMP_A_ACTIVE;

        // -----------------------------------------------------------------
        // DUAL_PUMP_ACTIVE
        // Entry condition:  (a) high bilge inflow demands both pumps, OR
        // (b) FAILOVER handoff complete — Pump B at full capacity
        // Exit condition:   waterLevel < triggerLevel_m → MONITORING
        // NOTE: Q_total = pumpA.flowRate + pumpB.flowRate; satisfies BPS-REQ-004
        // -----------------------------------------------------------------
        state DUAL_PUMP_ACTIVE;

        // -----------------------------------------------------------------
        // ALARM_TRIGGERED
        // Entry condition:  waterLevel > alarm threshold AND activationDelay_s ≤ 2.0 s
        // SOURCE: IEC 60945 §4.3; SIM-CTRL-001 alarm logic
        // Linked: UCA-003 (transitionRef), SR-003, BPS-REQ-003
        // Exit condition:   operator acknowledgement via ui.overrideOut → MONITORING
        // -----------------------------------------------------------------
        state ALARM_TRIGGERED;

        // -----------------------------------------------------------------
        // FAILOVER
        // Entry condition:  Pump A fault detected; controller issues ActivatePumpB command
        // failoverTime_s ≤ 3.0 s from fault detection to Pump B command
        // SOURCE: SIM-CTRL-001 §3.2 (nominal 0.8 s; delayed 2.7 s)
        // Linked: UCA-004 (transitionRef), SR-004, BPS-REQ-006
        // Exit condition:   Pump B reaches operational flow → DUAL_PUMP_ACTIVE
        // Linked FMs:       FM-C-003 (failover not triggered — violates BPS-REQ-006)
        // -----------------------------------------------------------------
        state FAILOVER;

        // -----------------------------------------------------------------
        // FAULT
        // Entry condition:  controller hang (FM-C-001) OR both pumps unavailable
        // Violates BPS-REQ-005 (responseTime_s → effectively ∞)
        // Exit condition:   operator hardware reset → IDLE (requires manual intervention)
        // Linked FMs:       FM-C-001 (RPN=140, S=10, O=2, D=7)
        // DESIGN NOTE:      SIM-CTRL-001 §3.1 — hardware watchdog recommended to prevent
        // software hang from being unrecoverable
        // -----------------------------------------------------------------
        state FAULT;

        // -----------------------------------------------------------------
        // TRANSITIONS
        // Names are the canonical cross-reference identifiers used in:
        // Safety.sysml  #UCA blocks → transitionRef field
        // lib/state-space.json     → coverage.uca_coverage entries
        // -----------------------------------------------------------------

        // Startup: enter IDLE first
        entry;
        then IDLE;

        // IDLE → MONITORING (auto-transition on system startup)
        // Condition: system power on; no active fault
        transition IDLE_to_MONITORING first IDLE then MONITORING;

        // MONITORING → PUMP_A_ACTIVE
        // Trigger:  waterLevel crosses triggerLevel_m (sensor.levelOut > controller threshold)
        // Timing:   responseTime_s ≤ 5.0 s from detection to pump command [UCA-001/005, BPS-REQ-005]
        // SOURCE:   SIM-CTRL-001 §3.1; STPA UCA-001 "ActivatePumpA — Not Provided"
        // transitionRef used in Safety.sysml: UCA-001, UCA-005
        // guard: sys.sensor.waterLevel >= sys.controller.triggerLevel_m
        // AND sys.controller.responseTime_s <= 5.0
        transition MONITORING_to_PUMP_A_ACTIVE first MONITORING then PUMP_A_ACTIVE;

        // PUMP_A_ACTIVE → ALARM_TRIGGERED
        // Trigger:  water level continues rising above alarm threshold
        // Timing:   activationDelay_s ≤ 2.0 s from trigger to alarm annunciation [UCA-003]
        // SOURCE: IEC 60945 §4.3; STPA UCA-003 "TriggerAlarm — Not Provided"
        // transitionRef used in Safety.sysml: UCA-003
        // guard: sys.alarm.activationDelay_s <= 2.0
        transition PUMP_A_ACTIVE_to_ALARM_TRIGGERED first PUMP_A_ACTIVE then ALARM_TRIGGERED;

        // PUMP_A_ACTIVE → FAILOVER
        // Trigger:  Pump A fault detected (zero flow or drive fault signal)
        // Timing:   failoverTime_s ≤ 3.0 s from fault detection to Pump B command [UCA-004, BPS-REQ-006]
        // SOURCE: SIM-CTRL-001 §3.2; STPA UCA-004 "ActivatePumpB — Not Provided"
        // transitionRef used in Safety.sysml: UCA-004
        // guard: sys.pumpA.flowRate == 0.0 AND sys.controller.failoverTime_s <= 3.0
        transition PUMP_A_ACTIVE_to_FAILOVER first PUMP_A_ACTIVE then FAILOVER;

        // PUMP_A_ACTIVE → FAULT (controller hang; FM-C-001)
        // Trigger:  controller responseTime_s exceeds maximum bound
        // NOTE:     In practice caught by hardware watchdog; modeled for FMEA traceability
        // guard: sys.controller.responseTime_s > 5.0
        transition PUMP_A_ACTIVE_to_FAULT first PUMP_A_ACTIVE then FAULT;

        // PUMP_A_ACTIVE → MONITORING (normal dewatering complete)
        // Trigger:  waterLevel drops below triggerLevel_m after pumping
        // guard: sys.sensor.waterLevel < sys.controller.triggerLevel_m
        transition PUMP_A_ACTIVE_to_MONITORING first PUMP_A_ACTIVE then MONITORING;

        // FAILOVER → DUAL_PUMP_ACTIVE
        // Trigger:  Pump B reaches operational flow rate; Pump A still faulted
        // guard: sys.pumpB.flowRate > 0.0
        transition FAILOVER_to_DUAL_PUMP_ACTIVE first FAILOVER then DUAL_PUMP_ACTIVE;

        // DUAL_PUMP_ACTIVE → MONITORING (dewatering complete; both pumps can stop)
        // guard: sys.sensor.waterLevel < sys.controller.triggerLevel_m
        transition DUAL_PUMP_ACTIVE_to_MONITORING first DUAL_PUMP_ACTIVE then MONITORING;

        // ALARM_TRIGGERED → MONITORING (operator acknowledges alarm)
        // Trigger:  operator action via ui.overrideOut port (bridge panel or HMI)
        // guard: sys.ui.overrideActive == true
        transition ALARM_TRIGGERED_to_MONITORING first ALARM_TRIGGERED then MONITORING;

        // FAULT → IDLE (operator hardware reset)
        // NOTE: Requires physical hardware action; cannot be cleared by software alone
        // guard: sys.ui.overrideActive == true (hardware reset acknowledged)
        transition FAULT_to_IDLE first FAULT then IDLE;
    }

    // =========================================================================
    // BilgePumpSystemBehavior
    // Top-level system state machine. Aggregates PumpController sub-states into
    // 5 system-level operational modes visible to crew and SCADA.
    // Exhibited by: sys : BilgePumpSystem (Architecture.sysml)
    //
    // STATE INVENTORY (5 states):
    // STANDBY         — normal operation; no bilge threat
    // PUMPING         — active dewatering underway
    // ALERT           — alarm active; awaiting crew acknowledgement
    // FAILOVER_ACTIVE — Pump A faulted; Pump B bearing sole load
    // CRITICAL_FAULT  — controller or dual-pump failure; SOLAS emergency protocol
    //
    // CREW-VISIBLE STATUS (maps to StatusPort.status string on controller.statusOut):
    // STANDBY        → "NORMAL"
    // PUMPING        → "PUMPING"
    // ALERT          → "FAULT"    (alarm annunciation active)
    // FAILOVER_ACTIVE → "FAULT"  (reduced redundancy — Pump A unavailable)
    // CRITICAL_FAULT → "FAULT"   + physical alarm latched (manual reset required)
    //
    // CONTROLLER SUB-STATE CORRESPONDENCE:
    // STANDBY        ← controller in IDLE or MONITORING
    // PUMPING        ← controller in PUMP_A_ACTIVE or DUAL_PUMP_ACTIVE
    // ALERT          ← controller in ALARM_TRIGGERED
    // FAILOVER_ACTIVE← controller in FAILOVER
    // CRITICAL_FAULT ← controller in FAULT
    // =========================================================================
    state def BilgePumpSystemBehavior {
        // STANDBY — normal operations; sensor polling; no active dewatering
        // Linked: no active requirements asserted (all SATISFIED by default)
        state STANDBY;

        // PUMPING — discharge operations active; waterLevel elevated or rising
        // Linked: BPS-REQ-004 (DischargeCapacityRequirement) under continuous evaluation
        state PUMPING;

        // ALERT — IEC 60945 alarm window active; audible/visual annunciation
        // Linked: BPS-REQ-003 (AlarmResponseRequirement)
        state ALERT;

        // FAILOVER_ACTIVE — Pump A unavailable; Pump B handling full discharge load
        // Linked: BPS-REQ-006 (FailoverSwitchTimingRequirement), SR-004
        state FAILOVER_ACTIVE;

        // CRITICAL_FAULT — controller or dual-pump failure; SOLAS emergency response
        // Linked: FM-C-001 (RPN=140); manual intervention mandatory
        state CRITICAL_FAULT;

        // Startup
        entry;
        then STANDBY;

        // STANDBY → PUMPING: water level crosses trigger threshold
        // Sub-state: controller transitions MONITORING → PUMP_A_ACTIVE
        // guard: sys.sensor.waterLevel >= sys.controller.triggerLevel_m
        transition STANDBY_to_PUMPING first STANDBY then PUMPING;

        // PUMPING → ALERT: alarm condition detected by controller
        // Sub-state: controller transitions PUMP_A_ACTIVE → ALARM_TRIGGERED
        // guard: sys.alarm.isActive == true
        transition PUMPING_to_ALERT first PUMPING then ALERT;

        // PUMPING → FAILOVER_ACTIVE: Pump A fault detected
        // Sub-state: controller transitions PUMP_A_ACTIVE → FAILOVER
        // guard: sys.pumpA.flowRate == 0.0
        transition PUMPING_to_FAILOVER_ACTIVE first PUMPING then FAILOVER_ACTIVE;

        // PUMPING → CRITICAL_FAULT: controller hang (FM-C-001)
        // Sub-state: controller transitions PUMP_A_ACTIVE → FAULT
        // guard: sys.controller.responseTime_s > 5.0
        transition PUMPING_to_CRITICAL_FAULT first PUMPING then CRITICAL_FAULT;

        // PUMPING → STANDBY: dewatering complete
        // Sub-state: controller transitions PUMP_A_ACTIVE or DUAL_PUMP_ACTIVE → MONITORING
        // guard: sys.sensor.waterLevel < sys.controller.triggerLevel_m
        transition PUMPING_to_STANDBY first PUMPING then STANDBY;

        // FAILOVER_ACTIVE → PUMPING: Pump B reaches nominal flow (handoff complete)
        // Sub-state: controller transitions FAILOVER → DUAL_PUMP_ACTIVE
        // guard: sys.pumpB.flowRate > 0.0
        transition FAILOVER_ACTIVE_to_PUMPING first FAILOVER_ACTIVE then PUMPING;

        // ALERT → STANDBY: operator acknowledges alarm via HMI
        // Sub-state: controller transitions ALARM_TRIGGERED → MONITORING
        // guard: sys.ui.overrideActive == true
        transition ALERT_to_STANDBY first ALERT then STANDBY;

        // CRITICAL_FAULT → STANDBY: operator hardware reset
        // Sub-state: controller transitions FAULT → IDLE
        // guard: sys.ui.overrideActive == true (hardware reset)
        transition CRITICAL_FAULT_to_STANDBY first CRITICAL_FAULT then STANDBY;
    }
} // package BilgePump_StateMachine
