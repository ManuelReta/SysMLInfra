import pytest

from sys_infra.api_utils import create_project, delete_project_by_name, get_project_ids
from sys_infra.commit import get_host


@pytest.mark.integration
def test_create_project(docker_compose) -> None:
    project_name = "TestingIntegrationProject"
    project_response = create_project(api_base=get_host(), project_name=project_name)

    assert not isinstance(project_response, int), "Failed to create project"

    assert project_response["name"] == project_name, "Project response ok"
    projects = get_project_ids()
    project_names = [project["name"] for project in projects]
    assert project_name in project_names, f"Project: {project_name} found"
    delete_project_by_name(project_name=project_name)
    projects = get_project_ids()
    project_names = [project["name"] for project in projects]
    assert project_name not in project_names, f"Project: {project_name} not found"
