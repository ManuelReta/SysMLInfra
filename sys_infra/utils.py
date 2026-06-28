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


def parse_sysml(text):
    package_match = re.search(r"package\s+(\w+)", text)
    package = package_match.group(1) if package_match else "Unknown"

    # ---------------------------
    # Parse requirement definitions
    # ---------------------------
    req_defs = {}
    for match in re.finditer(r"requirement\s+def\s+(\w+)\s*{([^}]*)}", text, re.DOTALL):
        name = match.group(1)
        body = match.group(2)

        # find "attribute req"
        attr_match = re.search(r"attribute\s+(\w+)\s*:", body)
        if attr_match:
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

    return package, req_usages, parts


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
