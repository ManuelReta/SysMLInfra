package VesselDrainageSoS_Analysis {
    private import ScalarValues::*;
    public import VesselDrainageSoS_Requirements::*;

    part sosVerification : VesselDrainageSoSContract {
        part :>> pumping {
            part :>> unitA {
                attribute :>> waterVelocity_mps = 2.2;
                attribute :>> capacity_m3h = 60.0;
                attribute :>> independentlyDriven = true;
                attribute :>> available = true;
                attribute :>> centrifugal = true;
                attribute :>> selfPriming = true;
                attribute :>> centralPrimingConnected = false;
                attribute :>> pressureLossCalculationApproved = true;
            }
            part :>> unitB {
                attribute :>> waterVelocity_mps = 2.1;
                attribute :>> capacity_m3h = 40.0;
                attribute :>> independentlyDriven = true;
                attribute :>> available = true;
                attribute :>> centrifugal = true;
                attribute :>> selfPriming = false;
                attribute :>> centralPrimingConnected = true;
                attribute :>> pressureLossCalculationApproved = true;
            }
            attribute :>> requiredCapacity_m3h = 90.0;
            attribute :>> deliveredCapacity_m3h = 100.0;
            attribute :>> operationalUnitCount = 2;
            attribute :>> simultaneousSuctionAvailable = true;
        }
        part :>> piping {
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
            attribute :>> mainPipeArea_mm2 = 7853.98;
            attribute :>> engineBranchArea_mm2 = 1963.495;
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
        part :>> monitoring {
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

        attribute SOS_001_capacity : Boolean =
            pumping.deliveredCapacity_m3h >= monitoring.requiredDrainageCapacity_m3h;
        attribute SOS_002_pipingCapacity : Boolean =
            piping.supportedCapacity_m3h >= pumping.deliveredCapacity_m3h;
        attribute SOS_003_connections : Boolean =
            piping.acceptedPumpCount >= pumping.operationalUnitCount;
        attribute SOS_004_endToEndPath : Boolean =
            monitoring.outletAvailable and piping.flowPathAvailable;
        attribute SOS_005_degradedOperation : Boolean =
            pumping.unitA.capacity_m3h >= 50.0 and monitoring.operatorFeedbackAvailable;
    }

    // Fault injection: an older piping contract accepts only 80 m3/h.
    part incompatibleComposition : VesselDrainageSoSContract {
        part :>> pumping {
            attribute :>> deliveredCapacity_m3h = 100.0;
        }
        part :>> piping {
            attribute :>> supportedCapacity_m3h = 80.0;
        }
        attribute SOS_002_rejectUndersizedPiping : Boolean =
            piping.supportedCapacity_m3h >= pumping.deliveredCapacity_m3h;
    }
}