package LayeredSystem {

    private import ScalarValues::Real;
    private import ScalarValues::String;
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

    requirement def LossRequirement {
        subject s : PumpSystem;
        attribute req: Boolean = s.loss >= 0; 
        
    }

    requirement def EfficiencyRequirement {
        subject s : PumpSystem;
        attribute req: Boolean = s.efficiency >= 0.7;
    }

    requirement def FlowRateRequirement {
        subject s : PumpSystem;
    
        attribute req : Boolean = s.hydraulicPower >= 50.0;
    }

    part pump : PumpSystem {
        :>> flowRate   = 0.1;
        :>> efficiency = 0.9;
        :>> powerInput = 1000;
    }

    requirement <R1> r_loss : LossRequirement {
        subject s = pump;
    }

    requirement <R2> r_eff : EfficiencyRequirement {
        subject s = pump;
    }

    requirement <R3> r_safe : FlowRateRequirement {
        subject s = pump;
    }

}
