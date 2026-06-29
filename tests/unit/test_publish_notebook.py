"""
tests/unit/test_publish_notebook.py

Unit tests for sys_infra/publish_notebook.py — the project-agnostic publish
notebook generator. No SysML kernel required (notebook is built, not executed).
"""

import pytest

from sys_infra.publish_notebook import (
    build_publish_notebook,
    parse_publish_manifest,
)

pytest.importorskip("nbformat")


def _write_project(tmp_path, *, publish_root=True, assertions=False):
    """Create a minimal two-layer SysML project with a manifest."""
    (tmp_path / "Library.sysml").write_text(
        "package Demo_Library {\n    attribute def Foo;\n}\n", encoding="utf-8"
    )
    (tmp_path / "Architecture.sysml").write_text(
        "package Demo_Architecture {\n    part def Sys;\n}\n", encoding="utf-8"
    )
    manifest = "name: DemoSystem\n"
    if publish_root:
        manifest += "publish_root: Demo\n"
    if assertions:
        manifest += "assertions_module: demo_assertions\n"
        (tmp_path / "demo_assertions.py").write_text(
            "ASSERTIONS = [\n"
            "    {'id': 'A1', 'fqn': 'Demo::check', 'layer': 'Analysis',\n"
            "     'requirement': 'REQ-1', 'kind': 'assert', 'expected': True,\n"
            "     'note': 'n'},\n"
            "]\n",
            encoding="utf-8",
        )
    (tmp_path / "sysml-project.yml").write_text(
        manifest + "layers:\n  - Library.sysml\n  - Architecture.sysml\n",
        encoding="utf-8",
    )
    return tmp_path


class TestParseManifest:
    def test_publish_root_used_when_present(self, tmp_path):
        _write_project(tmp_path, publish_root=True)
        root, layers, assertions = parse_publish_manifest(
            tmp_path / "sysml-project.yml"
        )
        assert root == "Demo"
        assert layers == ["Library.sysml", "Architecture.sysml"]
        assert assertions is None

    def test_falls_back_to_name(self, tmp_path):
        _write_project(tmp_path, publish_root=False)
        root, _, _ = parse_publish_manifest(tmp_path / "sysml-project.yml")
        assert root == "DemoSystem"

    def test_assertions_module_parsed(self, tmp_path):
        _write_project(tmp_path, assertions=True)
        _, _, assertions = parse_publish_manifest(tmp_path / "sysml-project.yml")
        assert assertions == "demo_assertions"


class TestBuildNotebook:
    def test_publishes_under_publish_root(self, tmp_path):
        _write_project(tmp_path)
        nb, root = build_publish_notebook(tmp_path, "sysml")
        assert root == "Demo"
        sources = [c.source for c in nb.cells]
        assert "%publish Demo" in sources
        # Umbrella imports the declared package of every layer.
        umbrella = next(s for s in sources if "public import" in s)
        assert "public import Demo_Library::*;" in umbrella
        assert "public import Demo_Architecture::*;" in umbrella

    def test_version_embedded_as_comment(self, tmp_path):
        _write_project(tmp_path)
        nb, _ = build_publish_notebook(tmp_path, "sysml", version="abc123")
        assert any("// model version: abc123" in c.source for c in nb.cells)

    def test_no_eval_cells_without_assertions(self, tmp_path):
        _write_project(tmp_path, assertions=False)
        nb, _ = build_publish_notebook(tmp_path, "sysml")
        assert not any(c.source.startswith("%eval") for c in nb.cells)

    def test_eval_cells_tagged_from_assertions(self, tmp_path):
        _write_project(tmp_path, assertions=True)
        nb, _ = build_publish_notebook(tmp_path, "sysml")
        eval_cells = [c for c in nb.cells if c.source.startswith("%eval")]
        assert len(eval_cells) == 1
        assert eval_cells[0].source == "%eval Demo::check"
        assert eval_cells[0].metadata["assertion"]["id"] == "A1"

    def test_missing_package_declaration_raises(self, tmp_path):
        _write_project(tmp_path)
        (tmp_path / "Library.sysml").write_text(
            "// no package here\n", encoding="utf-8"
        )
        with pytest.raises(ValueError, match="No top-level 'package"):
            build_publish_notebook(tmp_path, "sysml")
