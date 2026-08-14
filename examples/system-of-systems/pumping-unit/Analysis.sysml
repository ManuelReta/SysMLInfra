package PumpingUnit_Analysis {
    private import ScalarValues::*;
    public import PumpingUnit_Architecture::*;
    public import PumpingUnit_Requirements::*;

    part pumpingUnitVerification : PumpingUnitSubsystemContract {
        part :>> unitA {
            attribute :>> waterVelocity_mps = 5.2;
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
        attribute :>> deliveredCapacity_m3h = unitA.capacity_m3h + unitB.capacity_m3h;
        attribute :>> operationalUnitCount = 2;
        attribute :>> simultaneousSuctionAvailable = true;

        attribute DNV_PU_001_twoUnits : Boolean = unitA.available and unitB.available;
        attribute DNV_PU_003_independentDrive : Boolean =
            unitA.independentlyDriven and unitB.independentlyDriven;
        attribute DNV_PU_010_velocity : Boolean =
            unitA.waterVelocity_mps >= 2.0 and unitB.waterVelocity_mps >= 2.0;
        attribute DNV_PU_011_combinedCapacity : Boolean =
            unitA.capacity_m3h + unitB.capacity_m3h >= requiredCapacity_m3h;
        attribute DNV_PU_012_smallerShare : Boolean =
            unitB.capacity_m3h >= (unitA.capacity_m3h + unitB.capacity_m3h) / 3.0;
        attribute DNV_PU_020_overhaulAvailability : Boolean =
            unitA.available or unitB.available;
        attribute DNV_PU_017_priming : Boolean =
            (not unitA.centrifugal or unitA.selfPriming or unitA.centralPrimingConnected) and
            (not unitB.centrifugal or unitB.selfPriming or unitB.centralPrimingConnected);
        attribute DNV_PU_018_highVelocityApproval : Boolean =
            (unitA.waterVelocity_mps <= 5.0 or unitA.pressureLossCalculationApproved) and
            (unitB.waterVelocity_mps <= 5.0 or unitB.pressureLossCalculationApproved);
        attribute DNV_PU_021_simultaneousSuction : Boolean = simultaneousSuctionAvailable;
    }
}