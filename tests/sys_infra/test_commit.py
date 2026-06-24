import pytest
from sys_infra.api_utils import get_project_ids
from sys_infra.commit import (
    check_api_server,
    create_project,
    get_host,
)
from sys_infra.environment import EXAMPLES_BILGEPUMP_DIR


def test_get_host():
    assert get_host() == "http://localhost:9000"


@pytest.mark.integration
def test_check_api_server_success(docker_compose):
    assert check_api_server(), "Did not make connection to local sysml v2 api "


def test_check_api_server_failure(monkeypatch):
    def mock_get(*args, **kwargs):
        raise Exception("Connection failed")

    monkeypatch.setattr("sys_infra.commit.requests.get", mock_get)

    with pytest.raises(SystemExit):
        check_api_server()


@pytest.mark.integration
def test_create_project() -> None:
    project_dir = EXAMPLES_BILGEPUMP_DIR
    check_api_server()
    project_id = create_project(project_dir=project_dir)
    print(project_id)
    projects = get_project_ids()
    print(projects)
