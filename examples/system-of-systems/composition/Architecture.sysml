package VesselDrainageSoS_Architecture {
    private import ScalarValues::*;
    public import PumpingUnit_Library::*;
    public import PipingNetwork_Library::*;
    public import WellMonitoring_Library::*;

    part def VesselDrainageSoSContract {
        part pumping : PumpingUnitSubsystemContract;
        part piping : PipingNetworkSubsystemContract;
        part monitoring : WellMonitoringSubsystemContract;
    }
}