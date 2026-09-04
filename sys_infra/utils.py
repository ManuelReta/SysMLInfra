import logging
import os
from pathlib import Path
import sys
from typing import Any
import nbformat
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError
from sys_infra.commit import get_host
from sys_infra.environment import ManuelPackageStructure, SysandPackageStructure
import re
import yaml


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _supports_color() -> bool:
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


_USE_COLOR = _supports_color()


def _c(code: str, text: str) -> str:
    if not _USE_COLOR:
        return text
    return f"\033[{code}m{text}\033[0m"


def green(t: str) -> str:
    return _c("32", t)


def red(t: str) -> str:
    return _c("31;1", t)


def yellow(t: str) -> str:
    return _c("33", t)


def cyan(t: str) -> str:
    return _c("36", t)


def bold(t: str) -> str:
    return _c("1", t)


def dim(t: str) -> str:
    return _c("2", t)


# ── Kernel path: nbclient execution ──────────────────────────────────────────
def _discover_sysml_kernel() -> str | None:
    try:
        import jupyter_client

        installed = jupyter_client.kernelspec.find_kernel_specs()
    except Exception:
        return None
    for candidate in ("sysml2", "sysml"):
        if candidate in installed:
            return candidate
    for k in installed:
        if "sysml" in k.lower():
            return k
    return None


class SysMLProjectReader:
    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.manifest_path = project_dir / "sysml-project.yml"
        self.root_deps_dir = project_dir / "deps"

        if not self.project_dir.exists():
            raise FileNotFoundError(f"Project directory not found: {project_dir}")

        self.visited: set = set()

        self.name = ""
        self.layers: list[Path] = []
        self.validation_layers: list[Path] | None = None
        self._load()

    def _load(self) -> None:
        all_layers: list[Path] = []
        validation_layers: list[Path] = []

        self._resolve_project(self.project_dir, all_layers, validation_layers)

        self.layers = all_layers
        self.validation_layers = validation_layers if validation_layers else None

    def _resolve_project(
        self, project_dir: Path, all_layers: list[Path], validation_layers: list[Path]
    ) -> None:
        manifest_path: Path = project_dir / "sysml-project.yml"

        if not manifest_path.exists():
            sysml_files = sorted(project_dir.glob("*.sysml"))

            for f in sysml_files:
                self._add_layer(f.resolve(), all_layers)

            return

        with open(manifest_path) as ff:
            data = yaml.safe_load(ff)

        if not self.name:
            self.name = data.get("name", project_dir.name)

        deps = data.get("dependencies", [])

        for dep in deps:
            dep_name = dep["name"]
            dep_dir = self.root_deps_dir / dep_name

            if not dep_dir.exists():
                raise FileNotFoundError(f"Dependency not found: {dep_dir}")

            if dep_dir in self.visited:
                continue

            self.visited.add(dep_dir)
            self._resolve_project(dep_dir, all_layers, validation_layers)

        for layer in data.get("layers", []):
            full_path = (project_dir / layer).resolve()
            self._add_layer(full_path, all_layers)

        for layer in data.get("validation_layers", []) or []:
            full_path = (project_dir / layer).resolve()
            validation_layers.append(full_path)

    def _add_layer(self, path: Path, layer_list: list[Path]):
        if not path.exists():
            raise FileNotFoundError(f"Layer not found: {path}")

        if path not in layer_list:
            layer_list.append(path)

    def get_layers(self) -> list[Path]:
        return self.layers

    def get_validation_layers(self) -> list[Path] | None:
        return self.validation_layers

    def get_name(self) -> str:
        return self.name


# ── Manifest reader (same logic as ci_kernel_validate.py) ────────────────────
def _read_manifest(path: str) -> tuple[str, list[str], list[str] | None]:
    name = "SysMLProject"
    layers: list[str] = []
    validation_layers: list[str] | None = None
    current_list: list[str] | None = None
    with open(path) as fh:
        for raw in fh:
            s = raw.strip()
            if not s or s.startswith("#"):
                continue
            if s.startswith("name:"):
                name = s.split(":", 1)[1].strip().strip("\"'")
                current_list = None
            elif s == "layers:":
                current_list = layers
            elif s == "validation_layers:":
                validation_layers = []
                current_list = validation_layers
            elif current_list is not None and s.startswith("- "):
                current_list.append(s[2:].strip())
            elif (
                current_list is not None
                and s
                and not s.startswith("-")
                and not s.startswith("#")
            ):
                current_list = None
    return name, layers, validation_layers


def read_layers(project_dir: Path) -> tuple[str, list[str], list[str] | None, Path]:
    if not project_dir.exists():
        print(red(f"ERROR: Project directory not found: {project_dir}"))
        sys.exit(2)

    package_structure = ManuelPackageStructure(project_dir=project_dir)

    validation_layers: list[str] | None
    # ── Load manifest or fallback ───────────────────────────────────────────────
    if not package_structure.MANIFEST.exists():
        sysandpackage = SysandPackageStructure(project_dir)
        print(f"WARNING: sysml-project.yml not found at {package_structure.MANIFEST}")
        print("Falling back to reading .sysml files in project_dir")

        # Collect all .sysml files
        sysml_files = sorted(sysandpackage.project_dir.glob("*.sysml"))

        if not sysml_files:
            print("ERROR: No .sysml files found in project directory")
            sys.exit(2)

        # Use filenames (or full paths depending on your needs)
        all_layers = [str(f) for f in sysml_files]
        validation_layers = list(all_layers)

        # Derive a project name (optional)
        project_name = sysandpackage.project_name

    else:
        project_name, all_layers, validation_layers = _read_manifest(
            str(package_structure.MANIFEST)
        )

    if not all_layers:
        print(red("ERROR: sysml-project.yml contains no layers entries."))
        sys.exit(2)
    return project_name, all_layers, validation_layers, package_structure.MANIFEST


def run_kernel_publish(
    layer_paths: list[str], kernel_name: str, project_dir: Path, project_name: str
) -> tuple[bool, list[Any]]:
    """
    Publishes the layers bundled as one "superpackage". This is how the same project can be used.
    """
    try:
        import nbformat
        from nbclient import NotebookClient
        from nbclient.exceptions import CellExecutionError
    except ImportError as exc:
        print(red(f"ERROR: {exc}"))
        print("  Install CI dependencies:  pip install nbclient nbformat")
        sys.exit(2)

    nb = nbformat.v4.new_notebook()
    nb.metadata["kernelspec"] = {
        "display_name": "SysML v2",
        "language": "sysml",
        "name": kernel_name,
    }

    n_model_cells = 3
    all_packages = []
    package_name = f"{project_name}Super"
    super_package_prefix = f"package {package_name} {{\n\n"
    super_package_suffix = "\n }"
    super_text = super_package_prefix

    for layer_file in layer_paths:
        abs_path = os.path.join(project_dir, layer_file)

        text = _read(abs_path)
        super_text += text
        pattern = r"package\s+'?([\w:]+)'?\s*\{"
        packages = re.findall(pattern, text)
        all_packages += packages
    super_text += super_package_suffix

    nb.cells.append(nbformat.v4.new_code_cell(super_text))

    repo_cell = nbformat.v4.new_code_cell(f"%repo {get_host()}")
    publish_cell = nbformat.v4.new_code_cell(
        f"%publish {package_name} --project='{package_name}_project'"
    )
    publish_cell.metadata["tags"] = ["raises-exception"]
    nb.cells.append(repo_cell)
    nb.cells.append(publish_cell)

    client = NotebookClient(
        nb,
        timeout=300,
        kernel_name=kernel_name,
        resources={"metadata": {"path": project_dir}},
    )

    sys.stdout.flush()
    sys.stderr.flush()
    _saved_out = os.dup(1)
    _saved_err = os.dup(2)
    _devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(_devnull, 1)
    os.dup2(_devnull, 2)
    os.close(_devnull)

    _exec_error: Exception | None = None
    try:
        client.execute()
    except CellExecutionError:
        pass
    except Exception as exc:
        _exec_error = exc
    finally:
        os.dup2(_saved_out, 1)
        os.dup2(_saved_err, 2)
        os.close(_saved_out)
        os.close(_saved_err)

    if _exec_error is not None:
        print(red(f"\nKernel execution error: {_exec_error}"))
        return False, []

    cell_results: list[dict] = []
    all_ok = True
    for i in range(n_model_cells):
        cell = nb.cells[i]
        errors = [o for o in cell.get("outputs", []) if o.get("output_type") == "error"]
        cell_results.append(
            {
                "ok": not errors,
                "errors": errors,
            }
        )
        if errors:
            all_ok = False

    return all_ok, cell_results


def append_kernel_layers(layer_paths: list[Path], nb) -> tuple[bool, list[Any]]:
    """
    Publishes the layers one by on in sequence.
    """
    for layer_file in layer_paths:
        text = _read(str(layer_file))
        nb.cells.append(nbformat.v4.new_code_cell(text))
    return nb


def kernel_evaluate(
    expressions: list[str], kernel_name: str, project_dir: Path, nb
) -> list[dict[Any, Any]]:
    for expression in expressions:
        nb.cells.append(nbformat.v4.new_code_cell(expression))

    client = NotebookClient(
        nb,
        timeout=300,
        kernel_name=kernel_name,
        resources={"metadata": {"path": str(project_dir)}},
    )

    sys.stdout.flush()
    sys.stderr.flush()
    _saved_out = os.dup(1)
    _saved_err = os.dup(2)
    _devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(_devnull, 1)
    os.dup2(_devnull, 2)
    os.close(_devnull)

    _exec_error: Exception | None = None
    try:
        client.execute()
    except CellExecutionError:
        pass
    except Exception as exc:
        _exec_error = exc
    finally:
        os.dup2(_saved_out, 1)
        os.dup2(_saved_err, 2)
        os.close(_saved_out)
        os.close(_saved_err)

    if _exec_error is not None:
        print(red(f"\nKernel execution error: {_exec_error}"))
        raise ValueError(f"\nKernel execution error: {_exec_error}")

    cell_results: list[dict] = []
    for cell in nb.cells:
        out = [o for o in cell.get("outputs", [])]
        cell_results.append(
            {
                "in": cell.get("source"),
                "out": out,
            }
        )

    return cell_results


def parse_sysml(text, existing_req_defs):
    package_match = re.search(r"package\s+(\w+)", text)
    package = package_match.group(1) if package_match else "Unknown"

    logging.info(f"Parsing SysML text for package: {package}")
    # ---------------------------
    # Parse requirement definitions
    # ---------------------------
    req_defs = existing_req_defs  # {}
    for match in re.finditer(r"requirement\s+def\s+(\w+)\s*{([^}]*)}", text, re.DOTALL):
        name = match.group(1)
        body = match.group(2)

        # Unsupported SysML feature
        if re.search(r"require\s+constraint\s*{", body):
            logging.error(
                f"ERROR: Requirement '{name}' contains a "
                f"'require constraint' block. "
                f"This construct is not interpretable by the current kernel."
            )
            continue

        attr_block_match = re.search(r"attribute\s+(\w+)\s*:\s*Boolean\s*{", body)

        if attr_block_match:
            logging.info(
                f"Requirement '{name}' defines Boolean attribute "
                f"'{attr_block_match.group(1)}' using a block '{{...}}'. "
                f"This is not supported by the kernel. Use "
                f"'attribute {attr_block_match.group(1)}: Boolean = <expression>;' instead."
            )
            continue

        attr_match = re.search(r"attribute\s+(\w+)\s*:", body)
        if attr_match:
            logging.info(
                f"     Requirement '{name}' defines attribute '{attr_match.group(1)}'."
            )
            req_defs[name] = attr_match.group(1)

    # ---------------------------
    # Parse requirement usages
    # ---------------------------
    req_usages = []

    for match in re.finditer(r"requirement\s+(?:<([^>]+)>\s+)?(\w+)\s*:\s*(\w+)", text):
        tag = match.group(1)
        name = match.group(2)
        typename = match.group(3)

        attr = req_defs.get(typename)

        if attr:
            if tag:
                req_usages.append((tag, attr))
            else:
                req_usages.append((name, attr))

    parts = {}

    for match in re.finditer(r"part\s+(\w+)\s*:\s*(\w+)\s*{([^}]*)}", text, re.DOTALL):
        part_name = match.group(1)
        body = match.group(3)

        attributes = re.findall(r":>>\s*(\w+)", body)
        parts[part_name] = attributes

    logging.info(f"     Parsed requirement definitions: {req_defs}")
    logging.info(f"     Parsed requirement usages: {req_usages}")
    logging.info(f"     Parsed part definitions: {parts}")

    return package, req_usages, parts, req_defs


def generate_eval_commands(package, req_usages, parts):
    commands = []

    # Requirement evals
    for name, attr in req_usages:
        commands.append(f"%eval {package}::{name}.{attr}")

    # Part attribute evals
    for part, attrs in parts.items():
        for attr in attrs:
            commands.append(f"%eval {package}::{part}.{attr}")

    return commands


if __name__ == "__main__":
    ...
