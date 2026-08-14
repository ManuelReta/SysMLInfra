package PipingNetwork_Analysis {
    private import ScalarValues::*;
    public import PipingNetwork_Architecture::*;
    public import PipingNetwork_Requirements::*;

    part pipingVerification : PipingNetworkSubsystemContract {
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

        attribute DNV_PN_019_stopValves : Boolean = stopValveCount >= pumpConnectionCount;
        attribute DNV_PN_023_nonReturnValves : Boolean = maxNonReturnValvesPerSuction <= 2;
        attribute DNV_PN_032_branchDiameter : Boolean = branchDiameter_mm >= 50.0 and branchDiameter_mm <= 100.0;
        attribute DNV_PN_037_distributionArea : Boolean = distributionPipeArea_m2 >= twoLargestBranchArea_m2;
        attribute DNV_PN_040_tankProtection : Boolean = tankTransitProtected;
        attribute DNV_PN_051_strumArea : Boolean = strumOpenArea_m2 >= 2.0 * suctionPipeArea_m2;
        attribute DNV_PN_053_fullFlow : Boolean = fullFlowClearance;
        attribute DNV_PN_028_mainPipeArea : Boolean =
            mainPipeArea_mm2 >= 2.0 * engineBranchArea_mm2;
        attribute DNV_PN_035_emergencyDiameter : Boolean =
            not emergencySuctionFitted or
            (emergencySuctionDiameter_mm == pumpSuctionDiameter_mm and
             emergencySuctionDiameter_mm <= 400.0);
        attribute DNV_PN_044_cargoProtection : Boolean =
            not cargoHoldPipesPresent or
            (cargoPipeMechanicallyProtected and cargoPipeMaterialSuitable and
             cargoPipeCorrosionProtected);
    }
}