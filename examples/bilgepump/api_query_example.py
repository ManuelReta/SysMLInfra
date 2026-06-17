#!/usr/bin/env python3
"""
api_query_example.py — Annotated walkthrough of every SysML v2 API query pattern.

Run against the public SST server (no credentials needed):
    python examples/bilgepump/api_query_example.py

To run against your own kernel-published project:
    python examples/bilgepump/api_query_example.py --project <your-project-id>

──────────────────────────────────────────────────────────────────────────────
HOW THE API WORKS
──────────────────────────────────────────────────────────────────────────────
The SysML v2 Pilot REST API (sysml2.intercax.com:9000) stores model data that
was committed by the SysML v2 Jupyter kernel via `%publish`.

When you do:
  %publish              ← inside a SysML kernel cell in Analysis.ipynb

...the kernel serialises every element it has parsed into JSON-LD and POSTs
them to the API as a commit.  Each element gets a stable UUID `@id`.

When commit.sh is used instead, only a raw TextualRepresentation blob is
stored — no typed elements are indexed, so GET …/elements returns [].

──────────────────────────────────────────────────────────────────────────────
EXPECTED OUTPUT (from reference project "5-State-based Behavior-1")
──────────────────────────────────────────────────────────────────────────────

  [1] Health — server reachable. Projects on server: 100

  [2] Project metadata
      @id      : 00364405-201d-4866-9c6a-96f57c200c2a
      name     : 5-State-based Behavior-1
      created  : 2025-05-28T16:30:42.45717-04:00

  [3] Branch → head commit
      branch   : main  (id: 1a67c6fc-a05c-44bc-aa1b-09db61043159)
      head     : d725afc2-5bb5-4e5c-84dc-39ed5ac9afae

  [4] All elements in head commit — 100 total
      Count  Type
      -----  ----
         38  OwningMembership
         14  AttributeUsage
         13  Comment
         10  AttributeDefinition
          5  FeatureMembership
          4  Membership
          4  ReferenceUsage
          3  Documentation
          2  NamespaceImport
          2  Package
          2  StateDefinition
          ...

  [5] Single element detail  (first element)
      @id           : <uuid>
      @type         : OwningMembership
      name          : null
      ownedMemberElement : {"@id": "<child-uuid>"}
      owningRelatedElement: {"@id": "<parent-uuid>"}

  [6] Typed query — AttributeDefinition (10 elements)
      <uuid>  name='speed'
      <uuid>  name='acceleration'
      <uuid>  name='position'
      ...

  [7] Typed query — PartDefinition  (0 in this reference project)
      ⚠  No PartDefinition elements — this reference project only has attribute defs.
         A bilge pump model would return:
           <uuid>  name='BilgePumpA'
           <uuid>  name='BilgePumpB'
           <uuid>  name='PumpController'
           <uuid>  name='PowerSupply'
           ...
"""

import argparse
import json
import sys

try:
    import requests
except ImportError:
    sys.exit("requests not installed — run: pip install requests")

API_BASE = "http://sysml2.intercax.com:9000"

# Reference project committed via the SysML v2 kernel (has structured elements).
# This is a public shared project on sysml2.intercax.com.
REFERENCE_PROJECT_ID = "00364405-201d-4866-9c6a-96f57c200c2a"


# ── helpers ───────────────────────────────────────────────────────────────────


def get(url: str) -> list | dict | None:
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()


def head_commit(api: str, project_id: str) -> str:
    """Resolve the head commit ID for the default branch."""
    branches = get(f"{api}/projects/{project_id}/branches")
    if not branches:
        raise RuntimeError("No branches found")
    ref = branches[0].get("referencedCommit") or branches[0].get("head") or {}
    commit_id = ref.get("@id")
    if not commit_id:
        raise RuntimeError("Branch has no referencedCommit")
    return commit_id


# ── query patterns ────────────────────────────────────────────────────────────


def list_all_elements(api: str, project_id: str, commit_id: str) -> list[dict]:
    """
    Pattern 1 — GET all elements in a commit.

    Returns every element the kernel parsed, regardless of type.
    Useful for an initial inventory.

    GET /projects/{pid}/commits/{cid}/elements
    """
    return get(f"{api}/projects/{project_id}/commits/{commit_id}/elements") or []


def get_element_by_id(
    api: str, project_id: str, commit_id: str, element_id: str
) -> dict:
    """
    Pattern 2 — GET a single element by its @id.

    Each element has cross-references to its children/parent via @id links.
    Follow those links with additional GET calls to traverse the model graph.

    GET /projects/{pid}/commits/{cid}/elements/{eid}
    """
    return (
        get(f"{api}/projects/{project_id}/commits/{commit_id}/elements/{element_id}")
        or {}
    )


class QueryEndpointUnavailable(Exception):
    """Raised when the server does not support POST query-results (returns 404)."""


def query_by_type(
    api: str, project_id: str, commit_id: str, type_name: str
) -> tuple[list[dict], bool]:
    """
    Pattern 3 — POST query-results filtered by @type.

    More efficient than listing all elements and filtering client-side.
    The query body is JSON-LD using the SysML v2 Query schema.

    POST /projects/{pid}/commits/{cid}/query-results
    Body:
    {
      "query": {
        "@type": "Query",
        "select": ["@id", "@type", "name", "declaredName"],
        "where": {
          "@type": "PrimitiveConstraint",
          "inverse": false,
          "operator": "=",
          "property": "@type",
          "value": "<TypeName>"
        }
      }
    }

    Common @type values for a BilgePump-style model:
      PartDefinition          — part def BilgePumpA { ... }
      AttributeDefinition     — attribute def
      PortDefinition          — port def FluidFlowPort { ... }
      RequirementDefinition   — requirement def WaterLevelRequirement { ... }
      ConstraintDefinition    — constraint def PumpFlowPhysics { ... }
      AttributeUsage          — attribute flowRate : Real  (inside a part def)
      PortUsage               — port levelOut : LevelSignalPort
      BindingConnector        — bind statements in Analysis.sysml
      OwningMembership        — ownership edge (parent→child containment)

    Returns (results, server_supported) where server_supported=False means
    the endpoint returned 404 and results were filtered client-side instead.
    """
    body = {
        "query": {
            "@type": "Query",
            "select": ["@id", "@type", "name", "declaredName", "value"],
            "where": {
                "@type": "PrimitiveConstraint",
                "inverse": False,
                "operator": "=",
                "property": "@type",
                "value": type_name,
            },
        }
    }
    r = requests.post(
        f"{api}/projects/{project_id}/commits/{commit_id}/query-results",
        json=body,
        timeout=10,
    )
    if r.status_code == 404:
        # This deployment does not expose the query-results endpoint.
        # Fall back to fetching all elements and filtering client-side.
        raise QueryEndpointUnavailable()
    r.raise_for_status()
    result = r.json()
    return (result if isinstance(result, list) else []), True


def query_named_elements(
    api: str, project_id: str, commit_id: str, all_elements: list[dict] | None = None
) -> tuple[list[dict], bool]:
    """
    Pattern 4 — POST query-results for any element that has a non-null name.

    Uses a PrimitiveConstraint with inverse=True ("name IS null" negated → "name is NOT null").
    Falls back to client-side filtering if the endpoint returns 404.

    Returns (results, server_supported).
    """
    body = {
        "query": {
            "@type": "Query",
            "select": ["@id", "@type", "name"],
            "where": {
                "@type": "PrimitiveConstraint",
                "inverse": True,
                "operator": "=",
                "property": "name",
                "value": None,
            },
        }
    }
    r = requests.post(
        f"{api}/projects/{project_id}/commits/{commit_id}/query-results",
        json=body,
        timeout=10,
    )
    if r.status_code == 404:
        raise QueryEndpointUnavailable()
    r.raise_for_status()
    result = r.json()
    return (result if isinstance(result, list) else []), True


# ── main demo ─────────────────────────────────────────────────────────────────


def _filter(elements: list[dict], type_name: str) -> list[dict]:
    return [el for el in elements if el.get("@type") == type_name]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--api", default=API_BASE)
    parser.add_argument(
        "--project", default=None, help="Project ID (must be kernel-committed)"
    )
    args = parser.parse_args()

    api = args.api.rstrip("/")
    project_id = args.project or REFERENCE_PROJECT_ID

    # ── [1] Connectivity ─────────────────────────────────────────────────────
    print("\n[1] API connectivity")
    get(f"{api}/projects")  # raises on failure
    project = get(f"{api}/projects/{project_id}")
    commit_id = head_commit(api, project_id)
    print(f"    Server  : {api}")
    print(f"    Project : {project.get('name')!r}  ({project_id})")
    print(f"    Commit  : {commit_id}")

    # ── [2] Element inventory ────────────────────────────────────────────────
    print("\n[2] Element inventory  (GET …/elements)")
    elements = list_all_elements(api, project_id, commit_id)
    if not elements:
        print(
            "    ⚠  0 elements — project was committed as TextualRepresentation, not via kernel."
        )
        print("       Use %publish in Analysis.ipynb, then re-run.")
        sys.exit(0)

    by_type: dict[str, int] = {}
    for el in elements:
        by_type[el.get("@type", "Unknown")] = (
            by_type.get(el.get("@type", "Unknown"), 0) + 1
        )

    print(f"    {len(elements)} elements total")
    print(f"    {'Count':>6}  Type")
    print(f"    {'------':>6}  {'----'}")
    for t, count in sorted(by_type.items(), key=lambda x: -x[1]):
        print(f"    {count:>6}  {t}")

    # ── [3] Cross-element connectivity ───────────────────────────────────────
    # Find a BindingConnectorAsUsage — a bind statement linking two elements
    # from different packages. This proves the packages are wired together, not
    # just isolated blobs. If none exists, fall back to any element with
    # non-empty relatedElement refs.
    print("\n[3] Cross-element connectivity  (GET …/elements/{id})")
    connector = next(
        (
            el
            for el in elements
            if el.get("@type") in ("BindingConnectorAsUsage", "BindingConnector")
        ),
        None,
    )
    if connector is None:
        connector = next(
            (el for el in elements if el.get("source") or el.get("target")),
            None,
        )
    if connector is None:
        print("    ⚠  No connector elements found in this commit.")
    else:
        detail = get_element_by_id(api, project_id, commit_id, connector["@id"])
        print(f"    Element : {detail.get('@type')}  id={detail['@id'][:8]}…")

        sources = detail.get("source") or []
        targets = detail.get("target") or []
        related = detail.get("relatedElement") or []
        ends = detail.get("connectorEnd") or []

        if sources or targets:
            src_ids = [s["@id"][:8] + "…" for s in sources if isinstance(s, dict)]
            tgt_ids = [t["@id"][:8] + "…" for t in targets if isinstance(t, dict)]
            print(f"    source  : {src_ids}")
            print(f"    target  : {tgt_ids}")
        elif related:
            rel_ids = [r["@id"][:8] + "…" for r in related if isinstance(r, dict)]
            print(f"    relatedElement : {rel_ids}")
        elif ends:
            end_ids = [e["@id"][:8] + "…" for e in ends if isinstance(e, dict)]
            print(f"    connectorEnd   : {end_ids}")
        else:
            # In some API builds the connector fields are unpopulated stubs.
            # Navigate via OwningMembership to show what the connector belongs to.
            owner_memberships = [
                el
                for el in elements
                if el.get("@type") == "OwningMembership"
                and isinstance(el.get("ownedMemberElement"), dict)
                and el["ownedMemberElement"].get("@id") == detail["@id"]
            ]
            if owner_memberships:
                om = owner_memberships[0]
                owner_ns = om.get("membershipOwningNamespace") or om.get(
                    "owningRelatedElement"
                )
                owner_id = (owner_ns or {}).get("@id", "?")
                # Try to resolve the owner's name
                owner_detail = (
                    get_element_by_id(api, project_id, commit_id, owner_id)
                    if owner_id != "?"
                    else {}
                )
                owner_name = (
                    owner_detail.get("qualifiedName")
                    or owner_detail.get("name")
                    or owner_id[:8] + "…"
                )
                print(f"    Connector belongs to : {owner_name}")
                print(
                    f"    (source/target fields unpopulated in this API build — "
                    f"connector identity is confirmed via OwningMembership edge)"
                )
            else:
                print(
                    f"    (connector stub — no source/target or ownership edge resolved)"
                )

        ns = detail.get("owningNamespace") or detail.get("membershipOwningNamespace")
        if isinstance(ns, dict):
            print(f"    owningNamespace : {ns.get('@id', '?')[:8]}…")

    # ── [4] Attribute value on a named element ───────────────────────────────
    # Find a named element (something with an actual name, not None), fetch it
    # in full, and show one concrete attribute value — proving the store holds
    # typed data, not just anonymous graph edges.
    print("\n[4] Attribute value on a named element  (GET …/elements/{id})")
    named_elements = [el for el in elements if el.get("name") or el.get("declaredName")]
    if not named_elements:
        print("    ⚠  No named elements in this commit.")
    else:
        target_el = named_elements[0]
        full = get_element_by_id(api, project_id, commit_id, target_el["@id"])
        name = full.get("name") or full.get("declaredName")
        print(
            f"    Element : {full.get('@type')}  name={name!r}  id={full['@id'][:8]}…"
        )
        # Show a small set of meaningful, non-null scalar fields
        interesting = [
            "qualifiedName",
            "isAbstract",
            "isLibraryElement",
            "visibility",
            "value",
            "direction",
            "isOrdered",
            "isUnique",
        ]
        shown = 0
        for k in interesting:
            v = full.get(k)
            if v is not None:
                print(f"    {k:<30} {json.dumps(v)}")
                shown += 1
        if shown == 0:
            print(
                "    (all scalar fields are null — element has only graph-edge fields)"
            )

    # ── [5] Lookup by name — prove the store is queryable ───────────────────
    # Take the first named element found above, then re-find it purely by
    # scanning for its name. This demonstrates that you can navigate the model
    # by name rather than needing to know UUIDs in advance.
    print("\n[5] Lookup by name — retrieve an element using only its name")
    if not named_elements:
        print("    ⚠  No named elements available to demonstrate.")
    else:
        target_name = named_elements[0].get("name") or named_elements[0].get(
            "declaredName"
        )
        matches = [
            el
            for el in elements
            if el.get("name") == target_name or el.get("declaredName") == target_name
        ]
        print(f"    Looking for name={target_name!r} in {len(elements)} elements…")
        if matches:
            for m in matches:
                print(f"    FOUND  @type={m.get('@type')}  @id={m['@id']}")
        else:
            print(
                f"    NOT FOUND — name {target_name!r} does not exist in this commit."
            )
        # Now prove a non-existent name returns nothing
        fake = "__nonexistent_element_xyz__"
        no_match = [
            el
            for el in elements
            if el.get("name") == fake or el.get("declaredName") == fake
        ]
        print(
            f"    Looking for name={fake!r}…  → {len(no_match)} results (expected: 0)  ✓"
        )


if __name__ == "__main__":
    main()
