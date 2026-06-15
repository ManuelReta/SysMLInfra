import os
from pathlib import Path
from dotenv import load_dotenv
import json
from typing import Type, Union

load_dotenv()

REPO_ROOT = Path(os.getenv("REPO_ROOT", "."))
LIB_DIR = REPO_ROOT / "lib"

SCRIPTS_DIR = REPO_ROOT / "scripts"
EXAMPLES_BILGEPUMP_DIR = REPO_ROOT / "examples" / "bilgepump"


class SysandPackageStructure:
    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.MANIFEST = project_dir / "sysml-project.yml"
        self.metadata = project_dir / ".meta.json"
        self.project_file = project_dir / ".project.json"
        self.project_data = self._read_project_data()
        self.project_name = self.project_data.get("name", project_dir.name)

    def _read_project_data(self) -> dict:
        if self.project_file.exists():
            with open(self.project_file) as f:
                return json.load(f)
        return {}


class ManuelPackageStructure:
    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.MANIFEST = project_dir / "sysml-project.yml"


class CheckPackageType:
    def __init__(self, project_dir: Path) -> None:
        manifest_path = project_dir / "sysml-project.yml"
        root_project_file = project_dir / ".project.json"
        package: Union[Type[ManuelPackageStructure], Type]

        if not root_project_file.exists() and manifest_path.exists():
            package = ManuelPackageStructure

        elif not manifest_path.exists():
            package = SysandPackageStructure
        else:
            raise RuntimeError(f"Invalid package structure in {project_dir}")
        self.package = package

    def package_type(self):
        return self.package
