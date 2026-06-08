"""
diagram_gen.py — Visual diagram generator for the SysML v2 verification engine.

Generates three diagrams from the parsed .sysml model files using NetworkX + matplotlib:

  1. system_topology.png    — Parts as nodes, connect statements as directed edges
  2. requirement_status.png — Requirements (green=SATISFIED, red=VIOLATED) linked to
                              the component instances they constrain
  3. traceability.png       — Requirements ↔ UCAs ↔ FMEA failure modes

Output directory: bilgepump/docs/   (created if absent)

Dependencies: networkx, matplotlib  (both in requirements.txt)
"""

from __future__ import annotations

import os
import re
from pathlib import Path


# ---------------------------------------------------------------------------
# Optional dependency guard — diagram_gen is never on the critical path
# ---------------------------------------------------------------------------

def _check_deps() -> bool:
    try:
        import networkx  # noqa: F401
        import matplotlib  # noqa: F401
        return True
    except ImportError as exc:
        print(f"  WARNING: diagram generation skipped — {exc}")
        print("  Install: pip install networkx matplotlib")
        return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _strip_comments(text: str) -> str:
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    text = re.sub(r'//[^\n]*', '', text)
    return text


def _read(path: str | Path) -> str:
    with open(path, encoding='utf-8') as fh:
        return fh.read()


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def _parse_parts(arch_path: str) -> list[tuple[str, str]]:
    """
    Parse 'part <name> : <TypeDef>;' lines from Architecture.sysml.
    Returns list of (instance_name, type_name) tuples.
    """
    raw   = _read(arch_path)
    clean = _strip_comments(raw)
    parts = []
    for m in re.finditer(r'\bpart\s+(\w+)\s*:\s*(\w+)\s*;', clean):
        parts.append((m.group(1), m.group(2)))
    return parts


def _parse_connections(arch_path: str) -> list[tuple[str, str, str]]:
    """
    Parse 'connect <a>.<port> to <b>.<port>;' from Architecture.sysml.
    Returns list of (source_instance, target_instance, label) tuples.
    """
    raw   = _read(arch_path)
    clean = _strip_comments(raw)
    conns = []
    for m in re.finditer(
        r'\bconnect\s+([\w.]+)\s+to\s+([\w.]+)\s*;', clean
    ):
        src_full = m.group(1)  # e.g. "sensor.levelOut"
        tgt_full = m.group(2)  # e.g. "controller.levelIn"
        src_inst = src_full.split('.')[0]
        tgt_inst = tgt_full.split('.')[0]
        label    = f"{src_full.split('.',1)[-1] if '.' in src_full else ''}"
        conns.append((src_inst, tgt_inst, label))
    return conns


def _parse_requirement_subjects(req_paths: list[str]) -> dict[str, list[str]]:
    """
    Parse 'require constraint { sys.<component>.<attr> ... }' from requirement defs.
    Returns {req_name: [component_instance, ...]}
    """
    index: dict[str, list[str]] = {}
    for path in req_paths:
        if not os.path.exists(path):
            continue
        raw   = _read(path)
        clean = _strip_comments(raw)
        for m in re.finditer(
            r'requirement\s+def\s+(\w+).*?require\s+constraint\s*\{([^}]+)\}',
            clean,
            re.DOTALL,
        ):
            name = m.group(1)
            expr = m.group(2)
            components = list(dict.fromkeys(re.findall(r'sys\.(\w+)\.', expr)))
            if components:
                index[name] = components
    return index


def _parse_ucas(safety_path: str) -> list[dict]:
    if not os.path.exists(safety_path):
        return []
    raw   = _read(safety_path)
    clean = _strip_comments(raw)
    ucas  = []
    for block_m in re.finditer(r'#UCA\s*\{([^}]+)\}', clean, re.DOTALL):
        block = block_m.group(1)
        entry = {}
        for field in ('ucaId', 'controlAction', 'guideword', 'hazardRefs', 'failureModeLink'):
            fm = re.search(rf'{field}\s*=\s*"([^"]*)"', block)
            if fm:
                entry[field] = fm.group(1)
        if entry.get('ucaId'):
            ucas.append(entry)
    return ucas


def _parse_fmea_modes(fmea_path: str) -> list[dict]:
    if not os.path.exists(fmea_path):
        return []
    raw   = _read(fmea_path)
    clean = _strip_comments(raw)
    modes = []
    for block_m in re.finditer(r'#FailureMode\s*\{([^}]+)\}', clean, re.DOTALL):
        block = block_m.group(1)
        entry: dict = {}
        for field in ('fmId', 'component', 'instance', 'ucaRef'):
            fm = re.search(rf'{field}\s*=\s*"([^"]*)"', block)
            if fm:
                entry[field] = fm.group(1)
        for field in ('rpn',):
            fm = re.search(rf'{field}\s*=\s*([0-9]+)', block)
            if fm:
                entry[field] = int(fm.group(1))
        if entry.get('fmId'):
            modes.append(entry)
    return modes


# ---------------------------------------------------------------------------
# Diagram 1: System Topology
# ---------------------------------------------------------------------------

def _diagram_system_topology(
    parts: list[tuple[str, str]],
    connections: list[tuple[str, str, str]],
    out_path: str,
) -> None:
    import networkx as nx
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches

    # Color by subsystem role
    role_colors: dict[str, str] = {
        'sensor':     '#4FC3F7',   # light blue
        'controller': '#81C784',   # green
        'power':      '#FFD54F',   # amber
        'pumpA':      '#64B5F6',   # blue
        'pumpB':      '#90CAF9',   # lighter blue
        'discharge':  '#A5D6A7',   # light green
        'alarm':      '#EF9A9A',   # red-ish
        'ui':         '#CE93D8',   # purple
    }

    G = nx.DiGraph()
    for inst, type_name in parts:
        G.add_node(inst, type=type_name)
    for src, tgt, label in connections:
        if src != tgt:
            if G.has_edge(src, tgt):
                G[src][tgt]['label'] += f'\n{label}' if label else ''
            else:
                G.add_edge(src, tgt, label=label)

    fig, ax = plt.subplots(figsize=(14, 9))
    pos = nx.spring_layout(G, seed=42, k=2.5)

    node_colors = [role_colors.get(n, '#BDBDBD') for n in G.nodes()]
    nx.draw_networkx_nodes(G, pos, ax=ax, node_color=node_colors,
                           node_size=2200, alpha=0.92)
    nx.draw_networkx_labels(G, pos, ax=ax, font_size=9, font_weight='bold')
    nx.draw_networkx_edges(G, pos, ax=ax, edge_color='#546E7A',
                           arrows=True, arrowsize=18, width=1.5,
                           connectionstyle='arc3,rad=0.08')
    edge_labels = {(s, t): d['label'] for s, t, d in G.edges(data=True) if d.get('label')}
    nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, ax=ax,
                                  font_size=6.5, label_pos=0.35)

    # Type legend
    type_map = dict(parts)
    legend_entries = [
        mpatches.Patch(color=role_colors.get(inst, '#BDBDBD'),
                       label=f"{inst} : {type_map.get(inst, '')}")
        for inst, _ in parts
    ]
    ax.legend(handles=legend_entries, loc='lower left', fontsize=7.5,
              framealpha=0.8, title='Part instances')

    ax.set_title('BilgePump System — Architecture Topology', fontsize=13, fontweight='bold')
    ax.axis('off')
    fig.tight_layout()
    fig.savefig(out_path, dpi=140, bbox_inches='tight')
    plt.close(fig)


# ---------------------------------------------------------------------------
# Diagram 2: Requirement Satisfaction Status
# ---------------------------------------------------------------------------

def _diagram_requirement_status(
    req_subjects: dict[str, list[str]],
    results: list[dict],           # [{requirement, satisfied}, ...]
    out_path: str,
) -> None:
    import networkx as nx
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    status_map = {r['requirement']: r['satisfied'] for r in results}

    G = nx.DiGraph()

    # Add requirement nodes
    for req_name in req_subjects:
        sat = status_map.get(req_name)
        color = '#66BB6A' if sat is True else '#EF5350' if sat is False else '#FFA726'
        G.add_node(req_name, node_type='requirement', color=color)

    # Add component nodes and edges
    all_components: set[str] = set()
    for req_name, comps in req_subjects.items():
        for comp in comps:
            all_components.add(comp)
            G.add_edge(req_name, comp)

    for comp in all_components:
        G.add_node(comp, node_type='component', color='#90CAF9')

    req_nodes  = [n for n, d in G.nodes(data=True) if d.get('node_type') == 'requirement']
    comp_nodes = [n for n, d in G.nodes(data=True) if d.get('node_type') == 'component']

    fig, ax = plt.subplots(figsize=(13, 8))

    # Two-tier layout: requirements top, components bottom
    n_req  = len(req_nodes)
    n_comp = len(comp_nodes)
    pos = {}
    for i, r in enumerate(req_nodes):
        pos[r] = ((i + 0.5) / n_req, 0.75)
    for i, c in enumerate(comp_nodes):
        pos[c] = ((i + 0.5) / max(n_comp, 1), 0.25)

    req_colors  = [G.nodes[n]['color'] for n in req_nodes]
    comp_colors = [G.nodes[n]['color'] for n in comp_nodes]

    nx.draw_networkx_nodes(G, pos, nodelist=req_nodes, ax=ax,
                           node_color=req_colors, node_size=2800, node_shape='s')
    nx.draw_networkx_nodes(G, pos, nodelist=comp_nodes, ax=ax,
                           node_color=comp_colors, node_size=1800)
    nx.draw_networkx_labels(G, pos, ax=ax, font_size=7, font_weight='bold')
    nx.draw_networkx_edges(G, pos, ax=ax, edge_color='#546E7A',
                           arrows=True, arrowsize=14, width=1.2,
                           connectionstyle='arc3,rad=0.0')

    import matplotlib.patches as mpatches
    legend_handles = [
        mpatches.Patch(color='#66BB6A', label='SATISFIED'),
        mpatches.Patch(color='#EF5350', label='VIOLATED'),
        mpatches.Patch(color='#FFA726', label='UNKNOWN'),
        mpatches.Patch(color='#90CAF9', label='Component'),
    ]
    ax.legend(handles=legend_handles, loc='upper right', fontsize=8)
    ax.set_title('Requirement Satisfaction Status', fontsize=13, fontweight='bold')
    ax.axis('off')
    fig.tight_layout()
    fig.savefig(out_path, dpi=140, bbox_inches='tight')
    plt.close(fig)


# ---------------------------------------------------------------------------
# Diagram 3: Traceability (Requirements ↔ UCAs ↔ FMEA)
# ---------------------------------------------------------------------------

def _diagram_traceability(
    req_subjects: dict[str, list[str]],
    ucas: list[dict],
    fmea_modes: list[dict],
    results: list[dict],
    out_path: str,
) -> None:
    import networkx as nx
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches

    status_map = {r['requirement']: r['satisfied'] for r in results}
    G = nx.DiGraph()

    # Requirements
    for req_name in req_subjects:
        sat   = status_map.get(req_name)
        color = '#66BB6A' if sat is True else '#EF5350' if sat is False else '#FFA726'
        G.add_node(f"REQ:{req_name}", node_type='req', color=color,
                   label=req_name.replace('Requirement', '\nReq'))

    # UCAs
    for uca in ucas:
        uid = uca.get('ucaId', '')
        if uid:
            G.add_node(f"UCA:{uid}", node_type='uca', color='#FFB74D',
                       label=f"{uid}\n{uca.get('guideword','')[:18]}")

    # FMEA
    for fm in fmea_modes:
        fid = fm.get('fmId', '')
        if fid:
            rpn = fm.get('rpn', '')
            G.add_node(f"FM:{fid}", node_type='fm', color='#EF9A9A',
                       label=f"{fid}\nRPN={rpn}")

    # Edges: REQ → UCA (via component name matching)
    for req_name, comps in req_subjects.items():
        req_node = f"REQ:{req_name}"
        for uca in ucas:
            ca = uca.get('controlAction', '').lower()
            for comp in comps:
                if comp.lower().replace('pump', '') in ca or comp.lower() in ca:
                    uca_node = f"UCA:{uca['ucaId']}"
                    if G.has_node(uca_node):
                        G.add_edge(req_node, uca_node, color='#546E7A')
                    break

    # Edges: UCA → FMEA
    uca_id_map = {u.get('ucaId', ''): u for u in ucas}
    for fm in fmea_modes:
        uca_ref = fm.get('ucaRef', '')
        fm_node = f"FM:{fm['fmId']}"
        if uca_ref and uca_ref in uca_id_map and G.has_node(fm_node):
            G.add_edge(f"UCA:{uca_ref}", fm_node, color='#B71C1C')

    # Three-tier layout
    req_nodes = [n for n, d in G.nodes(data=True) if d.get('node_type') == 'req']
    uca_nodes = [n for n, d in G.nodes(data=True) if d.get('node_type') == 'uca']
    fm_nodes  = [n for n, d in G.nodes(data=True) if d.get('node_type') == 'fm']

    pos = {}
    def _spread(nodes: list, y: float) -> None:
        n = len(nodes)
        for i, node in enumerate(nodes):
            pos[node] = ((i + 0.5) / max(n, 1), y)

    _spread(req_nodes, 0.85)
    _spread(uca_nodes, 0.50)
    _spread(fm_nodes,  0.15)

    if not pos:
        # Nothing to draw
        return

    fig, ax = plt.subplots(figsize=(16, 10))

    def _draw_tier(nodes: list, shape: str = 'o') -> None:
        if not nodes:
            return
        colors = [G.nodes[n].get('color', '#BDBDBD') for n in nodes]
        nx.draw_networkx_nodes(G, pos, nodelist=nodes, ax=ax,
                               node_color=colors, node_size=2200,
                               node_shape=shape)

    _draw_tier(req_nodes, 's')
    _draw_tier(uca_nodes, 'D')
    _draw_tier(fm_nodes,  'o')

    labels = {n: G.nodes[n].get('label', n.split(':', 1)[-1]) for n in G.nodes()}
    nx.draw_networkx_labels(G, pos, labels=labels, ax=ax, font_size=6.5)

    edge_colors = [G.edges[e].get('color', '#9E9E9E') for e in G.edges()]
    nx.draw_networkx_edges(G, pos, ax=ax, edge_color=edge_colors,
                           arrows=True, arrowsize=14, width=1.3,
                           connectionstyle='arc3,rad=0.05')

    legend_handles = [
        mpatches.Patch(color='#66BB6A', label='Requirement (SATISFIED)'),
        mpatches.Patch(color='#EF5350', label='Requirement (VIOLATED)'),
        mpatches.Patch(color='#FFA726', label='Requirement (UNKNOWN)'),
        mpatches.Patch(color='#FFB74D', label='UCA (Unsafe Control Action)'),
        mpatches.Patch(color='#EF9A9A', label='FMEA Failure Mode'),
    ]
    ax.legend(handles=legend_handles, loc='lower right', fontsize=7.5)

    # Tier labels
    ax.text(0.01, 0.87, 'Requirements', transform=ax.transAxes,
            fontsize=9, color='#37474F', fontweight='bold')
    ax.text(0.01, 0.52, 'UCAs', transform=ax.transAxes,
            fontsize=9, color='#37474F', fontweight='bold')
    ax.text(0.01, 0.17, 'FMEA Failure Modes', transform=ax.transAxes,
            fontsize=9, color='#37474F', fontweight='bold')

    ax.set_title('Safety Traceability — Requirements ↔ UCAs ↔ FMEA',
                 fontsize=13, fontweight='bold')
    ax.axis('off')
    fig.tight_layout()
    fig.savefig(out_path, dpi=140, bbox_inches='tight')
    plt.close(fig)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_all(
    repo_root: str,
    all_layer_paths: list[str],
    results: list[dict],
    out_dir: str | None = None,
) -> list[str]:
    """
    Generate all three diagrams and return list of output file paths.

    Args:
        repo_root:        Absolute path to the repository root.
        all_layer_paths:  All layer files (relative to repo_root).
        results:          Verification results [{requirement, satisfied}, ...].
        out_dir:          Output directory (default: <first_layer_dir>/docs/).

    Returns:
        List of absolute paths to generated PNG files.
    """
    if not _check_deps():
        return []

    # Derive output directory from first layer path
    if out_dir is None:
        first_layer = all_layer_paths[0] if all_layer_paths else ''
        layer_dir   = os.path.dirname(os.path.join(repo_root, first_layer))
        out_dir     = os.path.join(layer_dir, 'docs')

    os.makedirs(out_dir, exist_ok=True)

    # Locate key files
    def _find_layer(keyword: str) -> str | None:
        for p in all_layer_paths:
            if keyword in p.lower():
                return os.path.join(repo_root, p)
        return None

    arch_path   = _find_layer('architecture')
    safety_path = _find_layer('safety')
    fmea_path   = _find_layer('fmea')
    req_paths   = [
        os.path.join(repo_root, p) for p in all_layer_paths
        if 'requirements' in p.lower() or 'safety' in p.lower()
    ]

    generated = []

    # --- Diagram 1: System Topology ---
    if arch_path and os.path.exists(arch_path):
        out1 = os.path.join(out_dir, 'system_topology.png')
        try:
            parts       = _parse_parts(arch_path)
            connections = _parse_connections(arch_path)
            _diagram_system_topology(parts, connections, out1)
            generated.append(out1)
            print(f"  ✓ system_topology.png  ({len(parts)} parts, {len(connections)} connections)")
        except Exception as exc:
            print(f"  ✗ system_topology.png  failed: {exc}")

    # --- Diagram 2: Requirement Status ---
    req_subjects = _parse_requirement_subjects(req_paths)
    if req_subjects:
        out2 = os.path.join(out_dir, 'requirement_status.png')
        try:
            _diagram_requirement_status(req_subjects, results, out2)
            generated.append(out2)
            n_sat = sum(1 for r in results if r.get('satisfied') is True)
            n_vio = sum(1 for r in results if r.get('satisfied') is False)
            print(f"  ✓ requirement_status.png  ({n_sat} SATISFIED, {n_vio} VIOLATED)")
        except Exception as exc:
            print(f"  ✗ requirement_status.png  failed: {exc}")

    # --- Diagram 3: Traceability ---
    ucas       = _parse_ucas(safety_path)  if safety_path else []
    fmea_modes = _parse_fmea_modes(fmea_path) if fmea_path else []
    if req_subjects and (ucas or fmea_modes):
        out3 = os.path.join(out_dir, 'traceability.png')
        try:
            _diagram_traceability(req_subjects, ucas, fmea_modes, results, out3)
            generated.append(out3)
            print(f"  ✓ traceability.png  ({len(ucas)} UCAs, {len(fmea_modes)} FMEA modes)")
        except Exception as exc:
            print(f"  ✗ traceability.png  failed: {exc}")

    return generated
