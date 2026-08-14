package PumpingUnit_Library {
    private import ScalarValues::*;

    part def PumpingUnit {
        attribute waterVelocity_mps : Real;
        attribute capacity_m3h : Real;
        attribute independentlyDriven : Boolean;
        attribute available : Boolean;
        attribute centrifugal : Boolean;
        attribute selfPriming : Boolean;
        attribute centralPrimingConnected : Boolean;
        attribute pressureLossCalculationApproved : Boolean;
    }

    part def PumpingUnitSubsystemContract {
        part unitA : PumpingUnit;
        part unitB : PumpingUnit;
        attribute requiredCapacity_m3h : Real;
        attribute deliveredCapacity_m3h : Real;
        attribute operationalUnitCount : Integer;
        attribute simultaneousSuctionAvailable : Boolean;
    }
}