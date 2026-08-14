package PipingNetwork_Architecture {
    private import ScalarValues::*;
    public import PipingNetwork_Library::*;

    part pipingNetwork : PipingNetworkSubsystemContract {
        attribute :>> pumpConnectionCount = 2;
        attribute :>> stopValveCount = 2;
        attribute :>> maxNonReturnValvesPerSuction = 2;
        attribute :>> branchDiameter_mm = 75.0;
        attribute :>> distributionPipeArea_m2 = 0.012;
        attribute :>> twoLargestBranchArea_m2 = 0.010;
        attribute :>> tankTransitProtected = true;
        attribute :>> strumOpenArea_m2 = 0.004;
        attribute :>> suctionPipeArea_m2 = 0.0018;
        attribute :>> fullFlowClearance = true;
        attribute :>> mainPipeDiameter_mm = 100.0;
        attribute :>> engineBranchDiameter_mm = 50.0;
        attribute :>> mainPipeArea_mm2 = 0.785398 * mainPipeDiameter_mm * mainPipeDiameter_mm;
        attribute :>> engineBranchArea_mm2 =
            0.785398 * engineBranchDiameter_mm * engineBranchDiameter_mm;
        attribute :>> emergencySuctionFitted = true;
        attribute :>> emergencySuctionDiameter_mm = 150.0;
        attribute :>> pumpSuctionDiameter_mm = 150.0;
        attribute :>> cargoHoldPipesPresent = true;
        attribute :>> cargoPipeMechanicallyProtected = true;
        attribute :>> cargoPipeMaterialSuitable = true;
        attribute :>> cargoPipeCorrosionProtected = true;
        attribute :>> acceptedPumpCount = 2;
        attribute :>> supportedCapacity_m3h = 110.0;
        attribute :>> flowPathAvailable = true;
    }
}