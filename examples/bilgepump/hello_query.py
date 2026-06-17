"""
hello_query.py — BilgePump SysML v2 REST API query demo
========================================================

Demonstrates:
  1. How to load multiple related SysML packages from the API
  2. How cross-project references work (Architecture → Library UUIDs)
  3. How to build a merged element registry to resolve those references

Cross-project reference model
------------------------------
When the kernel publishes each package as a separate project, elements that
reference types from another package use bare @id pointers — the same UUID
the defining element has in its own project.  The API has NO automatic
cross-project resolution; a client must:

  a) know the project-ID map  (see lib/current-project-id.txt)
  b) load elements from all relevant projects into one dict keyed by @id
  c) look up any @id reference in that merged dict regardless of which
     project it originally came from

BilgePump projects on http://sysml2.intercax.com:9000
  Library      : 0171dc68-e78c-41cc-8357-61665f5eface  (type vocabulary)
  Architecture : 8ba46c08-0454-4c15-87db-e56f339add56  (system composition)
  Requirements : c3c22f38-7b1d-4a58-9a87-f7d92f809534  (shall statements)
  Analysis     : f1062694-fa11-4bb1-b372-54446a17b540  (constraint + test defs)

Run
---
    cd /home/manret/SysMLInfra
    source .venv/bin/activate
    python examples/bilgepump/hello_query.py
"""

import requests

API = "http://sysml2.intercax.com:9000"

# Project-ID registry — one entry per published package.
# Architecture imports Library::*, so Architecture elements carry @id references
# that point into the Library project.  The registry lets us resolve them.
PROJECT_REGISTRY = {
    "BilgePump_Library": "0171dc68-e78c-41cc-8357-61665f5eface",
    "BilgePump_Architecture": "8ba46c08-0454-4c15-87db-e56f339add56",
    "BilgePump_Requirements": "c3c22f38-7b1d-4a58-9a87-f7d92f809534",
    "BilgePump_Analysis": "f1062694-fa11-4bb1-b372-54446a17b540",
}


# ── helpers ───────────────────────────────────────────────────────────────────


def head_commit(pid):
    """Return the latest commit @id for a project, or None if no commits."""
    commits = requests.get(f"{API}/projects/{pid}/commits", timeout=15).json()
    return commits[0]["@id"] if commits else None


def load_elements(pid, commit_id, page_size=200):
    """Fetch up to page_size elements from one commit into a dict keyed by @id."""
    r = requests.get(
        f"{API}/projects/{pid}/commits/{commit_id}/elements",
        params={"page[size]": page_size},
        timeout=15,
    )
    return {e["@id"]: e for e in r.json()}


def fetch_one(pid, commit_id, element_id, cache):
    """Return element from cache or fetch it individually (cross-project safe)."""
    if element_id in cache:
        return cache[element_id]
    r = requests.get(
        f"{API}/projects/{pid}/commits/{commit_id}/elements/{element_id}",
        timeout=10,
    )
    if r.status_code == 200:
        el = r.json()
        cache[element_id] = el
        return el
    return None


# ── 1. Build the merged element registry ─────────────────────────────────────
#
#  Load all projects that have commits.  Elements from every package end up
#  in one dict so that any @id reference — regardless of which project it
#  lives in — can be resolved with a single dict lookup.
#
print("Loading BilgePump packages from API...")
print(f"  API: {API}")
print()

merged = {}  # {element_id: element}   — the cross-project registry
project_heads = {}  # {project_name: commit_id}

for pkg_name, pid in PROJECT_REGISTRY.items():
    head = head_commit(pid)
    if head is None:
        print(f"  {pkg_name:<30} — no commits (skipped)")
        continue
    elems = load_elements(pid, head)
    project_heads[pkg_name] = (pid, head)
    merged.update(elems)
    print(f"  {pkg_name:<30} {len(elems):>4} elements  commit={head[:8]}...")

print(f"\nMerged registry: {len(merged)} elements total")


# ── 2. List PartDefinitions from the Library ─────────────────────────────────
#
#  These are the type-vocabulary entries every other package imports.
#  In the Architecture project they appear as FeatureTyping.type → @id,
#  resolved here via the merged registry.
#
part_defs = [
    e
    for e in merged.values()
    if e.get("@type") == "PartDefinition" and e.get("declaredName")
]
print(f"\nPartDefinitions in merged registry ({len(part_defs)}):")
for pd in sorted(part_defs, key=lambda e: e.get("declaredName", "")):
    print(f"  {pd['declaredName']:<25}  id={pd['@id'][:8]}...")


# ── 3. Show attributes of BilgePumpA ─────────────────────────────────────────
#
#  Find the PartDefinition, then collect all AttributeUsage elements whose
#  owner is BilgePumpA.  The owner relationship is a direct @id field.
#
pump_a = next(
    (
        e
        for e in merged.values()
        if e.get("@type") == "PartDefinition" and e.get("declaredName") == "BilgePumpA"
    ),
    None,
)

if pump_a:
    print(f"\nBilgePumpA  (id={pump_a['@id'][:8]}...)")
    attrs = [
        e
        for e in merged.values()
        if e.get("@type") == "AttributeUsage"
        and (e.get("owner") or {}).get("@id") == pump_a["@id"]
    ]
    for a in attrs:
        print(f"  attribute {a.get('declaredName')!r:20}  id={a['@id'][:8]}...")
else:
    print("\nBilgePumpA — not found in merged registry")


# ── 4. Show port definitions ──────────────────────────────────────────────────
#
#  PortDefinitions are the typed connectors.  BilgePumpA has controlIn,
#  powerIn, flowOut — each typed by a PortDefinition from the Library.
#
port_defs = [
    e
    for e in merged.values()
    if e.get("@type") == "PortDefinition" and e.get("declaredName")
]
print(f"\nPortDefinitions ({len(port_defs)}):")
for pd in sorted(port_defs, key=lambda e: e.get("declaredName", "")):
    print(f"  {pd['declaredName']}")


# ── 5. Cross-project reference walkthrough ───────────────────────────────────
#
#  Architecture elements contain FeatureTyping entries whose .type @id
#  points at a Library element UUID.  Because both projects are in `merged`,
#  that reference resolves with a plain dict lookup — no extra HTTP call.
#
#  Example: BilgePumpSystem.sensor  (PartUsage)
#           └─ FeatureTyping.type → @id of BilgeWaterSensor (Library)
#
print("\nCross-project reference demo")
print("  BilgePumpSystem (Architecture) → part types (Library)")

system_def = next(
    (
        e
        for e in merged.values()
        if e.get("@type") == "PartDefinition"
        and e.get("declaredName") == "BilgePumpSystem"
    ),
    None,
)

if system_def:
    part_usages = [
        e
        for e in merged.values()
        if e.get("@type") == "PartUsage"
        and (e.get("owner") or {}).get("@id") == system_def["@id"]
        and e.get("declaredName")
    ]
    for pu in sorted(part_usages, key=lambda e: e.get("declaredName", "")):
        # Walk ownedRelationship to find FeatureTyping
        resolved_type = "?"
        for rel_ref in pu.get("ownedRelationship") or []:
            rid = rel_ref["@id"] if isinstance(rel_ref, dict) else rel_ref
            rel = merged.get(rid)
            if rel and rel.get("@type") == "FeatureTyping":
                type_id = (rel.get("type") or {}).get("@id")
                type_elem = merged.get(type_id)  # resolved via merged registry
                if type_elem:
                    resolved_type = type_elem.get("declaredName", "?")
                break
        print(f"  part {pu.get('declaredName'):<12} : {resolved_type}")
else:
    print("  BilgePumpSystem — not yet in registry")
    print("  (Architecture commits may not be persisted on the public server yet;")
    print("   re-run %publish BilgePump_Architecture in Analysis.ipynb and retry)")


# ── 6. Direct element GET — single attribute by ID ───────────────────────────
#
#  The canonical single-element lookup.  Works even when the element was
#  loaded indirectly via the merged registry.
#
if pump_a and attrs:
    target = attrs[0]
    lib_pid, lib_head = project_heads.get("BilgePump_Library", (None, None))
    if lib_pid and lib_head:
        single = requests.get(
            f"{API}/projects/{lib_pid}/commits/{lib_head}/elements/{target['@id']}",
            timeout=10,
        ).json()
        print(f"\nDirect GET  /projects/.../elements/{single['@id'][:8]}...")
        print(f"  @type        : {single['@type']}")
        print(f"  declaredName : {single.get('declaredName')}")
        print(f"  isVariable   : {single.get('isVariable')}")
