from resolver.resolver import Resolver
from sys_infra.environment import INTEGRATION_EXAMPLES_DIR

import pytest

from sys_infra.kernel_evaluation import Pipeline


@pytest.mark.sysmlkernel
def test_layered_pump() -> None:
    project_dir = INTEGRATION_EXAMPLES_DIR / "layered_simple_pump"
    resolver = Resolver(project_dir=project_dir)

    resolver()

    p = Pipeline(project_dir)
    results = p(publish=False)
    assert results


@pytest.mark.sysmlkernel
def test_rollup() -> None:
    project_dir = INTEGRATION_EXAMPLES_DIR / "rollup"
    resolver = Resolver(project_dir=project_dir)

    resolver()

    p = Pipeline(project_dir)
    results = p(publish=False)
    assert results


@pytest.mark.sysmlkernel
def test_simple_pump() -> None:
    project_dir = INTEGRATION_EXAMPLES_DIR / "simple_pump"
    resolver = Resolver(project_dir=project_dir)

    resolver()

    p = Pipeline(project_dir)
    results = p(publish=False)
    assert results
