package PipingNetwork_Requirements {
    public import PipingNetwork_Library::*;

    // Source: DNV-RU-SHIP Pt.4 Ch.6 Sec.4, supplied extraction JSON.
    requirement def DNV_8_3_StopValves {
        subject sys : PipingNetworkSubsystemContract;
        require constraint { sys.stopValveCount >= sys.pumpConnectionCount }
    }
    requirement def DNV_8_3_NonReturnValveLimit {
        subject sys : PipingNetworkSubsystemContract;
        require constraint { sys.maxNonReturnValvesPerSuction <= 2 }
    }
    requirement def DNV_8_4_BranchDiameter {
        subject sys : PipingNetworkSubsystemContract;
        require constraint { sys.branchDiameter_mm >= 50.0 and sys.branchDiameter_mm <= 100.0 }
    }
    requirement def DNV_8_4_DistributionArea {
        subject sys : PipingNetworkSubsystemContract;
        require constraint { sys.distributionPipeArea_m2 >= sys.twoLargestBranchArea_m2 }
    }
    requirement def DNV_8_5_TankTransitProtection {
        subject sys : PipingNetworkSubsystemContract;
        require constraint { sys.tankTransitProtected }
    }
    requirement def DNV_8_7_StrumOpenArea {
        subject sys : PipingNetworkSubsystemContract;
        require constraint { sys.strumOpenArea_m2 >= 2.0 * sys.suctionPipeArea_m2 }
    }
    requirement def DNV_8_7_FullFlowClearance {
        subject sys : PipingNetworkSubsystemContract;
        require constraint { sys.fullFlowClearance }
    }

    requirement def DNV_8_4_MainPipeArea {
        subject sys : PipingNetworkSubsystemContract;
        require constraint { sys.mainPipeArea_mm2 >= 2.0 * sys.engineBranchArea_mm2 }
    }

    requirement def DNV_8_4_EmergencySuctionDiameter {
        subject sys : PipingNetworkSubsystemContract;
        require constraint {
            not sys.emergencySuctionFitted or
            (sys.emergencySuctionDiameter_mm == sys.pumpSuctionDiameter_mm and
             sys.emergencySuctionDiameter_mm <= 400.0)
        }
    }

    requirement def DNV_8_5_CargoPipeProtection {
        subject sys : PipingNetworkSubsystemContract;
        require constraint {
            not sys.cargoHoldPipesPresent or
            (sys.cargoPipeMechanicallyProtected and sys.cargoPipeMaterialSuitable and
             sys.cargoPipeCorrosionProtected)
        }
    }
}