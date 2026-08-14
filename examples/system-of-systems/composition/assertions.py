ANALYSIS = "VesselDrainageSoS_Analysis::sosVerification"


def assertion(rule_id, attribute, note):
    return {"id": rule_id, "fqn": f"{ANALYSIS}.{attribute}", "layer": "Analysis", "requirement": rule_id, "kind": "positive", "expected": True, "note": note}


ASSERTIONS = [
    assertion("SOS-001", "SOS_001_capacity", "Pumping guarantee covers monitoring demand"),
    assertion("SOS-002", "SOS_002_pipingCapacity", "Piping capacity accepts pumping output"),
    assertion("SOS-003", "SOS_003_connections", "Piping accepts every operational pump"),
    assertion("SOS-004", "SOS_004_endToEndPath", "End-to-end drainage path available"),
    assertion("SOS-005", "SOS_005_degradedOperation", "Single-pump operation retains feedback"),
    {
        "id": "SOS-002-NEG",
        "fqn": "VesselDrainageSoS_Analysis::incompatibleComposition.SOS_002_rejectUndersizedPiping",
        "layer": "Analysis",
        "requirement": "SOS-002",
        "kind": "negative",
        "expected": False,
        "note": "Undersized historical piping contract must be rejected",
    },
]