from sys_infra.environment import INTEGRATION_EXAMPLES_DIR

import pytest

from sys_infra.kernel_evaluation import Pipeline


@pytest.mark.sysmlkernel
def test_layered_pump() -> None:
    p = Pipeline(INTEGRATION_EXAMPLES_DIR / "layered_simple_pump")
    results = p(publish=False)
    assert results


@pytest.mark.sysmlkernel
def test_rollup() -> None:
    p = Pipeline(INTEGRATION_EXAMPLES_DIR / "rollup")
    results = p(publish=False)
    assert results


@pytest.mark.sysmlkernel
def test_simple_pump() -> None:
    p = Pipeline(INTEGRATION_EXAMPLES_DIR / "simple_pump")
    results = p(publish=False)
    assert results
