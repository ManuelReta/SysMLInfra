import yaml
from pathlib import Path
import zipfile
import os


def write_lockfile(resolved, project_dir: Path, lock_file: str = "sysml-lock.yml"):
    data: dict[str, dict] = {"dependencies": {}}

    for name, info in resolved.items():
        data["dependencies"][name] = {
            "version": info["version"],
            "resolved": info["commit"],
        }

    with open(project_dir / lock_file, "w") as f:
        yaml.dump(data, f)


def build_package(project: dict, project_dir: Path, lock_file: str = "sysml-lock.yml"):
    build_dir = project_dir / "build"
    build_dir.mkdir(exist_ok=True)

    zip_path = build_dir / f"{project['publish_root']}.zip"

    with zipfile.ZipFile(zip_path, "w") as z:
        for layer in project.get("layers", []):
            full_path = project_dir / layer

            if full_path.exists():
                z.write(full_path, arcname=layer)

        deps_dir = project_dir / "deps"
        for root, _, files in os.walk(deps_dir):
            for f in files:
                full_path = Path(root) / f
                arcname = full_path.relative_to(project_dir)

                z.write(full_path, arcname=arcname)

        z.write(project_dir / "sysml-project.yml", arcname="sysml-project.yml")

        lock_path = project_dir / lock_file
        if lock_path.exists():
            z.write(lock_path, arcname=lock_file)

    print(f"Built {zip_path}")
