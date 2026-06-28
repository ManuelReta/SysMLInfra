import os
from pathlib import Path
import yaml
import shutil
import subprocess
from typing import Any
from resolver.locker import build_package, write_lockfile


DEPS_DIR = "deps"


class Resolver:
    def __init__(self, project_dir: Path):
        os.makedirs(project_dir / DEPS_DIR, exist_ok=True)
        self.resolved: dict[Any, Any] = {}

    def resolve_project(self, project_path):
        with open(project_path) as f:
            project = yaml.safe_load(f)

        self._resolve_dependencies(project.get("dependencies", []))
        return project

    def _resolve_dependencies(self, deps):
        for dep in deps:
            name = dep["name"]

            if name in self.resolved:
                continue

            print(f"Resolving {name}")
            dest = os.path.join(DEPS_DIR, name)

            if dep["source"] == "git":
                commit = self._resolve_git(dep, dest)

            elif dep["source"] == "path":
                self._resolve_path(dep, dest)
                commit = None

            else:
                raise ValueError(f"Unknown source {dep['source']}")

            self.resolved[name] = {"version": dep.get("version"), "commit": commit}

            # 🔥 recursive dependency resolution
            sub_project = os.path.join(dest, "sysml-project.yml")
            if os.path.exists(sub_project):
                self.resolve_project(sub_project)

    def _resolve_git(self, dep, dest):
        url = dep["url"]
        version = dep.get("version", "main")

        if not os.path.exists(dest):
            subprocess.run(["git", "clone", url, dest], check=True)

        subprocess.run(["git", "checkout", version], cwd=dest, check=True)

        # get commit hash (for lock file)
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=dest, capture_output=True, text=True
        )

        return result.stdout.strip()

    def _resolve_path(self, dep, dest):
        src = dep["path"]

        if not os.path.exists(dest):
            shutil.copytree(src, dest)


class PackageStructure:
    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.MANIFEST = project_dir / "sysml-project.yml"


def main():
    project_dir = Path(
        "/mnt/c/Users/SINKAA/Desktop/code/mons_wp1/SysMLInfra/examples/bilgepump"
    )
    resolver = Resolver(project_dir=project_dir)
    ps = PackageStructure(project_dir)

    project = resolver.resolve_project(ps.MANIFEST)

    write_lockfile(resolver.resolved, project_dir=project_dir)

    build_package(project, project_dir)


if __name__ == "__main__":
    main()
