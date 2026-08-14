package WellMonitoring_Library {
    private import ScalarValues::*;

    part def WellMonitoringSubsystemContract {
        attribute operatingIndicationProvided : Boolean;
        attribute wellCapacity_m3 : Real;
        attribute machineryDrainLedToMudBox : Boolean;
        attribute mudBoxStraightTail : Boolean;
        attribute mudBoxInspectable : Boolean;
        attribute cargoStrumFitted : Boolean;
        attribute cargoStrumInspectable : Boolean;
        attribute fittingsAccessible : Boolean;
        attribute directSuctionStrumFitted : Boolean;
        attribute emergencySuctionStrumFitted : Boolean;
        attribute fittingsBelowFloor : Boolean;
        attribute floorPlateRemovable : Boolean;
        attribute fittingNameplateProvided : Boolean;

        // Public composition contract.
        attribute requiredDrainageCapacity_m3h : Real;
        attribute outletAvailable : Boolean;
        attribute operatorFeedbackAvailable : Boolean;
    }
}