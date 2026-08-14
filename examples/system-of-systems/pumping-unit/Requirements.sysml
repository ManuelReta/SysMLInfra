package PumpingUnit_Requirements {
    public import PumpingUnit_Library::*;

    // Source: DNV-RU-SHIP Pt.4 Ch.6 Sec.4, supplied extraction JSON.
    requirement def DNV_8_1_1_TwoUnits {
        subject sys : PumpingUnitSubsystemContract;
        require constraint { sys.unitA.available and sys.unitB.available }
    }

    requirement def DNV_8_1_1_IndependentDrive {
        subject sys : PumpingUnitSubsystemContract;
        require constraint { sys.unitA.independentlyDriven and sys.unitB.independentlyDriven }
    }

    requirement def DNV_8_2_1_MinimumVelocity {
        subject sys : PumpingUnitSubsystemContract;
        require constraint {
            sys.unitA.waterVelocity_mps >= 2.0 and sys.unitB.waterVelocity_mps >= 2.0
        }
    }

    requirement def DNV_8_2_1_CombinedCapacity {
        subject sys : PumpingUnitSubsystemContract;
        require constraint {
            sys.unitA.capacity_m3h + sys.unitB.capacity_m3h >= sys.requiredCapacity_m3h
        }
    }

    requirement def DNV_8_2_2_SmallerUnitShare {
        subject sys : PumpingUnitSubsystemContract;
        require constraint {
            sys.unitB.capacity_m3h >=
                (sys.unitA.capacity_m3h + sys.unitB.capacity_m3h) / 3.0
        }
    }

    requirement def DNV_8_3_OverhaulAvailability {
        subject sys : PumpingUnitSubsystemContract;
        require constraint { sys.unitA.available or sys.unitB.available }
    }

    requirement def DNV_8_3_CentrifugalPriming {
        subject sys : PumpingUnitSubsystemContract;
        require constraint {
            (not sys.unitA.centrifugal or sys.unitA.selfPriming or sys.unitA.centralPrimingConnected) and
            (not sys.unitB.centrifugal or sys.unitB.selfPriming or sys.unitB.centralPrimingConnected)
        }
    }

    requirement def DNV_8_3_HighVelocityApproval {
        subject sys : PumpingUnitSubsystemContract;
        require constraint {
            (sys.unitA.waterVelocity_mps <= 5.0 or sys.unitA.pressureLossCalculationApproved) and
            (sys.unitB.waterVelocity_mps <= 5.0 or sys.unitB.pressureLossCalculationApproved)
        }
    }

    requirement def DNV_8_3_SimultaneousSuction {
        subject sys : PumpingUnitSubsystemContract;
        require constraint { sys.simultaneousSuctionAvailable }
    }
}