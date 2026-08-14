ANALYSIS = "PipingNetwork_Analysis::pipingVerification"


def assertion(rule_id, attribute, requirement, note):
    return {"id": rule_id, "fqn": f"{ANALYSIS}.{attribute}", "layer": "Analysis", "requirement": requirement, "kind": "positive", "expected": True, "note": note}


ASSERTIONS = [
    assertion("DNV-PN-019", "DNV_PN_019_stopValves", "DNV #19", "Stop valve at every pump connection"),
    assertion("DNV-PN-023", "DNV_PN_023_nonReturnValves", "DNV #23", "At most two non-return valves"),
    assertion("DNV-PN-032", "DNV_PN_032_branchDiameter", "DNV #32", "Branch diameter within 50-100 mm"),
    assertion("DNV-PN-037", "DNV_PN_037_distributionArea", "DNV #37", "Distribution area covers two largest branches"),
    assertion("DNV-PN-040", "DNV_PN_040_tankProtection", "DNV #40", "Tank transit protected by non-return valve"),
    assertion("DNV-PN-051", "DNV_PN_051_strumArea", "DNV #51", "Open area at least twice pipe area"),
    assertion("DNV-PN-053", "DNV_PN_053_fullFlow", "DNV #53", "Suction clearance permits full flow"),
    assertion("DNV-PN-028", "DNV_PN_028_mainPipeArea", "DNV #28", "Main pipe area >= twice engine-room branch area"),
    assertion("DNV-PN-035", "DNV_PN_035_emergencyDiameter", "DNV #35", "Optional emergency suction matches pump and is <= 400 mm"),
    assertion("DNV-PN-044", "DNV_PN_044_cargoProtection", "DNV #44 + experiment acceptance profile", "Cargo-hold piping has mechanical, material, and corrosion protection"),
]