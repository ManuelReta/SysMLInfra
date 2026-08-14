package WellMonitoring_Architecture {
    private import ScalarValues::*;
    public import WellMonitoring_Library::*;

    part wellMonitoring : WellMonitoringSubsystemContract {
        attribute :>> operatingIndicationProvided = true;
        attribute :>> wellCapacity_m3 = 0.18;
        attribute :>> machineryDrainLedToMudBox = true;
        attribute :>> mudBoxStraightTail = true;
        attribute :>> mudBoxInspectable = true;
        attribute :>> cargoStrumFitted = true;
        attribute :>> cargoStrumInspectable = true;
        attribute :>> fittingsAccessible = true;
        attribute :>> directSuctionStrumFitted = false;
        attribute :>> emergencySuctionStrumFitted = false;
        attribute :>> fittingsBelowFloor = true;
        attribute :>> floorPlateRemovable = true;
        attribute :>> fittingNameplateProvided = true;
        attribute :>> requiredDrainageCapacity_m3h = 90.0;
        attribute :>> outletAvailable = true;
        attribute :>> operatorFeedbackAvailable = true;
    }
}