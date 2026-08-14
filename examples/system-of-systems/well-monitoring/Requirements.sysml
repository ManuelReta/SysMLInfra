package WellMonitoring_Requirements {
    public import WellMonitoring_Library::*;

    // Source: DNV-RU-SHIP Pt.4 Ch.6 Sec.4, supplied extraction JSON.
    requirement def DNV_8_6_OperatingIndication {
        subject sys : WellMonitoringSubsystemContract;
        require constraint { sys.operatingIndicationProvided }
    }
    requirement def DNV_8_7_WellCapacity {
        subject sys : WellMonitoringSubsystemContract;
        require constraint { sys.wellCapacity_m3 >= 0.15 }
    }
    requirement def DNV_8_7_MudBoxRouting {
        subject sys : WellMonitoringSubsystemContract;
        require constraint { sys.machineryDrainLedToMudBox }
    }
    requirement def DNV_8_7_MudBoxArrangement {
        subject sys : WellMonitoringSubsystemContract;
        require constraint { sys.mudBoxStraightTail and sys.mudBoxInspectable }
    }
    requirement def DNV_8_7_CargoStrum {
        subject sys : WellMonitoringSubsystemContract;
        require constraint { sys.cargoStrumFitted }
    }
    requirement def DNV_8_7_CargoStrumAccess {
        subject sys : WellMonitoringSubsystemContract;
        require constraint { sys.cargoStrumInspectable }
    }
    requirement def DNV_8_7_FittingAccess {
        subject sys : WellMonitoringSubsystemContract;
        require constraint { sys.fittingsAccessible }
    }

    requirement def DNV_8_7_NoDirectSuctionStrums {
        subject sys : WellMonitoringSubsystemContract;
        require constraint {
            not sys.directSuctionStrumFitted and not sys.emergencySuctionStrumFitted
        }
    }

    requirement def DNV_8_7_BelowFloorAccess {
        subject sys : WellMonitoringSubsystemContract;
        require constraint {
            not sys.fittingsBelowFloor or
            (sys.floorPlateRemovable and sys.fittingNameplateProvided)
        }
    }
}