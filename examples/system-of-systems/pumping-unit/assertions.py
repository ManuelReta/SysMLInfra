ANALYSIS = "PumpingUnit_Analysis::pumpingUnitVerification"


def assertion(rule_id, attribute, requirement, note):
    return {
        "id": rule_id,
        "fqn": f"{ANALYSIS}.{attribute}",
        "layer": "Analysis",
        "requirement": requirement,
        "kind": "positive",
        "expected": True,
        "note": note,
    }


ASSERTIONS = [
    assertion("DNV-PU-001", "DNV_PU_001_twoUnits", "DNV 8.1.1 #1", "At least two units"),
    assertion("DNV-PU-003", "DNV_PU_003_independentDrive", "DNV 8.1.1 #3", "Independent drives"),
    assertion("DNV-PU-010", "DNV_PU_010_velocity", "DNV 8.2.1 #10", "Each unit >= 2 m/s"),
    assertion("DNV-PU-011", "DNV_PU_011_combinedCapacity", "DNV 8.2.1 #11", "Combined capacity covers deficiency"),
    assertion("DNV-PU-012", "DNV_PU_012_smallerShare", "DNV 8.2.2 #12", "Smaller unit >= one third combined"),
    assertion("DNV-PU-020", "DNV_PU_020_overhaulAvailability", "DNV #20", "One unit available during overhaul"),
    assertion("DNV-PU-017", "DNV_PU_017_priming", "DNV #17", "Centrifugal pump has self or central priming"),
    assertion("DNV-PU-018", "DNV_PU_018_highVelocityApproval", "DNV #18", "Velocity above 5 m/s has approved pressure-loss evidence"),
    assertion("DNV-PU-021", "DNV_PU_021_simultaneousSuction", "DNV #21", "Direct and main-line suction can operate simultaneously"),
]