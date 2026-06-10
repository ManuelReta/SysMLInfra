"""
conftest.py — shared fixtures for the SysMLInfra test suite.

Adds the repo root and scripts/ directory to sys.path so that verify.py,
fault_tracer, and formal_analysis can be imported without installation.
"""

from dotenv import load_dotenv
from sys_infra.environment import EXAMPLES_BILGEPUMP_DIR
import pytest

load_dotenv()


@pytest.fixture(scope="session")
def manifest_path() -> str:
    return str(EXAMPLES_BILGEPUMP_DIR / "sysml-project.yml")


@pytest.fixture(scope="session")
def bilgepump_dir() -> str:
    return str(EXAMPLES_BILGEPUMP_DIR)
