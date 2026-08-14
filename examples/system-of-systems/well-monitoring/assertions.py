ANALYSIS = "WellMonitoring_Analysis::wellMonitoringVerification"


def assertion(rule_id, attribute, requirement, note):
    return {"id": rule_id, "fqn": f"{ANALYSIS}.{attribute}", "layer": "Analysis", "requirement": requirement, "kind": "positive", "expected": True, "note": note}


ASSERTIONS = [
    assertion("DNV-WM-045", "DNV_WM_045_indication", "DNV #45", "Remote operation indication"),
    assertion("DNV-WM-046", "DNV_WM_046_capacity", "DNV #46", "Well capacity >= 0.15 m3"),
    assertion("DNV-WM-047", "DNV_WM_047_mudBoxRouting", "DNV #47", "Machinery drains led to mud boxes"),
    assertion("DNV-WM-048", "DNV_WM_048_mudBoxArrangement", "DNV #48", "Straight, inspectable mud-box tails"),
    assertion("DNV-WM-050A", "DNV_WM_050_cargoStrum", "DNV #50", "Cargo-hold strums fitted"),
    assertion("DNV-WM-050B", "DNV_WM_050_cargoStrumAccess", "DNV #50", "Cargo-hold strums inspectable"),
    assertion("DNV-WM-054", "DNV_WM_054_fittingAccess", "DNV #54", "Fittings readily accessible"),
    assertion("DNV-WM-049", "DNV_WM_049_noDirectStrums", "DNV #49", "No strums on direct or emergency suctions"),
    assertion("DNV-WM-055", "DNV_WM_055_belowFloorAccess", "DNV #55", "Below-floor fittings have removable plate and nameplate"),
]