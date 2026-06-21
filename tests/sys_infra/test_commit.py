import pytest
from sys_infra.commit import (
    check_api_server,
    get_host,
)  # <-- replace with your file name


def test_get_host():
    assert get_host() == "http://localhost:9000"


def test_check_api_server_success(docker_compose):
    assert check_api_server(), "Did not make connection to local sysml v2 api "


def test_check_api_server_failure(monkeypatch):
    def mock_get(*args, **kwargs):
        raise Exception("Connection failed")

    monkeypatch.setattr("sys_infra.commit.requests.get", mock_get)

    with pytest.raises(SystemExit):
        check_api_server()
