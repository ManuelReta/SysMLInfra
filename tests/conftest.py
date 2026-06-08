"""
conftest.py — shared fixtures for the SysMLInfra test suite.

Adds the repo root and scripts/ directory to sys.path so that verify.py,
fault_tracer, and formal_analysis can be imported without installation.
"""
import sys
import pathlib

# Repo root is two levels above this file (tests/conftest.py → repo root)
REPO_ROOT = pathlib.Path(__file__).parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
BILGEPUMP_DIR = REPO_ROOT / "bilgepump"

for p in (str(REPO_ROOT), str(SCRIPTS_DIR), str(BILGEPUMP_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest


@pytest.fixture(scope="session")
def repo_root():
    return REPO_ROOT


@pytest.fixture(scope="session")
def manifest_path(repo_root):
    return str(repo_root / "sysml-project.yml")


@pytest.fixture(scope="session")
def bilgepump_dir(repo_root):
    return repo_root / "bilgepump"
