from sys_infra.environment import INTEGRATION_EXAMPLES_DIR
from sys_infra.verify import Pipeline


def test_layered_pump() -> None:
    p = Pipeline(INTEGRATION_EXAMPLES_DIR / "layered_simple_pump")
    results = p(publish=False)
    assert results


def test_rollup() -> None:
    p = Pipeline(INTEGRATION_EXAMPLES_DIR / "rollup")
    results = p(publish=False)
    assert results


def test_simple_pump() -> None:
    p = Pipeline(INTEGRATION_EXAMPLES_DIR / "simple_pump")
    results = p(publish=False)
    assert results
