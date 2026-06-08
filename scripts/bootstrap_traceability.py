#!/usr/bin/env python3
"""
bootstrap_traceability.py — Populate lib/traceability.json from ingested docs.

Parses the structured JSON documents in bilgepump/docs/ingested/ and writes a
populated traceability index to lib/traceability.json.  This unblocks the
TraceabilityAgent gate (which requires non-empty portDefs, attributeDefs,
partDefs, requirements, and connections arrays).

Ingested sources:
  bilgepump/docs/ingested/requirements/solas-regulatory-extract.json
    → requirements[], constraintDefs[]
  bilgepump/docs/ingested/components/bom-component-list.json
    → partDefs[], portDefs[], attributeDefs[]

Also updates lib/build-state.json:
  phase6.traceability → "complete"

Usage:
    python scripts/bootstrap_traceability.py
    python scripts/bootstrap_traceability.py --dry-run   # show output, don't write
    python scripts/bootstrap_traceability.py --verbose   # show per-entry details
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT      = Path(__file__).parent.parent.resolve()
INGESTED_DIR   = REPO_ROOT / "bilgepump" / "docs" / "ingested"
TRACEABILITY   = REPO_ROOT / "lib" / "traceability.json"
BUILD_STATE    = REPO_ROOT / "lib" / "build-state.json"

REQUIREMENTS_JSON = INGESTED_DIR / "requirements" / "solas-regulatory-extract.json"
COMPONENTS_JSON   = INGESTED_DIR / "components" / "bom-component-list.json"


# ── Parsers ───────────────────────────────────────────────────────────────────

def _parse_requirements(path: Path, verbose: bool) -> tuple[list, list]:
    """
    Parse solas-regulatory-extract.json.
    Returns (requirements_entries, constraint_def_entries).
    """
    with open(path) as f:
        data = json.load(f)

    requirements: list[dict] = []
    constraint_defs: list[dict] = []

    for req in data.get("requirements", []):
        req_entry = {
            "id":                 req.get("id", ""),
            "name":               req.get("name", ""),
            "text":               req.get("text", ""),
            "subject":            req.get("subject", ""),
            "regulatory_source":  req.get("regulatory_source", ""),
            "regulation_id":      req.get("regulation_id", ""),
            "verification_method": req.get("verification_method", "analysis"),
            "source_doc":         req.get("source_doc", ""),
            "section":            str(req.get("section", "")),
        }
        requirements.append(req_entry)

        expr = req.get("constraint_expression", "")
        if expr:
            constraint_defs.append({
                "name":    req.get("name", "") + "_constraint",
                "req_id":  req.get("id", ""),
                "expr":    expr,
                "unit":    req.get("constraint_unit", ""),
            })

        if verbose:
            print(f"  REQ  {req_entry['id']:12}  {req_entry['name']}")

    return requirements, constraint_defs


def _parse_components(path: Path, verbose: bool) -> tuple[list, list, list]:
    """
    Parse bom-component-list.json.
    Returns (part_def_entries, port_def_entries, attribute_def_entries).
    """
    with open(path) as f:
        data = json.load(f)

    part_defs: list[dict] = []
    port_defs: list[dict] = []
    attr_defs: list[dict] = []

    for comp in data.get("components", []):
        name = comp.get("name", "")
        part_defs.append({
            "name":         name,
            "part_number":  comp.get("part_number", ""),
            "description":  comp.get("description", ""),
            "manufacturer": comp.get("manufacturer", ""),
            "model":        comp.get("model", ""),
            "source_doc":   comp.get("source_doc", ""),
        })

        for port in comp.get("ports", []):
            port_defs.append({
                "name":       port.get("name", ""),
                "owner":      name,
                "type":       port.get("type", ""),
                "direction":  port.get("direction", ""),
            })

        for attr in comp.get("attributes", []):
            attr_defs.append({
                "name":       attr.get("name", ""),
                "owner":      name,
                "type":       attr.get("type", "Real"),
                "unit":       attr.get("unit", ""),
                "nominal":    attr.get("nominal"),
            })

        if verbose:
            n_ports = len(comp.get("ports", []))
            n_attrs = len(comp.get("attributes", []))
            print(f"  COMP {name:<30}  {n_ports} port(s), {n_attrs} attr(s)")

    return part_defs, port_defs, attr_defs


def _parse_connections(ingested_dir: Path, verbose: bool) -> list[dict]:
    """
    Parse connections/ directory if present.
    Returns connection entries.
    """
    conn_dir = ingested_dir / "connections"
    connections: list[dict] = []
    if not conn_dir.exists():
        return connections

    for f in sorted(conn_dir.glob("*.json")):
        try:
            with open(f) as fh:
                data = json.load(fh)
            for conn in data.get("connections", []):
                connections.append({
                    "id":     conn.get("id", ""),
                    "from":   conn.get("from", ""),
                    "to":     conn.get("to", ""),
                    "type":   conn.get("type", "signal"),
                    "label":  conn.get("label", ""),
                })
            if verbose:
                print(f"  CONN {f.name:<40}  {len(data.get('connections', []))} connection(s)")
        except (json.JSONDecodeError, KeyError):
            pass

    return connections


# ── Build-state updater ───────────────────────────────────────────────────────

def _update_build_state(build_state_path: Path, verbose: bool) -> None:
    """Set phase6.traceability = 'complete' in build-state.json."""
    if not build_state_path.exists():
        if verbose:
            print(f"  NOTE: {build_state_path} not found — skipping build-state update")
        return

    with open(build_state_path) as f:
        state = json.load(f)

    if "phaseStatus" not in state:
        state["phaseStatus"] = {}
    if "phase6" not in state["phaseStatus"]:
        state["phaseStatus"]["phase6"] = {}

    state["phaseStatus"]["phase6"]["traceability"] = "complete"
    state["phaseStatus"]["phase6"]["bootstrap_timestamp"] = (
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    with open(build_state_path, "w") as f:
        json.dump(state, f, indent=2)

    if verbose:
        print(f"  build-state.json → phase6.traceability = 'complete'")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="bootstrap_traceability.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--dry-run",  action="store_true",
                        help="Print what would be written without modifying any files.")
    parser.add_argument("--verbose",  action="store_true",
                        help="Print each entry as it is parsed.")
    args = parser.parse_args()

    print("\nBootstrapping traceability index...")
    print("─" * 60)

    # ── Parse sources ─────────────────────────────────────────────────────────
    requirements: list[dict]    = []
    constraint_defs: list[dict] = []
    part_defs: list[dict]       = []
    port_defs: list[dict]       = []
    attr_defs: list[dict]       = []
    connections: list[dict]     = []

    if REQUIREMENTS_JSON.exists():
        if args.verbose:
            print(f"\nParsing {REQUIREMENTS_JSON.relative_to(REPO_ROOT)}")
        r, c = _parse_requirements(REQUIREMENTS_JSON, args.verbose)
        requirements.extend(r)
        constraint_defs.extend(c)
    else:
        print(f"  WARNING: {REQUIREMENTS_JSON.relative_to(REPO_ROOT)} not found — skipping",
              file=sys.stderr)

    if COMPONENTS_JSON.exists():
        if args.verbose:
            print(f"\nParsing {COMPONENTS_JSON.relative_to(REPO_ROOT)}")
        p, po, a = _parse_components(COMPONENTS_JSON, args.verbose)
        part_defs.extend(p)
        port_defs.extend(po)
        attr_defs.extend(a)
    else:
        print(f"  WARNING: {COMPONENTS_JSON.relative_to(REPO_ROOT)} not found — skipping",
              file=sys.stderr)

    connections = _parse_connections(INGESTED_DIR, args.verbose)

    # ── Build output ──────────────────────────────────────────────────────────
    # Read existing traceability to preserve any existing analysisDefs/allocations
    existing: dict = {}
    if TRACEABILITY.exists():
        with open(TRACEABILITY) as f:
            existing = json.load(f)

    output = {
        "_comment":      existing.get("_comment",
                         "Traceability index. Each mapper agent appends entries here. "
                         "TraceabilityAgent reads this as ground truth."),
        "_bootstrap":    {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "sources": [
                str(REQUIREMENTS_JSON.relative_to(REPO_ROOT)),
                str(COMPONENTS_JSON.relative_to(REPO_ROOT)),
            ],
            "counts": {
                "requirements":   len(requirements),
                "constraintDefs": len(constraint_defs),
                "partDefs":       len(part_defs),
                "portDefs":       len(port_defs),
                "attributeDefs":  len(attr_defs),
                "connections":    len(connections),
            },
        },
        "portDefs":       port_defs,
        "attributeDefs":  attr_defs,
        "partDefs":       part_defs,
        "connections":    connections,
        "requirements":   requirements,
        "constraintDefs": constraint_defs,
        "allocations":    existing.get("allocations", []),
        "analysisDefs":   existing.get("analysisDefs", []),
    }

    # ── Summary ───────────────────────────────────────────────────────────────
    counts = output["_bootstrap"]["counts"]
    print(f"\n  Requirements   : {counts['requirements']}")
    print(f"  ConstraintDefs : {counts['constraintDefs']}")
    print(f"  PartDefs       : {counts['partDefs']}")
    print(f"  PortDefs       : {counts['portDefs']}")
    print(f"  AttributeDefs  : {counts['attributeDefs']}")
    print(f"  Connections    : {counts['connections']}")

    if args.dry_run:
        print("\n[DRY RUN] Would write to:")
        print(f"  {TRACEABILITY.relative_to(REPO_ROOT)}")
        print(f"  {BUILD_STATE.relative_to(REPO_ROOT)} (phase6.traceability=complete)")
        print()
        return

    # ── Write outputs ─────────────────────────────────────────────────────────
    TRACEABILITY.parent.mkdir(parents=True, exist_ok=True)
    with open(TRACEABILITY, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n  ✓  Written: {TRACEABILITY.relative_to(REPO_ROOT)}")

    _update_build_state(BUILD_STATE, args.verbose)
    print(f"  ✓  Updated: {BUILD_STATE.relative_to(REPO_ROOT)}")
    print()


if __name__ == "__main__":
    main()
