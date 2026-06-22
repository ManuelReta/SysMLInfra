from sys_infra.environment import REPO_ROOT


def test_simple_pump():
    path = REPO_ROOT / "test_models" / "simple_pump" / "simple_pump.sysml"
    print(path)
