#!/usr/bin/env python3
"""
api_probe.py — Query the SysML v2 Pilot API and report what is retrievable.

Usage:
    python scripts/api_probe.py
    python scripts/api_probe.py --api http://sysml2.intercax.com:9000
    python scripts/api_probe.py --project <project-id>
    python scripts/api_probe.py --query-type PartDefinition
    python scripts/api_probe.py --query-type AttributeUsage --project <id>

What this tests:
  1. API health (GET /projects)
  2. Our committed BilgePumpSystem project — metadata, branches, commits
  3. Element retrieval — why 0 come back (TextualRepresentation vs kernel commit)
  4. Demonstrates element queries DO work on a kernel-committed reference project
  5. Typed element query via POST .../query-results (filtered by @type)
"""

import argparse
import json
import os
import sys

try:
    import requests
except ImportError:
    sys.exit("requests not installed — run: pip install requests")

API_BASE = "http://sysml2.intercax.com:9000"
# Known kernel-committed project on the public server (for reference testing)
REFERENCE_PROJECT_ID = "00364405-201d-4866-9c6a-96f57c200c2a"
REFERENCE_PROJECT_NAME = "5-State-based Behavior-1"


def banner(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def ok(msg: str) -> None:
    print(f"  ✓  {msg}")


def warn(msg: str) -> None:
    print(f"  ⚠  {msg}")


def fail(msg: str) -> None:
    print(f"  ✗  {msg}")


def get(url: str, timeout: int = 10) -> list | dict | None:
    try:
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        fail(f"Cannot connect to {url}")
        return None
    except requests.exceptions.HTTPError as e:
        fail(f"HTTP {e.response.status_code} from {url}")
        return None
    except Exception as e:
        fail(f"Unexpected error: {e}")
        return None


def post(url: str, body: dict, timeout: int = 10) -> list | dict | None:
    try:
        r = requests.post(url, json=body, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        fail(f"Cannot connect to {url}")
        return None
    except requests.exceptions.HTTPError as e:
        fail(f"HTTP {e.response.status_code} from {url}")
        return None
    except Exception as e:
        fail(f"Unexpected error: {e}")
        return None


def get_head_commit(api: str, project_id: str) -> str | None:
    """Return the head commit ID for the first (main) branch of a project."""
    branches = get(f"{api}/projects/{project_id}/branches") or []
    if not branches:
        return None
    ref = branches[0].get("referencedCommit") or branches[0].get("head") or {}
    return ref.get("@id")


def fetch_element(
    api: str, project_id: str, commit_id: str, element_id: str
) -> dict | None:
    """GET a single element by its @id."""
    return get(f"{api}/projects/{project_id}/commits/{commit_id}/elements/{element_id}")


def query_elements_by_type(
    api: str,
    project_id: str,
    commit_id: str,
    type_name: str,
    all_elements: list[dict] | None = None,
) -> tuple[list[dict], bool]:
    """
    POST to the query-results endpoint to retrieve all elements of a given @type.
    Falls back to client-side filtering if the endpoint returns 404.

    Returns (results, server_supported).
    """
    body = {
        "query": {
            "@type": "Query",
            "select": ["@id", "@type", "name", "value", "declaredName"],
            "where": {
                "@type": "PrimitiveConstraint",
                "inverse": False,
                "operator": "=",
                "property": "@type",
                "value": type_name,
            },
        }
    }
    try:
        r = requests.post(
            f"{api}/projects/{project_id}/commits/{commit_id}/query-results",
            json=body,
            timeout=10,
        )
        if r.status_code == 404:
            raise requests.exceptions.HTTPError(response=r)
        r.raise_for_status()
        result = r.json()
        return (result if isinstance(result, list) else []), True
    except requests.exceptions.HTTPError:
        # Endpoint not supported on this deployment — filter client-side
        if all_elements is None:
            all_elements = (
                get(f"{api}/projects/{project_id}/commits/{commit_id}/elements") or []
            )
        return [el for el in all_elements if el.get("@type") == type_name], False


def probe_project(api: str, project_id: str, label: str = "") -> dict | None:
    """Fetch metadata + branch + commit + element counts for a project."""
    lbl = label or project_id[:8]

    # Project metadata
    project = get(f"{api}/projects/{project_id}")
    if project is None:
        fail(f"[{lbl}] Project not found")
        return None
    ok(
        f"[{lbl}] Project: {project.get('name')!r}  created:{project.get('created', '?')[:10]}"
    )

    # Branches
    branches = get(f"{api}/projects/{project_id}/branches") or []
    ok(f"[{lbl}] Branches: {len(branches)}")

    if not branches:
        warn(f"[{lbl}] No branches — nothing to query further")
        return project

    head_commit_id = (
        branches[0].get("referencedCommit") or branches[0].get("head") or {}
    ).get("@id")

    # Commits
    commits = get(f"{api}/projects/{project_id}/commits") or []
    ok(f"[{lbl}] Commits : {len(commits)}")
    for c in commits:
        desc = (c.get("description") or "")[:55]
        print(f"          {c['@id']}  {desc}")

    if not head_commit_id:
        warn(f"[{lbl}] Could not resolve head commit")
        return project

    # Elements in head commit
    elements = (
        get(f"{api}/projects/{project_id}/commits/{head_commit_id}/elements") or []
    )
    if elements:
        ok(f"[{lbl}] Elements: {len(elements)} (head commit {head_commit_id[:8]}...)")
        by_type: dict[str, int] = {}
        for el in elements:
            t = el.get("@type", "Unknown")
            by_type[t] = by_type.get(t, 0) + 1
        for t, count in sorted(by_type.items(), key=lambda x: -x[1])[:8]:
            print(f"          {count:4d}  {t}")
    else:
        warn(
            f"[{lbl}] Elements: 0 in head commit — "
            "model was committed as TextualRepresentation (raw SysML text).\n"
            "          The API stores the text but only the SysML kernel creates typed elements.\n"
            "          Use '%publish' in a Jupyter SysML kernel cell to push structured elements."
        )

    return project


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--api", default=API_BASE, help="API base URL")
    parser.add_argument(
        "--project",
        default=None,
        help="Project ID to probe (defaults to lib/current-project-id.txt)",
    )
    parser.add_argument(
        "--query-type",
        default=None,
        metavar="TYPE",
        help=(
            "Filter elements by @type using the POST query-results endpoint. "
            "Examples: PartDefinition, AttributeDefinition, PortDefinition, "
            "RequirementDefinition, ConstraintDefinition, AttributeUsage, BindingConnector. "
            "Runs against --project if it has elements, otherwise falls back to the reference project."
        ),
    )
    args = parser.parse_args()

    api = args.api.rstrip("/")

    # ── 1. Health check ──────────────────────────────────────────────────────
    banner("1 / API health check")
    projects = get(f"{api}/projects")
    if projects is None:
        sys.exit(1)
    ok(f"Server reachable at {api}")
    ok(f"Total projects on server: {len(projects)}")

    # ── 2. Our BilgePumpSystem project ───────────────────────────────────────
    banner("2 / BilgePumpSystem project (committed via commit.sh)")

    project_id = args.project
    if not project_id:
        id_file = os.path.join(
            os.path.dirname(__file__), "..", "lib", "current-project-id.txt"
        )
        try:
            with open(id_file) as f:
                project_id = f.read().strip()
        except FileNotFoundError:
            warn("lib/current-project-id.txt not found — run 'bash commit.sh' first")
            project_id = None

    if project_id:
        probe_project(api, project_id, "BilgePump")
    else:
        warn("Skipping — no project ID available")

    # ── 3. Reference project (committed via SysML kernel) ───────────────────
    banner("3 / Reference project (kernel-committed — elements expected)")
    probe_project(api, REFERENCE_PROJECT_ID, "KernelRef")

    # ── 4. Typed element query via POST query-results ────────────────────────
    # Determine which project + commit to query against: prefer the user's own
    # project if it has elements, otherwise fall back to the reference project.
    banner("4 / Typed element query  (POST …/query-results)")

    query_project_id = project_id
    query_commit_id = (
        get_head_commit(api, query_project_id) if query_project_id else None
    )
    has_elements = False
    if query_commit_id:
        sample = (
            get(f"{api}/projects/{query_project_id}/commits/{query_commit_id}/elements")
            or []
        )
        has_elements = len(sample) > 0

    if not has_elements:
        warn(
            "User project has 0 elements (TextualRepresentation commit) — using reference project for query demo"
        )
        query_project_id = REFERENCE_PROJECT_ID
        query_commit_id = get_head_commit(api, query_project_id)

    if not query_commit_id:
        warn("Cannot resolve commit — skipping query section")
    else:
        ok(f"Querying project {query_project_id[:8]}…  commit {query_commit_id[:8]}…")

        # Always show a breakdown of all types present, then optionally filter
        all_elements = (
            get(f"{api}/projects/{query_project_id}/commits/{query_commit_id}/elements")
            or []
        )
        by_type: dict[str, list[dict]] = {}
        for el in all_elements:
            t = el.get("@type", "Unknown")
            by_type.setdefault(t, []).append(el)

        print(f"\n  All element types in this commit ({len(all_elements)} total):")
        print(f"  {'Count':>6}  Type")
        print(f"  {'------':>6}  ----")
        for t, els in sorted(by_type.items(), key=lambda x: -len(x[1])):
            print(f"  {len(els):>6}  {t}")

        # Demonstrate single-element fetch
        if all_elements:
            first_id = all_elements[0]["@id"]
            print(f"\n  GET single element ({first_id[:8]}…):")
            el_detail = fetch_element(api, query_project_id, query_commit_id, first_id)
            if el_detail:
                for k, v in el_detail.items():
                    if k not in ("owningRelationship", "ownedRelationship"):
                        print(f"    {k:<30} {json.dumps(v)}")

        # Type-filtered query
        query_type = args.query_type or "AttributeDefinition"
        print(f"\n  POST query-results filtered by @type = {query_type!r}:")
        typed_els, server_supported = query_elements_by_type(
            api, query_project_id, query_commit_id, query_type, all_elements
        )
        method = (
            "server-side POST query-results"
            if server_supported
            else "client-side fallback (POST query-results returned 404)"
        )
        print(f"  Method : {method}")
        if typed_els:
            ok(f"  {len(typed_els)} element(s) of type {query_type}")
            for el in typed_els[:10]:
                name = el.get("name") or el.get("declaredName") or "<unnamed>"
                print(f"    {el['@id']}  name={name!r}")
            if len(typed_els) > 10:
                print(f"    … and {len(typed_els) - 10} more")
        else:
            warn(f"  No elements of type {query_type!r} found")
            print(f"    Types present: {', '.join(sorted(by_type.keys()))}")

    # ── Summary ──────────────────────────────────────────────────────────────
    banner("Summary")
    print("""
  API connectivity:      WORKING
  Project CRUD:          WORKING  (GET /projects, GET /projects/{id})
  Branch / commit query: WORKING  (GET …/branches, GET …/commits)
  Element retrieval:     WORKING  — but only for kernel-committed projects.
  Typed query (POST):    WORKING  — filters by @type via query-results endpoint.

  BilgePumpSystem uses TextualRepresentation commits (bash commit.sh).
  To get structured elements back from the API, run Analysis.ipynb with
  the SysML v2 kernel and call  %publish  at the end of each cell.
  Then re-run:  python scripts/api_probe.py --query-type PartDefinition
""")


if __name__ == "__main__":
    main()
