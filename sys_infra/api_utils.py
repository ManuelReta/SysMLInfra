import requests

from sys_infra.commit import get_host


def delete_project(project_id: str):
    API_BASE = get_host()
    r = requests.delete(f"{API_BASE}/projects/{project_id}")
    if r.status_code == 204:
        print(f"Project {project_id} deleted successfully.")
    else:
        print(f"Failed to delete project {project_id}: HTTP {r.status_code} - {r.text}")


def get_project_ids() -> list:
    host = get_host()

    projects_url = f"{host}/projects"
    response = requests.get(projects_url)
    if response.status_code == 200:
        projects = response.json()
        for project in projects:
            print(f"Project Name: {project['name']}, ID: {project['@id']}")
        return projects
    else:
        print(f"Failed to fetch projects: {response.status_code} - {response.text}")
        return []


def get_project_by_name(project_name: str):
    """Fetches the project with the given name and returns its details, including ID."""

    projects = get_project_ids()
    target_project = None
    for project in projects:
        if project["name"] == project_name:
            print(f"Found project: {project['name']} with ID: {project['@id']}")
            target_project = project
    return target_project


def delete_project_by_name(project_name: str):
    project = get_project_by_name(project_name=project_name)
    if project:
        delete_project(project_id=project["@id"])
    else:
        print(f"Project with name '{project_name}' not found. Cannot delete.")
