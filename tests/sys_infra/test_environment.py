import json
from pathlib import Path

import pytest

from sys_infra.environment import (
    SysandPackageStructure,
    ManuelPackageStructure,
    CheckPackageType,
)


@pytest.fixture
def tmp_project_dir(tmp_path: Path):
    return tmp_path


def test_sysand_reads_project_json(tmp_project_dir) -> None:
    project_data = {"name": "my_project"}
    project_file = tmp_project_dir / ".project.json"

    project_file.write_text(json.dumps(project_data))

    pkg = SysandPackageStructure(tmp_project_dir)

    assert pkg.project_data == project_data
    assert pkg.project_name == "my_project"


def test_sysand_missing_project_json(tmp_project_dir) -> None:
    pkg = SysandPackageStructure(tmp_project_dir)

    assert pkg.project_data == {}
    assert pkg.project_name == tmp_project_dir.name


def test_manuel_structure_sets_manifest(tmp_project_dir) -> None:
    pkg = ManuelPackageStructure(tmp_project_dir)

    assert pkg.MANIFEST == tmp_project_dir / "sysml-project.yml"


def test_check_package_type_manuel(tmp_project_dir) -> None:
    (tmp_project_dir / "sysml-project.yml").touch()

    checker = CheckPackageType(tmp_project_dir)

    assert checker.package_type() is ManuelPackageStructure


def test_check_package_type_sysand(tmp_project_dir) -> None:
    checker = CheckPackageType(tmp_project_dir)

    assert checker.package_type() is SysandPackageStructure


def test_check_package_type_invalid(tmp_project_dir) -> None:
    (tmp_project_dir / "sysml-project.yml").touch()
    (tmp_project_dir / ".project.json").touch()

    with pytest.raises(RuntimeError, match="Invalid package structure"):
        CheckPackageType(tmp_project_dir)


def test_sysand_empty_project_json(tmp_project_dir) -> None:
    (tmp_project_dir / ".project.json").write_text("{}")

    pkg = SysandPackageStructure(tmp_project_dir)

    assert pkg.project_name == tmp_project_dir.name
