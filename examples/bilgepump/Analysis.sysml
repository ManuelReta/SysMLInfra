// =============================================================================
// BilgePump::Analysis
// Layer: Analysis
// Purpose: Physics constraint definitions and the verification cases (the
// "test runner") that evaluate every system requirement.
//
// Import chain: Analysis imports Library, Architecture, and Requirements.
// Library <- Architecture <- Requirements <- Analysis   (no cycles)
//
// HOW THE VERIFICATION CASES WORK (kernel-evaluable form)
// -------------------------------------------------------
// The SysML v2 Pilot kernel does not execute `assert requirement` statements,
// and it cannot override an attribute value that Architecture already binds
// (e.g. `attribute waterLevel = 0.15;`).  To obtain machine-checkable PASS/FAIL
// verdicts that the pipeline can capture with `%eval`, each requirement is
// re-expressed here as a computed Boolean attribute on a concrete subject:
//
// part bpVerification : BilgePumpSystem {
// attribute BPS_REQ_001_waterLevel : Boolean = sensor.waterLevel <= 0.3;
// }
//
// The subject `bpVerification` is a usage of BilgePumpSystem, so it INHERITS
// every nominal attribute value declared in Architecture.sysml.  Attributes
// that Architecture leaves unbound (controller.failoverTime_s, sensor.accuracy_m)
// are supplied here via nested redefinition `attribute :>> name = value;`.
//
// Each Boolean is queryable headlessly:
// %eval BilgePump_Analysis::bpVerification.BPS_REQ_001_waterLevel
// -> LiteralBoolean true     (SATISFIED)
// The publish pipeline emits one %eval per Boolean and records the verdict in
// the `sysml_assertions` database table (see materialize_sysml_values.py).
//
// Negative (fault) verdicts live in FMEA.sysml; parametric-sweep verdicts in
// UQ.sysml.  The two physics constraint defs below are reused by both layers.
// =============================================================================

package BilgePump_Analysis {
    private import ScalarValues::*;
    public import BilgePump_Library::*;
    public import BilgePump_Architecture::*;
    public import BilgePump_Requirements::*;

    // =========================================================================
    // StateTransitionTimingPhysics  -- state machine transition timing budget
    //
    // Models the timing chain from sensor threshold crossing to pump activation
    // command (Simulink discrete-event model SIM-CTRL-001 §3.1):
    // totalTime_s = samplingLatency_s + processingTime_s + commandLatency_s
    // and asserts totalTime_s <= maxResponseTime_s.
    //
    // Linked requirement: BPS-REQ-005 (ControllerActivationTimingRequirement)
    // Linked state:       MONITORING -> PUMP_A_ACTIVE transition (StateMachine.sysml)
    // =========================================================================
    constraint def StateTransitionTimingPhysics {
        attribute samplingLatency_s : Real; // Sensor poll interval (s)
        attribute processingTime_s : Real; // Firmware processing time (s)
        attribute commandLatency_s : Real; // Output command transmission latency (s)
        attribute maxResponseTime_s : Real; // Maximum allowed response time (s) [BPS-REQ-005]
        attribute totalTime_s : Real; // Computed total response time

        assert constraint {
            totalTime_s == samplingLatency_s + processingTime_s + commandLatency_s and
            totalTime_s <= maxResponseTime_s
        }
    }

    // =========================================================================
    // PumpFlowPhysics  -- net discharge capacity physics constraint
    //
    // Q_net = (Q_A + Q_B) * eta * (1 - lambda)   and   Q_net >= Q_inflow
    //
    // EXTERNAL TOOL BINDINGS (hypothetical):
    // <- CFD (ANSYS Fluent / OpenFOAM): hydraulic efficiency eta
    // <- P&ID hydraulic calc (Caesar II / PIPESIM): pipe loss factor lambda
    // <- Maxsurf / NAPA stability module: design inflow Q_inflow
    // =========================================================================
    constraint def PumpFlowPhysics {
        attribute flowRateA : Real; // Pump A flow rate (m^3/s)
        attribute flowRateB : Real; // Pump B flow rate (m^3/s)
        attribute efficiency : Real; // Hydraulic efficiency eta (0.0-1.0)
        attribute pipeLossFactor : Real; // Pipe friction factor lambda (0.0-1.0)
        attribute designInflow : Real; // Required minimum discharge (m^3/s)
        attribute netFlow : Real; // Computed net effective discharge

        assert constraint {
            netFlow == (flowRateA + flowRateB) * efficiency * (1.0 - pipeLossFactor) and
            netFlow >= designInflow
        }
    }

    // =========================================================================
    // bpVerification  -- functional verification case (POSITIVE / nominal)
    //
    // Subject inherits all nominal attribute values from Architecture.sysml.
    // Each requirement is encoded as a computed Boolean (SATISFIED == true).
    //
    // Nominal values (from Architecture): sensor.waterLevel=0.15,
    // pumpA/B.flowRate=0.025, efficiency=0.82, discharge.pipeLossFactor=0.05,
    // alarm.activationDelay_s=0.5, pumpB.isRedundant=true.
    // netFlow = (0.025+0.025) * 0.82 * (1-0.05) = 0.03895 m^3/s >= 0.030  OK
    // =========================================================================
    part bpVerification : BilgePumpSystem {
        // Design inflow from damage stability analysis (Maxsurf / NAPA export)
        attribute designInflow : Real = 0.030;
        // Net effective discharge (PumpFlowPhysics evaluated on nominal values)
        attribute netFlow : Real =
            (pumpA.flowRate + pumpB.flowRate) * pumpA.efficiency * (1.0 - discharge.pipeLossFactor);

        // TEST BPS-REQ-001: water level must not exceed 0.3 m  [MARPOL 73/78]
        attribute BPS_REQ_001_waterLevel : Boolean = sensor.waterLevel <= 0.3;
        // TEST BPS-REQ-002: Pump B must be the designated redundant unit  [DNV Pt.4 Ch.6]
        attribute BPS_REQ_002_redundancy : Boolean = pumpB.isRedundant == true;
        // TEST BPS-REQ-003: alarm activation within 2.0 s  [IEC 60945 §4.3]
        attribute BPS_REQ_003_alarm : Boolean = alarm.activationDelay_s <= 2.0;
        // TEST BPS-REQ-004: combined discharge meets design inflow  [SOLAS II-1 Reg.35]
        attribute BPS_REQ_004_discharge : Boolean = pumpA.flowRate + pumpB.flowRate >= designInflow;
        // Physics: net effective discharge meets design inflow (efficiency + losses)
        attribute physicsCheck : Boolean = netFlow >= designInflow;
    }

    // =========================================================================
    // bpTimingVerification  -- timing verification case (POSITIVE / nominal)
    //
    // Verifies the two timing requirements (BPS-REQ-005, BPS-REQ-006) and
    // re-checks alarm timing (BPS-REQ-003) in the same harness.
    // failoverTime_s is unbound in Architecture, so it is supplied here.
    //
    // Nominal: responseTime_s=1.0 (SIM-CTRL-001 §3.1), failoverTime_s=0.8
    // (SIM-CTRL-001 §3.2), alarm.activationDelay_s=0.5.
    // =========================================================================
    part bpTimingVerification : BilgePumpSystem {
        // Failover time not bound in Architecture -> supply the nominal value
        part :>> controller {
            attribute :>> failoverTime_s = 0.8; // SIM-CTRL-001 §3.2 normal failover
        }

        // Timing budget decomposition (StateTransitionTimingPhysics, nominal)
        // 0.1 s sampling + 0.9 s processing + 0.0 s command = 1.0 s <= 5.0 s
        attribute timingBudgetTotal_s : Real = 0.1 + 0.9 + 0.0;
        attribute timingBudgetOk : Boolean = timingBudgetTotal_s <= 5.0;

        // TEST BPS-REQ-005: controller activation within 5.0 s of threshold crossing
        attribute BPS_REQ_005_activation : Boolean = controller.responseTime_s <= 5.0;
        // TEST BPS-REQ-006: failover switch within 3.0 s of Pump A fault
        attribute BPS_REQ_006_failover : Boolean = controller.failoverTime_s <= 3.0;
        // TEST BPS-REQ-003 (re-asserted in timing context): alarm within 2.0 s
        attribute BPS_REQ_003_alarmTiming : Boolean = alarm.activationDelay_s <= 2.0;
    }

    // =========================================================================
    // bpFaultToleranceVerification  -- fault-tolerance verification (POSITIVE)
    //
    // Verifies the FT-* requirements (BPS-FT-001..004) and OOR-001 that
    // decompose the abstract property "the system shall remain safe under all
    // conditions within its operating envelope".
    //
    // sensor.accuracy_m (unbound in Architecture) supplied here = 0.03
    // (±3 cm sensor class, IEC 60770-1).  inflowRate_m3s=0.020 and
    // criticalLevel_m=0.5 are inherited from Architecture (BilgePumpSystem).
    // failoverTime_s supplied for completeness.
    //
    // FT-001: 0.15 + 0.03 = 0.18 <= 0.30  OK
    // FT-002: (0.025*0.82 + 0.025*0.82) * (1-0.05) = 0.03895 >= 0.030  OK
    // FT-003: 0.25 + 0.03 = 0.28 <= 0.30  OK (narrow margin)
    // FT-004: (1.0 + 0.5) * 0.020 = 0.030 <= 0.5 - 0.15 = 0.35  OK
    // OOR-001: overrideActive(false) == false  OR  alarm.isActive  -> true  OK
    // =========================================================================
    part bpFaultToleranceVerification : BilgePumpSystem {
        // Sensor accuracy not bound in Architecture -> supply the class value
        part :>> sensor {
            attribute :>> accuracy_m = 0.03; // ±3 cm (IEC 60770-1 accuracy class)
        }
        part :>> controller {
            attribute :>> failoverTime_s = 0.8;
        }

        attribute designInflow : Real = 0.030;
        attribute netFlow : Real =
            (pumpA.flowRate * pumpA.efficiency + pumpB.flowRate * pumpB.efficiency) *
            (1.0 - discharge.pipeLossFactor);

        // TEST FT-001: reported level + sensor accuracy stays within MARPOL limit
        attribute BPS_FT_001_sensorAccuracy : Boolean =
            sensor.waterLevel + sensor.accuracy_m <= 0.3;
        // TEST FT-002: net effective discharge (per-pump efficiency) >= design inflow
        attribute BPS_FT_002_effDischarge : Boolean = netFlow >= designInflow;
        // TEST FT-003: trigger level + sensor accuracy stays within MARPOL limit
        attribute BPS_FT_003_triggerAccuracy : Boolean =
            controller.triggerLevel_m + sensor.accuracy_m <= 0.3;
        // TEST FT-004: timing chain feasible vs physical overflow window
        attribute BPS_FT_004_responseWindow : Boolean =
            (controller.responseTime_s + alarm.activationDelay_s) * inflowRate_m3s <=
            criticalLevel_m - sensor.waterLevel;
        // TEST OOR-001: override only after alarm active (Z3 Level-6 gap closure)
        attribute BPS_OOR_001_overrideOrdering : Boolean =
            ui.overrideActive == false or alarm.isActive == true;
    }

    // =========================================================================
    // V-MODEL TRACEABILITY (documentation)
    //
    // SysML v2 satisfy/verify relationships complete the V-model, but the Pilot
    // kernel in use rejects the `satisfy <RequirementDef> by <Type>;` and
    // `verify <RequirementDef> by <AnalysisDef>;` forms (they require a
    // requirement USAGE and a feature, not definitions/types).  The traceability
    // is therefore recorded here as documentation; the executable evidence is
    // the computed-Boolean verdicts above (positive), in FMEA.sysml (negative),
    // and in UQ.sysml (parametric sweep).
    //
    // satisfy WaterLevelRequirement                 by BilgeWaterSensor
    // satisfy PumpRedundancyRequirement             by BilgePumpB
    // satisfy AlarmResponseRequirement              by AlarmSystem
    // satisfy DischargeCapacityRequirement          by BilgePumpA, BilgePumpB, DischargeLine
    // satisfy EffectiveDischargeCapacityRequirement by BilgePumpA, BilgePumpB, DischargeLine
    // satisfy ControllerActivationTimingRequirement by PumpController
    // satisfy FailoverSwitchTimingRequirement       by PumpController
    // satisfy SensorAccuracyBoundRequirement        by BilgeWaterSensor
    // satisfy TriggerLevelAccuracyRequirement       by BilgeWaterSensor, PumpController
    // satisfy EndToEndResponseRequirement           by PumpController, AlarmSystem
    // satisfy OverrideOrderingRequirement           by PumpController, AlarmSystem, OperatorInterface
    //
    // verify  WaterLevelRequirement                 by bpVerification
    // verify  PumpRedundancyRequirement             by bpVerification
    // verify  AlarmResponseRequirement              by bpVerification, bpTimingVerification
    // verify  DischargeCapacityRequirement          by bpVerification
    // verify  EffectiveDischargeCapacityRequirement by bpFaultToleranceVerification
    // verify  ControllerActivationTimingRequirement by bpTimingVerification
    // verify  FailoverSwitchTimingRequirement       by bpTimingVerification
    // verify  SensorAccuracyBoundRequirement        by bpFaultToleranceVerification
    // verify  TriggerLevelAccuracyRequirement       by bpFaultToleranceVerification
    // verify  EndToEndResponseRequirement           by bpFaultToleranceVerification
    // verify  OverrideOrderingRequirement           by bpTimingVerification
    // =========================================================================
} // package BilgePump_Analysis
