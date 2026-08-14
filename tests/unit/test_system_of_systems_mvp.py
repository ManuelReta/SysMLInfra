"""Focused tests for the runnable system-of-systems MVP."""

from __future__ import annotations

import importlib.util
import json
import zipfile
from pathlib import Path

import pytest

MODULE_PATH = (
    Path(__file__).parents[2]
    / "examples"
    / "system-of-systems"
    / "runtime-mvp"
    / "mvp.py"
)
SPEC = importlib.util.spec_from_file_location("sos_mvp", MODULE_PATH)
assert SPEC and SPEC.loader
mvp = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mvp)


def statuses(case):
    return {result["rule"]: result["status"] for result in case["results"]}


def test_end_to_end_outputs_and_expected_failures(tmp_path):
    summary = mvp.run(tmp_path, clean=True)

    assert set(summary["sync_statuses"].values()) == {"PASS"}
    assert summary["async_status"] == "INCONCLUSIVE"
    assert summary["observations_appended"] == 12

    matrix = json.loads((tmp_path / "compatibility-report.json").read_text())
    by_name = {case["case"]: statuses(case) for case in matrix}
    assert by_name["compatible-pump-95"]["SOS-002"] == "PASS"
    assert by_name["oversized-pump-115"]["SOS-002"] == "FAIL"
    assert by_name["one-pipe-connection"]["SOS-003"] == "FAIL"
    assert by_name["well-demand-105"]["SOS-001"] == "FAIL"
    assert by_name["renamed-pump-export"]["SOS-001"] == "BLOCKED"


def test_release_is_deterministic_and_tampering_is_rejected(tmp_path):
    descriptor = mvp.load_descriptors()[0]
    first = mvp.build_release(descriptor, tmp_path)
    second = mvp.build_release(descriptor, tmp_path)
    assert first["digest"] == second["digest"]
    assert first["archive"] == second["archive"]

    archive = tmp_path / first["archive"]
    with zipfile.ZipFile(archive, "a") as bundle:
        bundle.writestr("tampered.txt", "changed")
    with pytest.raises(ValueError, match="digest mismatch"):
        mvp.verify_release(first, tmp_path)


def test_locked_federation_fails_on_commit_mismatch(tmp_path):
    lock, _ = mvp.build_lock(tmp_path)
    registry = json.loads((tmp_path / "federated-registry.json").read_text())
    project_id = lock["constituents"][0]["api_receipt"]["project_uuid"]
    registry[project_id]["commit_uuid"] = "wrong"

    with pytest.raises(ValueError, match="commit mismatch"):
        mvp.resolve_locked_exports(lock, registry)