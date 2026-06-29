"""Generalized publish-notebook generator (project-agnostic).

Ported and generalized from ``examples/bilgepump/make_publish_notebook.py``.

Builds a headless-runnable notebook that publishes a SysML v2 model as ONE
unified project (stable name = ``publish_root``):

  1. load every layer (from the manifest ``layers:``) into the kernel verbatim,
     in strict import order;
  2. emit an umbrella ``package <publish_root> { public import <Layer>::*; }``
     cell that re-exports all layers, then ``%publish <publish_root>`` ONCE; and
  3. emit one tagged ``%eval`` cell per assertion (when an ``assertions_module``
     is declared in the manifest) so ``materialize_sysml_values.py`` can read the
     executed verdicts into the ``sysml_assertions`` table.

Publishing one umbrella package to one stable project name keeps the project
UUID stable across republishes (a republish is just a new commit on that
project), which is what downstream queries depend on.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from typing import Any

from sys_infra.commit import get_host

_PACKAGE_RE = re.compile(r"package\s+'?([\w]+)'?\s*\{")
_ASSERTION_KEYS = ("id", "fqn", "layer", "requirement", "kind", "expected", "note")


class ManifestParser:
    """Parses the SysML project manifest and layer files (file parsing only)."""

    PACKAGE_RE = _PACKAGE_RE

    def parse_manifest(self, path: Path) -> tuple[str, list[str], str | None]:
        """Return ``(publish_root, layers, assertions_module)`` from the manifest.

        ``publish_root`` falls back to the manifest ``name`` when not set.
        ``assertions_module`` is an optional python module (without ``.py``)
        sitting next to the manifest; when absent no ``%eval`` cells are emitted.
        Uses the same forgiving line-oriented parsing as the rest of the
        toolchain (no PyYAML dependency).
        """
        publish_root = ""
        name = ""
        layers: list[str] = []
        assertions_module: str | None = None
        in_layers = False
        for raw in path.read_text(encoding="utf-8").splitlines():
            s = raw.strip()
            if not s or s.startswith("#"):
                continue
            if s.startswith("name:"):
                name = s.split(":", 1)[1].strip().strip("\"'")
                in_layers = False
            elif s.startswith("publish_root:"):
                publish_root = s.split(":", 1)[1].strip().strip("\"'")
                in_layers = False
            elif s.startswith("assertions_module:"):
                assertions_module = s.split(":", 1)[1].strip().strip("\"'")
                in_layers = False
            elif s == "layers:":
                in_layers = True
            elif in_layers and s.startswith("- "):
                layers.append(s[2:].strip())
            elif in_layers and not s.startswith("- "):
                in_layers = False
        return (publish_root or name or "SysMLProject"), layers, assertions_module

    def declared_package(self, text: str, filename: str) -> str:
        """Top-level package name declared in a layer (e.g. BilgePump_Library)."""
        match = self.PACKAGE_RE.search(text)
        if not match:
            raise ValueError(f"No top-level 'package <Name> {{' found in {filename}")
        return match.group(1)

    def load_assertions(
        self, project_dir: Path, module_name: str | None
    ) -> list[dict[str, Any]]:
        """Import ``<project_dir>/<module_name>.py`` and return its ASSERTIONS."""
        if not module_name:
            return []
        mod_path = project_dir / f"{module_name}.py"
        if not mod_path.exists():
            return []
        spec = importlib.util.spec_from_file_location(module_name, mod_path)
        if spec is None or spec.loader is None:
            return []
        module = importlib.util.module_from_spec(spec)
        # Resolve the assertions module's own imports relative to the project.
        sys.path.insert(0, str(project_dir))
        try:
            spec.loader.exec_module(module)
        finally:
            sys.path.pop(0)
        return list(getattr(module, "ASSERTIONS", []))


class NotebookBuilder:
    """Builds the publish notebook in memory (no kernel; pure assembly)."""

    def __init__(self, parser: ManifestParser | None = None) -> None:
        self.parser = parser or ManifestParser()

    def build(
        self,
        project_dir: Path,
        kernel_name: str,
        version: str | None = None,
    ) -> tuple[Any, str]:
        """Build the unified publish notebook. Returns ``(notebook, publish_root)``."""
        import nbformat  # local import: CI-only dependency

        manifest = project_dir / "sysml-project.yml"
        publish_root, layers, assertions_module = self.parser.parse_manifest(manifest)
        if not layers:
            raise ValueError(f"No 'layers:' entries found in {manifest}")

        nb = nbformat.v4.new_notebook()
        nb.metadata["kernelspec"] = {
            "display_name": "SysML",
            "language": "sysml",
            "name": kernel_name,
        }

        # 1. Load every layer into the kernel verbatim, in import order.
        packages: list[str] = []
        for filename in layers:
            source = (project_dir / filename).read_text(encoding="utf-8")
            packages.append(self.parser.declared_package(source, filename))
            nb.cells.append(nbformat.v4.new_code_cell(source))

        # 2. Umbrella package re-exporting every layer, then a single publish.
        imports = "\n".join(f"    public import {pkg}::*;" for pkg in packages)
        version_comment = f"// model version: {version}\n" if version else ""
        umbrella = (
            f"{version_comment}package {publish_root} {{\n"
            f"    private import ScalarValues::*;\n{imports}\n}}"
        )
        nb.cells.append(nbformat.v4.new_code_cell(umbrella))
        nb.cells.append(nbformat.v4.new_code_cell(f"%repo {get_host()}"))
        nb.cells.append(nbformat.v4.new_code_cell(f"%publish {publish_root}"))

        # 3. One tagged %eval cell per assertion (read back by the materializer).
        for assertion in self.parser.load_assertions(project_dir, assertions_module):
            cell = nbformat.v4.new_code_cell(f"%eval {assertion['fqn']}")
            cell.metadata["assertion"] = {k: assertion.get(k) for k in _ASSERTION_KEYS}
            nb.cells.append(cell)

        return nb, publish_root


class KernelRunner:
    """Kernel interfacing: discover the SysML v2 kernel and run a notebook headless.

    Owns the kernel name and is the single place that talks to ``nbclient``. A
    fresh instance per publish keeps the kernel identity explicit and testable.
    """

    def __init__(self, kernel_name: str | None = None) -> None:
        self._kernel_name = kernel_name

    @staticmethod
    def discover_kernel() -> str | None:
        """Return the installed SysML v2 jupyter kernel name, or ``None``."""
        try:
            import jupyter_client  # local import: optional dependency

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

    @property
    def kernel_name(self) -> str | None:
        if self._kernel_name is None:
            self._kernel_name = self.discover_kernel()
        return self._kernel_name

    def execute(self, nb: Any, out_path: Path, timeout: int = 600) -> None:
        """Execute *nb* headlessly and persist it to *out_path*.

        Always writes the (partially) executed notebook so a downstream
        materializer can read tagged outputs even on failure. Raises on a kernel
        cell error; callers translate that into an exit code.
        """
        import nbformat  # local import: CI-only dependency
        from nbclient import NotebookClient

        try:
            NotebookClient(nb, timeout=timeout, kernel_name=self.kernel_name).execute()
        finally:
            nbformat.write(nb, str(out_path))


def parse_publish_manifest(path: Path) -> tuple[str, list[str], str | None]:
    """Module-level shim → :meth:`ManifestParser.parse_manifest`."""
    return ManifestParser().parse_manifest(path)


def build_publish_notebook(
    project_dir: Path,
    kernel_name: str,
    version: str | None = None,
) -> tuple[Any, str]:
    """Module-level shim → :meth:`NotebookBuilder.build`."""
    return NotebookBuilder().build(project_dir, kernel_name, version=version)
