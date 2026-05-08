// =============================================================================
// BilgePump::Library
// Layer: Library
// Purpose: Pure definitions only — no part usages, no connections.
//          Every component in the bilge pump system is defined here as a
//          part def with typed ports and attributes. Architecture, Requirements,
//          and Analysis layers import this package and never re-define types.
//
// External engineering tool context (hypothetical integrations):
//   - Sensor calibration DB  → provides waterLevel range and accuracy specs
//   - Simulink/Stateflow     → provides PumpController logic model
//   - IEC 61850 power bus    → provides PowerSupply nominal voltage profile
//   - CFD simulation tool    → provides BilgePumpA/B flow rate & efficiency curves
//   - CAD (CATIA/SolidWorks) → provides physical envelope / strainer sizing
//   - P&ID tool              → provides DischargeLine pipe loss coefficients
//   - IEC 60945              → provides AlarmSystem activation delay standards
//   - HMI design tool        → provides OperatorInterface display/override spec
// =============================================================================

package 'BilgePump::Library' {

    // -------------------------------------------------------------------------
    // Attribute Definitions
    // -------------------------------------------------------------------------

    // Represents a water level measurement in metres above bilge floor.
    // SOURCE: sensor datasheet / calibration lab; range typically 0.0–1.0 m
    attribute def WaterLevelAttr { attribute waterLevel : Real; }

    // Pump operational flow rate in cubic metres per second.
    // SOURCE: CFD simulation tool (pump curve export, e.g. OpenFOAM or ANSYS Fluent)
    attribute def FlowRateAttr { attribute flowRate : Real; }

    // Hydraulic efficiency factor 0.0–1.0 (dimensionless).
    // SOURCE: CFD simulation; vendor pump test certificate
    attribute def EfficiencyAttr { attribute efficiency : Real; }

    // Pipe friction / loss factor (Darcy-Weisbach λ), dimensionless.
    // SOURCE: P&ID tool; manual hydraulic calculation per ISO 4185
    attribute def PipeLossAttr { attribute pipeLossFactor : Real; }

    // Alarm activation delay in seconds.
    // SOURCE: IEC 60945 §4.3 — must be ≤ 2.0 s for Class A alarms
    attribute def AlarmDelayAttr { attribute activationDelay_s : Real; }

    // -------------------------------------------------------------------------
    // Port Definitions
    // These represent typed signal / flow interfaces between components.
    // Conjugate ports (prefixed ~) are the receiving ends of each interface.
    // -------------------------------------------------------------------------

    // --- Level signal: Sensor → Controller ---
    // Carries the raw water-level measurement as a scalar.
    // In a real vessel integration, this maps to a 4–20 mA analog loop
    // or an NMEA 2000 PGN signal from the vessel sensor bus. 
    port def LevelSignalPort {
        attribute waterLevel : Real;
    }

    // --- Pump control command: Controller → Pump ---
    // Carries a start/stop command string (stub; full model would use enum def).
    // SOURCE (out): PumpController firmware model (Simulink discrete-event output)
    // DEST (in):    Pump motor drive / VFD firmware
    port def PumpControlPort {
        attribute command : String;  // "START" | "STOP" | "FAULT"
    }

    // --- Electrical power: PowerSupply → Pump ---
    // Carries bus voltage and a flag indicating whether emergency bus is active.
    // SOURCE: Vessel power management system (IEC 61850 GOOSE message)
    // DEST:   Pump motor drive; also feeds into load-shedding controller
    port def PowerPort {
        attribute voltage       : Real;
        attribute isEmergency   : Boolean;
    }

    // --- Fluid flow: Pump → DischargeLine ---
    // Carries volumetric flow rate through the discharge piping.
    // SOURCE: pump impeller speed sensor (tachometer) or flow meter (NMEA)
    // DEST:   Discharge overboard; MARPOL environmental compliance monitor
    port def FluidFlowPort {
        attribute flowRate : Real;
    }

    // --- System status: Controller ↔ OperatorInterface ---
    // Bidirectional; status string is a simplified representation.
    // In a real system: encoded as a CAN/NMEA 2000 status word or Modbus register.
    // DEST: Voyage Data Recorder (VDR), bridge BNWAS display
    port def StatusPort {
        attribute status : String;  // "NORMAL" | "PUMPING" | "FAULT" | "OVERRIDE"
    }

    // --- Alarm trigger: Controller → AlarmSystem ---
    // Boolean flag; high = alarm condition active.
    // SOURCE: PumpController threshold comparator
    // DEST:   Audible/visual alarm unit; VDR alarm log; bridge alarm panel (IEC 60945)
    port def AlarmPort {
        attribute alarmActive : Boolean;
    }

    // --- Manual override: OperatorInterface → Controller ---
    // Allows bridge crew to force-start/stop pumps regardless of automation state.
    // SOURCE: HMI panel (physical button or touchscreen)
    // DEST:   PumpController override input register
    port def OverridePort {
        attribute override : Boolean;
    }

    // =========================================================================
    // Part Definitions — Library Layer
    // Each part def declares its ports and attributes.
    // No values are assigned here; values are bound in Architecture or Analysis.
    // =========================================================================

    // -------------------------------------------------------------------------
    // BilgeWaterSensor
    // Measures water accumulation depth in the bilge.
    // -------------------------------------------------------------------------
    // ENGINEERING INPUTS:
    //   ← Sensor calibration certificate (accuracy class, temperature range)
    //   ← Classification society approval cert (DNV/Lloyd's type approval)
    // ENGINEERING OUTPUTS:
    //   → PumpController (level signal, this model)
    //   → SCADA / vessel management system (OPC-UA data point)
    //   → NMEA 2000 vessel data bus (PGN 127501 binary switch bank)
    part def BilgeWaterSensor {
        // Output: water level to controller
        port levelOut : LevelSignalPort;

        // Current measured water level in metres
        attribute waterLevel    : Real;
        // Sensor accuracy class (e.g., 0.01 m resolution)
        attribute accuracy_m    : Real;
    }

    // -------------------------------------------------------------------------
    // PumpController
    // Central control logic and diagnostics unit.
    // In practice, this is typically a PLC or dedicated bilge controller board.
    // -------------------------------------------------------------------------
    // ENGINEERING INPUTS:
    //   ← BilgeWaterSensor level signal (this model)
    //   ← OperatorInterface override command (this model)
    //   ← Simulink/Stateflow control logic model (firmware code generation)
    //   ← Classification society alarm logic spec (IEC 60945, DNV Rules Pt.4 Ch.6)
    // ENGINEERING OUTPUTS:
    //   → BilgePumpA / BilgePumpB start/stop commands (this model)
    //   → AlarmSystem trigger (this model)
    //   → OperatorInterface status (this model)
    //   → CMMS fault logger (maintenance work order generation)
    //   → SCADA historian (time-series event log)
    part def PumpController {
        // Input: water level from sensor
        port levelIn        : ~LevelSignalPort;
        // Output: pump A start/stop command
        port pumpAControl   : PumpControlPort;
        // Output: pump B start/stop command
        port pumpBControl   : PumpControlPort;
        // Output: system status to operator interface
        port statusOut      : StatusPort;
        // Output: alarm trigger to alarm system
        port alarmOut       : AlarmPort;
        // Input: manual override from operator
        port overrideIn     : ~OverridePort;

        // Time from threshold breach to pump start command (seconds)
        attribute responseTime_s    : Real;
        // Water level threshold at which pumping is triggered (metres)
        attribute triggerLevel_m    : Real;
    }

    // -------------------------------------------------------------------------
    // PowerSupply
    // Dual-source supply unit: main bus + emergency/battery backup.
    // Must maintain pump operation during main bus failure per SOLAS II-1.
    // -------------------------------------------------------------------------
    // ENGINEERING INPUTS:
    //   ← Vessel power management system (IEC 61850 GOOSE — bus availability)
    //   ← Electrical load analysis (power budget spreadsheet / ETAP model)
    //   ← Emergency generator sizing calculation
    // ENGINEERING OUTPUTS:
    //   → BilgePumpA / BilgePumpB power rails (this model)
    //   → Load shedding controller (IEC 61850 — priority group assignment)
    //   → Vessel alarm panel (power failure indication)
    part def PowerSupply {
        // Output: power to pump A
        port powerOutA      : PowerPort;
        // Output: power to pump B
        port powerOutB      : PowerPort;

        // Nominal DC/AC bus voltage in volts
        attribute nominalVoltage    : Real;
        // True when emergency bus has taken over
        attribute redundancyActive  : Boolean;
    }

    // -------------------------------------------------------------------------
    // BilgePumpA  (primary pump)
    // Centrifugal or diaphragm pump for main bilge drainage.
    // -------------------------------------------------------------------------
    // ENGINEERING INPUTS:
    //   ← CFD simulation tool: pump characteristic curve (H-Q curve, ANSYS or OpenFOAM)
    //   ← CAD model: physical envelope / mounting interface (CATIA/SolidWorks STEP file)
    //   ← Vendor test certificate: NPSH, efficiency at rated speed
    // ENGINEERING OUTPUTS:
    //   → DischargeLine flow (this model)
    //   → CMMS run-hour counter (predictive maintenance trigger at 250 h)
    //   → SCADA: flow rate telemetry (OPC-UA node)
    part def BilgePumpA {
        // Input: power from supply
        port powerIn        : ~PowerPort;
        // Input: start/stop command from controller
        port controlIn      : ~PumpControlPort;
        // Output: fluid flow to discharge line
        port flowOut        : FluidFlowPort;

        // Volumetric flow rate at rated speed (m³/s)
        attribute flowRate      : Real;
        // Hydraulic efficiency at operating point (0.0–1.0)
        attribute efficiency    : Real;
        // Cumulative run hours (sourced from CMMS at model instantiation)
        attribute runHours      : Real;
    }

    // -------------------------------------------------------------------------
    // BilgePumpB  (redundant pump)
    // Identical capability to Pump A; activates on A failure or override.
    // Classification rules (DNV Pt.4 Ch.6) require independent power feed.
    // -------------------------------------------------------------------------
    // ENGINEERING INPUTS: same as BilgePumpA
    // ENGINEERING OUTPUTS: same as BilgePumpA
    part def BilgePumpB {
        port powerIn        : ~PowerPort;
        port controlIn      : ~PumpControlPort;
        port flowOut        : FluidFlowPort;

        attribute flowRate      : Real;
        attribute efficiency    : Real;
        attribute runHours      : Real;
        // Flag confirming this unit is the designated redundant pump
        attribute isRedundant   : Boolean;
    }

    // -------------------------------------------------------------------------
    // DischargeLine
    // Overboard discharge piping including strainer basket and check valves.
    // -------------------------------------------------------------------------
    // ENGINEERING INPUTS:
    //   ← P&ID drawing tool: pipe routing, valve schedule (SmartPlant P&ID)
    //   ← CAD: strainer basket sizing, pipe bore (CATIA Piping & Tubing)
    //   ← Hydraulic calculation: Darcy-Weisbach friction factor per ISO 4185
    // ENGINEERING OUTPUTS:
    //   → Overboard discharge (physical)
    //   → MARPOL environmental compliance monitor (discharge rate < 15 ppm oily water)
    //   → Port state control inspection record (oil content meter reading)
    part def DischargeLine {
        // Input: flow from pump A
        port flowInA        : ~FluidFlowPort;
        // Input: flow from pump B
        port flowInB        : ~FluidFlowPort;

        // Darcy-Weisbach pipe friction/loss factor (dimensionless)
        attribute pipeLossFactor    : Real;
        // Strainer free-flow area (m²); sized from CAD
        attribute strainerArea_m2   : Real;
    }

    // -------------------------------------------------------------------------
    // AlarmSystem
    // Audible and visual alarm unit installed at the pump control station
    // and mirrored to the bridge alarm panel per IEC 60945 §4.3.
    // -------------------------------------------------------------------------
    // ENGINEERING INPUTS:
    //   ← PumpController alarm trigger (this model)
    //   ← IEC 60945 alarm standard: activation delay ≤ 2.0 s, sound level ≥ 75 dB
    //   ← Classification society alarm table (DNV Rules Pt.4 Ch.6 Table 1)
    // ENGINEERING OUTPUTS:
    //   → OperatorInterface notification (this model)
    //   → Bridge BNWAS (bridge navigational watch alarm system)
    //   → Voyage Data Recorder (VDR) alarm event log
    //   → Shore-based fleet monitoring system (satellite AIS/IoT gateway)
    part def AlarmSystem {
        // Input: alarm condition from controller
        port alarmIn        : ~AlarmPort;
        // Output: notification to operator interface
        port notifyOut      : AlarmPort;

        // Delay from trigger to annunciation in seconds (must be ≤ 2.0)
        attribute activationDelay_s : Real;
        // True when alarm is currently sounding
        attribute isActive          : Boolean;
    }

    // -------------------------------------------------------------------------
    // OperatorInterface
    // Local operator panel providing system status readout and manual override.
    // Typically a touchscreen HMI or physical panel with indicator lights.
    // -------------------------------------------------------------------------
    // ENGINEERING INPUTS:
    //   ← PumpController status (this model)
    //   ← AlarmSystem notification (this model)
    //   ← HMI design tool: screen layout, button mapping (Wonderware / FactoryTalk)
    //   ← Human factors / ergonomics standard (ISO 11064 control room design)
    // ENGINEERING OUTPUTS:
    //   → PumpController override command (this model)
    //   → Voyage Data Recorder (VDR): operator action log
    //   → Vessel management system: maintenance event annotation
    part def OperatorInterface {
        // Input: status from controller
        port statusIn       : ~StatusPort;
        // Input: notification from alarm system
        port notifyIn       : ~AlarmPort;
        // Output: manual override command to controller
        port overrideOut    : OverridePort;

        // True when the operator has asserted a manual override
        attribute overrideActive    : Boolean;
    }

}
// CI proof-of-concept trigger — Fri May  8 08:15:31 CEST 2026
