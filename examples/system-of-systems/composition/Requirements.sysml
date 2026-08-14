package VesselDrainageSoS_Requirements {
    public import VesselDrainageSoS_Architecture::*;

    requirement def CapacityCompatibility {
        subject sos : VesselDrainageSoSContract;
        require constraint { sos.pumping.deliveredCapacity_m3h >= sos.monitoring.requiredDrainageCapacity_m3h }
    }
    requirement def PipingCompatibility {
        subject sos : VesselDrainageSoSContract;
        require constraint { sos.piping.supportedCapacity_m3h >= sos.pumping.deliveredCapacity_m3h }
    }
    requirement def ConnectionCompatibility {
        subject sos : VesselDrainageSoSContract;
        require constraint { sos.piping.acceptedPumpCount >= sos.pumping.operationalUnitCount }
    }
    requirement def EndToEndFlowPath {
        subject sos : VesselDrainageSoSContract;
        require constraint { sos.monitoring.outletAvailable and sos.piping.flowPathAvailable }
    }
    requirement def DegradedOperation {
        subject sos : VesselDrainageSoSContract;
        require constraint {
            sos.pumping.unitA.capacity_m3h >= 50.0 and sos.monitoring.operatorFeedbackAvailable
        }
    }
}