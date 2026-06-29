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


def create_project(api_base: str, project_name: str, timeout: int = 1500) -> int | dict:
    r = requests.post(
        f"{api_base}/projects",
        json={"@type": "Project", "name": project_name},
        timeout=1500,
    )
    if r.status_code not in (200, 201):
        return r.status_code

    return r.json()


def set_project_description(project_name: str, description: str) -> bool:
    """Best-effort: stamp a description onto the named project. Non-fatal.

    Some pilot API builds do not support updating a project, so any failure is
    swallowed and ``False`` is returned.
    """
    try:
        proj = get_project_by_name(project_name)
        if proj is None:
            return False
        r = requests.put(
            f"{get_host()}/projects/{proj['@id']}",
            json={
                "@type": "Project",
                "name": project_name,
                "description": description,
            },
            timeout=30,
        )
        return r.status_code in (200, 201, 204)
    except Exception:
        return False


class SysMLApiClient:
    """API interfacing: project CRUD against the SysML v2 pilot REST API.

    Groups the project endpoints behind one host so callers (e.g. Publisher)
    depend on a single collaborator. Methods delegate to the module functions,
    which stay as the low-level shims used elsewhere.
    """

    def __init__(self, host: str | None = None) -> None:
        self.host = host or get_host()

    def get_by_name(self, project_name: str):
        return get_project_by_name(project_name)

    def create(self, project_name: str, timeout: int = 1500) -> int | dict:
        return create_project(self.host, project_name, timeout=timeout)

    def delete_by_name(self, project_name: str) -> None:
        delete_project_by_name(project_name)

    def set_description(self, project_name: str, description: str) -> bool:
        return set_project_description(project_name, description)
