import os
from pathlib import Path
import shutil
import subprocess
from typing import Any
import logging
import yaml
import typer

app = typer.Typer(help="SysML dependency resolver and package builder.")
DEPS_DIR = "deps"


class Resolver:
    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        os.makedirs(self.project_dir / DEPS_DIR, exist_ok=True)
        self.resolved: dict[Any, Any] = {}
        self.ps = PackageStructure

    def __call__(self):
        project = self.resolve_project(project_path=self.ps(self.project_dir).MANIFEST)
        self.write_lockfile(self.resolved, project_dir=self.project_dir)
        self.build_package_folder(project, self.project_dir)

    def resolve_project(self, project_path):
        project_dir = project_path.parent

        with open(project_path) as f:
            project = yaml.safe_load(f)

        self._resolve_dependencies(project.get("dependencies", []), project_dir)

        return project

    def _resolve_dependencies(self, deps, current_project_dir: Path):
        deps_dir = self.project_dir / "deps"
        deps_dir.mkdir(exist_ok=True)

        for dep in deps:
            name = dep["name"]

            if name in self.resolved:
                continue

            logging.info(f"Resolving {name} (from {current_project_dir})")

            dest = deps_dir / name

            if dep["source"] == "git":
                commit = self._resolve_git(dep, dest)

            elif dep["source"] == "path":
                self._resolve_path(dep, dest)
                commit = None

            else:
                raise ValueError(f"Unknown source {dep['source']}")

            self.resolved[name] = {
                "version": dep.get("version"),
                "commit": commit,
            }

            sub_project_manifest = dest / "sysml-project.yml"

            if sub_project_manifest.exists():
                self._resolve_dependencies(
                    self._read_dependencies(sub_project_manifest),
                    dest,
                )

    def _read_dependencies(self, manifest_path: Path):
        with open(manifest_path) as f:
            data = yaml.safe_load(f)
        return data.get("dependencies", [])

    def _resolve_git(self, dep, dest: Path):
        url = dep["url"]
        version = dep.get("version", "main")

        if not dest.exists():
            subprocess.run(["git", "clone", url, str(dest)], check=True)

        subprocess.run(["git", "checkout", version], cwd=dest, check=True)

        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=dest,
            capture_output=True,
            text=True,
        )

        return result.stdout.strip()

    def _resolve_path(self, dep, dest: Path):
        src_raw = dep["path"]
        src_path = (self.project_dir / src_raw).resolve()

        if not src_path.exists():
            raise FileNotFoundError(f"{src_path} not found")

        if not dest.exists():
            shutil.copytree(src_path, dest)

    @staticmethod
    def write_lockfile(resolved, project_dir: Path, lock_file: str = "sysml-lock.yml"):
        data: dict[str, dict] = {"dependencies": {}}

        for name, info in resolved.items():
            data["dependencies"][name] = {
                "version": info["version"],
                "resolved": info["commit"],
            }

        with open(project_dir / lock_file, "w") as f:
            yaml.dump(data, f)

    @staticmethod
    def build_package_folder(
        project: dict, project_dir: Path, lock_file: str = "sysml-lock.yml"
    ):
        build_dir = project_dir / "build"
        package_dir = build_dir / f"{project['name']}_{project['version']}"

        if package_dir.exists():
            shutil.rmtree(package_dir)

        package_dir.mkdir(parents=True)

        for layer in project.get("layers", []):
            src = project_dir / layer
            dest = package_dir / layer

            if src.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)

        deps_src = project_dir / "deps"
        deps_dest = package_dir / "deps"

        if deps_src.exists():
            shutil.copytree(deps_src, deps_dest)

        shutil.copy2(
            project_dir / "sysml-project.yml", package_dir / "sysml-project.yml"
        )

        lock_path = project_dir / lock_file
        if lock_path.exists():
            shutil.copy2(lock_path, package_dir / lock_file)

        logging.info(f"Built folder: {package_dir}")


class PackageStructure:
    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.manifest_file = "sysml-project.yml"
        self.MANIFEST = project_dir / self.manifest_file
        self.dependecy_dir = "deps"
        self.DEPS_DIR = project_dir / self.dependecy_dir


def example():
    project_dir = Path(
        "/mnt/c/Users/SINKAA/Desktop/code/mons_wp1/SysMLInfra/tests/sys_infra/test_models/layered_simple_pump"
    )
    resolver = Resolver(project_dir=project_dir)

    resolver()


@app.command()
def resolver(
    project_dir: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        help="Path to the SysML project directory.",
    ),
):
    """
    Resolve dependencies and build a package.
    """
    resolver = Resolver(project_dir=project_dir)
    resolver()

    typer.secho(
        f"Successfully resolved project: {project_dir} into {project_dir / 'build'}",
        fg=typer.colors.GREEN,
    )


if __name__ == "__main__":
    app()
