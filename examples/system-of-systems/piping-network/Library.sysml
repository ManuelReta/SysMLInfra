package PipingNetwork_Library {
    private import ScalarValues::*;

    part def PipingNetworkSubsystemContract {
        attribute pumpConnectionCount : Integer;
        attribute stopValveCount : Integer;
        attribute maxNonReturnValvesPerSuction : Integer;
        attribute branchDiameter_mm : Real;
        attribute distributionPipeArea_m2 : Real;
        attribute twoLargestBranchArea_m2 : Real;
        attribute tankTransitProtected : Boolean;
        attribute strumOpenArea_m2 : Real;
        attribute suctionPipeArea_m2 : Real;
        attribute fullFlowClearance : Boolean;
        attribute mainPipeDiameter_mm : Real;
        attribute engineBranchDiameter_mm : Real;
        attribute mainPipeArea_mm2 : Real;
        attribute engineBranchArea_mm2 : Real;
        attribute emergencySuctionFitted : Boolean;
        attribute emergencySuctionDiameter_mm : Real;
        attribute pumpSuctionDiameter_mm : Real;
        attribute cargoHoldPipesPresent : Boolean;
        attribute cargoPipeMechanicallyProtected : Boolean;
        attribute cargoPipeMaterialSuitable : Boolean;
        attribute cargoPipeCorrosionProtected : Boolean;

        // Public composition contract. Internal topology stays private to this subsystem.
        attribute acceptedPumpCount : Integer;
        attribute supportedCapacity_m3h : Real;
        attribute flowPathAvailable : Boolean;
    }
}