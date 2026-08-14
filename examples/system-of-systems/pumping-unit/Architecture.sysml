package PumpingUnit_Architecture {
    private import ScalarValues::*;
    public import PumpingUnit_Library::*;

    part pumpingUnitSystem : PumpingUnitSubsystemContract {
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
        attribute :>> deliveredCapacity_m3h = unitA.capacity_m3h + unitB.capacity_m3h;
        attribute :>> operationalUnitCount = 2;
        attribute :>> simultaneousSuctionAvailable = true;
    }
}