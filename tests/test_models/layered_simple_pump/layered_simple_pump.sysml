package LayeredSystem {

    private import ScalarValues::Real;
    private import ScalarValues::Boolean;

    part def PumpSystem {

        attribute flowRate   : Real;
        attribute efficiency : Real;
        attribute powerInput : Real;

        attribute hydraulicPower : Real = flowRate * 1000;
        attribute usefulPower    : Real = hydraulicPower * efficiency;
        attribute loss           : Real = powerInput - usefulPower;

        attribute isEfficient : Boolean = efficiency > 0.75;
        attribute isSafe      : Boolean = loss >= 0 and efficiency <= 1.0;
    }

    // ======================
    // REQUIREMENTS
    // ======================

    requirement def LossRequirement {
        subject s : PumpSystem;
        require constraint {
            s.loss >= 0
        }
    }

    requirement def EfficiencyRequirement {
        subject s : PumpSystem;
        require constraint {
            s.efficiency >= 0.7
        }
    }

    requirement def SafeOperation {
        subject s : PumpSystem;
        require constraint {
            s.loss >= 0 and s.efficiency <= 1.0
        }
    }

    // ======================
    // SYSTEM INSTANCE
    // ======================

    part pump : PumpSystem {
        :>> flowRate   = 0.0;
        :>> efficiency = 0.9;
        :>> powerInput = 1000;
    }

    // ======================
    // REQUIREMENT USAGE ✅
    // ======================

    requirement r_loss : LossRequirement {
        subject s = pump;
    }

    requirement r_eff : EfficiencyRequirement {
        subject s = pump;
    }

    requirement r_safe : SafeOperation {
        subject s = pump;
    }
}


// %eval LayeredSystem::pump.isEfficient
