import os
import sys
import json
from typing import Any
import requests
from pathlib import Path


def get_host() -> str:
    return "http://localhost:9000"


API_BASE = get_host()
SCRIPT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
HEADERS = {"Accept": "application/json"}


def check_api_server() -> None:
    print(f"Checking API server at {API_BASE}...")
    try:
        r = requests.get(f"{API_BASE}/", timeout=5)
        r.raise_for_status()
        print(f"  Server ready (HTTP {r.status_code})")
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        print("\nAPI server is not responding.")
        sys.exit(1)


def read_project_manifest(project_dir: Path) -> tuple[str, str]:
    """Read name/description from sysml-project.yml (simple parser)"""
    name = "SysMLProject"
    description = ""
    manifest = project_dir / "sysml-project.yml"

    try:
        with open(manifest) as f:
            for line in f:
                s = line.strip()
                if s.startswith("name:"):
                    name = s.split(":", 1)[1].strip().strip("'\"")
                elif s.startswith("description:"):
                    description = s.split(":", 1)[1].strip().strip("'\"")
    except FileNotFoundError:
        pass

    return name, description


def create_project(project_dir: Path) -> Any:
    print("\nCreating project...")
    name, description = read_project_manifest(project_dir=project_dir)

    r = requests.post(
        f"{API_BASE}/projects",
        json={"name": name, "description": description},
        timeout=10,
    )
    r.raise_for_status()

    project_id = r.json().get("@id", "")
    if not project_id:
        print("ERROR: Empty project ID", file=sys.stderr)
        sys.exit(1)

    print(f"  Project ID: {project_id}")

    # Persist
    lib_dir = SCRIPT_DIR / "lib"
    lib_dir.mkdir(exist_ok=True)

    with open(lib_dir / "current-project-id.txt", "w") as f:
        f.write(project_id)

    print("  Saved to lib/current-project-id.txt")

    return project_id


def parse_layers(project_dir: Path) -> list[str]:
    """Parse ordered layer list from sysml-project.yml"""
    manifest = project_dir / "sysml-project.yml"
    layers = []
    in_layers = False

    try:
        with open(manifest) as f:
            for line in f:
                s = line.strip()
                if s == "layers:":
                    in_layers = True
                elif in_layers and s.startswith("- "):
                    layers.append(s[2:].strip())
                elif (
                    in_layers and s and not s.startswith("- ") and not s.startswith("#")
                ):
                    in_layers = False
    except FileNotFoundError:
        layers = []

    return layers


def post_commit(project_id: str, filepath: Path, description: str) -> Any:
    with open(filepath) as f:
        content = f.read()

    payload = {
        "description": description,
        "changes": [{"@type": "TextualRepresentation", "body": content}],
    }

    r = requests.post(
        f"{API_BASE}/projects/{project_id}/commits", json=payload, timeout=30
    )

    try:
        r.raise_for_status()
    except Exception:
        print(f"ERROR: HTTP {r.status_code}", file=sys.stderr)
        print(r.text[:500], file=sys.stderr)
        sys.exit(1)

    return r.json().get("@id", "")


def commit_layers(project_id: str, project_dir: Path) -> None:
    print("\nCommitting SysML layers...")

    layers = parse_layers(project_dir=project_dir)
    commits = {}

    for i, layer_file in enumerate(layers, 1):
        filepath = project_dir / layer_file
        key = layer_file.replace(".sysml", "").lower()

        print(f"[{i}/{len(layers)}] {layer_file}")

        commit_id = post_commit(project_id, filepath, f"Layer: {layer_file}")

        commits[key] = commit_id
        print(f"       Commit ID: {commit_id}")

    # Save results
    lib_dir = SCRIPT_DIR / "lib"
    lib_dir.mkdir(exist_ok=True)

    with open(lib_dir / "commit-ids.json", "w") as f:
        json.dump({"project_id": project_id, "commits": commits}, f, indent=2)

    print("  Commit IDs saved to lib/commit-ids.json")


def delete_project_by_name(project_name: str) -> None:
    project = get_project_by_name(project_name=project_name)
    if project:
        delete_project(project_id=project["@id"])
    else:
        print(f"Project with name '{project_name}' not found. Cannot delete.")


def delete_project(project_id: str) -> None:
    API_BASE = get_host()
    r = requests.delete(f"{API_BASE}/projects/{project_id}")
    if r.status_code == 204:
        print(f"Project {project_id} deleted successfully.")
    else:
        print(f"Failed to delete project {project_id}: HTTP {r.status_code} - {r.text}")


def get_project_ids() -> Any:
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


def get_branches_in_project(project_id: str) -> Any:
    host = get_host()
    url = f"{host}/projects/{project_id}/branches"

    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()

    branches = r.json()
    return branches


def get_head_branch(project_id: str) -> Any:
    branches = get_branches_in_project(project_id)

    # Look for main branch in all returned branches.
    main_branch = next(b for b in branches if b.get("name") in ("main", "master"))
    return main_branch


def get_head_commit(project_id: str) -> Any:
    branch = get_head_branch(project_id)
    return branch["head"]["@id"]


def get_project_by_name(project_name: str) -> Any:
    """Fetches the project with the given name and returns its details, including ID."""

    projects = get_project_ids()
    target_project = None
    for project in projects:
        if project["name"] == project_name:
            print(f"Found project: {project['name']} with ID: {project['@id']}")
            target_project = project
    return target_project


def get_project_info(
    project_name: str,
) -> tuple[Any, Any, Any]:
    project = get_project_by_name(project_name=project_name)
    head_branch = get_head_branch(project["@id"])
    try:
        branch_id, commit_id = (
            head_branch["@id"],
            head_branch["referencedCommit"]["@id"],
        )
    except Exception:
        branch_id, commit_id = None, None
    print(
        f"Project name: {project_name}, Project ID: {project['@id']}, Branch ID: {branch_id}, Commit ID: {commit_id}"
    )
    return project, branch_id, commit_id


def main() -> None:
    project_dir = Path(
        "/mnt/c/Users/SINKAA/Desktop/code/mons_wp1/SysMLInfra/examples/bilgepump"
    )
    check_api_server()
    project_id = create_project(project_dir=project_dir)
    commit_layers(project_id=project_id, project_dir=project_dir)

    print("\n======================================================")
    print(" All layers committed.")
    print(f" Project ID : {project_id}")
    print("\n Next step:")
    print("   python verify.py")
    print("   python query-elements.py")
    print("======================================================")


if __name__ == "__main__":
    main()
