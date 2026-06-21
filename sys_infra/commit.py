import os
import sys
import json
from typing import Any
import requests
from pathlib import Path
import pandas as pd


def get_host() -> str:
    return "http://localhost:9000"


API_BASE = get_host()
SCRIPT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
HEADERS = {"Accept": "application/json"}


def check_api_server() -> bool:
    print(f"Checking API server at {API_BASE}...")
    try:
        r = requests.get(f"{API_BASE}/", timeout=5)
        r.raise_for_status()
        print(f"  Server ready (HTTP {r.status_code})")
        return True
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


def get_all_elements(base_url: str, project_id: str, commit_id: str):
    url = (
        f"{base_url}/projects/{project_id}/commits/{commit_id}/elements?page[size]=2000"
    )
    r = requests.get(url)
    r.raise_for_status()
    return r.json()


def update_numeric_literal(
    project_id: str,
    branch_id: str,
    updated: dict,
    new_value: float,
    previous_commit: str,
    literal_id: str,
):
    payload = {
        "@type": "Commit",
        "branch": {"@id": branch_id},
        "message": f"Update maxPressure to {new_value}",
        "change": [
            {
                "@type": "DataVersion",
                "payload": {
                    "@id": literal_id,
                    "@type": "LiteralRational",
                    "value": new_value,
                },
                "identity": {"@id": literal_id},
            },
        ],
        "previousCommit": {"@id": previous_commit},
    }

    r = requests.post(
        f"{get_host()}/projects/{project_id}/commits",
        headers={"Content-Type": "application/json"},
        json=payload,
    )

    if not r.ok:
        print(r.text)

    r.raise_for_status()


def update_target_parameter(
    project_name: str, parameter_name: str, new_value: float, unit: str
):
    project, branch_id, commit_id = get_project_info(project_name=project_name)
    # TODO You should also have to specify the component you are
    #  interested in as there might be multiple parameters with
    # the same name in different components.
    target_parameter, target_unit = get_target_parameter(
        project_id=project["@id"], commit_id=commit_id, part_name=parameter_name
    )

    if unit != target_unit["declaredShortName"]:
        print(
            f"Unit mismatch: provided unit {unit} does not match target parameter unit {target_unit['declaredShortName']}"
        )
        raise ValueError("Unit mismatch")
    print(
        f"Updating parameter {parameter_name} with id {target_parameter['@id']} to new value {new_value} {unit} from {target_parameter['value']} {target_unit['declaredShortName']}"
    )

    updated = target_parameter.copy()
    updated["value"] = new_value

    update_numeric_literal(
        project_id=project["@id"],
        branch_id=branch_id,
        updated=updated,
        new_value=new_value,
        previous_commit=commit_id,
        literal_id=target_parameter["@id"],
    )


def get_packages(project_id: str) -> pd.DataFrame:
    host = get_host()
    parts_tree_project_id = project_id

    query_input = {
        "@type": "Query",
        "select": [
            "@id",
            "qualifiedName",
            "name",
            "owner",
            "@type",
            "owningNamespace",
            "visibility",
            "import",
        ],
        "where": {
            "@type": "PrimitiveConstraint",
            "operator": "=",
            "property": "@type",
            "value": ["Package"],
        },
    }

    query_url = f"{host}/projects/{parts_tree_project_id}/query-results?page[size]=50"

    query_response = requests.post(query_url, json=query_input)

    if query_response.status_code == 200:
        query_response_json = query_response.json()

        df = pd.DataFrame(
            {
                "Package Name": [],
                "Package ID": [],
                "Owner": [],
                "@type": [],
                "owningNamespace": [],
                "visibility": [],
                "import": [],
            }
        )
        for p in query_response_json:
            df = pd.concat(
                [
                    df,
                    pd.DataFrame(
                        {
                            "Package Name": [p["name"]],
                            "Package ID": [p["@id"]],
                            "Owner": [p.get("owner")],
                            "@type": [p.get("@type")],
                            "owningNamespace": [p.get("owningNamespace")],
                            "visibility": [p.get("visibility")],
                            "import": [p.get("import")],
                        }
                    ),
                ],
                ignore_index=True,
            )
    return df


def find_parts_by_type(elements: list, part_type: str = "AttributeUsage") -> list:
    return [e for e in elements if e["@type"] == part_type]


def find_part_by_name(elements: list, name: str) -> list:
    return [e for e in elements if e.get("declaredName") == name]


def get_target_parameter(project_id: str, commit_id: str, part_name: str):
    # TODO Do some checking that the paramer is in the correct package and maybe component.
    _ = get_packages(project_id=project_id)

    all_elements_in_project = get_all_elements(
        base_url=get_host(), project_id=project_id, commit_id=commit_id
    )
    # TODO Duplicates should be removed below here.
    candidate_parts_by_type = find_parts_by_type(
        elements=all_elements_in_project, part_type="LiteralRational"
    )

    candidate_unit_attribute_usage_parts_by_type = find_parts_by_type(
        elements=all_elements_in_project, part_type="AttributeUsage"
    )
    target_part_by_name = find_part_by_name(
        elements=all_elements_in_project, name=part_name
    )

    # The candidate part might be in the candidate unit list so this is filtered out such that it wont be hit.
    filtered_candidate_unit_attribute_usage_parts_by_type = [
        x
        for x in candidate_unit_attribute_usage_parts_by_type
        if x not in target_part_by_name
    ]

    target_parameter = lookup(
        all_elements_in_project, target_part_by_name, candidate_parts_by_type
    )
    target_unit = lookup(
        all_elements_in_project,
        target_part_by_name,
        filtered_candidate_unit_attribute_usage_parts_by_type,
    )
    if len(target_parameter) != 1:
        raise ValueError(
            f"Expected exactly one target parameter, but found {len(target_parameter)}. Check if the parameter name is correct and unique."
        )
    if len(target_unit) != 1:
        print(
            f"Expected exactly one target unit, but found {len(target_unit)}. Parameter may not have a unit."
        )
        target_unit = [{"declaredShortName": None}]
    return target_parameter[0], target_unit[0]


def find_literal_rationals_from_part(start_element, elements_by_id, candidate_ids):
    found = []
    visited = set()

    def recurse(element):
        if not isinstance(element, dict):
            return

        el_id = element.get("@id")

        # Ensure el_id is a string
        if not isinstance(el_id, str):
            return

        if el_id in visited:
            return

        visited.add(el_id)

        # Check if it's a match
        if el_id in candidate_ids:
            found.append(element)
            return

        # Traverse ownedRelationship
        for rel_ref in element.get("ownedRelationship", []):
            rel_id = rel_ref.get("@id") if isinstance(rel_ref, dict) else None
            if not rel_id:
                continue

            rel = elements_by_id.get(rel_id)
            if not rel:
                continue

            # xplore all references inside relationship
            for key, value in rel.items():
                # Case 1: single reference
                if isinstance(value, dict):
                    ref_id = value.get("@id")
                    if isinstance(ref_id, str) and ref_id in elements_by_id:
                        recurse(elements_by_id[ref_id])

                # Case 2: list of references
                elif isinstance(value, list):
                    for v in value:
                        if isinstance(v, dict):
                            ref_id = v.get("@id")
                            if isinstance(ref_id, str) and ref_id in elements_by_id:
                                recurse(elements_by_id[ref_id])

    recurse(start_element)
    return found


def lookup(all_elements_in_project, target_part_by_name, candidate_parts_by_type):
    elements_by_id = {el["@id"]: el for el in all_elements_in_project}

    candidate_ids = {el["@id"] for el in candidate_parts_by_type}
    target_part = target_part_by_name[0]

    matching_literals = find_literal_rationals_from_part(
        target_part, elements_by_id, candidate_ids
    )
    return matching_literals


def get_target_parameter_and_unit(project_name: str, parameter_name: str):
    project, _, commit_id = get_project_info(project_name=project_name)

    target_parameter, target_unit = get_target_parameter(
        project_id=project["@id"], commit_id=commit_id, part_name=parameter_name
    )
    print(
        f"Got parameter {parameter_name} (id: {target_parameter['@id']}): {target_parameter['value']} {target_unit['declaredShortName']}"
    )
    return target_parameter, target_unit


def main() -> None:
    # target_parameter, target_unit = get_target_parameter_and_unit(project_name="SimplePump", parameter_name = "flowRate")

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
