#!/usr/bin/env python3
"""Runnable system-of-systems contract and mock-runtime MVP.

Uses only the standard library. It packages real SysML constituent sources,
locks them by SHA-256, resolves cross-project contract references through a
mock API receipt registry, and writes runtime observations/evidence as JSONL.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import uuid
import zipfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
CONTRACTS = HERE / "contracts"
DEFAULT_OUTPUT = HERE / "output"
FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def content_digest(entries: dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    for name in sorted(entries):
        digest.update(name.encode() + b"\0" + entries[name] + b"\0")
    return digest.hexdigest()


def load_descriptors() -> list[dict[str, Any]]:
    return [json.loads(path.read_text()) for path in sorted(CONTRACTS.glob("*.json"))]


def build_release(descriptor: dict[str, Any], output: Path) -> dict[str, Any]:
    project_dir = (CONTRACTS / descriptor["project_dir"]).resolve()
    entries = {
        name: (project_dir / name).read_bytes() for name in descriptor["source_files"]
    }
    entries["contract.json"] = canonical_json(
        {key: descriptor[key] for key in ("name", "version", "exports")}
    )
    digest = content_digest(entries)
    releases = output / "releases"
    releases.mkdir(parents=True, exist_ok=True)
    archive = releases / f"{descriptor['name']}-{descriptor['version']}-{digest[:12]}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for name in sorted(entries):
            info = zipfile.ZipInfo(name, FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            bundle.writestr(info, entries[name])

    # Synthetic receipts exercise exact project/commit addressing without
    # publishing scratch projects into the shared local Pilot API.
    return {
        "name": descriptor["name"],
        "version": descriptor["version"],
        "digest": f"sha256:{digest}",
        "archive": str(archive.relative_to(output)),
        "api_receipt": {
            "mode": "mock",
            "project_uuid": str(uuid.uuid5(uuid.NAMESPACE_URL, f"project:{descriptor['name']}")),
            "commit_uuid": str(uuid.uuid5(uuid.NAMESPACE_URL, f"commit:{digest}")),
        },
    }


def verify_release(item: dict[str, Any], output: Path) -> dict[str, Any]:
    archive = output / item["archive"]
    with zipfile.ZipFile(archive) as bundle:
        entries = {name: bundle.read(name) for name in bundle.namelist()}
    actual = f"sha256:{content_digest(entries)}"
    if actual != item["digest"]:
        raise ValueError(f"digest mismatch for {item['name']}: {actual}")
    return json.loads(entries["contract.json"])


def build_lock(output: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    items = [build_release(descriptor, output) for descriptor in load_descriptors()]
    lock = {"schema": "sos-lock/1", "constituents": items}
    (output / "composition.lock.json").write_bytes(canonical_json(lock))
    contracts = {item["name"]: verify_release(item, output) for item in items}
    registry = {
        item["api_receipt"]["project_uuid"]: {
            "commit_uuid": item["api_receipt"]["commit_uuid"],
            "digest": item["digest"],
            "exports": contracts[item["name"]]["exports"],
        }
        for item in items
    }
    (output / "federated-registry.json").write_bytes(canonical_json(registry))
    return lock, contracts


def resolve_locked_exports(
    lock: dict[str, Any], registry: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """Resolve contracts by exact project, commit, and package digest."""
    resolved = {}
    for item in lock["constituents"]:
        receipt = item["api_receipt"]
        project = registry.get(receipt["project_uuid"])
        if project is None:
            raise ValueError(f"unresolved project for {item['name']}")
        if project["commit_uuid"] != receipt["commit_uuid"]:
            raise ValueError(f"commit mismatch for {item['name']}")
        if project["digest"] != item["digest"]:
            raise ValueError(f"contract digest mismatch for {item['name']}")
        resolved[item["name"]] = project["exports"]
    return resolved


def evaluate(exports: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    pump = exports["PumpingUnitSubsystem"]
    pipe = exports["PipingNetworkSubsystem"]
    well = exports["WellMonitoringSubsystem"]
    rules = [
        ("SOS-001", pump.get("deliveredCapacity_m3h"), well.get("requiredDrainageCapacity_m3h"), ">="),
        ("SOS-002", pipe.get("supportedCapacity_m3h"), pump.get("deliveredCapacity_m3h"), ">="),
        ("SOS-003", pipe.get("acceptedPumpCount"), pump.get("operationalUnitCount"), ">="),
        ("SOS-004", well.get("outletAvailable"), pipe.get("flowPathAvailable"), "and"),
        ("SOS-005", pump.get("singlePumpCapacity_m3h"), well.get("operatorFeedbackAvailable"), "degraded"),
    ]
    results = []
    for rule_id, left, right, operator in rules:
        if left is None or right is None:
            status = "BLOCKED"
        elif operator == ">=":
            status = "PASS" if left >= right else "FAIL"
        elif operator == "and":
            status = "PASS" if left and right else "FAIL"
        else:
            status = "PASS" if left >= 50.0 and right else "FAIL"
        results.append({"rule": rule_id, "status": status, "observed": [left, right]})
    return results


def run_matrix(base: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    cases: list[tuple[str, str, dict[str, Any]]] = [
        ("baseline", "all-pass", {}),
        ("compatible-pump-95", "all-pass", {"PumpingUnitSubsystem": {"deliveredCapacity_m3h": 95.0}}),
        ("oversized-pump-115", "SOS-002-fail", {"PumpingUnitSubsystem": {"deliveredCapacity_m3h": 115.0}}),
        ("one-pipe-connection", "SOS-003-fail", {"PipingNetworkSubsystem": {"acceptedPumpCount": 1}}),
        ("well-demand-105", "SOS-001-fail", {"WellMonitoringSubsystem": {"requiredDrainageCapacity_m3h": 105.0}}),
        ("renamed-pump-export", "SOS-001-and-002-blocked", {"PumpingUnitSubsystem": {"deliveredCapacity_m3h": None}}),
    ]
    report = []
    for name, expected, changes in cases:
        candidate = deepcopy(base)
        for project, values in changes.items():
            candidate[project].update(values)
        report.append({"case": name, "expected": expected, "results": evaluate(candidate)})
    return report


def append_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, sort_keys=True) + "\n")


def synchronous_loop(exports: dict[str, dict[str, Any]], baseline_id: str) -> list[dict[str, Any]]:
    events = []
    for sequence in range(4):
        sim_time = float(sequence)
        demand = exports["WellMonitoringSubsystem"]["requiredDrainageCapacity_m3h"]
        pump_capacity = exports["PumpingUnitSubsystem"]["deliveredCapacity_m3h"]
        pipe_capacity = exports["PipingNetworkSubsystem"]["supportedCapacity_m3h"]
        produced = min(demand + sequence * 2.0, pump_capacity)
        delivered = min(produced, pipe_capacity)
        for producer, signal, value in (
            ("well-monitoring", "demandFlow_m3h", demand),
            ("pumping-unit", "producedFlow_m3h", produced),
            ("piping-network", "deliveredFlow_m3h", delivered),
        ):
            events.append({
                "baseline_id": baseline_id,
                "producer": producer,
                "sim_time": sim_time,
                "sequence": sequence,
                "signal": signal,
                "value": value,
                "unit": "m3/h",
                "quality": "GOOD",
            })
    return events


def asynchronous_evidence(events: list[dict[str, Any]], baseline_id: str) -> list[dict[str, Any]]:
    # Deterministic out-of-order replay; piping stops publishing after t=1.
    replay = [event for event in reversed(events) if not (
        event["producer"] == "piping-network" and event["sim_time"] > 1.0
    )]
    latest: dict[str, dict[str, Any]] = {}
    for event in replay:
        current = latest.get(event["signal"])
        if current is None or event["sim_time"] > current["sim_time"]:
            latest[event["signal"]] = event
    watermark = 3.0
    delivered = latest.get("deliveredFlow_m3h")
    status = "INCONCLUSIVE" if delivered is None or watermark - delivered["sim_time"] > 1.5 else "PASS"
    return [{
        "baseline_id": baseline_id,
        "mode": "asynchronous",
        "rule": "SOS-004-RUNTIME",
        "status": status,
        "reason": "deliveredFlow_m3h stale" if status == "INCONCLUSIVE" else "flow current",
        "watermark": watermark,
    }]


def run(output: Path, clean: bool = False) -> dict[str, Any]:
    if clean and output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    lock, _ = build_lock(output)
    registry = json.loads((output / "federated-registry.json").read_text())
    exports = resolve_locked_exports(lock, registry)
    baseline_id = hashlib.sha256(canonical_json(lock)).hexdigest()

    matrix = run_matrix(exports)
    (output / "compatibility-report.json").write_bytes(canonical_json(matrix))
    observations = synchronous_loop(exports, baseline_id)
    append_jsonl(output / "observations.jsonl", observations)
    sync_evidence = [{
        "baseline_id": baseline_id,
        "mode": "synchronous",
        **result,
    } for result in evaluate(exports)]
    async_evidence = asynchronous_evidence(observations, baseline_id)
    append_jsonl(output / "evidence.jsonl", [*sync_evidence, *async_evidence])
    summary = {
        "baseline_id": baseline_id,
        "locked_constituents": len(lock["constituents"]),
        "matrix_cases": len(matrix),
        "observations_appended": len(observations),
        "sync_statuses": {row["rule"]: row["status"] for row in sync_evidence},
        "async_status": async_evidence[0]["status"],
    }
    (output / "summary.json").write_bytes(canonical_json(summary))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--clean", action="store_true", help="replace previous append-only demo output")
    args = parser.parse_args()
    summary = run(args.output.resolve(), clean=args.clean)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())