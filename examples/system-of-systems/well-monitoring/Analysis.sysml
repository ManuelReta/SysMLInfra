package WellMonitoring_Analysis {
    private import ScalarValues::*;
    public import WellMonitoring_Architecture::*;
    public import WellMonitoring_Requirements::*;

    part wellMonitoringVerification : WellMonitoringSubsystemContract {
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

        attribute DNV_WM_045_indication : Boolean = operatingIndicationProvided;
        attribute DNV_WM_046_capacity : Boolean = wellCapacity_m3 >= 0.15;
        attribute DNV_WM_047_mudBoxRouting : Boolean = machineryDrainLedToMudBox;
        attribute DNV_WM_048_mudBoxArrangement : Boolean = mudBoxStraightTail and mudBoxInspectable;
        attribute DNV_WM_050_cargoStrum : Boolean = cargoStrumFitted;
        attribute DNV_WM_050_cargoStrumAccess : Boolean = cargoStrumInspectable;
        attribute DNV_WM_054_fittingAccess : Boolean = fittingsAccessible;
        attribute DNV_WM_049_noDirectStrums : Boolean =
            not directSuctionStrumFitted and not emergencySuctionStrumFitted;
        attribute DNV_WM_055_belowFloorAccess : Boolean =
            not fittingsBelowFloor or (floorPlateRemovable and fittingNameplateProvided);
    }
}