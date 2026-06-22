package SimplePump {

    private import ScalarValues::Real;
    private import ScalarValues::Boolean;

    part def Pump {

        // Inputs
        attribute flowRate   : Real = 0.01;
        attribute efficiency : Real = 0.5;
        attribute powerInput : Real = 1000.0;

        // Derived values
        attribute hydraulicPower : Real = flowRate * 1000;
        attribute usefulPower    : Real = hydraulicPower * efficiency;
        attribute loss           : Real = powerInput - usefulPower;

        // Boolean checks (these replace requirements)
        attribute lossOK      : Boolean = loss <= 0;
        attribute efficientOK : Boolean = efficiency <= 1.0;
        attribute overallOK   : Boolean = lossOK and efficientOK;
    }

    part p : Pump;
}