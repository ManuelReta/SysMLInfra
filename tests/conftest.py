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


def wait_for_api(url, timeout=30):
    for _ in range(timeout):
        try:
            r = requests.get(url)
            if r.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("API did not become ready")


@pytest.fixture(scope="session", autouse=True)
def docker_compose():
    LOCAL_RUN = os.getenv("LOCAL")
    running = (
        ["docker", "compose", "-f", "docker-compose.yaml", "up", "--"]
        if LOCAL_RUN
        else ["docker", "compose", "-f", "docker-compose-local.yaml", "up", "-d"]
    )

    subprocess.run(running, check=True)

    wait_for_api("http://localhost:9000")

    yield

    subprocess.run(["docker", "compose", "down"], check=True)
