"""
conftest.py — shared fixtures for the SysMLInfra test suite.

Adds the repo root and scripts/ directory to sys.path so that verify.py,
fault_tracer, and formal_analysis can be imported without installation.
"""

import os
import subprocess
import time

import requests

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


def wait_for_api(url, timeout=1800):
    for _ in range(timeout):
        try:
            r = requests.get(url)
            if r.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("API did not become ready")


def pytest_addoption(parser):
    parser.addoption("--no-docker", action="store_true")


@pytest.fixture(scope="session", autouse=True)
def docker_compose(request):
    LOCAL_RUN = os.getenv("LOCAL")
    if request.config.getoption("--no-docker"):
        yield
        return

    # Base stack is always required; behind the DNV proxy (default, no LOCAL set)
    # the zscaler overlay is layered on top. Tests stay ephemeral — the persist
    # overlay (named volume) is intentionally NOT included here.
    compose_files = ["-f", "docker-compose.yaml"]
    if not LOCAL_RUN:
        compose_files += ["-f", "docker-compose-local.yaml"]

    subprocess.run(["docker", "compose", *compose_files, "up", "-d"], check=True)

    wait_for_api("http://localhost:9000")

    yield
    subprocess.run(["docker", "compose", *compose_files, "down"], check=True)
